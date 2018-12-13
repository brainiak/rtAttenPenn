#!/usr/bin/env bash
source ~/.bashrc
conda deactivate
conda activate rtAtten
until python ServerMain.py -p 5200; do
    echo "Server crashed with exit code $?.  Respawning.." >&2
    sleep 3
done
