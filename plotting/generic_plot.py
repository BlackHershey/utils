import argparse
import pandas as pd
import numpy as np

from cycler import cycler
from matplotlib import pyplot as plt

def plot_csv(data_file, x_col, y_col, group_by=None, kind='line', subplots=(), grid=False, trailer=''):
	print('sp', subplots)
	if kind == 'line':
		colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
		plt.rc('axes', prop_cycle=(cycler('linestyle', ['-', ':']) * cycler('color', colors)))

	df = pd.read_csv(data_file)
	
	xlims = (df[x_col].min(), df[x_col].max())
	ylims = (df[y_col].min()-5, df[y_col].max()+5)

	nrows, ncols = subplots if subplots else (1,1)
	fig, axes = plt.subplots(nrows, ncols, figsize=(nrows*4,ncols*4), sharex=True, sharey=True)

	if not group_by:
		df.plot(x_col, y_col, ax=axes, kind=kind)
	else:
		g_df = df.groupby(group_by)

		print(axes)
		if not subplots:
			axes = np.array([axes] * len(g_df.groups))
		
		for (key, ax) in zip(sorted(g_df.groups.keys()), axes.flatten()):
			ax.set_xlim(xlims[0], xlims[1])
			ax.set_ylim(ylims[0], ylims[1])
			g_df.get_group(key).plot(x_col, y_col, label=key, ax=ax, kind=kind)
			if grid:
				ax.grid(True)

		#for label, g_df in df.groupby(group_by):
		#	g_df.plot(x_col, y_col, ax=ax, kind=kind)
		
		if not subplots:
			plt.legend(loc='center left', bbox_to_anchor=(1.04,.5))
			plt.subplots_adjust(right=0.75)

	
	plt.show()
	


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('data_file', help='csv file containing data to plot')
	parser.add_argument('x_col', help='column to plot on x-axis')
	parser.add_argument('y_col', help='column to plot on y-axis')
	parser.add_argument('-g', '--group_by', help='column used to split data into separate datasets (default is all data in one set)')
	parser.add_argument('--grid', action='store_true', help='show grid lines')
	parser.add_argument('-k', '--kind', default='line', choices=['line','bar','barh','hist','box','kde','area','pie','scatter','hexbin', 'violin'], help='type of graph (defaut=line)')
	parser.add_argument('-s', '--subplots', type=int, nargs=2, help='how to split groups into different graphs (i.e. 3 2 would give 3 rows by 2 cols; default is all on same graph)')
	parser.add_argument('-t', '--trailer', help='trailer for output file name(s)')
	args = parser.parse_args()

	plot_csv(args.data_file, args.x_col, args.y_col, args.group_by, args.kind, tuple(args.subplots) if args.subplots else None, args.grid, args.trailer)
