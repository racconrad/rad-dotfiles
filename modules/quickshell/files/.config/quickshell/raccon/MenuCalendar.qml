import QtQuick
import Quickshell

// Physical paper calendar sheet with Tag tab, SekaiPop tilted today tile, and tertiary accents.
Item {
  id: root
  property var model: ({
    day: 1, month: 1, year: 2026, date: "", month_title: "Calendar",
    weekdays: ["M", "T", "W", "T", "F", "S", "S"], weeks: [], error: ""
  })

  signal todayRequested
  signal moveRequested(int offset)
  signal dateSelected(string iso)

  readonly property string menuBin: Quickshell.env("HOME") + "/.local/bin/desktop-menu"

  implicitWidth: 302
  implicitHeight: col.implicitHeight

  Item {
    id: card
    width: root.width
    height: col.implicitHeight

    Column {
      id: col
      anchors {
        left: parent.left
        right: parent.right
        top: parent.top
      }
      spacing: 8

      MenuCalendarHeader {
        width: parent.width
        monthTitle: root.model ? root.model.month_title || "Calendar" : "Calendar"
        dateText: root.model && root.model.date ? root.model.date : ""
        onTodayRequested: {
          root.todayRequested();
          Quickshell.execDetached([root.menuBin, "calendar", "today"]);
        }
        onMoveRequested: offset => {
          root.moveRequested(offset);
          Quickshell.execDetached([root.menuBin, "calendar", "move", String(offset)]);
        }
      }

      Row {
        width: parent.width
        Repeater {
          model: root.model && root.model.weekdays ? root.model.weekdays : ["M", "T", "W", "T", "F", "S", "S"]
          Text {
            required property string modelData
            width: (parent.width - 18) / 7
            height: 20
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: modelData
            color: Theme.tertiary
            font { family: Theme.fontTag; pixelSize: 12; weight: 800 }
          }
        }
      }

      Zigzag {
        width: parent.width
        height: 6
        color: Theme.ink
        edge: "bottom"
        teeth: 16
      }

      MenuCalendarGrid {
        width: parent.width
        weeks: root.model && root.model.weeks ? root.model.weeks : []
        onDateSelected: iso => {
          root.dateSelected(iso);
          Quickshell.execDetached([root.menuBin, "calendar", "select", iso]);
        }
      }
    }
  }
}
