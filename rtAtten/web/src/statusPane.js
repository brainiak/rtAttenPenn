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
      <div>
        <p>MRI Scans Directory: {this.props.getConfigItem('imgDir')}</p>
        <hr />
        <div className="table">
          <p className="row">
            <label className="cell10p">Run #:</label>
            <input className="cell5p" size="20"
              value={this.props.getConfigItem('Runs')}
              onChange={this.runNumOnChange} />
          </p>
          <p className="row">
            <label className="cell10p">Scan #:</label>
            <input className="cell5p" size="20"
              value={this.props.getConfigItem('ScanNums')}
              onChange={this.scanNumOnChange} />
          </p>
        </div>
        <button onClick={this.runBttnOnClick}>Run</button>
        <button onClick={this.stopBttnOnClick}>Stop</button>
        <p>{errorStr}</p>
        <hr />
        <AutoscrolledList items={this.props.logLines} height="600px" />
      </div>
    );
  }
}

module.exports = StatusPane;
