import pytest
import os
import sys
import threading
import dateutil
import time
scriptPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(scriptPath, "../..")
sys.path.append(rootPath)
from rtfMRI.StructDict import StructDict
from rtfMRI.RtfMRIClient import loadConfigFile
from webInterface.rtAtten.RtAttenWeb import RtAttenWeb

webIsStarted = False


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
    regGlobals.data_path = "/tmp/registration"
    regGlobals.roi_name = "wholebrain_mask"
    scanDate = dateutil.parser.parse(cfg.session.date)
    regGlobals.subjName = scanDate.strftime("%m%d%Y") + str(regGlobals.runNum) + \
        '_' + cfg.experiment.experimentName
    dicomFolder = scanDate.strftime("%Y%m%d") + '.' + regGlobals.subjName + '.' + regGlobals.subjName
    regGlobals.scanFolder = os.path.join(cfg.session.imgDir, dicomFolder)
    return regGlobals


def webHandler(configData):
    global webIsStarted
    params = StructDict()
    params.rtserver = 'localhost:5200'
    params.rtlocal = False
    params.filesremote = False
    params.feedbackdir = 'webInterface/images'
    if not webIsStarted:
        webIsStarted = True
        RtAttenWeb.init(params, configData)


class TestRtAttenWeb:
    def setup_class(cls):
        print("starting web server")
        webThread = threading.Thread(name='webThread', target=webHandler, args=(configData,))
        webThread.setDaemon(True)
        webThread.start()
        time.sleep(1)

    def teardown_class(cls):
        RtAttenWeb.webServer.stop()
        time.sleep(1)

    def test_createRegConfig(cls, configData):
        regGlobals = localCreateRegConfig(configData)
        RtAttenWeb.writeRegConfigFile(regGlobals, '/tmp')
        assert os.path.exists(os.path.join('/tmp', 'globals.sh'))


    def test_runRegistration(cls, configData):
        params = StructDict()
        params.cfg = configData
        regGlobals = localCreateRegConfig(params.cfg)
        request = {'cmd': 'runReg',
                   'regConfig': regGlobals,
                   'regType': 'test',
                   'dayNum': 1}
        lineCount = RtAttenWeb.runRegistration(request, test=['ping', 'localhost', '-c', '3'])
        assert lineCount == 8
