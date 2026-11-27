import QtQuick
import QtQuick.Layouts

// Active timer actions with Pause/Continue in primary and Stop in error tone.
RowLayout {
  id: root
  property string state: "idle"

  signal toggleClicked
  signal stopClicked

  spacing: 8
  visible: state !== "idle"

  CutButton {
    Layout.fillWidth: true
    icon: root.state === "paused" ? "󰐊" : (root.state === "ended" ? "󰄬" : "󰏤")
    text: root.state === "paused" ? "CONTINUE" : (root.state === "ended" ? "OK" : "PAUSE")
    tone: "primary"
    onClicked: root.toggleClicked()
  }

  CutButton {
    Layout.fillWidth: true
    icon: "󰅖"
    text: "STOP"
    tone: "error"
    onClicked: root.stopClicked()
  }
}
