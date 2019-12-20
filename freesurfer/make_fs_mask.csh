#!/bin/csh

set scripts_dir = /data/nil-bluearc/black/git/utils

if ( ${#argv} < 4 ) then
	echo 'Usage: make_fs_mask.csh patid fs_seg target region_label region_index [ region_index ... ]'
	echo "N.B.: Should be run from a subject directory"
	echo "N.B: Full paths are required for mpr and fs_seg"
	echo 'N.B.: Mask files will be in atlas/${patid}_<output_root>.4dfp.img'
	exit 1
endif

set patid = $1
set fs_dir = $2:h
set fs_file = $2:r
set target = $3
set label = $4

set region_mask = ${patid}_${label}

set binarize_args = ()
foreach region ( $argv[5-] )
	set binarize_args = ( $binarize_args "--match" $region )
end

pushd atlas
	# create binary mask of region 
	if ( ! -e $region_mask.4dfp.img ) then
		mri_binarize --i ${fs_file}.mgz --o ${region_mask}.mgz $binarize_args
		${scripts_dir}/mgz_to_4dfp.csh $region_mask
	endif

	# convert freesurfer t1 image to 4dfp
	if ( ! -e orig.4dfp.img ) then
		cp ${fs_dir}/orig.mgz .
		${scripts_dir}/mgz_to_4dfp.csh orig
	endif

	# set apply flag if transform already exists
	set mpr = ${patid}_mpr1
	set apply = ""
	if ( -e orig_on_${mpr}.4dfp.img ) then
		set apply = "apply"
	endif

	# transform region mask to atlas space
	freesurfer2mpr_4dfp $mpr orig.4dfp.img -T$target -a$region_mask $apply

popd
