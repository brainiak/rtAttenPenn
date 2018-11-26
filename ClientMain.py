#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import os
import threading
import subprocess
import asyncio
import logging
import argparse
import json
import ServerMain
from rtAtten.RtAttenClient import RtAttenClient
from rtfMRI.RtfMRIClient import RtfMRIClient, loadConfigFile
from rtfMRI.BaseClient import BaseClient
from rtfMRI.Errors import InvocationError
from rtfMRI.utils import installLoggers, DebugLevels
from rtfMRI.StructDict import StructDict, recurseCreateStructDict
from rtfMRI.WebInterface import Web

# Globals
params = StructDict()
webClient = None
webClientThread = None
registrationThread = None
registrationDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'rtAtten/registration')


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


def webUserCallback(client, message):
    global params
    global webClient
    global webClientThread
    global registrationThread
    request = json.loads(message)
    cmd = request['cmd']
    # Common code for any command that sends config information - integrate into params
    if 'config' in request:
        try:
            cfg_struct = recurseCreateStructDict(request['config'])
            params = checkAndMergeConfigs(params, cfg_struct)
        except Exception as err:
            params.webInterface.setUserError(str(err))
            return

    logging.log(DebugLevels.L3, "WEB CMD: %s", cmd)
    if cmd == "getDefaultConfig":
        cfg = loadConfigFile(params.experiment)
        try:
            params = checkAndMergeConfigs(params, cfg)
        except Exception as err:
            params.webInterface.setUserError("Loading default config: " + str(err))
            return
        params.webInterface.sendUserConfig(cfg)
    elif cmd == "run":
        if webClientThread is not None:
            webClientThread.join(timeout=1)
            if webClientThread.is_alive():
                params.webInterface.setUserError("Client thread already runnning, skipping new request")
                return
            webClientThread = None
            webClient = None
        webClientThread = threading.Thread(name='webClientThread', target=RunClient, args=(params,))
        webClientThread.setDaemon(True)
        webClientThread.start()
    elif cmd == "stop":
        if webClientThread is not None:
            if webClient is not None:
                webClient.doStopRun()
    elif cmd == "runReg":
        if registrationThread is not None:
            registrationThread.join(timeout=1)
            if registrationThread.is_alive():
                params.webInterface.setUserError("Registraion thread already runnning, skipping new request")
                return
        registrationThread = threading.Thread(name='registrationThread', target=runRegistration, args=(params, request,))
        registrationThread.setDaemon(True)
        registrationThread.start()
    else:
        params.webInterface.setUserError("unknown command " + cmd)


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


def writeRegConfigFile(regGlobals, scriptPath):
    globalsFilename = os.path.join(scriptPath, 'globals_gen.sh')
    with open(globalsFilename, 'w') as fp:
        fp.write('#!/bin/bash\n')
        for key in regGlobals:
            fp.write(key + '=' + str(regGlobals[key]) + '\n')


def runRegistration(params, request, test=None):
    global registrationDir
    assert request['cmd'] == "runReg"
    regConfig = request['regConfig']
    regType = request['regType']
    dayNum = regConfig['dayNum']
    if None in (regConfig, regType, dayNum):
        params.webInterface.setUserError("Registration missing a parameter")
        return
    asyncio.set_event_loop(asyncio.new_event_loop())
    # Create the globals.sh file in registration directory
    writeRegConfigFile(regConfig, registrationDir)
    # Start bash command and monitor output
    if test is not None:
        cmd = test
    elif regType == 'skullstrip':
        if dayNum != 1:
            params.webInterface.setUserError("Skullstrip can only be run for day1 data")
            return
        cmd = ['rtAtten/registration/skullstrip_t1.sh', '1']  # replace with real registration commands
    elif regType == 'registration':
        pass
    elif regType == 'makemask':
        pass
    else:
        params.webInterface.setUserError("unknown registration type: " + regType)
        return

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    outputLineCount = 0
    line = 'start'
    # subprocess poll returns None while subprocess is running
    while(proc.poll() is None or line != ''):
        line = proc.stdout.readline().decode('utf-8')
        if line != '':
            # send output to web interface
            if test is None:
                response = {'cmd': 'regLog', 'value': line}
                params.webInterface.sendUserMessage(json.dumps(response))
            else:
                print(line, end='')
            outputLineCount += 1
    return outputLineCount


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
