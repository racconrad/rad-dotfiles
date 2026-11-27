import QtQuick
import QtQuick.Layouts

RowLayout {
  id: root

  property string title: ""
  property string avatar: ""
  property bool canEdit: true
  property bool editing: false
  signal editRequested()
  signal closeRequested()

  spacing: 12

  // Sharp square avatar frame with thick ink border
  Item {
    id: avatar
    readonly property bool canMask: GraphicsInfo.api !== GraphicsInfo.Software
    Layout.preferredWidth: 42
    Layout.preferredHeight: 42
    visible: root.avatar.length > 0

    // Hard accent shadow
    Rectangle {
      antialiasing: true
      x: 3; y: 3
      width: parent.width; height: parent.height
      color: Theme.shadowColor
      radius: Theme.radius
    }

    Rectangle {
      antialiasing: true
      anchors.fill: parent
      color: Theme.surface_container_high
      border.width: Theme.border
      border.color: Theme.ink
      radius: Theme.radius

      Image {
        anchors.fill: parent
        anchors.margins: Theme.border
        source: root.avatar ? "file://" + encodeURI(root.avatar).replace(/#/g, "%23").replace(/\?/g, "%3F") : ""
        sourceSize.width: 42
        sourceSize.height: 42
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
      }
    }
  }

  // Heading with bold 28px display type, tag and pixel spark
  ColumnLayout {
    Layout.fillWidth: true
    spacing: 2

    RowLayout {
      spacing: 6
      Tag {
        visible: root.editing
        text: "EDITING"
        tone: root.editing ? "tertiary" : "primary"
        tilt: -1
      }
      Spark {
        size: 18
        color: Theme.primary
        tilt: 15
      }
    }

    RowLayout {
      spacing: 6
      Text {
        text: root.title
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: Theme.on_surface
        font.family: Theme.fontDisplay
        font.pixelSize: 28
        font.weight: 800
        font.letterSpacing: -0.5
      }
    }
  }

  MenuButton {
    visible: root.canEdit
    selected: root.editing
    muted: true
    glyph: root.editing ? "󰄬" : "󰏫"
    hint: root.editing ? "Finish editing Home" : "Edit Home apps"
    onClicked: root.editRequested()
  }

  MenuButton {
    muted: true
    glyph: "󰅖"
    hint: "Close · Esc"
    onClicked: root.closeRequested()
  }
}
