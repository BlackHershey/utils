import argparse
import numpy as np
import os
import re

from glob import glob

DEFAULT_OUTFILE = 'subjects.lst'


def generate_lst(dcm_pattern, sub_regex, ses_regex=None, pad_session=0, outfile=DEFAULT_OUTFILE):
    match_sub = re.compile(sub_regex)
    match_ses = re.compile(ses_regex) if ses_regex else None

    dicoms = [ dcm for pattern in dcm_pattern for dcm in glob(pattern, recursive=False) ]
    # dcm_folders = set([ os.path.dirname(os.path.realpath(f)) for f in dcms])
    # dcm_folders = set([ os.path.dirname(f) for f in dcms])
    real_paths = []
    org_paths = []

    # change this to make a set of dictionaries
    for dcm in dicoms:
        dcm_org_path = os.path.dirname(dcm)
        dcm_real_path = os.path.dirname(os.path.realpath(dcm))
        if not dcm_real_path in real_paths:
            real_paths.append(dcm_real_path)
            org_paths.append(dcm_org_path)

    print(real_paths)
    print(org_paths)

    rows = set()
    for folder, org_path in zip(real_paths,org_paths):
        print('folder = {}'.format(folder))
        folder = re.sub(r'(/)\d+(/DICOM)', r'\1*\2', folder, flags=re.IGNORECASE)
        print('folder after re.sub = {}'.format(folder))
        sub = match_sub.search(org_path).group(1)
        ses = match_ses.search(org_path).group(1) if match_ses else None
        if pad_session and ses.isdigit():
            ses = ses.zfill(pad_session)
        rows.add((folder, sub, ses))

    np.savetxt(outfile, list(rows), fmt='%s', delimiter=',')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dcm-pattern', required=True, nargs='+', help='unix-style pattern to match dcm files for study')
    parser.add_argument('--sub-regex', required=True)
    parser.add_argument('--ses-regex')
    parser.add_argument('--pad-session', nargs=1, type=int, help='length to 0-pad session (if session string is digit)')
    parser.add_argument('--outfile', default=DEFAULT_OUTFILE)
    args = parser.parse_args()

    generate_lst(args.dcm_pattern, args.sub_regex, args.ses_regex, args.pad_session, args.outfile)
