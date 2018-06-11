import argparse
import json
import pydicom
from instructions import get_first_dicom
from params_common import write_file
from os import chdir, listdir
from subprocess import call


# determine if dicom directory structure is flat or nested
#	if dicom_dir contains dcm files, assume flat; otherwise, nested
def is_flat(dicom_dir):
	return [ f for f in listdir(dicom_dir) if f.endswith('.dcm') ] != []


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

			scans.append((cols[0], cols[2])) # (scan_number, scan_description)
	
	return sorted(scans)


# generate params file from studies file mappings
def gen_params_file(patid, dicom_dir, study_config, sort=False, duplicates=None):
	chdir(patid)
	
	flat = is_flat(dicom_dir)

	if sort:
		sort_dicoms(dicom_dir, flat)

	studies_file = '.'.join([dicom_dir, 'studies', 'txt'])
	scans = read_studies_file(studies_file)

	params = {
		'patid': patid,
		'irun': []
	}
	
	with open(study_config) as config_file:
		config = json.load(config_file)


	scan_mappings = config['series_desc_mapping']
	for val in scan_mappings.values():
		params[val] = []

	irun_mapping = config['irun']
	irun_series = list(irun_mapping.keys())
	label_counts = { k:0 for k in list(irun_mapping.values()) }

	for scan in scans:
		scan_number = scan[0]
		series_desc = scan[1]

		# remove unwanted duplicate images if present
		if duplicates and series_desc not in irun_series:
			img_type = pydicom.read_file(get_first_dicom(scan_number, flat)).ImageType
			if  ('NORM' in img_type and duplicates == 'orig') or ('NORM' not in img_type and duplicates == 'norm'):
				continue
		
		if series_desc not in list(scan_mappings.keys()):
			print('Scan type not found in config:', series_desc)
			continue

		var = scan_mappings[series_desc] # variable is value of series description in config
		params[var].append(scan_number) # set variable to the current scan number
		
		if series_desc in irun_series:
			label = irun_mapping[series_desc]
			label_counts[label] += 1
			params['irun'].append(label + str(label_counts[label]))


	params_file = '.'.join([patid, 'params']) 
	write_file(params_file, params)

	chdir('..')
	return				


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('patid')
	parser.add_argument('dicom_dir', help='top-level dicom directory (e.g. DICOM, SCANS) directory')
	parser.add_argument('study_config', help='json config file containing series desc to params variable mapping (see study_config_template.json)')
	parser.add_argument('-s', '--sort', action='store_true', help='run dcm_sort as part of setup process')
	parser.add_argument('-d', '--duplicates', choices=['orig', 'norm'], help='if there are duplicate scans, which Image Type to use (defualt use all)')	
	args = parser.parse_args()

	gen_params_file(args.patid, args.dicom_dir, args.study_config, args.sort, args.duplicates)



		
