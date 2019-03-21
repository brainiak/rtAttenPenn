const React = require('react')
const ReactDOM = require('react-dom')
const fs = require('fs')

const elem = React.createElement
var refreshCount = 0
var startTime

class SubjectDisplay extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      connected: false,
      imageData: '',
      message: 'Waiting for run to start ...',
      error: '',
    }
    this.onDeckImageData = ''
    this.createWebSocket = this.createWebSocket.bind(this)
    this.createWebSocket()
  }

  createWebSocket() {
    var wsSubjURL = 'wss://' + location.hostname + ':' + location.port + '/wsSubject'
    console.log(wsSubjURL)
    var webSocket = new WebSocket(wsSubjURL);
    webSocket.onopen = (openEvent) => {
      this.setState({connected: true})
      console.log("WebSocket OPEN: ");
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
      var cmd = request['cmd']
      if (cmd == 'subjectDisplay') {
        var msg = ('text' in request) ? request['text'] : ''
        var img = ('data' in request) ? request['data'] : ''
        this.onDeckImageData = img
        // TODO - wait for ttl pulse before showing image
        this.setState({imageData: img, message: msg})
      } else if (cmd == 'ttlPulse') {
        console.log('ttlPulse')
        // update the subject image display
        // this.setState({ imageData: this.onDeckImageData })
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
    var mainItem
    if (this.state.imageData == '') {
      const pstyle = {textalign: 'center', fontSize: '1.5em'}
      mainItem = (
        <div className="pageCenter">
          <p style={pstyle}> {this.state.message} </p>
        </div>
      )
    } else {
      var imgData = "data:image/jpeg;base64," + this.state.imageData
      mainItem = (<img src={imgData} alt="Waiting for feedback images ..." />)
      // <img src={this.state.feedbackImage} alt={`No Image ${this.state.feedbackImage}`} />
    }

    if (refreshCount == 0) {
      startTime = Date.now()
    } else if (refreshCount > 100) {
      let elapsedTime = Date.now() - startTime
      console.log('Displayed 100 images in %d ms', elapsedTime)
      refreshCount = 0
    }
    refreshCount++

    return (
      <div>
        {mainItem}
      </div>
    )
  }
}

function Render() {
  const pageDiv = document.getElementById('display');
  ReactDOM.render(elem(SubjectDisplay), pageDiv);
}

Render()
