import ClientMain
import sys
import logging
import pytest  # type: ignore


def test_baseModel():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    print("test_baseModel")
    client_args = ['ClientMain.py', '-l']
    result = ClientMain.client_main(client_args)
    assert result is True


if __name__ == '__main__':
    pytest.main(['-s', '--log-cli-level', 'DEBUG', 'test_BaseModel.py'])
