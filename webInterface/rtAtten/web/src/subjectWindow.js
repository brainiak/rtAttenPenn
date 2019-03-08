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
      if (cmd == 'feedbackImage') {
        this.onDeckImageData = request['data']
        //  TODO remove this and only update on ttlPulse
        this.setState({ imageData: this.onDeckImageData })
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
    var imgData = "data:image/jpeg;base64," + this.state.imageData

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
        <img src={imgData} alt="Waiting for feedback images ..." />
      </div>
    )
    // <img src={this.state.feedbackImage} alt={`No Image ${this.state.feedbackImage}`} />
  }
}

function Render() {
  const pageDiv = document.getElementById('display');
  ReactDOM.render(elem(SubjectDisplay), pageDiv);
}

Render()
