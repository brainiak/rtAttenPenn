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
      config: {session: {}},
      configFileName: 'Default',
      regConfig: {fParam: '0.6', makenii: true},
      regInfo: {},
      runStatus: '',
      filesRemote: true,  // whether the webserver gets image files from a remote server or locally
      connected: false,
      error: '',
      logLines: [],  // image classification log
      regLines: [],  // registration processing log
    }
    this.webSocket = null
    this.registrationTabIndex = 1
    this.onTabSelected = this.onTabSelected.bind(this);
    this.setConfigFileName = this.setConfigFileName.bind(this);
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
    this.formatConfigValues = this.formatConfigValues.bind(this)
    this.clearRunStatus = this.clearRunStatus.bind(this)
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
    var dateStr = cfg.session.date
    var dateStrMDY = ''
    var dateStrYYMD = ''
    if ([undefined, '', 'now'].indexOf(dateStr) != -1) {
      var dateNow = Date()
      dateStrMDY = dateformat(dateNow, 'mmddyy')
      dateStrYYMD = dateformat(dateNow, 'yyyymmdd')
    } else {
      // handle case where date string has '-' instead of '/'
      dateStr = cfg.session.date.replace('-', '/')
      var scanDate = Date.parse(dateStr)
      dateStrMDY = dateformat(scanDate, 'mmddyy')
      dateStrYYMD = dateformat(scanDate, 'yyyymmdd')
    }
    var regGlobals = {}
    regGlobals.subjectNum = cfg.session.subjectNum;
    regGlobals.dayNum = cfg.session.subjectDay;
    regGlobals.runNum = -1
    if (cfg.session.Runs != undefined) {
      regGlobals.runNum = cfg.session.Runs[0]
    }
    regGlobals.highresScan = this.getRegConfigItem('highresScan')
    regGlobals.functionalScan = this.getRegConfigItem('functionalScan')
    regGlobals.fParam = this.getRegConfigItem('fParam')
    regGlobals.makenii = this.getRegConfigItem('makenii')
    regGlobals.data_path = cfg.session.dataDir
    regGlobals.dryrun = cfg.session.registrationDryRun.toString().toLowerCase()
    regGlobals.roi_name = "wholebrain_mask"
    if (cfg.session.subjectName == undefined) {
      if (cfg.session.sessionNum == undefined) {
        this.setState({error: 'Configurations must define either subjectName or sessionNum to build subjectName'})
        return
      } else {
        regGlobals.subjName = dateStrMDY + cfg.session.sessionNum + '_' + cfg.experiment.experimentName
      }
    } else {
      regGlobals.subjName = cfg.session.subjectName
    }
    var dicomFolder = dateStrYYMD + '.' + regGlobals.subjName + '.' + regGlobals.subjName
    regGlobals.scanFolder = path.join(cfg.session.imgDir, dicomFolder)
    // Set tag line after day 1 only settings
    if (regGlobals.dayNum != 1) {
      var info = { highres: "(Day 1 only)",
                   skullstrip: "(Day 1 only)" }
      var regInfo = Object.assign({}, this.state.regInfo, info)
      this.setState({regInfo: regInfo})
    } else if (this.state.regConfig.dayNum != regGlobals.dayNum && regGlobals.dayNum == 1) {
      // switched back to day 1
      var info = { highres: "", skullstrip: "" }
      var regInfo = Object.assign({}, this.state.regInfo, info)
      this.setState({regInfo: regInfo})
    }
    this.setState({regConfig: regGlobals})

  }

  setConfigFileName(filename) {
    this.setState({configFileName: filename})
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

  clearRunStatus(){
    this.setState({runStatus: ''})
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
    var cmd = {cmd: 'getDefaultConfig'}
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

    if (this.state.regConfig.dayNum == 1 && this.state.regConfig.highresScan == '') {
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
    this.webSocket.send(JSON.stringify(request))
  }

  startRun() {
    // clear previous log output
    this.setState({logLines: []})
    this.setState({error: ''})

    this.formatConfigValues()
    this.webSocket.send(JSON.stringify({cmd: 'run', config: this.state.config}))
  }

  stopRun() {
    this.webSocket.send(JSON.stringify({cmd: 'stop'}))
  }

  formatConfigValues() {
    // After user changes on the web page we need to convert some values from strings
    // First format Runs and ScanNums to be numbers not strings
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

    // Next change all true/false strings to booleans
    // and change all number strings to numbers
    for (let sectionName in this.state.config) {
      var section = this.state.config[sectionName]
      for (let key in section) {
        var modified = false
        if (typeof section[key] === 'string') {
          var value = section[key]
          // check if the string should be a boolean
          switch(value.toLowerCase()) {
            case 'false':
            case 'flase':
            case 'fales':
            case 'flsae':
              section[key] = false
              modified = true
              break;
            case 'true':
            case 'ture':
            case 'treu':
              section[key] = true
              modified = true
              break;
          }
          // check if the string should be a number
          var regex = /^\d+$/;
          if (regex.test(value) == true) {
            section[key] = parseInt(value, 10)
            modified = true
          }
        }
      }
      if (modified) {
        var revConfig = Object.assign({}, this.state.config, { [sectionName]: section })
        this.setState({config: revConfig})
      }
    }
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
      // this.setState({error: ''})
      var cmd = request['cmd']
      if (cmd == 'config') {
        var config = request['value']
        var filesremote = this.state.filesRemote
        if ('filesremote' in request) {
          filesremote = request['filesremote']
        }
        this.setState({config: config, filesRemote: filesremote})
        this.createRegConfig();
      } else if (cmd == 'userLog') {
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
      } else if (cmd == 'runStatus') {
        var status = request['status']
        if (status == undefined || status.length == 0) {
          status = ''
        }
        this.setState({runStatus: status})
      } else if (cmd == 'regStatus') {
        var regType = request['type']
        var status = request['status']
        var regInfo
        if (status == undefined || status.length == 0) {
          regInfo = this.state.regInfo
          delete regInfo[regType]
        } else {
          // var msg = `Procs (${numProcs}): ${procNames}`
          regInfo = Object.assign({}, this.state.regInfo, { [regType]: status })
        }
        this.setState({regInfo: regInfo})
      } else if (cmd == 'uploadProgress') {
        var uploadType = request['type']
        var progress = request['progress']
        var regInfo = Object.assign({}, this.state.regInfo, { [uploadType]: progress })
        this.setState({regInfo: regInfo})
      } else if (cmd == 'error') {
        console.log("## Got Error: " + request['error'])
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
         elem(Tab, {}, 'Registration'),
         elem(Tab, {}, 'Settings'),
       ),
       elem(TabPanel, {},
         elem(StatusPane,
           {logLines: this.state.logLines,
            config: this.state.config,
            connected: this.state.connected,
            runStatus: this.state.runStatus,
            error: this.state.error,
            startRun: this.startRun,
            stopRun: this.stopRun,
            setConfig: this.setConfig,
            getConfigItem: this.getConfigItem,
            setConfigItem: this.setConfigItem,
            clearRunStatus: this.clearRunStatus,
           }
         ),
       ),
       elem(TabPanel, {},
         elem(RegistrationPane,
           {error: this.state.error,
            regLines: this.state.regLines,
            regInfo: this.state.regInfo,
            filesRemote: this.state.filesRemote,
            uploadImages: this.uploadImages,
            runRegistration: this.runRegistration,
            getRegConfigItem: this.getRegConfigItem,
            setRegConfigItem: this.setRegConfigItem,
           }
         ),
       ),
       elem(TabPanel, {},
         elem(SettingsPane,
           {config: this.state.config,
            configFileName: this.state.configFileName,
            setConfig: this.setConfig,
            getConfigItem: this.getConfigItem,
            setConfigItem: this.setConfigItem,
            setConfigFileName: this.setConfigFileName,
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
