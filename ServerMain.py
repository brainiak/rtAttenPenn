#!/usr/bin/env python3
"""
Top level routine for server side rtfMRI processing
Usage: ServerMain.py -p 5200
Will start a server listening for new connections on port 5200.
Only one connection (therefore) only one client can be supported at a time.
The server will receive commands from the client, execute them and reply.
"""
import os
import argparse
import logging
from rtfMRI.RtfMRIServer import RtfMRIServer
from rtfMRI.utils import installLoggers


def ServerMain(port, logLevel):
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # installLoggers(consoleLevel, fileLevel) Debug-10, Info-20, Warning-30, Error-40, Cricital-50
    installLoggers(logLevel, logging.INFO, filename='logs/rtAttenServer.log')

    try:
        # Parse and add any additional settings from the command line
        should_exit = False
        while not should_exit:
            logging.info("RtfMRI: Server Starting")
            rtfmri = RtfMRIServer(port)
            should_exit = rtfmri.RunEventLoop()
        logging.info("Server shutting down")
    except Exception as err:
        logging.error('ServerMain: {}'.format(repr(err)))
        raise err


if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument('--port', '-p', default=5200, type=int, help='server port')
    argParser.add_argument('--logLevel', '-g', default=20, type=int, help='console log level (0-50): default 20')
    args = argParser.parse_args()
    ServerMain(args.port, args.logLevel)
