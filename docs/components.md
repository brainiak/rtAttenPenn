# Components:

## Phase 1 Components
### Classification Server
**Main file: ServerMain.py**<br>
- Runs on the cloud computer to do model training and classification.
- Run an event loop that listens on a encrypted TCP socket and port for requests.
- An initial request establishes which processing model to use, the only current supported is 'rtAtten'.
- Once the model is selected it will forward command requests to the model file's handleMessage() function.
- See files rtfMRI/RtfMRIServer.py for the top level request handler, and rtAtten/RtAttenModel.py for the model specific message handling functions.

### Client
**Main file: ClientMain.py**<br>
- Runs on the local computer (in the control room)
- Accepts a parameter -m indicating which model to use (such as 'rtAtten')
- The model is the framework for the particular experiment, such as how to initialize the experiment, the blocks of TRs to run etc.
- The client connects to the server and runs the model making processing requests to the server as needed
- The only model currently supported is 'rtAtten'
- See files rtfMRI/RtfMRIClient.py for top level handling and rtAtten/RtAttenClient.py for model specific handling.

## Phase II Components - Web-Based Project Interface
### WebServer
**Main file: WebMain.py**<br>
- A web server running on the cloud computer that runs both the ClientMain.py and ServerMain.py (components described above) when requested to start a run
- Provides a browser based control panel for starting and stopping runs, viewing graphs of results, changing settings and registration steps.
- Accepts https connections from the experimenter's to provide a control panel
- Uses browser web-socket connection to provide logging, graphing and VNC display of registration results to the experimenter's browser
- Accepts web-socket connections from the FileWatchServer running on the local computer to read Dicom files as the become available from the scanner
- VNC server run with websockify as front-end to accept websocket connections for display in client browser. See scripts/run-vnc.sh and websockify conda environment
- See webInterface/ directory, webInterface/WebServer.py
- See webInterface/rtAtten/web for browser code and webInterface/rtAtten/registration for registration scripts
- See websockify.yml for installing websockify conda environment


### FileWatchServer
**Main file: FileWatchServer.py**<br>
- Runs on the local computer (in the control room) and listens for file requests, such as to watch for a Dicom file
- Retrieves the file being watched for when it is available and returns it to the webServer via web-sockets
- Accepts data files to be written locally from the webServer, primarily for supplying classification results back to the local computer for subject feedback display handled by PsychToolbox or PsychoPy
- See file webInterface/webSocketFileWatcher.py


### Browser code
**Main webServer file: webInterface/rtAtten/RtAttenWeb.py**<br>
- Called from WebMain.py and uses webInterface/webServer.py
- Browser
    - JavaScript code in webInterface/rtAtten/web/src
    - Uses React framework for handling events and rendering
    - Uses websockify in front of VNC for showing registration results in browser
- Registration scripts in webInterface/rtAtten/registration
- Connect to main control window at URL ```https://<cloud_ip_addr>:8888```
- Connect to subject feedback window at URL ```https://<cloud_ip_addr>:8888/feedback```
