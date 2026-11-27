import QtQuick

Item {
  id: root

  property int page: 0
  property string selected: "auto"
  property string confirmation: ""
  property bool busy: false
  property var desktop: ({})
  property var modes: []
  property var shortcuts: []
  property Component audioPage: Item {}
  property Component wifiPage: Item {}
  property Component bluetoothPage: Item {}
  property Component calendarPage: Item {}
  property Component timerPage: Item {}
  property int renderedPage: 0

  signal backRequested()
  signal selectRequested(string mode)
  signal applyRequested()
  signal confirmRequested(string action)
  signal commandRequested(var args)

  readonly property int panelWidth: 340
  readonly property Item loadedItem: load.item as Item
  readonly property real contentHeight: Math.max(0, loadedItem ? loadedItem.implicitHeight : 0)
  readonly property MenuShortcuts keyboardPage: load.item as MenuShortcuts
  readonly property MenuSearch shortcutSearch: page === 8 ? (keyboardPage ? keyboardPage.searchBar : null) : null
  readonly property Item focusItem: {
    if (page === 8)
      return shortcutSearch ? shortcutSearch.field : null;
    if (page === 2)
      return (load.item as MenuModes) ? (load.item as MenuModes).firstAction : null;
    if (page === 3)
      return (load.item as MenuSession) ? (load.item as MenuSession).firstAction : null;
    return page >= 4 ? externalFocus(loadedItem) : null;
  }

  width: page >= 2 && contentHeight > 0 ? panelWidth : 0
  // Pages report their own height.
  height: Math.min(520, contentHeight + 38)
  visible: (page >= 2 && contentHeight > 0) || width > 0
  enabled: page >= 2
  clip: true

  onPageChanged: {
    if (page >= 2)
      renderedPage = page;
    else if (width === 0)
      renderedPage = 0;
  }
  Component.onCompleted: if (page >= 2) renderedPage = page
  onWidthChanged: if (width === 0 && page < 2) renderedPage = 0

  Behavior on width {
    enabled: Theme.animations
    NumberAnimation { duration: Theme.motionBase; easing.type: Easing.OutCubic }
  }

  function externalFocus(item) { return item ? item.initialFocusItem : null; }
  function focusFirstShortcut() { return page === 8 && (keyboardPage ? keyboardPage.focusFirst() : false); }
  function focusFirstAction() { if (page === 3) { const s = load.item as MenuSession; if (s) s.restoreFocus(); } }
  function clearShortcutQuery() { return page === 8 && (keyboardPage ? keyboardPage.clearQuery() : false); }

  readonly property real sheetW: root.panelWidth - 10
  readonly property real sheetH: root.height - 10

  // One sheet with uneven corners (big top-left and bottom-right) and a hard soft-purple shadow.
  Rectangle {
    antialiasing: true
    x: 7; y: 7
    width: root.sheetW; height: root.sheetH
    color: Theme.toneAt(root.renderedPage).bg
    radius: 10
    topLeftRadius: 34; bottomRightRadius: 34
  }

  Rectangle {
    id: sheet
    antialiasing: true
    x: 0; y: 0
    width: root.sheetW
    height: root.sheetH
    radius: 10
    topLeftRadius: 34; bottomRightRadius: 34
    color: Theme.tone("paper").bg

    // Soft colour shapes behind the content, kept inside the corners.
    Rectangle {
      width: 70; height: 70; radius: 35
      x: parent.width - width - 14; y: 14
      color: Theme.tone("tertiary").bg; opacity: 0.55
      SequentialAnimation on y {
        running: Theme.animations && root.width > 0; loops: Animation.Infinite
        NumberAnimation { to: 20; duration: 2600; easing.type: Easing.InOutSine }
        NumberAnimation { to: 14; duration: 2600; easing.type: Easing.InOutSine }
      }
    }
    Rectangle {
      width: 90; height: 34; radius: 17
      x: 14; y: parent.height - height - 16
      color: Theme.tone("secondary").bg; opacity: 0.5
      SequentialAnimation on x {
        running: Theme.animations && root.width > 0; loops: Animation.Infinite
        NumberAnimation { to: 26; duration: 3200; easing.type: Easing.InOutSine }
        NumberAnimation { to: 14; duration: 3200; easing.type: Easing.InOutSine }
      }
    }

    Ridge { x: 34; width: parent.width - 68 }

    Loader {
      id: load
      anchors.fill: parent
      anchors.margins: 14
      sourceComponent: [null, null, power, session, root.audioPage, root.wifiPage, root.bluetoothPage,
        root.calendarPage, keys, root.timerPage][root.renderedPage] ?? null
      onLoaded: {
        if (Theme.animations)
          stampAnim.restart();
      }
      ParallelAnimation {
        id: stampAnim
        NumberAnimation { target: load; property: "scale"; from: 0.9; to: 1.0; duration: Theme.motionSlap; easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot }
        NumberAnimation { target: load; property: "opacity"; from: 0; to: 1; duration: Theme.motionBase; easing.type: Easing.OutQuad }
      }
    }
  }

  Component {
    id: power
    MenuModes {
      desktop: root.desktop
      modes: root.modes
      busy: root.busy
      selected: root.selected
      onSelectRequested: mode => root.selectRequested(mode)
      onApplyRequested: root.applyRequested()
    }
  }
  Component {
    id: session
    MenuSession {
      confirmation: root.confirmation
      busy: root.busy
      onBackRequested: root.backRequested()
      onConfirmRequested: action => root.confirmRequested(action)
      onCommandRequested: args => root.commandRequested(args)
    }
  }
  Component {
    id: keys
    MenuShortcuts { sections: root.shortcuts; ascii: root.desktop.ascii ?? false }
  }
}
