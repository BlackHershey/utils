import argparse
import csv
import dateutil.parser
import glob
import json
import numpy as np
import os
import pydicom
import re
import requests
import shutil
import sys
import tempfile
import vnav

from cnda.cnda_common import get_all_sessions
from getpass import getpass
from itertools import count, groupby
from zipfile import ZipFile

SCAN_REQUEST_TEMPLATE = 'https://cnda.wustl.edu/data/projects/{}/subjects/{}/experiments/{}/scans'
DOWNLOAD_REQUEST = 'https://cnda.wustl.edu/data/projects/{}/subjects/{}/experiments/{}/scans/{}/resources/{}/files?format=zip&structure=simplified'

modality_search = re.compile('_(T\dw)')

"""
Convert quarternions in sidecar into motion scores/timecourses
	Assumes that vnavNumbers is included in the passed in json object
"""
def extract_vnav_scores(scan_info):
	try:
		vnav_numbers = [ x.split() for x in scan_info['vnavNumbers'][1:] if x is not None ]
		rot_trans = [ ([1,0,0,0], [0,0,0]) ] + [ (list(map(float, x[1:5])), list(map(float, x[6:9]))) for x in vnav_numbers if len(x) > 9 ]
		rot_trans = [ (np.array(x[0]), np.array(x[1])) for x in rot_trans ]
		return vnav.parseMotion(rot_trans, scan_info['RepetitionTime'], 50)
	except ValueError as e:
		print('Error: Unable to parse vnav data')
		return { score_type: None for score_type in ['mean_rms', 'mean_max', 'rms_scores', 'max_scores'] }

def download(sess, url, outfile):
	response = sess.get(url, stream=True)
	print(url, response.status_code)
	with open(outfile, 'wb') as f:
		shutil.copyfileobj(response.raw, f)

	try:
		ZipFile(outfile).extractall(os.path.dirname(outfile))
		os.remove(outfile)
	except:
		print('Empty zip: ', outfile)


def vnav2bids(sess, project_id, config, bids_dir, session_label, session_map, scratch_dir=None, redo=False):
	work_dir = scratch_dir if scratch_dir else bids_dir

	subject_id, _, session = session_label.partition('_') # assumes only one underscore seprates sub from session (but does support multi-underscore sessions)

	if not os.path.exists(os.path.join(bids_dir, 'sub-' + subject_id)):
		print('\tSubject folder does not exist in bids dir. Skipping...')
		return None

	if session_map:
		session_match = [ k for k in session_map.keys() if re.match(session + '$', k, flags=re.IGNORECASE) ]
		if not session_match:
			print('\tSession not included in map. Skipping...')
			return None
		session = 'ses-' + session_map[session_match[0]]

	session_scans_url = SCAN_REQUEST_TEMPLATE.format(project_id, subject_id, session_label)
	response = sess.get(session_scans_url, params={'format': 'json'})
	scan_map = { scan['ID']: scan['series_description'] for scan in response.json()['ResultSet']['Result'] }

	anat_series = { item['series_description'] for item in config['bidsmap']['anat'] }
	if config['series_desc_regex']:
		anat_search = [ re.search(pattern, desc) for
		pattern in anat_series for _, desc in scan_map.items() ]
		anat_series = { match.group() for match in anat_search if match }


	results = {}
	for series_desc in anat_series:
		anat_sidecars = glob.glob(os.path.join(bids_dir, 'sub-' + subject_id, '**', 'anat', '*.json'), recursive=True)
		if session:
			anat_sidecars = [ f for f in anat_sidecars if re.search(session + os.path.sep, os.path.dirname(f), flags=re.IGNORECASE) ]

		if not anat_sidecars:
			print('\tNo matching bids sidecars found for MR session')
			continue

		# create map of anat scans by acquisition time
		anat_scan_info = {}
		for sidecar in anat_sidecars:
			with open(sidecar) as f:
				scan_info = json.load(f)

			if scan_info['SeriesDescription'] != series_desc:
				continue

			# if already processed, just report the vnav numbers from the sidecar and move on to next scan
			if not redo and 'vnavNumbers' in scan_info.keys():
				results[(scan_info['SeriesNumber'], modality_search.search(sidecar).group(1))] = extract_vnav_scores(scan_info)
				continue

			acq_time = dateutil.parser.parse(scan_info['AcquisitionTime']).strftime('%H%M%S.%f')
			anat_scan_info[float(acq_time)] = sidecar

		if not anat_scan_info:
			continue

		# map navigator sequence acquisition time to the sorted quaternion list
		session_zipfile = os.path.join(work_dir, session_label + '.zip')
		nav_scan_ids = [ id for id, desc in scan_map.items() if re.match(series_desc + '\w+', desc) ]
		if not nav_scan_ids:
			print('\tNo vnav scans found!')
			continue
		download_nav_dcm_url = DOWNLOAD_REQUEST.format(project_id, subject_id, session_label, ','.join(nav_scan_ids), 'DICOM')
		download(sess, download_nav_dcm_url, session_zipfile)

		nav_scan_info = {}
		for scan_id in nav_scan_ids:
			dcms = glob.glob(os.path.join(work_dir, session_label, 'scans', scan_id, 'DICOM', '*'))
			dcm_datasets = [ pydicom.read_file(dcm) for dcm in dcms ]
			if 'MOSAIC' not in dcm_datasets[0].ImageType: # correct setter image will have mosiac in scan type
				continue
			scan_info = sorted([ (float(ds.AcquisitionTime), ds.ImageComments if 'ImageComments' in ds else None) for ds in dcm_datasets ])
			nav_scan_info[scan_info[0][0]] = [ tup[1] for tup in scan_info ] # key = acquistion time, value = list of motion strings

		# match vnav numbers to the appropriate structural scan
		for series_time, sidecar in anat_scan_info.items():
			# get image comments list from the nav sequence that has the maximum series time that comes before the current anat sequence
			nav_series_times = list(nav_scan_info.keys())
			print(series_time, nav_series_times)
			vnav_numbers = nav_scan_info[max([time for time in nav_series_times if time < series_time])]

			# add those vnav numbers to the corresponding structural image's json file
			#   json doesn't support appending, so we'll read the file in, add the new var, and write it back to the file
			with open(sidecar, 'r') as f:
				sidecar_obj = json.load(f)
			with open(sidecar, 'w') as f:
				sidecar_obj['vnavNumbers'] = vnav_numbers
				json.dump(sidecar_obj, f)

			results[(sidecar_obj['SeriesNumber'], modality_search.search(sidecar).group(1))] = extract_vnav_scores(sidecar_obj)

	# clean up after all downloads/uploads are complete
	temp_folder = os.path.join(work_dir, session_label)
	if os.path.exists(temp_folder):
		shutil.rmtree(temp_folder)

	return results

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Extract vNav motion data from setter images and insert into the BIDS sidecar of the corresponding scan')
	parser.add_argument('--project_id', required=True)
	parser.add_argument('--user', help='CNDA username', required=True)
	parser.add_argument('--config_file', required=True)
	parser.add_argument('--bids_dir', required=True)
	parser.add_argument('--subjects_file')
	parser.add_argument('--session_label', help='CNDA session label')
	parser.add_argument('--scratch_dir')
	parser.add_argument('--redo', action='store_true')
	parser.add_argument('--session_map', nargs='+')
	args = parser.parse_args()

	auth_info = (args.user, getpass())
	sess = requests.Session()
	sess.auth = auth_info

	with open(args.config_file) as f:
		config = json.load(f)

	print('len(args.session_map) = {}'.format(len(args.session_map)))
	print('args.session_map = {}'.format(args.session_map))
	session_map = { cnda_session: l[0] for l in args.session_map for cnda_session in l[1:] }
	print('session_map = {}'.format(session_map))

	sessions = [ session['label'] for session in get_all_sessions(sess, args.project_id) ]

	with open('vnav_mean_scores.csv', 'w') as f:
		csv.writer(f).writerow(['patid', 'scan', 'modality', 'vnav_mean_rms', 'vnav_mean_max'])

	if os.path.exists('vnav_timecourse.csv'):
		os.remove('vnav_timecourse.csv')

	for session_label in sessions:
		if args.session_label and session_label != args.session_label:
			continue

		print(session_label)
		vnav_scores = vnav2bids(sess, args.project_id, config, args.bids_dir, session_label, session_map, args.scratch_dir, args.redo)

		if not vnav_scores:
			continue

		for tup, scores in vnav_scores.items():
			with open('vnav_mean_scores.csv', 'a') as f:
				writer = csv.writer(f)
				writer.writerow([session_label, tup[0], tup[1], scores['mean_rms'], scores['mean_max']])

			with open('vnav_timecourse.csv', 'a') as f:
				writer = csv.writer(f)
				writer.writerow([session_label, tup[0], tup[1], 'rms'] + scores['rms_scores'] if scores['rms_scores'] else [])
				writer.writerow([session_label, tup[0], tup[1], 'max'] + scores['max_scores'] if scores['max_scores'] else [])
