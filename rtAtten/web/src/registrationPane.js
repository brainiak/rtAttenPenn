const React = require('react');
import AutoscrolledList from "./AutoscrolledList";
const VNCViewerPane = require('./vncViewerPane.js')

const elem = React.createElement;


class RegistrationPane extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
    }
    this.highresScanOnChange = this.highresScanOnChange.bind(this)
    this.funcScanOnChange = this.funcScanOnChange.bind(this)
    this.runBttnOnClick = this.runBttnOnClick.bind(this)
    this.stopBttnOnClick = this.stopBttnOnClick.bind(this)
  }


  highresScanOnChange(event) {
    this.props.setRegConfigItem('highresScan', parseInt(event.target.value))
  }

  funcScanOnChange(event) {
    this.props.setRegConfigItem('functionalScan', parseInt(event.target.value))
  }

  runBttnOnClick(event) {
    this.props.runRegistration()
  }

  stopBttnOnClick(event) {
    // this.props.stopRun()
  }

  render() {
    var errorStr
    if (this.props.error != '') {
      errorStr = "Error: " + this.props.error
    }
    return (
      elem('div', {},
      elem('p', {}, `Image Directory: ${this.props.getRegConfigItem('scanFolder')}`),
      elem('hr'),
      elem('p', {}, 'Highres Scan #: ',
        elem('input', { value: this.props.getRegConfigItem('highresScan'), onChange: this.highresScanOnChange }),
      ),
      elem('p', {}, 'Functional Scan #: ',
        elem('input', { value: this.props.getRegConfigItem('functionalScan'), onChange: this.funcScanOnChange }),
      ),
      elem('button', { onClick: this.runBttnOnClick }, 'Run Registration'),
      elem('button', { onClick: this.stopBttnOnClick }, 'Stop'),
      elem('div', {}, errorStr),
      elem('hr'),
      elem(AutoscrolledList, {items: this.props.regLines, height: "100px"}),
      elem('hr'),
      elem(VNCViewerPane, {}),
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

module.exports = RegistrationPane;
