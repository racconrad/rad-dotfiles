import QtQuick
import QtQuick.Layouts

// Calm Collage floating countdown card with Tag, large outlined digits, and flat progress.
Item {
  id: card

  property var status: ({
    state: "idle", duration_seconds: 0, remaining_seconds: 0,
    time_formatted: "25:00", percent: 0, label: ""
  })
  property bool expanded: true
  property real maxX: 0
  property real maxY: 0

  signal toggleClicked
  signal stopClicked
  signal closeRequested
  signal dropped

  readonly property string state: (status && status.state) ? status.state : "idle"
  readonly property bool drawerOpen: expanded || state === "ended"

  width: 260
  height: mainCol.implicitHeight + 24

  // One hard 4px shadow
  Rectangle {
    antialiasing: true
    x: 4; y: 4
    width: card.width; height: card.height
    color: Theme.shadowColor
    radius: Theme.radius
  }

  // Paper card body
  Rectangle {
    id: body
    antialiasing: true
    anchors.fill: parent
    color: Theme.surface_container
    radius: Theme.radius
    border.width: card.state === "ended" ? 2 : 0
    border.color: Theme.error

    Ridge {}

    CutButton {
      icon: "󰅖"
      text: ""
      tone: "paper"
      anchors { top: parent.top; right: parent.right; topMargin: 6; rightMargin: 6 }
      z: 10
      onClicked: card.closeRequested()
    }

    MouseArea {
      id: dragArea
      anchors.fill: parent
      drag.target: card
      drag.minimumX: 0; drag.maximumX: card.maxX
      drag.minimumY: 0; drag.maximumY: card.maxY
      onReleased: card.dropped()
    }

    Column {
      id: mainCol
      anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12; topMargin: 16 }
      spacing: 8

      // Big outlined digits (>= 56px)
      Item {
        width: parent.width
        height: digitText.implicitHeight

        Text {
          id: digitText
          anchors.horizontalCenter: parent.horizontalCenter
          text: card.state === "ended" ? "DONE!" : (card.status && card.status.time_formatted ? card.status.time_formatted : "25:00")
          color: card.state === "ended" ? Theme.error : Theme.primary
          style: Text.Outline
          styleColor: Theme.ink
          font { family: Theme.fontDisplay; pixelSize: 58; weight: 800; letterSpacing: 2 }
        }
      }

      // Only the finished state needs a caption
      Text {
        visible: card.state === "ended"
        anchors.horizontalCenter: parent.horizontalCenter
        text: card.state === "ended" ? "TIMER COMPLETE" : "MINUTES // SECONDS"
        color: Theme.on_surface_variant
        font { family: Theme.fontTag; pixelSize: 10; weight: 800 }
      }

      // Flat progress bar
      Rectangle {
        antialiasing: true
        width: parent.width; height: 8; radius: Theme.radius
        color: Theme.ink; border.width: 1; border.color: Theme.outline

        Rectangle {
          antialiasing: true
          height: parent.height; radius: Theme.radius
          width: parent.width * Math.min(1.0, Math.max(0.0, (card.status && card.status.percent !== undefined ? card.status.percent : 0) / 100))
          color: card.state === "ended" ? Theme.error : (card.state === "paused" ? Theme.tertiary : Theme.primary)
        }
      }

      CountdownDrawer {
        width: parent.width
        visible: card.drawerOpen
        state: card.state
        onToggleClicked: card.toggleClicked()
        onStopClicked: card.stopClicked()
      }
    }
  }
}
