"""
RTAttenModel: Server-side logic for the real-time attention fMRI experiment

This module extends the generic BaseModel server-side logic for fMRI experiments,
and implements specific functionality for the real-time attention study.
This module primarily overrides the Start/End Session, Start/End Block Group,
and TRData funtions to handle data specific to the experiment
"""
import os
import time
import glob
import datetime
import logging
import numpy as np  # type: ignore
from enum import Enum, unique
import scipy.io as sio  # type: ignore
from sklearn.linear_model import LogisticRegression  # type: ignore
import rtfMRI.utils as utils
import rtfMRI.ValidationUtils as vutils
from ..MsgTypes import MsgResult
from ..BaseModel import BaseModel
from ..StructDict import StructDict, MatlabStructDict
from .smooth import smooth
from .highpassFunc import highPassRealTime, highPassBetweenRuns
from .Test_L2_RLR_realtime import Test_L2_RLR_realtime


class RtAttenModel(BaseModel):
    def __init__(self):
        super().__init__()
        self.dirs = StructDict()
        self.blkGrpCache = {}  # type: ignore
        self.modelCache = {}  # type: ignore
        self.session = None
        self.run = None
        self.blkGrp = None

    def StartSession(self, msg):
        """Initializes a session comprising multiple runs.
        Sets up data directories and clears caches
        """
        reply = super().StartSession(msg)
        if reply.result != MsgResult.Success:
            return reply
        self.session = msg.fields.cfg
        subjectDayDir = getSubjectDayDir(self.session.subjectNum, self.session.subjectDay)
        self.dirs.dataDir = os.path.join(self.session.serverDataDir, subjectDayDir)
        if not os.path.exists(self.dirs.dataDir):
            os.makedirs(self.dirs.dataDir)
        # clear cached items
        self.blkGrpCache = {}
        self.modelCache = {}
        return reply

    def EndSession(self, msg):
        # drop cached items
        self.blkGrpCache = {}
        self.modelCache = {}
        reply = super().EndSession(msg)
        return reply

    def StartRun(self, msg):
        """Initializes a run
        Updates caches, inits filecounter, returns header output.
        """
        reply = super().StartRun(msg)
        if reply.result != MsgResult.Success:
            return reply
        run = msg.fields.cfg
        if run.runId != self.id_fields.runId:
            errorReply = self.createReplyMessage(msg, MsgResult.Error)
            errorReply.data = "RunId mismatch: msg runId %r != session RunId %r" % (run.runId, self.id_fields.runId)
            return errorReply
        logging.info("Using ScanNum: %d", run.scanNum)
        if run.runId > 1:
            if len(self.blkGrpCache) > 1:
                # remove any cache items older than the previous run
                self.trimCache(run.runId - 1)
        run.fileCounter = 0

        # Output header
        now = datetime.datetime.now()
        reply.fields.outputlns.append('*********************************************')
        reply.fields.outputlns.append('* rtAttenPenn v.1.0')
        reply.fields.outputlns.append('* Date/Time: ' + now.isoformat())
        reply.fields.outputlns.append('* Seed: ' + str(self.session.seed))
        reply.fields.outputlns.append('* Subject Number: ' + str(self.session.subjectNum))
        reply.fields.outputlns.append('* Subject Name: ' + str(self.session.subjectName))
        reply.fields.outputlns.append('* Run Number: ' + str(run.runId))
        reply.fields.outputlns.append('* Real-Time Data: ' + str(self.session.rtData))
        reply.fields.outputlns.append('*********************************************\n')

        # ** Start Run ** #
        # prepare for TR sequence
        reply.fields.outputlns.append('run\tblock\tTR\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg')

        self.run = run
        return reply

    def EndRun(self, msg):
        self.trimCache(self.id_fields.runId)
        reply = super().EndRun(msg)
        return reply

    def StartBlockGroup(self, msg):
        """Initialize a block group. A run is comprised of 2 block groups (called phases in Matlab version).
        Block groups can be of type 1=(Training) or 2=(RealTime Predictions)
        Initialize the patterns data structure for the block group.
        If it is a prediction group (type 2) then load the trained model from the
        previous run and load the patterns data from the previous block group.
        """
        reply = super().StartBlockGroup(msg)
        if reply.result != MsgResult.Success:
            return reply
        errorReply = self.createReplyMessage(msg, MsgResult.Error)
        blkGrp = msg.fields.cfg
        run = self.run
        if blkGrp.nTRs is None:
            errorReply.data = "StartBlkGrp msg missing nTRs in blockGroup"
            return errorReply
        if self.session.nVoxels is None:
            errorReply.data = "StartBlkGrp msg missing nVoxels in blockGroup"
            return errorReply
        if self.session.roiInds is None:
            errorReply.data = "StartBlkGrp msg missing roiInds in blockGroup"
            return errorReply
        if blkGrp.blkGrpId not in (1, 2):
            errorReply.data = "StartBlkGrp: BlkGrpId {} not valid" % (blkGrp.blkGrpId)
            return errorReply
        blkGrp.legacyRun1Phase2Mode = False
        if run.runId == 1 and blkGrp.blkGrpId == 2 and self.session.legacyRun1Phase2Mode:
            # Handle as legacy matlab where run1, phase2 is treated as testing
            blkGrp.legacyRun1Phase2Mode = True
        blkGrp.patterns = StructDict()
        blkGrp.patterns.raw = np.full((blkGrp.nTRs, self.session.nVoxels), np.nan)
        blkGrp.patterns.raw_sm = np.full((blkGrp.nTRs, self.session.nVoxels), np.nan)
        blkGrp.patterns.raw_sm_filt = np.full((blkGrp.nTRs, self.session.nVoxels), np.nan)
        blkGrp.patterns.raw_sm_filt_z = np.full((blkGrp.nTRs, self.session.nVoxels), np.nan)
        blkGrp.patterns.phase1Mean = np.full((1, self.session.nVoxels), np.nan)
        blkGrp.patterns.phase1Y = np.full((1, self.session.nVoxels), np.nan)
        blkGrp.patterns.phase1Std = np.full((1, self.session.nVoxels), np.nan)
        blkGrp.patterns.phase1Var = np.full((1, self.session.nVoxels), np.nan)
        blkGrp.patterns.categoryseparation = np.full((1, blkGrp.nTRs), np.nan)  # (matlab: NaN(1,nTRs))
        blkGrp.patterns.predict = np.full((1, blkGrp.nTRs), np.nan)
        blkGrp.patterns.activations = np.full((2, blkGrp.nTRs), np.nan)
        blkGrp.patterns.attCateg = np.full((1, blkGrp.nTRs), np.nan)
        blkGrp.patterns.stim = np.full((1, blkGrp.nTRs), np.nan)
        blkGrp.patterns.type = np.full((1, blkGrp.nTRs), np.nan)
        blkGrp.patterns.regressor = np.full((2, blkGrp.nTRs), np.nan)
        # blkGrp.patterns.fileAvail = np.zeros((1, blkGrp.nTRs), dtype=np.uint8)
        blkGrp.patterns.fileload = np.full((1, blkGrp.nTRs), np.nan, dtype=np.uint8)
        blkGrp.patterns.fileNum = np.full((1, blkGrp.nTRs), np.nan, dtype=np.uint16)
        self.blkGrp = blkGrp
        if self.blkGrp.type == 2 or blkGrp.legacyRun1Phase2Mode:
            # ** Realtime Feedback Phase ** #
            try:
                # get blkGrp from phase 1
                prev_bg = self.getPrevBlkGrp(self.id_fields.sessionId, self.id_fields.runId, 1)
            except Exception as err:
                errorReply.data = "Error: getPrevBlkGrp(%r, %r, 1): %r" %\
                    (self.id_fields.sessionId, self.id_fields.runId, err)
                return errorReply
            self.blkGrp.patterns.phase1Mean[0, :] = prev_bg.patterns.phase1Mean[0, :]
            self.blkGrp.patterns.phase1Y[0, :] = prev_bg.patterns.phase1Y[0, :]
            self.blkGrp.patterns.phase1Std[0, :] = prev_bg.patterns.phase1Std[0, :]
            self.blkGrp.patterns.phase1Var[0, :] = prev_bg.patterns.phase1Var[0, :]
            self.blkGrp.combined_raw_sm = np.concatenate((prev_bg.patterns.raw_sm, blkGrp.patterns.raw_sm))
            self.blkGrp.combined_catsep = np.concatenate((prev_bg.patterns.categoryseparation,
                                                          blkGrp.patterns.categoryseparation))

            if self.id_fields.runId > 1:
                try:
                    # get trained model
                    self.blkGrp.trainedModel = self.getTrainedModel(self.id_fields.sessionId, self.id_fields.runId-1)
                except Exception as err:
                    errorReply.data = "Error: getTrainedModel(%r, %r): %r" %\
                        (self.id_fields.sessionId, self.id_fields.runId-1, err)
                    return errorReply
            reply.fields.outputlns.append('\n*********************************************')
            reply.fields.outputlns.append('beginning model testing...')
            # prepare for TR sequence
            reply.fields.outputlns.append('run\tblock\tTR\tbltyp\tblcat\tstim\tfilenum\tloaded\tpredict\toutput\tavg')
        return reply

    def EndBlockGroup(self, msg):
        """Finalize block group
        Complete calculations for the patterns data, do validation or results
        compared to a previous known run if requested, save the block group
        patterns data to a file.
        """
        patterns = self.blkGrp.patterns
        i1, i2 = 0, self.blkGrp.nTRs
        outputlns = []  # type: ignore
        # set validation indices
        validation_i1 = self.blkGrp.firstVol
        validation_i2 = validation_i1 + self.blkGrp.nTRs

        if self.blkGrp.type == 2 or self.blkGrp.legacyRun1Phase2Mode:  # RT predict
            runStd = np.nanstd(patterns.raw_sm_filt, axis=0)
            patterns.runStd = runStd.reshape(1, -1)
            # Do Validation
            if self.session.validate:
                try:
                    self.validateTestBlkGrp(validation_i1, validation_i2, outputlns)
                except Exception as err:
                    # Just log that an error happened during validation
                    logging.error("validateTestBlkGrp: %r", err)
                    pass

        elif self.blkGrp.type == 1:  # training
            outputlns.append('\n*********************************************')
            outputlns.append('beginning highpassfilter/zscore...')

            patterns.raw_sm_filt[i1:i2, :] = highPassBetweenRuns(patterns.raw_sm[i1:i2, :],
                                                                 self.run.TRTime, self.session.cutoff)
            # if self.blkGrp.blkGrpId == 1:
            # Calculate mean and stddev values for phase1 data (i.e. 1st blkGrp)
            patterns.phase1Mean[0, :] = np.mean(patterns.raw_sm_filt[i1:i2, :], axis=0)
            patterns.phase1Y[0, :] = np.mean(patterns.raw_sm_filt[i1:i2, :]**2, axis=0)
            patterns.phase1Std[0, :] = np.std(patterns.raw_sm_filt[i1:i2, :], axis=0)
            patterns.phase1Var[0, :] = patterns.phase1Std[0, :] ** 2
            # else:
            #     # get blkGrp from phase 1
            #     prev_bg = self.getPrevBlkGrp(self.id_fields.sessionId, self.id_fields.runId, 1)
            #     patterns.phase1Mean[0, :] = prev_bg.patterns.phase1Mean[0, :]
            #     patterns.phase1Y[0, :] = prev_bg.patterns.phase1Y[0, :]
            #     patterns.phase1Std[0, :] = prev_bg.patterns.phase1Std[0, :]
            #     patterns.phase1Var[0, :] = prev_bg.patterns.phase1Var[0, :]
            tileSize = [patterns.raw_sm_filt[i1:i2, :].shape[0], 1]
            patterns.raw_sm_filt_z[i1:i2, :] = np.divide(
                (patterns.raw_sm_filt[i1:i2, :] - np.tile(patterns.phase1Mean, tileSize)),
                np.tile(patterns.phase1Std, tileSize))
            # std dev across all volumes per voxel
            runStd = np.nanstd(patterns.raw_sm_filt, axis=0)
            patterns.runStd = runStd.reshape(1, -1)
            # Do Validation
            if self.session.validate:
                try:
                    self.validateTrainBlkGrp(validation_i1, validation_i2, outputlns)
                except Exception as err:
                    # Just log that an error happened during validation
                    logging.error("validateTrainBlkGrp: %r", err)
                    pass

            # cache the block group for predict phase and training the model
            bgKey = getBlkGrpKey(self.id_fields.runId, self.id_fields.blkGrpId)
            self.blkGrpCache[bgKey] = self.blkGrp

        else:
            errorReply = self.createReplyMessage(msg, MsgResult.Error)
            errorReply.data = "Unknown blkGrp type {}".format(self.blkGrp.type)
            return errorReply

        # save BlockGroup Data
        filename = getBlkGrpFilename(self.id_fields.sessionId,
                                     self.id_fields.runId,
                                     self.id_fields.blkGrpId)
        blkGrpFilename = os.path.join(self.dirs.dataDir, filename)
        reply = super().EndBlockGroup(msg)
        try:
            sio.savemat(blkGrpFilename, self.blkGrp, appendmat=False)
        except Exception as err:
            errorReply = self.createReplyMessage(msg, MsgResult.Error)
            errorReply.data = "Error: Unable to save blkGrpFile %s: %r" % (blkGrpFilename, err)
            return errorReply
        reply.fields.outputlns = outputlns
        return reply

    def TRData(self, msg):
        """Process the data from an fMRI scan.
        In training case smooth and add the data to the accumulated block in
        order to later create a ML model
        In realtime prediction case, do classification based on the loaded model
        """
        TR = msg.fields.cfg
        reply = super().TRData(msg)
        errorReply = self.createReplyMessage(msg, MsgResult.Error)
        if reply.result != MsgResult.Success:
            return reply
        if TR.type not in (0, 1, 2) or self.blkGrp.type not in (1, 2):
            errorReply.data = "Unknown TR type %r" % (TR.type)
            return errorReply
        if TR.trId is None:
            errorReply.data = "missing TR.trId"
            return errorReply
        outputlns = []  # type: ignore
        self.run.fileCounter = self.run.fileCounter + 1

        patterns = self.blkGrp.patterns
        setTrData(patterns, TR.trId, TR.data)
        patterns.attCateg[0, TR.trId] = TR.attCateg
        patterns.stim[0, TR.trId] = TR.stim
        patterns.type[0, TR.trId] = TR.type
        patterns.regressor[:, TR.trId] = TR.regressor[:]
        patterns.fileNum[0, TR.trId] = TR.vol + self.run.disdaqs // self.run.TRTime

        patterns.raw_sm[TR.trId, :] =\
            smooth(patterns.raw[TR.trId, :], self.session.roiDims, self.session.roiInds, self.session.FWHM)

        if TR.type == 2 or (TR.type == 0 and self.blkGrp.type == 2) or\
                self.blkGrp.legacyRun1Phase2Mode:
            # Testing
            predict_result, outputlns = self.Predict(TR)
            reply.fields.predict = predict_result
        elif TR.type == 1 or (TR.type == 0 and self.blkGrp.type == 1):
            # Training
            output_str = '{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}\t{:d}\t{:.3f}\t{:.3f}'.format(
                self.id_fields.runId, self.id_fields.blockId, TR.trId, TR.type, TR.attCateg, TR.stim,
                patterns.fileNum[0, TR.trId], patterns.fileload[0, TR.trId], np.nan, np.nan)
            outputlns.append(output_str)
        else:
            errorReply.data = "Process TR, TR.type %r or blkGrp.type %r unexpected" % (TR.type, self.blkGrp.type)
            return errorReply
        reply.fields.outputlns = outputlns
        return reply

    def Predict(self, TR):
        """Given a scan image (TR) predict the classification of the data (face/scene)
        """
        predict_result = StructDict()
        outputlns = []
        patterns = self.blkGrp.patterns
        combined_raw_sm = self.blkGrp.combined_raw_sm
        combined_TRid = self.blkGrp.firstVol + TR.trId

        combined_raw_sm[combined_TRid] = patterns.raw_sm[TR.trId]
        patterns.raw_sm_filt[TR.trId, :] = \
            highPassRealTime(combined_raw_sm[0:combined_TRid+1, :], self.run.TRTime, self.session.cutoff)
        patterns.raw_sm_filt_z[TR.trId, :] = \
            (patterns.raw_sm_filt[TR.trId, :] - patterns.phase1Mean[0, :]) / patterns.phase1Std[0, :]

        if self.run.rtfeedback:
            TR_regressor = np.array(TR.regressor)
            if np.any(TR_regressor):
                patterns.predict[0, TR.trId], _, _, patterns.activations[:, TR.trId] = \
                    Test_L2_RLR_realtime(self.blkGrp.trainedModel, patterns.raw_sm_filt_z[TR.trId, :],
                                         TR_regressor)
                # determine whether expecting face or scene for this TR
                categ = np.flatnonzero(TR_regressor)
                # the other category will be categ+1 mod 2 since there are only two category types
                otherCateg = (categ + 1) % 2
                patterns.categoryseparation[0, TR.trId] = \
                    patterns.activations[categ, TR.trId]-patterns.activations[otherCateg, TR.trId]
            else:
                patterns.categoryseparation[0, TR.trId] = np.nan
            predict_result.catsep = patterns.categoryseparation[0, TR.trId]
            predict_result.vol = patterns.fileNum[0, TR.trId]
        else:
            patterns.categoryseparation[0, TR.trId] = np.nan

        # print TR results
        categorysep_mean = np.nan
        # TODO - do we need to handle 0:TR here to include phase 1 data?
        if not np.all(np.isnan(patterns.categoryseparation[0, 0:TR.trId+1])):
            categorysep_mean = np.nanmean(patterns.categoryseparation[0, 0:TR.trId+1])
        output_str = '{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}\t{:d}\t{:.1f}\t{:.3f}\t{:.3f}'.format(
            self.id_fields.runId, self.id_fields.blockId, TR.trId, TR.type, TR.attCateg, TR.stim,
            patterns.fileNum[0, TR.trId], patterns.fileload[0, TR.trId], patterns.predict[0, TR.trId],
            patterns.categoryseparation[0, TR.trId], categorysep_mean)
        outputlns.append(output_str)
        return predict_result, outputlns

    def TrainModel(self, msg):
        """Load block group patterns data from this and the previous run and
        create the ML model for the next run. Save the model to a file.
        """
        reply = super().TrainModel(msg)
        trainStart = time.time()  # start timing
        # print training results
        reply.fields.outputlns.append('\n*********************************************')
        reply.fields.outputlns.append('beginning model training...')

        # load data to train model
        trainCfg = msg.fields.cfg
        bgRef1 = StructDict(trainCfg.blkGrpRefs[0])
        bgRef2 = StructDict(trainCfg.blkGrpRefs[1])
        try:
            bg1 = self.getPrevBlkGrp(self.id_fields.sessionId, bgRef1.run, bgRef1.phase)
            bg2 = self.getPrevBlkGrp(self.id_fields.sessionId, bgRef2.run, bgRef2.phase)
        except Exception as err:
            errorReply = self.createReplyMessage(msg, MsgResult.Error)
            if bg1 is None:
                errorReply.data = "Error: getPrevBlkGrp(%r, %r, %r): %r" %\
                    (self.id_fields.sessionId, bgRef1.run, bgRef1.phase, err)
            else:
                errorReply.data = "Error: getPrevBlkGrp(%r, %r, %r): %r" %\
                    (self.id_fields.sessionId, bgRef2.run, bgRef2.phase, err)
            return errorReply

        trainIdx1 = utils.find(np.any(bg1.patterns.regressor, axis=0))
        trainLabels1 = np.transpose(bg1.patterns.regressor[:, trainIdx1])  # find the labels of those indices
        trainPats1 = bg1.patterns.raw_sm_filt_z[trainIdx1, :]  # retrieve the patterns of those indices

        trainIdx2 = utils.find(np.any(bg2.patterns.regressor, axis=0))
        trainLabels2 = np.transpose(bg2.patterns.regressor[:, trainIdx2])
        trainPats2 = bg2.patterns.raw_sm_filt_z[trainIdx2, :]

        trainPats = np.concatenate((trainPats1, trainPats2))
        trainLabels = np.concatenate((trainLabels1, trainLabels2))
        trainLabels = trainLabels.astype(np.uint8)

        # train the model
        # sklearn LogisticRegression takes on set of labels and returns one set of weights.
        # The version implemented in Matlab can take multple sets of labels and return multiple weights.
        # To reproduct that behavior here, we will use a LogisticRegression instance for each set of lables (2 in this case)
        lrc1 = LogisticRegression()
        lrc2 = LogisticRegression()
        lrc1.fit(trainPats, trainLabels[:, 0])
        lrc2.fit(trainPats, trainLabels[:, 1])
        newTrainedModel = utils.MatlabStructDict({}, 'trainedModel')
        newTrainedModel.trainedModel = StructDict({})
        newTrainedModel.trainedModel.weights = np.concatenate((lrc1.coef_.T, lrc2.coef_.T), axis=1)
        newTrainedModel.trainedModel.biases = np.concatenate((lrc1.intercept_, lrc2.intercept_)).reshape(1, 2)
        newTrainedModel.trainPats = trainPats
        newTrainedModel.trainLabels = trainLabels

        trainEnd = time.time()  # end timing
        trainingOnlyTime = trainEnd - trainStart

        # print training timing and results
        outStr = 'model training time: \t{:.3f}'.format(trainingOnlyTime)
        reply.fields.outputlns.append(outStr)
        if newTrainedModel.biases is not None:
            outStr = 'model biases: \t{:.3f}\t{:.3f}'.format(
                newTrainedModel.biases[0, 0], newTrainedModel.biases[0, 1])
            reply.fields.outputlns.append(outStr)

        # cache the trained model
        self.modelCache[self.id_fields.runId] = newTrainedModel

        if self.session.validate:
            try:
                self.validateModel(newTrainedModel, reply.fields.outputlns)
            except Exception as err:
                # Just log that an error happened during validation
                logging.error("validateModel: %r", err)
                pass
        # write trained model to a file
        filename = getModelFilename(self.id_fields.sessionId, self.id_fields.runId)
        trainedModel_fn = os.path.join(self.dirs.dataDir, filename)
        try:
            sio.savemat(trainedModel_fn, newTrainedModel, appendmat=False)
        except Exception as err:
            errorReply = self.createReplyMessage(msg, MsgResult.Error)
            errorReply.data = "Error: Unable to save trainedModel %s: %s" % (filename, str(err))
            return errorReply
        return reply

    def RetrieveData(self, msg):
        """Retrieve a specfic data file.
        Sets the file path based on the session directory settings and then
        calls the BaseModel retrieve function.
        """
        fileInfo = msg.fields.cfg
        subjectDayDir = getSubjectDayDir(fileInfo.subjectNum, fileInfo.subjectDay)
        fullFileName = os.path.join(self.session.serverDataDir, subjectDayDir, fileInfo.filename)
        msg.fields.cfg = fullFileName
        reply = super().RetrieveData(msg)
        return reply

    def DeleteData(self, msg):
        """Delete data files matching the supplied pattern"""
        reply = self.createReplyMessage(msg, MsgResult.Success)
        fileInfo = msg.fields.cfg
        filePattern = fileInfo.filePattern
        # check that pattern is in the server directory
        if filePattern.startswith(self.dirs.dataDir):
            reply.fields.outputlns.append("Deleted:")
            for filename in glob.glob(filePattern):
                if os.path.isfile(filename):
                    reply.fields.outputlns.append(filename)
                    os.remove(filename)
        else:
            # invalid filepattern
            reply = self.createReplyMessage(msg, MsgResult.Error)
            reply.data = "Invalid filepattern: Must start with session directory %s"\
                         % (self.dirs.dataDir)
        return reply

    def getPrevBlkGrp(self, sessionId, runId, blkGrpId):
        """Retrieve a block group patterns data, first see if it is cached
        in memory, if not load it from file and add it to the cache.
        """
        bgKey = getBlkGrpKey(runId, blkGrpId)
        prev_bg = self.blkGrpCache.get(bgKey, None)
        if prev_bg is None:
            # load it from file
            logging.info("blkGrpCache miss on <runId, blkGrpId> %s", bgKey)
            fname = os.path.join(self.dirs.dataDir, getBlkGrpFilename(sessionId, runId, blkGrpId))
            prev_bg = utils.loadMatFile(fname)
            # loadMatFile should either raise an exception or return a value
            assert prev_bg is not None, "Load blkGrp returned None: %s" % (fname)
            if sessionId == self.id_fields.sessionId:
                self.blkGrpCache[bgKey] = prev_bg
        return prev_bg

    def getTrainedModel(self, sessionId, runId):
        """Retrieve a ML model trained in a previous run (runId). First see if it
        is cached in memory, if not load it from file and add it to the cache.
        """
        model = self.modelCache.get(runId, None)
        if model is None:
            # load it from file
            logging.info("modelCache miss on runId %d", runId)
            fname = os.path.join(self.dirs.dataDir, getModelFilename(sessionId, runId))
            model = utils.loadMatFile(fname)
            # loadMatFile should either raise an exception or return a value
            assert model is not None, "Load model returned None: %s" % (fname)
        if sessionId == self.id_fields.sessionId:
            self.modelCache[runId] = model
        return model

    def trimCache(self, oldestRunId):
        """Remove any cached elements older than oldestRunId
        """
        # trim blkGrpCache
        rm_keys = []
        for bgKey in self.blkGrpCache.keys():
            cache_runId, cache_blkGrpId = bgKey.split('.')
            if int(cache_runId) < oldestRunId:
                rm_keys.append(bgKey)
        for key in rm_keys:
            del(self.blkGrpCache[key])
        # trim modelCache
        rm_keys = [runId for runId in self.modelCache.keys() if runId < oldestRunId]
        for key in rm_keys:
            del(self.modelCache[key])

    def validateTrainBlkGrp(self, target_i1, target_i2, outputlns):
        """Compare the block group patterns file created in this run with that of
         a previous run (i.e. using the Matlab software) but having the same raw input
        """
        patterns = MatlabStructDict(self.blkGrp.patterns)
        # load the replay file for target outcomes
        target_patternsdata = utils.loadMatFile(self.run.validationDataFile)
        target_patterns = target_patternsdata.patterns
        strip_patterns(target_patterns, range(target_i1, target_i2))
        cmp_fields = ['raw', 'raw_sm', 'raw_sm_filt', 'raw_sm_filt_z',
                      'phase1Mean', 'phase1Y', 'phase1Std', 'phase1Var', 'regressor']
        res = vutils.compareMatStructs(patterns, target_patterns, field_list=cmp_fields)
        res_means = {key: value['mean'] for key, value in res.items()}
        outputlns.append("Validation Means: {}".format(res_means))
        # calculate the pierson correlation for raw_sm_filt_z
        pearson_mean = vutils.pearsons_mean_corr(patterns.raw_sm_filt_z, target_patterns.raw_sm_filt_z)
        outputlns.append("Phase1 sm_filt_z mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            # assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)
            logging.warn("Pearson mean for raw_sm_filt_z low, %f", pearson_mean)

    def validateTestBlkGrp(self, target_i1, target_i2, outputlns):
        """Compare the block group patterns file created in this run with that of
         a previous run (i.e. using the Matlab software) but having the same raw input
        """
        patterns = MatlabStructDict(self.blkGrp.patterns)
        # load the replay file for target outcomes
        target_patternsdata = utils.loadMatFile(self.run.validationDataFile)
        target_patterns = target_patternsdata.patterns
        strip_patterns(target_patterns, range(target_i1, target_i2))
        cmp_fields = ['raw', 'raw_sm', 'raw_sm_filt', 'raw_sm_filt_z',
                      'phase1Mean', 'phase1Y', 'phase1Std', 'phase1Var',
                      'categoryseparation', 'regressor']
        res = vutils.compareMatStructs(patterns, target_patterns, field_list=cmp_fields)
        res_means = {key: value['mean'] for key, value in res.items()}
        outputlns.append("Validation Means: {}".format(res_means))
        # Make sure the predict array values are identical
        # Predict values are (1, 2) in matlab, (0, 1) in python because it
        # Check if we need to convert from matlab to python values
        if (not np.all(np.isnan(target_patterns.predict))) and\
                np.nanmax(target_patterns.predict) > 1:
            # convert target.predict to zero based indexing
            target_patterns.predict = target_patterns.predict-1
        predictions_match = np.allclose(target_patterns.predict, patterns.predict, rtol=0, atol=0, equal_nan=True)
        if predictions_match:
            outputlns.append("All predictions match: {}".format(predictions_match))
        else:
            mask = ~np.isnan(target_patterns.predict)
            miss_count = np.sum(patterns.predict[mask] != target_patterns.predict[mask])
            outputlns.append("WARNING: predictions differ in {} TRs".format(miss_count))
        # calculate the pearson correlation for categoryseparation
        pearson_mean = vutils.pearsons_mean_corr(patterns.categoryseparation, target_patterns.categoryseparation)
        outputlns.append("Phase2 categoryseparation mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            outputlns.append("WARN: Pearson mean for categoryseparation low, {}".format(pearson_mean))
        # calculate the pearson correlation for raw_sm_filt_z
        pearson_mean = vutils.pearsons_mean_corr(patterns.raw_sm_filt_z, target_patterns.raw_sm_filt_z)
        outputlns.append("Phase2 sm_filt_z mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            # assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)
            outputlns.append("WARN: Pearson mean for raw_sm_filt_z low, {}".format(pearson_mean))

    def validateModel(self, newTrainedModel, outputlns):
        """Compare the trained model for this block group to a trained model
        created from a previous run using the same data (i.e. from the Matlab version)
        """
        target_model = utils.loadMatFile(self.run.validationModel)
        cmp_fields = ['trainLabels', 'weights', 'biases', 'trainPats']
        res = vutils.compareMatStructs(newTrainedModel, target_model, field_list=cmp_fields)
        res_means = {key: value['mean'] for key, value in res.items()}
        outputlns.append("TrainModel Validation Means: {}".format(res_means))
        # calculate the pierson correlation for trainPats
        pearson_mean = vutils.pearsons_mean_corr(newTrainedModel.trainPats, target_model.trainPats)
        outputlns.append("trainPats mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            # assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)
            logging.warn("Pearson mean for trainPats low, %f", pearson_mean)
        # calculate the pierson correlation for model weights
        pearson_mean = vutils.pearsons_mean_corr(newTrainedModel.weights, target_model.weights)
        outputlns.append("trainedWeights mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            # assert pearson_mean > .99, "Pearsons mean {} too low".format(pearson_mean)
            outputlns.append("WARN: Pearson mean for trainWeights low, {}".format(pearson_mean))


def setTrData(patterns, trId, data):
    """Given a new TR data vector, only use the data if there are no NaN values.
    If there are NaN values, find the last known good TR (with no NaNs) and use
    that again for this TR. Otherwise if there are no NaNs then set the patterns.raw
    to this new data. Update the fileload array to indicate if this data was
    used (file was loaded) or not.
    """
    TRsLoaded = np.where(patterns.fileload.squeeze() == 1)
    if np.any(np.isnan(data)) and len(TRsLoaded[0]) > 0:
        # data has NaN in it so load the last good data
        patterns.fileload[0, trId] = 0
        indLastValidPattern = np.max(TRsLoaded)
        patterns.raw[trId, :] = patterns.raw[indLastValidPattern, :]
    else:
        patterns.fileload[0, trId] = 1
        patterns.raw[trId, :] = data


def getSubjectDayDir(subjectNum, subjectDay):
    """The data directory is structured by subjectNum/subjectDay.
    Return that sub-directory.
    """
    subjectDayDir = "subject{}/day{}".format(subjectNum, subjectDay)
    return subjectDayDir


def getBlkGrpFilename(sessionId, runId, blkGrpId):
    """Return block group filename given session, run and blkgrp IDs.
    """
    filename = "blkGroup_r{}_p{}_{}_py.mat".format(runId, blkGrpId, sessionId)
    return filename


def getModelFilename(sessionId, runId):
    """Return trained model filename given session, run IDs.
    """
    filename = "trainedModel_r{}_{}_py.mat".format(runId, sessionId)
    return filename


def getBlkGrpKey(runId, blkGrpId):
    """This generates the key for accessing the block group data cache.
    The key is a combination of the run and block group IDs.
    """
    return'{}.{}'.format(runId, blkGrpId)


def strip_patterns(patterns, prange):
    """Modify the patterns data to restrict it to values in the range (prange)
    This is needed for example in validation where we might have patterns data for
    an entire run, but want to compare the data only for a specific block group.
    """
    patterns.raw = patterns.raw[prange, :]
    patterns.raw_sm = patterns.raw_sm[prange, :]
    patterns.raw_sm_filt = patterns.raw_sm_filt[prange, :]
    patterns.raw_sm_filt_z = patterns.raw_sm_filt_z[prange, :]
    patterns.categoryseparation = patterns.categoryseparation[0, prange]
    patterns.regressor = patterns.regressor[:, prange]
    tmp_predict = np.full((1, len(prange)), np.nan)
    if patterns.predict is not None:
        # sometime predict array will be a few short because no prediction on final trials
        if patterns.predict.shape[1] < prange[-1]:
            newrange = range(prange[0], patterns.predict.shape[1])
            tmp_predict[:, 0:len(newrange)] = patterns.predict[:, newrange]
        else:
            tmp_predict[:, 0:len(prange)] = patterns.predict[:, prange]
        mask = np.where(tmp_predict == 0)
        tmp_predict[mask] = np.nan
    patterns.predict = tmp_predict


@unique
class BlockType(Enum):
    Train = 1
    Predict = 2
