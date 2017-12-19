#!/usr/bin/env python3

import os
import datetime, time
import scipy.io as sio
import numpy as np
from rtAttenPy import utils
import rtAttenPy
import scipy.stats as sstats

# import matlab.engine
# eng = matlab.engine.start_matlab()

def realTimePunisherProcess(TestUsing=None):
    ## Boilerplate ##
    # TODO - set random Seed
    seed = time.time()

    ## Load or Initialize Real-Time Data
    runNum = 2
    subjectNum = 3
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
    # if TestUsing is set then set the filenames based on those parameters
    if TestUsing is not None:
        mean_limit = .0075  # within 3/4 of a percent error
        # i.e. use data/output/trace_params_run2_20171214T173415.mat
        assert os.path.isfile(TestUsing), 'Failed to find file {}'.format(TestUsing)
        test_params = sio.loadmat(TestUsing)
        test_params = utils.MatlabStructDict(test_params, 'params')
        patternsdesign_fname = test_params.patternsdesign_filename[0]
        curr_patterns_fname = test_params.cur_patterns_filename[0]
        prev_patterns_fname = test_params.prev_patterns_filename[0]
        model_fname = test_params.model_filename[0]
        runNum = test_params.runNum
        subjectNum = test_params.subjectNum
        rtfeedback = test_params.rtfeedback
        # load the result files that we will compare to
        target_patterns_fn = test_params.params.result_patterns_filename
        target_model_fn = test_params.result_model_filename
        target_patterns0 = sio.loadmat(target_patterns_fn[0])
        target_patterns = utils.MatlabStructDict(target_patterns0, 'patterns')
        target_model0 = sio.loadmat(target_model_fn[0])
        target_model = utils.MatlabStructDict(target_model0, 'trainedModel')

    patterns0 = sio.loadmat(patternsdesign_fname)
    patterns = utils.MatlabStructDict(patterns0, 'patterns')

    ## TODO - recreate patternsdesign for python case, for now fix up a little

    #load previous patterns
    if runNum > 1:
        oldpats0 = sio.loadmat(prev_patterns_fname.strip())
        oldpats = utils.MatlabStructDict(oldpats0, 'patterns')
        trainedModel0 = sio.loadmat(model_fname.strip())
        trainedModel = utils.MatlabStructDict(trainedModel0, 'trainedModel')

    # load current patterns data
    p0 = sio.loadmat(curr_patterns_fname.strip())
    p = utils.MatlabStructDict(p0, 'patterns')

    ## Experimental Parameters ##
    #scanning parameters
    imgmat = 64 # the fMRI image matrix size
    temp0 = sio.loadmat(inputDataDir+'/mask_'+str(subjectNum)+'.mat')
    temp = utils.MatlabStructDict(temp0)
    # Region of Interes (ROI) is an array with 1s indicating the voxels of interest
    roi = temp.mask
    assert type(roi) == np.ndarray
    roiDims = roi.shape
    # find indices of non-zero elements in roi
    inds = np.nonzero(roi)
    # We need to first convert to Matlab column order raveled indicies in order to
    #  sort the indicies in that order (the order the data appears in the p.raw matrix)
    indsMatRavel = np.ravel_multi_index(inds, roiDims, order='F')
    indsMatRavel.sort()
    # convert back to python raveled indices
    indsMat = np.unravel_index(indsMatRavel, roiDims, order='F')
    roiInds = np.ravel_multi_index(indsMat, roiDims, order='C')
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
    nVolsPhase1 = lastVolPhase1 - firstVolPhase1 + 1
    # Matlab: WAIT first vol are with any patterns in the block and then lastvolphase2
    # is SHIFTED??!?!? or no???
    # Matlab: lastVolPhase2 = find(patterns.type~=0,1,'last');
    lastVolPhase2 = np.max(np.where(patterns.type.squeeze() != 0))
    nVolsPhase2 = lastVolPhase2 - patterns.firstVolPhase2 + 1
    nVols = patterns.block.shape[1]            # (matlab: size(patterns.block,2))
    patterns.patterns.fileAvail = np.zeros((1,patterns.nTRs), dtype=np.uint8) # (matlab: zeros(1,nTRs))
    patterns.patterns.fileNum = np.full((1,patterns.nTRs), np.nan) # (matlab: NaN(1,nTRs))
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
    # Matlab: patterns.firstTestTR = find(patterns.regressor(1,:)+patterns.regressor(2,:),1,'first')
    sumRegressor = patterns.regressor[0,:] + patterns.regressor[1,:]
    patterns.patterns.firstTestTR = np.min(np.where(sumRegressor == 1)) #(because took out first 10)

    ## Output Files Setup ##
    now = datetime.datetime.now()
    # open and set-up output file
    dataFile = open(os.path.join(runDataDir,'fileprocessing.txt'),'w+')
    dataFile.write('\n*********************************************\n')
    dataFile.write('* rtAttenPenn v.1.0\n')
    dataFile.write('* Date/Time: ' + now.isoformat() + '\n')
    dataFile.write('* Seed: ' + str(seed) + '\n')
    dataFile.write('* Subject Number: ' + str(subjectNum) + '\n')
    dataFile.write('* Run Number: ' + str(runNum) + '\n')
    dataFile.write('*********************************************\n\n')

    # print header to command window
    print('\n*********************************************\n')
    print('* rtAttenPenn v.1.0\n')
    print(['* Date/Time: ' + now.isoformat() + '\n'])
    print(['* Seed: ' + str(seed) + '\n'])
    print(['* Subject Number: ' + str(subjectNum) + '\n'])
    print(['* Run Number: ' + str(runNum) + '\n'])
    print('*********************************************\n\n')

    ## Start Experiment ##
    # prepare for trial sequence
    dataFile.write('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n')
    print('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n')

    ## acquiring files ##

    fileCounter = firstVolPhase1 # file number = # of TR pulses
    for iTrialPhase1 in range(patterns.firstVolPhase2-1):
        # increase the count of TR pulses
        fileCounter = fileCounter+1 # so fileCounter begins at firstVolPhase1

        # smooth files
        patterns.patterns.raw_sm[iTrialPhase1, :] = rtAttenPy.smooth(patterns.raw[iTrialPhase1, :], roiDims, roiInds, FWHM)

        # print trial results
        dataFile.write('{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}\t{:d}\t{:.3f}\t{:.3f}\n'.format(\
            runNum, patterns.block[0][iTrialPhase1], iTrialPhase1, patterns.type[0][iTrialPhase1], \
            patterns.attCateg[0][iTrialPhase1], patterns.stim[0][iTrialPhase1], \
            patterns.fileNum[0][iTrialPhase1], patterns.fileAvail[0][iTrialPhase1], np.nan, np.nan))
        print('{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}\t{:d}\t{:.3f}\t{:.3f}'.format(\
            runNum, patterns.block[0][iTrialPhase1], iTrialPhase1, patterns.type[0][iTrialPhase1], \
            patterns.attCateg[0][iTrialPhase1], patterns.stim[0][iTrialPhase1], \
            patterns.fileNum[0][iTrialPhase1], patterns.fileAvail[0][iTrialPhase1], np.nan, np.nan))

    # end Phase1 loop - fileCounter will be at 115 here
    assert fileCounter == 115
    if TestUsing:
        assert utils.areArraysClose(patterns.raw_sm, target_patterns.raw_sm, mean_limit), "compare raw_sm failed"

    # quick highpass filter!
    dataFile.write('\n*********************************************\n')
    dataFile.write('beginning highpass filter/zscore...\n')
    print('\n*********************************************')
    print('beginning highpassfilter/zscore...')
    i1 = 0
    i2 = patterns.firstVolPhase2-1
    # TODO - load matlab raw_sm and then run remaining here to look if is equal
    patterns.patterns.raw_sm_filt[i1:i2, :] = np.transpose(rtAttenPy.highpass(np.transpose(patterns.raw_sm[i1:i2,:]), cutoff/(2*patterns.TR)))
    patterns.patterns.phase1Mean[0, :] = np.mean(patterns.raw_sm_filt[i1:i2,:], axis=0)
    patterns.patterns.phase1Y[0,:] = np.mean(np.square(patterns.raw_sm_filt[i1:i2,:]), axis=0)
    patterns.patterns.phase1Std[0,:] = np.std(patterns.raw_sm_filt[i1:i2,:], axis=0)
    patterns.patterns.phase1Var[0,:] = np.square(patterns.phase1Std[0,:])
    tileSize = [patterns.raw_sm_filt[i1:i2,:].shape[0], 1]
    patterns.raw_sm_filt_z[i1:i2,:] = np.divide((patterns.raw_sm_filt[i1:i2,:] - np.tile(patterns.phase1Mean,tileSize)), np.tile(patterns.phase1Std, tileSize))

    if TestUsing:
        res = utils.compareMatStructs(patterns, target_patterns, ['raw_sm', 'raw_sm_filt', 'raw_sm_filt_z', 'phase1Mean', 'phase1Y', 'phase1Std', 'phase1Var'])
        res_means = {key:value['mean'] for key, value in res.items()}
        # calculate the pierson correlation for raw_sm_filt_z
        pearsons = []
        num_cols = patterns.raw_sm_filt_z.shape[1]
        for col in range(num_cols):
            pearcol = sstats.pearsonr(patterns.raw_sm_filt_z[i1:i2, col], target_patterns.raw_sm_filt_z[i1:i2, col])
            pearsons.append(pearcol)
        pearsons = np.array(pearsons)
        pearsons_mean = np.mean(pearsons[:, 0])
        print("sm_filt_z mean pearsons correlation {}".format(pearsons_mean))
        assert pearsons_mean > .995, "Pearsons mean {} too low".format(pearsons_mean)

    ## testing ##
    dataFile.write('\n*********************************************\n')
    dataFile.write('beginning model testing...\n')
    print('\n*********************************************')
    print('beginning model testing...')

    # prepare for trial sequence
    dataFile.write('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg')
    print('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg')

    ## end clean up
    dataFile.close()
