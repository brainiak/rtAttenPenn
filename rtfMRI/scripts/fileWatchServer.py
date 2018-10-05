import os
import sys
import logging
import argparse
currPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(currPath, "../../")
sys.path.append(rootPath)
from rtfMRI.utils import installLoggers
from rtfMRI.fileWatcher import WebSocketFileWatcher


if __name__ == "__main__":
    installLoggers(logging.INFO, logging.DEBUG+1, filename='logs/fileWatcher.log')
    # do arg parse for server to connect to
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', action="store", dest="server")
    parser.add_argument('-i', action="store", dest="interval", type=int)
    args = parser.parse_args()
    if args.server is None:
        print("Usage: must specify a server address")
        parser.print_help()
    print(args.server)
    WebSocketFileWatcher.runFileWatcher(args.server, retryInterval=args.interval)
