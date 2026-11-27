import QtQuick
import Quickshell

Row {
  id: root
  property string iconFont: "Eva-Icons"
  spacing: 5
  height: 38

  property string timeString: ""
  property string dateString: ""

  readonly property var clockColors: Theme.tone("primary")
  readonly property var paperColors: Theme.tone("paper")
  readonly property var errColors: Theme.tone("error")

  function updateTime() {
    const d = new Date();
    root.timeString = Qt.formatTime(d, "hh:mm");
    root.dateString = Qt.formatDate(d, "ddd d MMM");
  }

  Timer {
    interval: 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.updateTime()
  }

  Paper {
    width: 30
    height: 34
    implicitWidth: width
    implicitHeight: height
    fill: root.paperColors.bg
    ink: Theme.ink
    shadowColor: "transparent"
    border: 0
    shadowOffset: 4
    radius: height / 2
    bare: true
    tilt: 0
    Text {
      anchors.centerIn: parent
      text: "\ueb92"
      font.family: root.iconFont
      font.pixelSize: 15
      color: root.paperColors.fg
    }
    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/display-mode"])
    }
  }

  Paper {
    id: clockPaper
    width: clockRow.width + 20
    height: 34
    implicitWidth: width
    implicitHeight: height
    fill: root.clockColors.bg
    ink: Theme.ink
    shadowColor: "transparent"
    border: 0
    shadowOffset: 4
    radius: height / 2
    bare: true
    tilt: 0
    Row {
      id: clockRow
      anchors.centerIn: parent
      spacing: 8

      Text {
        text: root.timeString
        font.family: Theme.fontDisplay
        font.pixelSize: 15
        font.weight: 800
        color: root.clockColors.fg
        anchors.verticalCenter: parent.verticalCenter
      }

      Sticker {
        text: root.dateString
        tone: "primary"
        tilt: 2.0
        anchors.verticalCenter: parent.verticalCenter
      }
    }

    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/desktop-panel", "calendar"])
    }
  }

  Paper {
    width: 30
    height: 34
    implicitWidth: width
    implicitHeight: height
    fill: root.errColors.bg
    ink: Theme.ink
    shadowColor: "transparent"
    border: 0
    shadowOffset: 4
    radius: height / 2
    tilt: 0
    Text {
      anchors.centerIn: parent
      text: "\ueb70"
      font.family: root.iconFont
      font.pixelSize: 16
      color: root.errColors.fg
    }
    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/raccon-float", "session"])
    }
  }
}
