-- https://wiki.hypr.land/configuring/core/monitors/
hl.monitor({ output = "eDP-1", mode = "preferred", position = "0x0", scale = "auto" })
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1, mirror = "eDP-1" })

-- Any other display that gets plugged in.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
