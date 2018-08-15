#!/usr/bin/env bash
source ~/.bashrc
conda deactivate
conda activate rtAtten
chmod o+rw /dev/ttyACM0
until python rtfMRI/ttlPulse.py -d /dev/ttyACM0; do
    echo "Server crashed with exit code $?.  Respawning.." >&2
    sleep 3
done
