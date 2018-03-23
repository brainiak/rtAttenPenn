import pytest
import logging

logging.basicConfig(level=logging.DEBUG)

def test_log1():
    print("test")
    logging.info("test log message 1")
    logging.info("test log message 2")
