import QtQuick
import QtQuick.Shapes

// Two floating blobs. The left one is a raised workspace wing fused to a lower apps pill through a
// concave fillet; the right one is a separate flat pill. Layers: hard accent shadow, fill with a thin
// ink outline, then a thick ridge along the top contour.
Item {
  id: root

  property real leftWing: 0     // workspace wing width
  property real appsWidth: 0    // fused apps pill width, 0 hides it
  property real rightWidth: 0   // separate right pill width
  property real lowTop: 12      // top of the apps and right pills; the wing reaches 0
  property real rightLift: 5    // the right pill floats this much above the left blob
  property real bodyHeight: 56
  property real bodyY: 3
  property real corner: 8       // wing top corners
  property real fillet: 4
  property real pill: 16        // rounded ends of the pills
  property color fill: Theme.tone("paper").bg
  property color ridge: Theme.tertiary

  readonly property real endX: leftWing + appsWidth

  // Ridges stop where the corners start, so the ends never cut into a rounded corner.
  readonly property string wingTop: `L ${leftWing - corner} 0 A ${corner} ${corner} 0 0 1 ${leftWing} ${corner}`
  readonly property string step: {
    const f = fillet, l = leftWing, t = lowTop;
    return appsWidth > 0 ? ` L ${l} ${t - f} A ${f} ${f} 0 0 0 ${l + f} ${t} L ${endX - pill} ${t}` : "";
  }
  readonly property string leftRidge: `M ${corner} 0 ${wingTop}${step}`
  readonly property string leftOutline: {
    const r = corner, p = pill, h = bodyHeight, e = appsWidth > 0 ? endX : leftWing, t = lowTop;
    const end = appsWidth > 0 ? ` A ${p} ${p} 0 0 1 ${e} ${t + p}` : "";
    return `M ${p} ${h} A ${p} ${p} 0 0 1 0 ${h - p} L 0 ${r} A ${r} ${r} 0 0 1 ${r} 0 ${wingTop}${step}${end}`
      + ` L ${e} ${h - p} A ${p} ${p} 0 0 1 ${e - p} ${h} Z`;
  }
  readonly property string rightRidge: `M ${width - rightWidth + pill} ${lowTop} L ${width - pill} ${lowTop}`
  readonly property string rightOutline: {
    const p = pill, x = width - rightWidth, h = bodyHeight, t = lowTop;
    return `M ${x + p} ${h} A ${p} ${p} 0 0 1 ${x} ${h - p} L ${x} ${t + p} A ${p} ${p} 0 0 1 ${x + p} ${t} L ${width - p} ${t}`
      + ` A ${p} ${p} 0 0 1 ${width} ${t + p} L ${width} ${h - p} A ${p} ${p} 0 0 1 ${width - p} ${h} Z`;
  }

  component Layer: Shape {
    id: layer
    property string path
    property color fillColor: "transparent"
    property color lineColor: "transparent"
    property real lineWidth: 0
    width: root.width
    height: root.height
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
      fillColor: layer.fillColor
      strokeColor: layer.lineColor
      strokeWidth: layer.lineWidth
      capStyle: ShapePath.RoundCap
      joinStyle: ShapePath.RoundJoin
      PathSvg { path: layer.path }
    }
  }

  Layer { x: Theme.shadowOffset; y: root.bodyY + Theme.shadowOffset; path: root.leftOutline; fillColor: Theme.shadowColor }
  Layer { x: Theme.shadowOffset; y: root.bodyY - root.rightLift + Theme.shadowOffset; path: root.rightOutline; fillColor: Theme.shadowColor }
  Layer { y: root.bodyY; path: root.leftOutline; fillColor: root.fill }
  Layer { y: root.bodyY - root.rightLift; path: root.rightOutline; fillColor: root.fill }
  Layer { y: root.bodyY; path: root.leftRidge; lineColor: root.ridge; lineWidth: 6 }
  Layer { y: root.bodyY - root.rightLift; path: root.rightRidge; lineColor: root.ridge; lineWidth: 6 }
}
