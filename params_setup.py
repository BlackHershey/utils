# assume for now that dicoms have been downloaded and stored in the appropriate location

import argparse
import json
from params_common import write_file
from os import chdir, listdir
from subprocess import call


def sort_dicoms(dicom_dir):
	if [ f for f in listdir(dicom_dir) if f.endswith('.dcm') ]: # if dicoms are in the patid dir
		call(['dcm_sort', dicom_dir])
	else: # assume nested scan structure
		call(['pseudo_dcm_sort.csh', dicom_dir, '-s'])
	

# helper function to read the output of (pseudo_)dcm_sort to map scan numbers to descriptions 
def read_studies_file(studies_file):
	scans = []
	with open(studies_file, 'rb') as f:
		for line in f:
			cols = line.split()

			scans.append((cols[0], cols[2])) # (scan_number, scan_description)
	
	return sorted(scans)


# generate params file from studies file mappings
def gen_params_file(patid, dicom_dir, study_config, sort=False,):
	chdir(patid)
	
	if sort:
		sort_dicoms(dicom_dir)

	studies_file = '.'.join([dicom_dir, 'studies', 'txt'])
	scans = read_studies_file(studies_file)

	params = {
		'patid': patid	
	}
	
	with open(study_config) as config_file:
		config = json.load(config_file)


	scan_mappings = config['series_desc_mapping']
	for val in scan_mappings.values():
		params[val] = []


	for scan in scans:
		scan_number = scan[0]
		series_desc = scan[1]
		try:
			var = scan_mappings[series_desc] # variable is value of series description in config
			params[var].append(scan_number) # set variable to the current scan number
		except:
			print('Scan type not found in config:', series_desc)

	
	for val in params.values():
		if isinstance(val, list):
			val.sort(key=lambda x: int(x))

	params['irun'] = [ str(x) for x in range(1,len(params[config['irun']])+1) ]
	
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
	args = parser.parse_args()

	gen_params_file(args.patid, args.dicom_dir, args.study_config, args.sort)



		
