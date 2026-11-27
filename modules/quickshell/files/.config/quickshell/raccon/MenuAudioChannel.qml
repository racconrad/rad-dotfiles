import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T

Column {
  id: root

  required property string channel
  property var device
  property var devices: []
  property bool expanded: false
  property bool available: false
  property int pendingValue: -1
  readonly property string token: (device && device.token) ? device.token : ""
  readonly property bool input: channel === "input"
  readonly property bool usable: available && token.length > 0
  readonly property alias muteButton: mute
  signal toggleRequested
  signal muteRequested(string token)
  signal deviceRequested(string token)
  signal volumeRequested(int percent)
  spacing: 6

  onTokenChanged: { sendVolume.stop(); releasePreview.stop(); pendingValue = -1; }

  RowLayout {
    width: root.width
    spacing: 6

    CutButton {
      id: mute
      icon: root.input ? (root.device && root.device.mute ? "󰍭" : "󰍬") : (root.device && root.device.mute ? "󰝟" : "󰕾")
      text: ""; tone: root.device && root.device.mute ? "error" : "paper"
      enabled: root.usable; onClicked: root.muteRequested(root.token)
    }

    CutButton {
      Layout.fillWidth: true
      text: (root.device && root.device.title) ? root.device.title : (root.input ? "Microphone…" : "Output…")
      icon: root.expanded ? "▴" : "▾"; tone: "paper"
      enabled: root.usable; onClicked: root.toggleRequested()
    }

    Text {
      text: Math.round(volume.value) + "%"
      color: Theme.on_surface; font { family: Theme.fontTag; pixelSize: 12; weight: 800 }
    }
  }

  T.Slider {
    id: volume
    width: root.width; height: 28; from: 0; to: 100; stepSize: 1
    value: root.pendingValue >= 0 ? root.pendingValue : (root.device && root.device.volume !== undefined ? root.device.volume : 0)
    enabled: root.usable
    onMoved: { root.pendingValue = Math.round(value); sendVolume.restart(); releasePreview.restart(); }

    background: Rectangle {
      y: (volume.height - height) / 2
      width: volume.availableWidth; height: 8; radius: Theme.radius
      color: Theme.ink; border.width: 1; border.color: Theme.outline
      Rectangle { width: parent.width * volume.visualPosition; height: parent.height; radius: Theme.radius; color: Theme.primary }
    }

    handle: Rectangle {
      x: volume.leftPadding + volume.visualPosition * (volume.availableWidth - width)
      y: (volume.height - height) / 2
      width: 18; height: 18; radius: Theme.radius
      color: volume.pressed ? Theme.on_primary_container : Theme.tone("paper").bg
      border.width: Theme.border; border.color: Theme.ink

      Rectangle {
        antialiasing: true
        z: -1; x: thumbArea.containsMouse ? 3 : 2; y: thumbArea.containsMouse ? 3 : 2
        width: parent.width; height: parent.height; color: Theme.shadowColor; radius: Theme.radius
      }
      Sticker {
        visible: thumbArea.containsMouse || volume.pressed
        anchors { bottom: parent.top; bottomMargin: 4; horizontalCenter: parent.horizontalCenter }
        text: Math.round(volume.value) + "%"; tone: "primary"
      }
      MouseArea { id: thumbArea; anchors.fill: parent; hoverEnabled: true }
    }
  }

  Timer { id: sendVolume; interval: 75; onTriggered: if (root.usable) root.volumeRequested(root.pendingValue) }
  Timer { id: releasePreview; interval: 1250; onTriggered: root.pendingValue = -1 }

  Column {
    width: root.width; spacing: 3
    visible: root.expanded && root.devices.length > 0
    Repeater {
      model: root.devices.length
      CutButton {
        required property int index
        readonly property var dev: root.devices[index]
        width: root.width; text: dev.title
        tone: dev.active ? "primary" : "paper"
        active: Boolean(dev.active); enabled: root.available && root.expanded
        onClicked: root.deviceRequested(dev.token)
      }
    }
  }
}
