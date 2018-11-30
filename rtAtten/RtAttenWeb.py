import os
import threading
import subprocess
import asyncio
import logging
import json
import re
from pathlib import Path
from rtfMRI.utils import DebugLevels
from rtfMRI.Errors import ValidationError
from rtfMRI.StructDict import recurseCreateStructDict
from rtfMRI.RtfMRIClient import loadConfigFile
from rtAtten.RtAttenClient import RtAttenClient, writeFile
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
    uploadImageThread = None
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
        elif cmd == "uploadImages":
            if RtAttenWeb.uploadImageThread is not None:
                RtAttenWeb.uploadImageThread.join(timeout=1)
                if RtAttenWeb.uploadImageThread.is_alive():
                    RtAttenWeb.webInterface.setUserError("Registraion thread already runnning, skipping new request")
                    return
            RtAttenWeb.uploadImageThread = threading.Thread(name='uploadImages',
                                                             target=RtAttenWeb.uploadImages,
                                                             args=(request,))
            RtAttenWeb.uploadImageThread.setDaemon(True)
            RtAttenWeb.uploadImageThread.start()
        else:
            RtAttenWeb.webInterface.setUserError("unknown command " + cmd)

    @staticmethod
    def writeRegConfigFile(regGlobals, scriptPath):
        globalsFilename = os.path.join(scriptPath, 'globals.sh')
        with open(globalsFilename, 'w') as fp:
            fp.write('#!/bin/bash\n')
            for key, val in regGlobals.items():
                if re.search('folder|dir|path', key, flags=re.IGNORECASE) is not None:
                    # prepend common writable directory to value
                    val = os.path.normpath('/data/' + val)
                fp.write(key + '=' + str(val) + '\n')
            fp.write('code_path=' + registrationDir)

    @staticmethod
    def runClient():
        assert RtAttenWeb.client is None
        RtAttenWeb.client = RtAttenClient()
        RtAttenWeb.client.setWebInterface(RtAttenWeb.webInterface)
        RtAttenWeb.client.runSession(RtAttenWeb.serverAddr, RtAttenWeb.serverPort, RtAttenWeb.cfg)
        RtAttenWeb.client = None

    @staticmethod
    def runRegistration(request, test=None):
        asyncio.set_event_loop(asyncio.new_event_loop())
        assert request['cmd'] == "runReg"
        try:
            regConfig = request['regConfig']
            regType = request['regType']
            dayNum = int(regConfig['dayNum'])
        except KeyError as err:
            RtAttenWeb.webInterface.setUserError("Registration missing a parameter ('regConfig', 'regType', 'dayNum')")
            return
        # Create the globals.sh file in registration directory
        RtAttenWeb.writeRegConfigFile(regConfig, registrationDir)
        # Start bash command and monitor output
        if test is not None:
            cmd = test
        elif regType == 'skullstrip':
            if dayNum != 1:
                RtAttenWeb.webInterface.setUserError("Skullstrip can only be run for day1 data")
                return
            cmd = ['bash', 'skullstrip_t1.sh', '1']
        elif regType == 'registration':
            if dayNum == 1:
                cmd = ['bash', 'reg_t1.sh']
            else:
                cmd = ['bash', 'reg_epi_day2.sh', '1', '1']
        elif regType == 'makemask':
            cmd = ['bash', 'run_makemask_nii.sh']
        else:
            RtAttenWeb.webInterface.setUserError("unknown registration type: " + regType)
            return

        proc = subprocess.Popen(cmd, cwd=registrationDir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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

    @staticmethod
    def uploadImages(request):
        asyncio.set_event_loop(asyncio.new_event_loop())
        assert request['cmd'] == "uploadImages"
        assert RtAttenWeb.webInterface is not None
        if len(RtAttenWeb.webInterface.wsDataConns) == 0:
            # A remote fileWatcher hasn't connected yet
            errStr = 'Waiting for fileWatcher to attach, please try again momentarily'
            RtAttenWeb.webInterface.setUserError(errStr)
            return
        try:
            scanFolder = request['scanFolder']
            scanNum = int(request['scanNum'])
            numDicoms = int(request['numDicoms'])
            uploadType = request['type']
        except KeyError as err:
            RtAttenWeb.webInterface.setUserError("Registration missing a parameter ('regConfig', 'regType', 'dayNum')")
            return
        watchFilePattern = "001_000{:03d}_0*".format(scanNum)
        RtAttenWeb.webInterface.initWatch(scanFolder, watchFilePattern, 1)
        fileType = Path(RtAttenWeb.cfg.session.dicomNamePattern).suffix
        outputFolder = os.path.normpath('/data/' + scanFolder)
        if not os.path.exists(outputFolder):
            os.makedirs(outputFolder)
        # send periodic progress reports to front-end
        dicomsInProgressInterval = numDicoms / 4
        intervalCount = 1
        response = {'cmd': 'uploadProgress', 'type': uploadType, 'progress': 'in-progress'}
        RtAttenWeb.webInterface.sendUserMessage(json.dumps(response))
        for i in range(1, numDicoms+1):
            filename = "001_{:06d}_{:06d}{}".format(scanNum, i, fileType)
            # print("uploading {} {}".format(scanFolder, filename))
            try:
                data = RtAttenWeb.webInterface.getFile(filename, asRawBytes=True)
            except Exception as err:
                RtAttenWeb.webInterface.setUserError(
                    "Error uploading file {}/{}: {}".format(scanFolder, filename, err))
                return
            # prepend with common '/data' path and write out file
            # note: can't just use os.path.join() because if two or more elements
            #   have an aboslute path it discards the earlier elements
            outputFilename = os.path.join(outputFolder, filename)
            writeFile(outputFilename, data)
            if i > intervalCount * dicomsInProgressInterval:
                val = 1/4 * intervalCount
                val = "{:.0f}%".format(val*100)
                response = {'cmd': 'uploadProgress', 'type': uploadType, 'progress': val}
                RtAttenWeb.webInterface.sendUserMessage(json.dumps(response))
                intervalCount += 1
        response = {'cmd': 'uploadProgress', 'type': uploadType, 'progress': 'complete \u2714'}
        RtAttenWeb.webInterface.sendUserMessage(json.dumps(response))


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
