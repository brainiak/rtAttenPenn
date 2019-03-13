const React = require('react')
import {XYPlot, FlexibleXYPlot, XAxis, YAxis, HorizontalGridLines, LineSeries, LineMarkSeries} from 'react-vis';

function yTickFormat(val) {
  var label = ''
  if (val == 1) {
    label = 'Scene'
  } else if (val == -1) {
    label = 'Face'
  }
  return (<tspan>{label}</tspan>)
}

class XYPlotPane extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
    }
    this.renderRunGraph = this.renderRunGraph.bind(this);
  }

  renderRunGraph(runClassVals, runId) {
    var numPoints = runClassVals.length
    var xHigh = (numPoints > 100) ? numPoints : 100
    var xLow = xHigh - 100
    var xRange = [xLow, xHigh]
    var uniqueKey = runId.toString() // + '.' + numPoints.toString()
    var plotColor = '#E0E0E0'
    var plotMargins = {left: 60, right: 20, top: 10, bottom: 40}
    var axesStyle = {
      text: {stroke: 'none', fill: plotColor, fontSize: '0.9em'}
    }
    return (
      <div key={uniqueKey}>
        <p>Run {runId}</p>
        <XYPlot
          width={900}
          height={300}
          xDomain={xRange}
          yDomain={[-1, 1]}
          margin={plotMargins}
        >
          <HorizontalGridLines />
          <LineMarkSeries
            animation
            color={plotColor}
            data={runClassVals}/>
          <XAxis style={axesStyle} tickTotal={11} title="TR" />
          <YAxis style={axesStyle} tickFormat={yTickFormat} tickPadding={5}/>
        </XYPlot>
        <br />
      </div>
    )
  }

  render() {
    var numRuns = this.props.classVals.length
    var plots = []
    for (let i = 0; i < numRuns; i++) {
      if (this.props.classVals[i].length != 0) {
        plots[i] = this.renderRunGraph(this.props.classVals[i], i+1)
      }
    }
    return (
      <div>
        <br />
        <p>Face/Scene Attention Classification vs. Trial</p>
        {plots}
      </div>
    )
  }
}

module.exports = XYPlotPane;
