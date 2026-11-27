import QtQuick

// Corner tab with monospaced tag font, ink border, and hard accent shadow.
Item {
  id: root

  property string text: ""
  property string tone: "primary"
  property real tilt: -2

  rotation: root.tilt
  transformOrigin: Item.TopLeft

  readonly property var toneColor: Theme.tone(root.tone)

  implicitWidth: body.width + 4
  implicitHeight: body.height + 4
  width: implicitWidth
  height: implicitHeight

  // Hard accent shadow
  Rectangle {
    antialiasing: true
    x: 3
    y: 3
    width: body.width
    height: body.height
    color: root.toneColor.shadow
    radius: Theme.radius
  }

  // Main tab piece
  Rectangle {
    antialiasing: true
    id: body
    width: label.implicitWidth + 12
    height: label.implicitHeight + 6
    color: root.toneColor.bg
    radius: Theme.radius
    border.width: Theme.border
    border.color: Theme.ink

    Text {
      id: label
      anchors.centerIn: parent
      text: root.text.toUpperCase()
      color: root.toneColor.fg
      font.family: Theme.fontTag
      font.pixelSize: 12
      font.weight: 800
      font.letterSpacing: 0.5
    }
  }
}
