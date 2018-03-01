import ClientMain
import sys
import logging
import pytest  # type: ignore

logging.basicConfig(level=logging.DEBUG)

def test_baseModel():
    print("test_baseModel")
    logging.error("###Test logging###")
    client_args = ['ClientMain.py', '-l', '-e', 'baseExpCfg.toml']
    # import pdb; pdb.set_trace()
    result = ClientMain.client_main(client_args)
    assert result is True


if __name__ == '__main__':
    pytest.main(['-s', '--log-cli-level', 'debug', 'tests/test_BaseModel.py'])
