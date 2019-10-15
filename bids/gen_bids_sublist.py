import argparse
import numpy as np
import os
import re

from glob import glob

DEFAULT_OUTFILE = 'subjects.lst'


def generate_lst(dcm_pattern, sub_regex, ses_regex=None, pad_session=0, outfile=DEFAULT_OUTFILE):
    match_sub = re.compile(sub_regex)
    match_ses = re.compile(ses_regex) if ses_regex else None

    dcms = [ dcm for pattern in dcm_pattern for dcm in glob(pattern) ]
    dcm_folders = set([ os.path.dirname(os.path.realpath(f)) for f in dcms])

    rows = set()
    for folder in dcm_folders:
        folder = re.sub('(/)\d+(/DICOM)', r'\1*\2', folder, flags=re.IGNORECASE)
        sub = match_sub.search(folder).group(1)
        ses = match_ses.search(folder).group(1) if match_ses else None
        if pad_session and ses.isdigit():
            ses = ses.zfill(pad_session)
        rows.add((folder, sub, ses))

    np.savetxt(outfile, list(rows), fmt='%s', delimiter='\t')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dcm-pattern', required=True, nargs='+', help='unix-style pattern to match dcm files for study')
    parser.add_argument('--sub-regex', required=True)
    parser.add_argument('--ses-regex')
    parser.add_argument('--pad-session', nargs=1, type=int, help='length to 0-pad session (if session string is digit)')
    parser.add_argument('--outfile', default=DEFAULT_OUTFILE)
    args = parser.parse_args()

    generate_lst(args.dcm_pattern, args.sub_regex, args.ses_regex, args.pad_session, args.outfile)
