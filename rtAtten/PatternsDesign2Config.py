"""Convert a Matlab patternsDesign file to a config file for rtfMRI"""
import os
import numpy as np  # type: ignore
from rtfMRI.StructDict import StructDict
from rtfMRI.utils import loadMatFile, findNewestFile


def createRunConfig(session, runId):
    run = StructDict()
    run.runId = runId
    ids = [idx for (idx, run) in enumerate(session.Runs) if run == runId]
    if len(ids) == 0:
        print("Run {} not in Runs List".format(runId))
        return None
    elif len(ids) > 1:
        print("Run {} declared multiple times in Runs List".format(runId))
        return None
    idx = ids[0]
    if session.ScanNums is not None and len(session.ScanNums) > idx:
        run.scanNum = session.ScanNums[idx]
    else:
        run.scanNum = -1
    dataDir = getSubjectDayDir(session, session.dataDir)
    if session.findNewestPatterns:
        # load the newest file patterns
        patternsFilename = findPatternsDesignFile(dataDir, runId)
    else:
        patternsFilename = session.patternsDesignFiles[idx]
        patternsFilename = os.path.join(session.dataDir, os.path.basename(patternsFilename))
    # load and parse the pattensDesign file
    patterns = loadMatFile(patternsFilename)

    run.disdaqs = int(patterns.disdaqs)
    run.nBlocksPerPhase = int(patterns.nBlocksPerPhase)
    run.TRTime = int(patterns.TR)
    run.nTRs = int(patterns.nTRs)
    run.nTRsFix = int(patterns.nTRsFix)

    run.firstVolPhase1 = int(np.min(np.where(patterns.block.squeeze() == 1)))
    run.lastVolPhase1 = int(np.max(np.where(patterns.block.squeeze() == patterns.nBlocksPerPhase)))
    assert run.lastVolPhase1 == patterns.lastVolPhase1-1,\
        "assert calulated lastVolPhase1 is same as loaded from patternsdesign {} {}"\
        .format(run.lastVolPhase1, patterns.lastVolPhase1)
    run.nVolsPhase1 = run.lastVolPhase1 - run.firstVolPhase1 + 1
    run.firstVolPhase2 = int(np.min(np.where(patterns.block.squeeze() == (patterns.nBlocksPerPhase+1))))
    assert run.firstVolPhase2 == patterns.firstVolPhase2-1,\
        "assert calulated firstVolPhase2 is same as load from patternsdesign {} {}"\
        .format(run.firstVolPhase2, patterns.firstVolPhase2)
    run.lastVolPhase2 = int(np.max(np.where(patterns.type.squeeze() != 0)))
    run.nVolsPhase2 = run.lastVolPhase2 - run.firstVolPhase2 + 1

    sumRegressor = patterns.regressor[0, :] + patterns.regressor[1, :]
    run.firstTestTR = int(np.min(np.where(sumRegressor == 1)))

    run.nVols = patterns.block.shape[1]

    blockGroups = []

    blkGrp1 = createBlockGroupConfig(range(run.firstVolPhase2), patterns)
    blkGrp1.blkGrpId = 1
    blkGrp1.nTRs = run.firstVolPhase2
    blockGroups.append(blkGrp1)

    blkGrp2 = createBlockGroupConfig(range(run.firstVolPhase2, run.nVols), patterns)
    blkGrp2.blkGrpId = 2
    blkGrp2.nTRs = run.nVols - run.firstVolPhase2
    blockGroups.append(blkGrp2)

    run.blockGroups = blockGroups
    return run


def createBlockGroupConfig(tr_range, patterns):
    blkGrp = StructDict()
    blkGrp.blocks = []
    blkGrp.type = 0
    blkGrp.firstVol = tr_range[0]
    block = StructDict()
    blockNum = -1
    for iTR in tr_range:
        if patterns.block[0, iTR] > 0 and patterns.block[0, iTR] != blockNum:
            if blockNum >= 0:
                blkGrp.blocks.append(block)
            blockNum = int(patterns.block[0, iTR])
            block = StructDict()
            block.blockId = blockNum
            block.TRs = []
        tr = StructDict()
        tr.trId = iTR - blkGrp.firstVol
        tr.vol = iTR + 1
        tr.attCateg = int(patterns.attCateg[0, iTR])
        tr.stim = int(patterns.stim[0, iTR])
        tr.type = int(patterns.type[0, iTR])
        if tr.type != 0:
            if blkGrp.type == 0:
                blkGrp.type = tr.type
            assert blkGrp.type == tr.type, "inconsistent TR types in block group"
        tr.regressor = [int(patterns.regressor[0, iTR]), int(patterns.regressor[1, iTR])]
        block.TRs.append(tr)
    if len(block.TRs) > 0:
        blkGrp.blocks.append(block)
    return blkGrp


def findPatternsDesignFile(inputDir, runNum):
    filePattern = 'patternsdesign_' + str(runNum) + '*.mat'
    pdesignFile = findNewestFile(inputDir, filePattern)
    if pdesignFile is not None and pdesignFile != '':
        return pdesignFile
    inputDir = os.path.join(inputDir, 'run'+str(runNum))
    pdesignFile = findNewestFile(inputDir, filePattern)
    if pdesignFile is None or pdesignFile == '':
        raise FileNotFoundError("No files found matching {}".format(filePattern))
    return pdesignFile


def getSubjectDayDir(session, dataDir):
    subjectDayDir = "subject{}/day{}".format(session.subjectNum, session.subjectDay)
    return os.path.join(dataDir, subjectDayDir)
