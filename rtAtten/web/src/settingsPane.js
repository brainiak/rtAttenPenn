const React = require('react')
const toml = require('toml')

const elem = React.createElement;


class SettingsPane extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      tomlErrorMsg: '',
    }
    this.tomlInputForm = this.tomlInputForm.bind(this)
    this.loadTomlFile = this.loadTomlFile.bind(this)
    this.inputOnChange = this.inputOnChange.bind(this)
    this.textInputField = this.textInputField.bind(this)
    this.settingsInputForm = this.settingsInputForm.bind(this)
  }

  tomlInputForm(props) {
    const form = (
        <fieldset>
          <legend>Select Toml Configuration File:</legend>
          <p>Current Config: {this.props.configFileName}</p>
          <input type='file' className='inputfile' title='My Title'
            onChange={(event) => {
              this.props.setConfigFileName(event.target.files[0].name)
              let reader = new FileReader()
              reader.onload = this.loadTomlFile
              reader.readAsText(event.target.files[0])
            }}
          />
          <p>{this.state.tomlErrorMsg}</p>
        </fieldset>
      );
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
    return (
      <div key={props.name} className="row">
        <label className="cell10p">{props.name}:</label>
        <input className="cell5p" size="20"
          {...props}
          value={this.props.config[props.section][props.name]}
          onChange={this.inputOnChange} />
      </div>
    );
  }

  settingsInputForm(props) {
    var formSections = []
    for (let section in this.props.config) {
      let subform = Object.keys(this.props.config[section]).map(k =>
        this.textInputField({ name: k, section: section })
      )
      formSections.push(
        <fieldset key={section}>
          <legend>{section}</legend>
          <div className="table">{subform}</div>
        </fieldset>
      );
    }
    const form = (
      <fieldset>
        <legend>Configurations</legend>
        <div>{formSections}</div>
      </fieldset>
    );
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

module.exports = SettingsPane;
