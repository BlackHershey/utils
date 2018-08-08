import argparse
import glob
import json
import os
import pydicom
import re
import requests
import shutil

from enum import Enum
from getpass import getpass
from itertools import count, groupby
from zipfile import ZipFile

# define tuple index constants
scan_api = Enum('scan_api', zip(['ID', 'DESC'], count()))
nav = Enum('nav', zip(['SERIES_TIME', 'IMG_COMMENTS'], count()))
anat = Enum('anat', zip(['ID', 'SERIES_TIME'], count()))

CONFIG_REQUEST_TEMPLATE = '{}/data/projects/{}/config/bids/bidsmap'
SCAN_REQUEST_TEMPLATE = '{}/data/projects/{}/subjects/{}/experiments/{}/scans'
DCM_TAG_REQUEST = '{}/REST/services/dicomdump?src=/archive/projects/{}/subjects/{}/experiments/{}/scans/{}&format=json'
DOWNLOAD_REQUEST = '{}/data/projects/{}/subjects/{}/experiments/{}/scans/{}/resources/{}/files?format=zip&structure=simplified'
UPLOAD_REQUEST = '{}/data/projects/{}/subjects/{}/experiments/{}/scans/{}/resources/BIDS/files'

def download(sess, url, outfile):
    response = sess.get(url, stream=True)
    print(url, response.status_code)
    with open(outfile, 'wb') as f:
        shutil.copyfileobj(response.raw, f)

    try:
        ZipFile(outfile).extractall()
        os.remove(outfile)
    except:
        print('Empty zip: ', outfile)


def vnav2bids(host, project_id, subject_id, session_label, sess):
    session_zipfile = session_label + '.zip'

    session_scans_url = SCAN_REQUEST_TEMPLATE.format(host, project_id, subject_id, session_label)
    response = sess.get(session_scans_url, params={'format': 'json'})
    scans = [ (scan['ID'], scan['series_description']) for scan in response.json()['ResultSet']['Result'] ]

    project_bidsmap_url = CONFIG_REQUEST_TEMPLATE.format(host, project_id)
    response = sess.get(project_bidsmap_url, params={'contents': True})
    anat_mapping = [ mapping for mapping in response.json() if mapping['bidsname'] in [ 'T1w','T2w'] ]
    anat_series = { mapping['series_description'] for mapping in anat_mapping }

    for series_desc in anat_series:
        scan_info = {}
        for scan in scans:
            if re.match(series_desc, scan[scan_api.DESC.value]):
                dcm_tag_url = DCM_TAG_REQUEST.format(host, project_id, subject_id, session_label, scan[scan_api.ID.value])
                response = sess.get(dcm_tag_url, params={'field': ['ImageType', 'SeriesTime'] })
                scan_info[scan[scan_api.ID.value]] = { tag['desc']: tag['value'] for tag in response.json()['ResultSet']['Result'] }


        anat_scan_info = { tup[scan_api.ID.value]: scan_info[tup[scan_api.ID.value]] for tup in scans if tup[scan_api.DESC.value] == series_desc }
        nav_scan_ids = [ tup[scan_api.ID.value] for tup in scans if re.match(series_desc + '\w+', tup[scan_api.DESC.value]) and 'MOSAIC' in scan_info[tup[scan_api.ID.value]]['Image Type'] ]

        # map navigator sequence acquisition time to the sorted quaternion list
        download_nav_dcm_url = DOWNLOAD_REQUEST.format(host, project_id, subject_id, session_label, ','.join(nav_scan_ids), 'DICOM')
        download(sess, download_nav_dcm_url, session_zipfile)
        os.chdir(session_label)
        nav_scan_info = {}
        for scan_id in nav_scan_ids:
            dcms = glob.glob('*/{}/DICOM/*'.format(scan_id))
            dcm_datasets = [ pydicom.read_file(dcm) for dcm in dcms ]
            scan_info = sorted([ (float(ds.AcquisitionTime), ds.ImageComments) for ds in dcm_datasets ])
            nav_scan_info[scan_info[0][nav.SERIES_TIME.value]] = [ tup[nav.IMG_COMMENTS.value] for tup in scan_info ]
        os.chdir('..')

        # create map of scans by acquisition time
        anat_scans = { float(props['Series Time']): id for id, props in anat_scan_info.items() }

        # match vnav numbers to the appropriate structural scan
        download_anat_json_url = DOWNLOAD_REQUEST.format(host, project_id, subject_id, session_label, ','.join(anat_scans.values()), 'BIDS')
        download(sess, download_anat_json_url, session_zipfile)
        os.chdir(session_label)
        for series_time, id in anat_scans.items():
            # get image comments list from the nav sequence that has the maximum series time that comes before the current anat sequence
            nav_series_times = list(nav_scan_info.keys())
            vnav_numbers = nav_scan_info[max([time for time in nav_series_times if time < series_time])]

            # add those vnav numbers to the corresponding structural image's json file
            #   json doesn't support appending, so we'll read the file in, add the new var, and write it back to the file
            scan_json_file = glob.glob('*/{}/BIDS/*.json'.format(id))[0]
            with open(scan_json_file, 'r') as f:
                sidecar = json.load(f)
            with open(scan_json_file, 'w') as f:
                sidecar['vnavNumbers'] = vnav_numbers
                json.dump(sidecar, f)
            upload_json_url = UPLOAD_REQUEST.format(host, project_id, subject_id, session_label, id)
            sess.put(upload_json_url, params={'overwrite':True}, files={ 'files': open(scan_json_file, 'rb') })

        os.chdir('..')

    # clean up after all downloads/uploads are complete
    shutil.rmtree(session_label)
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract vNav motion data from setter images and insert into the BIDS sidecar of the corresponding scan')
    parser.add_argument('--host', default='https://cnda.wustl.edu', help='CNDA host', required=True)
    parser.add_argument('--user', help='CNDA username', required=True)
    parser.add_argument('--project_id', required=True)
    parser.add_argument('--subject_id', required=True)
    parser.add_argument('--session_label', required=True)
    args = parser.parse_args()

    sess = requests.Session()
    sess.auth = (args.user, getpass())

    vnav2bids(args.host, args.project_id, args.subject_id, args.session_label, sess)
