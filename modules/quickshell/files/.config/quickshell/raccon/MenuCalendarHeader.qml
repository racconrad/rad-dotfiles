import QtQuick
import QtQuick.Layouts

// Header controls for calendar: month title, today jump, and month navigation.
Column {
  id: root
  property string monthTitle: "Calendar"
  property string dateText: ""

  signal todayRequested
  signal moveRequested(int offset)

  spacing: 8

  RowLayout {
    width: root.width
    spacing: 6

    Text {
      Layout.fillWidth: true
      text: root.monthTitle.toUpperCase()
      color: Theme.tertiary
      font { family: Theme.fontDisplay; pixelSize: 24; weight: 800 }
      elide: Text.ElideRight
    }

    CutButton {
      icon: "󰋜"
      text: "TODAY"
      tone: "tertiary"
      onClicked: root.todayRequested()
    }
  }

  RowLayout {
    width: root.width
    spacing: 4

    CutButton {
      icon: "󰅁"
      text: ""
      tone: "paper"
      onClicked: root.moveRequested(-1)
    }

    Rectangle {
      antialiasing: true
      Layout.fillWidth: true
      height: 28
      radius: Theme.radius
      border.width: Theme.border
      border.color: Theme.ink
      color: Theme.tone("tertiary").bg

      Text {
        anchors.centerIn: parent
        text: root.dateText
        color: Theme.tone("tertiary").fg
        font { family: Theme.fontTag; pixelSize: 12; weight: Font.Bold }
      }
    }

    CutButton {
      icon: "󰅂"
      text: ""
      tone: "paper"
      onClicked: root.moveRequested(1)
    }
  }
}
