import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

PanelWindow {
  id: root
  signal closeRequested

  anchors { bottom: true; left: true; right: true }
  margins { left: 10; right: 26; bottom: 10 }
  implicitHeight: 64
  color: "transparent"
  exclusionMode: ExclusionMode.Normal
  WlrLayershell.layer: WlrLayer.Top
  WlrLayershell.namespace: "raccon-bar"
  WlrLayershell.exclusiveZone: 64

  FontLoader {
    id: evaFont
    source: "fonts/Eva-Icons.ttf"
  }

  readonly property string iconFont: evaFont.name || "Eva-Icons"

  BarBody {
    anchors.fill: parent
    leftWing: leftSection.width + 28
    appsWidth: centerSection.width > 0 ? centerSection.width + 20 : 0
    rightWidth: rightSection.width + 28
  }

  // Three-region layout: fixed left, filling taskbar, implicit right
  RowLayout {
    id: barContent
    anchors { fill: parent; leftMargin: 14; rightMargin: 14; topMargin: 15; bottomMargin: 5 }
    spacing: 24

    BarWorkspaces {
      id: leftSection
      iconFont: root.iconFont
      Layout.alignment: Qt.AlignVCenter
      Layout.preferredWidth: implicitWidth
    }

    BarTaskbar {
      id: centerSection
      iconFont: root.iconFont
      Layout.preferredWidth: implicitWidth
      Layout.maximumWidth: Math.max(0, root.width - leftSection.width - rightSection.width - 120)
      Layout.alignment: Qt.AlignVCenter
      clip: true
    }

    Item {
      Layout.fillWidth: true
    }

    RowLayout {
      id: rightSection
      spacing: 4
      Layout.bottomMargin: 10
      Layout.alignment: Qt.AlignVCenter
      Layout.preferredWidth: implicitWidth

      BarMusic { iconFont: root.iconFont }
      BarTray {}
      BarHardware { iconFont: root.iconFont }
      BarSystem { iconFont: root.iconFont }
      BarStatus { iconFont: root.iconFont }
      BarClock { iconFont: root.iconFont }
    }
  }
}
