#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import os
import sys
import traceback
import threading
import logging
import argparse
import ServerMain
from rtAtten.RtAttenClient import RtAttenClient
from rtfMRI.RtfMRIClient import RtfMRIClient, loadConfigFile
from rtfMRI.BaseClient import BaseClient
from rtfMRI.Errors import InvocationError
from rtfMRI.utils import installLoggers
from rtfMRI.StructDict import StructDict


def ClientMain(params):
    installLoggers(logging.INFO, logging.INFO, filename='logs/rtAttenClient.log')

    # Create a thread reading from stdin to detect if parent process exited and if so then exit this process
    exitThread = threading.Thread(name='exitThread', target=processShouldExitThread, args=(params,))
    exitThread.setDaemon(True)
    exitThread.start()

    webpipes = None
    if params.webpipe is not None:
        # Open the in and out named pipes and pass to RtAttenClient for communication
        # with the webserver process. Open command on a pipe blocks until the other
        # end opens it as well. Therefore open the reader first here and the writer
        # first within the webserver.
        webpipes = StructDict()
        webpipes.name_in = params.webpipe + '.toclient'
        webpipes.name_out = params.webpipe + '.fromclient'
        webpipes.fd_in = open(webpipes.name_in, mode='r')
        webpipes.fd_out = open(webpipes.name_out, mode='w', buffering=1)

    cfg = loadConfigFile(params.experiment)
    params = mergeParamsConfigs(params, cfg)

    # Start local server if requested
    if params.run_local is True:
        startLocalServer(params.port)

    # run based on config file and passed in options
    client: RtfMRIClient  # define a new variable of type RtfMRIClient
    if params.cfg.experiment.model == 'base':
        client = BaseClient()
    elif params.cfg.experiment.model == 'rtAtten':
        client = RtAttenClient()
        if params.webpipe is not None:
            client.setWeb(webpipes, params.webfilesremote)
    else:
        raise InvocationError("Unsupported model %s" % (params.cfg.experiment.model))
    try:
        client.runSession(params.addr, params.port, params.cfg)
    except Exception as err:
        print(err)
        traceback_str = ''.join(traceback.format_tb(err.__traceback__))
        print(traceback_str)

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
    logLevel = 30  # Warn
    server_thread = threading.Thread(name='server', target=ServerMain.ServerMain, args=(port, logLevel))
    server_thread.setDaemon(True)
    server_thread.start()


def stopLocalServer(params):
    client = BaseClient()
    client.connect(params.addr, params.port)
    client.sendShutdownServer()


def processShouldExitThread(params):
    '''If this client was spawned by a parent process, then by listening on
    stdin we can tell that the parent process exited when stdin is closed. When
    stdin is closed we can exit this process as well.
    '''
    print('processShouldExitThread: starting', flush=True)
    while True:
        data = sys.stdin.read()
        if len(data) == 0:
            print('processShouldExitThread: stdin closed, exiting', flush=True)
            os._exit(0)  # - this kills everything immediately
            break


if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument('--addr', '-a', default='localhost', type=str, help='server ip address')
    argParser.add_argument('--port', '-p', default=5200, type=int, help='server port')
    argParser.add_argument('--experiment', '-e', default='conf/example.toml', type=str,
                           help='experiment file (.json or .toml)')
    argParser.add_argument('--model', '-m', default=None, type=str, help='model name')
    argParser.add_argument('--runs', '-r', default=None, type=str,
                           help='Comma separated list of run numbers')
    argParser.add_argument('--scans', '-s', default=None, type=str,
                           help='Comma separated list of scan number')
    argParser.add_argument('--run-local', '-l', default=False, action='store_true',
                           help='run client and server together locally')
    argParser.add_argument('--webpipe', '-w', default=None, type=str,
                           help='Named pipe to communicate with webServer')
    argParser.add_argument('--webfilesremote', '-x', default=False, action='store_true',
                           help='dicom files retrieved from remote server')
    args = argParser.parse_args()
    params = StructDict({'addr': args.addr, 'port': args.port, 'run_local': args.run_local,
                         'model': args.model, 'experiment': args.experiment,
                         'runs': args.runs, 'scans': args.scans,
                         'webpipe': args.webpipe, 'webfilesremote': args.webfilesremote})
    ClientMain(params)
