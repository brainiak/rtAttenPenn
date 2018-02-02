import ClientMain
import sys
import logging
import pytest  # type: ignore


def test_baseModel():
    logging.basicConfig(level=logging.debug, stream=sys.stdout)
    print("test_baseModel")
    client_args = ['ClientMain.py', '-l', '-m', 'base']
    result = ClientMain.client_main(client_args)
    assert result is True


if __name__ == '__main__':
    pytest.main(['-s', '--log-cli-level', 'debug', 'test_BaseModel.py'])
