-- Launchers and desktop actions.
local p = require("conf.programs")
local mod = "SUPER"
local run = hl.dsp.exec_cmd

hl.bind(mod .. " + Return",                  run(p.terminal))
hl.bind(mod .. " + E",                       run(p.files))
hl.bind(mod .. " + B",                       run(p.browser))
hl.bind(mod .. " + A",                       run(p.launcher))
hl.bind(mod .. " + SHIFT + Return",          run(p.launcher))
hl.bind(mod .. " + CTRL + Return",           run(p.search))
hl.bind(mod .. " + SHIFT + Escape",          run(p.terminal .. " -e btop"))
hl.bind(mod .. " + V",                       run("~/.local/bin/clip-pick"))
hl.bind(mod .. " + N",                       run("swaync-client -t -sw"))
hl.bind(mod .. " + W",                       run("~/.local/bin/raccon-float wallpaper"))
hl.bind(mod .. " + SHIFT + W",               run("waypaper"))
hl.bind(mod .. " + ALT + W",                 run("~/.local/bin/wallpaper-scheme"))
hl.bind(mod .. " + ALT + T",                 run("~/.local/bin/desktop-style toggle"))
hl.bind(mod .. " + SHIFT + B",               run("~/.local/bin/waybar-toggle"))
hl.bind(mod .. " + CTRL + Escape",           run("pkill -SIGUSR1 -x waybar"))

hl.bind(mod .. " + SHIFT + L",               run(p.lock))
hl.bind(mod .. " + CTRL + Q",                run(p.session))

hl.bind(mod .. " + SHIFT + S",               run(p.shot .. " area"))
hl.bind("Print",                             run(p.shot .. " full"))
