import QtQuick

// Discreet filter: three small words that stay faint until the pointer comes near.
Rectangle {
  id: root

  property string section: "all"
  property bool hidden: false
  signal sectionRequested(string section)

  width: row.width + 28; height: 28; radius: 14
  color: Qt.rgba(0, 0, 0, 0.5)
  opacity: hidden ? 0 : (hover.hovered ? 1 : 0.35)
  Behavior on opacity { enabled: Theme.animations; NumberAnimation { duration: Theme.motionBase } }
  HoverHandler { id: hover }

  Row {
    id: row
    anchors.centerIn: parent; spacing: 16
    Repeater {
      model: [{ k: "all", t: "ALL" }, { k: "images", t: "IMG" }, { k: "videos", t: "VID" }]
      Text {
        required property var modelData
        text: modelData.t
        color: Theme.on_surface; opacity: root.section === modelData.k ? 1 : 0.55
        font { family: Theme.fontTag; pixelSize: 12; weight: root.section === modelData.k ? Font.Bold : Font.Normal }
        MouseArea { anchors { fill: parent; margins: -6 } cursorShape: Qt.PointingHandCursor; onClicked: root.sectionRequested(modelData.k) }
      }
    }
  }
}
