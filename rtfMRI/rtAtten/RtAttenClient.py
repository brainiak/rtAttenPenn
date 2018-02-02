'''RtAttenClient - client logic for rtAtten experiment'''
import os
import time
import logging
import numpy as np  # type: ignore
import rtfMRI.utils as utils
from ..RtfMRIClient import RtfMRIClient, validateSessionCfg
from ..MsgTypes import MsgEvent
from ..StructDict import StructDict, copy_toplevel
from .PatternsDesign2Config import createPatternsDesignConfig


class RtAttenClient(RtfMRIClient):
    def __init__(self, addr, port):
        super().__init__(addr, port)
        self.dirs = StructDict()
        self.cfg = None
        self.prevData = None

    def runSession(self, experiment_cfg):
        assert self.modelName == 'rtAtten'
        cfg = createPatternsDesignConfig(experiment_cfg.session)
        validateSessionCfg(cfg)
        self.cfg = cfg
        self.id_fields = StructDict()

        # Send Start Session
        self.id_fields.experimentId = cfg.session.experimentId
        self.id_fields.sessionId = cfg.session.sessionId
        self.id_fields.subjectNum = cfg.session.subjectNum
        logging.debug("Start session {}".format(cfg.session.sessionId))
        self.sendCmdExpectSuccess(MsgEvent.StartSession, cfg.session)

        # Set Directories
        if cfg.session.workingDir == 'cwd':
            self.dirs.workingDir = os.getcwd()
        else:
            self.dirs.workingDir = cfg.session.workingDir
        self.dirs.inputDataDir = os.path.join(self.dirs.workingDir, cfg.session.inputDataDir)
        self.dirs.outputDataDir = os.path.join(self.dirs.workingDir, cfg.session.outputDataDir)
        dateStr = time.strftime("%Y%m%d", time.localtime())
        self.dirs.imgDataDir = cfg.session.imgDirHeader + dateStr + '.' +\
            cfg.session.subjectName + '.' + cfg.session.subjectName

        # Process each run
        for idx, run in enumerate(cfg.runs):
            if cfg.session.replayMode == 1:
                run.replayFile = os.path.join(self.dirs.outputDataDir, cfg.session.replayFiles[idx])
                run.validationModel = os.path.join(self.dirs.outputDataDir, cfg.session.validationModels[idx])
            self.runRun(run)
        del self.id_fields.runId
        self.sendCmdExpectSuccess(MsgEvent.EndSession, cfg.session)

    def runRun(self, run):
        self.id_fields.runId = run.runId

        # Setup output directory and output file
        runDataDir = os.path.join(self.dirs.outputDataDir, 'run' + str(run.runId))
        if not os.path.exists(runDataDir):
            os.makedirs(runDataDir)
        outputFile = open(os.path.join(runDataDir, 'fileprocessing_py.txt'), 'w+')

        # ** Experimental Parameters ** #
        run.seed = time.time()
        if run.runId > 1:
            run.rtfeedback = 1
        else:
            run.rtfeedback = 0

        # Load ROI mask - an array with 1s indicating the voxels of interest
        temp = utils.loadMatFile(self.dirs.inputDataDir+'/mask_'+str(self.id_fields.subjectNum)+'.mat')
        roi = temp.mask
        assert type(roi) == np.ndarray
        # find indices of non-zero elements in roi in row-major order but sorted by col-major order
        run.roiInds = utils.find(roi)
        run.roiDims = roi.shape
        run.nVoxels = run.roiInds.size

        runCfg = copy_toplevel(run)
        reply = self.sendCmdExpectSuccess(MsgEvent.StartRun, runCfg)
        outputReplyLines(reply.fields.outputlns, outputFile)

        if run.replayFile is not None:
            # load previous patterns data for this run
            p = utils.loadMatFile(run.replayFile)
            run.replay_data = p.patterns.raw

        # Begin BlockGroups (phases)
        for blockGroup in run.blockGroups:
            self.id_fields.blkGrpId = blockGroup.blkGrpId
            blockGroupCfg = copy_toplevel(blockGroup)
            reply = self.sendCmdExpectSuccess(MsgEvent.StartBlockGroup, blockGroupCfg)
            outputReplyLines(reply.fields.outputlns, outputFile)
            for block in blockGroup.blocks:
                self.id_fields.blockId = block.blockId
                blockCfg = copy_toplevel(block)
                reply = self.sendCmdExpectSuccess(MsgEvent.StartBlock, blockCfg)
                outputReplyLines(reply.fields.outputlns, outputFile)
                for TR in block.TRs:
                    self.id_fields.trId = TR.trId
                    if run.replay_data is not None:
                        # TR.vol is 1's based to match matlb, so we want vol-1 for zero based indexing
                        TR.data = run.replay_data[TR.vol-1]
                    else:
                        # Assuming the output file volumes are still 1's based
                        TR.data = self.getNextTRData(TR.vol)
                    reply = self.sendCmdExpectSuccess(MsgEvent.TRData, TR)
                    outputReplyLines(reply.fields.outputlns, outputFile)
                    outputPredictionFile(reply.fields.predict, runDataDir)
                del self.id_fields.trId
                reply = self.sendCmdExpectSuccess(MsgEvent.EndBlock, blockCfg)
                outputReplyLines(reply.fields.outputlns, outputFile)
            del self.id_fields.blockId
            reply = self.sendCmdExpectSuccess(MsgEvent.EndBlockGroup, blockGroupCfg)
            outputReplyLines(reply.fields.outputlns, outputFile)
        del self.id_fields.blkGrpId
        # Train the model for this Run
        trainCfg = StructDict()
        if run.runId == 1:
            trainCfg.blkGrpRefs = [{'run': 1, 'phase': 1}, {'run': 1, 'phase': 2}]
        elif run.runId == 2:
            trainCfg.blkGrpRefs = [{'run': 1, 'phase': 2}, {'run': 2, 'phase': 1}]
        else:
            trainCfg.blkGrpRefs = [{'run': run.runId-1, 'phase': 1}, {'run': run.runId, 'phase': 1}]
        reply = self.sendCmdExpectSuccess(MsgEvent.TrainModel, trainCfg)
        outputReplyLines(reply.fields.outputlns, outputFile)
        reply = self.sendCmdExpectSuccess(MsgEvent.EndRun, runCfg)
        outputReplyLines(reply.fields.outputlns, outputFile)

    def getNextTRData(self, trial_id):
        if self.cfg.replayData == 1:
            return


def outputReplyLines(lines, filehandle):
    if lines is not None:
        for line in lines:
            print(line)
            filehandle.write(line + '\n')


def outputPredictionFile(predict, runDataDir):
    if predict is None or predict.vol is None:
        return
    filename = os.path.join(runDataDir, 'vol_' + str(predict.vol) + '_py')
    with open(filename, 'w+') as volFile:
        volFile.write(str(predict.catsep))
