import QtQuick
import Quickshell
import Quickshell.Services.Mpris

Item {
  id: root
  property string iconFont: "Eva-Icons"

  readonly property var player: {
    const all = (Mpris.players && Mpris.players.values) ? Mpris.players.values : [];
    const p = all.find(item => item && item.isPlaying);
    return p ? p : (all.length > 0 ? all[0] : null);
  }
  readonly property bool isPlaying: Boolean(player && player.isPlaying)
  readonly property var colors: Theme.tone("tertiary")

  implicitWidth: isPlaying ? 220 : 34
  implicitHeight: 34
  width: implicitWidth
  height: implicitHeight
  Behavior on implicitWidth { enabled: Theme.animations; NumberAnimation { duration: Theme.motionBase; easing.type: Easing.OutBack } }

  Paper {
    id: musicPaper
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
    tilt: isPlaying ? 0.8 : -1.2

    Halftone {
      anchors.fill: parent
      color: Qt.rgba(Theme.ink.r, Theme.ink.g, Theme.ink.b, 0.08)
      visible: root.isPlaying
    }


    Row {
      anchors.fill: parent
      anchors.margins: 6
      spacing: 6
      visible: root.isPlaying

      Spectrum {
        active: root.isPlaying
        anchors.verticalCenter: parent.verticalCenter
        height: 18
      }

      Column {
        anchors.verticalCenter: parent.verticalCenter
        width: 100
        clip: true

        Text {
          text: (root.player && root.player.trackTitle) ? root.player.trackTitle : "Music"
          font.family: Theme.fontDisplay
          font.pixelSize: 12
          font.weight: 800
          color: root.colors.fg
          elide: Text.ElideRight
          width: parent.width
        }
        Text {
          text: (root.player && root.player.trackArtist) ? root.player.trackArtist : ""
          font.family: Theme.fontTag
          font.pixelSize: 12
          color: Theme.on_surface_variant
          elide: Text.ElideRight
          width: parent.width
          visible: text.length > 0
        }
      }

      Text {
        text: "\ueba5"
        font.family: root.iconFont
        font.pixelSize: 16
        color: root.colors.fg
        anchors.verticalCenter: parent.verticalCenter
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (root.player) root.player.previous() }
      }

      Text {
        text: root.isPlaying ? "\ueb69" : "\ueb68"
        font.family: root.iconFont
        font.pixelSize: 16
        color: root.colors.fg
        anchors.verticalCenter: parent.verticalCenter
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (root.player) root.player.togglePlaying() }
      }

      Text {
        text: "\ueba8"
        font.family: root.iconFont
        font.pixelSize: 16
        color: root.colors.fg
        anchors.verticalCenter: parent.verticalCenter
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (root.player) root.player.next() }
      }
    }

    Text {
      anchors.centerIn: parent
      visible: !root.isPlaying
      text: "\ueb68"
      font.family: root.iconFont
      font.pixelSize: 16
      color: root.colors.fg
    }

    MouseArea {
      anchors.fill: parent
      z: -1
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      cursorShape: Qt.PointingHandCursor
      onClicked: (mouse) => {
        if (mouse.button === Qt.RightButton)
          Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/raccon-player"]);
        else
          Quickshell.execDetached(["qs", "-c", "raccon", "ipc", "call", "raccon", "open", "music"]);
      }
    }

    WheelHandler {
      onWheel: (event) => Quickshell.execDetached(["swayosd-client", "--output-volume", event.angleDelta.y > 0 ? "raise" : "lower"])
    }
  }
}
