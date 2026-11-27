-- Launchers and desktop actions.
local p = require("conf.programs")
local mod = "SUPER"
local run = hl.dsp.exec_cmd

hl.bind(mod .. " + Return",                  run(p.terminal))
hl.bind(mod .. " + E",                       run(p.files))
hl.bind(mod .. " + B",                       run(p.browser))
hl.bind(mod .. " + A",                       run(p.launcher))
-- Tapping Super alone opens the menu; Super combos do not (release bind on the modifier itself).
hl.bind(mod .. " + Super_L",                 run(p.launcher), { release = true })
hl.bind(mod .. " + SHIFT + Return",          run(p.launcher))
hl.bind(mod .. " + CTRL + Return",           run(p.search))
hl.bind(mod .. " + SHIFT + Escape",          run(p.terminal .. " -e btop"))
hl.bind(mod .. " + V",                       run("~/.local/bin/clip-pick"))
hl.bind(mod .. " + N",                       run("swaync-client -t -sw"))
hl.bind(mod .. " + P",                       run("~/.local/bin/display-mode"))
hl.bind(mod .. " + W",                       run("~/.local/bin/raccon-float wallpaper"))
hl.bind(mod .. " + SHIFT + W",               run("waypaper"))
hl.bind(mod .. " + ALT + W",                 run("~/.local/bin/wallpaper-scheme"))

hl.bind(mod .. " + SHIFT + L",               run(p.lock))
hl.bind(mod .. " + CTRL + Q",                run(p.session))

-- Capture manager panel, quick area shot, full screen, and recording toggle.
hl.bind(mod .. " + SHIFT + S",               run("qs -c raccon ipc call raccon toggle capture"))
hl.bind(mod .. " + CTRL + S",                run(p.shot .. " shot area"))
hl.bind("Print",                             run(p.shot .. " shot screen"))
hl.bind(mod .. " + Print",                   run(p.shot .. " rec toggle"))
hl.bind(mod .. " + SHIFT + Print",           run(p.shot .. " folder"))
