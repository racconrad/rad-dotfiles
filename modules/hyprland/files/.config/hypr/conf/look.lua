-- https://wiki.hypr.land/configuring/core/config-options/
hl.config({
    general = {
        gaps_in     = 4,
        gaps_out    = 8,
        resize_on_border = true,
        allow_tearing    = false,
        layout           = "dwindle",
    },

    decoration = {
        blur     = { enabled = true, size = 4, passes = 2, new_optimizations = true, ignore_opacity = true },
    },

    misc = {
        disable_hyprland_logo   = true,
        force_default_wallpaper = 0,
        key_press_enables_dpms  = true,
        mouse_move_enables_dpms = true,
    },

    binds   = { workspace_back_and_forth = true },
    render  = { direct_scanout = 1 },
    xwayland = { force_zero_scaling = true },
})

require("conf.window-style")
