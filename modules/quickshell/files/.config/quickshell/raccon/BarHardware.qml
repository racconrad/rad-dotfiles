import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root
  property string iconFont: "Eva-Icons"
  property bool open: false

  property int cpuPercent: 0
  property int memPercent: 0
  property int tempC: 40
  property int diskRoot: 0
  property int diskHome: 0

  readonly property var colors: Theme.tone("paper")

  implicitWidth: open ? (drawerRow.width + 48) : 34
  implicitHeight: 34
  width: implicitWidth
  height: implicitHeight
  Behavior on implicitWidth {
    enabled: Theme.animations
    NumberAnimation { duration: Theme.motionBase; easing.type: Easing.OutBack }
  }

  Process {
    id: hwProc
    command: ["sh", "-c", "printf '%s|%s|%s|%s|%s' \"$(awk '/cpu /{print int(($2+$4)*100/($2+$4+$5))}' /proc/stat)\" \"$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print int((t-a)*100/t)}' /proc/meminfo)\" \"$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print int($1/1000)}')\" \"$(df --output=pcent / | tail -1 | tr -d ' %')\" \"$(df --output=pcent $HOME | tail -1 | tr -d ' %')\""]
    stdout: SplitParser {
      onRead: line => {
        const p = line.trim().split("|");
        if (p.length >= 5) {
          root.cpuPercent = parseInt(p[0]) || 0;
          root.memPercent = parseInt(p[1]) || 0;
          root.tempC = parseInt(p[2]) || 40;
          root.diskRoot = parseInt(p[3]) || 0;
          root.diskHome = parseInt(p[4]) || 0;
        }
      }
    }
  }

  Timer {
    running: root.open
    interval: 2000
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!hwProc.running) hwProc.running = true
  }

  Paper {
    id: hwPaper
    width: root.width
    height: root.height
    implicitWidth: width
    implicitHeight: height
    fill: root.colors.bg
    ink: Theme.ink
    shadowColor: Theme.primary
    border: Theme.border
    shadowOffset: 4
    radius: height / 2
    bare: true
    tilt: 0
    clip: true


    Row {
      anchors.left: parent.left
      anchors.leftMargin: 10
      anchors.verticalCenter: parent.verticalCenter
      spacing: 8

      Text {
        text: "\ueb91"
        font.family: root.iconFont
        font.pixelSize: 15
        color: root.colors.fg
        anchors.verticalCenter: parent.verticalCenter
        MouseArea {
          anchors.fill: parent
          cursorShape: Qt.PointingHandCursor
          onClicked: root.open = !root.open
        }
      }

      Row {
        id: drawerRow
        spacing: 8
        visible: root.open
        opacity: root.open ? 1 : 0
        Behavior on opacity {
          enabled: Theme.animations
          NumberAnimation { duration: Theme.motionFast }
        }

        Text {
          text: "\uea02 " + root.cpuPercent + "%"
          font.family: Theme.fontMono
          font.pixelSize: 12
          color: root.colors.fg
          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: Quickshell.execDetached(["kitty", "-e", "btop"])
          }
        }
        Text {
          text: "\ueaf1 " + root.memPercent + "%"
          font.family: Theme.fontMono
          font.pixelSize: 12
          color: root.colors.fg
        }
        Text {
          text: "\uebc0 " + root.tempC + "°"
          font.family: Theme.fontMono
          font.pixelSize: 12
          color: root.tempC > 80 ? Theme.tone("error").bg : root.colors.fg
        }
        Text {
          text: "/ " + root.diskRoot + "%"
          font.family: Theme.fontMono
          font.pixelSize: 12
          color: root.colors.fg
        }
        Text {
          text: "~ " + root.diskHome + "%"
          font.family: Theme.fontMono
          font.pixelSize: 12
          color: root.colors.fg
        }
      }
    }
  }
}
