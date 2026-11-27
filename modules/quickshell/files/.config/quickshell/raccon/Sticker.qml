import QtQuick

// Bold paper sticker with uppercase display font and ink border.
Item {
  id: root

  property string text: ""
  property string tone: "primary"
  property real tilt: 0

  rotation: root.tilt
  transformOrigin: Item.Center

  readonly property var toneColor: Theme.tone(root.tone)
  readonly property int padH: 8
  readonly property int padV: 4

  implicitWidth: label.implicitWidth + padH * 2
  implicitHeight: label.implicitHeight + padV * 2
  width: implicitWidth
  height: implicitHeight

  Rectangle {
    antialiasing: true
    anchors.fill: parent
    color: root.toneColor.bg
    radius: Theme.radius
    border.width: Theme.border
    border.color: Theme.ink

    Text {
      id: label
      anchors.centerIn: parent
      text: root.text.toUpperCase()
      color: root.toneColor.fg
      font.family: Theme.fontDisplay
      font.weight: 800
      font.pixelSize: 12
      font.letterSpacing: 1
    }
  }
}
