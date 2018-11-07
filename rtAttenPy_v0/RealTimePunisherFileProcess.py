#!/usr/bin/env python3

import os
import datetime, time
import numpy as np
from rtAttenPy_v0 import utils
import rtAttenPy_v0
import scipy.io as sio
from sklearn.linear_model import LogisticRegression

# import matlab.engine
# eng = matlab.engine.start_matlab()

def realTimePunisherProcess(subjectNum, runNum, ValidationFile=None):
    ## Boilerplate ##
    # TODO - set random Seed
    seed = time.time()

    ## Load or Initialize Real-Time Data
    if runNum > 1:
        rtfeedback = 1
    else:
        rtfeedback = 0

    workingDir = os.getcwd() # os.path.dirname(os.getcwd())
    inputDataDir = os.path.join(workingDir, 'data/input')
    outputDataDir = os.path.join(workingDir, 'data/output')
    runDataDir = os.path.join(workingDir, 'data/output/run' + str(runNum))
    if not os.path.exists(runDataDir):
        os.makedirs(runDataDir)

    # set filenames
    patternsdesign_fname = utils.findNewestFile(inputDataDir, 'patternsdesign_'+str(runNum)+'*.mat')
    curr_patterns_fname = utils.findNewestFile(outputDataDir, 'patternsdata_'+str(runNum)+'*.mat')
    prev_patterns_fname = utils.findNewestFile(outputDataDir, 'patternsdata_'+str(runNum-1)+'*.mat')
    model_fname = utils.findNewestFile(outputDataDir, 'trainedModel_'+str(runNum-1)+'*.mat')
    # if ValidationFile is set then set the filenames based on those parameters
    if ValidationFile is not None:
        mean_limit = .0075  # within 3/4 of a percent error
        # i.e. use data/output/trace_params_run2_20171214T173415.mat
        assert os.path.isfile(ValidationFile), 'Failed to find file {}'.format(ValidationFile)
        test_params = utils.loadMatFile(ValidationFile)
        patternsdesign_fname = test_params.patternsdesign_filename[0]
        curr_patterns_fname = test_params.curr_pdata_filename[0]
        if test_params.runNum > 1:
            prev_patterns_fname = test_params.prev_pdata_filename[0]
            model_fname = test_params.model_filename[0]
        # load the result files that we will compare to
        target_patterns_fn = test_params.result_patterns_filename
        target_model_fn = test_params.result_model_filename
        target_patterns = utils.loadMatFile(target_patterns_fn[0])
        target_model = utils.loadMatFile(target_model_fn[0])
        assert runNum == test_params.runNum, "trace file runNum doesn't agree"
        assert subjectNum == test_params.subjectNum, "trace file subjectNum doesn't agree"
        assert rtfeedback == test_params.rtfeedback, "trace file rtfeedback doesn't agree"

    patterns = utils.loadMatFile(patternsdesign_fname)

    #load previous patterns
    if runNum > 1:
        oldpats = utils.loadMatFile(prev_patterns_fname.strip())
        trainedModel = utils.loadMatFile(model_fname.strip())

    # load current patterns data
    p = utils.loadMatFile(curr_patterns_fname.strip())

    ## Experimental Parameters ##
    #scanning parameters
    imgmat = 64 # the fMRI image matrix size
    temp = utils.loadMatFile(inputDataDir+'/mask_'+str(subjectNum)+'.mat')
    # Region of Interes (ROI) is an array with 1s indicating the voxels of interest
    roi = temp.mask
    assert type(roi) == np.ndarray
    roiDims = roi.shape
    # find indices of non-zero elements in roi in row-major order but sorted by col-major order
    roiInds = utils.find(roi)
    # assert that the number of non-zero entries in mask equals the supplied data elements in one image
    assert roiInds.size == p.raw[0].size

    # pre-processing parameters
    FWHM = 5
    cutoff = 112
    # timeOut = TR/2+.25;

    zscoreNew = 1
    useHistory = 1
    firstBlockTRs = 64 # total number of TRs to take for standard deviation of last run

    ## Block Sequence ##
    nVoxels = p.raw.shape[1]

    # Matlab: firstVolPhase1 = find(patterns.block==1,1,'first'); %#ok<NODEF>
    firstVolPhase1 = np.min(np.where(patterns.block.squeeze() == 1))  # find first one
    # Matlab: lastVolPhase1 = find(patterns.block==nBlocksPerPhase,1,'last');
    lastVolPhase1 = np.max(np.where(patterns.block.squeeze()==patterns.nBlocksPerPhase)) # find last one
    assert lastVolPhase1 == patterns.lastVolPhase1-1, "assert calulated lastVolPhase1 is same as loaded from patternsdesign {} {}".format(lastVolPhase1, patterns.lastVolPhase1)
    nVolsPhase1 = lastVolPhase1 - firstVolPhase1 + 1
    # Matlab: WAIT first vol are with any patterns in the block and then lastvolphase2
    # is SHIFTED??!?!? or no???
    # Matlab: lastVolPhase2 = find(patterns.type~=0,1,'last');
    firstVolPhase2 = np.min(np.where(patterns.block.squeeze() == (patterns.nBlocksPerPhase+1)))
    assert firstVolPhase2 == patterns.firstVolPhase2-1, "assert calulated firstVolPhase2 is same as load from patternsdesign {} {}".format(firstVolPhase2, patterns.firstVolPhase2)
    lastVolPhase2 = np.max(np.where(patterns.type.squeeze() != 0))
    nVolsPhase2 = lastVolPhase2 - firstVolPhase2 + 1
    nVols = patterns.block.shape[1]            # (matlab: size(patterns.block,2))
    patterns.patterns.fileAvail = np.zeros((1,patterns.nTRs), dtype=np.uint8) # (matlab: zeros(1,nTRs))
    patterns.patterns.fileNum = np.full((1,patterns.nTRs), np.nan, dtype=np.uint16) # (matlab: NaN(1,nTRs))
    patterns.patterns.newFile = [np.nan] * patterns.nTRs  # emplty list (matlab: cell(1,nTRs))
    patterns.patterns.timeRead = [np.nan] * patterns.nTRs  # emplty list (matlab: cell(1,nTRs))
    patterns.patterns.fileload = np.full((1,patterns.nTRs), np.nan) # (matlab: NaN(1,nTRs))
    patterns.patterns.raw = p.patterns.raw
    patterns.patterns.raw_sm = np.full((patterns.nTRs,roiInds.size), np.nan)  # (matlab: nan(nTRs,numel(roiInds)))
    patterns.patterns.raw_sm_filt = np.full((patterns.nTRs,roiInds.size), np.nan)  # (matlab: nan(nTRs,numel(roiInds)))
    patterns.patterns.raw_sm_filt_z = np.full((patterns.nTRs,roiInds.size), np.nan)  # (matlab: nan(nTRs,numel(roiInds)))
    patterns.patterns.phase1Mean = np.full((1,nVoxels), np.nan)
    patterns.patterns.phase1Y = np.full((1,nVoxels), np.nan)
    patterns.patterns.phase1Std = np.full((1,nVoxels), np.nan)
    patterns.patterns.phase1Var = np.full((1,nVoxels), np.nan)
    patterns.patterns.categoryseparation = np.full((1,patterns.nTRs), np.nan)  # (matlab: NaN(1,nTRs))
    patterns.patterns.predict = np.full((1,nVols), np.nan)
    patterns.patterns.activations = np.full((2,nVols), np.nan)
    # Matlab: patterns.firstTestTR = find(patterns.regressor(1,:)+patterns.regressor(2,:),1,'first')
    sumRegressor = patterns.regressor[0,:] + patterns.regressor[1,:]
    patterns.patterns.firstTestTR = np.min(np.where(sumRegressor == 1)) #(because took out first 10)

    ## Output Files Setup ##
    now = datetime.datetime.now()
    # open and set-up output file
    dataFile = open(os.path.join(runDataDir,'fileprocessing_py0.txt'),'w+')
    dataFile.write('\n*********************************************\n')
    dataFile.write('* rtAttenPenn v.1.0\n')
    dataFile.write('* Date/Time: ' + now.isoformat() + '\n')
    dataFile.write('* Seed: ' + str(seed) + '\n')
    dataFile.write('* Subject Number: ' + str(subjectNum) + '\n')
    dataFile.write('* Run Number: ' + str(runNum) + '\n')
    dataFile.write('*********************************************\n\n')

    # print header to command window
    print('*********************************************')
    print('* rtAttenPenn v.1.0')
    print('* Date/Time: ' + now.isoformat())
    print('* Seed: ' + str(seed))
    print('* Subject Number: ' + str(subjectNum))
    print('* Run Number: ' + str(runNum))
    print('*********************************************\n')

    ## Start Experiment ##
    # prepare for trial sequence
    dataFile.write('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n')
    print('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg')

    ## acquiring files ##

    fileCounter = firstVolPhase1 # file number = # of TR pulses
    for iTrialPhase1 in range(firstVolPhase2):
        # increase the count of TR pulses
        fileCounter = fileCounter+1 # so fileCounter begins at firstVolPhase1

        # smooth files
        patterns.raw_sm[iTrialPhase1, :] = rtAttenPy_v0.smooth(patterns.raw[iTrialPhase1, :], roiDims, roiInds, FWHM)

        # print trial results
        output_str = '{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}\t{:d}\t{:.3f}\t{:.3f}'.format(\
            runNum, patterns.block[0][iTrialPhase1], iTrialPhase1, patterns.type[0][iTrialPhase1], \
            patterns.attCateg[0][iTrialPhase1], patterns.stim[0][iTrialPhase1], \
            patterns.fileNum[0][iTrialPhase1], patterns.fileAvail[0][iTrialPhase1], np.nan, np.nan)
        dataFile.write(output_str + '\n')
        print(output_str)

    # end Phase1 loop - fileCounter will be at 115 here
    assert fileCounter == 115
    if ValidationFile:
        assert utils.areArraysClose(patterns.raw_sm, target_patterns.raw_sm, mean_limit), "compare raw_sm failed"

    # quick highpass filter!
    dataFile.write('\n*********************************************\n')
    dataFile.write('beginning highpass filter/zscore...\n')
    print('\n*********************************************')
    print('beginning highpassfilter/zscore...')
    i1 = 0
    i2 = firstVolPhase2
    patterns.raw_sm_filt[i1:i2, :] = highPassBetweenRuns(patterns.raw_sm[i1:i2,:], patterns.TR, cutoff)
    patterns.phase1Mean[0, :] = np.mean(patterns.raw_sm_filt[i1:i2,:], axis=0)
    patterns.phase1Y[0,:] = np.mean(patterns.raw_sm_filt[i1:i2,:]**2, axis=0)
    patterns.phase1Std[0,:] = np.std(patterns.raw_sm_filt[i1:i2,:], axis=0)
    patterns.phase1Var[0,:] = patterns.phase1Std[0,:]**2
    tileSize = [patterns.raw_sm_filt[i1:i2,:].shape[0], 1]
    patterns.raw_sm_filt_z[i1:i2,:] = np.divide((patterns.raw_sm_filt[i1:i2,:] - np.tile(patterns.phase1Mean,tileSize)), np.tile(patterns.phase1Std, tileSize))

    if ValidationFile:
        res = utils.compareMatStructs(patterns, target_patterns, ['raw_sm', 'raw_sm_filt', 'raw_sm_filt_z', 'phase1Mean', 'phase1Y', 'phase1Std', 'phase1Var'])
        res_means = {key:value['mean'] for key, value in res.items()}
        print("Validation Means: ", res_means)
        # calculate the pierson correlation for raw_sm_filt_z
        pearson_mean = utils.pearsons_mean_corr(patterns.raw_sm_filt_z[i1:i2,:], target_patterns.raw_sm_filt_z[i1:i2,:])
        print("Phase1 sm_filt_z mean pearsons correlation {}".format(pearson_mean))
        assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)

    ## testing ##
    dataFile.write('\n*********************************************\n')
    dataFile.write('beginning model testing...\n')
    print('\n*********************************************')
    print('beginning model testing...')

    # prepare for trial sequence
    dataFile.write('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n')
    print('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\tpredict\toutput\tavg')

    for iTrialPhase2 in range(firstVolPhase2, nVols):
        fileCounter = fileCounter+1

        patterns.fileNum[0, iTrialPhase2] = fileCounter+patterns.disdaqs//patterns.TR # disdaqs/TR is num TRs pause before each phase

        # smooth
        patterns.raw_sm[iTrialPhase2,:] = rtAttenPy_v0.smooth(patterns.raw[iTrialPhase2,:], roiDims, roiInds, FWHM)

        # detrend
        patterns.raw_sm_filt[iTrialPhase2,:] = highPassRealTime(patterns.raw_sm[0:iTrialPhase2+1,:], patterns.TR, cutoff)

        # only update if the latest file wasn't nan
        #if patterns.fileload(iTrialPhase2)

        patterns.raw_sm_filt_z[iTrialPhase2,:] = (patterns.raw_sm_filt[iTrialPhase2,:] - patterns.phase1Mean[0,:]) / patterns.phase1Std[0,:]

        if rtfeedback:
            if np.any(patterns.regressor[:,iTrialPhase2]):
                patterns.predict[0, iTrialPhase2],_,_,patterns.activations[:,iTrialPhase2] = rtAttenPy_v0.Test_L2_RLR_realtime(trainedModel,patterns.raw_sm_filt_z[iTrialPhase2,:],patterns.regressor[:,iTrialPhase2])  # ok<NODEF>
                # determine whether expecting face or scene for this trial
                categ = np.flatnonzero(patterns.regressor[:,iTrialPhase2])
                # the other category will be categ+1 mod 2 since there are only two category types
                otherCateg = (categ + 1) %2
                patterns.categoryseparation[0,iTrialPhase2] = patterns.activations[categ,iTrialPhase2]-patterns.activations[otherCateg,iTrialPhase2]

                classOutput = patterns.categoryseparation[0,iTrialPhase2] #ok<NASGU>
                with open(os.path.join(runDataDir, 'vol_' + str(patterns.fileNum[0, iTrialPhase2]) + '_py0'), 'w+') as volFile:
                    volFile.write(str(classOutput))
            else:
                patterns.categoryseparation[0,iTrialPhase2] = np.nan

                classOutput = patterns.categoryseparation[0,iTrialPhase2] #ok<NASGU>
                with open(os.path.join(runDataDir, 'vol_' + str(patterns.fileNum[0, iTrialPhase2]) + '_py0'), 'w+') as volFile:
                    volFile.write(str(classOutput))
        else:
            patterns.categoryseparation[0,iTrialPhase2] = np.nan

        # print trial results
        categorysep_mean = np.nan
        if not np.all(np.isnan(patterns.categoryseparation[0,firstVolPhase2:iTrialPhase2+1])):
            categorysep_mean = np.nanmean(patterns.categoryseparation[0,firstVolPhase2:iTrialPhase2+1])
        output_str = '{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}\t{:d}\t{:.1f}\t{:.3f}\t{:.3f}'.format(\
            runNum, patterns.block[0][iTrialPhase2], iTrialPhase2, patterns.type[0][iTrialPhase2], \
            patterns.attCateg[0][iTrialPhase2], patterns.stim[0][iTrialPhase2], \
            patterns.fileNum[0][iTrialPhase2], patterns.fileAvail[0][iTrialPhase2], \
            patterns.predict[0][iTrialPhase2], patterns.categoryseparation[0][iTrialPhase2], \
            categorysep_mean)
        dataFile.write(output_str + '\n')
        print(output_str)

    # end Phase 2 loop

    runStd = np.nanstd(patterns.raw_sm_filt, axis=0) #std dev across all volumes per voxel
    patterns.runStd = runStd.reshape(1,-1)

    if ValidationFile:
        res = utils.compareMatStructs(patterns, target_patterns, ['raw_sm', 'raw_sm_filt', 'raw_sm_filt_z', 'categoryseparation', 'runStd'])
        res_means = {key:value['mean'] for key, value in res.items()}
        print("Validation Means: ", res_means)
        # Make sure the predict array values are identical
        target_predictions = target_patterns.predict-1 # matlab is ones based and python zeroes based
        predictions_match = np.allclose(target_predictions, patterns.predict, rtol=0, atol=0, equal_nan=True)
        if predictions_match:
            print("All predictions match: " + str(predictions_match))
        else:
            mask = ~np.isnan(target_predictions)
            miss_count = np.sum(patterns.predict[mask] != target_predictions[mask])
            print("WARNING: predictions differ in {} TRs".format(miss_count))
        # calculate the pierson correlation for raw_sm_filt_z
        pearson_mean = utils.pearsons_mean_corr(patterns.raw_sm_filt_z[firstVolPhase2:nVols, :], target_patterns.raw_sm_filt_z[firstVolPhase2:nVols, :])
        print("Phase2 sm_filt_z mean pearsons correlation {}".format(pearson_mean))
        assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)


    ## training ##
    trainStart = time.time()  #start timing

    # print training results
    dataFile.write('\n*********************************************\n')
    dataFile.write('beginning model training...\n')
    print('\n*********************************************')
    print('beginning model training...')

    # model training
    # we have to specify which TR's are correct for first 4 blocks and second
    # four blocks
    # last volPhase1 and first volPhase1/2 are NOT shifted though!!
    i_phase1 = range(0, lastVolPhase1+1+2)   # 1:lastVolPhase1+2;
    i_phase2 = range(firstVolPhase2, nVols)  # firstVolPhase2:nVols;
    #any(patterns.regressor(:,i_phase2),1)
    if runNum == 1:
        # for the first run, we're going to train on first and second part of
        # run 1
        trainIdx1 = utils.find(np.any(patterns.regressor[:,i_phase1], axis=0))
        trainLabels1 = np.transpose(patterns.regressor[:,trainIdx1])  # find the labels of those indices
        trainPats1 = patterns.raw_sm_filt_z[trainIdx1,:]  # retrieve the patterns of those indices

        trainIdx2 = utils.find(np.any(patterns.regressor[:,i_phase2], axis=0))
        trainLabels2 = np.transpose(patterns.regressor[:,(firstVolPhase2)+trainIdx2])  # find the labels of those indices
        trainPats2 = patterns.raw_sm_filt_z[(firstVolPhase2)+trainIdx2,:]
    elif runNum == 2:
        # take last run from run 1 and first run from run 2
        trainIdx1 = utils.find(np.any(oldpats.patterns.regressor[:,i_phase2], axis=0))
        trainLabels1 = np.transpose(oldpats.patterns.regressor[:,(firstVolPhase2)+trainIdx1])  # find the labels of those indices
        trainPats1 = oldpats.patterns.raw_sm_filt_z[(firstVolPhase2)+trainIdx1,:]

        trainIdx2 = utils.find(np.any(patterns.regressor[:,i_phase1], axis=0))
        trainLabels2 = np.transpose(patterns.regressor[:,trainIdx2])   # find the labels of those indices
        trainPats2 = patterns.raw_sm_filt_z[trainIdx2,:]   # retrieve the patterns of those indices
    else:
        # take previous 2 first parts
        trainIdx1 = utils.find(np.any(oldpats.patterns.regressor[:,i_phase1], axis=0))
        trainLabels1 = np.transpose(oldpats.patterns.regressor[:,trainIdx1])   # find the labels of those indices
        trainPats1 = oldpats.patterns.raw_sm_filt_z[trainIdx1,:]  # retrieve the patterns of those indices

        trainIdx2 = utils.find(np.any(patterns.regressor[:,i_phase1], axis=0))
        trainLabels2 = np.transpose(patterns.regressor[:,trainIdx2])  # find the labels of those indices
        trainPats2 = patterns.raw_sm_filt_z[trainIdx2,:]  # retrieve the patterns of those indices

    trainPats = np.concatenate((trainPats1,trainPats2))
    trainLabels = np.concatenate((trainLabels1,trainLabels2))

    # train the model
    # sklearn LogisticRegression takes on set of labels and returns one set of weights.
    # The version implemented in Matlab can take multple sets of labels and return multiple wieghts.
    # To reproduct that behavior here, we will use a LogisticRegression instance for each set of lables (2 in this case)
    lrc1 = LogisticRegression(solver='sag')
    lrc2 = LogisticRegression(solver='sag')
    lrc1.fit(trainPats, trainLabels[:, 0])
    lrc2.fit(trainPats, trainLabels[:, 1])
    newTrainedModel = utils.MatlabStructDict({}, 'trainedModel')
    newTrainedModel.trainedModel = utils.StructDict({})
    newTrainedModel.trainedModel.weights = np.concatenate((lrc1.coef_.T, lrc2.coef_.T), axis=1)
    newTrainedModel.trainedModel.biases = np.concatenate((lrc1.intercept_, lrc2.intercept_)).reshape(1, 2)
    newTrainedModel.trainPats = trainPats
    newTrainedModel.trainLabels = trainLabels

    if ValidationFile:
        res = utils.compareMatStructs(newTrainedModel, target_model, field_list=['trainLabels', 'weights', 'biases', 'trainPats'])
        res_means = {key:value['mean'] for key, value in res.items()}
        print("TrainModel Validation Means: ", res_means)
        # calculate the pierson correlation for trainPats
        pearson_mean = utils.pearsons_mean_corr(trainPats, target_model.trainPats)
        print("trainPats mean pearsons correlation {}".format(pearson_mean))
        assert pearson_mean > .995, "Pearsons mean {} too low".format(pearson_mean)
        # calculate the pierson correlation for model weights
        pearson_mean = utils.pearsons_mean_corr(newTrainedModel.weights, target_model.weights)
        print("trainedWeights mean pearsons correlation {}".format(pearson_mean))
        assert pearson_mean > .99, "Pearsons mean {} too low".format(pearson_mean)

    trainEnd = time.time()  # end timing
    trainingOnlyTime = trainEnd - trainStart

    # print training timing and results
    dataFile.write('model training time: \t{:.3f}\n'.format(trainingOnlyTime))
    print('model training time: \t{:.3f}'.format(trainingOnlyTime))
    if newTrainedModel.biases is not None:
        dataFile.write('model biases: \t{:.3f}\t{:.3f}\n'.format(newTrainedModel.biases[0,0],newTrainedModel.biases[0,1]))
        print('model biases: \t{:.3f}\t{:.3f}'.format(newTrainedModel.biases[0,0],newTrainedModel.biases[0,1]))

    ##

    datestr = time.strftime("%Y%m%dT%H%M%S", time.localtime())
    output_patterns_fn = os.path.join(outputDataDir, 'patternsdata_'+ str(runNum) + '_' + datestr + '_py0.mat')
    output_trainedModel_fn = os.path.join(outputDataDir, 'trainedModel_' + str(runNum) + '_' + datestr + '_py0.mat')
    sio.savemat(output_patterns_fn, patterns, appendmat=False)
    sio.savemat(output_trainedModel_fn, newTrainedModel, appendmat=False)

    # clean up and go home
    dataFile.close()
    # end


def highPassBetweenRuns(A_matrix, TR, cutoff):
    return np.transpose(rtAttenPy_v0.highpass(np.transpose(A_matrix), cutoff/(2*TR), False))

def highPassRealTime(A_matrix, TR, cutoff):
    full_matrix = np.transpose(rtAttenPy_v0.highpass(np.transpose(A_matrix), cutoff/(2*TR), True))
    return full_matrix[-1,:]
