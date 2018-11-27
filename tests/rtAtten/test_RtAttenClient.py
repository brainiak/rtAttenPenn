import pytest
import os
import sys
scriptPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(scriptPath, "../..")
sys.path.append(rootPath)
from rtfMRI.StructDict import StructDict
from rtAtten.RtAttenClient import RtAttenClient


def test_createRegConfig():
    client = RtAttenClient()

    # Test 1, list in a string
    cfg = StructDict()
    cfg.session = StructDict()
    cfg.session.Runs = '1 ,2, 3'
    cfg.session.ScanNums = '1'
    assert checkCfg(client, cfg)
    assert type(cfg.session.Runs[0]) is int
    assert type(cfg.session.ScanNums[0]) is int

    # Test 2, list of strings
    cfg = StructDict()
    cfg.session = StructDict()
    cfg.session.Runs = ['1', '2', '3']
    cfg.session.ScanNums = ['1']
    assert checkCfg(client, cfg)
    assert type(cfg.session.Runs[0]) is int
    assert type(cfg.session.ScanNums[0]) is int

    # Test 3, list of string list
    cfg = StructDict()
    cfg.session = StructDict()
    cfg.session.Runs = ['1 ,2, 3']
    cfg.session.ScanNums = ['1']
    assert checkCfg(client, cfg)
    assert type(cfg.session.Runs[0]) is int
    assert type(cfg.session.ScanNums[0]) is int

    # Test 3, list of ints
    cfg = StructDict()
    cfg.session = StructDict()
    cfg.session.Runs = [1, 2, 3]
    cfg.session.ScanNums = [1]
    assert checkCfg(client, cfg)
    assert type(cfg.session.Runs[0]) is int
    assert type(cfg.session.ScanNums[0]) is int

    # Test 4, empty list
    cfg = StructDict()
    cfg.session = StructDict()
    cfg.session.Runs = []
    cfg.session.ScanNums = []
    assert checkCfg(client, cfg) is False


def checkCfg(client, cfg):
    try:
        ret = client.cfgValidation(cfg)
        return ret
    except Exception as err:
        # print('Exception: {}'.format(err))
        return False
