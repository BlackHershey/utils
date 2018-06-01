import argparse
import numpy as np
from scipy import stats

import matplotlib
matplotlib.use('Qt4Agg') # must be set prior to pyplot import
from matplotlib import pyplot


def find_dvar_crit(dvars):
	mode = stats.mode(dvars)[0]
	sd = np.std(dvars)
	return mode + (2.5 * sd)


def plot_values(value_file, thresh=None, dvars=False, run=None, num_runs=None):
	vals = [ float(line.split('\t')[0]) for line in open(value_file).readlines() ]

	if run and num_runs:
		num_frames = len(vals) / num_runs
		start = (run - 1) * num_frames 
		vals = vals[start:start+num_frames]

	vals = [ x for x in vals if x != 500 ]

	pyplot.plot(vals)

	if dvars and not thresh:
		thresh = find_dvar_crit(vals)
	if thresh:
		pyplot.plot([ thresh for x in range(len(vals)) ])

	pyplot.savefig(value_file + '.png')


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('input_file', help='FD or dvars values file')
	parser.add_argument('--thresh', type=float, help='specify the movement threshold')
	parser.add_argument('--dvars', action='store_true')
	parser.add_argument('--run', type=int, help='which run to plot (defualt is all runs in file)')
	parser.add_argument('--num_runs', type=int, help='how many runs are in file')
	args = parser.parse_args()

	plot_values(args.input_file, args.thresh, args.dvars, args.run, args.num_runs)
	 



