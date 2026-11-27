import QtQuick
import QtQuick.Layouts

// Home mosaic: tiles of different sizes, one loud tile (Apps), the rest paper with an accent bar.
GridLayout {
  id: root

  columns: 4
  columnSpacing: 8
  rowSpacing: 8

  signal browseRequested()
  signal pageRequested(int page)
  signal commandRequested(var args)

  readonly property var tiles: [
    { page: 1,  label: "APPS",       glyph: "󰀻", accent: "primary",   cols: 2, rows: 2, loud: true },
    { page: 4,  label: "AUDIO",      glyph: "󰕾", accent: "secondary", cols: 1, rows: 1 },
    { page: 5,  label: "WI-FI",      glyph: "󰖩", accent: "tertiary",  cols: 1, rows: 1 },
    { page: 6,  label: "BLUETOOTH",  glyph: "󰂯", accent: "primary",   cols: 2, rows: 1 },
    { page: 7,  label: "CALENDAR",   glyph: "󰃭", accent: "tertiary",  cols: 2, rows: 1 },
    { page: 9,  label: "TIMER",      glyph: "󰀠", accent: "secondary", cols: 1, rows: 1 },
    { page: 2,  label: "POWER",      glyph: "󰠠", accent: "primary",   cols: 1, rows: 1 },
    { page: 8,  label: "KEYS",       glyph: "󰌌", accent: "secondary", cols: 1, rows: 1 },
    { page: -1, label: "WALLPAPERS", glyph: "󰸉", accent: "tertiary",  cols: 1, rows: 1 },
    { page: 3,  label: "SESSION",    glyph: "󰐥", accent: "error",     cols: 2, rows: 1 }
  ]

  Repeater {
    model: root.tiles

    Item {
      id: tile
      required property var modelData

      Layout.columnSpan: modelData.cols
      Layout.rowSpan: modelData.rows
      Layout.fillWidth: true
      Layout.fillHeight: true
      Layout.preferredHeight: 48 * modelData.rows + 8 * (modelData.rows - 1)
      Layout.preferredWidth: 100 * modelData.cols

      readonly property color accent: Theme[modelData.accent]
      readonly property bool hovered: area.containsMouse && !area.pressed
      readonly property bool filled: modelData.loud === true || hovered
      readonly property color ink: filled ? Theme.surface : Theme.on_surface

      Rectangle {
        antialiasing: true
        x: tile.hovered ? 5 : 3; y: tile.hovered ? 5 : 3
        width: parent.width; height: parent.height
        color: Theme.tone(tile.modelData.accent).bg; radius: Theme.radius
        Behavior on x { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
        Behavior on y { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
      }

      Rectangle {
        antialiasing: true
        x: area.pressed ? 2 : (tile.hovered ? -2 : 0)
        y: area.pressed ? 2 : (tile.hovered ? -2 : 0)
        width: parent.width; height: parent.height
        color: tile.filled ? tile.accent : Theme.tone("paper").bg
        border.width: Theme.border; border.color: Theme.ink; radius: Theme.radius
        Behavior on x { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
        Behavior on y { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
        Behavior on color { enabled: Theme.animations; ColorAnimation { duration: Theme.motionFast } }

        AccentBar {
          visible: !tile.filled
          anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
          barWidth: 4
          color: tile.accent
        }

        Text {
          id: glyph
          anchors { left: parent.left; leftMargin: 14; verticalCenter: tile.modelData.loud ? undefined : parent.verticalCenter; top: tile.modelData.loud ? parent.top : undefined; topMargin: 12 }
          text: tile.modelData.glyph; color: tile.filled ? tile.ink : tile.accent
          font.family: Theme.fontMono; font.pixelSize: tile.modelData.loud ? 44 : 24
        }

        Text {
          anchors {
            left: tile.modelData.loud ? parent.left : glyph.right; leftMargin: tile.modelData.loud ? 14 : 10
            bottom: tile.modelData.loud ? parent.bottom : undefined; bottomMargin: 12
            verticalCenter: tile.modelData.loud ? undefined : parent.verticalCenter
          }
          text: tile.modelData.label; color: tile.ink
          font.family: Theme.fontDisplay; font.weight: 800; font.pixelSize: tile.modelData.loud ? 28 : 14
        }

        MouseArea {
          id: area
          anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
          onClicked: {
            const page = tile.modelData.page;
            if (page === 1) root.browseRequested();
            else if (page === -1) root.commandRequested(["shortcut", "wallpaper"]);
            else root.pageRequested(page);
          }
        }
      }
    }
  }
}
