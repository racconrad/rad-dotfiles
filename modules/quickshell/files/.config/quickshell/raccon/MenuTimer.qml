import QtQuick
import QtQuick.Layouts
import Quickshell

// Physical paper timer sheet with big outlined digits, tertiary ring, and primary accents.
Item {
  id: root
  property var model: ({
    state: "idle", duration_seconds: 0, remaining_seconds: 0,
    time_formatted: "25:00", percent: 0, label: ""
  })
  signal startRequested(string duration)
  signal toggleRequested
  signal stopRequested

  readonly property string home: Quickshell.env("HOME")
  readonly property string countdownBin: home + "/.local/bin/countdown"
  readonly property string menuBin: home + "/.local/bin/desktop-menu"
  readonly property string state: (model && model.state) ? model.state : "idle"

  function launchTimer(dur) {
    const spec = dur.trim();
    if (!spec) return;
    root.startRequested(spec);
    Quickshell.execDetached(["sh", "-c", '"$1" start "$2" && "$3" close', "sh", root.countdownBin, spec, root.menuBin]);
  }

  implicitWidth: 302
  implicitHeight: col.implicitHeight

  Item {
    id: card
    width: root.width
    height: col.implicitHeight

    Column {
      id: col
      anchors { left: parent.left; right: parent.right; top: parent.top;  }
      spacing: 8

      RowLayout {
        width: parent.width; spacing: 8
        Sticker { text: "TIMER"; tone: "primary" }
        Item { Layout.fillWidth: true }
        Sticker {
          text: root.state.toUpperCase()
          tone: root.state === "running" ? "primary" : (root.state === "ended" ? "error" : "paper")
        }
      }

      Rectangle {
        antialiasing: true
        width: parent.width; height: 56; radius: Theme.radius
        color: Theme.surface_container_highest; border.width: 2; border.color: Theme.tertiary
        Rectangle {
          antialiasing: true
          z: -1; x: 3; y: 3; width: parent.width; height: parent.height; color: Theme.ink; radius: Theme.radius
        }
        Item {
          anchors.centerIn: parent
          width: digitsFront.implicitWidth + 4; height: digitsFront.implicitHeight + 4
          Text {
            x: 2; y: 2
            text: root.state === "ended" ? "DONE!" : (root.model && root.model.time_formatted ? root.model.time_formatted : "25:00")
            color: Theme.tertiary; font { family: Theme.fontDisplay; pixelSize: 32; weight: 900; letterSpacing: 2 }
          }
          Text {
            id: digitsFront; x: 0; y: 0
            text: root.state === "ended" ? "DONE!" : (root.model && root.model.time_formatted ? root.model.time_formatted : "25:00")
            color: root.state === "ended" ? Theme.error : Theme.primary
            font { family: Theme.fontDisplay; pixelSize: 32; weight: 900; letterSpacing: 2 }
          }
        }
      }

      MenuTimerInput { width: parent.width; onLaunchRequested: dur => root.launchTimer(dur) }
      MenuTimerPresets { width: parent.width; onPresetSelected: dur => root.launchTimer(dur) }
      MenuTimerActions {
        width: parent.width; state: root.state
        onToggleClicked: { root.toggleRequested(); Quickshell.execDetached([root.countdownBin, "toggle"]); }
        onStopClicked: { root.stopRequested(); Quickshell.execDetached([root.countdownBin, "stop"]); }
      }
    }
  }
}
