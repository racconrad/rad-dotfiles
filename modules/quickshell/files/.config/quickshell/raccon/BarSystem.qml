import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

Row {
  id: root
  property string iconFont: "Eva-Icons"
  spacing: 5
  height: 38

  property int updateCount: 0

  Process {
    id: updateProc
    command: [Quickshell.env("HOME") + "/.local/bin/raccon-update", "count"]
    stdout: SplitParser {
      onRead: line => {
        try {
          const v = JSON.parse(line);
          root.updateCount = parseInt((v && v.count !== undefined) ? v.count : v) || 0;
        } catch (e) {
          root.updateCount = parseInt(line.trim()) || 0;
        }
      }
    }
  }
  Timer { interval: 7200000; running: true; repeat: true; onTriggered: updateProc.running = true }
  Component.onCompleted: updateProc.running = true

  readonly property var paperColors: Theme.tone("paper")
  readonly property var primaryColors: Theme.tone("primary")

  Paper {
    width: root.updateCount > 0 ? 48 : 0
    height: 34
    implicitWidth: width
    implicitHeight: height
    visible: root.updateCount > 0
    fill: root.paperColors.bg
    ink: Theme.ink
    shadowColor: Theme.secondary
    border: Theme.border
    shadowOffset: 4
    radius: height / 2
    bare: true
    tilt: 0
    Text {
      anchors.centerIn: parent
      text: "\ueab0 " + root.updateCount
      font.family: root.iconFont
      font.pixelSize: 14
      color: root.paperColors.fg
    }
    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: Quickshell.execDetached(["kitty", "-e", Quickshell.env("HOME") + "/.local/bin/raccon-update", "run"])
    }
  }

  IdleInhibitor {
    id: inhibitor
    enabled: false
  }

  Paper {
    width: 30
    height: 34
    implicitWidth: width
    implicitHeight: height
    fill: inhibitor.enabled ? root.primaryColors.bg : root.paperColors.bg
    ink: Theme.ink
    shadowColor: inhibitor.enabled ? Theme.primary : Theme.shadowColor
    border: Theme.border
    shadowOffset: 4
    radius: height / 2
    bare: true
    tilt: 0
    Text {
      anchors.centerIn: parent
      text: inhibitor.enabled ? "\uebb6" : "\ueb33"
      font.family: root.iconFont
      font.pixelSize: 15
      color: inhibitor.enabled ? root.primaryColors.fg : root.paperColors.fg
    }
    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: inhibitor.enabled = !inhibitor.enabled
    }
  }

  Paper {
    width: 30
    height: 34
    implicitWidth: width
    implicitHeight: height
    fill: root.paperColors.bg
    ink: Theme.ink
    shadowColor: Theme.shadowColor
    border: Theme.border
    shadowOffset: 4
    radius: height / 2
    bare: true
    tilt: 0
    Text {
      anchors.centerIn: parent
      text: "\uebb6"
      font.family: root.iconFont
      font.pixelSize: 15
      color: root.paperColors.fg
    }
    WheelHandler {
      onWheel: (event) => {
        Quickshell.execDetached(["swayosd-client", "--brightness", event.angleDelta.y > 0 ? "raise" : "lower"]);
      }
    }
  }
}
