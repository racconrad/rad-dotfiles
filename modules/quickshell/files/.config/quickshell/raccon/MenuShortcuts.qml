import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts

// Physical paper shortcuts browser with secondary key caps and SekaiPop styling.
Item {
  id: root

  property var sections: []
  property bool ascii: false
  readonly property var filtered: {
    const words = search.words(search.text);
    return sections.map(section => ({
      title: section.title,
      rows: section.rows.filter(row => {
        const key = row.search ?? (row.keys + " " + row.action).toLowerCase();
        return words.every(word => key.includes(word));
      })
    })).filter(section => section.rows.length);
  }
  property alias searchBar: search

  function clearQuery() {
    if (!search.text.length) return false;
    search.text = ""; search.field.forceActiveFocus(); scroll.contentY = 0; return true;
  }
  function focusFirst() {
    const item = groups.itemAt(0); const first = item ? item.firstRow : null;
    if (!first) return false;
    first.forceActiveFocus(Qt.TabFocusReason); return true;
  }

  implicitWidth: 302
  implicitHeight: col.implicitHeight

  Item {
    id: card
    width: root.width
    height: col.implicitHeight

    Column {
      id: col
      anchors { left: parent.left; right: parent.right; top: parent.top;  }
      spacing: 6

      Sticker { text: "SHORTCUTS"; tone: "paper" }

      MenuSearch {
        id: search; width: col.width; field.objectName: "menuShortcutSearch"
        placeholder: "Search shortcuts…"; ascii: root.ascii; onEdited: scroll.contentY = 0
      }

      Item {
        width: col.width; height: 280
        Text {
          visible: !root.filtered.length; anchors.centerIn: parent; text: "NO SHORTCUTS MATCH"
          color: Theme.on_surface_variant; font { family: Theme.fontTag; pixelSize: 12; weight: Font.Bold }
        }

        Flickable {
          id: scroll; anchors.fill: parent; clip: true; boundsBehavior: Flickable.StopAtBounds
          contentWidth: width; contentHeight: content.height
          Column {
            id: content; width: scroll.width; spacing: 8
            Repeater {
              id: groups; model: root.filtered
              Column {
                id: group; required property var modelData
                readonly property Item firstRow: rows.itemAt(0)
                width: content.width; spacing: 3
                Tag { text: group.modelData.title.toUpperCase(); tone: "secondary"; tilt: 0 }

                Repeater {
                  id: rows; model: group.modelData.rows
                  Rectangle {
                    antialiasing: true
                    id: shortcutRow; required property var modelData
                    width: group.width; height: rowCol.implicitHeight + 8; radius: Theme.radius
                    color: rowArea.containsMouse ? Theme.tone("paper").bg : Theme.surface_container_highest
                    border.width: 1; border.color: Theme.ink

                    AccentBar { tone: "secondary"; grow: rowArea.containsMouse }

                    Column {
                      id: rowCol
                      anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 8; rightMargin: 8 }
                      spacing: 2
                      Rectangle {
                        antialiasing: true
                        width: capText.implicitWidth + 8; height: capText.implicitHeight + 2
                        radius: Theme.radius; color: Theme.surface_container
                        border.width: 1; border.color: Theme.secondary
                        Text {
                          id: capText; anchors.centerIn: parent; text: shortcutRow.modelData.keys
                          color: Theme.secondary; font { family: Theme.fontTag; pixelSize: 12; weight: Font.Bold }
                        }
                      }
                      Text {
                        width: parent.width; text: shortcutRow.modelData.action
                        elide: Text.ElideRight; color: Theme.on_surface
                        font { family: Theme.fontTag; pixelSize: 12 }
                      }
                    }
                    MouseArea { id: rowArea; anchors.fill: parent; hoverEnabled: true }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
