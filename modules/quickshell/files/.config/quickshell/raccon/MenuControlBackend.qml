pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io

Scope {
  id: root

  property int page: 0
  readonly property var audio: audioWatch.item?.model ?? null
  readonly property var wifi: wifiWatch.item?.model ?? null
  readonly property var bluetooth: bluetoothWatch.item?.model ?? null
  readonly property bool busy: action.inFlight
  readonly property string message: action.label
  readonly property string error: action.page === page ? action.failure : ""
  readonly property string menu: Quickshell.env("HOME") + "/.local/bin/desktop-menu"

  function dispatch(args, label, password) {
    if (busy)
      return;
    action.page = page;
    action.label = label;
    action.failure = "";
    action.stderrLine = "";
    action.isJoin = args[0] === "wifi-connect";
    action.retry = args[0] === "retry";
    action.secret = password ?? "";
    action.stdinEnabled = action.secret.length > 0;
    action.inFlight = true;
    action.command = [menu, "panel", ...args];
    action.running = true;
  }

  function setVolume(channel, percent) {
    if (channel !== "input" && channel !== "output")
      return;
    const input = channel === "input";
    const level = Math.max(0, Math.min(100, Math.round(percent)));
    Quickshell.execDetached(["pactl", input ? "set-source-volume" : "set-sink-volume",
      input ? "@DEFAULT_SOURCE@" : "@DEFAULT_SINK@", level + "%"]);
  }

  component Watch: Process {
    id: watch
    required property string kind
    property var model: ({})
    running: true
    command: [root.menu, "panel-watch", kind]

    onRunningChanged: if (!running)
      model = { status: "error", message: "Panel data stream stopped." }

    stdout: SplitParser {
      onRead: line => {
        try {
          const data = JSON.parse(line);
          if (data && typeof data.status === "string")
            watch.model = data;
        } catch (error) {
          console.warn("Menu: invalid panel data:", error);
        }
      }
    }
  }

  LazyLoader {
    id: audioWatch
    active: root.page === 4
    Watch { kind: "audio" }
  }
  LazyLoader {
    id: wifiWatch
    active: root.page === 5
    Watch { kind: "connections" }
  }
  LazyLoader {
    id: bluetoothWatch
    active: root.page === 6
    Watch { kind: "bluetooth" }
  }

  Process {
    id: action
    property bool inFlight: false
    property int page: 0
    property string label: ""
    property string failure: ""
    property string stderrLine: ""
    property string secret: ""
    property bool isJoin: false
    property bool retry: false

    stderr: SplitParser {
      onRead: line => { if (!action.isJoin && line.trim()) action.stderrLine = line.trim(); }
    }
    onStarted: {
      if (stdinEnabled) {
        write(secret);
        stdinEnabled = false;
      }
      secret = "";
    }
    onRunningChanged: if (!running && inFlight) Qt.callLater(action.checkLaunch)
    onExited: (code, status) => {
      inFlight = false;
      if (code !== 0 || status !== 0) {
        failure = isJoin ? "Could not connect. Check the password and try again."
          : stderrLine || "Could not complete the control action.";
      } else if (retry && page === root.page) {
        const watch = [audioWatch, wifiWatch, bluetoothWatch][page - 4]?.item;
        if (watch && !watch.running)
          watch.running = true;
      }
    }

    function checkLaunch() {
      if (running || !inFlight)
        return;
      secret = "";
      stdinEnabled = false;
      failure = "Could not start desktop-menu.";
      inFlight = false;
    }
  }
}
