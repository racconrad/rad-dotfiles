-- https://wiki.hypr.land/configuring/core/rules/
hl.window_rule({
    name  = "suppress-maximize-events",
    match = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name  = "fix-xwayland-drags",
    match = { class = "^$", title = "^$", xwayland = true, float = true, fullscreen = false, pin = false },
    no_focus = true,
})

-- hypr-canvas only moves floating windows, so every window floats.
hl.window_rule({
    name  = "float-all-for-canvas",
    match = { class = ".*" },
    float = true,
})

hl.window_rule({
    name  = "idle-inhibit-fullscreen",
    match = { fullscreen = true },
    idle_inhibit = "fullscreen",
})

-- Bar, notifications and OSD blur like windows do.
hl.layer_rule({
    name  = "blur-shell-layers",
    match = { namespace = "^(swaync-control-center|swaync-notification-window|swayosd)$" },
    blur  = true,
    ignore_alpha = 0.3,
})
