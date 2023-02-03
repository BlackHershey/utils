import importlib
import json
import os
import re
import sys

def get_key(template, outtype=('nii.gz',), annotation_classes=None):
    if not template:
        raise ValueError('Template must be a valid format string')

    return template, outtype, annotation_classes


# if an infotoids script was copied into container, import + call the overloaded infotoids function
if os.path.exists('/data/infotoids.py'):
    sys.path.append('/data')
    infotoids = getattr(importlib.import_module('infotoids'), 'infotoids')
    

def infotodict(seqinfo):
    available_series_descriptions = [ s.series_description for s in seqinfo ]

    with open('/data/heuristic.json') as f:
        heuristic = json.load(f)

    bidsmap = heuristic['bidsmap']
    use_regex = heuristic['series_desc_regex']

    # subject/session needs to be escaped since we do not fill it in, heudiconv does
    if heuristic['multi_session']:
        bidsname_template = 'sub-{{subject}}/{{session}}/{0}/sub-{{subject}}_{{session}}_{1}'
    else:
        bidsname_template = 'sub-{{subject}}/{0}/sub-{{subject}}_{1}'

    # Collapse human-readable JSON to dict for processing
    # Dict setup:
    #   key: tuple of tuples containing field/value pairs for properties to match on for a series (starting with description which should always be present)
    #   value: bidsname
    # Example: { (('SeriesDescription', 'ABCD_T1w_MPR_vNav'), ('ImageType', 'ORIGINAL\\PRIMARY\\M\\ND\\NORM')): 'sub-{subject}_{session}_acq-norm_T1w' }
    bidsnamemap = {}
    for folder, scan_maps in bidsmap.items():
        for mapping in scan_maps:
            # if use_regex, create bidsnamemap entry per regex-matched series description
            if use_regex:
                series_desc_matches = [ re.search(mapping['series_description'], desc) for desc in available_series_descriptions ]
                descs = [ item.group() for item in series_desc_matches if item ]
            # otherwise, only create one for exact match
            else:
                descs = mapping['series_description']

            criteria =  [ (crit['field'], crit['value']) if crit['field'] != 'image_type' else (crit['field'], tuple(crit['value'].split('\\')))  \
                for crit in (mapping['match_criteria'] if 'match_criteria' in mapping else []) ] # image_type needs to be handled specially - since it's a tuple in seqinfo but a sting in dcm header
            for d in descs:
                bidsnamemap[tuple([('series_description', d)] + criteria)] = bidsname_template.format(folder, mapping['template'])

    print(bidsnamemap)

    bidsSeriesDescCritMap = { tup[0][1]: [ tup[i][0] for i in range(1, len(tup)) ] for tup in bidsnamemap.keys() } # create map of fields that we care about for a series description

    info = { get_key(v): [] for v in bidsnamemap.values() }
    for s in seqinfo:
        series_props = s._asdict() # convert namedtuple to dict so we can do bracket indexing

        if s.series_description not in bidsSeriesDescCritMap.keys():
            print('Series desc not found in bids map', s.series_description)
            continue

        # create tuple of tuple identifier for current series & check bidsname map to see if it exists
        series_identifier = [ ('series_description', s.series_description) ]
        series_identifier += [ (crit, series_props[crit]) for crit in bidsSeriesDescCritMap[s.series_description] ]
        series_identifier = tuple(series_identifier)

        if series_identifier not in bidsnamemap:
            print('Identifier not found in bidsmap', series_identifier)
            continue

        bidsname = bidsnamemap[series_identifier]
        info[get_key(bidsname)].append(s.series_id)

    print(info)

    return info
