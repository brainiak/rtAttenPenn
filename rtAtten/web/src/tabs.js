const React = require('react')
const ReactDOM = require('react-dom')
const SettingsPane = require('./settingsPane.js')
const StatusPane = require('./statusPane.js')
const VNCViewerPane = require('./vncViewerPane.js')
const { Tab, Tabs, TabList, TabPanel } = require('react-tabs')


const elem = React.createElement;


class RtAtten extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      config: {},
      logLines: [],
      connected: false,
      error: '',
    }
    this.fslTabIndex = 2
    this.webSocket = null
    this.onTabSelected = this.onTabSelected.bind(this);
    this.setConfig = this.setConfig.bind(this);
    this.getConfigItem = this.getConfigItem.bind(this);
    this.setConfigItem = this.setConfigItem.bind(this);
    this.requestDefaultConfig = this.requestDefaultConfig.bind(this)
    this.startRun = this.startRun.bind(this);
    this.stopRun = this.stopRun.bind(this);
    this.createWebSocket = this.createWebSocket.bind(this)
    this.createWebSocket()
  }

  onTabSelected(index, lastIndex, event) {
    if (index == this.fslTabIndex) {
      // show the screen div
      var screenDiv = document.getElementById('screen')
      screenDiv.style.display = "initial";
    } else if (lastIndex == this.fslTabIndex && index != lastIndex){
      // hide the screen div
      var screenDiv = document.getElementById('screen')
      screenDiv.style.display = "none";
    }
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
          return this.setState({config: revConfig})
        }
      }
    }
    return null
  }

  requestDefaultConfig() {
    var cmd = {'cmd': 'getDefaultConfig'}
    var cmdStr = JSON.stringify(cmd)
    this.webSocket.send(cmdStr)
  }

  startRun() {
    // clear previous log output
    this.setState({logLines: []})

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
    var wsUserURL = 'ws://' + location.hostname + ':' + location.port + '/wsUser'
    console.log(wsUserURL)
    var webSocket = new WebSocket(wsUserURL);
    webSocket.onopen = (openEvent) => {
      this.setState({connected: true})
      console.log("WebSocket OPEN: ");
      this.requestDefaultConfig()
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
        this.setState({config: config})
      } else if (cmd == 'log') {
        var logItem = request['value'].trim()
        var itemPos = this.state.logLines.length + 1
        var newLine = elem('pre', { key: itemPos }, logItem)
        var logLines = this.state.logLines
        // console.log(logItem)
        // logLines.push(logItem)
        logLines.push(newLine)
        this.setState({logLines: []}) // if we don't have this it won't know to update
        this.setState({logLines: logLines})
      } else if (cmd == 'error') {
        console.log("## Got Error" + request['error'])
        this.setState({error: request['error']})
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
         elem(Tab, {}, 'FSL'),
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
         elem(VNCViewerPane, {}),
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
