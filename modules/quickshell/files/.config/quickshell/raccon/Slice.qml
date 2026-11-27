import QtQuick
import QtQuick.Shapes

// Diagonal ink band rendered via geometric polygon without blur.
Item {
  id: root

  property color color: Theme.ink
  property real angle: -12

  implicitWidth: 64
  implicitHeight: 16

  readonly property real rad: root.angle * Math.PI / 180
  readonly property real shift: Math.tan(rad) * root.height

  Shape {
    anchors.fill: parent
    asynchronous: true
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
      strokeWidth: 0
      strokeColor: "transparent"
      fillColor: root.color

      startX: Math.max(0, root.shift)
      startY: 0
      PathLine { x: Math.max(0, root.width + Math.min(0, root.shift)); y: 0 }
      PathLine { x: Math.max(0, root.width - Math.max(0, root.shift)); y: root.height }
      PathLine { x: Math.max(0, -root.shift); y: root.height }
      PathLine { x: Math.max(0, root.shift); y: 0 }
    }
  }
}
