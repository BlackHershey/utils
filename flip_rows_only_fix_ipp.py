#!/usr/bin/env python3
"""
Rows-only (vertical) flip for an entire folder of DICOMs, with correct geometry update.

- Classic single-frame:
    uses (0020,0037) IOP, (0020,0032) IPP, (0028,0030) PixelSpacing.
- Enhanced multi-frame:
    uses Shared and/or Per-Frame Functional Groups as present.
- Pixel operation: flip rows axis ONLY.
- Geometry fix:
    ΔIPP = (Rows-1) * RowSpacing * ColDir
    (RowSpacing == PixelSpacing[0]; ColDir == IOP[3:6])
- IOP unchanged. PatientPosition unchanged (avoid viewer double flips).
- Output: uncompressed Explicit VR Little Endian, fresh SOP Instance UID,
          and fresh SeriesInstanceUID unless --keep-series-uid is provided.
- Non-DICOM or unreadable files are copied unchanged.

Install decoders for compressed PixelData:
    pip install pydicom numpy pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg
    # or: pip install gdcm
"""

import argparse
import os
import shutil
import sys
import traceback
from pathlib import Path

import numpy as np
try:
    import pydicom
except Exception:
    print("Missing dependency 'pydicom'.\nInstall required packages, for example:\n  python -m pip install pydicom numpy pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg\nOr install from the project's requirements.txt:\n  python -m pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)
from pydicom.uid import generate_uid, ExplicitVRLittleEndian


# ------------------------ helpers ------------------------

def _triplet(vals):
    return np.array([float(vals[0]), float(vals[1]), float(vals[2])], dtype=float)

def _dtype_from_bits(bits_alloc, signed):
    if bits_alloc == 8:
        return np.int8 if signed else np.uint8
    if bits_alloc == 16:
        return np.int16 if signed else np.uint16
    if bits_alloc == 32:
        return np.int32 if signed else np.uint32
    raise RuntimeError(f"Unsupported BitsAllocated: {bits_alloc}")

def _get_pf_plane_position(pf_item):
    if "PlanePositionSequence" in pf_item:
        return pf_item.PlanePositionSequence[0]
    if "PlanePositionSlideSequence" in pf_item:
        return pf_item.PlanePositionSlideSequence[0]
    raise RuntimeError("Missing PlanePosition sequence in Per-Frame FG item.")

def _get_row_col_dirs(shared_fg, pf_item_or_none):
    """Return (row_dir, col_dir) 3-vectors from IOP."""
    if shared_fg is not None and "PlaneOrientationSequence" in shared_fg:
        iop = shared_fg.PlaneOrientationSequence[0].ImageOrientationPatient
        return _triplet(iop[:3]), _triplet(iop[3:])
    if pf_item_or_none is not None and "PlaneOrientationSequence" in pf_item_or_none:
        iop = pf_item_or_none.PlaneOrientationSequence[0].ImageOrientationPatient
        return _triplet(iop[:3]), _triplet(iop[3:])
    raise RuntimeError("Missing PlaneOrientationSequence (both Shared and Per-Frame).")

def _get_pixel_spacing(shared_fg, pf_item_or_none):
    """Return (row_spacing, col_spacing) in mm."""
    if shared_fg is not None and "PixelMeasuresSequence" in shared_fg:
        ps = shared_fg.PixelMeasuresSequence[0].PixelSpacing
        return float(ps[0]), float(ps[1])
    if pf_item_or_none is not None and "PixelMeasuresSequence" in pf_item_or_none:
        ps = pf_item_or_none.PixelMeasuresSequence[0].PixelSpacing
        return float(ps[0]), float(ps[1])
    raise RuntimeError("Missing PixelMeasuresSequence/PixelSpacing.")

def _rows_only_delta(rows, row_spacing, col_dir):
    """
    Correct ΔIPP for a rows-only (vertical) flip:
        ΔIPP = (Rows - 1) * RowSpacing * ColDir

    Pixel coordinate mapping (DICOM):
        position = IPP + column * RowDir * ColumnSpacing + row * ColDir * RowSpacing
    Flipping rows maps row -> (Rows-1 - row), so the new IPP should be
    the original pixel at row = Rows-1, giving the delta below.
    """
    return (rows - 1) * row_spacing * np.asarray(col_dir, dtype=float)


def _choose_ipp(ipp, row_dir, col_dir, rows, cols, row_spacing, col_spacing):
    """
    Choose an IPP candidate that best preserves the image center after a rows-only flip.
    Try: no-change, +/- row_dir*(Rows-1)*row_spacing, +/- col_dir*(Rows-1)*row_spacing
    Return the candidate IPP (3-vector) with minimal change in image center position.
    """
    ipp = np.asarray(ipp, dtype=float)
    row_dir = np.asarray(row_dir, dtype=float)
    col_dir = np.asarray(col_dir, dtype=float)

    center_before = ipp + row_dir * ((rows - 1) / 2.0) * row_spacing + col_dir * ((cols - 1) / 2.0) * col_spacing

    candidates = []
    candidates.append(ipp)
    shift = (rows - 1) * row_spacing
    candidates.append(ipp +  shift * row_dir)
    candidates.append(ipp -  shift * row_dir)
    candidates.append(ipp +  shift * col_dir)
    candidates.append(ipp -  shift * col_dir)

    best = None
    best_dist = None
    for c in candidates:
        center_after = c + row_dir * ((rows - 1) / 2.0) * row_spacing + col_dir * ((cols - 1) / 2.0) * col_spacing
        d = np.linalg.norm(center_after - center_before)
        if best is None or d < best_dist: # pyright: ignore[reportOperatorIssue]
            best = c
            best_dist = d

    return best


# ------------------------ per-file processors ------------------------

def process_classic_rows_flip(ds):
    """Flip rows for single-frame, update IPP; return flipped pixel array."""
    rows = int(ds.Rows)
    cols = int(ds.Columns)
    if not hasattr(ds, "ImageOrientationPatient") or not hasattr(ds, "ImagePositionPatient") or not hasattr(ds, "PixelSpacing"):
        raise RuntimeError("Missing IOP/IPP/PixelSpacing.")

    iop = ds.ImageOrientationPatient
    row_dir = _triplet(iop[:3])
    col_dir = _triplet(iop[3:])
    ps = ds.PixelSpacing
    row_spacing = float(ps[0])  # dy

    px = ds.pixel_array  # (R, C) or (R, C, 3) or (3, R, C)
    spp = int(getattr(ds, "SamplesPerPixel", 1))
    if spp == 3 and px.ndim == 3 and px.shape[0] == 3 and px.shape[1] == rows and px.shape[2] == cols:
        # planar configuration 1 -> interleaved
        px = np.transpose(px, (1, 2, 0))

    # Sanity
    if spp == 1 and px.shape != (rows, cols):
        raise RuntimeError(f"Decoded pixel shape {px.shape} != ({rows},{cols})")
    if spp == 3 and px.shape != (rows, cols, 3):
        raise RuntimeError(f"Decoded RGB pixel shape {px.shape} != ({rows},{cols},3)")

    px_out = np.flip(px, axis=0)  # rows axis

    ipp = _triplet(ds.ImagePositionPatient)
    # choose best ipp candidate to preserve image center
    ipp_new = _choose_ipp(ipp, row_dir, col_dir, rows, cols, row_spacing, float(ps[1]))
    ds.ImagePositionPatient = [str(ipp_new[0]), str(ipp_new[1]), str(ipp_new[2])] # pyright: ignore[reportOptionalSubscript]
    return px_out


def process_enhanced_rows_flip(ds):
    """Flip rows for every frame in Enhanced; update per-frame IPP; return flipped pixel stack."""
    rows = int(ds.Rows)
    cols = int(ds.Columns)
    nF = int(ds.NumberOfFrames)

    shared_fg = None
    if hasattr(ds, "SharedFunctionalGroupsSequence") and len(ds.SharedFunctionalGroupsSequence) > 0:
        shared_fg = ds.SharedFunctionalGroupsSequence[0]

    spp = int(getattr(ds, "SamplesPerPixel", 1))
    px = ds.pixel_array  # (F, R, C) or (F, R, C, 3) or (F, 3, R, C)

    if spp == 3 and px.ndim == 4 and px.shape[1] == 3 and px.shape[2] == rows and px.shape[3] == cols:
        # planar configuration 1 -> interleaved
        px = np.transpose(px, (0, 2, 3, 1))

    if spp == 1 and px.shape != (nF, rows, cols):
        raise RuntimeError(f"Decoded pixels {px.shape} != ({nF},{rows},{cols})")
    if spp == 3 and px.shape != (nF, rows, cols, 3):
        raise RuntimeError(f"Decoded RGB pixels {px.shape} != ({nF},{rows},{cols},3)")

    pfs = ds.PerFrameFunctionalGroupsSequence
    if len(pfs) != nF:
        raise RuntimeError("PerFrameFunctionalGroupsSequence length mismatch.")

    px_out = px.copy()
    for k in range(nF):
        pf = pfs[k]
        row_dir, col_dir = _get_row_col_dirs(shared_fg, pf)
        row_spacing, _ = _get_pixel_spacing(shared_fg, pf)

        # Flip rows axis for this frame
        frame = px_out[k]
        frame = np.flip(frame, axis=0)
        px_out[k] = frame

        # Update IPP for this frame
        ipp_item = _get_pf_plane_position(pf)
        ipp = _triplet(ipp_item.ImagePositionPatient)
        ipp_new = _choose_ipp(ipp, row_dir, col_dir, rows, cols, row_spacing, 0.0)
        ipp_item.ImagePositionPatient = [str(ipp_new[0]), str(ipp_new[1]), str(ipp_new[2])] # pyright: ignore[reportOptionalSubscript]

    return px_out


def process_file_rows_flip(in_path: Path, out_path: Path, keep_series_uid: bool = False) -> bool:
    """
    Attempt to process a single DICOM file; returns True if flipped, False if copied unchanged.
    Raises on hard errors (caller will count as fail and copy unchanged).
    """
    ds = pydicom.dcmread(str(in_path))
    if not hasattr(ds, "PixelData"):
        # Not an image or not DICOM with pixels -> copy unchanged
        shutil.copy2(str(in_path), str(out_path))
        return False

    is_enhanced = hasattr(ds, "PerFrameFunctionalGroupsSequence")

    # Do the flip & geometry update (in-place on ds for tags)
    if is_enhanced:
        px_out = process_enhanced_rows_flip(ds)
    else:
        px_out = process_classic_rows_flip(ds)

    # Build output dataset
    new = ds.copy()
    # Always give the output file a fresh SOP Instance UID
    new.SOPInstanceUID = generate_uid()
    # SeriesInstanceUID: only generate a new one if caller explicitly requested it
    if hasattr(new, "SeriesInstanceUID") and keep_series_uid:
        new.SeriesInstanceUID = generate_uid()

    # Make sure we write uncompressed EVR LE
    new.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    new.is_implicit_VR = False
    new.is_little_endian = True

    # Pack PixelData
    bits_alloc = int(new.BitsAllocated)
    signed = int(new.PixelRepresentation) == 1
    dtype = _dtype_from_bits(bits_alloc, signed)

    if np.issubdtype(px_out.dtype, np.floating):
        px_out = np.rint(px_out)
    iinfo = np.iinfo(dtype)
    px_out = np.clip(px_out, iinfo.min, iinfo.max).astype(dtype, copy=False)

    # Keep PlanarConfiguration and descriptive tags unchanged; just replace PixelData
    new.PixelData = np.ascontiguousarray(px_out).tobytes()

    # Save using Explicit VR Little Endian as before (uncompressed)
    new.save_as(str(out_path), write_like_original=False)
    return True


# ------------------------ CLI / folder driver ------------------------

def main():
    ap = argparse.ArgumentParser(description="Flip rows (vertical) for all DICOMs in a folder; fix geometry correctly.")
    ap.add_argument("input_folder", help="Folder containing DICOMs (left untouched).")
    ap.add_argument("--suffix", default="_rowsflip", help="Suffix for output folder name (default: _rowsflip).")
    ap.add_argument("--include-subdirs", action="store_true", help="Process recursively and mirror folder tree.")
    ap.add_argument("--force", action="store_true", help="Overwrite the output folder if it exists.")
    ap.add_argument("--new-series-uid", action="store_true", help="Generate a new SeriesInstanceUID for the flipped files (default: keep original).")
    args = ap.parse_args()

    src = Path(args.input_folder).resolve()
    if not src.exists() or not src.is_dir():
        print(f"ERROR: Input folder not found or not a directory: {src}", file=sys.stderr)
        sys.exit(1)

    outdir = src.with_name(src.name + args.suffix)
    if outdir.exists():
        if args.force:
            shutil.rmtree(outdir)
        else:
            print(f"ERROR: Output folder already exists: {outdir}\nUse --force to overwrite.", file=sys.stderr)
            sys.exit(1)
    outdir.mkdir(parents=True, exist_ok=True)

    total = processed = copied = failed = 0

    def handle_file(in_path: Path, rel_path: Path):
        nonlocal total, processed, copied, failed
        total += 1
        out_path = outdir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            done = process_file_rows_flip(in_path, out_path, keep_series_uid=args.new_series_uid)
            if done:
                processed += 1
            else:
                # if the function chose to copy unchanged
                copied += 1
        except Exception:
            failed += 1
            # fallback: copy unchanged to keep folder mirror complete
            try:
                shutil.copy2(str(in_path), str(out_path))
                copied += 1
            except Exception:
                pass
            print(f"[FAIL] {in_path}", file=sys.stderr)
            traceback.print_exc(limit=1)

    if args.include_subdirs:
        for root, _, files in os.walk(src):
            rel_dir = Path(root).relative_to(src)
            for fname in files:
                handle_file(Path(root) / fname, rel_dir / fname)
    else:
        for f in sorted(src.iterdir()):
            if f.is_dir():
                # mirror subfolders even in flat mode (copy unchanged)
                shutil.copytree(f, outdir / f.name)
                continue
            handle_file(f, Path(f.name))

    print("\n=== Summary ===")
    print(f"Input folder   : {src}")
    print(f"Output folder  : {outdir}")
    print(f"Total files    : {total}")
    print(f"Processed (flipped) : {processed}")
    print(f"Copied unchanged    : {copied}")
    print(f"Failed              : {failed}")

if __name__ == "__main__":
    main()
