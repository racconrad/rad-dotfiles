import QtQuick
import QtQuick.Layouts

// Expandable drawer actions for the countdown card using CutButtons.
Item {
  id: root
  property string state: "idle"

  signal toggleClicked
  signal stopClicked

  implicitHeight: actionsRow.implicitHeight + 8
  width: parent.width

  RowLayout {
    id: actionsRow
    anchors.centerIn: parent
    spacing: 8

    CutButton {
      visible: root.state !== "ended"
      icon: root.state === "paused" ? "󰐊" : "󰏤"
      text: root.state === "paused" ? "CONTINUE" : "PAUSE"
      tone: root.state === "paused" ? "tertiary" : "primary"
      onClicked: root.toggleClicked()
    }

    CutButton {
      icon: "󰅖"
      text: root.state === "ended" ? "DISMISS" : "STOP"
      tone: "error"
      onClicked: root.stopClicked()
    }
  }
}
