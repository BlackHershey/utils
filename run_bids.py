import argparse
import requests

from getpass import getpass
from vnav2bids import vnav2bids

# Successful call: 'https://cnda.wustl.edu/data/projects/NP1081/pipelines/DicomToBIDS/experiments/NEWT004_s1?subject=NEWT004'

LAUNCH_PIPELINE_REQUEST = '{}/data/projects/{}/pipelines/DicomToBIDS/experiments/{}?subject={}'

parser = argparse.ArgumentParser(description='Convert subject data to BIDS with vnav numbers and download')
parser.add_argument('--host', default='https://cnda.wustl.edu', help='CNDA host', required=True)
parser.add_argument('--user', help='CNDA username', required=True)
parser.add_argument('--project_id', required=True)
parser.add_argument('--subject_id', required=True)
parser.add_argument('--session_label', required=True)
args = parser.parse_args()

sess = requests.Session()
sess.auth = (args.user, getpass())

launch_pipeline_url = LAUNCH_PIPELINE_REQUEST.format(args.host, args.project_id, args.session_label, args.subject_id)
response = sess.post(launch_pipeline_url)

vnav2bids(args.host, args.project_id, args.subject_id, args.session_label, sess)
