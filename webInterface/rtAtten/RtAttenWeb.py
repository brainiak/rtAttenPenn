import os
import io
import threading
import subprocess
import psutil
import queue
import time
import math
import logging
import random
import json
import re
import toml
import shlex
from PIL import Image
from pathlib import Path
from base64 import b64encode
from rtfMRI.utils import DebugLevels, copyFileWildcard
from rtfMRI.StructDict import StructDict, recurseCreateStructDict
from rtfMRI.Errors import RequestError, StateError, InvocationError
from rtAtten.RtAttenModel import getRunDir
from webInterface.WebServer import Web, CommonOutputDir
from webInterface.WebServer import makeFifo, handleFifoRequests, resignalFifoThreadExit
from webInterface.WebClientUtils import getFileReqStruct


moduleDir = os.path.dirname(os.path.realpath(__file__))
rootDir = os.path.join(moduleDir, "../../")
registrationDir = os.path.join(moduleDir, 'registration/')
patternsDir = os.path.join(moduleDir, 'patterns/')
webDir = os.path.join(moduleDir, 'web')
htmlDir = os.path.join(moduleDir, 'web/html')
confDir = os.path.join(moduleDir, 'conf/')
if not os.path.exists(confDir):
    os.makedirs(confDir)


class RtAttenWeb():
    webServer = Web()
    rtserver = 'localhost:5200'
    rtlocal = True
    filesremote = False
    feedbackdir = 'webInterface/images'
    cfg = None
    initialized = False
    stopRun = False
    stopReg = False
    runSessionThread = None
    registrationThread = None
    uploadImageThread = None
    fifoFileThread = None
    numFaceFiles = 0
    numSceneFiles = 0

    @staticmethod
    def init(params, cfg):
        RtAttenWeb.rtserver = params.rtserver or RtAttenWeb.rtserver
        RtAttenWeb.rtlocal = params.rtlocal or RtAttenWeb.rtlocal
        RtAttenWeb.filesremote = params.filesremote or RtAttenWeb.filesremote
        RtAttenWeb.feedbackdir = params.feedbackdir or RtAttenWeb.feedbackdir
        RtAttenWeb.cfg = cfg
        RtAttenWeb.stopRun = False
        RtAttenWeb.stopReg = False
        # Get number of image files in FACE and SCENE directories
        faceImagesDir = os.path.join(RtAttenWeb.feedbackdir, 'FACE')
        sceneImagesDir = os.path.join(RtAttenWeb.feedbackdir, 'SCENE')
        if not os.path.exists(faceImagesDir) or not os.path.exists(sceneImagesDir):
            raise InvocationError('Directory for FACE or SCENE missing: {}, {}'.format(faceImagesDir, sceneImagesDir))
        # TODO - list only .jpg files when doing count
        RtAttenWeb.numFaceFiles = len(os.listdir(faceImagesDir))
        RtAttenWeb.numSceneFiles = len(os.listdir(sceneImagesDir))
        if RtAttenWeb.numFaceFiles == 0 or RtAttenWeb.numSceneFiles == 0:
            raise StateError('FACE or SCENE image directory empty')
        RtAttenWeb.initialized = True
        RtAttenWeb.webServer.start(htmlDir=htmlDir,
                                   userCallback=RtAttenWeb.webUserCallback,
                                   subjCallback=RtAttenWeb.webSubjCallback,
                                   eventCallback=RtAttenWeb.eventCallback,
                                   port=8888)

    @staticmethod
    def webUserCallback(client, message):
        if RtAttenWeb.initialized is not True:
            raise StateError('webUserCallback: RtAttenWeb not initialized')
        request = json.loads(message)
        if 'config' in request:
            # Common code for any command that sends config information - retrieve the config info
            cfgData = request['config']
            newCfg = recurseCreateStructDict(cfgData)
            if newCfg is not None:
                RtAttenWeb.cfg = newCfg
            else:
                if cfgData is None:
                    errStr = 'webUserCallback: Config field is None'
                elif type(cfgData) not in (dict, list):
                    errStr = 'webUserCallback: Config field wrong type {}'.format(type(cfgData))
                else:
                    errStr = 'webUserCallback: Error parsing config field {}'.format(cfgData)
                RtAttenWeb.webServer.setUserError(errStr)
                return

        cmd = request['cmd']
        logging.log(DebugLevels.L3, "WEB USER CMD: %s", cmd)
        if cmd == "getDefaultConfig":
            if 'session' in RtAttenWeb.cfg:
                # remove the roiInds ndarray because it can't be Jsonified.
                del RtAttenWeb.cfg.session.roiInds
            RtAttenWeb.webServer.sendUserConfig(RtAttenWeb.cfg, filesremote=RtAttenWeb.filesremote)
        elif cmd == "run":
            if RtAttenWeb.runSessionThread is not None:
                RtAttenWeb.runSessionThread.join(timeout=1)
                if RtAttenWeb.runSessionThread.is_alive():
                    RtAttenWeb.webServer.setUserError("Client thread already runnning, skipping new request")
                    return
                RtAttenWeb.runSessionThread = None
            RtAttenWeb.stopRun = False
            RtAttenWeb.runSessionThread = threading.Thread(name='runSessionThread', target=RtAttenWeb.runSession)
            RtAttenWeb.runSessionThread.setDaemon(True)
            RtAttenWeb.runSessionThread.start()
        elif cmd == "stop":
            if RtAttenWeb.runSessionThread is not None:
                RtAttenWeb.stopRun = True
                RtAttenWeb.runSessionThread.join(timeout=1)
                if not RtAttenWeb.runSessionThread.is_alive():
                    RtAttenWeb.runSessionThread = None
                    RtAttenWeb.stopRun = False
        elif cmd == "runReg":
            if RtAttenWeb.registrationThread is not None:
                RtAttenWeb.registrationThread.join(timeout=1)
                if RtAttenWeb.registrationThread.is_alive():
                    RtAttenWeb.webServer.setUserError("Registraion thread already runnning, skipping new request")
                    return
            RtAttenWeb.stopReg = False
            RtAttenWeb.registrationThread = threading.Thread(name='registrationThread',
                                                             target=RtAttenWeb.runRegistration,
                                                             args=(request,))
            RtAttenWeb.registrationThread.setDaemon(True)
            RtAttenWeb.registrationThread.start()
        elif cmd == "stopReg":
            if RtAttenWeb.registrationThread is not None:
                RtAttenWeb.stopReg = True
                RtAttenWeb.registrationThread.join(timeout=1)
                if not RtAttenWeb.registrationThread.is_alive():
                    RtAttenWeb.registrationThread = None
                    RtAttenWeb.stopReg = False
        elif cmd == "uploadImages":
            if RtAttenWeb.uploadImageThread is not None:
                RtAttenWeb.uploadImageThread.join(timeout=1)
                if RtAttenWeb.uploadImageThread.is_alive():
                    RtAttenWeb.webServer.setUserError("Registraion thread already runnning, skipping new request")
                    return
            RtAttenWeb.uploadImageThread = threading.Thread(name='uploadImages',
                                                            target=RtAttenWeb.uploadImages,
                                                            args=(request,))
            RtAttenWeb.uploadImageThread.setDaemon(True)
            RtAttenWeb.uploadImageThread.start()
        else:
            RtAttenWeb.webServer.setUserError("unknown command " + cmd)

    @staticmethod
    def webSubjCallback(client, message):
        if RtAttenWeb.initialized is not True:
            raise StateError('webUserCallback: RtAttenWeb not initialized')
        request = json.loads(message)
        cmd = request['cmd']
        logging.log(DebugLevels.L3, "WEB SUBJ CMD: %s", cmd)
        print('Subject Callback: {}'.format(cmd))

    @staticmethod
    def eventCallback(client, message):
        if RtAttenWeb.initialized is not True:
            raise StateError('webUserCallback: RtAttenWeb not initialized')
        request = json.loads(message)
        cmd = request['cmd']
        logging.log(DebugLevels.L3, "WEB EVENT CMD: %s", cmd)
        if cmd == 'ttlPulse':
            # forward the ttlPulse to the subjectWindow
            cmd = {'cmd': 'ttlPulse'}
            RtAttenWeb.webServer.sendSubjMsgFromThread(json.dumps(cmd))

    @staticmethod
    def webPipeCallback(request):
        if 'cmd' not in request:
            raise StateError('handleFifoRequests: cmd field not in request: {}'.format(request))
        cmd = request['cmd']
        route = request.get('route')
        response = StructDict({'status': 200})
        if route == 'dataserver':
            try:
                response = RtAttenWeb.webServer.sendDataMsgFromThread(request, timeout=10)
                if response is None:
                    raise StateError('handleFifoRequests: Response None from sendDataMessage')
                if 'status' not in response:
                    raise StateError('handleFifoRequests: status field missing from response: {}'.format(response))
                if response['status'] not in (200, 408):
                    if 'error' not in response:
                        raise StateError('handleFifoRequests: error field missing from response: {}'.format(response))
                    RtAttenWeb.webServer.setUserError(response['error'])
                    logging.error('handleFifo status {}: {}'.format(response['status'], response['error']))
            except Exception as err:
                errStr = 'SendDataMessage Exception type {}: error {}:'.format(type(err), str(err))
                response = {'status': 400, 'error': errStr}
                RtAttenWeb.webServer.setUserError(errStr)
                logging.error('handleFifo Excpetion: {}'.format(errStr))
                raise err
        else:
            if cmd == 'webCommonDir':
                response.filename = CommonOutputDir
            elif cmd == 'classificationResult':
                predict = request['value']
                runId = request['runId']
                # predict has {'catsep': val, 'vol': val}
                catsep = predict.get('catsep')
                vol = predict.get('vol')
                # Test for NaN by comparing value to itself, if not equal then it is NaN
                if catsep is not None and catsep == catsep:
                    alpha = 0.5
                    if vol == 'train':
                        # for training set image as 60% face, 40% scene
                        alpha = 0.4
                    else:
                        # calculate the biased alpha value
                        gain = 2.3
                        x_shift = 0.2
                        y_shift = 0.12
                        steepness = 0.9
                        alpha = steepness / (1 + math.exp(-gain*(catsep-x_shift))) + y_shift
                    # Choose random number for which images to use
                    faceRndNum = random.randint(1, RtAttenWeb.numFaceFiles)
                    sceneRndNum = random.randint(1, RtAttenWeb.numSceneFiles)
                    faceFilename = os.path.join(RtAttenWeb.feedbackdir, 'FACE/{}.jpg'.format(faceRndNum))
                    sceneFilename = os.path.join(RtAttenWeb.feedbackdir, 'SCENE/{}.jpg'.format(sceneRndNum))
                    faceImg = Image.open(faceFilename)
                    sceneImg = Image.open(sceneFilename)
                    # Blend the images together using the classification result value
                    # When alpha is closer to 0 then 1st img param (face) will be move visible
                    # and conversely when alpha is closer to 1 then 2nd img param (scene) will be more visible
                    blendImg = Image.blend(faceImg, sceneImg, alpha=alpha)
                    # convert it to jpeg format and get the bytes to send
                    jpgBuf = io.BytesIO()
                    blendImg.save(jpgBuf, format='jpeg')
                    jpgBytes = jpgBuf.getvalue()
                    b64Data = b64encode(jpgBytes)
                    b64StrData = b64Data.decode('utf-8')
                    cmd = {'cmd': 'feedbackImage', 'data': b64StrData}
                    RtAttenWeb.webServer.sendSubjMsgFromThread(json.dumps(cmd))
                    # also update clinician window
                    # change classification value range to 0 to 1 instead of -1 to 1
                    # classVal = (catsep + 1) / 2
                    cmd = {'cmd': 'classificationResult', 'classVal': catsep, 'vol': vol, 'runId': runId}
                    RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(cmd))
        return response

    @staticmethod
    def writeRegConfigFile(regGlobals, scriptPath):
        globalsFilename = os.path.join(scriptPath, 'globals.sh')
        with open(globalsFilename, 'w') as fp:
            fp.write('#!/bin/bash\n')
            for key, val in regGlobals.items():
                if RtAttenWeb.filesremote is True:
                    # prepend directories with commonOutputDir
                    if re.search('folder|dir|path', key, flags=re.IGNORECASE) is not None:
                        val = os.path.normpath(CommonOutputDir + val)
                fp.write(key + '=' + str(val) + '\n')
            fp.write('code_path=' + registrationDir)

    @staticmethod
    def runSession():
        cfg = RtAttenWeb.cfg
        # override confirmation for files already existing if needed
        if (cfg.session.skipConfirmForReprocess is None or
                cfg.session.skipConfirmForReprocess is False):
            logging.warn('Overriding skipConfirmForReprocess to True... skipping confimation')
            cfg.session.skipConfirmForReprocess = True

        # write out config file for use by rtAtten client
        configFileName = os.path.join(confDir, 'cfg_{}_day{}_run{}.toml'.
                                      format(cfg.session.subjectName,
                                             cfg.session.subjectDay,
                                             cfg.session.Runs[0]))
        with open(configFileName, 'w+') as fd:
            toml.dump(cfg, fd)

        if RtAttenWeb.filesremote is True and not cfg.session.getPatternsFromControlRoom:
            # copy the default patterns files to the local run directory
            for runId in cfg.session.Runs:
                runDataDir = getRunDir(cfg.session.dataDir, cfg.session.subjectNum,
                                       cfg.session.subjectDay, runId)
                runDataDir = os.path.normpath(CommonOutputDir + runDataDir)
                if not os.path.exists(runDataDir):
                    os.makedirs(runDataDir)
                patternsSource = os.path.join(patternsDir, 'patternsdesign_'+str(runId)+'*')
                copyFileWildcard(patternsSource, runDataDir)

        # specify -u python option to disable buffering print commands
        cmdStr = 'python -u ClientMain.py -e {}'.format(configFileName)
        # set options for runnings a local rtserver or connecting to remote one
        if RtAttenWeb.rtlocal is True:
            cmdStr += ' -l'
        else:
            (server, port) = RtAttenWeb.rtserver.split(':')
            cmdStr += ' -a {} -p {}'.format(server, port)
        # set option for remote file requests
        if RtAttenWeb.filesremote is True:
            cmdStr += ' -x'
        # Always create a webpipe session even if using local files so we can send
        #  classification results to the subject feedback window
        webpipes = makeFifo()
        cmdStr += ' --webpipe {}'.format(webpipes.fifoname)
        # start thread listening for remote file requests on fifo queue
        fifoThread = threading.Thread(name='fifoThread', target=handleFifoRequests,
                                      args=(webpipes, RtAttenWeb.webPipeCallback))
        fifoThread.setDaemon(True)
        fifoThread.start()
        # print(cmdStr)
        cmd = shlex.split(cmdStr)
        proc = subprocess.Popen(cmd, cwd=rootDir, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
        # send running status to user web page
        response = {'cmd': 'runStatus', 'status': 'running'}
        RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(response))
        # start a separate thread to read the process output
        lineQueue = queue.Queue()
        outputThread = threading.Thread(target=RtAttenWeb.procOutputReader, args=(proc, lineQueue))
        outputThread.setDaemon(True)
        outputThread.start()
        line = 'start'
        while(proc.poll() is None or line != ''):
            # subprocess poll returns None while subprocess is running
            if RtAttenWeb.stopRun is True:
                # signal the process to exit by closing stdin
                proc.stdin.close()
            try:
                line = lineQueue.get(block=True, timeout=1)
            except queue.Empty:
                line = ''
            if line != '':
                RtAttenWeb.webServer.userLog(line)
        # processing complete, set status
        endStatus = 'complete \u2714'
        if RtAttenWeb.stopRun is True:
            endStatus = 'stopped'
        response = {'cmd': 'runStatus', 'status': endStatus}
        RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(response))
        outputThread.join(timeout=1)
        if outputThread.is_alive():
            print("OutputThread failed to exit")
        # make sure fifo thread has exited
        if fifoThread is not None:
            resignalFifoThreadExit(fifoThread, webpipes)
        return

    @staticmethod
    def procOutputReader(proc, lineQueue):
        for bline in iter(proc.stdout.readline, b''):
            line = bline.decode('utf-8')
            # check if line has error in it and print to console
            if re.search('error', line, re.IGNORECASE):
                print(line)
            # send to output queue
            lineQueue.put(line)
            if line == '':
                break

    @staticmethod
    def runRegistration(request, test=None):
        if 'cmd' not in request or request['cmd'] != "runReg":
            raise StateError('runRegistration: incorrect cmd request: {}'.format(request))
        try:
            regConfig = request['regConfig']
            regType = request['regType']
            dayNum = int(regConfig['dayNum'])
        except KeyError as err:
            RtAttenWeb.webServer.setUserError("Registration missing a parameter ('regConfig', 'regType', 'dayNum')")
            return
        # Create the globals.sh file in registration directory
        RtAttenWeb.writeRegConfigFile(regConfig, registrationDir)
        # Start bash command and monitor output
        if test is not None:
            cmd = test
        elif regType == 'skullstrip':
            if dayNum != 1:
                RtAttenWeb.webServer.setUserError("Skullstrip can only be run for day1 data")
                return
            cmd = ['bash', 'skullstrip_t1.sh', '1']
            if 'makenii' in regConfig and regConfig['makenii'] is False:
                cmd = ['bash', 'skullstrip_t1.sh']
        elif regType == 'registration':
            if dayNum == 1:
                cmd = ['bash', 'reg_t1.sh']
            else:
                cmd = ['bash', 'reg_epi_day2.sh', '1', '1']
        elif regType == 'makemask':
            cmd = ['bash', 'run_makemask_nii.sh']
        else:
            RtAttenWeb.webServer.setUserError("unknown registration type: " + regType)
            return

        proc = subprocess.Popen(cmd, cwd=registrationDir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lineQueue = queue.Queue()
        outputThread = threading.Thread(target=RtAttenWeb.procOutputReader, args=(proc, lineQueue))
        outputThread.setDaemon(True)
        outputThread.start()
        outputLineCount = 0
        line = 'start'
        statusInterval = 0.5  # interval (sec) for sending status updates
        statusTime = time.time() - statusInterval
        # subprocess poll returns None while subprocess is running
        while(proc.poll() is None or line != ''):
            currTime = time.time()
            if RtAttenWeb.stopReg is True:
                killPid(proc.pid)
                break
            if currTime >= statusTime + statusInterval:
                # send status
                statusTime = currTime
                # logging.log(logging.INFO, "psutil pid %d", proc.pid)
                procInfo = getProcessInfo(proc.pid, str(cmd))
                response = {'cmd': 'regStatus', 'type': regType, 'status': procInfo}
                RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(response))
            try:
                line = lineQueue.get(block=True, timeout=1)
            except queue.Empty:
                line = ''
            if line != '':
                # send output to web interface
                if test:
                    print(line, end='')
                else:
                    response = {'cmd': 'regLog', 'value': line}
                    RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(response))
                outputLineCount += 1
        outputThread.join(timeout=1)
        if outputThread.is_alive():
            print("OutputThread failed to exit")
        # processing complete, clear status
        endStatus = 'complete \u2714'
        if RtAttenWeb.stopReg is True:
            endStatus = 'stopped'
        response = {'cmd': 'regStatus', 'type': regType, 'status': endStatus}
        RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(response))
        return outputLineCount

    @staticmethod
    def uploadImages(request):
        if 'cmd' not in request or request['cmd'] != "uploadImages":
            raise StateError('uploadImages: incorrect cmd request: {}'.format(request))
        if RtAttenWeb.webServer.wsDataConn is None:
            # A remote fileWatcher hasn't connected yet
            errStr = 'Waiting for fileWatcher to attach, please try again momentarily'
            RtAttenWeb.webServer.setUserError(errStr)
            return
        try:
            scanFolder = request['scanFolder']
            scanNum = int(request['scanNum'])
            numDicoms = int(request['numDicoms'])
            uploadType = request['type']
        except KeyError as err:
            RtAttenWeb.webServer.setUserError("Registration request missing a parameter: {}".format(err))
            return
        fileType = Path(RtAttenWeb.cfg.session.dicomNamePattern).suffix
        dicomsInProgressInterval = numDicoms / 4
        intervalCount = 1
        # send periodic progress reports to front-end
        response = {'cmd': 'uploadProgress', 'type': uploadType, 'progress': 'in-progress'}
        RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(response))
        for i in range(1, numDicoms+1):
            filename = "001_{:06d}_{:06d}{}".format(scanNum, i, fileType)
            fullFilename = os.path.join(scanFolder, filename)
            try:
                cmd = getFileReqStruct(fullFilename, writefile=True)
                response = RtAttenWeb.webServer.sendDataMsgFromThread(cmd)
                if response['status'] != 200:
                    raise RequestError(response['error'])
            except Exception as err:
                RtAttenWeb.webServer.setUserError(
                    "Error uploading file {}: {}".format(fullFilename, str(err)))
                return
            if i > intervalCount * dicomsInProgressInterval:
                val = "{:.0f}%".format(1/4 * intervalCount * 100)  # convert to a percentage
                response = {'cmd': 'uploadProgress', 'type': uploadType, 'progress': val}
                RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(response))
                intervalCount += 1
        response = {'cmd': 'uploadProgress', 'type': uploadType, 'progress': 'complete \u2714'}
        RtAttenWeb.webServer.sendUserMsgFromThread(json.dumps(response))


def getProcessInfo(pid, name):
    try:
        proc = psutil.Process(pid)
        children = proc.children()
        cpu = proc.cpu_times()
        cpuTime = cpu.user + cpu.system + cpu.children_user + cpu.children_system
        statsStr = '#Procs({}), CPU({:.2f}), {}: '.format(len(children)+1, cpuTime, name)
        names = [statsStr]
        for child in children:
            names.append(child.name())
        return names
    except Exception as err:
        logging.log(logging.INFO, "psutil error: %s", err)
        return []


def killPid(pid):
    proc = psutil.Process(pid)
    for childproc in proc.children(recursive=True):
        childproc.kill()
    proc.kill()
