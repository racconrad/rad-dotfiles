import QtQuick
import Quickshell
import Quickshell.Services.SystemTray

Paper {
  id: root
  visible: SystemTray.items.values.length > 0
  width: trayRow.width + 16
  height: 34
  implicitWidth: width
  implicitHeight: height
  fill: Theme.tone("paper").bg
  ink: Theme.ink
  shadowColor: Theme.shadowColor
  border: Theme.border
  shadowOffset: 4
  radius: height / 2
  bare: true
  tilt: 0
  Row {
    id: trayRow
    anchors.centerIn: parent
    spacing: 6

    Repeater {
      model: SystemTray.items.values
      delegate: Item {
        required property var modelData
        width: 22
        height: 22

        Image {
          id: trayIcon
          anchors.fill: parent
          source: Quickshell.iconPath(modelData.icon, true)
          fillMode: Image.PreserveAspectFit
        }

        // Items that publish no usable icon still get a visible initial instead of an empty tile.
        Text {
          anchors.centerIn: parent
          visible: trayIcon.status !== Image.Ready
          text: (modelData.title || modelData.id || "?").charAt(0).toUpperCase()
          color: Theme.on_surface
          font { family: Theme.fontDisplay; pixelSize: 16; weight: 800 }
        }

        MouseArea {
          anchors.fill: parent
          acceptedButtons: Qt.LeftButton | Qt.RightButton
          cursorShape: Qt.PointingHandCursor
          onClicked: (mouse) => {
            if (mouse.button === Qt.RightButton)
              modelData.display(root, mouse.x, mouse.y);
            else
              modelData.activate();
          }
        }
      }
    }
  }
}
