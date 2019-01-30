#!/usr/bin/env bash

while test $# -gt 0
do
  case "$1" in
    -ip) IP=$2
      ;;
    -e) CFG=$2
      ;;
  esac
  shift
done

if [ -z $IP ]; then
  echo "Warning: no ip address supplied, credentials won't be updated"
else
  bash scripts/make-sslcert.sh $IP
fi

# build javascritp files
pushd webInterface/rtAtten/web
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
if [ ! -z $CFG ]; then
  EXP_PARAM="-e $CFG"
fi

# run rtAtten web server
echo "python WebMain.py -l -r $EXP_PARAM"
python WebMain.py -l -r $EXP_PARAM

kill -15 $VNCPID
