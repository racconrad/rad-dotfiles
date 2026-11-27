import QtQuick
import Quickshell
import Quickshell.Io

Scope {
  id: root

  readonly property string home: Quickshell.env("HOME")
  readonly property string menu: home + "/.local/bin/desktop-menu"
  readonly property string runtime: Quickshell.env("XDG_RUNTIME_DIR") || home + "/.cache"
  property var catalogue: ({})
  property var desktop: ({})
  property var modes: []
  property var shortcuts: []
  property string error: ""
  property var wallpaperHandler: null
  readonly property bool busy: action.running
  signal dismissRequested

  function parse(line, accept) {
    try {
      accept(JSON.parse(line));
    } catch (error) {
      console.warn("Menu: invalid desktop-menu data:", error);
    }
  }

  function dispatch(args) {
    if (action.running)
      return;
    root.error = "";
    let command = [menu, ...args];
    action.dismiss = false;
    switch (args[0]) {
      case "shortcut":
      case "search-action":
        if (args[1] === "wallpaper" && typeof wallpaperHandler === "function")
          wallpaperHandler();
        else
          Quickshell.execDetached(command);
        dismissRequested();
        return;
      case "launch":
        action.dismiss = true;
        break;
      case "favorite":
      case "recent":
        break;
      case "apply":
        if (!modes.some(mode => mode.id === args[1]))
          return;
        command = [home + "/.local/bin/desktop-power", "set", args[1]];
        break;
      case "session-action":
        // Match the checked session path to terminate only the current user session.
        if (args[1] === "logout") {
          const session = Quickshell.env("XDG_SESSION_ID") || "";
          if (!/^[A-Za-z0-9_-]+$/.test(session)) {
            root.error = "Could not identify this session.";
            return;
          }
          command = ["loginctl", "terminate-session", session];
        } else if (["suspend", "reboot", "poweroff"].includes(args[1])) {
          command = ["systemctl", args[1]];
        } else {
          return;
        }
        action.dismiss = true;
        break;
      default:
        return;
    }
    action.message = "";
    action.command = command;
    action.running = true;
  }

  Process {
    command: [root.menu, "watch-catalogue"]
    running: true
    stdout: SplitParser { onRead: line => root.parse(line, data => { root.catalogue = data; }) }
  }
  Process {
    command: [root.menu, "listen"]
    // Isolate the runtime directory so stale visibility markers do not silence this stream.
    environment: ({ XDG_RUNTIME_DIR: root.runtime + "/raccon-quickshell" })
    running: true
    stdout: SplitParser { onRead: line => root.parse(line, data => { root.desktop = data; }) }
  }
  Process {
    command: [root.menu, "modes-data"]
    running: true
    stdout: SplitParser { onRead: line => root.parse(line, data => { root.modes = data; }) }
  }
  Process {
    command: [root.menu, "shortcuts-data"]
    running: true
    stdout: SplitParser { onRead: line => root.parse(line, data => { root.shortcuts = data; }) }
  }
  Process {
    id: action
    property bool dismiss: false
    property string message: ""
    stderr: SplitParser { onRead: line => { if (line.trim()) action.message = line.trim(); } }
    onExited: (code, status) => {
      if (code !== 0 || status !== 0)
        root.error = action.message || "Could not complete the menu action.";
      else if (action.dismiss)
        root.dismissRequested();
    }
  }
}
