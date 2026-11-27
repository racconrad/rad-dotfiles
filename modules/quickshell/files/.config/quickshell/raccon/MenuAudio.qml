import QtQuick

MenuControlPage {
  id: root

  property string openChannel: ""
  signal volumeRequested(string channel, int percent)

  title: "Audio"
  tagText: "02 // AUDIO"
  tone: "primary"
  kind: "audio"
  loadingText: "Loading audio devices…"
  initialFocusItem: output.muteButton.enabled ? output.muteButton : mixer

  headingActions: CutButton {
    id: mixer
    icon: "󰒓"
    text: "MIX"
    tone: "paper"
    enabled: !root.busy
    onClicked: root.commandRequested(["advanced", "audio"], "Opening audio mixer…")
  }

  MenuAudioChannel {
    id: output
    width: root.width
    channel: "output"
    device: root.model ? root.model.output : null
    devices: root.model && root.model.outputs ? root.model.outputs : []
    expanded: root.openChannel === channel
    available: !root.busy
    onToggleRequested: root.openChannel = expanded ? "" : channel
    onMuteRequested: token => root.commandRequested(["audio-mute", channel, token], "Changing output mute…")
    onDeviceRequested: token => {
      root.openChannel = "";
      root.commandRequested(["audio-device", channel, token], "Changing audio output…");
    }
    onVolumeRequested: percent => root.volumeRequested(channel, percent)
  }

  Zigzag {
    width: root.width
    height: 6
    color: Theme.ink
    edge: "bottom"
    teeth: 16
  }

  MenuAudioChannel {
    width: root.width
    channel: "input"
    device: root.model ? root.model.input : null
    devices: root.model && root.model.inputs ? root.model.inputs : []
    expanded: root.openChannel === channel
    available: !root.busy
    onToggleRequested: root.openChannel = expanded ? "" : channel
    onMuteRequested: token => root.commandRequested(["audio-mute", channel, token], "Changing microphone mute…")
    onDeviceRequested: token => {
      root.openChannel = "";
      root.commandRequested(["audio-device", channel, token], "Changing microphone…");
    }
    onVolumeRequested: percent => root.volumeRequested(channel, percent)
  }
}
