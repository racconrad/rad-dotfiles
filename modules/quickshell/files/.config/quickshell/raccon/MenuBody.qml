import QtQuick
import QtQuick.Window
import "MenuNavigation.js" as Navigation

FocusScope {
  id: root

  property var catalogue: ({})
  property var desktop: ({})
  property var modes: []
  property var shortcuts: []
  property bool busy: false
  property string error: ""
  property alias audioPage: side.audioPage
  property alias wifiPage: side.wifiPage
  property alias bluetoothPage: side.bluetoothPage
  property alias calendarPage: side.calendarPage
  property alias timerPage: side.timerPage

  readonly property alias page: menuState.page
  readonly property alias editing: menuState.editing
  readonly property alias selected: menuState.selected
  readonly property alias confirmation: menuState.confirmation
  property alias mainRegion: main
  property alias sideRegion: side
  signal closeRequested()
  signal commandRequested(var args)

  // Fixed footprint: the side card animates inside it, so the layer surface never resizes (the mask limits input).
  implicitWidth: main.width + 12 + side.panelWidth
  implicitHeight: Math.max(main.height, side.height)
  focus: true

  function openPage(index) {
    menuState.openPage(index);
    Qt.callLater(focusPage);
  }

  function focusPage() {
    const target = side.focusItem ? side.focusItem : main.searchField;
    if (target) target.forceActiveFocus();
  }

  function handleEscape() {
    if (side.clearShortcutQuery()) return;
    if (menuState.query.length) {
      menuState.search("");
      focusPage();
    } else if (menuState.confirmation) {
      menuState.confirmation = "";
      side.focusFirstAction();
    } else if (page > 0) {
      openPage(0);
    } else {
      closeRequested();
    }
  }

  function routeKey(event) {
    const key = event.key;
    const win = root.Window.window;
    const active = win ? win.activeFocusItem : null;
    const modifiers = event.modifiers;
    if (modifiers & Qt.ControlModifier) {
      if (key >= Qt.Key_1 && key <= Qt.Key_9) openPage(key - Qt.Key_1);
      else if (key === Qt.Key_F || key === Qt.Key_L) openPage(1);
      else if (key === Qt.Key_W) closeRequested();
      else return;
    } else if ((modifiers & Qt.AltModifier) && key >= Qt.Key_1 && key <= Qt.Key_9) {
      const tile = main.tileAt(key - Qt.Key_1);
      if (tile && tile.enabled && !event.isAutoRepeat) tile.clicked();
    } else if (key === Qt.Key_Escape) {
      if (!event.isAutoRepeat) handleEscape();
    } else if (!(modifiers & (Qt.AltModifier | Qt.MetaModifier))) {
      if (key === Qt.Key_Down && active === main.searchField && main.focusFirst()) event.accepted = true;
      else if (key === Qt.Key_Down && side.shortcutSearch && side.shortcutSearch.field && active === side.shortcutSearch.field && side.focusFirstShortcut()) event.accepted = true;
      else if ([Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down].includes(key)) event.accepted = !!active && Navigation.move(active, root, key);
      else if (event.text && !/[\x00-\x1F\x7F]/.test(event.text) && active && active.inputMethodComposing === undefined) {
        const bar = menuState.page === 8 ? side.shortcutSearch : main.searchBar;
        if (bar) bar.appendText(event.text);
        event.accepted = !!bar;
      }
      return;
    } else {
      return;
    }
    event.accepted = true;
  }

  Keys.priority: Keys.AfterItem
  Keys.onPressed: event => root.routeKey(event)
  Component.onCompleted: Qt.callLater(focusPage)

  MenuState {
    id: menuState
    selected: root.desktop.preference ?? "auto"
    onCommandRequested: args => root.commandRequested(args)
  }

  MenuMain {
    id: main
    anchors.bottom: parent.bottom
    desktop: root.desktop; catalogue: root.catalogue
    editing: menuState.editing; page: menuState.page; query: menuState.query; error: root.error
    onEditRequested: menuState.editing = !menuState.editing
    onCloseRequested: root.closeRequested()
    onPageRequested: index => root.openPage(index)
    onSearchEdited: text => menuState.search(text)
    onActivated: row => {
      const previousPage = menuState.page;
      menuState.activate(row);
      if (previousPage !== menuState.page) Qt.callLater(root.focusPage);
    }
    onCommandRequested: args => root.commandRequested(args)
  }

  MenuSide {
    id: side
    anchors { left: main.right; leftMargin: 12; bottom: parent.bottom }
    page: menuState.page; desktop: root.desktop; modes: root.modes; shortcuts: root.shortcuts; busy: root.busy
    selected: menuState.selected; confirmation: menuState.confirmation
    onBackRequested: root.openPage(0)
    onSelectRequested: mode => { menuState.selected = mode; }
    onApplyRequested: root.commandRequested(["apply", menuState.selected])
    onConfirmRequested: action => { menuState.confirmation = action; }
    onCommandRequested: args => {
      if (args[0] === "session-action") {
        if (!menuState.confirmation || args[1] !== menuState.confirmation) return;
        menuState.confirmation = "";
      }
      root.commandRequested(args);
    }
  }
}
