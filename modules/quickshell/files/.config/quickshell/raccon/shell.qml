import QtQuick
import Quickshell
import Quickshell.Io

// Resident entry point. Widgets are LazyLoaders toggled over IPC:
//   qs -c raccon ipc call raccon toggle music
ShellRoot {
  id: root

  LazyLoader {
    id: music
    MusicCard { onCloseRequested: music.active = false }
  }

  // The catalogue is preloaded at startup so opening is instant; the window itself exists only while open.
  QtObject { id: wallpaper; property bool active: false }
  WallStore { id: wallStore; active: wallpaper.active }
  LazyLoader { active: wallpaper.active; Wall { store: wallStore; onCloseRequested: wallpaper.active = false } }

  LazyLoader {
    id: session
    Float { onCloseRequested: session.active = false }
  }

  LazyLoader {
    id: capture
    Capture { onCloseRequested: capture.active = false }
  }

  LazyLoader {
    id: captureframe
    CaptureFrame { onCloseRequested: captureframe.active = false }
  }

  LazyLoader {
    id: capturepreview
    CapturePreview { onCloseRequested: capturepreview.active = false }
  }

  LazyLoader {
    id: countdown
    Countdown { onCloseRequested: countdown.active = false }
  }

  // Outside the menu loader so closing the menu does not kill an in-flight action.
  MenuControlBackend {
    id: controls
    page: menu.active ? menu.item.page : 0
  }

  LazyLoader {
    id: menu
    MenuHost {
      wallpaperHandler: () => { wallpaper.active = true; }
      onCloseRequested: menu.active = false

      audioPage: Component {
        MenuAudio {
          model: controls.audio
          busy: controls.busy
          actionMessage: controls.message
          actionError: controls.error
          onCommandRequested: (args, label) => controls.dispatch(args, label)
          onVolumeRequested: (channel, percent) => controls.setVolume(channel, percent)
        }
      }
      wifiPage: Component {
        MenuWifi {
          model: controls.wifi
          busy: controls.busy
          actionMessage: controls.message
          actionError: controls.error
          onCommandRequested: (args, label) => controls.dispatch(args, label)
          onJoinRequested: (token, password) => controls.dispatch(["wifi-connect", token], "Connecting…", password)
        }
      }
      bluetoothPage: Component {
        MenuBluetooth {
          model: controls.bluetooth
          busy: controls.busy
          actionMessage: controls.message
          actionError: controls.error
          onCommandRequested: (args, label) => controls.dispatch(args, label)
        }
      }
    }
  }

  LazyLoader {
    id: bar
    active: true
    Bar { onCloseRequested: bar.active = false }
  }

  readonly property var widgets: ({ music, wallpaper, session, capture, captureframe, capturepreview, countdown, menu, bar })

  IpcHandler {
    target: "raccon"

    function ping(): string { return "pong"; }
    function list(): string { return Object.keys(root.widgets).join("\n"); }

    function toggle(name: string): void {
      const w = root.widgets[name];
      if (w) w.active = !w.active;
    }

    function open(name: string): void {
      const w = root.widgets[name];
      if (w) w.active = true;
    }

    function close(name: string): void {
      const w = root.widgets[name];
      if (w) w.active = false;
    }

    function openMenu(page: int): void {
      if (page < 0 || page > 9) return;
      menu.active = true;
      menu.item.openPage(page);
    }
  }
}
