# Function to load in niftis and make a mask for those files

import numpy as np
import sys
import os
import os
import scipy
from scipy import io
import glob
import nibabel
import matplotlib.pyplot as plt
import argparse
import logging
# needs to:
# load the 2 nifti files
# rotate back to be in functional space - 90 degree counterclockwise rotation of the third dimension

subjectNum = np.int(sys.argv[1])
dayNum = np.float(sys.argv[2])
# check if it's just an integer --> if so, make it as an integer
z = dayNum - np.floor(dayNum)
if z == 0:
    dayNum = np.int(dayNum)
data_path = sys.argv[3]
def plot3Dbrain(nslices,mask):
    plt.subplots()
    for s in np.arange(nslices):
        plt.subplot(6,6,s+1)
        plt.imshow(mask[:,:,s])
    plt.show()
    return


def makeMask(subjectNum,dayNum,data_path):


    roi_name = 'wholebrain_mask'

    if dayNum==1:
        functionalFN = 'exfunc'
        maskName = roi_name + '_' + 'exfunc'
    else:
        functionalFN = 'exfunc2'
        maskName = 'mask12func2'

    subject_day_dir = "{0}/subject{1}/day{2}".format(data_path,subjectNum,dayNum)
    nifti_exfunc = "{0}/reg/{1}_brain.nii.gz".format(subject_day_dir,functionalFN)
    nifti_mask = "{0}/reg/{1}.nii.gz".format(subject_day_dir,maskName)
    matrix_mask_output = "{0}/mask_{1}_{2}.mat".format(subject_day_dir,subjectNum,dayNum)
    # start with example case then check later
    # nifti_exfunc='/Volumes/norman/amennen/TEMP_MAKE_MASK/exfunc_brain.nii.gz'
    # nifti_mask='/Volumes/norman/amennen/TEMP_MAKE_MASK/wholebrain_mask_exfunc.nii.gz'

    exfunc_img = nibabel.load(nifti_exfunc).get_data()
    mask_img = nibabel.load(nifti_mask).get_data()
    
    # now rotate each
    anatMaskRot = np.zeros(np.shape(exfunc_img))
    brainExtRot = np.zeros((np.shape(exfunc_img)))
    for i in np.arange(np.shape(exfunc_img)[2]):
        anatMaskRot[:,:,i] = np.rot90(mask_img[:,:,i])
        brainExtRot[:,:,i] = np.rot90(exfunc_img[:,:,i])
    
    anatMaskRot = anatMaskRot.astype(bool)
    brainExtRot = brainExtRot.astype(bool)
    intersection = np.logical_and(anatMaskRot,brainExtRot)
    mask_brain = np.zeros((np.shape(exfunc_img)))
    mask_brain[intersection] = 1
    #mask_brain = mask_brain.astype(int)
    mask = {}
    mask['mask'] = mask_brain
    checkMask = 0
    if checkMask:
        plot3Dbrain(36,mask_brain)

    scipy.io.savemat(matrix_mask_output,mask)

    return 


def main():

    # MAKE FUNCTION HERE TO TAKE IN THE ARGUMENT OF SAVE PATH!
    makeMask(subjectNum,dayNum,data_path)
if __name__ == "__main__":
    # execute only if run as a script
    main()
