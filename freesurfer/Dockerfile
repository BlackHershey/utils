# Use the official Freesurfer docker image from MGH as a base
FROM freesurfer/freesurfer:7.4.1@sha256:10b6468cbd9fcd2db3708f4651d59ad75d4da849a2c5d8bb6dba217f08b8c46b

# Install hostname command
RUN dnf makecache && dnf install -y hostname

# Add custom atlases
COPY custom_atlases/*.* /usr/local/freesurfer/average/
