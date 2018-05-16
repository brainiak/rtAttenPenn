#!/usr/bin/env python3
"""
Top level routine for client side rtfMRI processing
"""
import threading
import logging
import click
import clickutil
from rtAtten.RtAttenClient import RtAttenClient
from rtfMRI.RtfMRIClient import RtfMRIClient, loadConfigFile
from rtfMRI.BaseClient import BaseClient
from rtfMRI.Errors import InvocationError, RequestError
import rtfMRI.scripts.ServerMain as ServerMain


def ClientMain(addr: str, port: int, experiment: str, run_local: bool, model: str):
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    try:
        # Get params and load config file
        # settings = parseCommandArgs(argv, defaultSettings)
        cfg = loadConfigFile(experiment)
        if 'experiment' not in cfg.keys():
            raise InvocationError("Experiment file must have \"experiment\" section")
        if 'session' not in cfg.keys():
            raise InvocationError("Experiment file must have \"session\" section")

        # Start local server if requested
        if run_local is True:
            startLocalServer(port)

        # Determine the desired model
        if cfg.experiment.model is None:
            raise InvocationError("No model specified in experiment file")
        # Start up client logic for the specified model
        model = cfg.experiment.model
        client: RtfMRIClient
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
@clickutil.call(ClientMain)
def _ClientMain():
    pass


def startLocalServer(port):
    server_thread = threading.Thread(name='server', target=ServerMain.ServerMain, args=(port,))
    server_thread.setDaemon(True)
    server_thread.start()


if __name__ == "__main__":
    _ClientMain()
