import QtQuick

// Hard paper piece with offset ink shadow and animated lift.
Item {
  id: root

  property color fill: Theme.surface_container
  property color ink: Theme.ink
  property color shadowColor: Theme.shadowColor
  property int border: Theme.border
  property int shadowOffset: Theme.shadowOffset
  property real tilt: 0
  property real radius: Theme.radius
  // Square top-right and bottom-left corners: a leaf instead of a pill.
  property bool leaf: false
  // Content only: no fill, outline or shadow.
  property bool bare: false
  property bool lifted: false

  default property alias content: body.data

  rotation: root.tilt
  transformOrigin: Item.Center

  implicitWidth: Math.max(10, body.childrenRect.x + body.childrenRect.width + root.border * 2)
  implicitHeight: Math.max(10, body.childrenRect.y + body.childrenRect.height + root.border * 2)

  readonly property real currentShadowOffset: root.shadowOffset + (root.lifted ? 3 : 0)
  readonly property real pieceOffset: root.lifted ? -2 : 0

  // Hard offset shadow in an accent colour, never blurred
  Rectangle {
    antialiasing: true
    id: shadow
    x: piece.x + root.currentShadowOffset
    y: piece.y + root.currentShadowOffset
    width: piece.width
    height: piece.height
    visible: !root.bare
    color: root.shadowColor
    radius: root.radius
    topRightRadius: root.leaf ? 0 : root.radius
    bottomLeftRadius: root.leaf ? 0 : root.radius

    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
  }

  // Paper card piece
  Rectangle {
    antialiasing: true
    id: piece
    x: root.pieceOffset
    y: root.pieceOffset
    width: root.width
    height: root.height
    color: root.bare ? "transparent" : root.fill
    radius: root.radius
    topRightRadius: root.leaf ? 0 : root.radius
    bottomLeftRadius: root.leaf ? 0 : root.radius
    border.width: root.bare ? 0 : root.border
    border.color: root.ink

    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }

    Item {
      id: body
      anchors.fill: parent
      anchors.margins: root.border
    }
  }
}
