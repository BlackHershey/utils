from builtins import input
from getpass import getpass
from os import getcwd, listdir, remove
from os.path import isdir, join
from requests import get
from requests.auth import HTTPBasicAuth
from shutil import copyfileobj
from subprocess import call

import argparse
import json

cnda_base_url = 'https://cnda.wustl.edu'
download_url_template = '/data/projects/{}/subjects/{}/experiments/{}/scans/{}/resources/{}/files?format=zip&structure=simplified'
subject_list_url_template = '/data/projects/{}/subjects?format=json'
session_list_url_template = '/data/projects/{}{}/experiments?format=json'


def get_auth_obj():
	username = input('CNDA username: ')
	return HTTPBasicAuth(username, getpass())


def download_dicoms(project_id, subject_id=None, session_label=None, scan_types=None, resources='DICOM', exclusions=[]):
	auth_obj = get_auth_obj()
	
	sessions = None
	warning_msg = ''
	if session_label:
		sessions = [session_label]
		warning_msg = 'Session {} has already been downloaded'.format(session_label)
	else:
		sessions = get_sessions(project_id, subject_id, auth_obj)
		warning_msg = 'All sessions are already downloaded'

	existing_sessions = [ d for d in listdir(getcwd()) if isdir(join(getcwd(), d)) ]
	subject_session_map = [ (session.rsplit('_', 1)[0], session) for session in sessions if session not in existing_sessions + exclusions ] 

	if not subject_session_map:
		print(warning_msg)

	scan_types = ','.join(scan_types) if scan_types else 'ALL'

	downloaded_sessions = []
	for tup in subject_session_map:
		url = cnda_base_url + download_url_template.format(project_id, tup[0], tup[1], scan_types, resources)
		zip_file = '.'.join([tup[1], 'zip'])
	
		print('GET', url)
		r = get(url, stream=True, auth=auth_obj)
		with open(zip_file, 'wb') as f:
			copyfileobj(r.raw, f)

		try:
			call(['unzip', zip_file])
			remove(zip_file)
			downloaded_sessions.append(tup[1])
		except:
			print('Empty zip for session: {}'.format(tup[1]))
	
	return downloaded_sessions


def get_result_list(url, auth_obj):
	r = get(url, auth=auth_obj)
	return [ result['label'] for result in r.json()['ResultSet']['Result'] ]


def get_sessions(project_id, subject_id, auth_obj):
	subject_str = '/subjects/' + subject_id if subject_id else ''
	url = cnda_base_url + session_list_url_template.format(project_id, subject_str)
	return get_result_list(url, auth_obj)
	
	
if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='download dicoms from CNDA')
	parser.add_argument('project_id', help='CNDA project id')
	parser.add_argument('--subject_id', help='CNDA subject to download (default is all subjects not present in folder)')
	parser.add_argument('--session_label', help='CNDA session to download (default is all sessions not present in folder')
	parser.add_argument('--scan_types', nargs='+', help='scan types to download (default is all scan types)')
	parser.add_argument('--config', help='study config file containing desired scan types (shared with setup script)')
	args = parser.parse_args()
	
	download_dicoms(args.project_id, args.subject_id, args.session_label, args.scan_types)

