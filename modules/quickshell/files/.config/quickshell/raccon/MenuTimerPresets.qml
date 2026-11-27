import QtQuick
import QtQuick.Layouts

// Preset duration chips row in CutButton style.
RowLayout {
  id: root
  signal presetSelected(string duration)

  spacing: 6

  Repeater {
    model: ["5m", "10m", "15m", "25m"]

    CutButton {
      required property string modelData
      Layout.fillWidth: true
      text: modelData
      tone: "paper"
      onClicked: root.presetSelected(modelData)
    }
  }
}
