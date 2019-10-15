import json

from zipfile import ZipFile
from os import remove
from os.path import exists
from shutil import copyfileobj


HOST = 'https://cnda.wustl.edu'

LONG_FORM_TEMPLATE = '{}/data/projects/{}/subjects/{}/experiments/{}'
SHORT_FORM_TEMPLATE = '{}/data/experiments/{}'

ALL_SESSION_REQUEST_TEMPLATE = '{}/data/projects/{}/experiments'
DOWNLOAD_LONG_FORM_REQUEST_TEMPLATE = '{}/data/projects/{}/subjects/{}experiments/{}/scans/{}/resources/{}/files'
DOWNLOAD_REQUEST_TEMPLATE = '{}/data/projects/{}/experiments/{}/scans/{}/resources/{}/files'
SCAN_RESOURCES_REQUEST_TEMPLATE = '{}/data/experiments/{}/scans/{}/resources'
SCAN_REQUEST_TEMPLATE = '{}/data/projects/{}/subjects/{}/experiments/{}/scans'

JSON_FORMAT = {'format': 'json'}
DOWNLOAD_PARAMS = {'format': 'zip', 'structure': 'simplified'}

def get_result_array(response):
	return response.json()['ResultSet']['Result']


def download(sess, url, session_label, overwrite=False):
	if exists(session_label) and not overwrite:
		return

	zip_file = session_label + '.zip'
	r = sess.get(url, params=DOWNLOAD_PARAMS, stream=True)
	with open(zip_file, 'wb') as f:
		copyfileobj(r.raw, f)
	
	dl = ZipFile(zip_file)
	dl.extractall('.')
	dl.close()
	remove(zip_file)

def download_by_session_id(sess, session_id, session_label, scans, resources, host=HOST, overwrite=False):
	base_url = SHORT_FORM_TEMPLATE.format(host, session_id)
	download(sess, '{}/scans/{}/resources/{}/files'.format(base_url, scans, resources), session_label, overwrite)


def download_by_subject_session_label(sess, project_id, subject_id, session_label, scans, resources, host=HOST, overwrite=False):
	base_url = LONG_FORM_TEMPLATE.format(host, project_id, subject_id, session_label)
	download(sess, '{}/scans/{}/resources/{}/files'.format(base_url, scans, resources), session_label, overwrite)


def get_all_sessions(sess, project_id, host=HOST):
	base_url = '{}/data/projects/{}/experiments'.format(host, project_id)
	response = sess.get(base_url, params=JSON_FORMAT)
	return get_result_array(response)


def get_dcm_tag_info(sess, project_id, session_id, scan_id, fields=None, host=HOST):
	base_url = '{}/REST/services/dicomdump'.format(host)
	params = {}
	params['src'] = '/archive/projects/{}/experiments/{}/scans/{}'.format(project_id, session_id, scan_id)
	if fields:
		params['field'] = fields
	params = { **params, **JSON_FORMAT }
	response = sess.get(base_url, params=params)
	return { tag['desc']: tag['value'] for tag in get_result_array(response) }


def get_scan_info(sess, project_id, subject_id, session_label, host=HOST):
	base_url = LONG_FORM_TEMPLATE.format(host, project_id, subject_id, session_label)
	print(base_url)
	response = sess.get('{}/scans'.format(base_url), params=JSON_FORMAT)
	return [ (scan['ID'], scan['series_description']) for scan in get_result_array(response) ]


def get_scan_resources(sess, session_id, scan_id='ALL', host=HOST):
	base_url = SHORT_FORM_TEMPLATE.format(host, session_id)
	response = sess.get('{}/scans/{}/resources'.format(base_url, scan_id), params=JSON_FORMAT)
	return get_result_array(response) 



