import QtQuick

// Month date cells grid with filled tilted tile for today and hard ink borders.
Column {
  id: root
  property var weeks: []

  signal dateSelected(string iso)

  spacing: 3

  Repeater {
    model: root.weeks ?? []
    Row {
      id: weekRow
      required property var modelData
      width: root.width
      spacing: 3

      Repeater {
        model: weekRow.modelData
        Item {
          id: cellContainer
          required property var modelData
          readonly property bool isSelected: Boolean(modelData.selected)
          readonly property bool isToday: Boolean(modelData.today)
          readonly property bool isOther: Boolean(modelData.other)
          readonly property bool hasEvent: Boolean(modelData.event)

          width: (weekRow.width - 18) / 7
          height: 28

          // Hard shadow behind today or selected cell
          Rectangle {
            antialiasing: true
            visible: cellContainer.isSelected || cellContainer.isToday
            x: 2; y: 2
            width: parent.width; height: parent.height
            color: Theme.ink
            radius: Theme.radius
          }

          // Tile
          Rectangle {
            antialiasing: true
            id: dayCell
            anchors.fill: parent
            radius: Theme.radius
            rotation: cellContainer.isToday ? -3 : 0
            transformOrigin: Item.Center
            opacity: cellContainer.isOther ? 0.35 : 1.0

            color: cellContainer.isToday ? Theme.tertiary
              : cellContainer.isSelected ? Theme.primary
              : dayArea.containsMouse ? Theme.surface_container_highest : Theme.surface_container
            border.width: (cellContainer.isToday || cellContainer.isSelected) ? 2 : 1
            border.color: Theme.ink

            Text {
              anchors.centerIn: parent
              text: cellContainer.modelData.day ?? ""
              color: cellContainer.isToday ? Theme.on_tertiary
                : cellContainer.isSelected ? Theme.on_primary
                : Theme.on_surface
              font {
                family: Theme.fontTag
                pixelSize: 12
                weight: (cellContainer.isSelected || cellContainer.isToday) ? 800 : Font.Normal
              }
            }

            // Diamond badge event indicator
            Rectangle {
              antialiasing: true
              visible: cellContainer.hasEvent
              width: 4; height: 4
              rotation: 45
              anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 2 }
              color: cellContainer.isToday ? Theme.on_tertiary : Theme.tertiary
            }

            MouseArea {
              id: dayArea
              anchors.fill: parent
              hoverEnabled: true
              enabled: Boolean(cellContainer.modelData.iso)
              onClicked: root.dateSelected(cellContainer.modelData.iso)
            }
          }
        }
      }
    }
  }
}
