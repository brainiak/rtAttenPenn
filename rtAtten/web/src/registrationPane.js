const React = require('react');
import AutoscrolledList from "./AutoscrolledList";
const VNCViewerPane = require('./vncViewerPane.js')

const elem = React.createElement;


class RegistrationPane extends React.Component {
  constructor(props) {
    super(props)
    this.state = {}
    this.inputOnChange = this.inputOnChange.bind(this)
    this.runBttnOnClick = this.runBttnOnClick.bind(this)
    this.stopBttnOnClick = this.stopBttnOnClick.bind(this)
    this.uploadBttnOnClick = this.uploadBttnOnClick.bind(this)
  }

  inputOnChange(event) {
    var val = event.target.value
    var name = event.target.name
    this.props.setRegConfigItem(name, val)
  }

  runBttnOnClick(event) {
    this.props.runRegistration(event.target.name)
  }

  stopBttnOnClick(event) {
    // this.props.stopRun()
  }

  uploadBttnOnClick(event) {
    var uploadType = event.target.name
    var scanNum = 0
    var numDicoms = 0
    var scanFolder = this.props.getRegConfigItem('scanFolder')
    if (uploadType == 'highres') {
      scanNum = this.props.getRegConfigItem('highresScan')
      numDicoms = this.props.getRegConfigItem('NumHighresDicoms')
    } else if (uploadType == 'functional') {
      scanNum = this.props.getRegConfigItem('functionalScan')
      numDicoms = this.props.getRegConfigItem('NumFuncDicoms')
    }
    this.props.uploadImages(uploadType, scanFolder, scanNum, numDicoms)
  }

  render() {
    var errorStr
    var day1Input
    if (this.props.error != '') {
      errorStr = "Error: " + this.props.error
    }
    if (this.props.getRegConfigItem('dayNum') != 1) {
      day1Input = "disabled"
    }

    return (
      <div>
        <p>
          Image Directory: {this.props.getRegConfigItem('scanFolder')}
        </p>
        <div className="table">
          <p className={`row ${day1Input}`}>
            <label className="cell10p">Highres</label>
              <label className="cell5p">Scan#:</label>
              <input className="cell5p" size="5"
                name='highresScan'
                value={this.props.getRegConfigItem('highresScan')}
                onChange={this.inputOnChange}
              />
              <label className="cell5p">Num Dicoms:</label>
              <input className="cell5p" size="5"
                name='NumHighresDicoms'
                value={this.props.getRegConfigItem('NumHighresDicoms')}
                onChange={this.inputOnChange}
              />
              <button className="cell5p"
                name="highres"
                onClick={this.uploadBttnOnClick}>Upload Highres Images</button>
              <label className="cell5p">{this.props.regInfo['highres']}</label>
          </p>
          <p className="row">
            <label className="cell10p">Functional</label>
              <label className="cell5p">Scan#:</label>
              <input className="cell5p" size="5"
                name='functionalScan'
                value={this.props.getRegConfigItem('functionalScan')}
                onChange={this.inputOnChange}
              />
              <label className="cell5p">Num Dicoms: </label>
              <input className="cell5p" size="5"
                name='NumFuncDicoms'
                value={this.props.getRegConfigItem('NumFuncDicoms')}
                onChange={this.inputOnChange}
              />
              <button className="cell5p"
                name="functional"
                onClick={this.uploadBttnOnClick}>Upload Functional Images</button>
              <label className="cell5p">{this.props.regInfo['functional']}</label>
          </p>
        </div>
        <hr />
        <div className="table">
          <p className={`row ${day1Input}`}>
            <label className="cell10p">SkullStrip</label>
            <label className="cell5p">f param:</label>
            <input className="cell5p" size="5"
              name='fParam'
              value={this.props.getRegConfigItem('fParam')}
              onChange={this.inputOnChange}
            />
            <button className="cell5p" name="skullstrip" onClick={this.runBttnOnClick}>Run</button>
            <label className="cell5p">{this.props.regInfo['skullstrip']}</label>
          </p>
          <p className="row">
            <label className="cell10p">Registartion</label>
            <label className="cell5p"></label>
            <input className="cell5p hidden" size="5" />
            <button className="cell5p" name="registration" onClick={this.runBttnOnClick}>Run</button>
            <label className="cell5p">{this.props.regInfo['registration']}</label>
          </p>
          <p className="row">
            <label className="cell10p">Make Mask</label>
            <label className="cell5p"></label>
            <input className="cell5p hidden" size="5" />
            <button className="cell5p" name="makemask" onClick={this.runBttnOnClick}>Run</button>
            <label className="cell5p">{this.props.regInfo['makemask']}</label>
          </p>
        </div>
        <p> {errorStr} </p>
        <hr />
        <AutoscrolledList items={this.props.regLines} height="100px" />
        <hr />
        <VNCViewerPane />
      </div>
    );
  }
}

module.exports = RegistrationPane;
