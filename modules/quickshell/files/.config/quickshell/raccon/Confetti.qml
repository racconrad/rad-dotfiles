import QtQuick

// Flat square confetti burst in primary/secondary/tertiary colors.
Item {
  id: root
  property bool active: false

  readonly property var palette: [
    Theme.primary, Theme.secondary, Theme.tertiary
  ]

  onActiveChanged: if (active && Theme.animations) burst.restart()

  Repeater {
    id: particles
    model: 36

    Rectangle {
      antialiasing: true
      id: piece
      required property int index
      readonly property real angle: (index / 36) * Math.PI * 2 + (index % 3) * 0.18
      readonly property real dist: 70 + (index % 5) * 26
      readonly property real targetX: root.width / 2 + Math.cos(angle) * dist
      readonly property real targetY: root.height / 2 + Math.sin(angle) * dist + 28

      width: 7 + (index % 3) * 2
      height: 7 + (index % 3) * 2
      radius: 0
      color: root.palette[index % root.palette.length]
      x: root.width / 2 - width / 2
      y: root.height / 2 - height / 2
      opacity: 0
      rotation: 0

      ParallelAnimation {
        id: anim
        running: false
        NumberAnimation { target: piece; property: "x"; from: root.width / 2 - piece.width / 2; to: piece.targetX; duration: 950; easing.type: Easing.OutCubic }
        NumberAnimation { target: piece; property: "y"; from: root.height / 2 - piece.height / 2; to: piece.targetY; duration: 950; easing.type: Easing.OutQuad }
        NumberAnimation { target: piece; property: "rotation"; from: 0; to: (piece.index % 2 === 0 ? 1 : -1) * (240 + piece.index * 12); duration: 1100 }
        SequentialAnimation {
          NumberAnimation { target: piece; property: "opacity"; from: 0; to: 1; duration: 120 }
          PauseAnimation { duration: 480 }
          NumberAnimation { target: piece; property: "opacity"; from: 1; to: 0; duration: 500; easing.type: Easing.InQuad }
        }
      }

      function fire() { anim.restart(); }
    }
  }

  Timer {
    id: burst
    interval: 10
    onTriggered: {
      for (let i = 0; i < particles.count; i++) {
        const item = particles.itemAt(i);
        if (item) item.fire();
      }
    }
  }
}
