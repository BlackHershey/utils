import argparse
import os
import pathlib
from pydicom.fileset import FileSet

def combine_dicom_sessions(input_dir, output_dir, patient_info=None):
    print('Input directory = {}'.format(input_dir))
    print('Output directory = {}'.format(output_dir))
    if ( patient_info ):
        print('PatientName will be set to "{}"'.format(patient_info[0]))
        print('PatientID will be set to "{}"'.format(patient_info[1]))


    # create empty pydicom FileSet
    fs_in = FileSet()

    # Add all input images to FileSet
    for path, _, files in os.walk(input_dir):
        for name in files:
            dcmfilepath = pathlib.PurePath(path, name)
            try:
                fs_in.add(dcmfilepath)
            except:
                print('WARNING: Not a DICOM file: {}'.format(dcmfilepath))

    print(fs_in)

    # get study UIDs
    study_uids = fs_in.find_values('StudyInstanceUID')
    print('StudyUIDs = {}'.format(study_uids))
    first_study_uid = study_uids[0]
    print('First StudyUID = {}'.format(first_study_uid))

    # loop over StudyUIDs
    for idx, study_uid in enumerate(study_uids):
        dicom_file_instances = fs_in.find(StudyInstanceUID=study_uid)

        # loop over files, update StudyInstanceUID and SeriesNumber
        for dicom_file in dicom_file_instances:
            ds = dicom_file.load()

            # set StudyNumber to 1
            ds.StudyID = "1"

            # set StudyInstanceUID to first StudyInstanceUID
            ds.StudyInstanceUID = first_study_uid

            # set SeriesNumber to 100 + SeriesNumber for first partial set, 200 + SeriesNumber for second parital set, etc.
            ds.SeriesNumber = ds.SeriesNumber + 100 * (idx + 1)

            # optionally set PatientName and PatientID
            if ( patient_info ):
                ds.PatientName = patient_info[0]
                ds.PatientID = patient_info[1]

            # save DICOM file to output path
            _, output_file_name = os.path.split(dicom_file.path)
            ds.save_as(os.path.join(output_dir, output_file_name))


    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dir', help='Input directory containing DICOMs to be merged into one session')
    parser.add_argument('output_dir', help='Output directory for the merged session')
    parser.add_argument('--patient_info', action='store', nargs=2, metavar=('PATIENT_NAME', 'PATIENT_ID'), help='Set PatientName and PatientID tags to specified values')
    args = parser.parse_args()

    if ( args.patient_info ):
        combine_dicom_sessions(args.input_dir, args.output_dir, args.patient_info)
    else:
        combine_dicom_sessions(args.input_dir, args.output_dir)