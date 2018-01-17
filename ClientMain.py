#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import sys
import threading
import getopt
import json
import logging
from rtfMRI.StructDict import StructDict, recurseCreateStructDict
from rtfMRI.RtfMRIClient import RtfMRIClient
from rtfMRI.Errors import *

defaultSettings = {
    'addr':'localhost',
    'port':5500,
    'model':'base',
    'experiment':'experiment.json',
    'run_local':False
}

def printUsage(argv):
    usage_format = """Usage:
    {}: [-a <addr>, -p <port>, -m <model>, -l, -e <jsonfile>]
    options:
        -a [--addr] -- server ip address
        -p [--port] -- server port
        -m [--model] -- model name
        -e [--experiment] -- experiment json file
        -l [--run_local] -- run client and server together locally"""
    print(usage_format.format(argv[0]))

def parseArgs(argv, settings):
    try:
        opts, _ = getopt.gnu_getopt(argv[1:], "a:p:m:e:l", ["addr=", "port=", "model=", "experiment=", "run_local"])
    except getopt.GetoptError as err:
        logging.error(repr(err))
        raise InvocationError("Invalid parameter specified: " + repr(err))
    for opt, arg in opts:
        if opt in ("-a", "--addr"):
            settings.addr = arg
        elif opt in ("-p", "--port"):
            settings.port = int(arg)
        elif opt in ("-m", "--model"):
            settings.model = arg
        elif opt in ("-e", "--experiment"):
            settings.experiment = arg
        elif opt in ("-l", "--run_local"):
            settings.run_local = True
        else:
            raise InvocationError("unimplemented option {} {}", opt, arg)
    return settings

def client_main(argv):
    logging.basicConfig(level=logging.INFO)
    settings = StructDict(defaultSettings)
    try:
        settings = parseArgs(argv, settings)
        if settings.run_local is True:
            startLocalServer(settings)
        client = RtfMRIClient(settings.addr, settings.port)
        client.initModel(settings.model)
        with open(settings.experiment) as fp:
            expJson = json.load(fp)
        cfg = recurseCreateStructDict(expJson)
        client.run(cfg)
        if settings.run_local is True:
            client.sendShutdownServer()
        client.close()
    except InvocationError as err:
        print(repr(err))
        printUsage(argv)
        return False
    except FileNotFoundError as err:
        print("file {} not found: {}".format(settings.experiment, err))
        return False
    return True

def startLocalServer(settings):
    from ServerMain import server_main
    def start_server():
        server_args = ['ServerMain.py', '-p', str(settings.port)]
        server_main(server_args)
    server_thread = threading.Thread(name='server', target=start_server)
    server_thread.setDaemon(True)
    server_thread.start()

if __name__ == "__main__":
    client_main(sys.argv)
