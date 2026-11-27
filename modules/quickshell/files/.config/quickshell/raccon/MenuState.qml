import QtQuick

QtObject {
  id: root

  property int page: 0
  property bool editing: false
  property string selected: "auto"
  property string confirmation: ""
  property string query: ""
  property bool browsingApps: false

  readonly property var pages: ["home", "apps", "modes", "session", "audio",
    "connections", "bluetooth", "calendar", "shortcuts", "timer"]

  function openPage(index) {
    if (!Number.isInteger(index) || index < 0 || index >= pages.length)
      return;
    query = "";
    confirmation = "";
    browsingApps = index === 1;
    page = index;
  }

  function search(text) {
    query = text;
    if (text.length) {
      confirmation = "";
      page = 1;
    } else if (!browsingApps) {
      page = 0;
    }
  }

  function activate(row) {
    if (!row || row.available === false)
      return;
    if (row.action === "search-action") {
      const index = pages.indexOf(row.value);
      if (index !== -1) {
        openPage(index);
        return;
      }
    }
    if (["launch", "shortcut", "search-action"].includes(row.action))
      commandRequested([row.action, row.value]);
  }

  signal commandRequested(var args)
}
