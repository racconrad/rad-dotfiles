import QtQuick
import Quickshell
import Quickshell.Io

// 12-band flat square-edged spectrum alternating primary/secondary/tertiary tones.
Row {
  id: root
  property bool active: false
  property var bands: []
  property int level: 0
  readonly property int cap: 24

  spacing: 3
  height: cap
  opacity: root.active ? 1 : 0.45
  Behavior on opacity { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }

  Process {
    running: root.active
    command: [Quickshell.env("HOME") + "/.local/bin/desktop-menu", "music-viz"]
    stdout: SplitParser {
      onRead: line => {
        try {
          const v = JSON.parse(line);
          root.bands = Array.from({length: 12}, (_, i) => v["b" + i] ?? 4);
          root.level = v.level ?? 0;
        } catch (e) {}
      }
    }
  }

  Repeater {
    model: 12
    Rectangle {
      antialiasing: true
      required property int index
      width: 4
      radius: 0
      anchors.bottom: parent.bottom
      height: Theme.animations ? Math.min(root.cap, root.bands[index] ?? 4) : 4
      color: index % 3 === 0 ? Theme.primary : (index % 3 === 1 ? Theme.secondary : Theme.tertiary)
    }
  }
}
