import React from "react";
import autoscroll from "autoscroll-react";

const styles = {
  overflowY: "scroll",
  height: "600px"
};

class List extends React.Component {
  render() {
    const { items } = this.props;

    return (
      <div style={styles} {...this.props}>
        {items.map((item, idx) => <pre key={idx}>{item}</pre>)}
      </div>
    );
  }
}

export default autoscroll(List, { isScrolledDownThreshold: 5 });
