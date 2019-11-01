# Running RtAtten Software

## Command Line Interface (CLI)
#### Run Server and Client Separately
1. Start classification server listening for requests

        python ServerMain.py -p <listen_port>

2. To start client connecting to server<br>
Notes: It is optional to specify run and scan numbers, if not specified the values from the experiment file will be used. The runs and scans can be a comma separated list

        python ClientMain.py -a <server_addr> -p <server_port> -e <experiment_toml_file> -r <runs> -s <scans>

#### Run Client and Server together (for running locally together)
Notes: The -l option specifies to run the server locally

    python ClientMain.py -l -e <experiment_toml_file> -r <runs> -s <scans>

#### Retrieve run files from the server after run completed
    python RetrieveFiles.py -a <server_addr> -p <server_port> -e <experiment_file> -r <runs> -s <scans>


## Web Based Interface
### Start file watcher on scanner computer
Note: allowed dirs and file types can be a comma separated list

    python FileWatchServer.py -d <allowed_dirs> -f <allowed_file_types> -s <server:port>

### Start web server on cloud computer
Note: The classification server (ServerMain.py) is automatically run by the web-interface

    bash scripts/run-web.sh -ip <local_ip_addr> -e <default_experiment_file> -ip <cloud_id_addr>

### Connect from browser
1. Main control panel
        https://cloud_ip_addr:8888
2. Subject feedback panel
        https://cloud_ip_addr:8888/feedback
