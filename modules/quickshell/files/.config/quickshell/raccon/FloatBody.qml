import QtQuick

// Cut-paper card around the session dialog.
Item {
  id: card
  property var who: ({ user: "user", host: "localhost", uptime: "0m" })
  property string armed: ""

  signal closeRequested
  signal actionTriggered(string action)

  implicitWidth: paper.width + 6
  implicitHeight: paper.height + 14
  width: implicitWidth
  height: implicitHeight

  Rectangle {
    antialiasing: true
    x: 4; y: 12
    width: paper.width; height: paper.height
    color: Theme.tone("tertiary").bg
    radius: 10; topLeftRadius: 38; bottomRightRadius: 38
  }

  Rectangle {
    antialiasing: true
    id: paper
    x: 0; y: 8
    width: sessionView.implicitWidth + 32
    height: sessionView.implicitHeight + 28
    radius: 10; topLeftRadius: 38; bottomRightRadius: 38
    color: Theme.tone("paper").bg

    // Colour shapes behind the actions.
    Rectangle {
      width: 150; height: 150; radius: 75
      x: parent.width - 110; y: -40
      color: Theme.tone("secondary").bg; opacity: 0.55
    }
    Rectangle {
      width: 120; height: 46; radius: 23
      x: 24; y: parent.height - 70
      color: Theme.tone("primary").bg; opacity: 0.5
    }

    Ridge { x: 38; width: parent.width - 76 }

    FloatSession {
      id: sessionView
      x: 16; y: 14
      who: card.who
      armed: card.armed
      onCloseRequested: card.closeRequested()
      onActionTriggered: a => card.actionTriggered(a)
    }
  }

  Tape {
    anchors.top: paper.top
    anchors.topMargin: -7
    anchors.horizontalCenter: paper.horizontalCenter
    tilt: -2
    color: Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.65)
    z: 10
  }
}
