# utils
General imaging utility scripts for the lab

*4dfp/*
  
  Scripts to help set up data to be run through 4dfp pipelines
  - instructions.py: extract study parameters from DICOM headers to form base of 4dfp instructions file
  - mgz_to_4dfp.csh: utility for 2-step conversion of mgz to 4dfp file format
  - params_common.py: helper functions for writing a 4dfp participant params file
  - params_setup.py: generates a participant params file using premade study configuration based on series description

*bids/*
 
 Scripts to convert data to BIDS format and run BIDS app on converted data
  - *config/*
    - generic_convertall.py: script to be passed to run_heudiconv to allow conversion spec to be JSON mapping (versus python script)
  - bids_scan_lookup.py: get mapping of bids filename to MR session series number
  - gen_bids_sub_list.py: utility to generate lookup table of DICOM location for each subject/session (output is used in run_heudiconv)
  - run_heudiconv.py: convert all missing subject data to BIDS format and optionally run MRIQC
  - vnav2bids_v2.py: pull vNav motion numbers from setter DICOM headers and match with correct anatomical scan
  
*cnda/*
 
 Scripts to facilitate download of data from CNDA
  - cnda_common.py: helper functions for API calls to CNDA
  - download_dicoms.py: downloads and unzips specific scans from CNDA
  - facemask_helper.py: identify which scans have not been run through facemasking pipeline on CNDA
  
*freesurfer/*
  
  Scripts to call FS and extract ROIs and quality metrics
  - euler_number.py: create table of euler number (QC metric) for each scan
  - gen_fs_calls.csh: create script to launch FS for a subject (can be used with 'at now' call)
  - make_fs_masks.csh: create masks for any ROI as 4dfp atlas-aligned images
  
*plotting/*
  
  Scripts to generate frequently used graphs
  - generic_plot.py: attempt to have generic code base to make plots from any CSV
  - plot_FD.py: generate graphs of patient movement
  
study_config_template.json: example configuration for using study_setup

study_setup.py: script for setting up data to be run through common piplines; steps: (1) download missing scans from CNDA, (2) generate 4dfp params file, (3) create FS call + run
