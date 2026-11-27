import QtQuick
import QtQuick.Layouts

ColumnLayout {
  id: root

  property var catalogue: ({})
  signal activated(var app)
  signal commandRequested(var args)

  spacing: 6

  RowLayout {
    Layout.fillWidth: true
    spacing: 8

    Tag {
      text: "RECENT TICKETS"
      tone: "tertiary"
      tilt: -1
    }

    Item { Layout.fillWidth: true }

    MenuButton {
      text: root.catalogue.recent_enabled ? "Disable" : "Enable"
      hint: "Toggle recording launches"
      onClicked: root.commandRequested(["recent", root.catalogue.recent_enabled ? "disable" : "enable"])
    }

    MenuButton {
      glyph: "󰃢"
      hint: "Clear recent apps"
      onClicked: root.commandRequested(["recent", "clear"])
    }
  }

  Text {
    Layout.fillWidth: true
    visible: (root.catalogue.recent_enabled ?? false) && !(root.catalogue.recent && root.catalogue.recent.length)
    text: "No tickets punched yet. Launch an app to print a ticket."
    wrapMode: Text.WordWrap
    color: Theme.on_surface_variant
    font.family: Theme.fontDisplay
    font.pixelSize: 12
  }

  RowLayout {
    visible: (root.catalogue.recent_enabled ?? false) && root.catalogue.recent && root.catalogue.recent.length > 0
    Layout.fillWidth: true
    spacing: 8

    Repeater {
      model: root.catalogue.recent ?? []
      Item {
        required property var modelData
        required property int index
        Layout.fillWidth: true
        Layout.minimumHeight: 36

        // Ticket hard shadow
        Rectangle {
          antialiasing: true
          x: 2; y: 2
          width: parent.width; height: parent.height
          color: Theme.shadowColor
          radius: Theme.radius
        }

        Rectangle {
          antialiasing: true
          anchors.fill: parent
          color: Theme.tone("tertiary").bg
          border.width: Theme.border
          border.color: Theme.ink
          radius: Theme.radius

          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            spacing: 4

            Text {
              text: "|||"
              color: Theme.tone("tertiary").fg
              font.family: Theme.fontDisplay
              font.pixelSize: 12
              font.weight: 900
              opacity: 0.6
            }

            MenuButton {
              Layout.fillWidth: true
              artwork: modelData
              glyphSize: 18
              text: modelData.name
              fill: "transparent"
              ink: Theme.tone("tertiary").fg
              onClicked: root.activated(modelData)
            }
          }
        }
      }
    }
  }
}
