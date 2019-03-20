'''RtAttenClient - client logic for rtAtten experiment'''
import os
import re
import time
import datetime
import logging
import numpy as np  # type: ignore
from dateutil import parser
from pathlib import Path
import rtfMRI.utils as utils
import webInterface.WebClientUtils as wcutils
from rtfMRI.RtfMRIClient import RtfMRIClient, validateRunCfg
from rtfMRI.MsgTypes import MsgEvent
from rtfMRI.StructDict import StructDict, copy_toplevel
from rtfMRI.ReadDicom import readDicomFromFile, applyMask, parseDicomVolume
from rtfMRI.ttlPulse import TTLPulseClient
from rtfMRI.utils import dateStr30, DebugLevels, writeFile
from rtfMRI.fileWatcher import FileWatcher
from rtfMRI.Errors import InvocationError, ValidationError, StateError, RequestError, RTError
from .PatternsDesign2Config import createRunConfig, getRunIndex, getLocalPatternsFile
from .PatternsDesign2Config import getPatternsFileRegex
from .RtAttenModel import getBlkGrpFilename, getModelFilename, getSubjectDataDir

'''Note: print() command buffers multiple lines before outputting by default.
To change print() command to unbuffered invoke python with -u option. Or use alias
import functools; print = functools.partial(print, flush=True)
'''


class RtAttenClient(RtfMRIClient):
    def __init__(self):
        super().__init__()
        self.dirs = StructDict()
        self.prevData = None
        self.printFirstFilename = True
        self.ttlPulseClient = TTLPulseClient()
        self.fileWatcher = FileWatcher()
        self.webpipes = None
        self.webCommonDir = None
        self.webPatternsDir = None
        self.webUseRemoteFiles = False

    def __del__(self):
        # logging.log(DebugLevels.L1, "## Stop Client")
        if self.ttlPulseClient is not None:
            self.ttlPulseClient.close()
        super().__del__()

    def setWeb(self, webpipes, useRemoteFiles):
        self.webpipes = webpipes
        self.webUseRemoteFiles = useRemoteFiles
        if useRemoteFiles:
            self.fileWatcher = None

    def cfgValidation(self, cfg):
        # some model specific validations
        # Convert Runs to a list of integers if needed
        if type(cfg.session.Runs) is str:
            cfg.session.Runs = [int(s) for s in cfg.session.Runs.split(',')]
        elif type(cfg.session.Runs) is list:
            if len(cfg.session.Runs) == 0:
                raise InvocationError("List of Run integers is empty")
            elif type(cfg.session.Runs[0]) is str:
                # convert to list of ints
                if len(cfg.session.Runs) == 1:
                    try:
                        cfg.session.Runs = [int(s) for s in cfg.session.Runs[0].split(',')]
                    except Exception as err:
                        raise InvocationError("List of Run integers is malformed")
                else:
                    cfg.session.Runs = [int(s) for s in cfg.session.Runs]
            elif type(cfg.session.Runs[0]) is not int:
                raise InvocationError("List of Runs must be integers or strings")
        else:
            raise InvocationError("Runs must be a list of integers or string of integers")

        # Convert ScanNums to a list of integers if needed
        if type(cfg.session.ScanNums) is str:
            cfg.session.ScanNums = [int(s) for s in cfg.session.ScanNums.split(',')]
        elif type(cfg.session.ScanNums) is list:
            if len(cfg.session.ScanNums) == 0:
                raise InvocationError("List of Run integers is empty")
            elif type(cfg.session.ScanNums[0]) is str:
                # convert to list of ints
                if len(cfg.session.ScanNums) == 1:
                    try:
                        cfg.session.ScanNums = [int(s) for s in cfg.session.ScanNums[0].split(',')]
                    except Exception as err:
                        raise InvocationError("List of Run integers is malformed")
                else:
                    cfg.session.ScanNums = [int(s) for s in cfg.session.ScanNums]
            elif type(cfg.session.ScanNums[0]) is not int:
                raise InvocationError("List of ScanNums must be integers or strings")
        else:
            raise InvocationError("ScanNums must be a list of integers or string of integers")
        return True

    def initSession(self, cfg):
        self.cfgValidation(cfg)
        if cfg.session.sessionId in (None, '') or cfg.session.useSessionTimestamp is True:
            cfg.session.useSessionTimestamp = True
            cfg.session.sessionId = dateStr30(time.localtime())
        else:
            cfg.session.useSessionTimestamp = False

        logging.log(DebugLevels.L1, "## Start Session: %s, subNum%d subDay%d",
                    cfg.session.sessionId, cfg.session.subjectNum, cfg.session.subjectDay)
        logging.log(DebugLevels.L1, "Config: %r", cfg)

        # Set Directories
        self.dirs.dataDir = getSubjectDataDir(cfg.session.dataDir, cfg.session.subjectNum, cfg.session.subjectDay)
        if self.webUseRemoteFiles:
            # Remote fileWatcher dataDir will be the same, but locally we want
            # the data directory to be a subset of a common output directory.
            self.dirs.remoteDataDir = self.dirs.dataDir
            cmd = {'cmd': 'webCommonDir'}
            retVals = wcutils.clientWebpipeCmd(self.webpipes, cmd)
            self.webCommonDir = retVals.filename
            self.dirs.dataDir = os.path.normpath(self.webCommonDir + self.dirs.dataDir)
        self.dirs.serverDataDir = getSubjectDataDir(cfg.session.serverDataDir, cfg.session.subjectNum, cfg.session.subjectDay)
        if os.path.abspath(self.dirs.serverDataDir):
            # strip the leading separator to make it a relative path
            self.dirs.serverDataDir = self.dirs.serverDataDir.lstrip(os.sep)
        if not os.path.exists(self.dirs.serverDataDir):
            os.makedirs(self.dirs.serverDataDir)
        if cfg.session.buildImgPath:
            imgDirDate = datetime.datetime.now()
            dateStr = cfg.session.date.lower()
            if dateStr != 'now' and dateStr != 'today':
                try:
                    imgDirDate = parser.parse(cfg.session.date)
                except ValueError as err:
                    raise RequestError('Unable to parse date string {} {}'.format(cfg.session.date, err))
            datestr = imgDirDate.strftime("%Y%m%d")
            imgDirName = "{}.{}.{}".format(datestr, cfg.session.subjectName, cfg.session.subjectName)
            self.dirs.imgDir = os.path.join(cfg.session.imgDir, imgDirName)
        else:
            self.dirs.imgDir = cfg.session.imgDir
        print("fMRI files being read from: {}".format(self.dirs.imgDir))
        if self.webUseRemoteFiles:
            # send initWatch via webpipe
            initWatchCmd = wcutils.initWatchReqStruct(self.dirs.imgDir,
                                                      cfg.session.watchFilePattern,
                                                      cfg.session.minExpectedDicomSize,
                                                      cfg.session.demoStep)
            wcutils.clientWebpipeCmd(self.webpipes, initWatchCmd)
        else:
            if not os.path.exists(self.dirs.imgDir):
                os.makedirs(self.dirs.imgDir)
            if self.fileWatcher is None:
                raise StateError('initSession: fileWatcher is None')
            self.fileWatcher.initFileNotifier(self.dirs.imgDir,
                                              cfg.session.watchFilePattern,
                                              cfg.session.minExpectedDicomSize,
                                              cfg.session.demoStep)
        # Load ROI mask - an array with 1s indicating the voxels of interest
        maskData = None
        maskFileName = 'mask_' + str(cfg.session.subjectNum) + '_' + str(cfg.session.subjectDay) + '.mat'
        if self.webUseRemoteFiles and cfg.session.getMasksFromControlRoom:
            # get the mask from remote site
            maskFileName = os.path.join(self.dirs.remoteDataDir, maskFileName)
            logging.info("Getting Remote Mask file: %s", maskFileName)
            getFileCmd = wcutils.getFileReqStruct(maskFileName)
            retVals = wcutils.clientWebpipeCmd(self.webpipes, getFileCmd)
            maskData = retVals.data
            print("Using remote mask {}".format(retVals.filename))
        else:
            # read mask locally
            maskFileName = os.path.join(self.dirs.dataDir, maskFileName)
            logging.info("Getting Local Mask file: %s", maskFileName)
            maskData = utils.loadMatFile(maskFileName)
            print("Using mask {}".format(maskFileName))
        roi = maskData.mask
        if type(roi) != np.ndarray:
            raise StateError('initSession: ROI type {} is not ndarray'.format(type(roi)))
        # find indices of non-zero elements in roi in row-major order but sorted by col-major order
        cfg.session.roiInds = utils.find(roi)
        cfg.session.roiDims = roi.shape
        cfg.session.nVoxels = cfg.session.roiInds.size
        super().initSession(cfg)

    def doRuns(self):
        # Process each run
        for runId in self.cfg.session.Runs:
            self.runRun(runId)

    def runRun(self, runId, scanNum=-1):
        # Setup output directory and output file
        runDataDir = os.path.join(self.dirs.dataDir, 'run' + str(runId))
        if not os.path.exists(runDataDir):
            os.makedirs(runDataDir)
        outputInfo = StructDict()
        outputInfo.runId = runId
        outputInfo.classOutputDir = os.path.join(runDataDir, 'classoutput')
        if not os.path.exists(outputInfo.classOutputDir):
            os.makedirs(outputInfo.classOutputDir)
        outputInfo.logFilename = os.path.join(runDataDir, 'fileprocessing_py.txt')
        outputInfo.logFileHandle = open(outputInfo.logFilename, 'w+')
        if self.webpipes is not None:
            outputInfo.webpipes = self.webpipes
        if self.webUseRemoteFiles:
            outputInfo.webUseRemoteFiles = True
            remoteRunDataDir = os.path.join(self.dirs.remoteDataDir, 'run' + str(runId))
            outputInfo.remoteClassOutputDir = os.path.join(remoteRunDataDir, 'classoutput')
            outputInfo.remoteLogFilename = os.path.join(remoteRunDataDir, 'fileprocessing_py.txt')
        # Get patterns design file for this run
        patterns = None
        if self.webUseRemoteFiles and self.cfg.session.getPatternsFromControlRoom:
            fileRegex = getPatternsFileRegex(self.cfg.session, self.dirs.remoteDataDir, runId, addRunDir=True)
            getNewestFileCmd = wcutils.getNewestFileReqStruct(fileRegex)
            retVals = wcutils.clientWebpipeCmd(self.webpipes, getNewestFileCmd)
            if retVals.statusCode != 200:
                raise RequestError('runRun: statusCode not 200: {}'.format(retVals.statusCode))
            patterns = retVals.data
            logging.info("Using Remote Patterns file: %s", retVals.filename)
            print("Using remote patterns {}".format(retVals.filename))
        else:
            patterns, filename = getLocalPatternsFile(self.cfg.session, self.dirs.dataDir, runId)
            print("Using patterns {}".format(filename))
        run = createRunConfig(self.cfg.session, patterns, runId, scanNum)
        validateRunCfg(run)
        self.id_fields.runId = run.runId
        logging.log(DebugLevels.L4, "Run: %d, scanNum %d", runId, run.scanNum)
        if self.cfg.session.rtData:
            # Check if images already exist and warn and ask to continue
            firstFileName = self.getDicomFileName(run.scanNum, 1)
            if os.path.exists(firstFileName):
                logging.log(DebugLevels.L3, "Dicoms already exist")
                skipCheck = self.cfg.session.skipConfirmForReprocess
                if skipCheck is None or skipCheck is False:
                    resp = input('Files with this scan number already exist. Do you want to continue? Y/N [N]: ')
                    if resp.upper() != 'Y':
                        outputInfo.logFileHandle.close()
                        return
            else:
                logging.log(DebugLevels.L3, "Dicoms - waiting for")
        elif self.cfg.session.replayMatFileMode or self.cfg.session.validate:
            idx = getRunIndex(self.cfg.session, runId)
            if idx >= 0 and len(self.cfg.session.validationModels) > idx:
                run.validationModel = os.path.join(self.dirs.dataDir, self.cfg.session.validationModels[idx])
            else:
                raise ValidationError("Insufficient config runs or validationModels specified: "
                                      "runId {}, validationModel idx {}", runId, idx)
            if idx >= 0 and len(self.cfg.session.validationData) > idx:
                run.validationDataFile = os.path.join(self.dirs.dataDir, self.cfg.session.validationData[idx])
            else:
                raise ValidationError("Insufficient config runs or validationDataFiles specified: "
                                      "runId {}, validationData idx {}", runId, idx)

        # ** Experimental Parameters ** #
        run.seed = time.time()
        if run.runId > 1:
            run.rtfeedback = 1
        else:
            run.rtfeedback = 0

        runCfg = copy_toplevel(run)
        reply = self.sendCmdExpectSuccess(MsgEvent.StartRun, runCfg)
        outputReplyLines(reply.fields.outputlns, outputInfo)

        if self.cfg.session.replayMatFileMode and not self.cfg.session.rtData:
            # load previous patterns data for this run
            p = utils.loadMatFile(run.validationDataFile)
            run.replay_data = p.patterns.raw

        # Begin BlockGroups (phases)
        for blockGroup in run.blockGroups:
            self.id_fields.blkGrpId = blockGroup.blkGrpId
            blockGroupCfg = copy_toplevel(blockGroup)
            logging.log(DebugLevels.L4, "BlkGrp: %d", blockGroup.blkGrpId)
            reply = self.sendCmdExpectSuccess(MsgEvent.StartBlockGroup, blockGroupCfg)
            outputReplyLines(reply.fields.outputlns, outputInfo)
            for block in blockGroup.blocks:
                self.id_fields.blockId = block.blockId
                blockCfg = copy_toplevel(block)
                logging.log(DebugLevels.L4, "Blk: %d", block.blockId)
                reply = self.sendCmdExpectSuccess(MsgEvent.StartBlock, blockCfg)
                outputReplyLines(reply.fields.outputlns, outputInfo)
                for TR in block.TRs:
                    self.id_fields.trId = TR.trId
                    fileNum = TR.vol + run.disdaqs // run.TRTime
                    logging.log(DebugLevels.L3, "TR: %d, fileNum %d", TR.trId, fileNum)
                    if self.cfg.session.rtData:
                        # Assuming the output file volumes are still 1's based
                        trVolumeData = self.getNextTRData(run, fileNum)
                        if trVolumeData is None:
                            if TR.trId == 0:
                                errStr = "First TR {} of run {} missing data, aborting...".format(TR.trId, runId)
                                raise RTError(errStr)
                            logging.warn("TR {} missing data, sending empty data".format(TR.trId))
                            TR.data = np.full((self.cfg.session.nVoxels), np.nan)
                            reply = self.sendCmdExpectSuccess(MsgEvent.TRData, TR)
                            continue
                        TR.data = applyMask(trVolumeData, self.cfg.session.roiInds)
                    else:
                        # TR.vol is 1's based to match matlab, so we want vol-1 for zero based indexing
                        TR.data = run.replay_data[TR.vol-1]
                    processingStartTime = time.time()
                    imageAcquisitionTime = 0.0
                    pulseBroadcastTime = 0.0
                    trStartTime = 0.0
                    gotTTLTime = False
                    if (self.cfg.session.enforceDeadlines is not None and
                            self.cfg.session.enforceDeadlines is True):
                        # capture TTL pulse from scanner to calculate next deadline
                        trStartTime = self.ttlPulseClient.getTimestamp()
                        if trStartTime == 0 or imageAcquisitionTime > run.TRTime:
                            # Either no TTL Pulse time signal or stale time signal
                            #   Approximate trStart as current time minus 500ms
                            #   because scan reconstruction takes about 500ms
                            gotTTLTime = False
                            trStartTime = time.time() - 0.5
                            # logging.info("Approx TR deadline: {}".format(trStartTime))
                        else:
                            gotTTLTime = True
                            imageAcquisitionTime = time.time() - trStartTime
                            pulseBroadcastTime = trStartTime - self.ttlPulseClient.getServerTimestamp()
                            # logging.info("TTL TR deadline: {}".format(trStartTime))
                        # Deadline is TR_Start_Time + time between TRs +
                        #  clockSkew adjustment - 1/2 Max Net Round_Trip_Time -
                        #  Min RTT because clock skew calculation can be off
                        #  by the RTT used for calculation which is Min RTT.
                        TR.deadline = (trStartTime + self.cfg.clockSkew + run.TRTime -
                                       (0.5 * self.cfg.maxRTT) - self.cfg.minRTT)
                    reply = self.sendCmdExpectSuccess(MsgEvent.TRData, TR)
                    processingEndTime = time.time()
                    missedDeadline = False
                    if (reply.fields.missedDeadline is not None and
                            reply.fields.missedDeadline is True):
                        # TODO - store reply.fields.threadId in order to get completed reply later
                        # TODO - add a message type that retrieves previous thread results
                        missedDeadline = True
                    else:
                        # classification result
                        outputPredictionFile(reply.fields.predict, outputInfo)

                    # log the TR processing time
                    serverProcessTime = processingEndTime - processingStartTime
                    elapsedTRTime = 0.0
                    if gotTTLTime is True:
                        elapsedTRTime = time.time() - trStartTime
                    logStr = "TR:{}:{}:{:03}, fileNum {}, server_process_time {:.3f}s, " \
                             "elapsedTR_time {:.3f}s, image_time {:.3f}s, " \
                             "pulse_time {:.3f}s, gotTTLPulse {}, missed_deadline {}, " \
                             "dicom_arrival {:.5f}" \
                             .format(runId, block.blockId, TR.trId, fileNum,
                                     serverProcessTime, elapsedTRTime,
                                     imageAcquisitionTime, pulseBroadcastTime,
                                     gotTTLTime, missedDeadline, processingStartTime)
                    logging.log(DebugLevels.L3, logStr)
                    outputReplyLines(reply.fields.outputlns, outputInfo)
                del self.id_fields.trId
                reply = self.sendCmdExpectSuccess(MsgEvent.EndBlock, blockCfg)
                outputReplyLines(reply.fields.outputlns, outputInfo)
            del self.id_fields.blockId
            reply = self.sendCmdExpectSuccess(MsgEvent.EndBlockGroup, blockGroupCfg)
            outputReplyLines(reply.fields.outputlns, outputInfo)
            # self.retrieveBlkGrp(self.id_fields.sessionId, self.id_fields.runId, self.id_fields.blkGrpId)
        del self.id_fields.blkGrpId
        # End Run
        if self.webpipes is not None:
            # send instructions to subject window display
            cmd = {'cmd': 'subjectInstructions', 'value': 'Waiting for next run to start...'}
            wcutils.clientWebpipeCmd(self.webpipes, cmd)
        # Train the model for this Run
        trainCfg = StructDict()
        if run.runId == 1:
            trainCfg.blkGrpRefs = [{'run': 1, 'phase': 1}, {'run': 1, 'phase': 2}]
        elif run.runId == 2:
            trainCfg.blkGrpRefs = [{'run': 1, 'phase': 2}, {'run': 2, 'phase': 1}]
        else:
            trainCfg.blkGrpRefs = [{'run': run.runId-1, 'phase': 1}, {'run': run.runId, 'phase': 1}]
        outlns = []
        outlns.append('*********************************************')
        outlns.append("Train Model {} {}".format(trainCfg.blkGrpRefs[0], trainCfg.blkGrpRefs[1]))
        outputReplyLines(outlns, outputInfo)
        processingStartTime = time.time()
        reply = self.sendCmdExpectSuccess(MsgEvent.TrainModel, trainCfg)
        processingEndTime = time.time()
        # log the model generation time
        logStr = "Model:{} training time {:.3f}s\n".format(runId, processingEndTime - processingStartTime)
        logging.log(DebugLevels.L3, logStr)
        outputReplyLines(reply.fields.outputlns, outputInfo)
        reply = self.sendCmdExpectSuccess(MsgEvent.EndRun, runCfg)
        outputReplyLines(reply.fields.outputlns, outputInfo)
        if self.cfg.session.retrieveServerFiles:
            self.retrieveRunFiles(runId)
        del self.id_fields.runId
        outputInfo.logFileHandle.close()

    def retrieveRunFiles(self, runId):
        if self.messaging.addr == 'localhost':
            print("Skipping file retrieval from localhost")
            return
        blkGrp1_filename = getBlkGrpFilename(self.id_fields.sessionId, runId, 1)
        self.retrieveFile(blkGrp1_filename)
        blkGrp2_filename = getBlkGrpFilename(self.id_fields.sessionId, runId, 2)
        self.retrieveFile(blkGrp2_filename)
        model_filename = getModelFilename(self.id_fields.sessionId, runId)
        self.retrieveFile(model_filename)

    def retrieveFile(self, filename):
        fileInfo = StructDict()
        fileInfo.subjectNum = self.id_fields.subjectNum
        fileInfo.subjectDay = self.id_fields.subjectDay
        fileInfo.filename = filename
        if self.cfg.session.useSessionTimestamp is True:
            fileInfo.findNewestPattern = re.sub(r'T\d{6}', 'T*', filename)
            print("Retrieving newest file for {}... ".format(fileInfo.findNewestPattern), end='')
        else:
            print("Retrieving file {}... ".format(filename), end='')
        stime = time.time()
        reply = self.sendCmdExpectSuccess(MsgEvent.RetrieveData, fileInfo)
        retFilename = reply.fields.filename
        print("took {:.2f} secs".format(time.time() - stime))
        clientFile = os.path.join(self.dirs.dataDir, retFilename)
        writeFile(clientFile, reply.data)
        serverFile = os.path.join(self.dirs.serverDataDir, retFilename)
        if not os.path.exists(serverFile):
            try:
                os.symlink(clientFile, serverFile)
            except OSError:
                logging.error("Unable to link file %s", serverFile)

    def getNextTRData(self, run, fileNum):
        specificFileName = self.getDicomFileName(run.scanNum, fileNum)
        data = None
        if self.printFirstFilename:
            print("Loading first file: {}".format(specificFileName))
            self.printFirstFilename = False
        if self.webUseRemoteFiles:
            statusCode = 408  # loop while filewatch timeout 408 occurs
            while statusCode == 408:
                watchCmd = wcutils.watchFileReqStruct(specificFileName)
                retVals = wcutils.clientWebpipeCmd(self.webpipes, watchCmd)
                statusCode = retVals.statusCode
                data = retVals.data
            if statusCode != 200:
                raise StateError('getNextTRData: statusCode not 200: {}'.format(statusCode))
        else:
            self.fileWatcher.waitForFile(specificFileName)
            # Load the file, retry if necessary taking up to 500ms
            retries = 0
            while retries < 5:
                retries += 1
                try:
                    data = self.loadImageData(specificFileName)
                    # successful
                    break
                except Exception as err:
                    logging.warn("LoadImage error, retry in 100 ms: {} ".format(err))
                    time.sleep(0.1)
            if data is None:
                return None
        fileExtension = Path(specificFileName).suffix
        if fileExtension == '.mat':
            trVol = data.vol
        elif fileExtension == '.dcm':
            trVol = parseDicomVolume(data, self.cfg.session.sliceDim)
        else:
            raise ValidationError('Only filenames of type .mat or .dcm supported')
        return trVol

    def loadImageData(self, filename):
        fileExtension = Path(filename).suffix
        if fileExtension == '.mat':
            data = utils.loadMatFile(filename)
        else:
            # Dicom file:
            if fileExtension != '.dcm':
                raise StateError('loadImageData: fileExtension not .dcm: {}'.format(fileExtension))
            data = readDicomFromFile(filename)
            # Check that pixeldata can be read, will throw exception if not
            _ = data.pixel_array
        return data

    def getDicomFileName(self, scanNum, fileNum):
        if scanNum < 0:
            raise ValidationError("ScanNumber not supplied of invalid {}".format(scanNum))
        scanNumStr = str(scanNum).zfill(2)
        fileNumStr = str(fileNum).zfill(3)
        if self.cfg.session.dicomNamePattern is None:
            raise InvocationError("Missing config settings dicomNamePattern")
        fileName = self.cfg.session.dicomNamePattern.format(scanNumStr, fileNumStr)
        fullFileName = os.path.join(self.dirs.imgDir, fileName)
        return fullFileName

    def deleteSessionData(self):
        sessionIdPattern = re.sub('T.*', 'T*', self.id_fields.sessionId)
        filePattern = os.path.join(self.dirs.serverDataDir,
                                   "*" + sessionIdPattern + "*.mat")
        fileInfo = StructDict()
        fileInfo.filePattern = filePattern
        reply = self.sendCmdExpectSuccess(MsgEvent.DeleteData, fileInfo)
        outputReplyLines(reply.fields.outputlns, None)

    def ping(self):
        processingStartTime = time.time()
        self.sendCmdExpectSuccess(MsgEvent.Ping, None)
        processingEndTime = time.time()
        print("RTT: {:.2f}ms".format(processingEndTime-processingStartTime))


def outputReplyLines(lines, outputInfo):
    if lines is not None:
        concatedLines = ''
        for line in lines:
            print(line)
            concatedLines += line + '\n'
        if outputInfo is not None and outputInfo.logFileHandle is not None:
            outputInfo.logFileHandle.write(concatedLines)


def outputPredictionFile(predict, outputInfo):
    if outputInfo.webpipes is not None:
        # send classification result to RtAttenWeb for subject window display
        vals = predict
        if predict is None or predict.catsep is None:
            vals = {'catsep': 0.0, 'vol': 'train'}
        cmd = {'cmd': 'classificationResult', 'value': vals, 'runId': outputInfo.runId}
        wcutils.clientWebpipeCmd(outputInfo.webpipes, cmd)
    if predict is None or predict.vol is None:
        return
    if outputInfo.webUseRemoteFiles:
        # Send classification result to data server
        remoteFilename = os.path.join(outputInfo.remoteClassOutputDir, 'vol_' + str(predict.vol) + '_py.txt')
        putFileCmd = wcutils.putTextFileReqStruct(remoteFilename, str(predict.catsep))
        wcutils.clientWebpipeCmd(outputInfo.webpipes, putFileCmd)
    else:
        filename = os.path.join(outputInfo.classOutputDir, 'vol_' + str(predict.vol) + '_py.txt')
        with open(filename, 'w+') as volFile:
            volFile.write(str(predict.catsep))
