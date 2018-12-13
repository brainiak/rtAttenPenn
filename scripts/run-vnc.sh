#!/bin/bash
source ~/.bashrc
conda deactivate
conda activate websockify

vncserver :1 -SecurityTypes None &

websockify --cert certs/rtAtten.crt --key certs/rtAtten_private.key 6080 localhost:5901

vncserver -kill :1
