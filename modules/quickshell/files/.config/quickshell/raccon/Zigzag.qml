import QtQuick
import QtQuick.Shapes

// Torn-paper edge strip rendered as a geometric zigzag polygon.
Item {
  id: root

  property color color: Theme.ink
  property string edge: "bottom"
  property int teeth: 12
  property int depth: 6

  implicitWidth: (edge === "top" || edge === "bottom") ? 120 : depth
  implicitHeight: (edge === "left" || edge === "right") ? 120 : depth

  function generatePoints() {
    const pts = [];
    const t = Math.max(1, root.teeth);
    const d = root.depth;
    const w = root.width;
    const h = root.height;

    if (root.edge === "bottom") {
      pts.push(Qt.point(0, 0));
      pts.push(Qt.point(w, 0));
      const step = w / t;
      for (let i = t; i >= 0; i--) {
        const x = i * step;
        const y = (i % 2 === 1) ? d : 0;
        pts.push(Qt.point(x, y));
      }
    } else if (root.edge === "top") {
      pts.push(Qt.point(w, h));
      pts.push(Qt.point(0, h));
      const step = w / t;
      for (let i = 0; i <= t; i++) {
        const x = i * step;
        const y = (i % 2 === 1) ? 0 : h;
        pts.push(Qt.point(x, y));
      }
    } else if (root.edge === "right") {
      pts.push(Qt.point(0, 0));
      pts.push(Qt.point(0, h));
      const step = h / t;
      for (let i = t; i >= 0; i--) {
        const y = i * step;
        const x = (i % 2 === 1) ? d : 0;
        pts.push(Qt.point(x, y));
      }
    } else {
      pts.push(Qt.point(w, h));
      pts.push(Qt.point(w, 0));
      const step = h / t;
      for (let i = 0; i <= t; i++) {
        const y = i * step;
        const x = (i % 2 === 1) ? 0 : w;
        pts.push(Qt.point(x, y));
      }
    }
    return pts;
  }

  Shape {
    anchors.fill: parent
    asynchronous: true
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
      strokeWidth: 0
      strokeColor: "transparent"
      fillColor: root.color

      PathPolyline {
        path: root.generatePoints()
      }
    }
  }
}
