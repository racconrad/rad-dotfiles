import QtQuick
import Quickshell
import Quickshell.Hyprland

Item {
  id: root
  property string iconFont: "Eva-Icons"

  readonly property int currentWs: Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : 1

  implicitWidth: wsRow.implicitWidth + 4
  implicitHeight: 38

  WheelHandler {
    onWheel: (event) => Hyprland.dispatch("hl.dsp.focus({ workspace = '" + (event.angleDelta.y > 0 ? "e-1" : "e+1") + "' })")
  }

  // One capsule holds the workspaces; the launcher stays outside it.
  Rectangle {
    x: launcherBtn.width + wsRow.spacing
    width: wsRow.width - x + 4
    height: 34
    radius: 17
    anchors.verticalCenter: parent.verticalCenter
    color: Theme.surface_container_highest
  }

  Row {
    id: wsRow
    spacing: 5
    height: 38
    anchors.verticalCenter: parent.verticalCenter

    CutButton {
      id: launcherBtn
      width: 34
      height: 34
      icon: "\ueb31"
      iconFont: root.iconFont
      tone: "primary"
      radius: 17
      shadowColor: "transparent"
      outline: "transparent"
      anchors.verticalCenter: parent.verticalCenter
      onClicked: Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/desktop-menu"])
    }

    Repeater {
      model: 9
      delegate: Item {
        id: wsItem
        required property int index
        readonly property int wsId: index + 1
        readonly property bool active: root.currentWs === wsId
        readonly property bool hasWindows: {
          const wsList = (Hyprland.workspaces && Hyprland.workspaces.values) ? Hyprland.workspaces.values : [];
          const ws = wsList.find(w => w && w.id === wsId);
          return Boolean(ws && ws.toplevels && ws.toplevels.values && ws.toplevels.values.length > 0);
        }
        readonly property var colors: active ? Theme.tone("primary") : Theme.tone("paper")

        width: active ? 34 : 28
        height: 34
        anchors.verticalCenter: parent.verticalCenter

        onActiveChanged: {
          if (active && Theme.animations) {
            stampAnim.restart();
            wsBurst.fire(width / 2, height / 2);
          }
        }

        SequentialAnimation {
          id: stampAnim
          PropertyAction { target: wsItem; property: "scale"; value: 1.15 }
          NumberAnimation { target: wsItem; property: "scale"; to: 1.0; duration: Theme.motionBase; easing.type: Easing.OutBack; easing.overshoot: Theme.overshoot }
        }

        Burst {
          id: wsBurst
          color: colors.fg
          count: 8
          z: 20
        }

        Paper {
          id: wsPaper
          width: parent.width
          height: parent.height
          implicitWidth: width
          implicitHeight: height
          fill: active ? Theme.primary : colors.bg
          ink: Theme.ink
          shadowColor: "transparent"
          border: 0
          shadowOffset: 4
          radius: height / 2
          bare: !active
          lifted: active || wsHover.containsMouse
          tilt: 0

          Behavior on tilt { enabled: Theme.animations; NumberAnimation { duration: Theme.motionBase; easing.type: Easing.OutQuad } }
          Behavior on width { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }

          Text {
            anchors.centerIn: parent
            text: String(wsId)
            font.family: Theme.fontDisplay
            font.pixelSize: active ? 15 : 12
            font.bold: true
            color: active ? Theme.surface : Theme.on_surface
          }

          Spark {
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 2
            size: 10
            color: Theme.tone("secondary").fg
            visible: hasWindows && !active
            spin: 0
          }

          MouseArea {
            id: wsHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: Hyprland.dispatch("hl.dsp.focus({ workspace = " + wsId + " })")
          }
        }
      }
    }
  }
}
