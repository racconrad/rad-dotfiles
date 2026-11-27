import QtQuick
import QtQuick.Layouts

// Collage status banner with 2px ink border, hard accent shadow, and rotating indicator.
Rectangle {
  antialiasing: true
  id: root

  property string status
  property string message
  property bool waiting: false
  property bool retry: false
  signal retryRequested

  readonly property bool isError: status === "error"
  readonly property var colors: isError ? Theme.tone("error") : (waiting || status === "ready" ? Theme.tone("primary") : Theme.tone("paper"))

  implicitHeight: row.implicitHeight + 14
  radius: Theme.radius
  border.width: Theme.border
  border.color: Theme.ink
  color: root.colors.bg

  // Hard accent shadow
  Rectangle {
    antialiasing: true
    z: -1
    anchors.fill: parent
    anchors.margins: -3
    anchors.leftMargin: 3
    anchors.topMargin: 3
    color: root.isError ? Theme.error : Theme.shadowColor
    radius: Theme.radius
  }

  RowLayout {
    id: row
    anchors { fill: parent; leftMargin: 10; rightMargin: 10; topMargin: 6; bottomMargin: 6 }
    spacing: 8

    // Rotating indicator
    Text {
      id: spinner
      visible: root.waiting
      text: "󰑐"
      color: root.colors.fg
      font { family: Theme.fontMono; pixelSize: 14 }
      RotationAnimation on rotation {
        running: spinner.visible && Theme.animations
        from: 0; to: 360; duration: 1000
        loops: Animation.Infinite
        onStopped: spinner.rotation = 0
      }
    }

    Rectangle {
      antialiasing: true
      Layout.preferredWidth: 8
      Layout.preferredHeight: 8
      radius: Theme.radius
      color: root.colors.fg
      visible: !root.waiting
    }

    Text {
      Layout.fillWidth: true
      text: root.message
      textFormat: Text.PlainText
      wrapMode: Text.Wrap
      color: root.colors.fg
      font { family: Theme.fontTag; pixelSize: 12; weight: Font.Bold }
    }

    CutButton {
      visible: root.retry
      text: "RETRY"
      tone: "primary"
      onClicked: root.retryRequested()
    }
  }
}
