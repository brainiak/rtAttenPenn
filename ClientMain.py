#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import threading
import logging
import argparse
import ServerMain
from rtAtten.RtAttenClient import RtAttenClient
from rtAtten.RtAttenWeb import RtAttenWeb
from rtfMRI.RtfMRIClient import RtfMRIClient, loadConfigFile
from rtfMRI.BaseClient import BaseClient
from rtfMRI.Errors import InvocationError
from rtfMRI.utils import installLoggers
from rtfMRI.StructDict import StructDict


def ClientMain(params):
    installLoggers(logging.INFO, logging.DEBUG+1, filename='logs/rtAttenClient.log')

    cfg = loadConfigFile(params.experiment)
    params = mergeParamsConfigs(params, cfg)

    # Start local server if requested
    if params.run_local is True:
        startLocalServer(params.port)

    if params.use_web:
        # run as web server listening for requests
        if params.cfg.experiment.model == 'rtAtten':
            # call starts web listen thread and doesn't return
            rtAttenWeb = RtAttenWeb()
            rtAttenWeb.init(params.addr, params.port, params.cfg)
        else:
            raise InvocationError("Web client: Unsupported model %s" % (params.cfg.experiment.model))
    else:
        # run based on config file and passed in options
        client: RtfMRIClient  # define a new variable of type RtfMRIClient
        if params.cfg.experiment.model == 'base':
            client = BaseClient()
        elif params.cfg.experiment.model == 'rtAtten':
            client = RtAttenClient()
        else:
            raise InvocationError("Unsupported model %s" % (params.cfg.experiment.model))
        try:
            client.runSession(params.addr, params.port, params.cfg)
        except Exception as err:
            print(err)

    if params.run_local is True:
        stopLocalServer(params)

    return True


def mergeParamsConfigs(params, cfg):
    if params.runs is not None:
        if params.scans is None:
            raise InvocationError(
                "Scan numbers must be specified when run numbers are specified.\n"
                "Use -s to input scan numbers that correspond to the runs entered.")
        cfg.session.Runs = [int(x) for x in params.runs.split(',')]
        cfg.session.ScanNums = [int(x) for x in params.scans.split(',')]

    # Determine the desired model
    if params.model is not None:
        cfg.experiment.model = params.model
    else:
        if cfg.experiment.model is None:
            raise InvocationError("No model specified in experiment file")

    params.cfg = cfg
    return params


def startLocalServer(port):
    server_thread = threading.Thread(name='server', target=ServerMain.ServerMain, args=(port,))
    server_thread.setDaemon(True)
    server_thread.start()


def stopLocalServer(params):
    client = BaseClient()
    client.connect(params.addr, params.port)
    client.sendShutdownServer()


if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument('--addr', '-a', default='localhost', type=str, help='server ip address')
    argParser.add_argument('--port', '-p', default=5200, type=int, help='server port')
    argParser.add_argument('--experiment', '-e', default='conf/example.toml', type=str, help='experiment file (.json or .toml)')
    argParser.add_argument('--model', '-m', default=None, type=str, help='model name')
    argParser.add_argument('--runs', '-r', default=None, type=str, help='Comma separated list of run numbers')
    argParser.add_argument('--scans', '-s', default=None, type=str, help='Comma separated list of scan number')
    argParser.add_argument('--run-local', '-l', default=False, action='store_true', help='run client and server together locally')
    argParser.add_argument('--use-web', '-w', default=False, action='store_true', help='Run client as a web portal')
    args = argParser.parse_args()
    params = StructDict({'addr': args.addr, 'port': args.port, 'experiment': args.experiment,
                         'run_local': args.run_local, 'model': args.model, 'runs': args.runs,
                         'scans': args.scans, 'use_web': args.use_web})
    ClientMain(params)
