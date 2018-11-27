import os
import threading
import subprocess
import asyncio
import logging
import json
from rtfMRI.utils import DebugLevels
from rtfMRI.Errors import ValidationError
from rtfMRI.StructDict import recurseCreateStructDict
from rtfMRI.RtfMRIClient import loadConfigFile
from rtAtten.RtAttenClient import RtAttenClient
from rtfMRI.WebInterface import Web


moduleDir = os.path.dirname(os.path.realpath(__file__))
registrationDir = os.path.join(moduleDir, 'registration/')
htmlIndex = os.path.join(moduleDir, 'web/html/index.html')


class RtAttenWeb():
    webInterface = None
    serverAddr = 'localhost'
    serverPort = 5200
    cfg = None
    client = None
    webClientThread = None
    registrationThread = None
    initialized = False

    @staticmethod
    def init(serverAddr, serverPort, cfg):
        RtAttenWeb.serverAddr = serverAddr
        RtAttenWeb.serverPort = serverPort
        RtAttenWeb.cfg = cfg
        RtAttenWeb.initialized = True
        RtAttenWeb.webInterface = Web()
        RtAttenWeb.webInterface.start(htmlIndex, RtAttenWeb.webUserCallback, None, 8888)

    @staticmethod
    def webUserCallback(client, message):
        assert RtAttenWeb.initialized is True
        request = json.loads(message)
        if 'config' in request:
            # Common code for any command that sends config information - retrieve the config info
            try:
                RtAttenWeb.cfg = recurseCreateStructDict(request['config'])
            except Exception as err:
                RtAttenWeb.webInterface.setUserError(str(err))
                return

        cmd = request['cmd']
        logging.log(DebugLevels.L3, "WEB CMD: %s", cmd)
        if cmd == "getDefaultConfig":
            RtAttenWeb.webInterface.sendUserConfig(RtAttenWeb.cfg)
        elif cmd == "run":
            if RtAttenWeb.webClientThread is not None:
                RtAttenWeb.webClientThread.join(timeout=1)
                if RtAttenWeb.webClientThread.is_alive():
                    RtAttenWeb.webInterface.setUserError("Client thread already runnning, skipping new request")
                    return
                RtAttenWeb.webClientThread = None
                RtAttenWeb.client = None
            RtAttenWeb.webClientThread = threading.Thread(name='webClientThread', target=RtAttenWeb.runClient)
            RtAttenWeb.webClientThread.setDaemon(True)
            RtAttenWeb.webClientThread.start()
        elif cmd == "stop":
            if RtAttenWeb.webClientThread is not None:
                if RtAttenWeb.client is not None:
                    RtAttenWeb.client.doStopRun()
        elif cmd == "runReg":
            if RtAttenWeb.registrationThread is not None:
                RtAttenWeb.registrationThread.join(timeout=1)
                if RtAttenWeb.registrationThread.is_alive():
                    RtAttenWeb.webInterface.setUserError("Registraion thread already runnning, skipping new request")
                    return
            RtAttenWeb.registrationThread = threading.Thread(name='registrationThread',
                                                             target=RtAttenWeb.runRegistration,
                                                             args=(request,))
            RtAttenWeb.registrationThread.setDaemon(True)
            RtAttenWeb.registrationThread.start()
        else:
            RtAttenWeb.webInterface.setUserError("unknown command " + cmd)

    @staticmethod
    def writeRegConfigFile(regGlobals, scriptPath):
        globalsFilename = os.path.join(scriptPath, 'globals_gen.sh')
        with open(globalsFilename, 'w') as fp:
            fp.write('#!/bin/bash\n')
            for key in regGlobals:
                fp.write(key + '=' + str(regGlobals[key]) + '\n')

    @staticmethod
    def runClient():
        assert RtAttenWeb.client is None
        RtAttenWeb.client = RtAttenClient()
        RtAttenWeb.client.setWebInterface(RtAttenWeb.webInterface)
        RtAttenWeb.client.runSession(RtAttenWeb.serverAddr, RtAttenWeb.serverPort, RtAttenWeb.cfg)
        RtAttenWeb.client = None

    @staticmethod
    def runRegistration(request, test=None):
        assert request['cmd'] == "runReg"
        regConfig = request['regConfig']
        regType = request['regType']
        dayNum = regConfig['dayNum']
        if None in (regConfig, regType, dayNum):
            RtAttenWeb.webInterface.setUserError("Registration missing a parameter")
            return
        asyncio.set_event_loop(asyncio.new_event_loop())
        # Create the globals.sh file in registration directory
        RtAttenWeb.writeRegConfigFile(regConfig, registrationDir)
        # Start bash command and monitor output
        if test is not None:
            cmd = test
        elif regType == 'skullstrip':
            if dayNum != 1:
                RtAttenWeb.webInterface.setUserError("Skullstrip can only be run for day1 data")
                return
            cmd = ['rtAtten/registration/skullstrip_t1.sh', '1']  # replace with real registration commands
        elif regType == 'registration':
            pass
        elif regType == 'makemask':
            pass
        else:
            RtAttenWeb.webInterface.setUserError("unknown registration type: " + regType)
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
                    RtAttenWeb.webInterface.sendUserMessage(json.dumps(response))
                else:
                    print(line, end='')
                outputLineCount += 1
        return outputLineCount


# def checkConfig(self, cfg):
#     if 'experiment' not in cfg.keys():
#         raise ValidationError("Experiment file must have \"experiment\" section")
#     if 'session' not in cfg.keys():
#         raise ValidationError("Experiment file must have \"session\" section")
#
#     if type(cfg.session.Runs) == str:
#         cfg.session.Runs = [int(x) for x in params.runs.split(',')]
#     if type(cfg.session.ScanNums) == str:
#         cfg.session.ScanNums = [int(x) for x in params.scans.split(',')]
#     return cfg
