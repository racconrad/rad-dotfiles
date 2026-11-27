import QtQuick
import QtQuick.Layouts

// Calm Collage floating music card with paper frame, Tag, and tactile CutButtons.
Item {
  id: card

  property var player
  property real maxX: 0
  property real maxY: 0
  signal closeRequested
  signal dropped

  width: 340; height: mainCol.implicitHeight + 24

  readonly property real posRatio: {
    const len = card.player && card.player.length ? card.player.length : 0;
    const pos = card.player && card.player.position ? card.player.position : 0;
    return len > 0 ? Math.min(1.0, Math.max(0.0, pos / len)) : 0;
  }

  Rectangle {
    antialiasing: true; x: 4; y: 4; width: card.width; height: card.height
    color: Theme.shadowColor; radius: Theme.radius
  }

  Rectangle {
    id: body
    antialiasing: true; anchors.fill: parent; color: Theme.surface_container
    radius: Theme.radius; border.width: 0

    Ridge {}

    Tag {
      text: "NOW PLAYING"; tone: "primary"; tilt: -2; z: 10
      anchors.top: parent.top; anchors.left: parent.left; anchors.topMargin: -8; anchors.leftMargin: 10
    }

    CutButton {
      icon: "󰅖"; text: ""; tone: "paper"; z: 10
      anchors.top: parent.top; anchors.right: parent.right; anchors.topMargin: 6; anchors.rightMargin: 6
      onClicked: card.closeRequested()
    }

    MouseArea {
      id: dragArea; anchors.fill: parent; drag.target: card
      drag.minimumX: 0; drag.maximumX: card.maxX; drag.minimumY: 0; drag.maximumY: card.maxY
      onReleased: card.dropped()
    }

    Column {
      id: mainCol
      anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12; topMargin: 16 }
      spacing: 10

      RowLayout {
        width: parent.width; spacing: 12

        Item {
          Layout.preferredWidth: 64; Layout.preferredHeight: 64
          Rectangle {
            antialiasing: true; x: 3; y: 3; width: parent.width; height: parent.height
            color: Theme.shadowColor; radius: Theme.radius
          }
          Rectangle {
            antialiasing: true; anchors.fill: parent; color: Theme.surface_container_highest
            border.width: 0; radius: Theme.radius
            Image {
              anchors.fill: parent; fillMode: Image.PreserveAspectCrop
              source: (card.player && card.player.trackArtUrl) ? card.player.trackArtUrl : ""
              asynchronous: true
            }
            Text {
              visible: !card.player || !card.player.trackArtUrl; anchors.centerIn: parent
              text: "󰝚"; color: Theme.outline; font { family: Theme.fontMono; pixelSize: 26 }
            }
          }
        }

        Column {
          Layout.fillWidth: true; spacing: 2
          Text {
            width: parent.width; text: (card.player && card.player.trackTitle) ? card.player.trackTitle : "Nothing playing"
            color: Theme.on_surface; elide: Text.ElideRight; font { family: Theme.fontDisplay; pixelSize: 22; weight: 800 }
          }
          Text {
            width: parent.width; text: (card.player && card.player.trackArtist) ? card.player.trackArtist : "Unknown Artist"
            color: Theme.on_surface_variant; elide: Text.ElideRight; font { family: Theme.fontTag; pixelSize: 11; weight: 800 }
          }
        }
      }

      Item {
        width: parent.width; height: 14
        Rectangle {
          antialiasing: true; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
          height: 8; radius: Theme.radius; color: Theme.ink; border.width: 1; border.color: Theme.outline
          Rectangle {
            antialiasing: true; height: parent.height; radius: Theme.radius; color: Theme.primary
            width: parent.width * card.posRatio
          }
        }
        Rectangle {
          antialiasing: true
          x: Math.max(0, Math.min(parent.width - width, parent.width * card.posRatio - width / 2))
          anchors.verticalCenter: parent.verticalCenter
          width: 12; height: 12; radius: Theme.radius; color: Theme.tone("paper").bg; border.width: 0
        }
        MouseArea {
          anchors.fill: parent
          onWheel: w => { if (card.player && card.player.canSeek) card.player.position += w.angleDelta.y > 0 ? 5 : -5; }
          onClicked: m => {
            if (card.player && card.player.canSeek && card.player.length > 0)
              card.player.position = card.player.length * (m.x / width);
          }
        }
      }

      RowLayout {
        width: parent.width; spacing: 8
        CutButton {
          icon: "󰒮"; text: ""; tone: "paper"
          onClicked: if (card.player && card.player.canGoPrevious) card.player.previous()
        }
        CutButton {
          icon: (card.player && card.player.isPlaying) ? "󰏤" : "󰐊"
          text: ""; tone: "primary"; active: true
          onClicked: if (card.player) card.player.togglePlaying()
        }
        CutButton {
          icon: "󰒭"; text: ""; tone: "paper"
          onClicked: if (card.player && card.player.canGoNext) card.player.next()
        }
        Item { Layout.fillWidth: true }
        Spectrum {
          id: spectrum; active: Boolean(card.player && card.player.isPlaying)
          Layout.alignment: Qt.AlignVCenter
        }
      }
    }
  }
}
