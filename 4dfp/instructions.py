import argparse
import glob
import math
import os
import pydicom
import re

from params_common import write_file
from sys import exit, stderr

scan_number_pattern = '(?:\w*\.){3}(\d+)\..*'
sorted_path_template = 'study{}/*.dcm'
flat_path_template = '*/*.dcm'
nested_path_template = '*/{}/DICOM/*.dcm'


def find_dicoms(scan_number='*', sorted=False, inpath='.'):
	if sorted:
		return glob.glob(os.path.join(inpath, sorted_path_template.format(scan_number)))
	else:
		flat_files = [ f for f in glob.glob(os.path.join(inpath, flat_path_template)) if not f.startswith('study') ]
		if scan_number != '*':
			flat_files = [ f for f in flat_files if int(re.search(scan_number_pattern, dcm).groups(1)) == scan_number ]
		return flat_files if flat_files else glob.glob(os.path.join(inpath, nested_path_template.format(scan_number)))


def get_header_data(series_desc):
	series_map = {}
	studies_file = glob.glob('*.studies.txt')

	if not studies_file: # if dicoms are not sorted, search headers to find desired scans
		for dcm in find_dicoms():
			scan_number = re.search(scan_number_pattern, dcm).groups(1)

			if scan_number in series_map:
				continue
		
			ds = pydicom.read_file(dcm)
			if ds.SeriesDescription == series_desc:
				return ds
			else:
				series_map[scan_number] = ds.SeriesDescription
	else: # otherwise, grab a matching scan number from studies file
		with open(studies_file[0]) as f:
			for line in f:
				scan_num, _, desc, _ = line.split(' ')
				if series_desc in line:
					dcm = find_dicoms(scan_num, True)[0]
					return pydicom.read_file(dcm)
				series_map[scan_num] = desc

	stderr.write('No matching dicoms found!')
	print(set(series_map.values()))
	exit(1)


def calc_unpack_dim(img_dim, num_imgs):
	return img_dim / math.ceil(math.sqrt(num_imgs))


def instructions(series_desc, output_file=None):
	ds = get_header_data(series_desc)

	instructions = {
		'nx': calc_unpack_dim(ds.Rows, ds[0x19,0x100a].value),
		'ny': calc_unpack_dim(ds.Columns, ds[0x19,0x100a].value),
		'TR_vol': float(ds.RepetitionTime) / 1000,
		'TR_slc': 0,
		'TE_vol': float(ds.EchoTime)
	}

	# assume BOLD if 'BandwidthPerPixelPhaseEncode' in DICOM header
	bandwidth_tag = (0x19,0x1028)
	if bandwidth_tag:
		instructions['dwell'] = 1000 / (float(ds[bandwidth_tag].value) * instructions['nx'] )

		slice_timing = ds[0x19,0x1029].value

		# slice_timing only exists for multiband
		if slice_timing:
			MBfac = slice_timing.count(0) # get number of bands
			instructions['MBfac'] = MBfac

			num_slices = len(slice_timing)
			slice_time_tuples = sorted([ (time, slc) for slc, time in enumerate(slice_timing[:num_slices // MBfac]) ])
			slice_order = [ tup[1]+1 for tup in slice_time_tuples ]

			if slice_order == range(1, num_slices+1): # check if sequential
				instructions['interleave'] = '-S'
			elif all(slc % 2 == 0 for slc in slice_order[:len(slice_order) // 2]): # check for Siemen's interleave (starts with evens if even number of slices)
				instructions['Siemens_interleave'] = 1
			elif not all(slc % 2 != 0 for slc in slice_order[:len(slice_order) // 2]): # if not regular interleave (starts with odd slices and is enabled if no other interleave param is set), supply slice ordering
				instructions['seqstr'] = ','.join(map(str,slice_order))

	if not output_file:
		output_file = '../{}.params'.format(os.path.basename(os.path.abspath('..')))
	write_file(output_file, instructions)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Generate scan-specific instructions variables for cross_bold (to be run from subject dir)')
	parser.add_argument('epi_series_desc', help='series description for scan')
	parser.add_argument('-o', '--output_file', help='output file name (default = ../<parent_dir>.params)')
	args = parser.parse_args()

	instructions(args.epi_series_desc, args.output_file)
