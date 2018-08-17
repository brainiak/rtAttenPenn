#!/usr/bin/env bash
source ~/.bashrc
conda deactivate
conda activate rtAtten
# chmod o+rw /dev/ttyACM0
python rtfMRI/ttlPulse.py -d /dev/ttyACM0

