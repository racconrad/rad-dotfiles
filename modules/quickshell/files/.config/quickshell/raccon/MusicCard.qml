import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Mpris

// Floating, draggable music card. The window covers the screen but only the card takes input,
// so dragging moves a QML item (no layer-shell margin round trip per frame).
PanelWindow {
  id: root
  signal closeRequested

  readonly property string home: Quickshell.env("HOME")
  readonly property string runtime: Quickshell.env("XDG_RUNTIME_DIR") || (home + "/.cache")
  readonly property string statePath: (Quickshell.env("XDG_STATE_HOME") || (home + "/.local/state")) + "/raccon-music/pos"
  readonly property var player: {
    const all = Mpris.players.values;
    return all.find(p => p.isPlaying) ?? all[0] ?? null;
  }
  property string barPosition: "bottom"
  property bool placed: false

  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.namespace: "raccon-music"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
  mask: Region { item: card }

  FileView {
    id: saved
    path: root.statePath
    onLoaded: {
      const [x, y] = text().trim().split(",").map(Number);
      if (Number.isFinite(x) && Number.isFinite(y)) { card.x = x; card.y = y; root.placed = true; }
    }
  }

  // Offsets position the card with at least 12px clearance above the 64px+10px bottom bar.
  function dock() {
    const w = root.width, h = root.height, c = card;
    switch (barPosition) {
      case "bottom": c.x = w - c.width - 14; c.y = h - c.height - 88; break;
      case "left": c.x = 88; c.y = 14; break;
      case "right": c.x = w - c.width - 88; c.y = 14; break;
      default: c.x = w - c.width - 14; c.y = h - c.height - 88;
    }
  }
  onWidthChanged: if (!placed && width > 0) dock()
  onBarPositionChanged: if (!placed) dock()

  Shortcut { sequences: ["Escape", "Ctrl+W"]; onActivated: root.closeRequested() }
  Shortcut { sequence: "Space"; onActivated: if (root.player) root.player.togglePlaying() }

  Timer {
    running: Boolean(root.player && root.player.isPlaying)
    interval: 1000
    repeat: true
    onTriggered: if (root.player) root.player.positionChanged()
  }

  MusicCardBody {
    id: card
    player: root.player
    maxX: root.width - width
    maxY: root.height - height
    onCloseRequested: root.closeRequested()
    onDropped: {
      root.placed = true;
      Quickshell.execDetached(["sh", "-c", 'mkdir -p "$(dirname "$1")" && printf "%s,%s" "$2" "$3" > "$1"', "sh", root.statePath, x, y]);
    }
  }
}
