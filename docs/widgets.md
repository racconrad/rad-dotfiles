# tinyWidgets

Enable **tinyWidgets** on the Features page to open its own page. Get the source from [racconrad/tinyWidgets](https://github.com/racconrad/tinyWidgets); it defaults to `~/projects/tinyWidgets` and is never downloaded automatically.

| Option | Provides | Needs |
| --- | --- | --- |
| Runtime | Editor, widget catalog, manager, theme bridge | Eww, GTK3, gtk-layer-shell, Python GObject/Cairo; Rust and a C compiler to build |
| Layouts | Saved profiles and editor grid | tinyWidgets |
| Themes | Personal, Quiet, Pixel, Terminal | tinyWidgets |
| Motion | 60 FPS, Balanced 24 FPS or no transitions | tinyWidgets |
| Wallpaper colors | Live Matugen palette | Matugen / theme module |
| Music | MPRIS controls | `playerctl` |
| GitHub | Activity and avatar | GitHub CLI (`gh auth login`), ImageMagick |
| Minecraft | Animated scene | `python-pillow` |

## Layouts

**Personal**, **Trabajo**, **Gaming**, **Dashboard**, **Cyberpunk** and **silly**. Choose which to install and which is active. **Keep** preserves an existing `instances.json`; a new install starts with Trabajo.

Private commands, URLs, tokens, photo paths, tasks and credentials are never exported. Those widgets keep their place but start disabled.

```sh
widgetctl profile list
widgetctl profile apply Trabajo
widgetctl editor
```

## Install modes

- **Auto:** use the installed app; build only when missing.
- **Build:** rebuild from the source directory.
- **Configure:** install settings and layouts only.

```sh
./install.sh --modules tinywidgets --widget-profile Personal \
  --widget-theme quiet --widget-motion balanced --packages --yes
```

## Refresh the bundle from your desktop

```sh
python3 scripts/capture_widget_presets.py --from-home "$HOME"
```

Review the diff before committing.
