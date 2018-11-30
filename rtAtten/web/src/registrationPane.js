const React = require('react');
import AutoscrolledList from "./AutoscrolledList";
const VNCViewerPane = require('./vncViewerPane.js')

const elem = React.createElement;

// CSS Styles
const table = { display: "table", }
const row = { display: "table-row", }
const cell5p = { display: "table-cell", marginRight:"5px", paddingRight:"5px" }
const cell10p = { display: "table-cell", marginRight:"10px", paddingRight:"10px" }
const hidden = { visibility:"hidden" }


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
    if (this.props.error != '') {
      errorStr = "Error: " + this.props.error
    }

    return (
      <div>
        <p>
          Image Directory: {this.props.getRegConfigItem('scanFolder')}
        </p>
        <div style={table}>
          <p style={row}>
            <label style={cell10p}>Highres</label>
              <label style={cell5p}>Scan#:</label>
              <input style={cell5p} size="5"
                name='highresScan'
                value={this.props.getRegConfigItem('highresScan')}
                onChange={this.inputOnChange}
              />
              <label style={cell5p}>Num Dicoms:</label>
              <input style={cell5p} size="5"
                name='NumHighresDicoms'
                value={this.props.getRegConfigItem('NumHighresDicoms')}
                onChange={this.inputOnChange}
              />
              <button style={cell5p}
                name="highres"
                onClick={this.uploadBttnOnClick}>Upload Highres Images</button>
              <label style={cell5p}>{this.props.regInfo['highres']}</label>
          </p>
          <p style={row}>
            <label style={cell10p}>Functional</label>
              <label style={cell5p}>Scan#:</label>
              <input style={cell5p} size="5"
                name='functionalScan'
                value={this.props.getRegConfigItem('functionalScan')}
                onChange={this.inputOnChange}
              />
              <label style={cell5p}>Num Dicoms: </label>
              <input style={cell5p} size="5"
                name='NumFuncDicoms'
                value={this.props.getRegConfigItem('NumFuncDicoms')}
                onChange={this.inputOnChange}
              />
              <button style={cell5p}
                name="functional"
                onClick={this.uploadBttnOnClick}>Upload Functional Images</button>
              <label style={cell5p}>{this.props.regInfo['functional']}</label>
          </p>
        </div>
        <hr />
        <div style={table}>
          <p style={row}>
            <label style={cell10p}>SkullStrip</label>
            <label style={cell5p}>f param:</label>
            <input style={cell5p} size="5"
              name='fParam'
              value={this.props.getRegConfigItem('fParam')}
              onChange={this.inputOnChange}
            />
            <button style={cell5p} name="skullstrip" onClick={this.runBttnOnClick}>Run</button>
          </p>
          <p style={row}>
            <label style={cell10p}>Registartion</label>
            <label style={cell5p}></label>
            <input style={{...cell5p, ...hidden}} size="5" />
            <button style={cell5p} name="registration" onClick={this.runBttnOnClick}>Run</button>
          </p>
          <p style={row}>
            <label style={cell10p}>Make Mask</label>
            <label style={cell5p}></label>
            <input style={{...cell5p, ...hidden}} size="5" />
            <button style={cell5p} name="makemask" onClick={this.runBttnOnClick}>Run</button>
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

{/*
//   elem('div', {},
//   elem('p', {}, `Image Directory: ${this.props.getRegConfigItem('scanFolder')}`),
//   elem('hr'),
//   elem('p', {}, 'Highres Scan #: ',
//     elem('input', { value: this.props.getRegConfigItem('highresScan'), onChange: this.highresScanOnChange }),
//   ),
//   elem('p', {}, 'Functional Scan #: ',
//     elem('input', { value: this.props.getRegConfigItem('functionalScan'), onChange: this.funcScanOnChange }),
//   ),
//   elem('button', { onClick: this.runBttnOnClick }, 'Run Registration'),
//   elem('button', { onClick: this.stopBttnOnClick }, 'Stop'),
//   elem('div', {}, errorStr),
//   elem('hr'),
//   elem(AutoscrolledList, {items: this.props.regLines, height: "100px"}),
//   elem('hr'),
//   elem(VNCViewerPane, {}),
//   // TODO: for future conversion to JSX format
//   // <div>
//   //   <button onClick={this.runBttnOnClick}>Run</button>
//   //   <button onClick={this.stopBttnOnClick}>Stop</button>
//   //   <AutoscrolledList items={this.props.logLines} />
//   // </div>
// )
*/};

module.exports = RegistrationPane;
