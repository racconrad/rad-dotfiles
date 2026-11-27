import QtQuick

// Dot grid painted once with Canvas; repaints only on size or color changes.
Item {
  id: root

  property color color: Theme.ink
  property int spacing: 8
  property real dot: 1.4

  implicitWidth: 100
  implicitHeight: 100

  Canvas {
    id: canvas
    anchors.fill: parent
    renderTarget: Canvas.Image

    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
      const ctx = getContext("2d");
      ctx.reset();
      if (root.spacing <= 0 || root.dot <= 0 || width <= 0 || height <= 0) return;

      ctx.fillStyle = root.color;
      const r = root.dot / 2;
      const s = root.spacing;

      ctx.beginPath();
      for (let x = s / 2; x < width; x += s) {
        for (let y = s / 2; y < height; y += s) {
          ctx.moveTo(x + r, y);
          ctx.arc(x, y, r, 0, Math.PI * 2);
        }
      }
      ctx.fill();
    }
  }

  onColorChanged: canvas.requestPaint()
  onSpacingChanged: canvas.requestPaint()
  onDotChanged: canvas.requestPaint()
}
