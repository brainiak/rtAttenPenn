const React = require('react')
const ReactDOM = require('react-dom')
const dateformat = require('dateformat');
const path = require('path');
const SettingsPane = require('./settingsPane.js')
const StatusPane = require('./statusPane.js')
const RegistrationPane = require('./registrationPane.js')
const VNCViewerPane = require('./vncViewerPane.js')
const { Tab, Tabs, TabList, TabPanel } = require('react-tabs')


const elem = React.createElement;

const logLineStyle = {
    margin: '0',
}

class RtAtten extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      config: {},
      regConfig: {fParam: '0.6'},
      regInfo: {},
      connected: false,
      error: '',
      logLines: [],  // image classification log
      regLines: [],  // registration processing log
    }
    this.registrationTabIndex = 2
    this.webSocket = null
    this.onTabSelected = this.onTabSelected.bind(this);
    this.setConfig = this.setConfig.bind(this);
    this.getConfigItem = this.getConfigItem.bind(this);
    this.setConfigItem = this.setConfigItem.bind(this);
    this.getRegConfigItem = this.getRegConfigItem.bind(this);
    this.setRegConfigItem = this.setRegConfigItem.bind(this);
    this.runRegistration = this.runRegistration.bind(this);
    this.requestDefaultConfig = this.requestDefaultConfig.bind(this)
    this.createRegConfig = this.createRegConfig.bind(this)
    this.startRun = this.startRun.bind(this);
    this.stopRun = this.stopRun.bind(this);
    this.uploadImages = this.uploadImages.bind(this);
    this.createWebSocket = this.createWebSocket.bind(this)
    this.createWebSocket()
  }

  onTabSelected(index, lastIndex, event) {
    if (index == this.registrationTabIndex) {
      // show the screen div
      var screenDiv = document.getElementById('screen')
      screenDiv.style.display = "initial";
      this.createRegConfig()
    } else if (lastIndex == this.registrationTabIndex && index != lastIndex){
      // hide the screen div
      var screenDiv = document.getElementById('screen')
      screenDiv.style.display = "none";
    }
  }

  createRegConfig() {
    var cfg = this.state.config;
    // TODO - handle case where date string is 'now'
    var scanDate = Date.parse(cfg.session.date)
    var dateStrMDY = dateformat(scanDate, 'mmddyy')
    var dateStrYYMD = dateformat(scanDate, 'yyyymmdd')
    var regGlobals = {}
    regGlobals.subjectNum = cfg.session.subjectNum;
    regGlobals.dayNum = cfg.session.subjectDay;
    regGlobals.runNum = cfg.session.Runs[0]
    regGlobals.highresScan = this.getRegConfigItem('highresScan')
    regGlobals.functionalScan = this.getRegConfigItem('functionalScan')
    regGlobals.fParam = this.getRegConfigItem('fParam')
    regGlobals.project_path = cfg.session.regDir
    regGlobals.dryrun = cfg.session.registrationDryRun.toString().toLowerCase()
    regGlobals.roi_name = "wholebrain_mask"
    regGlobals.subjName = dateStrMDY + regGlobals.runNum + '_' + cfg.experiment.experimentName
    var dicomFolder = dateStrYYMD + '.' + regGlobals.subjName + '.' + regGlobals.subjName
    regGlobals.scanFolder = path.join(cfg.session.imgDir, dicomFolder)
    console.log(regGlobals)
    this.setState({regConfig: regGlobals})
  }

  setConfig(newConfig) {
    this.setState({config: newConfig})
  }

  getConfigItem(name) {
    for (let section in this.state.config) {
      for (let key in this.state.config[section]) {
        if (key == name) {
          return this.state.config[section][key]
        }
      }
    }
    return ''
  }

  setConfigItem(name, value) {
    for (let section in this.state.config) {
      for (let key in this.state.config[section]) {
        if (key == name) {
          var revSection = Object.assign({}, this.state.config[section], { [name]: value })
          var revConfig = Object.assign({}, this.state.config, { [section]: revSection })
          this.setState({config: revConfig})
          return
        }
      }
    }
  }

  getRegConfigItem(name) {
    if (name in this.state.regConfig) {
      return this.state.regConfig[name]
    }
    return ''
  }

  setRegConfigItem(name, value) {
    var regConfig = Object.assign({}, this.state.regConfig, { [name]: value })
    this.setState({regConfig: regConfig})
  }

  requestDefaultConfig() {
    var cmd = {'cmd': 'getDefaultConfig'}
    var cmdStr = JSON.stringify(cmd)
    this.webSocket.send(cmdStr)
  }

  uploadImages(uploadType, scanFolder, scanNum, numDicoms) {
    var request = {cmd: 'uploadImages',
                   type: uploadType,
                   scanFolder: scanFolder,
                   scanNum: scanNum,
                   numDicoms: numDicoms,
                  }
    this.webSocket.send(JSON.stringify(request))
  }

  runRegistration(regType) {
    // clear previous log output
    this.setState({regLines: []})
    this.setState({error: ''})

    if (this.state.regConfig.highresScan == '') {
      this.setState({error: 'Must specify Highres Scan value'})
      return
    }
    if (this.state.regConfig.functionalScan == '') {
      this.setState({error: 'Must specify Functional Scan value'})
      return
    }
    if (regType == 'skullstrip' && this.state.regConfig.fParam == '') {
      this.setState({error: 'Must specify fParam value'})
      return
    }
    var request = {cmd: 'runReg',
                   regType: regType,
                   config: this.state.config,
                   regConfig: this.state.regConfig,
                  }
    console.log('runRegistration ' + regType)
    this.webSocket.send(JSON.stringify(request))
  }

  startRun() {
    // clear previous log output
    this.setState({logLines: []})
    this.setState({error: ''})

    var runs = this.getConfigItem('Runs')
    var scans = this.getConfigItem('ScanNums')
    if (! Array.isArray(runs) || ! Array.isArray(scans)) {
      this.setState({error: 'Runs or ScanNums must be an array'})
      return
    }

    if (typeof runs[0] === 'string') {
      if (runs.length > 1) {
        this.setState({error: 'Runs is string array > length 1'})
        return
      }
      runs = runs[0].split(',').map(Number);
    }

    if (typeof scans[0] === 'string') {
      if (scans.length > 1) {
        this.setState({error: 'Scans is string array > length 1'})
        return
      }
      scans = scans[0].split(',').map(Number);
    }
    this.setConfigItem('Runs', runs)
    this.setConfigItem('ScanNums', scans)

    this.webSocket.send(JSON.stringify({cmd: 'run', config: this.state.config}))
  }

  stopRun() {
    this.webSocket.send(JSON.stringify({cmd: 'stop'}))
  }

  createWebSocket() {
    var wsUserURL = 'wss://' + location.hostname + ':' + location.port + '/wsUser'
    console.log(wsUserURL)
    var webSocket = new WebSocket(wsUserURL);
    webSocket.onopen = (openEvent) => {
      this.setState({connected: true})
      console.log("WebSocket OPEN: ");
      this.requestDefaultConfig();
    };
    webSocket.onclose = (closeEvent) => {
      this.setState({connected: false})
      console.log("WebSocket CLOSE: ");
    };
    webSocket.onerror = (errorEvent) => {
      this.setState({error: JSON.stringify(errorEvent, null, 4)})
      console.log("WebSocket ERROR: " + JSON.stringify(errorEvent, null, 4));
    };
    webSocket.onmessage = (messageEvent) => {
      var wsMsg = messageEvent.data;
      var request = JSON.parse(wsMsg)
      // reset error message
      this.setState({error: ''})
      var cmd = request['cmd']
      if (cmd == 'config') {
        var config = request['value']
        console.log(config)
        this.setState({config: config})
        this.createRegConfig();
      } else if (cmd == 'log') {
        var logItem = request['value'].trim()
        var itemPos = this.state.logLines.length + 1
        var newLine = elem('pre', { style: logLineStyle,  key: itemPos }, logItem)
        // Need to use concat() to create a new logLines object or React won't know to re-render
        var logLines = this.state.logLines.concat([newLine])
        this.setState({logLines: logLines})
      } else if (cmd == 'regLog') {
        var logItem = request['value'].trim()
        var itemPos = this.state.regLines.length + 1
        var newLine = elem('pre', { style: logLineStyle,  key: itemPos }, logItem)
        var regLines = this.state.regLines.concat([newLine])
        this.setState({regLines: regLines})
      } else if (cmd == 'uploadProgress') {
        var uploadType = request['type']
        var progress = request['progress']
        var regInfo = Object.assign({}, this.state.regInfo, { [uploadType]: progress })
        this.setState({regInfo: regInfo})
      } else if (cmd == 'error') {
        console.log("## Got Error" + request['error'])
        this.setState({error: request['error']})
      } else {
        errStr = "Unknown message type: " + cmd
        console.log(errStr)
        this.setState({error: errStr})
      }
    };
    this.webSocket = webSocket
  }

  render() {
    var tp =
     elem(Tabs, {onSelect: this.onTabSelected},
       elem(TabList, {},
         elem(Tab, {}, 'Run'),
         elem(Tab, {}, 'Settings'),
         elem(Tab, {}, 'Registration'),
       ),
       elem(TabPanel, {},
         elem(StatusPane,
           {logLines: this.state.logLines,
            config: this.state.config,
            error: this.state.error,
            startRun: this.startRun,
            stopRun: this.stopRun,
            setConfig: this.setConfig,
            getConfigItem: this.getConfigItem,
            setConfigItem: this.setConfigItem,
           }
         ),
       ),
       elem(TabPanel, {},
         elem(SettingsPane,
           {config: this.state.config,
            setConfig: this.setConfig,
            getConfigItem: this.getConfigItem,
            setConfigItem: this.setConfigItem,
           }
         ),
       ),
       elem(TabPanel, {},
         elem(RegistrationPane,
           {error: this.state.error,
            regLines: this.state.regLines,
            regInfo: this.state.regInfo,
            uploadImages: this.uploadImages,
            runRegistration: this.runRegistration,
            getRegConfigItem: this.getRegConfigItem,
            setRegConfigItem: this.setRegConfigItem,
           }
         ),
       ),
     )
    return tp
  }
}

function Render() {
  const tabDiv = document.getElementById('tabs_container');
  ReactDOM.render(elem(RtAtten), tabDiv);
}

Render()
