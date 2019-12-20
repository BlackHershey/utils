#!/bin/csh

## Scipt to create shareable BIDS-structured folder 
#   N.B: assumes the defaced data has been converted to BIDS aleady and is stored separate from the raw data (i.e. under derivatives),
#   N.B.: should be run from bids dir
#
#   "anat" folder in the BIDS directory contains original scans and defaced scans are under the "derivatives" folder
#    We've chosen to store it this way because MRIQC is meant to be run on unprocessed images (facemasking may affect IQM estimation)
#
#   In order to share the BIDS-structured data, we need to replace the anat folder with the defaced anat
#
#   Output:
#       new directory "shareable" (under the bids dir) that contain BIDS-structure with symlinks to underlying data, 
#           where anat points to the defaced scans and everything else to the orignal scans 

set bids_dir = $cwd

if ( ! -e shareable ) then
    mkdir shareable
endif

pushd shareable

    cp -as ${bids_dir}/sub-* . # link to original bids sub dirs

    /bin/rm -r sub-*/*/anat  # remove link to original anat folders
    cp -as ${bids_dir}/derivatives/xnat_mask_face/sub-* . # link to defaced anat folder

popd