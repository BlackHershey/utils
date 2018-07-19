import argparse
import glob
import json
import os
import os.path
from sys import exit, stderr

# local files
from download_dicoms import download_dicoms
from params_setup import gen_params_file


def setup(config_file, img_type=None, exclusions=[]):
	with open(config_file) as f:
		config = json.load(f)

	existing_patids = [ d.split('_')[0] for d in os.listdir('.') if os.path.isdir(d) ]

	scan_types = list(config['series_desc_mapping'].keys())
	new_sessions = download_dicoms(config['cnda_project_id'], scan_types=scan_types, exclusions=exclusions)
	for session in new_sessions:
		patid = session.split('_')[0]
		day1_patid = '{}_s1'.format(patid) if patid in existing_patids else None
		dicom_dir = [ d for d in os.listdir(session) ][0] # dicom_dir should be only thing in patient directory after download
		gen_params_file(session, dicom_dir, config_file, sort=True, duplicates=img_type, day1_patid=day1_patid)


if __name__ == '__main__':
	parser = argparse.ArgumentParser('Setup super script')
	parser.add_argument('study_config', help='json file containing study-specific parameters')
	parser.add_argument('-d', '--duplicates', metavar="img_type", choices=['orig', 'norm'], help='if you have duplicate scans, which Image Type to use (if unspecified, all will be used)')
	parser.add_argument('-x', '--exclusions', nargs='+', help='session labels to exclude from processing')	
	args = parser.parse_args()

	exclusions = args.exclusions if args.exclusions else []
	setup(args.study_config, args.duplicates, exclusions)
