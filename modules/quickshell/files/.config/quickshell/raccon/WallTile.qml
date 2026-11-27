import QtQuick

// One poster on the wall: thumbnail in a cut-paper frame. It slaps in when its batch is revealed
// and shrinks away when the wall closes, except the picked one which fades last.
Item {
  id: root

  required property var tile
  property bool active: false
  property bool near: true
  // Originals are never decoded here: wallpapers can be huge, so a tile waits for its small cached thumbnail.
  property bool shown: true
  property bool leaving: false
  property bool picked: false
  property bool fadeAll: false
  signal chosen()

  readonly property bool hovered: area.containsMouse && !leaving
  readonly property bool current: active || Boolean(tile.current)
  readonly property bool flip: tile.index % 2 === 1

  opacity: leaving ? (picked && !fadeAll ? 1 : 0) : (shown ? 1 : 0)
  scale: leaving ? (picked && !fadeAll ? 1.05 : 0.92) : (shown ? 1 : 0.95)
  transform: Translate { y: root.shown || root.leaving ? 0 : 30; Behavior on y { enabled: Theme.animations; NumberAnimation { duration: 620; easing.type: Easing.OutQuint } } }
  Behavior on opacity { enabled: Theme.animations; NumberAnimation { duration: root.leaving ? 420 : 900; easing.type: Easing.OutCubic } }
  Behavior on scale {
    enabled: Theme.animations
    NumberAnimation { duration: root.leaving ? 420 : 1100; easing.type: root.leaving ? Easing.InQuad : Easing.OutQuint }
  }

  Rectangle {
    antialiasing: true
    x: root.hovered ? 8 : 4; y: root.hovered ? 8 : 4
    width: parent.width - 12; height: parent.height - 12
    color: Theme.toneAt(root.tile.index).bg
    radius: 8; topLeftRadius: root.flip ? 8 : 24; bottomRightRadius: root.flip ? 8 : 24
    topRightRadius: root.flip ? 24 : 8; bottomLeftRadius: root.flip ? 24 : 8
    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: 320 } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: 320 } }
  }

  Rectangle {
    antialiasing: true
    x: root.hovered ? -3 : 0; y: root.hovered ? -3 : 0
    width: parent.width - 12; height: parent.height - 12
    color: Theme.tone("paper").bg
    radius: 8; topLeftRadius: root.flip ? 8 : 24; bottomRightRadius: root.flip ? 8 : 24
    topRightRadius: root.flip ? 24 : 8; bottomLeftRadius: root.flip ? 24 : 8
    border.width: root.current ? 4 : 0
    border.color: Theme.primary
    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: 320 } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: 320 } }

    // Placeholder while the still is decoded or the video thumbnail is still being rendered.
    Rectangle {
      anchors { fill: parent; margins: 9 }
      visible: img.status !== Image.Ready
      color: Theme.surface_container_highest
      Row {
        anchors.centerIn: parent; spacing: 6
        Repeater {
          model: 3
          Rectangle {
            required property int index
            width: 8; height: 8; color: Theme.on_surface_variant
            opacity: 0.3
            SequentialAnimation on opacity {
              running: root.near && root.shown && img.status === Image.Loading && Theme.animations
              loops: Animation.Infinite
              PauseAnimation { duration: index * 160 }
              NumberAnimation { to: 0.9; duration: 320 }
              NumberAnimation { to: 0.3; duration: 320 }
              PauseAnimation { duration: (2 - index) * 160 }
            }
          }
        }
      }
    }

    Image {
      id: img
      anchors { fill: parent; margins: 9 }
      visible: root.near && root.shown
      opacity: status === Image.Ready ? 1 : 0
      Behavior on opacity { enabled: Theme.animations; NumberAnimation { duration: 360 } }
      asynchronous: true
      fillMode: Image.PreserveAspectCrop
      sourceSize.width: 480
      source: root.near && root.shown ? (root.tile.has_thumb ? "file://" + root.tile.thumb : "") : ""
    }

    Sticker {
      visible: root.current || root.tile.video
      anchors { left: parent.left; top: parent.top; margins: 10 }
      text: root.current ? "ACTIVE" : "VIDEO"
      tone: root.current ? "primary" : "tertiary"
    }

    Rectangle {
      visible: root.hovered
      anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 9 }
      height: 28
      color: Theme.surface
      Text {
        anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        text: root.tile.name; color: Theme.on_surface
        font { family: Theme.fontTag; pixelSize: 13; weight: Font.Bold }
      }
    }
  }

  MouseArea {
    id: area
    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
    enabled: !root.leaving
    onClicked: root.chosen()
  }
}
