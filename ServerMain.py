#!/usr/bin/env python3
"""
Top level routine for server side rtfMRI processing
"""
import sys
import getopt
import logging
from rtfMRI.RtfMRIServer import RtfMRIServer
from rtfMRI.StructDict import StructDict
from rtfMRI.Errors import InvocationError

defaultSettings = {
    'port': 5500,
}


def printUsage(argv):
    usage_format = """Usage:
    {}: [-p <port>]
    options:
        -p [--port] -- server port"""
    print(usage_format.format(argv[0]))


def parseArgs(argv, settings):
    try:
        opts, _ = getopt.gnu_getopt(argv[1:], "p:", ["port="])
    except getopt.GetoptError as err:
        logging.error(repr(err))
        raise InvocationError("Invalid parameter specified: " + repr(err))
    for opt, arg in opts:
        if opt in ("-p", "--port"):
            settings.port = int(arg)
        else:
            raise InvocationError("unimplemented option {} {}", opt, arg)
    return settings


def server_main(argv):
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    settings = StructDict(defaultSettings)
    try:
        settings = parseArgs(argv, settings)
        should_exit = False
        while not should_exit:
            logging.info("RtfMRI: Server Starting")
            rtfmri = RtfMRIServer(settings.port)
            should_exit = rtfmri.RunEventLoop()
        print("Server shutting down")
    except InvocationError as err:
        print(repr(err))
        printUsage(argv)
    except Exception as err:
        logging.error(repr(err))
        raise err


if __name__ == "__main__":
    server_main(sys.argv)
