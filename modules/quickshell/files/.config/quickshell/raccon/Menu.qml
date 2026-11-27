import QtQuick
import Quickshell
import Quickshell.Wayland

PanelWindow {
  id: root

  property alias wallpaperHandler: backend.wallpaperHandler
  property alias audioPage: body.audioPage
  property alias wifiPage: body.wifiPage
  property alias bluetoothPage: body.bluetoothPage
  property alias calendarPage: body.calendarPage
  property alias timerPage: body.timerPage
  readonly property alias page: body.page
  signal closeRequested()

  function openPage(index) { body.openPage(index); }

  anchors { bottom: true; left: true }
  margins { left: 16; bottom: 74 }
  implicitWidth: body.implicitWidth
  implicitHeight: body.implicitHeight
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.namespace: "raccon-menu"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

  mask: Region {
    Region { item: body.mainRegion }
    Region { item: body.sideRegion }
  }

  MenuBackend {
    id: backend
    onDismissRequested: root.closeRequested()
  }

  MenuBody {
    id: body
    anchors.fill: parent
    catalogue: backend.catalogue
    desktop: backend.desktop
    modes: backend.modes
    shortcuts: backend.shortcuts
    busy: backend.busy
    error: backend.error
    onCommandRequested: args => backend.dispatch(args)
    onCloseRequested: root.closeRequested()
  }
}
