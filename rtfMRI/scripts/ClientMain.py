#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import sys
import os
import threading
import logging
import click
import clickutil
# fix up search path
currPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(currPath, "../../")
sys.path.append(rootPath)
from rtAtten.RtAttenClient import RtAttenClient
from rtfMRI.RtfMRIClient import RtfMRIClient, loadConfigFile
from rtfMRI.BaseClient import BaseClient
from rtfMRI.Errors import InvocationError, RequestError
import rtfMRI.scripts.ServerMain as ServerMain
from rtfMRI.utils import installLoggers


def ClientMain(addr: str, port: int, experiment: str, run_local: bool,
               model: str, runs: str, scans: str):
    installLoggers(logging.INFO, logging.DEBUG+1, filename='logs/rtAttenClient.log')

    try:
        # Get params and load config file
        # settings = parseCommandArgs(argv, defaultSettings)
        cfg = loadConfigFile(experiment)
        if 'experiment' not in cfg.keys():
            raise InvocationError("Experiment file must have \"experiment\" section")
        if 'session' not in cfg.keys():
            raise InvocationError("Experiment file must have \"session\" section")

        if runs is not None:
            if scans is None:
                raise InvocationError(
                    "Scan numbers must be specified when run numbers are specified.\n"
                    "Use -s to input scan numbers that correspond to the runs entered.")
            cfg.session.Runs = [int(x) for x in runs.split(',')]
            cfg.session.ScanNums = [int(x) for x in scans.split(',')]

        # Start local server if requested
        if run_local is True:
            startLocalServer(port)

        # Determine the desired model
        if cfg.experiment.model is None:
            raise InvocationError("No model specified in experiment file")
        # Start up client logic for the specified model
        model = cfg.experiment.model
        client: RtfMRIClient  # define a new variable of type RtfMRIClient
        if model == 'base':
            client = BaseClient()
        elif model == 'rtAtten':
            client = RtAttenClient()
        else:
            raise InvocationError("Unsupported model %s" % (model))
        # Run the session
        client.connect(addr, port)
        client.initSession(cfg)
        client.doRuns()
        client.endSession()
        if run_local is True:
            client.sendShutdownServer()
        client.close()
    except FileNotFoundError as err:
        print("Error: {}: {}".format(experiment, err))
        return False
    except RequestError as err:
        print("Request Error: {}".format(err))
    return True


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--addr', '-a', default='localhost', type=str, help='server ip address')
@click.option('--port', '-p', default=5200, type=int, help='server port')
@click.option('--experiment', '-e', default='conf/example.toml', type=str, help='experiment file (.json or .toml)')
@click.option('--run-local', '-l', default=False, is_flag=True, type=bool, help='run client and server together locally')
@click.option('--model', '-m', default=None, type=str, help='model name')
@click.option('--runs', '-r', default=None, type=str, help='Comma separated list of run numbers')
@click.option('--scans', '-s', default=None, type=str, help='Comma separated list of scan number')
@clickutil.call(ClientMain)
def _ClientMain():
    pass


def startLocalServer(port):
    server_thread = threading.Thread(name='server', target=ServerMain.ServerMain, args=(port,))
    server_thread.setDaemon(True)
    server_thread.start()


if __name__ == "__main__":
    _ClientMain()
