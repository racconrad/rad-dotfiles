import QtQuick
import QtQuick.Layouts

// Power modes in a compact two-column grid on the side sheet, with one apply button.
Item {
  id: root

  property var modes: []
  property var desktop: ({})
  property string selected: "auto"
  property bool busy: false
  readonly property Item firstAction: applying ? null : modeRows.itemAt(0)
  readonly property bool applying: busy || Boolean(desktop && desktop.applying)
  readonly property bool unchanged: selected === (desktop ? desktop.source : "") && !Boolean(desktop && desktop.has_errors)
  signal selectRequested(string mode)
  signal applyRequested

  implicitWidth: 302
  implicitHeight: col.implicitHeight

  Column {
    id: col
    anchors { left: parent.left; right: parent.right; top: parent.top }
    spacing: 8

    Sticker {
      text: "POWER MODES"
      tone: "primary"
    }

    GridLayout {
      width: col.width
      columns: 2
      columnSpacing: 8
      rowSpacing: 8

      Repeater {
        id: modeRows
        model: root.modes
        CutButton {
          required property var modelData
          Layout.fillWidth: true
          implicitHeight: 48
          enabled: !root.applying
          active: root.selected === modelData.id
          tone: root.selected === modelData.id ? "primary" : "paper"
          icon: ({ auto: "󰒓", performance: "󰁺", balanced: "󰠠", complete: "󰖙", working: "󰅨" })[modelData.id] ?? "󰒓"
          text: modelData.name
          onClicked: root.selectRequested(modelData.id)
        }
      }
    }

    CutButton {
      width: col.width
      enabled: root.modes.length > 0 && !root.applying && (!root.unchanged || !(root.desktop && root.desktop.ready))
      tone: "primary"
      icon: root.applying ? "󰔛" : (root.unchanged ? "󰄬" : "󰐊")
      text: root.applying ? "APPLYING…" : (root.unchanged ? "ACTIVE MODE" : "APPLY MODE")
      onClicked: root.applyRequested()
    }

    Text {
      width: col.width
      visible: Boolean(root.desktop && root.desktop.has_errors)
      text: "Some settings pending. Apply again."
      color: Theme.error
      wrapMode: Text.WordWrap
      font { family: Theme.fontTag; pixelSize: 12; weight: Font.Bold }
    }
  }
}
