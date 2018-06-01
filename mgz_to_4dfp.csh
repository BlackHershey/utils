#!/bin/csh

if ( ${#argv} < 1 ) then
	echo "Usage: mgz_to_4dfp <imgroot>"
	exit 1
endif

set imgroot = $1

mri_convert ${imgroot}.mgz ${imgroot}.nii --out_orientation RAS
nifti_4dfp -4 ${imgroot}.nii ${imgroot}.4dfp.img

/bin/rm ${imgroot}.mgz
/bin/rm ${imgroot}.nii
