import QtQuick

MenuControlPage {
  id: root

  readonly property var device: (model && model.detail) ? model.detail : ({})
  readonly property bool radioOn: Boolean(model && model.enabled)
  readonly property bool scanning: Boolean(model && model.scanning)

  title: "Bluetooth"
  tagText: "06 // BLUETOOTH"
  tone: "secondary"
  kind: "bluetooth"
  loadingText: "Loading Bluetooth devices…"
  initialFocusItem: details.visible ? details.backButton : power.enabled ? power : null

  function deviceGlyph(icon) {
    switch (icon) {
    case "audio-headset": case "audio-headphones": return "󰋋";
    case "audio-card": return "󰓃";
    case "input-keyboard": return "󰌌";
    case "input-mouse": return "󰍽";
    case "input-gaming": return "󰊗";
    case "phone": return "󰏲";
    case "computer": return "󰍹";
    default: return "󰂯";
    }
  }

  function goBack() {
    if (!details.visible || root.busy)
      return false;
    root.commandRequested(["bt-back"], "Loading Bluetooth devices…");
    return true;
  }

  function focusControls() {
    if (root.visible && root.initialFocusItem)
      root.initialFocusItem.forceActiveFocus(Qt.TabFocusReason);
  }

  Keys.onEscapePressed: event => { event.accepted = root.goBack(); }

  headingActions: [
    CutButton {
      icon: "󰑐"
      text: "SCAN"
      tone: "secondary"
      active: root.scanning
      enabled: Boolean(root.model && root.model.available) && root.radioOn && !root.busy
      onClicked: root.commandRequested(["bt-scan"], "Starting Bluetooth scan…")
    },
    CutButton {
      id: power
      icon: "󰐥"
      text: root.radioOn ? "ON" : "OFF"
      tone: root.radioOn ? "secondary" : "paper"
      active: root.radioOn
      enabled: Boolean(root.model && root.model.available) && !root.busy
      onClicked: root.commandRequested(["bt-power", root.radioOn ? "off" : "on"],
        root.radioOn ? "Turning off Bluetooth…" : "Turning on Bluetooth…")
    }
  ]

  MenuControlList {
    width: root.width
    visible: !details.visible
    tone: "secondary"
    rows: root.model && root.model.rows ? root.model.rows : []
    pageIndex: root.model && root.model.list_page ? root.model.list_page : 0
    pageCount: root.model && root.model.page_count ? root.model.page_count : 1
    total: root.model && root.model.total ? root.model.total : 0
    available: root.radioOn && !root.busy
    describe: row => ({
      token: row.token, title: row.title, selected: row.connected, glyph: root.deviceGlyph(row.icon),
      subtitle: row.connected ? "Connected" : (row.paired ? "Paired" : "Available"),
      trailing: row.battery ?? ""
    })
    onRowRequested: token => root.commandRequested(["bt-select", token], "Loading Bluetooth device…")
    onPageRequested: direction => root.commandRequested(["bt-page", direction], "Loading Bluetooth devices…")
  }

  MenuControlDetails {
    id: details
    width: root.width
    tone: "secondary"
    visible: root.radioOn && Boolean(root.device && root.device.token)
    onVisibleChanged: Qt.callLater(root.focusControls)
    backHint: "Back to devices"
    glyph: root.deviceGlyph(root.device ? root.device.icon : "")
    title: (root.device && root.device.title) ? root.device.title : ""
    fields: [
      ["Status", root.device && root.device.connected ? "Connected" : "Disconnected"],
      ["Type", (root.device && root.device.kind) ? root.device.kind : "Device"],
      ["Battery", (root.device && root.device.battery) ? root.device.battery : "No data"],
      ["Paired", root.device && root.device.paired ? "Yes" : "No"],
      ["Signal", (root.device && root.device.signal) ? root.device.signal : "No data"]
    ]
    caption: (root.device && root.device.address) ? root.device.address : ""
    busy: root.busy
    canApply: root.radioOn && Boolean(root.device && root.device.token)
    actionLabel: root.device && root.device.connected ? "Disconnect" : (root.device && root.device.paired ? "Connect" : "Pair & connect")
    actionGlyph: root.device && root.device.connected ? "󰌙" : "󰌘"
    onBackRequested: root.goBack()
    onApplyRequested: root.commandRequested(["bt-device", root.device.token],
      root.device && root.device.connected ? "Disconnecting…" : "Connecting…")
  }
}
