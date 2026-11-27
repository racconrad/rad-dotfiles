import QtQuick
import Quickshell
import Quickshell.Wayland

Item {
  id: root
  property string iconFont: "Eva-Icons"
  implicitWidth: taskRow.implicitWidth
  implicitHeight: 38
  clip: true

  readonly property var toplevels: (ToplevelManager.toplevels && ToplevelManager.toplevels.values) ? ToplevelManager.toplevels.values : []

  WheelHandler {
    target: flick
    onWheel: (event) => {
      if (flick.contentWidth > flick.width) {
        flick.contentX = Math.max(0, Math.min(flick.contentWidth - flick.width, flick.contentX - event.angleDelta.y));
      }
    }
  }

  Flickable {
    id: flick
    anchors.fill: parent
    contentWidth: taskRow.implicitWidth
    contentHeight: parent.height
    boundsBehavior: Flickable.StopAtBounds
    interactive: contentWidth > width
    clip: true

    Row {
      id: taskRow
      spacing: 6
      height: parent.height
      anchors.verticalCenter: parent.verticalCenter
      x: Math.max(0, (flick.width - width) / 2)

      Repeater {
        model: root.toplevels
        delegate: Item {
          id: tabDelegate
          required property int index
          required property var modelData
          readonly property var toplevel: modelData
          readonly property bool active: Boolean(toplevel && toplevel.activated)
          readonly property var colors: active ? Theme.tone("secondary") : Theme.tone("paper")

          width: 34
          height: 34

          // Washi tape holding the polaroid tile at the top

          Paper {
            id: tabPaper
            width: 34
            height: 34
            implicitWidth: 34
            implicitHeight: 34
            fill: colors.bg
            ink: Theme.ink
            shadowColor: Theme.shadowColor
            border: Theme.border
            shadowOffset: 4
            radius: height / 2
            bare: true
            lifted: tabHover.containsMouse
            tilt: 0

            Behavior on lifted {
              enabled: Theme.animations
              PropertyAnimation { duration: Theme.motionFast }
            }
            Behavior on tilt {
              enabled: Theme.animations
              NumberAnimation { duration: Theme.motionFast }
            }

            Image {
              anchors.centerIn: parent
              anchors.verticalCenterOffset: active ? -2 : 0
              width: 20
              height: 20
              source: Quickshell.iconPath((toplevel && toplevel.appId) ? toplevel.appId : "", true)
              fillMode: Image.PreserveAspectFit
            }

            Slice {
              visible: active
              color: colors.fg
              angle: 0
              width: 22
              height: 3
              anchors.horizontalCenter: parent.horizontalCenter
              anchors.bottom: parent.bottom
              anchors.bottomMargin: 3
            }

            MouseArea {
              id: tabHover
              anchors.fill: parent
              hoverEnabled: true
              acceptedButtons: Qt.LeftButton | Qt.MiddleButton
              cursorShape: Qt.PointingHandCursor
              onClicked: (mouse) => {
                if (mouse.button === Qt.MiddleButton) {
                  if (toplevel) toplevel.close();
                } else {
                  if (toplevel) toplevel.activate();
                }
              }
            }
          }
        }
      }
    }
  }
}
