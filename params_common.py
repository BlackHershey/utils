
# helper function to generate a csh variable declaration string from variable name/value pairs
def convert_to_csh(var, value):
	csh = 'set {0: <5} = '.format(var)

	if isinstance(value, list):
		csh += '( {} )'.format(' '.join('{0: <2}'.format(v) for v in value))
	else:
		csh += str(value)

	return csh

# helper function to write csh variables to file
def write_file(filename, params):
	with open(filename, 'w') as f:
		for key in params.keys():
			f.write(convert_to_csh(key, params[key]) + '\n')
	return

