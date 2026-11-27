import QtQuick

// Thick accent ridge along the top edge of a panel, shared with the bar.
Rectangle {
  id: root
  anchors.top: parent.top
  anchors.topMargin: -3
  x: Theme.radius
  width: parent.width - Theme.radius * 2
  height: 6
  radius: 3
  color: Theme.tertiary
  clip: true
  z: 5

  Rectangle {
    width: 64; height: parent.height
    gradient: Gradient {
      orientation: Gradient.Horizontal
      GradientStop { position: 0; color: "transparent" }
      GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.6) }
      GradientStop { position: 1; color: "transparent" }
    }
    SequentialAnimation on x {
      running: Theme.animations && root.visible; loops: Animation.Infinite
      NumberAnimation { from: -64; to: root.width; duration: 1800; easing.type: Easing.InOutSine }
      PauseAnimation { duration: 3200 }
    }
  }
}
