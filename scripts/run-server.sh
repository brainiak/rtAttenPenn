#!/usr/bin/env bash
source ~/.bashrc
conda activate rtAtten
until server -p 5200; do
    echo "Server crashed with exit code $?.  Respawning.." >&2
    sleep 3
done
