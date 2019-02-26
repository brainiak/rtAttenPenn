import re
import logging
import argparse
from rtfMRI.utils import installLoggers
from webInterface.webSocketFileWatcher import WebSocketFileWatcher


defaultAllowedDirs = ['/tmp', '/data']
defaultAllowedTypes = ['.dcm', '.mat']


if __name__ == "__main__":
    installLoggers(logging.INFO, logging.INFO, filename='logs/fileWatcher.log')
    # do arg parse for server to connect to
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', action="store", dest="server", default="localhost:8888",
                        help="Server Address")
    parser.add_argument('-i', action="store", dest="interval", type=int, default=5,
                        help="Retry connection interval (seconds)")
    parser.add_argument('-d', action="store", dest="allowedDirs", default=defaultAllowedDirs,
                        help="Allowed directories to server files from - comma separated list")
    parser.add_argument('-f', action="store", dest="allowedFileTypes", default=defaultAllowedTypes,
                        help="Allowed file types - comma separated list")
    parser.add_argument('-u', '--username', action="store", dest="username", default=None,
                        help="rtAtten website username")
    parser.add_argument('-p', '--password', action="store", dest="password", default=None,
                        help="rtAtten website password")
    args = parser.parse_args()

    if not re.match(".*:\d+", args.server):
        print("Usage: Expecting server address in the form <servername:port>")
        parser.print_help()

    if type(args.allowedDirs) is str:
        args.allowedDirs = args.allowedDirs.split(',')

    if type(args.allowedFileTypes) is str:
        args.allowedFileTypes = args.allowedFileTypes.split(',')

    print("Server: {}, interval {}".format(args.server, args.interval))
    print("Allowed file types {}".format(args.allowedFileTypes))
    print("Allowed directories {}".format(args.allowedDirs))

    WebSocketFileWatcher.runFileWatcher(args.server,
                                        retryInterval=args.interval,
                                        allowedDirs=args.allowedDirs,
                                        allowedTypes=args.allowedFileTypes,
                                        username=args.username,
                                        password=args.password)
