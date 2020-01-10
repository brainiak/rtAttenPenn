#!/usr/bin/env bash

# Save command line params
PARAMS=$@

while test $# -gt 0
do
  case "$1" in
    -h)
      echo "$0 [-e <toml_file>] [-ip <local_ip_or_hostname>] [--server <remote_classification_server:port>] [--localfiles] [--filewatcher [-u <username> -p <password>]]"
      exit 0
      ;;
    --filewatcher) RUNFILEWATCHER=1
      ;;
    -u) USERNAME=$2
      ;;
    -p) PASSWORD=$2
      ;;
  esac
  shift
done

# start vnc server
bash scripts/run-vnc.sh &
VNCPID=$!

FILEWATCHER_PID=''
if [ ! -z $RUNFILEWATCHER ]; then
  # Run filewatcher
  if [ ! -z $USERNAME && ! -z $PASSWORD ]; then
    python fileWatchServer.py -s localhost:8888 -i 5 -u $USERNAME -p $PASSWORD &
    FILEWATCHER_PID=$!
  else
    echo "Must specify -u username -p password for use with --filewatcher"
    exit -1
  fi

fi

scriptDir=`dirname $0`
bash $scriptDir/run-web-core.sh $PARAMS

if [ ! -z $FILEWATCHER_PID ]; then
  kill -15 $FILEWATCHER_PID
fi

kill -15 $VNCPID
