# Generate a noise volume given a set of parameters

import os
import time
import inspect
import shutil
import typing
import nibabel  # type: ignore
import numpy as np  # type: ignore
import scipy.io as sio  # type: ignore
from dateutil import parser
from brainiak.utils import fmrisim as sim  # type: ignore
from rtfMRI.RtfMRIClient import loadConfigFile


def generate_data(cfgFile):
    cfg = loadConfigFile(cfgFile)
    frame = inspect.currentframe()
    moduleFile = typing.cast(str, frame.f_code.co_filename)
    moduleDir = os.path.dirname(moduleFile)
    cfgDate = parser.parse(cfg.session.date).strftime("%Y%m%d")
    dataDir = os.path.join(cfg.session.dataDir, "subject{}/day{}".
                           format(cfg.session.subjectNum, cfg.session.subjectDay))
    imgDir = os.path.join(cfg.session.imgDir, "{}.{}.{}".
                          format(cfgDate, cfg.session.subjectName, cfg.session.subjectName))
    if os.path.exists(dataDir) and os.path.exists(imgDir):
        print("output data and imgage directory already exist, skippig data generation")
        return
    runPatterns = ['patternsdesign_1_20180101T000000.mat',
                   'patternsdesign_2_20180101T000000.mat',
                   'patternsdesign_3_20180101T000000.mat']
    template_name = os.path.join(moduleDir, 'sub_template.nii.gz')
    noise_dict_name = os.path.join(moduleDir, 'sub_noise_dict.txt')
    inputA_name = os.path.join(moduleDir, 'ROI_A.nii.gz')
    inputB_name = os.path.join(moduleDir, 'ROI_B.nii.gz')
    output_file_pattern = '001_0000{}_000{}.mat'
    if not os.path.exists(imgDir):
        os.makedirs(imgDir)
    if not os.path.exists(dataDir):
        os.makedirs(dataDir)

    print('Load data')
    template_nii = nibabel.load(template_name)
    template = template_nii.get_data()
    # dimsize = template_nii.header.get_zooms()

    inputA_nii = nibabel.load(inputA_name)
    inputB_nii = nibabel.load(inputB_name)
    signalA = inputA_nii.get_data()
    signalB = inputB_nii.get_data()

    dimensions = np.array(template.shape[0:3])  # What is the size of the brain

    print('Create mask')
    # Generate the continuous mask from the voxels
    mask, _ = sim.mask_brain(volume=template,
                             mask_self=True,
                             )
    # Write out the mask as matlab
    mask_uint8 = mask.astype(np.uint8)
    maskfilename = os.path.join(dataDir, 'mask_{}_{}.mat'.
                                format(cfg.session.subjectNum, cfg.session.subjectDay))
    sio.savemat(maskfilename, {'mask': mask_uint8})

    # Load the noise dictionary
    with open(noise_dict_name, 'r') as f:
        noise_dict = f.read()

    print('Loading ' + noise_dict_name)
    noise_dict = eval(noise_dict)

    runNum = 1
    scanNum = 0
    for patfile in runPatterns:
        fullPatfile = os.path.join(moduleDir, patfile)
        # make dataDir run directory
        runDir = os.path.join(dataDir, "run{}".format(runNum))
        if not os.path.exists(runDir):
            os.makedirs(runDir)
        shutil.copy(fullPatfile, runDir)
        runNum += 1

        pat = sio.loadmat(fullPatfile)
        scanNum += 1
        regressor = pat['patterns']['regressor'][0][0]
        trialType = pat['patterns']['type'][0][0]
        TR_dur = pat['TR'][0][0]
        disdaqs = pat['disdaqs'][0][0]
        begTrOffset = disdaqs // TR_dur
        nTRs = pat['nTRs'][0][0]
        nTestTRs = np.count_nonzero(trialType == 2)

        # Preset some of the parameters
        tr_duration = TR_dur  # How long in seconds is each TR?
        trs = nTRs + begTrOffset  # How many time points are there?

        print('Generating data')
        start = time.time()
        noiseVols = sim.generate_noise(dimensions=dimensions,
                                       stimfunction_tr=np.zeros((trs, 1)),
                                       tr_duration=int(tr_duration),
                                       template=template,
                                       mask=mask,
                                       noise_dict=noise_dict,
                                       )
        print("Time: generate noise vols {} sec".format(time.time() - start))

        testTrId = 0
        numVols = noiseVols.shape[3]
        for idx in range(numVols):
            start = time.time()
            brain = noiseVols[:, :, :, idx]
            if idx >= begTrOffset:
                trIdx = idx-begTrOffset
                if trialType[0][trIdx] == 1:
                    # training TR, so create pure A or B signal
                    if regressor[0][trIdx] != 0:
                        brain = brain + signalA
                    elif regressor[1][trIdx] != 0:
                        brain = brain + signalB
                elif trialType[0][trIdx] == 2:
                    # testing TR, so create a mixture of A and B signal
                    testTrId += 1
                    testPercent = testTrId / nTestTRs
                    brain = brain + testPercent * signalA + (1-testPercent) * signalB

            # Save the volume as a matlab file
            filenum = idx+1
            filename = output_file_pattern.format(str(scanNum).zfill(2), str(filenum).zfill(3))
            outputfile = os.path.join(imgDir, filename)
            brain_float32 = brain.astype(np.float32)
            sio.savemat(outputfile, {'vol': brain_float32})
            print("Time: generate vol {}: {} sec".format(filenum, time.time() - start))
