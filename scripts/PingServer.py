#!/usr/bin/env python3
"""
Utility to test if the server is accessible and measure round-trip time
"""
import sys
import time
import getopt
import os
# fix up search path
currPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(currPath, "../")
sys.path.append(rootPath)
from rtfMRI.MsgTypes import MsgEvent
from rtfMRI.RtfMRIClient import RtfMRIClient
from rtfMRI.Errors import RequestError, InvocationError


def printUsage(argv):
    usage_format = """Usage:
    {}: [-a <addr>, -p <port>]
    options:
        -a [--addr] -- server ip address
        -p [--port] -- server port"""
    print(usage_format.format(argv[0]))


def parseCommandArgs(argv):
    addr = 'localhost'
    port = 5500
    try:
        shortOpts = "a:p:"
        longOpts = ["addr=", "port="]
        opts, _ = getopt.gnu_getopt(argv[1:], shortOpts, longOpts)
    except getopt.GetoptError as err:
        raise InvocationError("Invalid parameter specified: " + repr(err))
    for opt, arg in opts:
        if opt in ("-a", "--addr"):
            addr = arg
        elif opt in ("-p", "--port"):
            port = int(arg)
        else:
            raise InvocationError("unimplemented option {} {}", opt, arg)
    return (addr, port)


def ping_main(argv):
    (addr, port) = parseCommandArgs(argv)
    try:
        print("Ping {}:{}".format(addr, port))
        startTime = time.time()
        client = RtfMRIClient()
        client.connect(addr, port)
        client.sendCmdExpectSuccess(MsgEvent.Ping, None)
        client.disconnect()
        endTime = time.time()
        print("RTT: {:.2f}ms".format(endTime-startTime))
    except ConnectionRefusedError as err:
        print("Connection Refused")
    except InvocationError as err:
        print(repr(err))
        printUsage(argv)
        return False
    except RequestError as err:
        print("Request Error: {}".format(err))
    return True


if __name__ == "__main__":
    ping_main(sys.argv)
