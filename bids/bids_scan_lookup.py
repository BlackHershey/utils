import argparse
import csv
import json
import os
import re

from glob import glob


def gen_bids_scan_lut(bids_dir):
	results = [['sub', 'ses', 'bids_run', 'modality', 'filename', 'series_num']]

	# check for both single-session and multi-session folders for sidecars (more efficient than recursive glob)
	sidecars = glob(os.path.join(bids_dir, 'sub-*', 'anat', '*.json')) + glob(os.path.join(bids_dir, 'sub-*', 'ses-*', 'anat', '*.json')) \
		+ glob(os.path.join(bids_dir, 'sub-*', 'func', '*.json')) + glob(os.path.join(bids_dir, 'sub-*', 'ses-*', 'func', '*.json'))
	for sidecar in sidecars:
		print('Processing', sidecar, '...')
		filename = os.path.basename(sidecar)
		sub, ses, run, mod  = re.search('sub-(\w+)(?:_ses-(\w+))?(?:_\w+-\w+)?(?:_run-(\d{2}))?_(\w+).json', filename).groups()
		run = run if run else 1

		with open(sidecar) as f:
			series_num = json.load(f)['SeriesNumber']

		results.append([sub, ses, run, mod, os.path.splitext(filename)[0], series_num])

	outfile =  os.path.join(bids_dir, 'bids_scan_num_lookup.csv')
	with open(outfile, 'w', newline='') as f:
		csv.writer(f).writerows(results)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('bids_dir')
	args = parser.parse_args()

	gen_bids_scan_lut(args.bids_dir)
