import QtQuick

// Accent indicator for tile left edges that expands to a full fill on hover.
Item {
  id: root

  property string tone: "primary"
  property bool grow: false
  property var color: undefined
  property int barWidth: 3

  implicitWidth: root.barWidth
  implicitHeight: parent ? parent.height : 24
  width: root.grow && parent ? parent.width : root.barWidth
  height: parent ? parent.height : implicitHeight

  readonly property var toneColor: Theme.tone(root.tone)
  readonly property color barColor: root.color !== undefined ? root.color : (Theme[root.tone] !== undefined ? Theme[root.tone] : root.toneColor.bg)

  Rectangle {
    antialiasing: true
    anchors.fill: parent
    color: root.barColor
    radius: Theme.radius
  }

  Behavior on width {
    enabled: Theme.animations
    NumberAnimation {
      duration: Theme.motionFast
      easing.type: Easing.OutCubic
    }
  }
}
