import QtQuick
import Quickshell
import Quickshell.Services.Pipewire

Row {
  id: root
  property string iconFont: "Eva-Icons"
  spacing: 5
  height: 38

  readonly property var sink: Pipewire.defaultAudioSink
  readonly property int volume: Math.round(((sink && sink.audio) ? sink.audio.volume : 1.0) * 100)
  readonly property bool muted: Boolean(sink && sink.audio && sink.audio.muted)
  readonly property var volumeColors: root.muted ? Theme.tone("error") : Theme.tone("paper")
  readonly property var paperColors: Theme.tone("paper")

  Paper {
    width: 52
    height: 34
    implicitWidth: width
    implicitHeight: height
    fill: root.volumeColors.bg
    ink: Theme.ink
    shadowColor: root.muted ? Theme.error : Theme.shadowColor
    border: Theme.border
    shadowOffset: 4
    radius: height / 2
    bare: true
    tilt: 0
    Text {
      anchors.centerIn: parent
      text: (root.muted ? "\uebe2 " : "\uebe6 ") + root.volume + "%"
      font.family: root.iconFont
      font.pixelSize: 13
      color: root.volumeColors.fg
    }

    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      cursorShape: Qt.PointingHandCursor
      onClicked: (mouse) => {
        if (mouse.button === Qt.RightButton)
          Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/desktop-panel", "audio"]);
        else if (root.sink && root.sink.audio)
          root.sink.audio.muted = !root.sink.audio.muted;
      }
    }
    WheelHandler {
      onWheel: (event) => {
        Quickshell.execDetached(["swayosd-client", "--output-volume", event.angleDelta.y > 0 ? "raise" : "lower"]);
      }
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
      text: "\uea48"
      font.family: root.iconFont
      font.pixelSize: 15
      color: root.paperColors.fg
    }
    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/desktop-panel", "bluetooth"])
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
      text: "\uebea"
      font.family: root.iconFont
      font.pixelSize: 15
      color: root.paperColors.fg
    }
    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/desktop-panel", "connections"])
    }
  }
}
