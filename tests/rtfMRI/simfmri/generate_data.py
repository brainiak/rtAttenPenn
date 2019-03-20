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
    moduleFile = typing.cast(str, frame.f_code.co_filename)  # type: ignore
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
    template_filename = os.path.join(moduleDir, 'sub_template.nii.gz')
    noise_dict_filename = os.path.join(moduleDir, 'sub_noise_dict.txt')
    roiA_filename = os.path.join(moduleDir, 'ROI_A.nii.gz')
    roiB_filename = os.path.join(moduleDir, 'ROI_B.nii.gz')
    output_file_pattern = '001_0000{}_000{}.mat'
    if not os.path.exists(imgDir):
        os.makedirs(imgDir)
    if not os.path.exists(dataDir):
        os.makedirs(dataDir)

    print('Load data')
    template_nii = nibabel.load(template_filename)
    template = template_nii.get_data()
    # dimsize = template_nii.header.get_zooms()

    roiA_nii = nibabel.load(roiA_filename)
    roiB_nii = nibabel.load(roiB_filename)
    roiA = roiA_nii.get_data()
    roiB = roiB_nii.get_data()

    dimensions = np.array(template.shape[0:3])  # What is the size of the brain

    print('Create mask')
    # Generate the continuous mask from the voxels
    mask, template = sim.mask_brain(volume=template,
                             mask_self=True,
                             )
    # Write out the mask as matlab
    mask_uint8 = mask.astype(np.uint8)
    maskfilename = os.path.join(dataDir, 'mask_{}_{}.mat'.
                                format(cfg.session.subjectNum, cfg.session.subjectDay))
    sio.savemat(maskfilename, {'mask': mask_uint8})

    # Load the noise dictionary
    with open(noise_dict_filename, 'r') as f:
        noise_dict = f.read()

    print('Loading ' + noise_dict_filename)
    noise_dict = eval(noise_dict)
    noise_dict['matched'] = 0

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
        # shifted labels are in regressor field
        shiftedLabels = pat['patterns']['regressor'][0][0]
        # non-shifted labels are in attCateg field and whether stimulus applied in the stim field
        nsLabels = pat['patterns']['attCateg'][0][0] * pat['patterns']['stim'][0][0]
        labels_A = (nsLabels == 1).astype(int)
        labels_B = (nsLabels == 2).astype(int)

        # trialType = pat['patterns']['type'][0][0]
        tr_duration = pat['TR'][0][0]
        disdaqs = pat['disdaqs'][0][0]
        begTrOffset = disdaqs // tr_duration
        nTRs = pat['nTRs'][0][0]
        # nTestTRs = np.count_nonzero(trialType == 2)

        # Preset some of the parameters
        total_trs = nTRs + begTrOffset  # How many time points are there?

        print('Generating data')
        start = time.time()
        noiseVols = sim.generate_noise(dimensions=dimensions,
                                       stimfunction_tr=np.zeros((total_trs, 1)),
                                       tr_duration=int(tr_duration),
                                       template=template,
                                       mask=mask,
                                       noise_dict=noise_dict,
                                       )
        print("Time: generate noise vols {} sec".format(time.time() - start))

        nVoxelsA = int(roiA.sum())
        nVoxelsB = int(roiB.sum())
        # Multiply each pattern by each voxel time course
        weights_A = np.tile(labels_A.reshape(-1, 1), nVoxelsA)
        weights_B = np.tile(labels_B.reshape(-1, 1), nVoxelsB)

        print('Creating signal time course')
        signal_func_A = sim.convolve_hrf(stimfunction=weights_A,
                                         tr_duration=tr_duration,
                                         temporal_resolution=(1/tr_duration),
                                         scale_function=1,
                                         )

        signal_func_B = sim.convolve_hrf(stimfunction=weights_B,
                                         tr_duration=tr_duration,
                                         temporal_resolution=(1/tr_duration),
                                         scale_function=1,
                                         )

        max_activity = noise_dict['max_activity']
        signal_change = 10  # .01 * max_activity
        signal_func_A *= signal_change
        signal_func_B *= signal_change

        # Combine the signal time course with the signal volume
        print('Creating signal volumes')
        signal_A = sim.apply_signal(signal_func_A,
                                    roiA,
                                    )

        signal_B = sim.apply_signal(signal_func_B,
                                    roiB,
                                    )
        # Combine the two signal timecourses
        signal = signal_A + signal_B

        # testTrId = 0
        numVols = noiseVols.shape[3]
        for idx in range(numVols):
            start = time.time()
            brain = noiseVols[:, :, :, idx]
            if idx >= begTrOffset:
                # some initial scans are skipped as only instructions and not stimulus are shown
                signalIdx = idx-begTrOffset
                brain += signal[:, :, :, signalIdx]

            # TODO: how to create a varying combined percentage of A and B signals
            #     if trialType[0][idx] == 1:
            #         # training TR, so create pure A or B signal
            #         if labels_A[idx] != 0:
            #             brain = brain + roiA
            #         elif labels_B[idx] != 0:
            #             brain = brain + roiB
            #     elif trialType[0][idx] == 2:
            #         # testing TR, so create a mixture of A and B signal
            #         testTrId += 1
            #         testPercent = testTrId / nTestTRs
            #         brain = brain + testPercent * roiA + (1-testPercent) * roiB

            # Save the volume as a matlab file
            filenum = idx+1
            filename = output_file_pattern.format(str(scanNum).zfill(2), str(filenum).zfill(3))
            outputfile = os.path.join(imgDir, filename)
            brain_float32 = brain.astype(np.float32)
            sio.savemat(outputfile, {'vol': brain_float32})
            print("Time: generate vol {}: {} sec".format(filenum, time.time() - start))


if __name__ == "__main__":
    generate_data("syntheticDataCfg.toml")
