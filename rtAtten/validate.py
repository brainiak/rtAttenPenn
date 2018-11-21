import os
import argparse
import numpy as np  # type: ignore
import sys
# Add current working dir so main can be run from the top level rtAttenPenn directory
sys.path.append(os.getcwd())
import rtfMRI.utils as utils
import rtfMRI.ValidationUtils as vutils
from rtfMRI.RtfMRIClient import loadConfigFile
from rtfMRI.Errors import ValidationError
from rtAtten.RtAttenModel import getSubjectDayDir
from sklearn.model_selection import KFold
from sklearn.linear_model import LogisticRegression
from rtfMRI.StructDict import StructDict, MatlabStructDict
from sklearn.metrics import roc_auc_score

def validateMatlabPython(configFile):
    cfg = loadConfigFile(configFile)
    subjectDayDir = getSubjectDayDir(cfg.session.subjectNum, cfg.session.subjectDay)
    matDataDir = os.path.join(cfg.session.dataDir, subjectDayDir)
    pyDataDir = matDataDir
    all_ROC = np.zeros((4,2,len(cfg.session.Runs)))
    for runId in cfg.session.Runs:
        print("EXECUTING ANALYSES FOR RUN {}".format(runId))
        validatePatternsData(matDataDir, pyDataDir, runId)
        validateFileprocessingTxt(matDataDir, pyDataDir, runId)
        mat_roc,py_roc = crossvalidateModels(matDataDir,pyDataDir,runId)
        all_ROC[:,0,runId-1] = mat_roc
        all_ROC[:,1,runId-1] = py_roc
    fullfilename = matDataDir + '/' + 'xvalresults.npy'
    print("saving to %s\n" % fullfilename)
    np.save(fullfilename,all_ROC)

def validatePatternsData(matDataDir, pyDataDir, runId):
    runDir = 'run'+str(runId)+'/'
    # Check how well raw_sm_filt_z values match
    matPatternsFn = utils.findNewestFile(matDataDir, runDir+'patternsdata_'+str(runId)+'*.mat')
    pyBlkGrp1Fn = utils.findNewestFile(pyDataDir, 'blkGroup_r'+str(runId)+'_p1_*_py.mat')
    pyBlkGrp2Fn = utils.findNewestFile(pyDataDir, 'blkGroup_r'+str(runId)+'_p2_*_py.mat')
    print("Validating patternrs: Matlab {}, Python {} {}".format(matPatternsFn, pyBlkGrp1Fn, pyBlkGrp2Fn))

    matPatterns = utils.loadMatFile(matPatternsFn)
    pyBlkGrp1 = utils.loadMatFile(pyBlkGrp1Fn)
    pyBlkGrp2 = utils.loadMatFile(pyBlkGrp2Fn)
    mat_nTRs = matPatterns.raw.shape[0]
    pyp1_nTRs = pyBlkGrp1.raw.shape[0]
    pyp2_nTRs = pyBlkGrp2.raw.shape[0]
    py_nTRs = pyp1_nTRs + pyp2_nTRs
    mat_nVoxels = matPatterns.raw.shape[1]
    py_nVoxels = pyBlkGrp1.raw.shape[1]

    if mat_nTRs != py_nTRs or mat_nVoxels != py_nVoxels:
        raise ValidationError("Number of TRs or Voxels don't match: nTRs m{} p{}, nVoxels m{} p{}".
                              format(mat_nTRs, py_nTRs, mat_nVoxels, py_nVoxels))

    pyCombined_raw_sm_file_z = np.full((py_nTRs, py_nVoxels), np.nan)
    pyCombined_raw_sm_file_z[0:pyp1_nTRs] = pyBlkGrp1.raw_sm_filt_z
    pyCombined_raw_sm_file_z[pyp1_nTRs:] = pyBlkGrp2.raw_sm_filt_z

    corr = vutils.pearsons_mean_corr(matPatterns.raw_sm_filt_z, pyCombined_raw_sm_file_z)
    print("raw_sm_filt_z correlation: {}".format(corr))
    if corr < 0.99:
        raise ValidationError("Pearson correlation low for raw_sm_filt_z: {}".format(corr))

    # Check how well the models match
    matModelFn = utils.findNewestFile(matDataDir, runDir+'trainedModel_'+str(runId)+'*.mat')
    pyModelFn = utils.findNewestFile(pyDataDir, 'trainedModel_r'+str(runId)+'*_py.mat')
    matModel = utils.loadMatFile(matModelFn)
    pyModel = utils.loadMatFile(pyModelFn)
    corr = vutils.pearsons_mean_corr(matModel.weights, pyModel.weights)
    print("model weights correlation: {}".format(corr))
    if corr < 0.99:
        raise ValidationError("Pearson correlation low for model weights: {}".format(corr))
    return


def validateFileprocessingTxt(matDataDir, pyDataDir, runId):
    # Compare fileprocessing.txt files
    runDir = 'run'+str(runId)+'/'
    matFn = os.path.join(matDataDir, runDir, "fileprocessing.txt")
    pyFn = os.path.join(pyDataDir, runDir, "fileprocessing_py.txt")
    # Traverse in reverse order
    with open(matFn) as f:
        matLines = np.asarray(f.readlines())
    with open(pyFn) as f:
        pyLines = np.asarray(f.readlines())

    matLines_rev = matLines[::-1]
    pyLines_rev = pyLines[::-1]

    matStartIdx = pyStartIdx = -1
    for midx in range(matLines_rev.size):
        matLn = matLines_rev[midx].rstrip()
        if len(matLn) > 0 and matLn[0] == str(runId):
            matStartIdx = midx
            break
    for pidx in range(pyLines_rev.size):
        pyLn = pyLines_rev[pidx].rstrip()
        if len(pyLn) > 0 and pyLn[0] == str(runId):
            pyStartIdx = pidx
            break

    if matStartIdx == -1 or pyStartIdx == -1:
        raise ValidationError("Missing line entries with runId m{} p{}".format(matStartIdx, pyStartIdx))

    matCmpLines = matLines_rev[matStartIdx:]
    pyCmpLines = pyLines_rev[pyStartIdx:]
    lineCnt = mispredCnt = diffCnt = 0
    for idx in range(pyCmpLines.size):
        if len(matCmpLines) == 0 or matCmpLines[idx][0] != str(runId):
            break
        lineCnt += 1
        matVals = matCmpLines[idx].rstrip().split('\t')
        pyVals = pyCmpLines[idx].rstrip().split('\t')
        matCategoryVal = float(matVals[-2])
        pyCategoryVal = float(pyVals[-2])
        # print("Vol {}: MatCatVal {}: PyCatVal {}".format(matVals[6], matCategoryVal, pyCategoryVal))
        # Check if the sign of the categoryVals are equal (thus same category)
        if np.isnan(matCategoryVal) and np.isnan(pyCategoryVal):
            continue
        if matCategoryVal != pyCategoryVal:
            # Check if the category vals have the same sign
            if abs(matCategoryVal + pyCategoryVal) != abs(matCategoryVal) + abs(pyCategoryVal):
                # Predictions differ
                mispredCnt += 1
                print("Fileprocessing misprediction: Vol {}: MatCatVal {}: PyCatVal {}"
                      .format(matVals[6], matCategoryVal, pyCategoryVal))
            # Check the magnitude of the difference
            diff = abs(matCategoryVal - pyCategoryVal)
            if diff > 0.3:
                diffCnt += 1
                print("Fileprocessing diff > 0.3: Vol {}: MatCatVal {}: PyCatVal {}"
                      .format(matVals[6], matCategoryVal, pyCategoryVal))
    print("Fileprocessing Results: {} lines compared, {} mispredictions, {} diff > 0.3".
          format(lineCnt, mispredCnt, diffCnt))
    return


def crossvalidateModels(matDataDir, pyDataDir, runId):
    runDir = 'run'+str(runId)+'/'
    matModelFn = utils.findNewestFile(matDataDir, runDir+'trainedModel_'+str(runId)+'*.mat')
    pyModelFn = utils.findNewestFile(pyDataDir, 'trainedModel_r'+str(runId)+'*_py.mat')
    matModel = utils.loadMatFile(matModelFn)
    pyModel = utils.loadMatFile(pyModelFn)
    selector = np.concatenate((0*np.ones((50)),1*np.ones((50)),2*np.ones((50)),3*np.ones((50))),axis=0)
    X = np.array([1,2,3,4])
    nfold = 4
    kf = KFold(nfold)
    mat_roc = np.zeros((nfold))
    py_roc = np.zeros((nfold))
    i = 0
    for train_index, test_index in kf.split(X):
        print("TRAIN:", train_index, "TEST:", test_index)
        trTrain = np.in1d(selector,train_index)
        trTest = np.in1d(selector,test_index)
        # matlab first
        mat_lrc = LogisticRegression(solver='sag', penalty='l2', max_iter=300)
        categoryTrainLabels = np.argmax(matModel.trainLabels[trTrain,:],axis=1)
        mat_lrc.fit(matModel.trainPats[trTrain,:], categoryTrainLabels)
        mat_predict = mat_lrc.predict_proba(matModel.trainPats[trTest,:])
        categ_sep = -1*np.diff(mat_predict,axis=1)
        C0 = np.argwhere(np.argmax(matModel.trainLabels[trTest,:],axis=1)==0)
        C1 = np.argwhere(np.argmax(matModel.trainLabels[trTest,:],axis=1)==1)
        correctLabels = np.ones((len(categ_sep)))
        correctLabels[C1] = -1
        mat_roc[i] = roc_auc_score(correctLabels, categ_sep)
        print("MAT AUC for iteration %i is: %.2f" %(i,mat_roc[i]))
        # python second
        py_lrc = LogisticRegression(solver='sag', penalty='l2', max_iter=300)
        categoryTrainLabels = np.argmax(pyModel.trainLabels[trTrain,:],axis=1)
        py_lrc.fit(pyModel.trainPats[trTrain,:], categoryTrainLabels)
        py_predict = py_lrc.predict_proba(pyModel.trainPats[trTest,:])
        categ_sep = -1*np.diff(py_predict,axis=1)
        C0 = np.argwhere(np.argmax(pyModel.trainLabels[trTest,:],axis=1)==0)
        C1 = np.argwhere(np.argmax(pyModel.trainLabels[trTest,:],axis=1)==1)
        correctLabels = np.ones((len(categ_sep)))
        correctLabels[C1] = -1
        py_roc[i] = roc_auc_score(correctLabels, categ_sep)
        print("PY AUC for iteration %i is: %.2f\n" %(i,py_roc[i]))
        i+= 1
    print("AVG AUC MAT,PY is: %.2f,%.2f\n" %(np.mean(mat_roc),np.mean(py_roc)))
    #mat_mean = np.mean(mat_roc)
    #py_mean = np.mean(py_roc)
    #all_ROC = np.concatenate((mat_roc[:,np.newaxis],py_roc[:,np.newaxis]),axis=1)
    #fullfilename = matDataDir + '/' + 'xvalresults.npy'
    #print("saving to %s\n" % fullfilename)
    #np.save(fullfilename,all_ROC)
    return mat_roc,py_roc
def main():
    descStr = 'Compare and validate that python and matlab output agree. Specify '\
        'either a config file or a directory and runID to test'
    parser = argparse.ArgumentParser(description=descStr)
    parser.add_argument('-e', action="store", dest="cfg")
    parser.add_argument('-d', action="store", dest="dir")
    parser.add_argument('-r', action="store", dest="runId", type=int)
    args = parser.parse_args()
    if args.cfg is not None:
        print("Validating using config file {}".format(args.cfg))
        validateMatlabPython(args.cfg)
    elif args.dir is not None:
        if args.runId is None:
            print("Usage: must specify both a directory and runId")
            parser.print_help()
            return
        print("Validating using dir {}: runId {}".format(args.dir, args.runId))
        validatePatternsData(args.dir, args.dir, args.runId)
        validateFileprocessingTxt(args.dir, args.dir, args.runId)
        crossvalidateModels(args.dir,args,dir,args.runId)
    else:
        parser.print_help()
        return


if __name__ == "__main__":
    main()
