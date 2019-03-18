import sys
import re
import time
import json
import threading
import logging
import argparse
from rtfMRI.utils import installLoggers
from webInterface.EventNotifier import EventNotifier
from webInterface.WebClientUtils import certFile, checkSSLCertAltName, makeSSLCertFile


def sendTTLPulses():
    cmd = {'cmd': 'ttlPulse'}
    while True:
        time.sleep(2)
        EventNotifier.sendMessage(json.dumps(cmd))


if __name__ == "__main__":
    installLoggers(logging.DEBUG+1, logging.DEBUG+1, filename='logs/EventServer.log')
    # do arg parse for server to connect to
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', action="store", dest="server", default="localhost:8888",
                        help="Server Address")
    parser.add_argument('-i', action="store", dest="interval", type=int, default=5,
                        help="Retry connection interval (seconds)")
    parser.add_argument('-u', '--username', action="store", dest="username", default=None,
                        help="rtAtten website username")
    parser.add_argument('-p', '--password', action="store", dest="password", default=None,
                        help="rtAtten website password")
    args = parser.parse_args()

    if not re.match(r'.*:\d+', args.server):
        print("Usage: Expecting server address in the form <servername:port>")
        parser.print_help()
        sys.exit()

    addr, port = args.server.split(':')
    # Check if the ssl certificate is valid for this server address
    if checkSSLCertAltName(certFile, addr) is False:
        # Addr not listed in sslCert, recreate ssl Cert
        makeSSLCertFile(addr)

    # start a thread that sends TTL pulses every 2 seconds
    ttlThread = threading.Thread(name='ttlThread', target=sendTTLPulses)
    ttlThread.setDaemon(True)
    ttlThread.start()

    print("Server: {}, interval {}".format(args.server, args.interval))
    EventNotifier.runNotifier(args.server,
                              retryInterval=args.interval,
                              username=args.username,
                              password=args.password)
