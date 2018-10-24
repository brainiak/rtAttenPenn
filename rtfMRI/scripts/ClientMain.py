#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import sys
import os
import threading
import logging
import argparse
import json
# fix up search path
currPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(currPath, "../../")
sys.path.append(rootPath)
from rtAtten.RtAttenClient import RtAttenClient
from rtfMRI.RtfMRIClient import RtfMRIClient, loadConfigFile
from rtfMRI.BaseClient import BaseClient
from rtfMRI.Errors import InvocationError
import rtfMRI.scripts.ServerMain as ServerMain
from rtfMRI.utils import installLoggers, DebugLevels
from rtfMRI.StructDict import StructDict, recurseCreateStructDict
from rtfMRI.WebInterface import Web

# Globals
params = None
webClient = None
webClientThread = None


def ClientMain(params):
    installLoggers(logging.INFO, logging.DEBUG+1, filename='logs/rtAttenClient.log')

    # Start local server if requested
    if params.run_local is True:
        startLocalServer(params.port)

    if params.use_web:
        # run as web server listening for requests, listens on port 8888
        params.webInterface = Web()
        params.webInterface.start('rtAtten/web/html/index.html', webUserCallback, None, 8888)
    else:
        # run based on config file and passed in options
        cfg = loadConfigFile(params.experiment)
        params = checkAndMergeConfigs(params, cfg)
        RunClient(params)

    if params.run_local is True:
        stopLocalServer(params)

    return True


def webErrorResponse(client, errStr):
    print(errStr)
    response = {'cmd': 'error', 'error': errStr}
    params.webInterface.sendUserMessage(json.dumps(response))


def webUserCallback(client, message):
    global params
    global webClient
    global webClientThread
    request = json.loads(message)
    cmd = request['cmd']
    logging.log(DebugLevels.L3, "WEB CMD: %s", cmd)
    if cmd == "getDefaultConfig":
        cfg = loadConfigFile(params.experiment)
        params = checkAndMergeConfigs(params, cfg)
        response = {'cmd': 'config', 'value': params.cfg}
        params.webInterface.sendUserMessage(json.dumps(response))
    elif cmd == "run":
        if webClientThread is not None:
            webClientThread.join(timeout=1)
            if webClientThread.is_alive():
                webErrorResponse(client, "Client thread already runnning, skipping new request")
                return
            webClientThread = None
            webClient = None
        cfg_struct = recurseCreateStructDict(request['config'])
        try:
            params = checkAndMergeConfigs(params, cfg_struct)
        except Exception as err:
            webErrorResponse(client, str(err))
            return
        webClientThread = threading.Thread(name='webClientThread', target=RunClient, args=(params,))
        webClientThread.setDaemon(True)
        webClientThread.start()
    elif cmd == "stop":
        if webClientThread is not None:
            if webClient is not None:
                webClient.doStopRun()
    else:
        webErrorResponse(client, "unknown command " + cmd)


def checkAndMergeConfigs(params, cfg):
    if 'experiment' not in cfg.keys():
        raise InvocationError("Experiment file must have \"experiment\" section")
    if 'session' not in cfg.keys():
        raise InvocationError("Experiment file must have \"session\" section")

    if params.runs is not None:
        if params.scans is None:
            raise InvocationError(
                "Scan numbers must be specified when run numbers are specified.\n"
                "Use -s to input scan numbers that correspond to the runs entered.")
        cfg.session.Runs = [int(x) for x in params.runs.split(',')]
        cfg.session.ScanNums = [int(x) for x in params.scans.split(',')]
    params.cfg = cfg

    # Determine the desired model
    if params.model is None:
        if cfg.experiment.model is None:
            raise InvocationError("No model specified in experiment file")
        # Start up client logic for the specified model
        params.model = cfg.experiment.model
    return params


def RunClient(params):
    global webClient
    client: RtfMRIClient  # define a new variable of type RtfMRIClient
    if params.model == 'base':
        client = BaseClient()
    elif params.model == 'rtAtten':
        client = RtAttenClient()
        if params.webInterface is not None:
            client.setWebInterface(params.webInterface)
    else:
        raise InvocationError("Unsupported model %s" % (params.model))
    webClient = client
    # Run the session
    try:
        client.connect(params.addr, params.port)
        client.initSession(params.cfg)
        client.doRuns()
        client.endSession()
    except Exception as err:
        logging.log(logging.ERROR, "Client exception: %s", str(err))
    client.close()
    webClient = None


def startLocalServer(port):
    server_thread = threading.Thread(name='server', target=ServerMain.ServerMain, args=(port,))
    server_thread.setDaemon(True)
    server_thread.start()


def stopLocalServer(params):
    client = BaseClient()
    client.connect(params.addr, params.port)
    client.sendShutdownServer()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--addr', '-a', default='localhost', type=str, help='server ip address')
    parser.add_argument('--port', '-p', default=5200, type=int, help='server port')
    parser.add_argument('--experiment', '-e', default='conf/example.toml', type=str, help='experiment file (.json or .toml)')
    parser.add_argument('--model', '-m', default=None, type=str, help='model name')
    parser.add_argument('--runs', '-r', default=None, type=str, help='Comma separated list of run numbers')
    parser.add_argument('--scans', '-s', default=None, type=str, help='Comma separated list of scan number')
    parser.add_argument('--run-local', '-l', default=False, action='store_true', help='run client and server together locally')
    parser.add_argument('--use-web', '-w', default=False, action='store_true', help='Run client as a web portal')
    args = parser.parse_args()
    params = StructDict({'addr': args.addr, 'port': args.port, 'experiment': args.experiment,
                         'run_local': args.run_local, 'model': args.model, 'runs': args.runs,
                         'scans': args.scans, 'use_web': args.use_web})
    ClientMain(params)
