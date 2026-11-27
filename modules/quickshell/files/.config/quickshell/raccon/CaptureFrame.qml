import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Recording indicator: a small pill above the bar (click to stop) and, for area recordings, a thin
// neutral frame just outside the region so it never appears in the video.
// Opened and closed by raccon-capture; it polls the status once a second only while it exists.
PanelWindow {
  id: root
  signal closeRequested

  readonly property string bin: Quickshell.env("HOME") + "/.local/bin/raccon-capture"
  property int seconds: 0
  property real gx: 0
  property real gy: 0
  property real gw: 0
  property real gh: 0
  readonly property real gap: 6

  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.namespace: "raccon-capture-frame"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
  mask: Region { item: pill }

  Process {
    id: statusProc
    command: [root.bin, "status"]
    running: true
    stdout: SplitParser {
      onRead: line => {
        const parts = line.split(" ");
        if (parts[0] !== "recording") return;
        root.seconds = parseInt(parts[1]) || 0;
        if (parts.length < 4) { root.gw = 0; return; }
        const pos = parts[2].split(",");
        const size = parts[3].split("x");
        root.gx = parseFloat(pos[0]); root.gy = parseFloat(pos[1]);
        root.gw = parseFloat(size[0]); root.gh = parseFloat(size[1]);
      }
    }
  }
  Timer { interval: 1000; running: true; repeat: true; onTriggered: statusProc.running = true }

  Rectangle {
    visible: root.gw > 0
    x: root.gx - root.gap; y: root.gy - root.gap
    width: root.gw + root.gap * 2; height: root.gh + root.gap * 2
    radius: 12
    color: "transparent"
    border.width: 3
    border.color: Theme.tertiary
  }

  Rectangle {
    id: pill
    height: 26; width: label.implicitWidth + 38; radius: 13
    // Sits right above the bar's right pill.
    x: root.width - width - 40
    y: root.height - 64 - 10 - height - 10
    color: Theme.tone("primary").bg

    Rectangle {
      width: 8; height: 8; radius: 4; color: Theme.error
      anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
    }
    Text {
      id: label
      anchors { left: parent.left; leftMargin: 24; verticalCenter: parent.verticalCenter }
      text: String(Math.floor(root.seconds / 60)).padStart(2, "0") + ":" + String(root.seconds % 60).padStart(2, "0")
        + (root.gw > 0 ? "  " + Math.round(root.gw) + "×" + Math.round(root.gh) : "")
      color: Theme.tone("primary").fg
      font { family: Theme.fontDisplay; pixelSize: 11; weight: Font.Bold }
    }
    MouseArea {
      anchors.fill: parent; cursorShape: Qt.PointingHandCursor
      onClicked: Quickshell.execDetached([root.bin, "rec", "stop"])
    }
  }
}
