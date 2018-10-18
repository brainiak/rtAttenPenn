const React = require('react')
const ReactDOM = require('react-dom')
const toml = require('toml')
const { Tab, Tabs, TabList, TabPanel } = require('react-tabs')
// const ScrollableFeed = require('react-scrollable-feed').default

const elem = React.createElement;


class SettingsPane extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      tomlFile: '',
      tomlErrorMsg: '',
    }
    this.tomlInputForm = this.tomlInputForm.bind(this)
    this.loadTomlFile = this.loadTomlFile.bind(this)
    this.inputOnChange = this.inputOnChange.bind(this)
    this.textInputField = this.textInputField.bind(this)
    this.settingsInputForm = this.settingsInputForm.bind(this)
  }

  tomlInputForm(props) {
    const form =
      elem('fieldset', {},
        elem('legend', {}, 'Select Toml Configuration File:'),
        elem('input', {
          type: 'file',
          onChange: (event) => {
            let reader = new FileReader()
            reader.onload = this.loadTomlFile
            reader.readAsText(event.target.files[0])
          },
        }),
        elem('p', {}, this.state.tomlErrorMsg)
      )
    return form
  }

  loadTomlFile(event) {
    try {
      const configData = toml.parse(event.target.result)
      this.props.setConfig(configData)
    } catch (err) {
      this.setState({ tomlErrorMsg: err.message })
    }
  }

  inputOnChange(event) {
    const section = event.target.attributes.section.value
    var revSection = Object.assign({}, this.props.config[section], { [event.target.name]: event.target.value })
    var revConfig = Object.assign({}, this.props.config, { [section]: revSection })
    this.props.setConfig(revConfig)
  }

  textInputField(props) {
    return elem('p', { key: props.name },
      props.name + ': ',
      elem('input', Object.assign(props, { value: this.props.config[props.section][props.name], onChange: this.inputOnChange })),
    )
  }

  settingsInputForm(props) {
    var formSections = []
    for (let section in this.props.config) {
      let subform = Object.keys(this.props.config[section]).map(k =>
        this.textInputField({ name: k, section: section })
      )
      formSections.push(
        elem('fieldset', { key: section },
          elem('legend', {}, section),
          subform,
        )
      )
    }
    const form =
      elem('fieldset', {},
        elem('legend', {}, 'Configurations'),
        formSections,
      )
    return form
  }

  render() {
    // if (this.errorMsg) {
    // var errElem = elem('span', {}, this.errorMsg)
    // }
    return elem('div', {},
      this.tomlInputForm({}),
      elem('br'),
      this.settingsInputForm({})
    )
  }
}


class StatusPane extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
    }
    // this.scrollRef = React.createRef()
    this.runNumOnChange = this.runNumOnChange.bind(this)
    this.scanNumOnChange = this.scanNumOnChange.bind(this)
    this.runBttnOnClick = this.runBttnOnClick.bind(this)
    this.stopBttnOnClick = this.stopBttnOnClick.bind(this)
  }

  runNumOnChange(event) {
    this.props.setConfigItem('Runs', [event.target.value])
  }

  scanNumOnChange(event) {
    this.props.setConfigItem('ScanNums', [event.target.value])
  }

  runBttnOnClick(event) {
    this.props.startRun()
  }

  stopBttnOnClick(event) {
    this.props.stopRun()
  }

  // componentDidUpdate () {
  //   this.scrollRef.scrollIntoView({ behavior: 'smooth' })
  // }
  // componentDidMount() {
  // }

  render() {
    var errorStr
    if (this.props.error != '') {
      errorStr = "Error: " + this.props.error
    }
    return elem('div', {},
      elem('p', {}, `MRI Scans Directory: ${this.props.getConfigItem('imgDir')}`),
      elem('hr'),
      elem('p', {}, 'Run #: ',
        elem('input', { value: this.props.getConfigItem('Runs'), onChange: this.runNumOnChange }),
      ),
      elem('p', {}, 'Scan #: ',
        elem('input', { value: this.props.getConfigItem('ScanNums'), onChange: this.scanNumOnChange }),
      ),
      elem('button', { onClick: this.runBttnOnClick }, 'Run'),
      elem('button', { onClick: this.stopBttnOnClick }, 'Stop'),
      elem('div', {}, errorStr),
      elem('hr'),
      // elem(ScrollBox, {style: {height: '200px'}, axes: ScrollAxes.Y}, this.props.logLines),
      // elem(ScrollableFeed, {}, this.props.logLines),
      elem('div', {}, this.props.logLines),
    )
  }
}


class RtAtten extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      config: {},
      logLines: [],
      connected: false,
      error: '',
    }
    this.webSocket = null
    this.setConfig = this.setConfig.bind(this);
    this.getConfigItem = this.getConfigItem.bind(this);
    this.setConfigItem = this.setConfigItem.bind(this);
    this.requestDefaultConfig = this.requestDefaultConfig.bind(this)
    this.startRun = this.startRun.bind(this);
    this.stopRun = this.stopRun.bind(this);
    this.createWebSocket = this.createWebSocket.bind(this)
    this.createWebSocket()
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
        var logItem = request['value']
        var itemPos = this.state.logLines.length + 1
        var newLine = elem('div', { key: itemPos }, logItem)
        var logLines = this.state.logLines
        logLines.push(newLine)
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
     elem(Tabs, {},
       elem(TabList, {},
         elem(Tab, {}, 'Run'),
         elem(Tab, {}, 'Settings'),
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
     )
    return tp
  }
}

function Render() {
  const tabDiv = document.getElementById('tabs_container');
  ReactDOM.render(elem(RtAtten), tabDiv);
}

Render()
