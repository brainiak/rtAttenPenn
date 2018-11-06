'''RtAttenClient - client logic for rtAtten experiment'''
import os
import time
import json
import asyncio
import numpy as np  # type: ignore
import datetime
import logging
import pathlib
from dateutil import parser
from pathlib import Path
import rtfMRI.utils as utils
from rtfMRI.RtfMRIClient import RtfMRIClient, validateRunCfg
from rtfMRI.MsgTypes import MsgEvent
from rtfMRI.StructDict import StructDict, copy_toplevel
from rtfMRI.ReadDicom import readDicomFromFile, applyMask
from rtfMRI.ttlPulse import TTLPulseClient
from rtfMRI.utils import dateStr30, DebugLevels
from rtfMRI.fileWatcher import FileWatcher
from rtfMRI.Errors import InvocationError, ValidationError, StateError
from .PatternsDesign2Config import createRunConfig, getRunIndex, getLocalPatternsFile, getPatternsFileRegex
from .RtAttenModel import getBlkGrpFilename, getModelFilename, getSubjectDayDir


class RtAttenClient(RtfMRIClient):
    def __init__(self):
        super().__init__()
        self.dirs = StructDict()
        self.prevData = None
        self.printFirstFilename = True
        self.ttlPulseClient = TTLPulseClient()
        self.fileWatcher = FileWatcher()
        self.useWeb = False
        self.webInterface = None
        self.stopRun = False

    def __del__(self):
        logging.log(DebugLevels.L1, "## Stop Client")
        if self.ttlPulseClient is not None:
            self.ttlPulseClient.close()
        super().__del__()

    def setWebInterface(self, web):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.webInterface = web
        self.useWeb = True
        self.fileWatcher = None

    def doStopRun(self):
        self.stopRun = True

    def cfgValidation(self, cfg):
        # some model specific validations
        if type(cfg.session.Runs) is not list or type(cfg.session.ScanNums) is not list:
            raise InvocationError("Runs and ScanNums must be a list of integers")

        if type(cfg.session.Runs[0]) is not int:
            # convert to list of ints
            try:
                cfg.session.Runs = [int(s) for s in cfg.session.Runs[0].split(',')]
            except Exception as err:
                raise InvocationError("List of Run integers is malformed")

        if type(cfg.session.ScanNums[0]) is not int:
            # convert to list of ints
            try:
                cfg.session.ScanNums = [int(s) for s in cfg.session.ScanNums[0].split(',')]
            except Exception as err:
                raise InvocationError("List of ScanNum integers is malformed")

    def initSession(self, cfg):
        self.cfgValidation(cfg)

        if cfg.session.sessionId is None or cfg.session.sessionId == '':
            cfg.session.sessionId = dateStr30(time.localtime())

        logging.log(DebugLevels.L1, "## Start Session: %s, subNum%d subDay%d",
                    cfg.session.sessionId, cfg.session.subjectNum, cfg.session.subjectDay)
        logging.log(DebugLevels.L1, "Config: %r", cfg)

        # Set Directories
        subjectDayDir = getSubjectDayDir(cfg.session.subjectNum, cfg.session.subjectDay)
        self.dirs.dataDir = os.path.join(cfg.session.dataDir, subjectDayDir)
        print("Mask and patterns files being read from: {}".format(self.dirs.dataDir))
        self.dirs.serverDataDir = os.path.join(cfg.session.serverDataDir, subjectDayDir)
        if not os.path.exists(self.dirs.serverDataDir):
            os.makedirs(self.dirs.serverDataDir)
        if cfg.session.buildImgPath:
            imgDirDate = datetime.datetime.now()
            dateStr = cfg.session.date.lower()
            if dateStr != 'now' and dateStr != 'today':
                try:
                    imgDirDate = parser.parse(cfg.session.date)
                except ValueError as err:
                    imgDirDate = datetime.datetime.now()
                    resp = input("Unable to parse date string, use today's date for image dir? Y/N [N]: ")
                    if resp.upper() != 'Y':
                        return
            datestr = imgDirDate.strftime("%Y%m%d")
            imgDirName = "{}.{}.{}".format(datestr, cfg.session.subjectName, cfg.session.subjectName)
            self.dirs.imgDir = os.path.join(cfg.session.imgDir, imgDirName)
        else:
            self.dirs.imgDir = cfg.session.imgDir
        if not os.path.exists(self.dirs.imgDir):
            os.makedirs(self.dirs.imgDir)
        print("fMRI files being read from: {}".format(self.dirs.imgDir))
        if self.useWeb:
            assert self.webInterface is not None
            if len(self.webInterface.wsDataConns) == 0:
                # A remote fileWatcher hasn't connected yet
                errStr = 'Waiting for fileWatcher to attach, please try again momentarily'
                self.webInterface.setUserError(errStr)
                raise StateError(errStr)
            self.webInterface.initWatch(self.dirs.imgDir,
                                        cfg.session.watchFilePattern,
                                        cfg.session.minExpectedDicomSize)
        else:
            assert self.fileWatcher is not None
            self.fileWatcher.initFileNotifier(self.dirs.imgDir,
                                              cfg.session.watchFilePattern,
                                              cfg.session.minExpectedDicomSize)

        # Load ROI mask - an array with 1s indicating the voxels of interest
        maskFileName = 'mask_' + str(cfg.session.subjectNum) + '_' + str(cfg.session.subjectDay) + '.mat'
        maskFileName = os.path.join(self.dirs.dataDir, maskFileName)
        if self.useWeb and cfg.session.getMasksPatternsFromCR:
            # get the mask from remote site
            temp = self.webInterface.getFile(maskFileName)
        else:
            # read mask locally
            temp = utils.loadMatFile(maskFileName)
        roi = temp.mask
        assert type(roi) == np.ndarray
        # find indices of non-zero elements in roi in row-major order but sorted by col-major order
        cfg.session.roiInds = utils.find(roi)
        cfg.session.roiDims = roi.shape
        cfg.session.nVoxels = cfg.session.roiInds.size
        print("Using mask {}".format(maskFileName))

        super().initSession(cfg)

    def doRuns(self):
        # Process each run
        for runId in self.cfg.session.Runs:
            self.runRun(runId)
            if self.stopRun:
                return

    def runRun(self, runId, scanNum=-1):
        if self.useWeb and self.cfg.session.getMasksPatternsFromCR:
            fileRegex = getPatternsFileRegex(self.cfg.session, runId, addRunDir=True)
            patterns = self.webInterface.getNewestFile(fileRegex)
        else:
            patterns = getLocalPatternsFile(self.cfg.session, runId)
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

        # Setup output directory and output file
        runDataDir = os.path.join(self.dirs.dataDir, 'run' + str(run.runId))
        if not os.path.exists(runDataDir):
            os.makedirs(runDataDir)
        classOutputDir = os.path.join(runDataDir, 'classoutput')
        if not os.path.exists(classOutputDir):
            os.makedirs(classOutputDir)
        outputFile = open(os.path.join(runDataDir, 'fileprocessing_py.txt'), 'w+')

        # ** Experimental Parameters ** #
        run.seed = time.time()
        if run.runId > 1:
            run.rtfeedback = 1
        else:
            run.rtfeedback = 0

        runCfg = copy_toplevel(run)
        reply = self.sendCmdExpectSuccess(MsgEvent.StartRun, runCfg)
        outputReplyLines(reply.fields.outputlns, outputFile, self.webInterface)

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
            outputReplyLines(reply.fields.outputlns, outputFile, self.webInterface)
            for block in blockGroup.blocks:
                self.id_fields.blockId = block.blockId
                blockCfg = copy_toplevel(block)
                logging.log(DebugLevels.L4, "Blk: %d", block.blockId)
                reply = self.sendCmdExpectSuccess(MsgEvent.StartBlock, blockCfg)
                outputReplyLines(reply.fields.outputlns, outputFile, self.webInterface)
                for TR in block.TRs:
                    self.id_fields.trId = TR.trId
                    fileNum = TR.vol + run.disdaqs // run.TRTime
                    logging.log(DebugLevels.L3, "TR: %d, fileNum %d", TR.trId, fileNum)
                    if self.cfg.session.rtData:
                        # Assuming the output file volumes are still 1's based
                        trVolumeData = self.getNextTRData(run, fileNum)
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
                        outputPredictionFile(reply.fields.predict, classOutputDir)
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
                    outputReplyLines(reply.fields.outputlns, outputFile, self.webInterface)
                    if self.stopRun:
                        return
                del self.id_fields.trId
                reply = self.sendCmdExpectSuccess(MsgEvent.EndBlock, blockCfg)
                outputReplyLines(reply.fields.outputlns, outputFile, self.webInterface)
            del self.id_fields.blockId
            reply = self.sendCmdExpectSuccess(MsgEvent.EndBlockGroup, blockGroupCfg)
            outputReplyLines(reply.fields.outputlns, outputFile, self.webInterface)
            # self.retrieveBlkGrp(self.id_fields.sessionId, self.id_fields.runId, self.id_fields.blkGrpId)
        del self.id_fields.blkGrpId
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
        outputReplyLines(outlns, outputFile, self.webInterface)
        processingStartTime = time.time()
        reply = self.sendCmdExpectSuccess(MsgEvent.TrainModel, trainCfg)
        processingEndTime = time.time()
        # log the model generation time
        logStr = "Model:{} training time {:.3f}s\n".format(runId, processingEndTime - processingStartTime)
        logging.log(DebugLevels.L3, logStr)
        outputReplyLines(reply.fields.outputlns, outputFile, self.webInterface)
        reply = self.sendCmdExpectSuccess(MsgEvent.EndRun, runCfg)
        outputReplyLines(reply.fields.outputlns, outputFile, self.webInterface)
        if self.cfg.session.retrieveServerFiles:
            self.retrieveRunFiles(runId)
        del self.id_fields.runId

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
        print("Retrieving data for {}... ".format(filename), end='')
        fileInfo = StructDict()
        fileInfo.subjectNum = self.id_fields.subjectNum
        fileInfo.subjectDay = self.id_fields.subjectDay
        fileInfo.filename = filename
        stime = time.time()
        reply = self.sendCmdExpectSuccess(MsgEvent.RetrieveData, fileInfo)
        print("took {:.2f} secs".format(time.time() - stime))
        clientFile = os.path.join(self.dirs.dataDir, filename)
        writeFile(clientFile, reply.data)
        serverFile = os.path.join(self.dirs.serverDataDir, filename)
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
        if self.useWeb:
            assert self.webInterface is not None
            data = self.webInterface.watchFile(specificFileName)
        else:
            self.fileWatcher.waitForFile(specificFileName)
            data = self.loadImageData(specificFileName)
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
            assert fileExtension == '.dcm'
            data = readDicomFromFile(filename)
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
        filePattern = os.path.join(self.dirs.serverDataDir,
                                   "*" + self.id_fields.sessionId + "*.mat")
        fileInfo = StructDict()
        fileInfo.filePattern = filePattern
        reply = self.sendCmdExpectSuccess(MsgEvent.DeleteData, fileInfo)
        outputReplyLines(reply.fields.outputlns, None, self.webInterface)

    def ping(self):
        processingStartTime = time.time()
        self.sendCmdExpectSuccess(MsgEvent.Ping, None)
        processingEndTime = time.time()
        print("RTT: {:.2f}ms".format(processingEndTime-processingStartTime))


def outputReplyLines(lines, filehandle, web):
    if lines is not None:
        for line in lines:
            print(line)
            if filehandle is not None:
                filehandle.write(line + '\n')
            if web is not None:
                cmd = {'cmd': 'log', 'value': line}
                web.sendUserMessage(json.dumps(cmd))


def outputPredictionFile(predict, classOutputDir):
    if predict is None or predict.vol is None:
        return
    filename = os.path.join(classOutputDir, 'vol_' + str(predict.vol) + '_py.txt')
    with open(filename, 'w+') as volFile:
        volFile.write(str(predict.catsep))


def writeFile(filename, data):
    with open(filename, 'wb') as fh:
        bytesWritten = fh.write(data)
        if bytesWritten != len(data):
            raise InterruptedError("Write file %s wrote %d of %d bytes" % (filename, bytesWritten, len(data)))
