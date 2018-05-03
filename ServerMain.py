#!/usr/bin/env python3
"""
Top level routine for server side rtfMRI processing
Usage: ServerMain.py -p 5200
Will start a server listening for new connections on port 5200.
Only one connection (therefore) only one client can be supported at a time.
The server will receive commands from the client, execute them and reply.
"""
import os
import sys
import getopt
import logging
from rtfMRI.RtfMRIServer import RtfMRIServer
from rtfMRI.StructDict import StructDict
from rtfMRI.Errors import InvocationError

defaultSettings = {
    'port': 5200,
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
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        filename='logs/rtAttenServer.log')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)

    # Load default settings as a data structure
    settings = StructDict(defaultSettings)
    try:
        # Parse and add any additional settings from the command line
        settings = parseArgs(argv, settings)
        should_exit = False
        while not should_exit:
            logging.info("RtfMRI: Server Starting")
            rtfmri = RtfMRIServer(settings.port)
            should_exit = rtfmri.RunEventLoop()
        logging.info("Server shutting down")
    except InvocationError as err:
        print(repr(err))
        printUsage(argv)
    except Exception as err:
        logging.error(repr(err))
        raise err


if __name__ == "__main__":
    server_main(sys.argv)
