import QtQuick

// Coloured session action with its own silhouette; lifts and tilts on hover, pulses once armed.
Item {
  id: root

  property string icon: ""
  property string title: ""
  property string tone: "primary"
  property bool danger: false
  property bool armed: false
  property bool iconOnly: false
  // 0 pill or circle, 1 leaf, 2 mirrored leaf, 3 big blob
  property int shape: 0
  signal triggered

  readonly property bool hovered: area.containsMouse
  readonly property var colors: Theme.tone(armed && danger ? "error" : tone)
  readonly property real big: Math.min(width, height) * 0.4
  readonly property real small: shape === 0 ? Math.min(width, height) / 2 : 10
  readonly property real tl: shape === 1 || shape === 3 ? big : small
  readonly property real br: tl
  readonly property real tr: shape === 2 ? big : small
  readonly property real bl: tr

  Rectangle {
    antialiasing: true
    x: root.hovered ? 8 : 5; y: root.hovered ? 8 : 5
    width: parent.width; height: parent.height
    color: root.colors.shadow
    topLeftRadius: root.tl; bottomRightRadius: root.br; topRightRadius: root.tr; bottomLeftRadius: root.bl
    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: 260 } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: 260 } }
  }

  Rectangle {
    id: body
    antialiasing: true
    x: root.hovered ? -3 : 0; y: root.hovered ? -3 : 0
    width: parent.width; height: parent.height
    color: root.colors.bg
    topLeftRadius: root.tl; bottomRightRadius: root.br; topRightRadius: root.tr; bottomLeftRadius: root.bl
    rotation: root.hovered ? (root.shape === 2 ? 3 : -3) : 0
    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: 260; easing.type: Easing.OutBack } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: 260; easing.type: Easing.OutBack } }
    Behavior on rotation { enabled: Theme.animations; NumberAnimation { duration: 320; easing.type: Easing.OutBack } }
    Behavior on color { enabled: Theme.animations; ColorAnimation { duration: 260 } }

    SequentialAnimation on scale {
      running: root.armed && Theme.animations; loops: Animation.Infinite
      NumberAnimation { to: 1.05; duration: 520; easing.type: Easing.InOutSine }
      NumberAnimation { to: 1.0; duration: 520; easing.type: Easing.InOutSine }
      onRunningChanged: if (!running) body.scale = 1
    }

    Column {
      anchors.centerIn: parent
      spacing: 6
      Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.armed ? "󰄬" : root.icon
        color: root.colors.fg
        font.family: Theme.fontMono; font.pixelSize: root.iconOnly ? 18 : (root.shape === 3 ? 34 : 26)
      }
      Text {
        visible: !root.iconOnly
        anchors.horizontalCenter: parent.horizontalCenter
        text: (root.armed ? "Confirm" : root.title).toUpperCase()
        color: root.colors.fg
        font { family: Theme.fontDisplay; pixelSize: 12; weight: Font.Bold }
      }
    }
  }

  MouseArea {
    id: area
    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
    onClicked: root.triggered()
  }
}
