import argparse
import glob
import json
import os
import os.path
from subprocess import call
from sys import exit, stderr

# local files
from download_dicoms import download_dicoms
from params_setup import gen_params_file

scripts_dir = '/net/zfs-black/BLACK/black/git/utils'

def setup(config_file, img_type=None, sessions=[]):
	with open(config_file) as f:
		config = json.load(f)

	existing_patids = [ d.split('_')[0] for d in os.listdir('.') if os.path.isdir(d) ]

	series_mapping = config['series_desc_mapping']
	t1_series_desc = '|'.join([ k for k,v in series_mapping.items() if v == 'mprs' ])

	scan_types = list(series_mapping.keys())

	new_sessions = download_dicoms(config['cnda_project_id'], scan_types=scan_types, exclusions=config['exclusions'])
	sessions += new_sessions
	for session in sessions:
		patid = session.split('_')[0]
		day1_patid = '{}_s1'.format(patid) if not session.endswith('s1') else None
		dicom_dir = [ d for d in os.listdir(session) ][0] # dicom_dir should be only thing in patient directory after download
		gen_params_file(session, '*', config_file, sort=True, duplicates=img_type, day1_patid=day1_patid)

		fs_config = config['freesurfer']
		if fs_config['subjects_dir'] and not day1_patid and not os.path.exists(os.path.join(fs_config['subjects_dir'], session)):
			cmd = [os.path.join(scripts_dir, 'gen_fs_calls.csh'), session, "{}".format(t1_series_desc), fs_config['subjects_dir'], fs_config['recon-all_flags']]
			print(' '.join(cmd))
			print(os.getcwd())
			call(cmd)
			call(['at', 'now', '-f', '{0}/{0}_fs_call.csh'.format(session)])

	return


if __name__ == '__main__':
	parser = argparse.ArgumentParser('Setup super script')
	parser.add_argument('study_config', help='json file containing study-specific parameters')
	parser.add_argument('-d', '--duplicates', metavar='img_type', choices=['orig', 'norm'], help='if you have duplicate scans, which Image Type to use (if unspecified, all will be used)')
	parser.add_argument('-s', '--sessions', nargs='+', default=[], help='list of sessions to process')
	args = parser.parse_args()

	setup(args.study_config, args.duplicates, args.sessions)
