'''RtAttenClient - client logic for rtAtten experiment'''
import os
import time
import numpy as np  # type: ignore
import rtfMRI.utils as utils
from ..RtfMRIClient import RtfMRIClient, validateSessionCfg, loadConfigFile
from ..MsgTypes import MsgEvent
from ..StructDict import StructDict, copy_toplevel
from ..Errors import InvocationError
from .PatternsDesign2Config import createPatternsDesignConfig


class RtAttenClient(RtfMRIClient):
    def __init__(self, settings):
        super().__init__(settings)
        self.dirs = StructDict()
        self.cfg = None
        self.prevData = None

    def runSession(self, experiment_file):
        experiment_cfg = loadConfigFile(experiment_file)
        if 'session' not in experiment_cfg.keys():
            raise InvocationError("Experiment file must have session section")
        cfg = createPatternsDesignConfig(experiment_cfg.session)
        validateSessionCfg(cfg)
        self.cfg = cfg
        self.id_fields = StructDict()
        # Send Start Session
        self.id_fields.experimentId = cfg.session.experimentId
        self.id_fields.sessionId = cfg.session.sessionId
        self.id_fields.subjectNum = cfg.session.subjectNum
        self.sendCmdExpectSuccess(MsgEvent.StartSession, cfg.session)
        # Set Working Directories
        if cfg.session.workingDir == 'cwd':
            self.dirs.working = os.getcwd()
        else:
            self.dirs.working = cfg.session.workingDir
        self.dirs.inputData = os.path.join(self.dirs.working, cfg.session.inputDataDir)
        self.dirs.outputData = os.path.join(self.dirs.working, cfg.session.outputDataDir)
        dateStr = time.strftime("%Y%m%d", time.localtime())
        self.dirs.imgData = cfg.session.imgDirHeader + dateStr + '.' +\
            cfg.session.subjectName + '.' + cfg.session.subjectName

        # Process each run
        for idx, run in enumerate(cfg.runs):
            if cfg.session.replayMode == 1:
                run.replayFile = os.path.join(self.dirs.outputData, cfg.session.replayFiles[idx])
                run.validationModel = os.path.join(self.dirs.outputData, cfg.session.validationModels[idx])
            self.runRun(run)
        del self.id_fields.runId
        self.sendCmdExpectSuccess(MsgEvent.EndSession, cfg.session)

    def runRun(self, run):
        self.id_fields.runId = run.runId

        # self.dirs.runDataDir = os.path.join(self.dirs.outputData, 'run' + str(run.id))
        # if not os.path.exists(self.runDataDir):
        #     os.makedirs(self.runDataDir)

        # ** Experimental Parameters ** #
        run.seed = time.time()
        if run.runId > 1:
            run.rtfeedback = 1
        else:
            run.rtfeedback = 0

        # Load ROI mask - an array with 1s indicating the voxels of interest
        temp = utils.loadMatFile(self.dirs.inputData+'/mask_'+str(self.id_fields.subjectNum)+'.mat')
        roi = temp.mask
        assert type(roi) == np.ndarray
        # find indices of non-zero elements in roi in row-major order but sorted by col-major order
        run.roiInds = utils.find(roi)
        run.roiDims = roi.shape
        run.nVoxels = run.roiInds.size

        runCfg = copy_toplevel(run)
        self.sendCmdExpectSuccess(MsgEvent.StartRun, runCfg)

        if run.replayFile is not None:
            # load previous patterns data for this run
            p = utils.loadMatFile(run.replayFile)
            run.replay_data = p.patterns.raw

        # Begin BlockGroups (phases)
        for blockGroup in run.blockGroups:
            self.id_fields.blkGrpId = blockGroup.blkGrpId
            blockGroupCfg = copy_toplevel(blockGroup)
            self.sendCmdExpectSuccess(MsgEvent.StartBlockGroup, blockGroupCfg)
            for block in blockGroup.blocks:
                self.id_fields.blockId = block.blockId
                blockCfg = copy_toplevel(block)
                self.sendCmdExpectSuccess(MsgEvent.StartBlock, blockCfg)
                for TR in block.TRs:
                    self.id_fields.trId = TR.trId
                    if run.replay_data is not None:
                        # TR.vol is 1's based to match matlb, so we want vol-1 for zero based indexing
                        TR.data = run.replay_data[TR.vol-1]
                    else:
                        # Assuming the output file volumes are still 1's based
                        TR.data = self.getNextTRData(TR.vol)
                    self.sendCmdExpectSuccess(MsgEvent.TRData, TR)
                del self.id_fields.trId
                self.sendCmdExpectSuccess(MsgEvent.EndBlock, blockCfg)
            del self.id_fields.blockId
            self.sendCmdExpectSuccess(MsgEvent.EndBlockGroup, blockGroupCfg)
        del self.id_fields.blkGrpId
        # Train the model for this Run
        trainCfg = StructDict()
        if run.runId == 1:
            trainCfg.blkGrpRefs = [{'run': 1, 'phase': 1}, {'run': 1, 'phase': 2}]
        elif run.runId == 2:
            trainCfg.blkGrpRefs = [{'run': 1, 'phase': 2}, {'run': 2, 'phase': 1}]
        else:
            trainCfg.blkGrpRefs = [{'run': run.runId-1, 'phase': 1}, {'run': run.runId, 'phase': 1}]
        self.sendCmdExpectSuccess(MsgEvent.TrainModel, trainCfg)
        self.sendCmdExpectSuccess(MsgEvent.EndRun, runCfg)

    def getNextTRData(self, trial_id):
        if self.cfg.replayData == 1:
            return
