import QtQuick
import QtQuick.Layouts

// Collage list rows with AccentBar, status Stickers, and ink borders.
Column {
  id: root

  property var rows: []
  property int pageIndex: 0
  property int pageCount: 1
  property int total: 0
  property bool available: false
  property var describe
  property string tone: "primary"
  signal rowRequested(string token)
  signal pageRequested(string direction)
  spacing: 6

  // Zero-sized so the Column does not reserve its 64px default.
  Burst { id: burst; width: 0; height: 0; color: Theme.tone(root.tone).bg }

  Column {
    width: root.width
    spacing: 5

    Repeater {
      model: root.rows.length
      Item {
        id: itemRow
        required property int index
        readonly property var row: root.describe(root.rows[index])
        width: root.width
        height: Math.max(34, contentRow.implicitHeight + 10)
        readonly property bool hovered: rowArea.containsMouse
        readonly property bool selected: Boolean(row.selected)
        readonly property var rowColors: selected || hovered ? Theme.tone(root.tone) : Theme.tone("paper")

        Rectangle {
          antialiasing: true
          anchors { fill: parent; margins: -2; leftMargin: 2; topMargin: 2 }
          color: Theme.tone(root.tone).shadow; radius: Theme.radius
        }

        Rectangle {
          antialiasing: true
          anchors.fill: parent
          radius: Theme.radius
          border.width: Theme.border; border.color: Theme.ink
          color: itemRow.rowColors.bg

          AccentBar { tone: root.tone; grow: itemRow.hovered || itemRow.selected }

          RowLayout {
            id: contentRow
            anchors { fill: parent; leftMargin: 8; rightMargin: 8; topMargin: 4; bottomMargin: 4 }
            spacing: 8

            Text {
              text: itemRow.row.glyph ?? "󰂯"
              color: itemRow.rowColors.fg
              font { family: Theme.fontMono; pixelSize: 15 }
            }

            Column {
              Layout.fillWidth: true
              spacing: 1
              Text {
                width: parent.width; text: itemRow.row.title
                textFormat: Text.PlainText; elide: Text.ElideRight
                color: itemRow.rowColors.fg; font { family: Theme.fontDisplay; pixelSize: 13; weight: Font.Bold }
              }
              Text {
                width: parent.width; text: itemRow.row.subtitle
                elide: Text.ElideRight
                color: itemRow.selected || itemRow.hovered ? itemRow.rowColors.fg : Theme.on_surface_variant
                font { family: Theme.fontTag; pixelSize: 12 }
              }
            }

            Sticker {
              visible: (itemRow.row.trailing ?? "").length > 0
              text: itemRow.row.trailing ?? ""
              tone: itemRow.selected ? "tertiary" : "paper"
            }
          }

          MouseArea {
            id: rowArea
            anchors.fill: parent; hoverEnabled: root.available; enabled: root.available
            onClicked: { burst.fire(mouseX, mouseY); root.rowRequested(itemRow.row.token); }
          }
        }
      }
    }
  }

  RowLayout {
    width: root.width
    spacing: 6
    visible: root.pageCount > 1

    CutButton {
      icon: "󰅁"; text: ""; tone: "paper"
      enabled: root.available && root.pageIndex > 0
      onClicked: root.pageRequested("previous")
    }

    Rectangle {
      antialiasing: true
      Layout.fillWidth: true; height: 28; radius: Theme.radius
      border.width: Theme.border; border.color: Theme.ink; color: Theme.tone("paper").bg
      Text {
        anchors.centerIn: parent
        text: (root.pageIndex + 1) + " / " + root.pageCount + " // TOTAL " + root.total
        color: Theme.on_surface; font { family: Theme.fontTag; pixelSize: 12; weight: Font.Bold }
      }
    }

    CutButton {
      icon: "󰅂"; text: ""; tone: "paper"
      enabled: root.available && root.pageIndex + 1 < root.pageCount
      onClicked: root.pageRequested("next")
    }
  }
}
