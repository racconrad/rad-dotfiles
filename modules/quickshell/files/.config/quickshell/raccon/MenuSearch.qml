import QtQuick

// Long paper search strip with 3px primary bar and blinking square caret.
Item {
  id: root

  property alias text: input.text
  property alias field: input
  property string placeholder: "Search apps…"
  property bool ascii: false
  signal edited(string value)
  signal accepted()

  implicitHeight: 42

  function words(value) {
    const normalized = value.normalize("NFKD").toLowerCase().replace(/[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]/g, "")
      .replace(/ß/g, "ss").replace(/ς/g, "σ").trim();
    return normalized ? normalized.split(/\s+/) : [];
  }

  function appendText(value) {
    input.forceActiveFocus();
    input.insert(input.cursorPosition, value);
    edited(input.text);
  }

  readonly property bool focused: input.activeFocus

  Rectangle {
    antialiasing: true
    x: root.focused ? 4 : 3
    y: root.focused ? 4 : 3
    width: parent.width
    height: parent.height
    radius: height / 2
    color: root.focused ? Theme.tone("secondary").bg : Theme.surface_container_highest
    Behavior on color { enabled: Theme.animations; ColorAnimation { duration: Theme.motionFast } }
  }

  Rectangle {
    antialiasing: true
    id: box
    x: root.focused ? -1 : 0
    y: root.focused ? -1 : 0
    width: parent.width
    height: parent.height
    radius: height / 2
    color: root.focused ? Theme.tone("primary").bg : Theme.surface_container_high
    Behavior on color { enabled: Theme.animations; ColorAnimation { duration: Theme.motionFast } }
    Behavior on x { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }
    Behavior on y { enabled: Theme.animations; NumberAnimation { duration: Theme.motionFast } }

    Rectangle {
      id: badge
      antialiasing: true
      width: parent.height - 10; height: width; radius: width / 2
      anchors { left: parent.left; leftMargin: 5; verticalCenter: parent.verticalCenter }
      color: root.focused ? Theme.primary : Theme.tone("tertiary").bg
      Behavior on color { enabled: Theme.animations; ColorAnimation { duration: Theme.motionFast } }

      Text {
        anchors.centerIn: parent
        text: root.ascii ? ">_" : "󰍉"
        color: root.focused ? Theme.on_primary : Theme.tone("tertiary").fg
        font.family: Theme.fontMono
        font.pixelSize: 15
      }
    }

    Rectangle {
      id: clear
      antialiasing: true
      visible: input.text.length > 0
      width: 24; height: 24; radius: 12
      anchors { right: parent.right; rightMargin: 9; verticalCenter: parent.verticalCenter }
      color: clearArea.containsMouse ? Theme.tone("error").bg : Theme.surface_container_highest
      Text { anchors.centerIn: parent; text: "󰅖"; color: Theme.on_surface; font.family: Theme.fontMono; font.pixelSize: 12 }
      MouseArea {
        id: clearArea
        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
        onClicked: { input.text = ""; root.edited(""); input.forceActiveFocus(); }
      }
    }

    TextInput {
      id: input
      anchors {
        left: badge.right; right: clear.visible ? clear.left : parent.right; verticalCenter: parent.verticalCenter
        leftMargin: 10; rightMargin: 10
      }
      clip: true
      activeFocusOnTab: true
      selectByMouse: true
      color: Theme.on_surface
      selectionColor: Theme.primary
      selectedTextColor: Theme.on_primary
      font.family: Theme.fontDisplay
      font.pixelSize: 15
      font.weight: Font.DemiBold

      // Blinking caret
      cursorDelegate: Rectangle {
        width: 3
        height: 18
        radius: 1.5
        color: Theme.primary
        visible: input.activeFocus

        // A timer, not an endless animation: the latter keeps the render loop ticking at the display rate.
        Timer {
          running: input.activeFocus && Theme.animations
          interval: 450; repeat: true
          onTriggered: parent.opacity = parent.opacity > 0.5 ? 0 : 1
          onRunningChanged: if (!running) parent.opacity = 1
        }
      }

      onTextEdited: root.edited(text)
      onAccepted: root.accepted()
      Accessible.name: root.placeholder

      Text {
        anchors.fill: parent
        visible: !input.text && !input.preeditText
        text: root.placeholder
        elide: Text.ElideRight
        color: Theme.on_surface_variant
        font: input.font
      }
    }
  }
}
