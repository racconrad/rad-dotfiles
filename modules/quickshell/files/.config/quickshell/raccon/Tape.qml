import QtQuick

// Translucent washi/masking tape strip with tilted angle and optional stripes.
Item {
  id: root

  property color color: Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.55)
  property real tilt: -6
  property bool striped: false

  implicitWidth: 54
  implicitHeight: 16
  width: implicitWidth
  height: implicitHeight

  rotation: root.tilt
  transformOrigin: Item.Center

  Rectangle {
    antialiasing: true
    anchors.fill: parent
    color: root.color
    opacity: root.color.a < 1.0 ? 1.0 : 0.65
    radius: Theme.radius
    border.width: 1
    border.color: Qt.alpha(Theme.ink, 0.25)

    Canvas {
      id: stripeCanvas
      anchors.fill: parent
      visible: root.striped
      onWidthChanged: requestPaint()
      onHeightChanged: requestPaint()
      onPaint: {
        const ctx = getContext("2d");
        ctx.reset();
        ctx.strokeStyle = Qt.alpha(Theme.ink, 0.35);
        ctx.lineWidth = 2;
        for (let x = -height; x < width + height; x += 8) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x + height, height);
          ctx.stroke();
        }
      }
    }
  }
}
