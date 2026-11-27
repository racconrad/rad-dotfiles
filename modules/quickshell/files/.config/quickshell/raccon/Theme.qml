pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Material You palette. Fallback default colors; matugen overwrites colors.json.
Singleton {
  id: root

  property color primary: "#e1b8f5"
  property color on_primary: "#422255"
  property color primary_container: "#5a396d"
  property color on_primary_container: "#f5d9ff"
  property color secondary: "#d3c0d8"
  property color secondary_container: "#4f4255"
  property color on_secondary_container: "#efdcf5"
  property color tertiary: "#f4b7b8"
  property color tertiary_container: "#663b3c"
  property color on_tertiary_container: "#ffd9d9"
  property color error: "#ffb4ab"
  property color error_container: "#93000a"
  property color on_error_container: "#ffdad6"
  property color surface: "#161217"
  property color surface_container: "#221e24"
  property color surface_container_high: "#2d282e"
  property color surface_container_highest: "#383339"
  property color on_surface: "#e9e0e7"
  property color on_surface_variant: "#cec3ce"
  property color outline: "#978e98"
  property color outline_variant: "#4b444d"
  property color shadow: "#000000"

  // A wallpaper change fades the whole palette instead of snapping.
  Behavior on primary { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on on_primary { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on primary_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on on_primary_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on secondary { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on secondary_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on on_secondary_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on tertiary { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on tertiary_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on on_tertiary_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on error { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on error_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on on_error_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on surface { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on surface_container { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on surface_container_high { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on surface_container_highest { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on on_surface { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on on_surface_variant { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on outline { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on outline_variant { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
  Behavior on shadow { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }

  readonly property int radius: 20
  readonly property int border: 0
  readonly property int shadowOffset: 5
  readonly property int motionFast: 140
  readonly property int motionBase: 220
  property bool animations: true
  readonly property string fontDisplay: "Fira Sans Compressed"
  readonly property string fontMono: "JetBrainsMono Nerd Font"
  readonly property string fontTag: "FantasqueSansM Nerd Font Mono"
  // Near-black outline of every cut piece; the hard shadow uses shadowColor (an accent).
  readonly property color ink: Qt.darker(surface_container, 1.25)
  readonly property color shadowColor: primary_container

  function tone(name) {
    switch (name) {
      case "primary":
        return { bg: root.primary_container, fg: root.on_primary_container, shadow: root.secondary_container };
      case "secondary":
        return { bg: root.secondary_container, fg: root.on_secondary_container, shadow: root.tertiary_container };
      case "tertiary":
        return { bg: root.tertiary_container, fg: root.on_tertiary_container, shadow: root.primary_container };
      case "error":
        return { bg: root.error_container, fg: root.on_error_container, shadow: root.tertiary_container };
      case "paper":
      default:
        return { bg: root.surface_container_high, fg: root.on_surface, shadow: root.primary_container };
    }
  }

  FileView {
    path: Quickshell.env("HOME") + "/.config/quickshell/raccon/colors.json"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: {
      try {
        const palette = JSON.parse(text());
        for (const key in palette)
          if (key in root) root[key] = palette[key];
      } catch (e) {
        console.warn("Theme: invalid colors.json", e);
      }
    }
  }

  FileView {
    path: Quickshell.env("HOME") + "/.config/raccon/config.json"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: {
      try {
        const cfg = JSON.parse(text());
        root.animations = typeof cfg.animations === "boolean" ? cfg.animations : true;
      } catch (_) {
        root.animations = true;
      }
    }
    onLoadFailed: root.animations = true
  }

  readonly property int motionSlap: 360
  readonly property real overshoot: 1.7

  function toneAt(i) {
    const tones = ["primary", "secondary", "tertiary"];
    const idx = ((i % tones.length) + tones.length) % tones.length;
    return tone(tones[idx]);
  }
}
