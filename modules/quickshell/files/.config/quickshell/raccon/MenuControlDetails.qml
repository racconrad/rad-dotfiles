import QtQuick
import QtQuick.Layouts

// Collage device/connection details card with fields and chunky action button.
Column {
  id: root

  property string backHint
  property string glyph
  property string title
  property var fields: []
  property string caption: ""
  property string actionLabel
  property string actionGlyph
  property bool busy: false
  property bool canApply: false
  property string tone: "primary"
  property alias form: formFields.data
  readonly property alias backButton: back
  signal backRequested
  signal applyRequested

  spacing: 8

  RowLayout {
    width: root.width
    spacing: 8

    CutButton {
      id: back
      icon: "󰅁"
      text: "BACK"
      tone: "paper"
      enabled: !root.busy
      onClicked: root.backRequested()
    }

    Sticker {
      Layout.fillWidth: true
      text: root.title
      tone: root.tone
    }
  }

  // Header icon & title banner
  Rectangle {
    antialiasing: true
    width: root.width
    height: 38
    radius: Theme.radius
    border.width: Theme.border
    border.color: Theme.ink
    color: Theme.tone(root.tone).bg

    RowLayout {
      anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
      spacing: 8
      Text {
        text: root.glyph
        color: Theme.tone(root.tone).fg
        font { family: Theme.fontMono; pixelSize: 18 }
      }
      Text {
        Layout.fillWidth: true
        text: root.title
        elide: Text.ElideRight
        color: Theme.tone(root.tone).fg
        font { family: Theme.fontDisplay; pixelSize: 16; weight: Font.Bold }
      }
    }
  }

  // Fields table
  Column {
    width: root.width
    spacing: 4

    Repeater {
      model: root.fields.length

      Rectangle {
        antialiasing: true
        id: detail
        required property int index
        readonly property var field: root.fields[index]

        width: root.width
        height: 24
        radius: Theme.radius
        border.width: 1
        border.color: Theme.ink
        color: Theme.surface_container

        RowLayout {
          anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
          spacing: 6

          Text {
            Layout.fillWidth: true
            text: detail.field[0].toUpperCase()
            color: Theme.on_surface_variant
            font { family: Theme.fontTag; pixelSize: 12 }
          }
          Text {
            Layout.maximumWidth: root.width * 0.65
            text: detail.field[1]
            elide: Text.ElideRight
            color: Theme.on_surface
            font { family: Theme.fontMono; pixelSize: 12; weight: Font.Bold }
          }
        }
      }
    }
  }

  Text {
    visible: text.length > 0
    width: root.width
    text: root.caption
    wrapMode: Text.Wrap
    color: Theme.on_surface_variant
    font { family: Theme.fontTag; pixelSize: 12 }
  }

  Column {
    id: formFields
    width: root.width
    spacing: 6
  }

  CutButton {
    visible: root.actionLabel.length > 0
    width: root.width
    text: root.actionLabel
    icon: root.actionGlyph
    tone: root.actionLabel.toLowerCase().includes("disconnect") ? "error" : root.tone
    enabled: root.canApply && !root.busy
    onClicked: root.applyRequested()
  }
}
