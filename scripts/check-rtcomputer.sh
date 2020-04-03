#!/usr/bin/env bash

#dataDrive=/mnt/rtexport/RTexport_Current/
dataDrive=/mnt/Data/
matlab=/opt/MATLAB/R2014a/bin/matlab

# Check internet access
wget -q --tries=3 --timeout=3 --spider http://www.google.com
if [[ $? -eq 0 ]]; then
    echo "OK: Internet Access"
else
    echo "FAILED: No Internet Access"
    exit -1
fi

# Check if mount drive is accessible
# nullglob will return '' empty string if no files found
echo "Checking access to $dataDrive"
files=($(shopt -s nullglob dotglob; ls $dataDrive))
if [[ ${#files[*]} -gt 0 ]]; then
    echo "OK: $dataDrive is accessible"
else
    echo "FAILED: $dataDrive not accessible or empty"
    exit -1
fi

uname -a | grep  3.10.0-514 &> /dev/null
if [[ $? -eq 0 ]]; then
    echo "OK: RHE 7.3 (514) Kernel running"
else
    echo "FAILED: Wrong Kernel running"
    exit -1
fi

nvidia-smi | grep 384 &> /dev/null
if [[ $? -eq 0 ]]; then
    echo "OK: NVidia driver 384 running"
else
    echo "FAILED: Wrong NVidia driver running"
    exit -1
fi

# Check if python (and conda) working properly
conda --version  &> /dev/null
if [[ $? -eq 0 ]]; then
    echo "OK: Conda installed"
else
    echo "FAILED: Conda not installed"
    exit -1
fi

source ~/.bashrc
conda activate rtAtten &> /dev/null
if [[ $? -eq 0 ]]; then
    echo "OK: Conda rtAtten environment installed"
else
    echo "FAILED: Conda rtAtten env not installed"
    exit -1
fi

python -c 'import numpy as np; a = np.array([1,2,3])'
if [[ $? -eq 0 ]]; then
    echo "OK: python and numpy installed"
else
    echo "FAILED: python installation error"
    exit -1
fi


# Check if Matlab working properly
$matlab -nodisplay -nodesktop -nosplash -r '2+3, quit'
if [[ $? -eq 0 ]]; then
    echo "OK: Matlab installed"
else
    echo "FAILED: Matlab not working"
    exit -1
fi
