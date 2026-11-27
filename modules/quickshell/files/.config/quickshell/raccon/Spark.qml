import QtQuick
import QtQuick.Shapes

// 4-point geometric star with continuous spinning capability.
Item {
  id: root

  property color color: Theme.primary
  property int size: 18
  property real spin: 0
  property real tilt: 0
  rotation: root.tilt

  implicitWidth: root.size
  implicitHeight: root.size
  width: root.size
  height: root.size

  readonly property real cx: root.width / 2
  readonly property real cy: root.height / 2
  readonly property real rOuter: root.size / 2
  readonly property real rInner: root.size * 0.22

  Shape {
    id: starShape
    anchors.fill: parent
    asynchronous: true
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
      strokeWidth: 0
      strokeColor: "transparent"
      fillColor: root.color

      PathPolyline {
        path: [
          Qt.point(root.cx, root.cy - root.rOuter),
          Qt.point(root.cx + root.rInner, root.cy - root.rInner),
          Qt.point(root.cx + root.rOuter, root.cy),
          Qt.point(root.cx + root.rInner, root.cy + root.rInner),
          Qt.point(root.cx, root.cy + root.rOuter),
          Qt.point(root.cx - root.rInner, root.cy + root.rInner),
          Qt.point(root.cx - root.rOuter, root.cy),
          Qt.point(root.cx - root.rInner, root.cy - root.rInner),
          Qt.point(root.cx, root.cy - root.rOuter)
        ]
      }
    }
  }

  NumberAnimation on rotation {
    from: 0
    to: 360
    duration: root.spin !== 0 ? Math.max(10, Math.abs(360 / root.spin) * 1000) : 1000
    loops: Animation.Infinite
    running: root.spin !== 0 && root.visible && Theme.animations
  }
}
