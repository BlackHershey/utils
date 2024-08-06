import argparse
import fnmatch
import glob
import json
import pydicom
import re

from instructions import find_dicoms
from params_common import write_file
from os.path import dirname, join, basename, sep as os_sep
from subprocess import call


def sort_dicoms(dicom_dir, is_flat):
	if is_flat:
		call(['dcm_sort', dicom_dir])
	else:
		call(['pseudo_dcm_sort.csh', dicom_dir, '-s'])


# helper function to read the output of (pseudo_)dcm_sort to map scan numbers to descriptions
def read_dcm_sort_file(dcm_sort_file):
	series_list = []
	with open(dcm_sort_file, 'r') as f:
		for line in f:
			cols = line.split()

			series_list.append((int(cols[0]), cols[2])) # (series_number, series_description)

	return sorted(series_list)


# generate params file from studies file mappings
def gen_params_file(patid, study_config, inpath='.', duplicates=None, day1_patid=None, outfile=None, verbose=False):
	xa30=False
	with open(study_config) as config_file:
			config = json.load(config_file)

	dcm_sort_file = next(iter(glob.glob('*.studies.txt')), 0)
	if verbose:
		print('Found dcm_sort file {}'.format(dcm_sort_file))

	if not dcm_sort_file:
		if verbose:
			print('WARNING: Did not find a dcm_sort-ed .studies.txt file for {}'.format(patid))
		dcms = find_dicoms(inpath=inpath)
		if not dcms:
			print('ERROR: No DICOM files found under current directory. If they are stored elsewhere, try the --inpath flag')
			exit(-1)

		dcm_paths = { dirname(dcm) for dcm in dcms }
		if len(dcm_paths) == 1:
			flat = True
			dcm_dir = next(dcm_paths)
		else:
			flat = False
			split_dcm_paths = { s.split(os_sep) for s in dcm_paths }
			dcm_dir_parts = []
			for i in range(min(len(s) for s in split_dcm_paths)):
				elems = { p[i] for p in split_dcm_paths }
				if len(elems) == 1:
					dcm_dir_parts.append(next(elem))
				break
			dcm_dir = join(dcm_dir_parts)
		sort_dicoms(dcm_dir, flat)
		dcm_sort_file = basename(dcm_dir) + '.studies.txt'

	series_list = read_dcm_sort_file(dcm_sort_file)
	params = {
		'patid': patid,
		'irun': []
	}

	scan_mappings = { k: v for k,v in config['series_desc_mapping'].items() if v != '' }
	if verbose:
		print(scan_mappings)
	for val in scan_mappings.values():
		params[val] = []

	irun_mapping = config['irun']
	irun_series = list(irun_mapping.keys()) # get all series that contribute to fstd/irun
	label_counts = { k:0 for k in list(irun_mapping.values()) } # setup map to keep track of how many of each label seen so far

	previous_series_number = "0"
	for series_index, series in enumerate(series_list):
		series_number = str(series[0])
		series_desc = series[1]

		series_desc_matches = [ key for key in scan_mappings.keys() if fnmatch.fnmatch(series_desc, key) ]
		if not series_desc_matches:
			if verbose:
				print('series {}: (NOT FOUND IN CONFIG, {})'.format(series_number,series_desc))
			continue
		series_key = series_desc_matches[0]
		var = scan_mappings[series_key] # variable is value of series description in config
		if verbose:
			print('series {}: ({}, {})'.format(series_number,scan_mappings[series_key],series_desc))

		# remove unwanted duplicate (non-functional) images if present
		# set previous series acquisition time to something that will never match
		previous_series_acq_time = "-1.0"
		if duplicates and series_key not in irun_mapping.keys() and series_index > 0:
			# find_dicoms(series_number, True)
			previous_series_number = str(series_list[series_index - 1][0])
			if verbose:
				print('check for duplicate using norm rules for series {}'.format(previous_series_number))
			try:
				previous_series_ds = pydicom.read_file(find_dicoms(previous_series_number, True)[0])
				if 'XA30' in previous_series_ds.SoftwareVersions:
					xa30=True
				try:
					previous_series_acq_time = previous_series_ds.AcquisitionTime
				except:
					previous_series_acq_time = previous_series_ds.AcquisitionDateTime
			except:
				if verbose:
					print('WARNING: current series number = {}, no DICOM files found for previous series {}'.format(series_number, previous_series_number))
			current_series_ds = pydicom.read_file(find_dicoms(series_number, True)[0])
			if xa30:
				try:
					current_series_img_type = current_series_ds[0x5200,0x9230][0][0x21,0x11fe][0][0x21,0x1175].value
				except:
					current_series_img_type = current_series_ds[0x5200,0x9230][0][0x21,0x10fe][0][0x21,0x1075].value
			else:
				current_series_img_type = current_series_ds.ImageType
			print('duplicates: current_series number = {}'.format(current_series_ds.SeriesNumber))
			try:
				current_series_acq_time = current_series_ds.AcquisitionTime
			except:
				current_series_acq_time = current_series_ds.AcquisitionDateTime

			if (duplicates == 'orig' and 'NORM' in current_series_img_type):
				if verbose:
					print('duplicates: skipping {}: {} / {} # SEE NORM/IRUN RULES'.format(series_number,series_desc,current_series_img_type))
				continue

			if (duplicates == 'norm' and 'NORM' in current_series_img_type):
				# check previous series acquisition time, if same, remove from list
				if verbose:
					print('duplicates: current series AcqTime = {}, previous series AcqTime = {}')
				if (current_series_acq_time == previous_series_acq_time):
					params[var].remove(previous_series_number)

		params[var].append(series_number) # append the current series number

		# add appropriate numbered label to irun list
		irun_matches = [ re.match(item, series_key) for item in irun_series ]
		if any(irun_matches):
			irun_match = next(item for item in irun_matches if item is not None).group(0)
			label = irun_mapping[irun_match]
			label_counts[label] += 1
			params['irun'].append(label + str(label_counts[label]))

	# if processing a scan that shares an MPRAGE with another processing stream, use "cross day" logic to reuse existing atlas transform
	if not day1_patid and not 'mprs' in params:
		day1_patid = patid

	# set up cross day parameters if day1_patid specified (i.e. if current session is not subject's first
	if day1_patid:
		params['day1_patid'] = day1_patid
		params['day1_path'] = glob.glob(join(dirname(study_config), '**', day1_patid, 'atlas'), recursive=True)[0]
	
	params_file = outfile if outfile else '.'.join([patid, 'params'])
	write_file(params_file, params)

	return


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('patid')
	parser.add_argument('study_config', help='json config file containing series desc to params variable mapping (see study_config_template.json)')
	parser.add_argument('-s', '--sort', action='store_true', help='run dcm_sort as part of setup process')
	parser.add_argument('--inpath', help='path to subject raw data directory')
	parser.add_argument('-d', '--duplicates', choices=['orig', 'norm'], help='if there are duplicate scans, which Image Type to use (defualt use all)')
	parser.add_argument('--day1_patid', help='patient directory for first session (if patid is not patient\'s first session)')
	parser.add_argument('--outfile', help='name for output file')
	args = parser.parse_args()

	gen_params_file(args.patid, args.study_config, args.sort, args.inpath, args.duplicates, args.day1_patid, args.outfile)
