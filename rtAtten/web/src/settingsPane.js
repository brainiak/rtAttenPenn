const React = require('react')
const toml = require('toml')

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

module.exports = SettingsPane;
