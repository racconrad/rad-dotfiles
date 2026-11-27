import QtQuick

// Session card body: user/host/uptime header and 5 tactile cut-paper action tiles.
Column {
  id: root
  property var who: ({ user: "user", host: "localhost", uptime: "0m" })
  property string armed: ""

  signal closeRequested
  signal actionTriggered(string action)

  width: 522
  spacing: 16

  // Header row: Tag 'SESSION', User Avatar, Name & Uptime, Close CutButton
  Row {
    width: parent.width
    spacing: 10

    Rectangle {
      antialiasing: true
      width: 32; height: 32
      radius: Theme.radius
      border.width: Theme.border
      border.color: Theme.ink
      color: Theme.tone("primary").bg
      anchors.verticalCenter: parent.verticalCenter

      Text {
        anchors.centerIn: parent
        text: "󰀄"
        color: Theme.tone("primary").fg
        font.family: Theme.fontMono
        font.pixelSize: 18
      }
    }

    Column {
      id: userCol
      anchors.verticalCenter: parent.verticalCenter
      spacing: 2

      Text {
        text: (root.who && root.who.user) ? root.who.user : "user"
        color: Theme.tone("paper").fg
        font.family: Theme.fontDisplay
        font.pixelSize: 20
        font.weight: Font.ExtraBold
      }

    }

    Item {
      height: 1
      width: Math.max(8, root.width - 85 - 32 - 10*3 - userCol.implicitWidth - closeBtn.width)
    }

    CutButton {
      id: closeBtn
      anchors.verticalCenter: parent.verticalCenter
      icon: "󰅖"
      tone: "paper"
      onClicked: root.closeRequested()
    }
  }

  // Five coloured actions with different silhouettes, bottom-aligned so the row reads as a mosaic.
  Row {
    id: actions
    spacing: 12
    height: 112

    Repeater {
      model: [
        { action: "lock", title: "Lock", icon: "󰌾", tone: "tertiary", danger: false, shape: 0, w: 88, h: 88 },
        { action: "suspend", title: "Suspend", icon: "󰏤", tone: "secondary", danger: false, shape: 0, w: 88, h: 112 },
        { action: "logout", title: "Log out", icon: "󰍃", tone: "primary", danger: true, shape: 1, w: 100, h: 88 },
        { action: "reboot", title: "Restart", icon: "󰜉", tone: "tertiary", danger: true, shape: 2, w: 88, h: 112 },
        { action: "poweroff", title: "Shut down", icon: "󰐥", tone: "error", danger: true, shape: 3, w: 110, h: 112 }
      ]

      SessionTile {
        required property var modelData
        width: modelData.w; height: modelData.h
        y: actions.height - height
        icon: modelData.icon; title: modelData.title; tone: modelData.tone
        danger: modelData.danger; shape: modelData.shape
        armed: root.armed === modelData.action
        onTriggered: {
          const act = modelData.action;
          if (act !== "lock" && root.armed !== act) root.armed = act;
          else root.actionTriggered(act);
        }
      }
    }
  }
}
