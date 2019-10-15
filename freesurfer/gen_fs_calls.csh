#!/bin/csh

if ( ${#argv} < 3 ) then
	echo "Usage: gen_fs_calls.csh subj_pattern series_desc fs_dir [ flag [flag] ... ]"
	echo "e.g.: gen_fs_calls.csh MPD T1w /data/nil-bluearc/black/MPDP/freesurfer -hires -bigventricles"
	echo "N.B.: base call is to recon-all with -all, -s, -i flags"
	echo "N.B.: subj_pattern can be a partial match from the start of the string"
	echo "N.B.: series_desc can be a partial match anywhere in the string"
	echo "N.B.: fs_dir should be a full path"
	exit 1
endif

set subj_pattern = $1
set series_desc = "$2"
set fs_dir = $3

set flags = ( $argv[4-] )

set subj_dirs = `find . -maxdepth 1 -type d -name "${subj_pattern}*"`
echo $subj_dirs

foreach patid ( $subj_dirs )
	set outfile = ${patid}_fs_call.csh
	if ( -e ${patid}/$outfile ) then
		continue
	endif

	pushd $patid
		set studies_file = `find . -type f -name "*.studies.txt" -prune`
		set dicom_dir = $studies_file:r:r
		set study_num = `cat $studies_file | egrep "${series_desc}" | awk '{print $1}'`

		# if more than one study matching the description is found
		if ( ${#study_num} > 1 ) then

			# try to resolve based on choice of scan in the params file
			if ( -e ${patid}.params ) then
				foreach num ( $study_num )
					set results = `cat ${patid}.params | grep "${num}"`
					if ( ${#results} != 0 ) then
						set study_num = $num
						break
					endif
				end
			endif

			# if no scan number is found in the params that matches the series_desc
			if ( ! ${#results} ) then
				echo "${#study_num} studies matching series_desc found for $patid and unable to choose based on params file"
				exit 1
			endif
		endif

		pushd $dicom_dir
			set dicom_path = `find $PWD -name "*.dcm" | egrep -e "\.${study_num}\.1\." -e "-${study_num}-1-"`
			set fs_str = "recon-all -all -s $patid:t -i $dicom_path $flags"
		popd

		echo setenv SUBJECTS_DIR $fs_dir >> $outfile
		echo $fs_str >> $outfile

	popd
end
