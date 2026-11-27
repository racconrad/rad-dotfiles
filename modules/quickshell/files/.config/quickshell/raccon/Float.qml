import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Floating session dialog (lock, logout, suspend, reboot, power off).
PanelWindow {
  id: root
  signal closeRequested

  property var whoData: ({ user: Quickshell.env("USER") || "user", host: "localhost", uptime: "0m" })

  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.namespace: "raccon-float"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
  mask: Region { item: body }

  Process {
    running: true
    command: ["sh", "-c", 'read -r u _ < /proc/uptime; s=${u%%.*}; d=$((s/86400)); h=$(((s%86400)/3600)); m=$(((s%3600)/60)); out=""; [ $d -gt 0 ] && out="${d}d "; [ $h -gt 0 ] && out="${out}${h}h "; printf "%s|%s" "$(cat /etc/hostname 2>/dev/null || echo localhost)" "${out}${m}m"']
    stdout: SplitParser {
      onRead: line => {
        const [host, uptime] = line.split("|");
        root.whoData = { user: Quickshell.env("USER") || "user", host: host || "localhost", uptime: uptime || "0m" };
      }
    }
  }

  Shortcut {
    sequence: "Escape"
    onActivated: {
      if (body.armed !== "") body.armed = "";
      else root.closeRequested();
    }
  }
  Shortcut { sequence: "Ctrl+W"; onActivated: root.closeRequested() }

  FloatBody {
    id: body
    anchors.centerIn: parent
    who: root.whoData

    onCloseRequested: root.closeRequested()
    onActionTriggered: action => {
      root.closeRequested();
      if (action === "lock") Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/lock"]);
      else if (action === "logout") Quickshell.execDetached(["loginctl", "terminate-session", Quickshell.env("XDG_SESSION_ID")]);
      else Quickshell.execDetached(["systemctl", action]);
    }
  }
}
