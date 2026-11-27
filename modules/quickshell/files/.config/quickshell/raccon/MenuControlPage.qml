import QtQuick
import QtQuick.Layouts

// Flat page content; the side sheet is the only surface.
Item {
  id: root

  default property alias content: body.data
  property alias headingActions: actions.data
  property var model: ({})
  property bool busy: false
  property string actionMessage: ""
  property string actionError: ""
  property string title: ""
  property string loadingText: ""
  property string kind: ""
  property string tagText: ""
  property string tone: "primary"
  property Item initialFocusItem: null
  signal commandRequested(var args, string message)

  implicitWidth: 302
  implicitHeight: col.implicitHeight

  Item {
    id: card
    width: root.width
    height: col.implicitHeight

    Column {
      id: col
      anchors {
        left: parent.left
        right: parent.right
        top: parent.top
      }
      spacing: 8

      // Header row
      RowLayout {
        width: parent.width
        spacing: 6

        Sticker {
          text: root.title
          tone: root.tone
        }

        Item { Layout.fillWidth: true }

        RowLayout {
          id: actions
          spacing: 6
        }
      }

      MenuControlStatus {
        width: parent.width
        status: root.actionError ? "error" : (root.model && root.model.status ? root.model.status : "loading")
        waiting: root.busy || Boolean(root.model && root.model.scanning) || status === "loading"
        message: root.busy ? (root.actionMessage || "Applying changes…")
          : root.actionError || (root.model && root.model.message ? root.model.message : (status === "loading" ? root.loadingText : ""))
        retry: Boolean(root.model && root.model.status === "error" && !root.busy)
        onRetryRequested: root.commandRequested(["retry", root.kind], "Checking service…")
      }

      Column {
        id: body
        width: parent.width
        spacing: 6
      }
    }
  }
}
