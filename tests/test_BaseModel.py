import ClientMain as ClientMain
import os
import inspect
import typing
import logging
import pytest  # type: ignore
from rtfMRI.StructDict import StructDict

logging.basicConfig(level=logging.DEBUG)
cfgFile = 'baseExpCfg.toml'


@pytest.fixture(scope="module")
def cfgFilePath():  # type: ignore
    """Get the directory of this test file"""
    frame = inspect.currentframe()
    moduleFile = typing.cast(str, frame.f_code.co_filename)  # type: ignore
    moduleDir = os.path.dirname(moduleFile)
    cfgFullPath = os.path.join(moduleDir, cfgFile)
    return cfgFullPath


def test_baseModel(cfgFilePath):
    print("test_baseModel")
    logging.error("###Test logging###")
    # import pdb; pdb.set_trace()
    params = StructDict(
        {'addr': 'localhost', 'port': 5210,
         'experiment': cfgFilePath,
         'run_local': True, 'use_web': False,
        })
    result = ClientMain.ClientMain(params)
    assert result is True


if __name__ == '__main__':
    pytest.main(['-s', '--log-cli-level', 'debug', 'tests/test_BaseModel.py'])
