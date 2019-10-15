from builtins import input
from getpass import getpass
from os import getcwd, listdir, remove
from os.path import isdir, join
from requests.auth import HTTPBasicAuth
from shutil import copyfileobj
from subprocess import call

import argparse
import fnmatch
import json
import requests

import cnda_common

cnda_base_url = 'https://cnda.wustl.edu'
download_url_template = '/data/projects/{}/subjects/{}/experiments/{}/{}/{}/resources/{}/files?format=zip&structure=simplified'
subject_list_url_template = '/data/projects/{}/subjects?format=json'
session_list_url_template = '/data/projects/{}{}/experiments?format=json'


def get_auth_session():
	username = input('CNDA username: ')
	sess = requests.Session()
	sess.auth = (username, getpass())
	return sess


def get_scans_to_download(sess, project_id, subject, session, scan_types):
	if not scan_types:
		return 'ALL'

	if all(t.isdigit() for t in scan_types):
		scans = scan_types
	else:
		scans = []
		scan_info = cnda_common.get_scan_info(sess, project_id, subject, session)
		for scan_id, series_desc in scan_info:
			if any(fnmatch.fnmatch(series_desc, scan_type) for scan_type in scan_types):
				scans.append(scan_id)
	return ','.join(scans)


def download_dicoms(project_id, subject_id=None, session_label=None, scan_types=None, folder='scans', resources='DICOM', exclusions=[], auth=None):
	sess = auth if auth else get_auth_session()

	sessions = None
	warning_msg = ''
	if session_label:
		sessions = [ session_label ]
		warning_msg = 'Session {} has already been downloaded'.format(session_label)
	else:
		sessions = get_sessions(project_id, subject_id, sess)
		warning_msg = 'All sessions are already downloaded'

	existing_sessions = [ d for d in listdir(getcwd()) if isdir(join(getcwd(), d)) ]
	subject_session_map = [ ((subject_id if subject_id else session.rsplit('_', 1)[0]), session) for session in sessions if session not in existing_sessions + exclusions ]
	print(subject_session_map)

	if not subject_session_map:
		print(warning_msg)


	downloaded_sessions = []
	for tup in subject_session_map:
		scans = get_scans_to_download(sess, project_id, tup[0], tup[1], scan_types)
		url = cnda_base_url + download_url_template.format(project_id, tup[0], tup[1], folder, scans, resources)
		zip_file = '.'.join([tup[1], 'zip'])

		print('GET', url)
		r = sess.get(url, stream=True)
		with open(zip_file, 'wb') as f:
			copyfileobj(r.raw, f)

		try:
			call(['unzip', zip_file])
			remove(zip_file)
			downloaded_sessions.append(tup[1])
		except:
			print('Empty zip for session: {}'.format(tup[1]))

	return downloaded_sessions


def get_result_list(url, sess):
	print(url)
	r = sess.get(url)
	return [ result['label'] for result in r.json()['ResultSet']['Result'] ]


def get_sessions(project_id, subject_id, sess):
	subject_str = '/subjects/' + subject_id if subject_id else ''
	url = cnda_base_url + session_list_url_template.format(project_id, subject_str)
	return get_result_list(url, sess)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='download dicoms from CNDA')
	parser.add_argument('project_id', help='CNDA project id')
	parser.add_argument('--subject_id', help='CNDA subject to download (default is all subjects not present in folder)')
	parser.add_argument('--session_label', help='CNDA session to download (default is all sessions not present in folder')
	parser.add_argument('--scan_types', nargs='+', help='scan types to download (default is all scan types)')
	args = parser.parse_args()

	download_dicoms(args.project_id, args.subject_id, args.session_label, args.scan_types)
