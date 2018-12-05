import os
import sys
import logging
import argparse
currPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(currPath, "../../")
sys.path.append(rootPath)
from rtfMRI.utils import installLoggers
from rtfMRI.fileWatcher import WebSocketFileWatcher


defaultAllowedDirs = ['/tmp', '/data']
defaultAllowedTypes = ['.dcm', '.mat']


if __name__ == "__main__":
    installLoggers(logging.INFO, logging.DEBUG+1, filename='logs/fileWatcher.log')
    # do arg parse for server to connect to
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', action="store", dest="server",
                        help="Server Address")
    parser.add_argument('-i', action="store", dest="interval", type=int,
                        help="Retry connection interval (seconds)")
    parser.add_argument('-d', action="store", dest="allowedDirs",
                        help="Allowed directories to server files from - comma separated list")
    parser.add_argument('-f', action="store", dest="allowedFileTypes",
                        help="Allowed file types - comma separated list")
    args = parser.parse_args()
    if args.server is None:
        print("Usage: must specify a server address")
        parser.print_help()
    if args.allowedDirs is None:
        args.allowedDirs = defaultAllowedDirs
    if args.allowedFileTypes is None:
        args.allowedFileTypes = defaultAllowedTypes

    WebSocketFileWatcher.runFileWatcher(args.server,
                                        retryInterval=args.interval,
                                        allowedDirs=args.allowedDirs,
                                        allowedTypes=args.allowedFileTypes)
