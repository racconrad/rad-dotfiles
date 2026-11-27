import QtQuick
import QtQuick.Layouts

ColumnLayout {
  id: root

  property var catalogue: ({})
  property bool editing: false
  readonly property var favorites: (catalogue.favorites ?? []).reduce((all, row) => all.concat(row), [])
  readonly property bool canAdd: (catalogue.home_count ?? 0) < (catalogue.home_limit ?? 6)
  signal activated(var app)
  signal commandRequested(var args)
  signal browseRequested()
  signal pageRequested(int page)

  spacing: 8

  function tileAt(index) {
    const loader = tiles.itemAt(index) as TileLoader;
    return loader ? loader.launchButton : null;
  }

  // Mosaic of page shortcuts
  MenuSekaiCards {
    visible: !root.editing
    Layout.fillWidth: true
    onBrowseRequested: root.browseRequested()
    onPageRequested: p => root.pageRequested(p)
    onCommandRequested: args => root.commandRequested(args)
  }

  GridLayout {
    visible: root.favorites.length > 0
    Layout.fillWidth: true
    columns: 6
    uniformCellWidths: true
    columnSpacing: 6
    rowSpacing: 6

    Repeater {
      id: tiles
      model: root.favorites.length
      TileLoader {}
    }
  }

  component TileLoader: Loader {
    id: tileLoader
    required property int index
    readonly property Item launchButton: {
      const tile = item as MenuHomeTile;
      return tile ? tile.launchButton : null;
    }
    Layout.fillWidth: true; Layout.minimumWidth: 0
    sourceComponent: index < root.favorites.length ? tile : null

    Component {
      id: tile
      MenuHomeTile {
        app: root.favorites[tileLoader.index]
        index: tileLoader.index
        editing: root.editing
        onActivated: app => root.activated(app)
        onCommandRequested: args => root.commandRequested(args)
      }
    }
  }

  MenuRecents {
    visible: root.editing || (root.catalogue.recent_enabled ?? false)
    Layout.fillWidth: true
    catalogue: root.catalogue
    onActivated: app => root.activated(app)
    onCommandRequested: args => root.commandRequested(args)
  }
}
