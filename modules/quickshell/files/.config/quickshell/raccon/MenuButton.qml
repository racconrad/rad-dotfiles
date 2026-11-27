import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Templates as T
import QtQuick.Layouts
import Quickshell

T.Button {
  id: root

  property string glyph: ""
  property string detail: ""
  property string hint: text
  property var artwork: null
  property bool stacked: false
  property bool selected: false
  property bool result: false
  property bool muted: false
  property int glyphSize: 16
  property int cornerRadius: Theme.radius
  property int iconAlignment: Qt.AlignLeft
  property color fill: "transparent"
  property color ink: selected && !result ? Theme.tone("primary").fg : (selected ? Theme.primary : (muted ? Theme.on_surface_variant : Theme.on_surface))

  implicitWidth: Math.max(26, contentItem.implicitWidth + leftPadding + rightPadding)
  implicitHeight: Math.max(28, contentItem.implicitHeight + topPadding + bottomPadding)
  padding: 5
  focusPolicy: Qt.StrongFocus
  hoverEnabled: true
  opacity: enabled ? 1 : 0.45

  Accessible.name: hint || text
  Controls.ToolTip.visible: hovered && hint.length > 0
  Controls.ToolTip.text: hint
  Controls.ToolTip.delay: 600

  Keys.onReturnPressed: event => { if (!event.isAutoRepeat) clicked(); }
  Keys.onEnterPressed: event => { if (!event.isAutoRepeat) clicked(); }

  readonly property real moveX: down ? 1 : (hovered ? -1 : 0)
  readonly property real moveY: down ? 1 : (hovered ? -1 : 0)

  background: Item {
    // Hard ink shadow behind button when hovered
    Rectangle {
      antialiasing: true
      anchors.fill: parent
      anchors.margins: -1
      color: Theme.ink
      radius: root.cornerRadius
      visible: false
    }

    Rectangle {
      antialiasing: true
      x: root.moveX
      y: root.moveY
      width: parent.width
      height: parent.height
      radius: root.cornerRadius
      color: root.selected && !root.result ? Theme.tone("primary").bg
        : (root.down ? Qt.alpha(Theme.primary, 0.28)
        : (root.hovered ? Qt.alpha(Theme.primary, 0.14) : root.fill))
      border.width: root.visualFocus ? 2 : 0
      border.color: root.visualFocus ? Theme.primary : Theme.ink

      // Thick ink slice accent on selected list items
      Rectangle {
        antialiasing: true
        visible: root.result && root.selected
        color: Theme.primary
        width: 4
        height: parent.height
        anchors.left: parent.left
      }
    }
  }

  contentItem: GridLayout {
    columns: root.stacked ? 1 : 3
    columnSpacing: 8
    rowSpacing: 3

    Item {
      visible: root.glyph.length > 0 || root.artwork !== null
      Layout.preferredWidth: root.glyphSize
      Layout.preferredHeight: root.glyphSize
      Layout.alignment: root.iconAlignment | Qt.AlignVCenter
      scale: !Theme.animations ? 1 : root.down ? 0.92 : root.hovered ? 1.08 : 1
      Behavior on scale { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic } }

      Image {
        id: icon
        anchors.fill: parent
        source: {
          const art = root.artwork;
          if (art && art.has_file && art.file)
            return "file://" + encodeURI(art.file).replace(/#/g, "%23").replace(/\?/g, "%3F");
          if (art && art.icon)
            return Quickshell.iconPath(art.icon, true);
          return "";
        }
        sourceSize.width: root.glyphSize
        sourceSize.height: root.glyphSize
        fillMode: Image.PreserveAspectFit
        asynchronous: true
      }

      Text {
        anchors.centerIn: parent
        visible: icon.status !== Image.Ready
        text: root.glyph || "󰀻"
        color: root.artwork ? Theme.primary : root.ink
        font.family: Theme.fontMono
        font.pixelSize: root.glyphSize
      }
    }

    Text {
      visible: root.text.length > 0
      Layout.fillWidth: true
      text: root.text
      textFormat: Text.PlainText
      horizontalAlignment: root.stacked ? Text.AlignHCenter : Text.AlignLeft
      elide: Text.ElideRight
      color: root.ink
      font: root.font
    }

    Text {
      visible: root.detail.length > 0
      text: root.detail
      textFormat: Text.PlainText
      color: Theme.on_surface_variant
      opacity: 0.8
      font.family: Theme.fontDisplay
      font.pixelSize: 12
    }
  }

  font { family: Theme.fontDisplay; pixelSize: 12; weight: Font.Medium }
}
