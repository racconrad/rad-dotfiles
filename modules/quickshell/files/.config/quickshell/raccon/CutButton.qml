import QtQuick

// Tactile cut-paper button: lifts on hover and stamps into its shadow when pressed.
Item {
  id: root

  property string text: ""
  property string icon: ""
  property string iconFont: Theme.fontMono
  property string tone: "paper"
  property bool active: false
  property bool enabled: true
  property bool vertical: false
  property int iconSize: 14
  property real radius: Theme.radius
  property color shadowColor: colors.shadow
  property color outline: Theme.ink
  // Small buttons sit flat; only large ones cast the hard shadow.
  readonly property bool small: height < 44

  signal clicked()

  readonly property var colors: Theme.tone(root.active ? (root.tone === "paper" ? "primary" : root.tone) : root.tone)
  readonly property bool hovered: area.containsMouse && !area.pressed
  readonly property bool pressed: area.pressed && area.containsMouse

  readonly property real pieceOffset: pressed ? Theme.shadowOffset : (hovered ? -2 : 0)
  readonly property real shadowOffset: pressed ? Theme.shadowOffset : (hovered ? Theme.shadowOffset + 3 : Theme.shadowOffset)

  implicitWidth: Math.max(32, root.vertical ? (col.implicitWidth + 20) : (row.implicitWidth + 24))
  implicitHeight: Math.max(32, root.vertical ? (col.implicitHeight + 16) : (row.implicitHeight + 12))
  opacity: root.enabled ? 1.0 : 0.45

  // Hard offset shadow rectangle
  Rectangle {
    antialiasing: true
    id: shadow
    visible: !root.small
    x: root.shadowOffset
    y: root.shadowOffset
    width: piece.width
    height: piece.height
    color: root.shadowColor
    radius: root.radius

    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
  }

  // Paper button piece
  Rectangle {
    antialiasing: true
    id: piece
    x: root.pieceOffset
    y: root.pieceOffset
    width: root.width
    height: root.height
    color: root.colors.bg
    radius: root.radius
    border.width: Theme.border
    border.color: root.active ? Theme.primary : root.outline

    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }

    Row {
      id: row
      visible: !root.vertical
      anchors.centerIn: parent
      spacing: 6

      Text {
        visible: root.icon.length > 0
        text: root.icon
        color: root.colors.fg
        font.family: root.iconFont
        font.pixelSize: root.iconSize
        anchors.verticalCenter: parent.verticalCenter
      }

      Text {
        visible: root.text.length > 0
        text: root.text
        color: root.colors.fg
        font.family: Theme.fontDisplay
        font.pixelSize: 12
        font.weight: Font.Bold
        anchors.verticalCenter: parent.verticalCenter
      }
    }

    Column {
      id: col
      visible: root.vertical
      anchors.centerIn: parent
      spacing: 6

      Text {
        visible: root.icon.length > 0
        text: root.icon
        color: root.colors.fg
        font.family: root.iconFont
        font.pixelSize: root.iconSize > 14 ? root.iconSize : 24
        anchors.horizontalCenter: parent.horizontalCenter
      }

      Text {
        visible: root.text.length > 0
        text: root.text
        color: root.colors.fg
        font.family: Theme.fontDisplay
        font.pixelSize: 13
        font.weight: Font.Bold
        anchors.horizontalCenter: parent.horizontalCenter
      }
    }
  }

  MouseArea {
    id: area
    anchors.fill: parent
    hoverEnabled: root.enabled
    cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: if (root.enabled) root.clicked()
  }
}
