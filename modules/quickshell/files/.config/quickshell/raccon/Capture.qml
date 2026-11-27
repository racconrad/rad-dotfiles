import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Compact capture picker: five small icon tiles. The panel closes first, then the command runs,
// so it is never part of the shot.
PanelWindow {
  id: root
  signal closeRequested

  readonly property string bin: Quickshell.env("HOME") + "/.local/bin/raccon-capture"
  property bool recording: false

  function run(args) {
    closeRequested();
    Quickshell.execDetached(["sh", "-c", 'sleep 0.4; exec "$@"', "sh", bin, ...args]);
  }

  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.namespace: "raccon-capture"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
  mask: Region { item: body }

  Shortcut { sequence: "Escape"; onActivated: root.closeRequested() }
  Shortcut { sequence: "Ctrl+W"; onActivated: root.closeRequested() }

  Process {
    id: statusProc
    command: [root.bin, "status"]
    running: true
    stdout: SplitParser {
      onRead: line => {
        root.recording = line.startsWith("recording");
      }
    }
  }
  // Polled only while the panel exists.
  Timer { interval: 1000; running: true; repeat: true; onTriggered: statusProc.running = true }

  Item {
    id: body
    anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 64 + 10 + 14 }
    width: sheet.width + 6
    height: sheet.height + 6

    Rectangle {
      antialiasing: true
      x: 5; y: 5; width: sheet.width; height: sheet.height
      color: Theme.tone("secondary").bg
      radius: 8; topLeftRadius: 22; bottomRightRadius: 22
    }

    Rectangle {
      id: sheet
      antialiasing: true
      width: row.implicitWidth + 24
      height: 56
      color: Theme.tone("paper").bg
      radius: 8; topLeftRadius: 22; bottomRightRadius: 22

      Ridge { x: 22; width: parent.width - 44 }

      Row {
        id: row
        x: 12; anchors.verticalCenter: parent.verticalCenter
        spacing: 8

        Repeater {
          model: [
            { icon: "󰆞", tone: "tertiary", shape: 0, w: 38, args: ["shot", "area"] },
            { icon: "󰖯", tone: "secondary", shape: 1, w: 38, args: ["shot", "window"] },
            { icon: "󰍹", tone: "primary", shape: 0, w: 50, args: ["shot", "screen"] },
            { icon: "󰑊", tone: "tertiary", shape: 2, w: 38, args: ["rec", "area"] },
            { icon: "󰑊", tone: "error", shape: 3, w: 38, args: ["rec", "screen"] }
          ]

          SessionTile {
            required property var modelData
            required property int index
            readonly property bool stopSlot: root.recording && index === 4
            iconOnly: true
            width: modelData.w; height: 38
            anchors.verticalCenter: parent.verticalCenter
            enabled: !(root.recording && index === 3)
            opacity: enabled ? 1 : 0.35
            icon: stopSlot ? "󰓛" : modelData.icon
            tone: stopSlot ? "error" : modelData.tone
            shape: modelData.shape
            onTriggered: root.run(stopSlot ? ["rec", "stop"] : modelData.args)
          }
        }
      }
    }
  }
}
