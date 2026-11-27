import QtQuick
import QtQuick.Layouts

ColumnLayout {
  id: root

  required property var app
  required property int index
  property bool editing: false
  property alias launchButton: launch
  signal activated(var app)
  signal commandRequested(var args)

  spacing: 4

  // Polaroid-style paper tile with corner tape and accent bar
  Item {
    Layout.fillWidth: true
    Layout.minimumHeight: 64
    Layout.preferredHeight: 68

    // Hard offset shadow
    Rectangle {
      antialiasing: true
      x: launch.down ? 2 : (launch.hovered ? 5 : 3)
      y: launch.down ? 2 : (launch.hovered ? 5 : 3)
      width: parent.width; height: parent.height
      color: Theme.toneAt(root.index).bg
      radius: Theme.radius
    }

    Rectangle {
      antialiasing: true
      id: card
      x: launch.down ? 2 : (launch.hovered ? -2 : 0)
      y: launch.down ? 2 : (launch.hovered ? -2 : 0)
      width: parent.width; height: parent.height
      color: Theme.tone("paper").bg
      border.width: Theme.border
      border.color: Theme.ink
      radius: Theme.radius
      rotation: 0

      Behavior on rotation { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
      Behavior on x { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
      Behavior on y { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }

      // Left AccentBar
      AccentBar {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        barWidth: 4
        color: [Theme.primary, Theme.secondary, Theme.tertiary][root.index % 3]
      }

      MenuButton {
        id: launch
        anchors.fill: parent
        objectName: "menuHomeTile" + root.index
        enabled: root.app.available !== false
        artwork: root.app
        glyph: ({ browser: "󰖟", files: "󰉋", terminal: "󰆍" })[root.app.value] ?? "󰀻"
        glyphSize: 28
        iconAlignment: Qt.AlignHCenter
        text: root.app.name
        hint: root.app.name + (enabled ? "" : " · Not installed")
        stacked: true
        fill: "transparent"
        ink: Theme.on_surface
        onClicked: root.activated(root.app)
      }
    }
  }

  RowLayout {
    visible: root.editing
    Layout.fillWidth: true
    spacing: 2

    Repeater {
      model: [
        { glyph: "󰅁", hint: "Move earlier", allowed: root.app.can_move_previous, args: ["move", root.app.ref, "previous"] },
        { glyph: "󰍴", hint: "Remove from Home", allowed: true, args: ["remove", root.app.ref] },
        { glyph: "󰅂", hint: "Move later", allowed: root.app.can_move_next, args: ["move", root.app.ref, "next"] }
      ]
      MenuButton {
        required property var modelData
        Layout.fillWidth: true
        enabled: modelData.allowed === true
        glyph: modelData.glyph
        hint: modelData.hint
        glyphSize: 14
        iconAlignment: Qt.AlignHCenter
        onClicked: root.commandRequested(["favorite", ...modelData.args])
      }
    }
  }
}
