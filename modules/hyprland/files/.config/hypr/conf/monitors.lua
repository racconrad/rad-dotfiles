-- https://wiki.hypr.land/configuring/core/monitors/
hl.monitor({ output = "eDP-1", mode = "preferred", position = "0x0", scale = "auto" })
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1, mirror = "eDP-1" })

-- Any other display that gets plugged in.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

local function restore_projection()
    hl.exec_cmd("~/.local/bin/display-mode --restore")
end

hl.on("hyprland.start", restore_projection)
hl.on("config.reloaded", restore_projection)
hl.on("monitor.added", restore_projection)
hl.on("monitor.removed", restore_projection)
