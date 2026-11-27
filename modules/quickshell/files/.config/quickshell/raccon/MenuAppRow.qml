import QtQuick
import QtQuick.Layouts

Item {
  id: row
  required property int index
  required property var modelData
  property Item launchButton: launch
  property ListView listView: null
  property bool editing: false
  property bool canAdd: true

  signal activated(var app)
  signal commandRequested(var args)
  signal focusResultRequested(int idx)

  implicitWidth: listView ? listView.width - 6 : 280
  implicitHeight: layout.implicitHeight

  RowLayout {
    id: layout
    anchors.fill: parent
    spacing: 6

    Rectangle {
      antialiasing: true
      Layout.fillWidth: true; Layout.minimumHeight: 38
      color: Theme.tone("paper").bg
      border.width: Theme.border; border.color: Theme.ink; radius: Theme.radius

      AccentBar {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        barWidth: 4; color: [Theme.primary, Theme.secondary, Theme.tertiary][row.index % 3]
      }

      MenuButton {
        id: launch
        anchors.fill: parent; anchors.leftMargin: 8
        objectName: "menuAppResult" + row.index
        leftPadding: 8; rightPadding: 8; glyphSize: 22
        artwork: row.modelData
        glyph: row.modelData.category === "Setting" ? "󰒓" : row.modelData.category === "Action" ? "󰓥" : "󰀻"
        text: row.modelData.name; detail: row.modelData.category ?? ""; hint: row.modelData.name
        result: true
        selected: row.listView && (row.index === row.listView.currentIndex || row.index === 0)
        onClicked: row.activated(row.modelData)
        onActiveFocusChanged: if (activeFocus && row.listView) row.listView.positionViewAtIndex(row.index, ListView.Contain)
        Keys.onDownPressed: event => { row.focusResultRequested(row.index + 1); event.accepted = true; }
        Keys.onUpPressed: event => { row.focusResultRequested(row.index - 1); event.accepted = true; }
        Keys.onTabPressed: event => {
          if (!pin.visible || !pin.enabled) { row.focusResultRequested(row.index + 1); event.accepted = true; }
          else event.accepted = false;
        }
        Keys.onBacktabPressed: event => {
          if (!row.editing) { row.focusResultRequested(row.index - 1); event.accepted = true; }
          else event.accepted = false;
        }
      }
    }

    MenuButton {
      id: pin
      visible: row.editing && (row.modelData.pinnable ?? false)
      enabled: row.canAdd || (row.modelData.pinned ?? false)
      selected: row.modelData.pinned ?? false
      glyph: selected ? "󰍴" : "󰐕"
      hint: selected ? "Remove from Home" : "Add to Home"
      onClicked: row.commandRequested(["favorite", selected ? "remove" : "add", row.modelData.ref])
      onActiveFocusChanged: if (activeFocus && row.listView) row.listView.positionViewAtIndex(row.index, ListView.Contain)
      Keys.onTabPressed: event => { row.focusResultRequested(row.index + 1); event.accepted = true; }
    }
  }
}
