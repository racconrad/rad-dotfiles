import QtQuick
import QtQuick.Shapes

// Decorative backdrop scene with a faint grid, skewed drift polygons, and a translucent highlight.
Item {
  id: root

  property int seed: 1
  property int slices: 3
  property bool animated: true

  implicitWidth: 320
  implicitHeight: 240

  // PRNG helper for deterministic layout
  function pseudoRandom(s) {
    const v = Math.sin(s * 12.9898 + 78.233) * 43758.5453;
    return v - Math.floor(v);
  }

  // Faint background grid painted once
  Canvas {
    id: gridCanvas
    anchors.fill: parent
    renderTarget: Canvas.Image

    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
      const ctx = getContext("2d");
      ctx.reset();
      if (width <= 0 || height <= 0) return;

      const c = Theme.outline_variant;
      ctx.strokeStyle = Qt.rgba(c.r, c.g, c.b, 0.28);
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = 0; x <= width; x += 32) {
        ctx.moveTo(x + 0.5, 0);
        ctx.lineTo(x + 0.5, height);
      }
      for (let y = 0; y <= height; y += 32) {
        ctx.moveTo(0, y + 0.5);
        ctx.lineTo(width, y + 0.5);
      }
      ctx.stroke();
    }
  }

  // Deterministic skewed polygons
  Item {
    id: sliceGroup
    anchors.fill: parent

    Repeater {
      model: root.slices

      Item {
        id: sliceItem
        anchors.fill: parent

        readonly property real r0: root.pseudoRandom(root.seed * 31 + index * 17)
        readonly property real r1: root.pseudoRandom(root.seed * 47 + index * 23)
        readonly property real r2: root.pseudoRandom(root.seed * 71 + index * 29)
        readonly property real r3: root.pseudoRandom(root.seed * 89 + index * 41)

        readonly property color sliceFill: index % 3 === 0 ? Theme.primary_container : (index % 3 === 1 ? Theme.secondary_container : Theme.tertiary_container)

        Shape {
          anchors.fill: parent
          asynchronous: true
          preferredRendererType: Shape.CurveRenderer

          ShapePath {
            strokeWidth: 1
            strokeColor: Theme.outline
            fillColor: sliceItem.sliceFill

            startX: root.width * (0.05 + sliceItem.r0 * 0.3)
            startY: root.height * (0.1 + sliceItem.r1 * 0.3)

            PathLine { x: root.width * (0.45 + sliceItem.r2 * 0.5); y: root.height * (0.05 + sliceItem.r3 * 0.3) }
            PathLine { x: root.width * (0.35 + sliceItem.r1 * 0.5); y: root.height * (0.55 + sliceItem.r0 * 0.4) }
            PathLine { x: root.width * (0.02 + sliceItem.r3 * 0.3); y: root.height * (0.45 + sliceItem.r2 * 0.4) }
            PathLine { x: root.width * (0.05 + sliceItem.r0 * 0.3); y: root.height * (0.1 + sliceItem.r1 * 0.3) }
          }
        }

        SequentialAnimation on y {
          loops: Animation.Infinite
          running: root.animated && root.visible && Theme.animations

          NumberAnimation {
            from: -6
            to: 6
            duration: 4500
            easing.type: Easing.InOutSine
          }
          NumberAnimation {
            from: 6
            to: -6
            duration: 4500
            easing.type: Easing.InOutSine
          }
        }
      }
    }
  }

  // Translucent parallelogram highlight
  Shape {
    anchors.fill: parent
    asynchronous: true
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
      strokeWidth: 0
      strokeColor: "transparent"
      fillColor: Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.12)

      startX: root.width * 0.2
      startY: 0
      PathLine { x: root.width * 0.45; y: 0 }
      PathLine { x: root.width * 0.25; y: root.height }
      PathLine { x: 0; y: root.height }
      PathLine { x: root.width * 0.2; y: 0 }
    }
  }
}
