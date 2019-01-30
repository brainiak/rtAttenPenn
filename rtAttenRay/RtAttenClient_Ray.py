
import os
import time
import numpy as np  # type: ignore
import datetime
import click
import clickutil
from queue import Queue
from dateutil import parser
from watchdog.observers import Observer  # type: ignore
from watchdog.events import PatternMatchingEventHandler  # type: ignore
import sys
# fix up the module search path to be the rtAtten project path
scriptPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(scriptPath, "../")
sys.path.append(rootPath)
import rtfMRI.utils as utils
import rtfMRI.ReadDicom as ReadDicom
from rtfMRI.StructDict import StructDict
from rtfMRI.RtfMRIClient import loadConfigFile, validateSessionCfg, validateRunCfg
from rtfMRI.Errors import InvocationError, ValidationError
import rtAtten.PatternsDesign2Config as Pats
from rtAttenRay.RtAttenModel_Ray import RtAttenModel_Ray, getSubjectDataDir, getBlkGrpFilename, getModelFilename
import ray


def ClientMain(config: str, rayremote: str):
    ray.init(redis_address=rayremote)
    RtAttenModel_Remote = ray.remote(RtAttenModel_Ray)

    rtatten = RtAttenModel_Remote.remote()
    client = LocalClient(rtatten)
    cfg = loadConfigFile(config)
    client.start_session(cfg)
    subjectDataDir = getSubjectDataDir(cfg.session.dataDir, cfg.session.subjectNum, cfg.session.subjectDay)
    for runId in cfg.session.Runs:
        patterns, _ = Pats.getLocalPatternsFile(cfg.session, subjectDataDir, runId)
        run = Pats.createRunConfig(cfg.session, patterns, runId)
        validateRunCfg(run)
        client.do_run(run)
    client.end_session()


class LocalClient():
    def __init__(self, rtatten):
        super().__init__()
        self.cfg = None
        self.dirs = StructDict()
        self.prevData = None
        self.observer = None
        self.fileNotifyHandler = None
        self.fileNotifyQ = Queue()  # type: None
        self.printFirstFilename = True
        self.logtimeFile = None
        self.id_fields = StructDict()
        self.rtatten = rtatten

    def start_session(self, cfg):
        self.cfg = cfg
        validateSessionCfg(cfg)
        if cfg.session.sessionId is None or cfg.session.sessionId == '':
            cfg.session.sessionId = utils.dateStr30(time.localtime())

        self.modelName = cfg.experiment.model
        self.id_fields.experimentId = cfg.experiment.experimentId
        self.id_fields.sessionId = cfg.session.sessionId
        self.id_fields.subjectNum = cfg.session.subjectNum
        self.id_fields.subjectDay = cfg.session.subjectDay

        # Set Directories
        self.dirs.dataDir = getSubjectDataDir(cfg.session.dataDir, cfg.session.subjectNum, cfg.session.subjectDay)
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
        self.initFileNotifier(self.dirs.imgDir, cfg.session.watchFilePattern)

        # Open file for logging processing time measurements
        logtimeFilename = os.path.join(self.dirs.dataDir, "logtime.txt")
        self.logtimeFile = open(logtimeFilename, "a", 1)  # linebuffered=1
        initLogStr = "## Start Session: date:{} subNum:{} subDay:{} ##\n".format(
                     datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                     cfg.session.subjectNum,
                     cfg.session.subjectDay)
        self.logtimeFile.write(initLogStr)

        # Load ROI mask - an array with 1s indicating the voxels of interest
        maskFileName = 'mask_' + str(cfg.session.subjectNum) + '_' + str(cfg.session.subjectDay) + '.mat'
        maskFileName = os.path.join(self.dirs.dataDir, maskFileName)
        temp = utils.loadMatFile(maskFileName)
        roi = temp.mask
        assert type(roi) == np.ndarray
        # find indices of non-zero elements in roi in row-major order but sorted by col-major order
        cfg.session.roiInds = utils.find(roi)
        cfg.session.roiDims = roi.shape
        cfg.session.nVoxels = cfg.session.roiInds.size
        print("Using mask {}".format(maskFileName))
        replyId = self.rtatten.StartSession.remote(cfg.session)
        reply = ray.get(replyId)
        assert reply.success is True

    def end_session(self):
        pass

    def do_run(self, run):
        # Setup output directory and output file
        runDataDir = os.path.join(self.dirs.dataDir, 'run' + str(run.runId))
        if not os.path.exists(runDataDir):
            os.makedirs(runDataDir)
        classOutputDir = os.path.join(runDataDir, 'classoutput')
        if not os.path.exists(classOutputDir):
            os.makedirs(classOutputDir)
        outputFile = open(os.path.join(runDataDir, 'fileprocessing_py.txt'), 'w+')

        replyId = self.rtatten.StartRun.remote(run)
        reply = ray.get(replyId)
        assert reply.success is True
        outputReplyLines(reply.outputlns, outputFile)

        # ** Experimental Parameters ** #
        run.seed = time.time()
        if run.runId > 1:
            run.rtfeedback = 1
        else:
            run.rtfeedback = 0

        for blockGroup in run.blockGroups:
            replyId = self.rtatten.StartBlockGroup.remote(blockGroup)
            reply = ray.get(replyId)
            assert reply.success is True
            outputReplyLines(reply.outputlns, outputFile)
            for block in blockGroup.blocks:
                replyId = self.rtatten.StartBlock.remote(block)
                reply = ray.get(replyId)
                assert reply.success is True
                outputReplyLines(reply.outputlns, outputFile)
                for TR in block.TRs:
                    # Assuming the output file volumes are still 1's based
                    fileNum = TR.vol + run.disdaqs // run.TRTime
                    trVolumeData = self.getNextTRData(run, fileNum)
                    TR.data = ReadDicom.applyMask(trVolumeData, self.cfg.session.roiInds)
                    replyId = self.rtatten.TRData.remote(TR)
                    reply = ray.get(replyId)
                    assert reply.success is True
                    outputReplyLines(reply.outputlns, outputFile)
                    outputPredictionFile(reply.predict, classOutputDir)
                replyId = self.rtatten.EndBlock.remote()
                reply = ray.get(replyId)
                assert reply.success is True
                outputReplyLines(reply.outputlns, outputFile)
            replyId = self.rtatten.EndBlockGroup.remote()
            reply = ray.get(replyId)
            assert reply.success is True
            outputReplyLines(reply.outputlns, outputFile)
        trainCfg = makeTrainCfg(run)
        replyId = self.rtatten.TrainModel.remote(trainCfg)
        reply = ray.get(replyId)
        assert reply.success is True
        outputReplyLines(reply.outputlns, outputFile)
        replyId = self.rtatten.EndRun.remote()
        reply = ray.get(replyId)
        assert reply.success is True
        outputReplyLines(reply.outputlns, outputFile)
        if self.cfg.session.retrieveServerFiles:
            self.retrieveRunFiles(run.runId)

    def retrieveRunFiles(self, runId):
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
        replyId = self.rtatten.RetrieveData.remote(fileInfo)
        reply = ray.get(replyId)
        assert reply.success is True
        print("took {:.2f} secs".format(time.time() - stime))
        clientFile = os.path.join(self.dirs.dataDir, filename)
        writeFile(clientFile, reply.data)
        serverFile = os.path.join(self.dirs.serverDataDir, filename)
        if not os.path.exists(serverFile):
            try:
                os.symlink(clientFile, serverFile)
            except OSError:
                print("Unable to link file %s", serverFile)

    def getNextTRData(self, run, fileNum):
        specificFileName = self.getDicomFileName(run.scanNum, fileNum)
        if self.printFirstFilename:
            print("Loading first file: {}".format(specificFileName))
            self.printFirstFilename = False
        fileExists = os.path.exists(specificFileName)
        if not fileExists and self.observer is None:
            raise FileNotFoundError("No fileNotifier and dicom file not found %s" % (specificFileName))
        while not fileExists:
            # look for file creation event
            event, ts = self.fileNotifyQ.get()
            if event.src_path == specificFileName:
                fileExists = True
        # wait for the full file to be written, wait at most 200 ms
        fileSize = 0
        totalWait = 0.0
        waitIncrement = 0.01
        while fileSize < self.cfg.session.minExpectedDicomSize and totalWait <= 0.3:
            time.sleep(waitIncrement)
            totalWait += waitIncrement
            fileSize = os.path.getsize(specificFileName)
        logStr = "FileWait: fileNum {}: size {}: wait {:.3f}s\n".format(fileNum, fileSize, totalWait)
        self.logtimeFile.write(logStr)
        _, file_extension = os.path.splitext(specificFileName)
        if file_extension == '.mat':
            data = utils.loadMatFile(specificFileName)
            trVol = data.vol
        else:
            dicomImg = ReadDicom.readDicomFromFile(specificFileName)
            trVol = ReadDicom.parseDicomVolume(dicomImg, self.cfg.session.sliceDim)
        return trVol

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

    def initFileNotifier(self, imgDir, filePattern):
        if self.observer is not None:
            self.observer.stop()
        self.observer = Observer()
        if filePattern is None or filePattern == '':
            filePattern = '*'
        self.fileNotifyHandler = FileNotifyHandler(self.fileNotifyQ, [filePattern])
        self.observer.schedule(self.fileNotifyHandler, imgDir, recursive=False)
        self.observer.start()


class FileNotifyHandler(PatternMatchingEventHandler):  # type: ignore
    def __init__(self, q, patterns):
        super().__init__(patterns=patterns)
        self.q = q

    def on_created(self, event):
        self.q.put((event, time.time()))


def makeTrainCfg(run):
    trainCfg = StructDict()
    if run.runId == 1:
        trainCfg.blkGrpRefs = [{'run': 1, 'phase': 1}, {'run': 1, 'phase': 2}]
    elif run.runId == 2:
        trainCfg.blkGrpRefs = [{'run': 1, 'phase': 2}, {'run': 2, 'phase': 1}]
    else:
        trainCfg.blkGrpRefs = [{'run': run.runId-1, 'phase': 1}, {'run': run.runId, 'phase': 1}]
    return trainCfg


def outputPredictionFile(predict, classOutputDir):
    if predict is None or predict.vol is None:
        return
    filename = os.path.join(classOutputDir, 'vol_' + str(predict.vol) + '_py.txt')
    with open(filename, 'w+') as volFile:
        volFile.write(str(predict.catsep))


def outputReplyLines(lines, filehandle):
    if lines is not None:
        for line in lines:
            print(line)
            if filehandle is not None:
                filehandle.write(line + '\n')


def writeFile(filename, data):
    with open(filename, 'wb') as fh:
        bytesWritten = fh.write(data)
        if bytesWritten != len(data):
            raise InterruptedError("Write file %s wrote %d of %d bytes" % (filename, bytesWritten, len(data)))


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--rayremote', '-r', default=None, type=str, help='ray server ip address')
@click.option('--config', '-c', default='conf/example.toml', type=str, help='experiment file (.json or .toml)')
@clickutil.call(ClientMain)
def _ClientMain():
    pass


if __name__ == "__main__":
    _ClientMain()
