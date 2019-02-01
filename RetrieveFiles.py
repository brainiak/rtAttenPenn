#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import sys
import argparse
from rtAtten.RtAttenClient import RtAttenClient
from rtfMRI.RtfMRIClient import loadConfigFile


if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument('--addr', '-a', default='localhost', type=str, help='server ip address')
    argParser.add_argument('--port', '-p', default=5200, type=int, help='server port')
    argParser.add_argument('--experiment', '-e', default='conf/example.toml', type=str, help='experiment file (.json or .toml)')
    argParser.add_argument('--runs', '-r', default=None, type=str, help='Comma separated list of run numbers')
    args = argParser.parse_args()

    cfg = loadConfigFile(args.experiment)

    client = RtAttenClient()
    client.connect(args.addr, args.port)
    client.initSession(cfg)
    for runId in args.runs.split(','):
        print('retrieve files for run {}'.format(runId))
        client.retrieveRunFiles(runId)

    client.endSession()
    client.disconnect()
    print('Done')
    sys.exit(0)

