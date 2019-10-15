import argparse
import cnda_common
import csv
import re
import requests
import zipfile

from datetime import datetime
from getpass import getpass
from os.path import exists


def get_unmasked_sessions(project_id, user, scan_types=None, from_date=None, download=False, img_type=None):
	sess = requests.Session()
	sess.auth = (user, getpass('CNDA password:'))

	rows = []
	project_sessions = cnda_common.get_all_sessions(sess, project_id)
	for session in project_sessions:
		subject_id = session['label'].split('_')[0]

		if from_date and datetime.strptime(session['insert_date'][:10], '%Y-%m-%d') < from_date:
			continue

		scan_resources = cnda_common.get_scan_resources(sess, session['ID'])
		print(session['label'])

		id_resource_map = {}
		for resource in scan_resources:
			if scan_types and not any(re.search(scantype, resource['cat_desc']) for scantype in scan_types):
				continue

			if img_type:
				dcm_img_type = cnda_common.get_dcm_tag_info(sess, project_id, session['ID'], resource['cat_id'], fields=['ImageType'])['Image Type']
				if ('NORM' in dcm_img_type and img_type == 'orig') or ('NORM' not in dcm_img_type and img_type == 'norm'):
					continue

			if resource['cat_id'] not in id_resource_map:
				id_resource_map[resource['cat_id']] = []
			id_resource_map[resource['cat_id']].append(resource['label'])


		unfacemasked_scans = [ scan_id for scan_id, resource_list in id_resource_map.items() if 'DICOM_DEFACED' not in resource_list ]
		if unfacemasked_scans:
			print('unmasked:', session['label'], unfacemasked_scans )
			rows.append([session['label'], ';'.join(unfacemasked_scans)])

		if download:
			facemasked_scans = [ scan_id for scan_id in id_resource_map.keys() if scan_id not in unfacemasked_scans ]
			if not facemasked_scans:
				continue

			print('downloading', facemasked_scans)
			cnda_common.download_by_session_id(sess, session['ID'], session['label'], ','.join(map(str,facemasked_scans)), 'DICOM_DEFACED')


	with open('facemask_missing.csv', 'w', newline='') as f:
		writer = csv.writer(f)
		writer.writerows(rows)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('project_id')
	parser.add_argument('user')
	parser.add_argument('--scan_types', nargs='+', help='series descriptions to check resources for')
	parser.add_argument('--from_date', type=lambda d: datetime.strptime(d, '%Y-%m-%d'), help='limit results to sessions after date')
	parser.add_argument('-d', '--download', action='store_true', help='download facemasked sessions?')
	parser.add_argument('--imgtype', choices=['orig','norm'], help='download specified version of image')
	args = parser.parse_args()

	print(args)
	get_unmasked_sessions(args.project_id, args.user, args.scan_types, args.from_date, args.download, args.imgtype)
