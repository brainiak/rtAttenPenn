#!/usr/bin/env bash

if [ ! $# == 1 ]; then
  echo "Warning: no ip address supplied, credentials won't be updated"
else
  bash scripts/make-sslcert.sh $1
fi

# build javascritp files
pushd rtAtten/web
npm run build
popd

# start vnc server
bash scripts/run-vnc.sh &
VNCPID=$!

# activate conda python env
source ~/.bashrc
conda deactivate
conda activate rtAtten


# check if experiment file is supplied with -e filename
EXP_PARAM=''
if [ $# -gt 1 ]; then
  EXP_PARAM="$1 $2"
fi

# run rtAtten web server
python ClientMain.py -w -l $EXP_PARAM

kill -15 $VNCPID
