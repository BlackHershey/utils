import argparse
import fnmatch
import glob
import json
import pydicom
import re

from instructions import get_first_dicom
from params_common import write_file
from os import chdir, getcwd, listdir
from os.path import dirname, islink, join
from subprocess import call


def sort_dicoms(dicom_dir, is_flat):
	if is_flat:
		call(['dcm_sort', dicom_dir])
	else:
		call(['pseudo_dcm_sort.csh', dicom_dir, '-s'])


# helper function to read the output of (pseudo_)dcm_sort to map scan numbers to descriptions
def read_studies_file(studies_file):
	scans = []
	with open(studies_file, 'r') as f:
		for line in f:
			cols = line.split()

			scans.append((int(cols[0]), cols[2])) # (scan_number, scan_description)

	return sorted(scans)


# generate params file from studies file mappings
def gen_params_file(patid, inpath, study_config, sort=False, duplicates=None, day1_patid=None, outfile=None):

	with open(study_config) as config_file:
			config = json.load(config_file)

	chdir(patid)

	dcms = glob.glob(join(inpath, '*.dcm'))
	if dcms:
		flat = True
		dicom_dir = inpath
	else:
		flat = False
		dcms = glob.glob(join(inpath, '*', '\d+', 'DICOM', '*.dcm'))
		dicom_dir = re.search('(scans|DICOM)', dcms[0], flags=re.IGNORECASE).group(0)

	if sort:
		sort_dicoms(dicom_dir, flat)

	studies_file = glob.glob('*.studies.txt')[0]
	scans = read_studies_file(studies_file)
	params = {
		'patid': patid,
		'irun': []
	}

	scan_mappings = { k: v for k,v in config['series_desc_mapping'].items() if v != '' }
	print(scan_mappings)
	for val in scan_mappings.values():
		params[val] = []

	irun_mapping = config['irun']
	irun_series = list(irun_mapping.keys()) # get all series that contribute to fstd/irun
	label_counts = { k:0 for k in list(irun_mapping.values()) } # setup map to keep track of how many of each label seen so far

	for scan in scans:
		scan_number = str(scan[0])
		series_desc = scan[1]

		series_desc_matches = [ key for key in scan_mappings.keys() if fnmatch.fnmatch(series_desc, key) ]
		if not series_desc_matches:
			print('Scan type not found in config:', series_desc)
			continue
		series_key = series_desc_matches[0]

		# remove unwanted duplicate (non-functional) images if present
		if duplicates and series_key not in irun_mapping.keys():
			img_type = pydicom.read_file(get_first_dicom(scan_number, True)).ImageType
			if  ('NORM' in img_type and duplicates == 'orig') or ('NORM' not in img_type and duplicates == 'norm'):
				continue

		var = scan_mappings[series_key] # variable is value of series description in config
		params[var].append(scan_number) # set variable to the current scan number

		# add appropriate numbered label to irun list
		irun_matches = [ re.match(item, series_key) for item in irun_series ]
		if any(irun_matches):
			irun_match = next(item for item in irun_matches if item is not None).group(0)
			label = irun_mapping[irun_match]
			label_counts[label] += 1
			params['irun'].append(label + str(label_counts[label]))

	# set up cross day parameters if day1_patid specified (i.e. if current session is not subject's first
	if day1_patid:
		params['day1_patid'] = day1_patid
		params['day1_path'] = join(dirname(getcwd()), '${day1_patid}', 'atlas')
		if 'mprs' in params:
			del params['mprs']
		if 'tse' in params:
			del params['tse']

	params_file = outfile if outfile else '.'.join([patid, 'params'])
	write_file(params_file, params)

	chdir('..')
	return


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('patid')
	parser.add_argument('inpath', help='path to subject raw data directory')
	parser.add_argument('study_config', help='json config file containing series desc to params variable mapping (see study_config_template.json)')
	parser.add_argument('-s', '--sort', action='store_true', help='run dcm_sort as part of setup process')
	parser.add_argument('-d', '--duplicates', choices=['orig', 'norm'], help='if there are duplicate scans, which Image Type to use (defualt use all)')
	parser.add_argument('--day1_patid', help='patient directory for first session (if patid is not patient\'s first session)')
	parser.add_argument('--outfile', help='name for output file')
	args = parser.parse_args()

	gen_params_file(args.patid, args.dicom_dir, args.study_config, args.sort, args.duplicates, args.day1_patid, args.outfile)
