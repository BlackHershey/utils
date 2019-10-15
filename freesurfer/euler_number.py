import argparse
import csv
import os
import re

from glob import glob
from subprocess import run, PIPE

input_search = re.compile('MR\.head_\w+\.(\d+)')
euler_num_search = re.compile('= (-*\d+) -->')

def extract_euler(subjects_dir, outfile, surf_dirs):
	results = [ ['patid', 'scan', 'lh_euler', 'rh_euler'] ]
	for d in surf_dirs:
		patid = d.split(os.sep)[-2] # get subject folder name
		logfile = os.path.join(os.path.dirname(d), 'scripts', 'recon-all.done')
		if os.path.exists(logfile):
			print(logfile)
			input_args = run(['grep', 'CMDARGS', logfile], stdout=PIPE).stdout.decode()
			search_res = input_search.search(input_args)
			input_scan = search_res.group(1) if search_res else None
		else:
			input_scan = None

		euler_nums = []
		for hemi in [ 'lh', 'rh' ]:
			surf = os.path.join(d, '{}.orig.nofix'.format(hemi))
			print('Processing {}...'.format(surf))

			if not os.path.exists(surf):
				euler_nums.append(None)
				continue

			num = euler_num_search.search(run(['mris_euler_number', surf], stderr=PIPE).stderr.decode()).group(1) # response goes to stderr (not sure why)
			euler_nums.append(num)

		results.append([patid, input_scan] + euler_nums)

	outfile = outfile if outfile else os.path.join(subjects_dir, 'euler_numbers.csv')
	with open(outfile, 'w') as f:
		writer = csv.writer(f)
		writer.writerows(results)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('subjects_dir')
	parser.add_argument('-o', '--outfile', help='where to store group results')
	parser.add_argument('--subj_pattern', help='patid matching pattern (unix-style)')
	args = parser.parse_args()

	subj_pattern = args.subj_pattern if args.subj_pattern else '*'
	surf_dirs = glob(os.path.join(args.subjects_dir, '**', subj_pattern, 'surf'), recursive=True)

	extract_euler(args.subjects_dir, args.outfile, surf_dirs)
