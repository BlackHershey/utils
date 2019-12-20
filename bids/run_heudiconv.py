import argparse
import numpy as np
import os
import shutil
import stat

from glob import glob
from subprocess import call
from bids_scan_lookup import gen_bids_scan_lut

GENERIC_CONVERTALL_PATH = '/net/zfs-black/BLACK/black/git/utils/bids/config/generic_convertall.py'
BASE_CMD = 'docker run --rm -it --user={uid}:{gid}'.format(uid=os.getuid(), gid=os.getgid())


def run_heudiconv(dcm_dir, sub, ses, convertall=GENERIC_CONVERTALL_PATH, heuristic=None,
					bids_dir=os.getcwd(), redo=False, mriqc=False):
	if not redo and os.path.exists(os.path.join(bids_dir, 'sub-' + sub, 'ses-' + ses)):
		print('subject has already been converted:', sub)
		return

	if not [ f for f in glob(dcm_dir) if not os.path.islink(f) ]:
		print('sub folder does not exist', sub)
		return

	mount_cmd = '-v {}:/data/DICOM -v {}:/out -v {}:/data/convertall.py'.format(dcm_dir, bids_dir, convertall)
	if heuristic:
		mount_cmd += ' -v {}:/data/heuristic.json'.format(heuristic)

	heudiconv_cmd = 'nipy/heudiconv:unstable --files /data/DICOM -f /data/convertall.py -s {sub} {ses} -o /out -b --minmeta --overwrite' \
		.format(sub=sub, ses=(' '.join(['-ss', ses]) if ses else ''))

	cmd_str = ' '.join([BASE_CMD, mount_cmd, heudiconv_cmd])
	print(cmd_str)
	call(cmd_str.split())

	# converted files are read only, so change json file permissions afterwards
	mode = (stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH)
	for f in glob(os.path.join(bids_dir, 'sub-' + sub, '**', '*.json'), recursive=True):
		print(f, mode)
		os.chmod(f, mode)

	if mriqc:
		run_mriqc(bids_dir, sub, ses) # run mriqc for participant


def run_mriqc(bids_dir, sub=None, ses=None):
	mriqc_dir = os.path.join(bids_dir, 'derivatives', 'mriqc')
	if not os.path.exists(mriqc_dir):
		os.makedirs(mriqc_dir)

	mount_cmd = '-v {}:/data -v {}:/out'.format(bids_dir, mriqc_dir)
	mriqc_cmd = 'poldracklab/mriqc:latest /data /out'

	mriqc_opts = []
	if not sub:
		mriqc_opts.append('group')
	else:
		mriqc_opts += [ 'participant', '--participant_label', sub]
		if ses:
			mriqc_opts += ['--session-id', ses]

	cmd_str = ' '.join([BASE_CMD, mount_cmd, mriqc_cmd] + mriqc_opts)
	print(cmd_str)
	call(cmd_str.split())


def deface_anat(bids_dir, sub, ses):
	sourcedata_dir = os.path.join(bids_dir, 'sourcedata')
	if not os.path.exists(sourcedata_dir):
		os.makedirs(sourcedata_dir)

	anat_dir = os.path.join(bids_dir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'anat')
	mprs = sorted(glob(os.path.join(anat_dir, '*T1w.nii.gz')))
	t2ws = glob(os.path.join(anat_dir, '*T2w.nii.gz'))

	# copy anatomical scans to sourcedata directory
	anat_scans = mprs + t2ws
	for scan in anat_scans:
		relpath = os.path.relpath(scan, bids_dir)
		dest = os.path.join(sourcedata_dir, relpath)

		if os.path.exists(dest):
			continue

		if not os.path.exists(os.path.dirname(dest)):
			os.makedirs(os.path.dirname(dest))
		shutil.copy(relpath, dest)

	# deface anatomical scans
	for idx, mpr in enumerate(mprs):
		applyto_str = '--applyto {}'.format(' '.join(t2ws)) if (idx == 0 and t2ws) else '' # facemask t2w images based on 1st t1w
		call(' '.join(['/data/cerbo/data1/nipype_env/bin/pydeface', mpr, applyto_str]), shell=True)

	# rename to be bids-compatible
	defaced = glob(os.path.join(anat_dir, '_defaced.nii.gz'))
	for scan in defaced:
		os.rename(scan, scan.replace('_defaced', ''))


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('subjects_file', help='csv file with 3 columns: unix-style pattern to subject dicom directory (full path), bids subject label, bids session label')
	parser.add_argument('--bids_dir', help='directory to store the BIDS structured data in')
	parser.add_argument('--redo', action='store_true')
	parser.add_argument('--mriqc', action='store_true', help='run mriqc on converted sessions')
	parser.add_argument('--scan_num_map', action='store_true', help='generate map file of scan number to bids run')

	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument('--convertall_script', default=GENERIC_CONVERTALL_PATH, help='heudiconv convertall python script to use')
	group.add_argument('--json_heuristic', help='json file containing scan/criteria mapping')
	args = parser.parse_args()

	subjects = np.genfromtxt(args.subjects_file, delimiter=',', dtype='str')
	print(subjects[0])

	for dcm_dir, sub, ses in subjects:
		print(dcm_dir, sub, ses)
		run_heudiconv(dcm_dir, sub, ses, args.convertall_script, args.json_heuristic, args.bids_dir, args.redo, args.mriqc)

	if args.mriqc:
		run_mriqc(args.bids_dir) # run mriqc for group

	if args.scan_num_map:
		gen_bids_scan_lut(args.bids_dir)
