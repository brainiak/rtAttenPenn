import pytest
import os
import sys
import dateutil
scriptPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(scriptPath, "../..")
sys.path.append(rootPath)
from rtfMRI.StructDict import StructDict
from rtfMRI.RtfMRIClient import loadConfigFile
from rtAtten.RtAttenWeb import RtAttenWeb


@pytest.fixture(scope="module")
def configData():
    currentDir = os.path.dirname(os.path.realpath(__file__))
    cfg = loadConfigFile(os.path.join(currentDir, '../rtfMRI/syntheticDataCfg.toml'))
    return cfg


def localCreateRegConfig(cfg):
    regGlobals = StructDict()
    regGlobals.subjectNum = cfg.session.subjectNum
    regGlobals.dayNum = cfg.session.subjectDay
    regGlobals.runNum = cfg.session.Runs[0]
    regGlobals.highresScan = 5  # TODO load from request
    regGlobals.functionalScan = 7  # TODO load from request
    regGlobals.project_path = "/tmp/registration"
    regGlobals.roi_name = "wholebrain_mask"
    scanDate = dateutil.parser.parse(cfg.session.date)
    regGlobals.subjName = scanDate.strftime("%m%d%Y") + str(regGlobals.runNum) + \
        '_' + cfg.experiment.experimentName
    dicomFolder = scanDate.strftime("%Y%m%d") + '.' + regGlobals.subjName + '.' + regGlobals.subjName
    regGlobals.scanFolder = os.path.join(cfg.session.imgDir, dicomFolder)
    return regGlobals


def test_createRegConfig(configData):
    regGlobals = localCreateRegConfig(configData)
    RtAttenWeb.writeRegConfigFile(regGlobals, '/tmp')
    assert os.path.exists(os.path.join('/tmp', 'globals.sh'))


def test_runRegistration(configData):
    params = StructDict()
    params.cfg = configData
    regGlobals = localCreateRegConfig(params.cfg)
    request = {'cmd': 'runReg',
               'regConfig': regGlobals,
               'regType': 'test',
               'dayNum': 1}
    lineCount = RtAttenWeb.runRegistration(request, test=['ping', 'www.google.com', '-c', '3'])
    assert lineCount == 8
