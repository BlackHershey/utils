import argparse
import glob
import math
import os
import pydicom
import re

from params_common import write_file
from sys import exit, stderr

scan_number_pattern = '(?:\w*\.){3}(\d+)\..*'
flat_path_template = '*/*.{}.1.*.dcm'
nested_path_template = '*/{}/DICOM/*.1.*.dcm'


def get_first_dicom(scan_number, flat):
	dcm_path_template = flat_path_template if flat else nested_path_template
	return glob.glob(dcm_path_template.format(scan_number))[0]


def get_bold_header_data(series_desc):
	ds = None
	
	descs = set()
	studies_file = glob.glob('*.studies.txt')

	flat_files = [ f for f in glob.glob(flat_path_template.format('*')) if not f.startswith('study') ]	
	
	if not studies_file: # if dicoms are not sorted, search headers to find bold scans
		dcms = flat_files if flat_files else glob.glob(nested_path_template.format('*'))

		for dcm in dcms:
			scan_number = re.search(scan_number_pattern, dcm).groups()[0]
			dcm_header = get_first_dicom(scan_number, flat_files)

			ds = pydicom.read_file(dcm_header)
			if ds.SeriesDescription == series_desc:
				return ds
			else:
				descs.add(ds.SeriesDescription)
	else: # otherwise, grab a bold scan number from studies file
		with open(studies_file[0]) as f:
			for line in f:
				if series_desc in line:
					return pydicom.read_file(get_first_dicom(line.split(' ')[0], flat_files))
	
	stderr.write('No BOLD dicoms found!')
	print(descs)
	exit(1)


def calc_unpack_dim(img_dim, num_imgs):
	return img_dim / math.ceil(math.sqrt(num_imgs))


def instructions(series_desc, output_file=None):
	ds = get_bold_header_data(series_desc)

	instructions = {
		'nx': calc_unpack_dim(ds.Rows, ds[0x19,0x100a].value),
		'ny': calc_unpack_dim(ds.Columns, ds[0x19,0x100a].value),
		'TR_vol': float(ds.RepetitionTime) / 1000,
		'TR_slc': 0,
		'TE_vol': float(ds.EchoTime)
	}

	slice_timing = ds[0x19,0x1029].value
	MBfac = slice_timing.count(0) # get number of bands
	instructions['MBfac'] = MBfac

	num_slices = len(slice_timing)
	slice_time_tuples = sorted([ (time, slc) for slc, time in enumerate(slice_timing[:num_slices / MBfac]) ])
	slice_order = [ tup[1]+1 for tup in slice_time_tuples ]
	
	if slice_order == range(1, num_slices+1): # check if sequential
		instructions['interleave'] = '-S'
	elif all(slc % 2 == 0 for slc in slice_order[:num_slices/2]): # check for Siemen's interleave (starts with evens if even number of slices)
			instructions['Siemens_interleave'] = 1
	elif all(slc % 2 != 0 for slc in slice_order[:num_slices/2]): # check for regular interleave (starts with odd slices)
			instructions['Siemens_interleave'] = 0
	else:			
		instructions['seqstr'] = ','.join(map(str,slice_order)) # otherwise, supply slice ordering string

	if not output_file:
		output_file = '../{}.params'.format(os.path.basename(os.path.abspath('..')))
	write_file(output_file, instructions)		


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Generate scan-specific instructions variables for cross_bold (to be run from subject dir)')
	parser.add_argument('epi_series_desc', help='series description for BOLD scans')
	parser.add_argument('-o', '--output_file', help='output file name (default = ../<parent_dir>.params)')
	args = parser.parse_args()

	instructions(args.epi_series_desc, args.output_file)
