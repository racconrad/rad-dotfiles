import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Floating, draggable countdown chip with confetti on finish and Super/Esc close.
PanelWindow {
  id: root
  signal closeRequested

  readonly property string home: Quickshell.env("HOME")
  readonly property string countdownBin: home + "/.local/bin/countdown"
  readonly property string statePath: (Quickshell.env("XDG_STATE_HOME") || (home + "/.local/state")) + "/raccon-countdown/pos"

  property string barPosition: "bottom"
  property bool placed: false
  property string prevState: "idle"
  property var statusData: ({
    state: "idle", duration_seconds: 0, remaining_seconds: 0,
    time_formatted: "25:00", percent: 0, label: ""
  })

  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.namespace: "raccon-countdown"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
  mask: Region { item: chip }

  FileView {
    path: root.statePath
    onLoaded: {
      const [x, y] = text().trim().split(",").map(Number);
      if (Number.isFinite(x) && Number.isFinite(y)) { chip.x = x; chip.y = y; root.placed = true; }
    }
  }

  function dock() {
    if (root.width <= 0) return;
    chip.x = (root.width - chip.width) / 2;
    chip.y = root.barPosition === "top" ? 68 : 18;
  }
  onWidthChanged: if (!placed && width > 0) dock()
  onBarPositionChanged: if (!placed) dock()

  Process {
    running: true
    command: [root.countdownBin, "--listen"]
    stdout: SplitParser {
      onRead: line => {
        try {
          const next = JSON.parse(line);
          if (next.state === "ended" && root.prevState !== "ended") confetti.active = true;
          else if (next.state !== "ended") confetti.active = false;
          root.prevState = next.state ?? "idle";
          root.statusData = next;
        } catch (e) {}
      }
    }
  }

  function stopAndClose() {
    Quickshell.execDetached([root.countdownBin, "stop"]);
    root.closeRequested();
  }

  Shortcut { sequences: ["Escape", "Ctrl+W", "Meta+W", "Meta+Q"]; onActivated: root.stopAndClose() }
  Shortcut { sequences: ["Space", "P"]; onActivated: Quickshell.execDetached([root.countdownBin, "toggle"]) }

  Confetti {
    id: confetti
    x: chip.x + chip.width / 2 - width / 2
    y: chip.y + chip.height / 2 - height / 2
    width: 320
    height: 320
  }

  CountdownBody {
    id: chip
    status: root.statusData
    maxX: root.width - width
    maxY: root.height - height
    onToggleClicked: Quickshell.execDetached([root.countdownBin, "toggle"])
    onStopClicked: root.stopAndClose()
    onCloseRequested: root.stopAndClose()
    onDropped: {
      root.placed = true;
      Quickshell.execDetached(["sh", "-c", 'mkdir -p "$(dirname "$1")" && printf "%s,%s" "$2" "$3" > "$1"', "sh", root.statePath, x, y]);
    }
  }
}
