import QtQuick

// Ink splat of small squares flying outward and fading in a one-shot burst.
Item {
  id: root

  property color color: Theme.ink
  property int count: 8

  implicitWidth: 64
  implicitHeight: 64

  function fire(x, y) {
    burstGroup.x = x;
    burstGroup.y = y;
    burstAnim.restart();
  }

  Item {
    id: burstGroup
    width: 0
    height: 0

    Repeater {
      model: root.count

      Rectangle {
        antialiasing: true
        id: particle
        width: 5
        height: 5
        color: root.color
        radius: Theme.radius

        readonly property real angle: (index / Math.max(1, root.count)) * 2 * Math.PI
        readonly property real targetDist: 28 + (index % 3) * 6

        x: -width / 2 + Math.cos(angle) * progress.dist
        y: -height / 2 + Math.sin(angle) * progress.dist
        opacity: progress.fade
      }
    }
  }

  QtObject {
    id: progress
    property real dist: 0
    property real fade: 0
  }

  ParallelAnimation {
    id: burstAnim

    NumberAnimation {
      target: progress
      property: "dist"
      from: 0
      to: 32
      duration: 320
      easing.type: Easing.OutQuad
    }

    SequentialAnimation {
      ScriptAction { script: progress.fade = 1.0 }
      PauseAnimation { duration: 120 }
      NumberAnimation {
        target: progress
        property: "fade"
        from: 1.0
        to: 0.0
        duration: 200
        easing.type: Easing.InQuad
      }
    }
  }
}
