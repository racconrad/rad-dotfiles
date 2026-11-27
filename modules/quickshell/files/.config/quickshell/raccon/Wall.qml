import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Endless wallpaper wall over the bare wallpaper. The window exists only while open; its catalogue
// (WallStore) is preloaded at startup, so opening stays instant and the RAM is returned on close.
PanelWindow {
  id: root

  required property var store
  property int revealed: 0
  property int appliedIndex: -1
  property bool closing: false
  property bool fadeAll: false
  property real scrollY: 0
  signal closeRequested

  readonly property string menuBin: store.menuBin
  readonly property var tiles: store.tiles
  readonly property int columnCount: Math.max(3, Math.round(width / 400))
  readonly property int batch: 3
  // Uneven column weights give the mosaic a few wide posters among narrow ones.
  readonly property var weights: [1.5, 0.85, 1.2, 0.8, 1.4, 1.0, 0.9, 1.25]
  function weightBefore(i) { let s = 0; for (let k = 0; k < i; k++) s += weights[k % weights.length]; return s; }
  readonly property real weightSum: weightBefore(columnCount)
  readonly property var currentTile: tiles.find(t => t.current)
  readonly property var pickedTile: tiles.find(t => t.index === appliedIndex)

  // Videos have no still of their own, so their cached thumbnail stands in for them.
  function stillOf(t) { return t ? "file://" + (t.video ? (t.has_thumb ? t.thumb : "") : t.source) : ""; }
  function setSection(sec) { revealed = 0; scrollY = 0; store.setSection(sec); }
  function pick(tile) {
    if (closing) return;
    appliedIndex = tile.index; closing = true;
    Quickshell.execDetached([menuBin, "walls", "set", store.section, String(tile.index)]);
    fadeTimer.start(); closeTimer.start();
  }

  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.namespace: "raccon-wall"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

  Component.onCompleted: store.refresh()

  // Reveal a few posters at a time.
  Timer {
    interval: 260; repeat: true; running: !root.closing && root.revealed < root.tiles.length
    onTriggered: root.revealed = Math.min(root.tiles.length, root.revealed + root.batch)
  }
  Timer { id: fadeTimer; interval: 500; onTriggered: root.fadeAll = true }
  Timer { id: closeTimer; interval: 1200; onTriggered: root.closeRequested() }

  Shortcut { sequence: "Escape"; onActivated: root.closeRequested() }
  Shortcut { sequence: "Ctrl+W"; onActivated: root.closeRequested() }
  Shortcut { sequence: "Down"; onActivated: root.scrollY += 320 }
  Shortcut { sequence: "Up"; onActivated: root.scrollY -= 320 }
  Shortcut { sequence: "PgDown"; onActivated: root.scrollY += 900 }
  Shortcut { sequence: "PgUp"; onActivated: root.scrollY -= 900 }

  // Bare wallpaper behind the posters; on pick the chosen one fades in as the new background.
  Rectangle { anchors.fill: parent; color: Theme.surface }
  Image {
    anchors.fill: parent
    source: root.stillOf(root.currentTile)
    asynchronous: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 1920
  }
  Image {
    anchors.fill: parent
    source: root.closing ? root.stillOf(root.pickedTile) : ""
    opacity: root.closing && status === Image.Ready ? 1 : 0
    Behavior on opacity { enabled: Theme.animations; NumberAnimation { duration: Theme.motionBase * 3.5; easing.type: Easing.OutCubic } }
    asynchronous: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 1920
  }

  MouseArea { anchors.fill: parent; onClicked: root.closeRequested() }

  // Full-bleed: posters run off every screen edge instead of stopping at a margin.
  Item {
    id: wall
    anchors.fill: parent
    Repeater {
      model: root.columnCount
      WallColumn {
        required property int index
        readonly property real gap: 16
        readonly property real room: wall.width - gap * (root.columnCount + 1)
        readonly property real colW: room * root.weights[index % root.weights.length] / root.weightSum
        x: gap + index * gap + room * root.weightBefore(index) / root.weightSum; width: colW; height: wall.height
        tiles: root.tiles.filter(t => t.rank % root.columnCount === index)
        dims: root.store.dims
        scrollY: root.scrollY
        phase: index * 211
        appliedIndex: root.appliedIndex
        revealed: root.revealed
        closing: root.closing
        fadeAll: root.fadeAll
        onChosen: tile => root.pick(tile)
      }
    }
  }

  // Soft fades so posters leave the screen gently at the top and bottom.
  Rectangle { width: parent.width; height: 56; anchors.top: parent.top; gradient: Gradient { GradientStop { position: 0; color: Qt.rgba(0, 0, 0, 0.55) } GradientStop { position: 1; color: "transparent" } } }
  Rectangle { width: parent.width; height: 56; anchors.bottom: parent.bottom; gradient: Gradient { GradientStop { position: 0; color: "transparent" } GradientStop { position: 1; color: Qt.rgba(0, 0, 0, 0.55) } } }

  WheelHandler {
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    onWheel: event => root.scrollY -= event.angleDelta.y
  }

  WallFilter {
    anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 12 }
    section: root.store.section
    hidden: root.closing
    onSectionRequested: sec => root.setSection(sec)
  }
}
