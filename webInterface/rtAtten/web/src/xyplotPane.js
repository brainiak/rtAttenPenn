const React = require('react')
import {XYPlot, FlexibleXYPlot, XAxis, YAxis, HorizontalGridLines, LineSeries, LineMarkSeries} from 'react-vis';


class XYPlotPane extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
    }
  }

  render() {
    var numPoints = this.props.classVals.length
    var xHigh = (numPoints > 100) ? numPoints : 100
    var xLow = xHigh - 100
    var xRange = [xLow, xHigh]
    return (
      <div>
        <br />
        <p>Face Scene Classification Result vs Time</p>
        <XYPlot
          width={800}
          height={300}
          xDomain={xRange}
          yDomain={[0, 1]}>
          <HorizontalGridLines />
          <LineMarkSeries
            animation
            color="white"
            data={this.props.classVals}/>
          <XAxis title="Classification Trial" />
          <YAxis title="Face:0 or Scene:1 classification" />
        </XYPlot>
      </div>
    )
  }
}

module.exports = XYPlotPane;
