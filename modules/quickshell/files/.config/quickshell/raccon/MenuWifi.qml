import QtQuick
import QtQuick.Templates as T

MenuControlPage {
  id: root

  property string selectedToken: ""
  property string pendingOperation: ""
  readonly property bool connected: Boolean(network && network.active)
  readonly property bool needsPassword: !connected && Boolean(network && network.secured)
  signal joinRequested(string token, string password)
  readonly property var network: {
    const list = root.model && root.model.networks ? root.model.networks : [];
    return list.find(row => row.token === root.selectedToken) || null;
  }
  readonly property bool radioOn: Boolean(model && model.enabled)

  title: "Wi-Fi"
  tagText: "05 // WI-FI"
  tone: "secondary"
  kind: "connections"
  loadingText: "Loading networks…"
  initialFocusItem: details.visible ? (needsPassword ? passwordField : details.backButton) : power.enabled ? power : null

  function clearSelection() { root.selectedToken = ""; root.pendingOperation = ""; power.forceActiveFocus(Qt.TabFocusReason); }
  function goBack() { if (!root.selectedToken || root.busy) return false; root.clearSelection(); return true; }
  function applyNetwork() {
    if (root.busy || !root.network || !root.radioOn) return;
    if (root.connected) {
      root.pendingOperation = "disconnect";
      root.commandRequested(["wifi-disconnect", root.network.token], "Disconnecting from " + root.network.title + "…");
    } else {
      root.pendingOperation = "join";
      root.joinRequested(root.network.token, root.needsPassword ? passwordField.text : "");
      passwordField.clear();
    }
  }

  onRadioOnChanged: if (!radioOn && selectedToken) clearSelection()
  onActionErrorChanged: if (actionError) pendingOperation = ""
  onSelectedTokenChanged: passwordField.clear()
  onNetworkChanged: if (selectedToken && (!network || (pendingOperation === "disconnect" && !connected) || (pendingOperation === "join" && connected))) clearSelection()
  Keys.onEscapePressed: event => { event.accepted = root.goBack(); }

  headingActions: [
    CutButton {
      icon: "󰑐"; text: "SCAN"; tone: "secondary"
      enabled: Boolean(root.model && root.model.available) && root.radioOn && !root.busy
      onClicked: root.commandRequested(["wifi-scan"], "Scanning nearby Wi-Fi networks…")
    },
    CutButton {
      id: power
      icon: "󰐥"; text: root.radioOn ? "ON" : "OFF"
      tone: root.radioOn ? "secondary" : "paper"; active: root.radioOn
      enabled: Boolean(root.model && root.model.available) && !root.busy
      onClicked: root.commandRequested(["wifi-power", root.radioOn ? "off" : "on"], root.radioOn ? "Turning off Wi-Fi…" : "Turning on Wi-Fi…")
    }
  ]

  MenuControlList {
    width: root.width; visible: !details.visible; tone: "secondary"
    rows: root.model && root.model.rows ? root.model.rows : []
    pageIndex: root.model && root.model.list_page ? root.model.list_page : 0
    pageCount: root.model && root.model.page_count ? root.model.page_count : 1
    total: root.model && root.model.total ? root.model.total : 0
    available: root.radioOn && !root.busy
    describe: row => ({
      token: row.token, title: row.title, selected: row.active,
      subtitle: row.active ? "Connected" : (row.secured ? "Secured" : "Open"),
      glyph: row.signal >= 65 ? "󰤨" : (row.signal >= 35 ? "󰤥" : "󰤟"),
      trailing: (row.signal || 0) + "%"
    })
    onRowRequested: token => {
      root.selectedToken = token;
      if (details.visible && root.initialFocusItem) root.initialFocusItem.forceActiveFocus(Qt.TabFocusReason);
    }
    onPageRequested: direction => root.commandRequested(["wifi-page", direction], "Loading networks…")
  }

  MenuControlDetails {
    id: details
    width: root.width; tone: "secondary"
    visible: root.radioOn && root.network !== null
    backHint: "Back to networks"; glyph: "󰖩"
    title: root.network ? root.network.title : ""
    fields: [
      ["Status", root.network && root.network.active ? "Connected" : "Disconnected"],
      ["Security", root.network && root.network.security ? root.network.security : "None"],
      ["Signal", ((root.network && root.network.signal) ? root.network.signal : 0) + "%"]
    ]
    busy: root.busy; canApply: root.radioOn && root.network !== null
    actionLabel: root.connected ? "Disconnect" : "Connect"
    actionGlyph: root.connected ? "󰌙" : "󰌘"
    onBackRequested: root.goBack()
    onApplyRequested: root.applyNetwork()

    form: [
      Text {
        visible: root.needsPassword; text: "KEY // PASSWORD"
        color: Theme.on_surface_variant; font { family: Theme.fontTag; pixelSize: 12; weight: Font.Bold }
      },
      T.TextField {
        id: passwordField
        width: root.width; implicitHeight: 32; padding: 6
        visible: root.needsPassword; enabled: !root.busy
        echoMode: TextInput.Password; color: Theme.on_surface
        font { family: Theme.fontMono; pixelSize: 12 }
        Accessible.name: "Password"
        onAccepted: root.applyNetwork()
        background: Rectangle {
          radius: Theme.radius; color: Theme.surface_container_highest
          border.width: Theme.border; border.color: passwordField.activeFocus ? Theme.secondary : Theme.ink
        }
      }
    ]
  }
}
