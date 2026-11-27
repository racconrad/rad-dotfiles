import QtQuick
import Quickshell
import Quickshell.Io

// Wallpaper catalogue kept in memory for the whole session. It is fetched once, in the background,
// so the wall window can be created on open and destroyed on close without losing instant opening.
Scope {
  id: root

  property bool active: false
  property string section: "all"
  property var tilesByIndex: ({})
  property var counts: ({ all: 0, images: 0, videos: 0 })
  property int loadedPages: 0
  property int pages: 1
  property bool pending: false
  property bool warmExpired: false
  // Media sizes by source path; tiles use them to keep each poster's own proportions.
  property var dims: ({})

  readonly property string menuBin: Quickshell.env("HOME") + "/.local/bin/desktop-menu"
  readonly property var tiles: Object.values(tilesByIndex).sort((a, b) => a.index - b.index).map((t, k) => Object.assign({ rank: k }, t))
  // The backend watcher runs only while the wall is open or while pages/thumbnails are still arriving.
  readonly property bool warming: !warmExpired && (loadedPages < pages || tiles.some(t => !t.has_thumb))

  function request(sec, page) { pending = true; Quickshell.execDetached([menuBin, "walls", "request", sec, String(page)]); }
  function refresh() { loadedPages = 0; request(section, 0); }
  function setSection(sec) {
    section = sec; tilesByIndex = ({}); loadedPages = 0; pages = 1;
    request(sec, 0);
  }

  Component.onCompleted: setSection("all")

  Process {
    running: root.active || root.warming
    command: [root.menuBin, "walls", "watch"]
    stdout: SplitParser {
      onRead: line => {
        let data; try { data = JSON.parse(line); } catch (e) { return; }
        if (data.section !== root.section) return;
        const merged = Object.assign({}, root.tilesByIndex);
        for (const row of data.rows ?? []) for (const t of row.tiles ?? []) merged[t.index] = t;
        root.tilesByIndex = merged;
        root.counts = data.counts ?? root.counts;
        root.pages = data.pages ?? root.pages;
        // The backend replays its last state on connect, so only the page we asked for advances the count.
        if (root.pending && data.page === root.loadedPages) { root.loadedPages++; root.pending = false; }
      }
    }
  }

  Timer { interval: 90000; running: true; onTriggered: root.warmExpired = true }

  onTilesChanged: dimsTimer.restart()
  Timer {
    id: dimsTimer
    interval: 600
    onTriggered: if (root.tiles.some(t => !root.dims[t.source])) dimsProc.running = true
  }
  Process {
    id: dimsProc
    command: [Quickshell.env("HOME") + "/.local/bin/raccon-wall-dims"]
    stdinEnabled: true
    onStarted: {
      write(root.tiles.filter(t => !root.dims[t.source]).map(t => t.source).join("\n") + "\n");
      stdinEnabled = false;
    }
    stdout: SplitParser {
      onRead: line => {
        try { root.dims = Object.assign({}, root.dims, JSON.parse(line)); } catch (e) { return; }
      }
    }
    onExited: stdinEnabled = true
  }

  Timer {
    interval: 140; repeat: true; running: root.active || root.warming
    onTriggered: if (!root.pending && root.loadedPages < root.pages) root.request(root.section, root.loadedPages)
  }
}
