import QtQuick

// One endless column of the wall: its posters repeat so scrolling never reaches an end.
Item {
  id: root

  property var tiles: []
  property var dims: ({})
  property real scrollY: 0
  property real phase: 0
  property int appliedIndex: -1
  property int revealed: 0
  property bool closing: false
  property bool fadeAll: false
  signal chosen(var tile)

  readonly property real gap: 14
  readonly property var ratios: [0.6, 1.2, 0.72, 0.95, 1.45, 0.66, 0.88, 1.1]
  // Frame and matte add 30px around the picture; the picture keeps its own proportions so nothing is cropped.
  // Until a size is known, the height comes from the file index so it never changes between reloads.
  function ratioOf(t) {
    const d = dims[t.source];
    return d && d[0] > 0 ? Math.max(0.4, Math.min(2.0, d[1] / d[0])) : ratios[t.index % ratios.length];
  }
  readonly property var heights: tiles.map(t => Math.round((width - 30) * ratioOf(t) + 30))
  readonly property var tops: {
    let y = 0; const out = [];
    for (const h of heights) { out.push(y); y += h + gap; }
    return out;
  }
  readonly property real total: Math.max(1, tops.length ? tops[tops.length - 1] + heights[heights.length - 1] + gap : 1)
  readonly property real shift: (((scrollY + phase) % total) + total) % total
  // Capped: a column measured at width 0 while the window is being configured must not spawn thousands of posters.
  readonly property int copies: width > 40 && heights.length ? Math.min(4, Math.ceil(height / total) + 1) : 0

  Repeater {
    model: root.tiles.length ? root.copies * root.tiles.length : 0

    WallTile {
      required property int index
      readonly property int copy: Math.floor(index / root.tiles.length)
      readonly property int slot: index % root.tiles.length
      width: root.width; height: root.heights[slot]
      y: root.tops[slot] + copy * root.total - root.shift
      tile: root.tiles[slot]
      active: root.appliedIndex === tile.index && !root.closing
      shown: tile.rank < root.revealed
      leaving: root.closing
      picked: root.appliedIndex === tile.index
      fadeAll: root.fadeAll
      near: y > -height - 200 && y < root.height + 200
      onChosen: root.chosen(tile)
    }
  }
}
