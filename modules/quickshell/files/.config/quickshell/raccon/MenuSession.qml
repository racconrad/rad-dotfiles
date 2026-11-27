import QtQuick
import QtQuick.Layouts

// Session actions in a compact grid on the side sheet; destructive ones ask for confirmation.
Item {
  id: root

  property string confirmation: ""
  property bool busy: false
  readonly property alias firstAction: back
  readonly property var choices: [
    { id: "lock", text: "Lock", glyph: "󰌾" },
    { id: "suspend", text: "Suspend", glyph: "󰤄" },
    { id: "logout", text: "Log out", glyph: "󰍃" },
    { id: "reboot", text: "Restart", glyph: "󰜉" },
    { id: "poweroff", text: "Shut down", glyph: "󰐥" }
  ]
  readonly property string question: {
    const c = choices.find(choice => choice.id === root.confirmation);
    return (c ? c.text : "") + "?";
  }
  signal backRequested
  signal confirmRequested(string action)
  signal commandRequested(var args)

  property Item lastChoice: null
  function restoreFocus() { if (lastChoice) lastChoice.forceActiveFocus(Qt.TabFocusReason); }

  implicitWidth: 302
  implicitHeight: col.implicitHeight

  Column {
    id: col
    anchors { left: parent.left; right: parent.right; top: parent.top }
    spacing: 8

    RowLayout {
      width: col.width
      spacing: 6
      CutButton { id: back; icon: "󰁍"; text: "BACK"; tone: "paper"; onClicked: root.backRequested() }
      Sticker { text: "SESSION"; tone: "paper" }
    }

    GridLayout {
      width: col.width
      columns: 2
      columnSpacing: 8
      rowSpacing: 8

      Repeater {
        model: root.choices
        CutButton {
          id: choiceBtn
          required property var modelData
          required property int index
          objectName: "menuSession-" + modelData.id
          Layout.fillWidth: true
          Layout.columnSpan: index === root.choices.length - 1 ? 2 : 1
          implicitHeight: 52
          enabled: !root.busy
          text: modelData.text.toUpperCase()
          icon: modelData.glyph
          active: modelData.id === root.confirmation
          tone: modelData.id === root.confirmation ? "error" : "paper"
          onClicked: {
            if (modelData.id === "lock")
              root.commandRequested(["shortcut", "lock"]);
            else {
              root.lastChoice = choiceBtn;
              root.confirmRequested(modelData.id);
            }
          }
        }
      }
    }

    RowLayout {
      width: col.width
      spacing: 8
      visible: root.confirmation.length > 0 && !root.busy

      CutButton {
        Layout.fillWidth: true
        icon: "󰁍"
        text: "CANCEL"
        tone: "paper"
        onClicked: { root.confirmRequested(""); root.restoreFocus(); }
      }
      CutButton {
        objectName: "menuSessionConfirm"
        Layout.fillWidth: true
        icon: "󰄬"
        text: "CONFIRM " + root.question.toUpperCase()
        tone: "error"
        onClicked: root.commandRequested(["session-action", root.confirmation])
      }
    }
  }
}
