import QtQuick
import QtQuick.Layouts

// Custom duration text input with ink borders and Start CutButton.
RowLayout {
  id: root
  signal launchRequested(string duration)

  spacing: 8

  Rectangle {
    antialiasing: true
    Layout.fillWidth: true
    height: 32
    radius: Theme.radius
    color: Theme.surface_container_highest
    border.width: Theme.border
    border.color: input.activeFocus ? Theme.primary : Theme.ink

    TextInput {
      id: input
      anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
      verticalAlignment: Text.AlignVCenter
      color: Theme.on_surface
      font { family: Theme.fontMono; pixelSize: 13 }
      clip: true
      onAccepted: root.launchRequested(text)

      Text {
        anchors.fill: parent
        verticalAlignment: Text.AlignVCenter
        text: "10m, 45s, 1h30m…"
        color: Theme.on_surface_variant
        font: parent.font
        visible: !parent.text && !parent.activeFocus
      }
    }
  }

  CutButton {
    id: startBtn
    icon: "󰐊"
    text: "START"
    tone: "primary"
    onClicked: root.launchRequested(input.text)
  }
}
