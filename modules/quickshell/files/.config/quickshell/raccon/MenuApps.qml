import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts

ColumnLayout {
  id: root

  property var results: []
  property bool editing: false
  property bool canAdd: true
  property int viewportHeight: 330
  signal activated(var app)
  signal commandRequested(var args)

  spacing: 6

  function focusResult(index) {
    if (index < 0 || index >= list.count) return false;
    list.currentIndex = index;
    list.positionViewAtIndex(index, ListView.Contain);
    list.forceLayout();
    const row = list.currentItem as MenuAppRow;
    const button = row ? row.launchButton : null;
    if (button) button.forceActiveFocus(Qt.TabFocusReason);
    return !!button;
  }

  function resetPosition() {
    list.currentIndex = -1;
    list.positionViewAtBeginning();
  }

  RowLayout {
    Layout.fillWidth: true; spacing: 8

    Item { Layout.fillWidth: true }
    Text {
      visible: root.editing; text: root.canAdd ? "+ to pin to Home" : "Home limit reached"
      color: Theme.on_surface_variant; font.family: Theme.fontDisplay; font.pixelSize: 12
    }
  }

  Item {
    Layout.fillWidth: true; implicitHeight: root.viewportHeight

    Text {
      visible: list.count === 0; x: 4; y: 14
      text: "No matches found. Try another search term."
      color: Theme.on_surface_variant; font.family: Theme.fontDisplay; font.pixelSize: 13
    }

    ListView {
      id: list
      anchors.fill: parent; clip: true; spacing: 5
      model: root.results; reuseItems: true; boundsBehavior: Flickable.StopAtBounds; keyNavigationEnabled: false

      Controls.ScrollBar.vertical: Controls.ScrollBar {
        width: 5
        contentItem: Rectangle { radius: Theme.radius; color: Theme.ink; border.width: 1; border.color: Theme.shadowColor }
      }

      delegate: MenuAppRow {
        listView: list; editing: root.editing; canAdd: root.canAdd
        onActivated: app => root.activated(app)
        onCommandRequested: args => root.commandRequested(args)
        onFocusResultRequested: idx => root.focusResult(idx)
      }
    }
  }
}
