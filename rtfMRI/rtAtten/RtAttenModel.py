"""
Server-side logic for the real-time attention fMRI experiment
"""
import os
import time
import datetime
import logging
import numpy as np  # type: ignore
from enum import Enum, unique
import scipy.io as sio  # type: ignore
from sklearn.linear_model import LogisticRegression  # type: ignore
import rtfMRI.utils as utils
import rtfMRI.ValidationUtils as vutils
from ..MsgTypes import MsgEvent
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
        reply = super().StartSession(msg)
        if reply.event_type != MsgEvent.Success:
            return reply
        self.session = msg.fields.cfg
        # Set Working Directories
        if self.session.workingDir == 'cwd':
            self.dirs.workingDir = os.getcwd()
        else:
            self.dirs.workingDir = self.session.workingDir
        self.dirs.outputDataDir = os.path.join(self.dirs.workingDir, self.session.outputDataDir)
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
        reply = super().StartRun(msg)
        if reply.event_type != MsgEvent.Success:
            return reply
        run = msg.fields.cfg
        assert run.runId == self.id_fields.runId
        if run.runId > 1:
            if len(self.blkGrpCache) > 1:
                # remove any cache items older than the previous run
                self.trimCache(run.runId - 1)
        run.fileCounter = 0
        # ** Setup Output File ** #
        self.dirs.runDataDir = os.path.join(self.dirs.outputDataDir, 'run' + str(run.runId))
        if not os.path.exists(self.dirs.runDataDir):
            os.makedirs(self.dirs.runDataDir)
        now = datetime.datetime.now()
        # open and set-up output file
        run.dataFile = open(os.path.join(self.dirs.runDataDir, 'fileprocessing_py.txt'), 'w+')
        run.dataFile.write('\n*********************************************\n')
        run.dataFile.write('* rtAttenPenn v.1.0\n')
        run.dataFile.write('* Date/Time: ' + now.isoformat() + '\n')
        run.dataFile.write('* Seed: ' + str(self.session.seed) + '\n')
        run.dataFile.write('* Subject Number: ' + str(self.session.subjectNum) + '\n')
        run.dataFile.write('* Run Number: ' + str(run.runId) + '\n')
        run.dataFile.write('*********************************************\n\n')

        # print header to command window
        print('*********************************************')
        print('* rtAttenPenn v.1.0')
        print('* Date/Time: ' + now.isoformat())
        print('* Seed: ' + str(self.session.seed))
        print('* Subject Number: ' + str(self.session.subjectNum))
        print('* Run Number: ' + str(run.runId))
        print('*********************************************\n')

        # ** Start Run ** #
        # prepare for TR sequence
        run.dataFile.write('run\tblock\tTR\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n')
        print('run\tblock\tTR\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg')

        self.run = run
        return reply

    def EndRun(self, msg):
        self.run.dataFile.close()
        self.trimCache(self.id_fields.runId)
        reply = super().EndRun(msg)
        return reply

    def StartBlockGroup(self, msg):
        reply = super().StartBlockGroup(msg)
        if reply.event_type != MsgEvent.Success:
            return reply
        blkGrp = msg.fields.cfg
        run = self.run
        assert blkGrp.nTRs is not None, "missing nTRs in blockGroup"
        assert run.nVoxels is not None, "missing nVoxels in blockGroup"
        assert run.roiInds is not None, "missing roiInds in blockGroup"
        assert blkGrp.blkGrpId in (1, 2), "BlkGrpId {} not valid" % (blkGrp.blkGrpId)
        blkGrp.legacyRun1Phase2Mode = False
        if run.runId == 1 and blkGrp.blkGrpId == 2 and self.session.legacyRun1Phase2Mode:
            # Handle as legacy matlab where run1, phase2 is treated as testing
            blkGrp.legacyRun1Phase2Mode = True
        blkGrp.patterns = StructDict()
        blkGrp.patterns.raw = np.full((blkGrp.nTRs, run.nVoxels), np.nan)
        blkGrp.patterns.raw_sm = np.full((blkGrp.nTRs, run.nVoxels), np.nan)
        blkGrp.patterns.raw_sm_filt = np.full((blkGrp.nTRs, run.nVoxels), np.nan)
        blkGrp.patterns.raw_sm_filt_z = np.full((blkGrp.nTRs, run.nVoxels), np.nan)
        blkGrp.patterns.phase1Mean = np.full((1, run.nVoxels), np.nan)
        blkGrp.patterns.phase1Y = np.full((1, run.nVoxels), np.nan)
        blkGrp.patterns.phase1Std = np.full((1, run.nVoxels), np.nan)
        blkGrp.patterns.phase1Var = np.full((1, run.nVoxels), np.nan)
        blkGrp.patterns.categoryseparation = np.full((1, blkGrp.nTRs), np.nan)  # (matlab: NaN(1,nTRs))
        blkGrp.patterns.predict = np.full((1, blkGrp.nTRs), np.nan)
        blkGrp.patterns.activations = np.full((2, blkGrp.nTRs), np.nan)
        blkGrp.patterns.attCateg = np.full((1, blkGrp.nTRs), np.nan)
        blkGrp.patterns.stim = np.full((1, blkGrp.nTRs), np.nan)
        blkGrp.patterns.type = np.full((1, blkGrp.nTRs), np.nan)
        blkGrp.patterns.regressor = np.full((2, blkGrp.nTRs), np.nan)
        # blkGrp.patterns.fileAvail = np.zeros((1, blkGrp.nTRs), dtype=np.uint8)
        blkGrp.patterns.fileNum = np.full((1, blkGrp.nTRs), np.nan, dtype=np.uint16)
        self.blkGrp = blkGrp
        if self.blkGrp.type == 2 or blkGrp.legacyRun1Phase2Mode:
            # ** testing ** #
            # get blkGrp from phase 1
            prev_bg = self.getPrevBlkGrp(self.id_fields.sessionId, self.id_fields.runId, 1)
            self.blkGrp.patterns.phase1Mean[0, :] = prev_bg.patterns.phase1Mean[0, :]
            self.blkGrp.patterns.phase1Y[0, :] = prev_bg.patterns.phase1Y[0, :]
            self.blkGrp.patterns.phase1Std[0, :] = prev_bg.patterns.phase1Std[0, :]
            self.blkGrp.patterns.phase1Var[0, :] = prev_bg.patterns.phase1Var[0, :]
            self.blkGrp.combined_raw_sm = np.concatenate((prev_bg.patterns.raw_sm, blkGrp.patterns.raw_sm))
            self.blkGrp.combined_catsep = np.concatenate((prev_bg.patterns.categoryseparation,
                                                          blkGrp.patterns.categoryseparation))

            # get trained model
            if self.id_fields.runId > 1:
                self.blkGrp.trainedModel = self.getTrainedModel(self.id_fields.sessionId, self.id_fields.runId-1)

            self.run.dataFile.write('\n*********************************************\n')
            self.run.dataFile.write('beginning model testing...\n')
            print('\n*********************************************')
            print('beginning model testing...')
            # prepare for TR sequence
            self.run.dataFile.write('run\tblock\tTR\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n')
            print('run\tblock\tTR\tbltyp\tblcat\tstim\tfilenum\tloaded\tpredict\toutput\tavg')
        return reply

    def EndBlockGroup(self, msg):
        patterns = self.blkGrp.patterns
        i1, i2 = 0, self.blkGrp.nTRs
        # set validation indices
        validation_i1 = self.blkGrp.firstVol
        validation_i2 = validation_i1 + self.blkGrp.nTRs

        if self.blkGrp.type == 2 or self.blkGrp.legacyRun1Phase2Mode:  # predict
            runStd = np.nanstd(patterns.raw_sm_filt, axis=0)
            patterns.runStd = runStd.reshape(1, -1)
            # Do Validation
            if self.session.validate and self.session.replayMode:
                self.validateTestBlkGrp(validation_i1, validation_i2)

        elif self.blkGrp.type == 1:  # training
            self.run.dataFile.write('\n*********************************************\n')
            self.run.dataFile.write('beginning highpass filter/zscore...\n')
            print('\n*********************************************')
            print('beginning highpassfilter/zscore...')

            patterns.raw_sm_filt[i1:i2, :] = highPassBetweenRuns(patterns.raw_sm[i1:i2, :], self.run.TRTime, self.run.cutoff)
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
            if self.session.validate and self.session.replayMode:
                self.validateTrainBlkGrp(validation_i1, validation_i2)
            # cache the block group for predict phase and training the model
            bgKey = getBlkGrpKey(self.id_fields.runId, self.id_fields.blkGrpId)
            self.blkGrpCache[bgKey] = self.blkGrp

        else:
            reply = self.createReplyMessage(msg.id, MsgEvent.Error)
            reply.data = "Unknown blkGrp type {}".format(self.blkGrp.type)

        # save BlockGroup Data
        filename = getBlkGrpFilename(self.id_fields.sessionId,
                                     self.id_fields.runId,
                                     self.id_fields.blkGrpId)
        blkGrpFilename = os.path.join(self.dirs.outputDataDir, filename)
        sio.savemat(blkGrpFilename, self.blkGrp, appendmat=False)
        reply = super().EndBlockGroup(msg)
        return reply

    def TRData(self, msg):
        reply = super().TRData(msg)
        if reply.event_type != MsgEvent.Success:
            return reply
        TR = msg.fields.cfg
        if TR.type == 2 or (TR.type == 0 and self.blkGrp.type == 2) or\
                self.blkGrp.legacyRun1Phase2Mode:
            # Testing
            self.Predict(TR)
        elif TR.type == 1 or (TR.type == 0 and self.blkGrp.type == 1):
            # Training
            self.AccumulateTrainingData(TR)
        else:
            reply = self.createReplyMessage(msg.id, MsgEvent.Error)
            reply.data = "Unknown TR type %d", TR.type
        return reply

    def AccumulateTrainingData(self, TR):
        assert TR.trId is not None, "missing TR.trId"
        # increase the count of TR pulses
        self.run.fileCounter = self.run.fileCounter + 1  # so fileCounter begins at firstVolPhase1

        patterns = self.blkGrp.patterns
        patterns.attCateg[0, TR.trId] = TR.attCateg
        patterns.stim[0, TR.trId] = TR.stim
        patterns.type[0, TR.trId] = TR.type
        patterns.regressor[:, TR.trId] = TR.regressor[:]
        patterns.raw[TR.trId, :] = TR.data
        patterns.raw_sm[TR.trId, :] =\
            smooth(patterns.raw[TR.trId, :], self.run.roiDims, self.run.roiInds, self.run.FWHM)

        # print TR results
        output_str = '{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}\t{:d}\t{:.3f}\t{:.3f}'.format(
            self.id_fields.runId, self.id_fields.blockId, TR.trId, TR.type,
            TR.attCateg, TR.stim, TR.vol, 1, np.nan, np.nan)
        self.run.dataFile.write(output_str + '\n')
        print(output_str)
        return

    def Predict(self, TR):
        assert TR.trId is not None, "missing TR.trId"
        patterns = self.blkGrp.patterns
        combined_raw_sm = self.blkGrp.combined_raw_sm
        combined_TRid = self.blkGrp.firstVol + TR.trId
        patterns.attCateg[0, TR.trId] = TR.attCateg
        patterns.stim[0, TR.trId] = TR.stim
        patterns.type[0, TR.trId] = TR.type
        patterns.regressor[:, TR.trId] = TR.regressor[:]
        patterns.fileNum[0, TR.trId] = TR.vol + self.run.disdaqs // self.run.TRTime
        patterns.raw[TR.trId, :] = TR.data
        patterns.raw_sm[TR.trId, :] = \
            smooth(patterns.raw[TR.trId, :], self.run.roiDims, self.run.roiInds, self.run.FWHM)
        combined_raw_sm[combined_TRid] = patterns.raw_sm[TR.trId]
        patterns.raw_sm_filt[TR.trId, :] = \
            highPassRealTime(combined_raw_sm[0:combined_TRid+1, :], self.run.TRTime, self.run.cutoff)
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

            classOutput = patterns.categoryseparation[0, TR.trId]
            filename = os.path.join(self.dirs.runDataDir, 'vol_' + str(patterns.fileNum[0, TR.trId]) + '_py')
            with open(filename, 'w+') as volFile:
                volFile.write(str(classOutput))
        else:
            patterns.categoryseparation[0, TR.trId] = np.nan

        # print TR results
        categorysep_mean = np.nan
        # TODO - do we need to handle 0:TR here to include phase 1 data?
        if not np.all(np.isnan(patterns.categoryseparation[0, 0:TR.trId+1])):
            categorysep_mean = np.nanmean(patterns.categoryseparation[0, 0:TR.trId+1])
        output_str = '{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}\t{:d}\t{:.1f}\t{:.3f}\t{:.3f}'.format(
            self.id_fields.runId, self.id_fields.blockId, TR.trId, TR.type, TR.attCateg, TR.stim,
            patterns.fileNum[0, TR.trId], 1, patterns.predict[0, TR.trId],
            patterns.categoryseparation[0, TR.trId], categorysep_mean)
        self.run.dataFile.write(output_str + '\n')
        print(output_str)
        # todo - reply with category separation
        return

    def TrainModel(self, msg):
        trainStart = time.time()  # start timing
        # print training results
        self.run.dataFile.write('\n*********************************************\n')
        self.run.dataFile.write('beginning model training...\n')
        print('\n*********************************************')
        print('beginning model training...')

        # load data to train model
        trainCfg = msg.fields.cfg
        bgRef1 = StructDict(trainCfg.blkGrpRefs[0])
        bgRef2 = StructDict(trainCfg.blkGrpRefs[1])
        bg1 = self.getPrevBlkGrp(self.id_fields.sessionId, bgRef1.run, bgRef1.phase)
        bg2 = self.getPrevBlkGrp(self.id_fields.sessionId, bgRef2.run, bgRef2.phase)

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
        self.run.dataFile.write(outStr + '\n')
        print(outStr)
        if newTrainedModel.biases is not None:
            outStr = 'model biases: \t{:.3f}\t{:.3f}'.format(
                newTrainedModel.biases[0, 0], newTrainedModel.biases[0, 1])
            self.run.dataFile.write(outStr + '\n')
            print(outStr)

        # cache the trained model
        self.modelCache[self.id_fields.runId] = newTrainedModel

        if self.session.validate:
            self.validateModel(newTrainedModel)

        # write trained model to a file
        filename = getModelFilename(self.id_fields.sessionId, self.id_fields.runId)
        trainedModel_fn = os.path.join(self.dirs.outputDataDir, filename)
        sio.savemat(trainedModel_fn, newTrainedModel, appendmat=False)

        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def getPrevBlkGrp(self, sessionId, runId, blkGrpId):
        bgKey = getBlkGrpKey(runId, blkGrpId)
        prev_bg = self.blkGrpCache.get(bgKey, None)
        if prev_bg is None:
            # load it from file
            logging.info("blkGrpCache miss on key %s", bgKey)
            fname = os.path.join(self.dirs.outputDataDir, getBlkGrpFilename(sessionId, runId, blkGrpId))
            prev_bg = utils.loadMatFile(fname)
            assert prev_bg is not None, "unable to load blkGrp %s" % (fname)
            if sessionId == self.id_fields.sessionId:
                self.blkGrpCache[bgKey] = prev_bg
        return prev_bg

    def getTrainedModel(self, sessionId, runId):
        model = self.modelCache.get(runId, None)
        if model is None:
            # load it from file
            logging.info("modelCache miss on key %d", runId)
            fname = os.path.join(self.dirs.outputDataDir, getModelFilename(sessionId, runId))
            model = utils.loadMatFile(fname)
            assert model is not None, "unable to load model %s" % (fname)
        if sessionId == self.id_fields.sessionId:
            self.modelCache[runId] = model
        return model

    def trimCache(self, oldestRunId):
        '''Remove any cached elements older than oldestRunId'''
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

    def validateTrainBlkGrp(self, target_i1, target_i2):
        patterns = MatlabStructDict(self.blkGrp.patterns)
        # load the replay file for target outcomes
        target_patternsdata = utils.loadMatFile(self.run.replayFile)
        target_patterns = target_patternsdata.patterns
        strip_patterns(target_patterns, range(target_i1, target_i2))
        cmp_fields = ['raw', 'raw_sm', 'raw_sm_filt', 'raw_sm_filt_z',
                      'phase1Mean', 'phase1Y', 'phase1Std', 'phase1Var']
        res = vutils.compareMatStructs(patterns, target_patterns, field_list=cmp_fields)
        res_means = {key: value['mean'] for key, value in res.items()}
        print("Validation Means: ", res_means)
        # calculate the pierson correlation for raw_sm_filt_z
        pearson_mean = vutils.pearsons_mean_corr(patterns.raw_sm_filt_z, target_patterns.raw_sm_filt_z)
        print("Phase1 sm_filt_z mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            # assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)
            logging.warn("Pearson mean for raw_sm_filt_z low, %f", pearson_mean)

    def validateTestBlkGrp(self, target_i1, target_i2):
        patterns = MatlabStructDict(self.blkGrp.patterns)
        # load the replay file for target outcomes
        target_patternsdata = utils.loadMatFile(self.run.replayFile)
        target_patterns = target_patternsdata.patterns
        strip_patterns(target_patterns, range(target_i1, target_i2))
        cmp_fields = ['raw', 'raw_sm', 'raw_sm_filt', 'raw_sm_filt_z',
                      'phase1Mean', 'phase1Y', 'phase1Std', 'phase1Var',
                      'categoryseparation']
        res = vutils.compareMatStructs(patterns, target_patterns, field_list=cmp_fields)
        res_means = {key: value['mean'] for key, value in res.items()}
        print("Validation Means: ", res_means)
        # Make sure the predict array values are identical
        # Predict values are (1, 2) in matlab, (0, 1) in python because it
        # Check if we need to convert from matlab to python values
        if (not np.all(np.isnan(target_patterns.predict))) and\
                np.nanmax(target_patterns.predict) > 1:
            # convert target.predict to zero based indexing
            target_patterns.predict = target_patterns.predict-1
        predictions_match = np.allclose(target_patterns.predict, patterns.predict, rtol=0, atol=0, equal_nan=True)
        if predictions_match:
            print("All predictions match: " + str(predictions_match))
        else:
            mask = ~np.isnan(target_patterns.predict)
            miss_count = np.sum(patterns.predict[0, mask] != target_patterns.predict[mask])
            print("WARNING: predictions differ in {} TRs".format(miss_count))
        # calculate the pierson correlation for raw_sm_filt_z
        pearson_mean = vutils.pearsons_mean_corr(patterns.raw_sm_filt_z, target_patterns.raw_sm_filt_z)
        print("Phase2 sm_filt_z mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            # assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)
            logging.warn("Pearson mean for raw_sm_filt_z low, %f", pearson_mean)

    def validateModel(self, newTrainedModel):
        target_model = utils.loadMatFile(self.run.validationModel)
        cmp_fields = ['trainLabels', 'weights', 'biases', 'trainPats']
        res = vutils.compareMatStructs(newTrainedModel, target_model, field_list=cmp_fields)
        res_means = {key: value['mean'] for key, value in res.items()}
        print("TrainModel Validation Means: ", res_means)
        # calculate the pierson correlation for trainPats
        pearson_mean = vutils.pearsons_mean_corr(newTrainedModel.trainPats, target_model.trainPats)
        print("trainPats mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            # assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)
            logging.warn("Pearson mean for trainPats low, %f", pearson_mean)
        # calculate the pierson correlation for model weights
        pearson_mean = vutils.pearsons_mean_corr(newTrainedModel.weights, target_model.weights)
        print("trainedWeights mean pearsons correlation {}".format(pearson_mean))
        if pearson_mean < .995:
            # assert pearson_mean > .99, "Pearsons mean {} too low".format(pearson_mean)
            logging.warn("Pearson mean for trainWeights low, %f", pearson_mean)


def getBlkGrpFilename(sessionId, runId, blkGrpId):
    filename = "blkGroup_{}_r{}_p{}_py.mat".format(sessionId, runId, blkGrpId)
    return filename


def getModelFilename(sessionId, runId):
    filename = "trainedModel_{}_r{}_py.mat".format(sessionId, runId)
    return filename


def getBlkGrpKey(runId, blkGrpId):
    return'{}.{}'.format(runId, blkGrpId)


def strip_patterns(patterns, prange):
    patterns.raw = patterns.raw[prange, :]
    patterns.raw_sm = patterns.raw_sm[prange, :]
    patterns.raw_sm_filt = patterns.raw_sm_filt[prange, :]
    patterns.raw_sm_filt_z = patterns.raw_sm_filt_z[prange, :]
    patterns.categoryseparation = patterns.categoryseparation[0, prange]
    patterns.predict = patterns.predict[0, prange]


@unique
class BlockType(Enum):
    Train = 1
    Predict = 2
