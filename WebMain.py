import logging
import argparse
from webInterface.rtAtten.RtAttenWeb import RtAttenWeb
from rtfMRI.RtfMRIClient import loadConfigFile
from rtfMRI.utils import installLoggers
from rtfMRI.StructDict import StructDict


def WebMain(params):
    installLoggers(logging.INFO, logging.INFO, filename='logs/webServer.log')
    cfg = loadConfigFile(params.experiment)

    if cfg.experiment.model == 'rtAtten':
        # call starts web server thread and doesn't return
        rtAttenWeb = RtAttenWeb()
        rtAttenWeb.init(params, cfg)
    else:
        print('Model {}: unsupported or not specified'.format(cfg.experiment.model))


if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument('--rtserver', '-s', default='localhost:5200', type=str,
                           help='rtAtten server hostname:port')
    argParser.add_argument('--rtlocal', '-l', default=False, action='store_true',
                           help='run client and server together locally')
    argParser.add_argument('--filesremote', '-r', default=False, action='store_true',
                           help='dicom files retrieved from remote server')
    argParser.add_argument('--experiment', '-e', default='conf/example.toml', type=str,
                           help='experiment file (.json or .toml)')
    argParser.add_argument('--feedbackdir', '-f', default='webInterface/images', type=str,
                           help='Directory with feedback image files')
    args = argParser.parse_args()
    params = StructDict({'rtserver': args.rtserver,
                         'rtlocal': args.rtlocal,
                         'filesremote': args.filesremote,
                         'experiment': args.experiment,
                         'feedbackdir': args.feedbackdir})
    WebMain(params)
