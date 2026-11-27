import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// Soft preview of the newest capture: glides in above the bar, waits while hovered
// and glides out by itself. A click opens the file; the pencil edits it.
PanelWindow {
  id: root
  signal closeRequested

  readonly property string bin: Quickshell.env("HOME") + "/.local/bin/raccon-capture"
  property string file: ""
  property string thumb: ""
  property bool leaving: false
  readonly property bool video: file.endsWith(".mp4")
  readonly property string shown: video ? thumb : file

  function leave() { if (!leaving) { leaving = true; outAnim.start(); } }

  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.namespace: "raccon-capture-preview"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
  mask: Region { item: card }

  Process {
    running: true
    command: [root.bin, "recent", "1"]
    stdout: SplitParser {
      onRead: line => {
        root.file = line;
        // exec() so the command is the new path when it starts, not the previous binding value.
        if (line.endsWith(".mp4")) thumbProc.exec([root.bin, "thumb", line]);
      }
    }
  }

  Process {
    id: thumbProc
    stdout: SplitParser { onRead: line => root.thumb = line }
  }

  // Dismiss after a while, but never under the pointer.
  Timer { id: dismiss; interval: 6500; running: root.file !== "" && !area.containsMouse && !root.leaving; onTriggered: root.leave() }

  Item {
    id: card
    width: 232; height: 144
    x: 14 + slide
    y: root.height - 64 - 10 - height - 14
    property real slide: -width - 40
    opacity: 0

    Rectangle {
      x: 5; y: 5; width: parent.width; height: parent.height
      radius: 10; topLeftRadius: 28; bottomRightRadius: 28
      color: Theme.tone("secondary").bg
    }
    Rectangle {
      id: frame
      anchors.fill: parent
      radius: 10; topLeftRadius: 28; bottomRightRadius: 28
      color: Theme.tone("primary").bg
      scale: area.containsMouse ? 1.03 : 1
      Behavior on scale { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }

      Image {
        id: img
        anchors { fill: parent; margins: 6 }
        source: root.shown !== "" ? "file://" + root.shown : ""
        sourceSize.width: 464
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
      }
      // Time left, as a thin line.
      Rectangle {
        anchors { left: parent.left; bottom: parent.bottom; leftMargin: 30; bottomMargin: 3 }
        height: 2; radius: 1; color: Theme.on_surface; opacity: 0.5
        width: (parent.width - 60) * remaining
        property real remaining: 1
        NumberAnimation on remaining { from: 1; to: 0; duration: 6500; running: root.file !== "" && !area.containsMouse && !root.leaving }
      }
    }

    MouseArea {
      id: area
      anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
      onClicked: { Quickshell.execDetached(["xdg-open", root.file]); root.leave(); }
    }

    // Video badge.
    Rectangle {
      visible: root.video && !area.containsMouse
      width: 38; height: 38; radius: 19
      anchors.centerIn: parent
      color: Qt.alpha(Theme.surface, 0.75)
      Text { anchors.centerIn: parent; text: "\uf04b"; color: Theme.on_surface; font { family: Theme.fontMono; pixelSize: 15 } }
    }

    Row {
      visible: area.containsMouse
      anchors { right: parent.right; top: parent.top; rightMargin: 12; topMargin: 12 }
      spacing: 6
      Repeater {
        model: [
          { glyph: "\uf044", edit: true },
          { glyph: "\uf07b", edit: false }
        ]
        Rectangle {
          required property var modelData
          visible: !(modelData.edit && root.video)
          width: 28; height: 28; radius: 14
          color: Theme.surface_container_high
          Text { anchors.centerIn: parent; text: parent.modelData.glyph; color: Theme.on_surface; font { family: Theme.fontMono; pixelSize: 13 } }
          MouseArea {
            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
            onClicked: {
              if (parent.modelData.edit) Quickshell.execDetached(["swappy", "-f", root.file, "-o", root.file]);
              else Quickshell.execDetached([root.bin, "folder"]);
              root.leave();
            }
          }
        }
      }
    }

    ParallelAnimation {
      id: inAnim
      running: root.file !== ""
      NumberAnimation { target: card; property: "slide"; to: 0; duration: 450; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "opacity"; to: 1; duration: 420; easing.type: Easing.OutCubic }
    }
    ParallelAnimation {
      id: outAnim
      NumberAnimation { target: card; property: "slide"; to: -card.width - 40; duration: 520; easing.type: Easing.InCubic }
      NumberAnimation { target: card; property: "opacity"; to: 0; duration: 420; easing.type: Easing.InQuad }
      onFinished: root.closeRequested()
    }
  }
}
