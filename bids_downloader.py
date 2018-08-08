import argparse
import glob
import re
import shutil

from download_dicoms import download_dicoms
from os import chdir, listdir, mkdir
from os.path import basename, exists, join

BIDS_FOLDER_MAP = {
	'anat': ['T1w', 'T2w'],
	'dwi': ['dwi'],
	'fmap': ['epi', 'fieldmap', 'magnitude\d*', 'phase(\d|diff)'],
	'func': ['bold', 'sbref']
}
FOLDER_STRUCT_TEMPLATE = '*/*/{}/*'
RESOURCES = ['BIDS', 'NIFTI']

def download_bids(project_id, subject_id=None, session_label=None, scan_types=None):
	downloaded_sessions = download_dicoms(project_id, subject_id, session_label, scan_types, ','.join(RESOURCES))
	for session in downloaded_sessions:
		sub_folder = 'sub-' + session
		shutil.move(session, sub_folder)
		chdir(sub_folder)

		scans_dir = listdir('.')[0] # after download, only one dir should be in the subject folder (the one containing the downloaded files)

		bids_files = [ f for folder in RESOURCES for f in glob.glob(FOLDER_STRUCT_TEMPLATE.format(folder)) ]
		for f in bids_files:
			for folder, file_endings in BIDS_FOLDER_MAP.items():
				pattern = '(' + '|'.join(file_endings) + ')$'
				if re.search(pattern, f.split('.')[0]):
					if not exists(folder):
						mkdir(folder)
					shutil.move(f, join(folder, basename(f)))
					break
		shutil.rmtree(scans_dir)
		chdir('..')
	return


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='download dicoms from CNDA')
	parser.add_argument('project_id', help='CNDA project id')
	parser.add_argument('--subject_id', help='CNDA subject to download (default is all subjects not present in folder)')
	parser.add_argument('--session_label', help='CNDA session to download (default is all sessions not present in folder')
	parser.add_argument('--scan_types', nargs='+', help='scan types to download (default is all scan types)')
	args = parser.parse_args()

	download_bids(args.project_id, args.subject_id, args.session_label, args.scan_types)
