import QtQuick
import QtQuick.Layouts

Item {
  id: root

  property var desktop: ({})
  property var catalogue: ({})
  property bool editing: false
  property int page: 0
  property string query: ""
  property string error: ""
  property alias searchBar: search
  property alias searchField: search.field
  readonly property bool ascii: desktop.ascii ?? false
  readonly property var results: {
    const words = search.words(query);
    const entries = catalogue.search ?? [];
    return words.length ? entries.filter(app => words.every(word => (app.search ?? "").includes(word))) : entries;
  }

  signal editRequested(); signal closeRequested(); signal pageRequested(int page)
  signal searchEdited(string text); signal activated(var app); signal commandRequested(var args)

  width: 560; height: 530
  scale: 1.0; rotation: 0; transformOrigin: Item.BottomLeft

  function tileAt(index) { return home.tileAt(index); }
  function focusFirst() {
    if (page === 1) return apps.focusResult(0);
    const tile = home.favorites.map((_, index) => tileAt(index)).find(button => button && button.enabled);
    if (!tile) return false;
    tile.forceActiveFocus(Qt.TabFocusReason);
    return true;
  }

  Component.onCompleted: if (Theme.animations) slapIn.start()

  ParallelAnimation {
    id: slapIn
    NumberAnimation { target: root; property: "scale"; from: 1.05; to: 1.0; duration: Theme.motionBase; easing.type: Easing.OutBack }
    NumberAnimation { target: root; property: "rotation"; from: -1.5; to: 0; duration: Theme.motionBase; easing.type: Easing.OutQuad }
  }

  readonly property real sheetW: root.width - 12
  readonly property real sheetH: root.height - 12

  Backdrop { x: 0; y: 0; width: root.sheetW; height: root.sheetH; animated: false }
  Rectangle { x: 10; y: 10; width: root.sheetW; height: root.sheetH; color: Theme.tone("tertiary").bg; radius: Theme.radius }

  Rectangle {
    antialiasing: true
    id: frontSheet
    x: 0; y: 0; width: root.sheetW; height: root.sheetH
    color: Theme.tone("paper").bg; border.width: Theme.border; border.color: Theme.ink; radius: Theme.radius

    Ridge {}

    Zigzag {
      anchors.bottom: parent.bottom
      anchors.left: parent.left
      anchors.right: parent.right
      edge: "bottom"
      depth: 8
      color: Theme.tone("paper").bg
    }

    Tape {
      striped: true
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.topMargin: -8
      anchors.leftMargin: 20
      tilt: -6
    }

    ColumnLayout {
      id: content
      anchors.fill: parent; anchors.margins: 14; spacing: 8

      MenuHeader {
        Layout.fillWidth: true
        title: root.ascii ? "[ " + (root.desktop.user ?? "") + " ]" : (root.desktop.user ?? "")
        avatar: root.desktop.has_avatar ? (root.desktop.avatar ?? "") : ""
        canEdit: root.page === 0; editing: root.editing
        onEditRequested: root.editRequested(); onCloseRequested: root.closeRequested()
      }

      MenuSearch {
        id: search
        Layout.fillWidth: true; field.objectName: "menuAppSearch"
        text: root.query; ascii: root.ascii
        onEdited: value => { root.searchEdited(value); apps.resetPosition(); }
        onAccepted: {
          if (root.results.length) root.activated(root.results[0]);
          else if (root.page !== 1) root.pageRequested(1);
        }
      }

      MenuHome {
        id: home
        Layout.fillWidth: true; Layout.fillHeight: true
        visible: root.page !== 1; editing: root.editing; catalogue: root.catalogue
        onActivated: app => root.activated(app); onCommandRequested: args => root.commandRequested(args)
        onBrowseRequested: root.pageRequested(1); onPageRequested: p => root.pageRequested(p)
      }

      MenuApps {
        id: apps
        Layout.fillWidth: true; Layout.fillHeight: true
        visible: root.page === 1; results: root.results; editing: root.editing; canAdd: home.canAdd
        onActivated: app => root.activated(app); onCommandRequested: args => root.commandRequested(args)
      }

      Text {
        Layout.fillWidth: true; visible: root.error.length > 0
        text: root.error; textFormat: Text.PlainText; wrapMode: Text.Wrap
        color: Theme.error; font.family: Theme.fontDisplay; font.pixelSize: 12
      }

    }
  }
}
