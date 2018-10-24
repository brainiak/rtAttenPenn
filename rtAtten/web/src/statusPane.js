const React = require('react')
import AutoscrolledList from "./AutoscrolledList";

const elem = React.createElement;


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
    return (
      elem('div', {},
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
      elem(AutoscrolledList, {items: this.props.logLines}),
      // TODO: for future conversion to JSX format
      // <div>
      //   <button onClick={this.runBttnOnClick}>Run</button>
      //   <button onClick={this.stopBttnOnClick}>Stop</button>
      //   <AutoscrolledList items={this.props.logLines} />
      // </div>
    )
  )
  }
}

module.exports = StatusPane;
