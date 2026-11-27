-- https://wiki.hypr.land/configuring/core/config-options/#input
hl.config({
    input = {
        kb_layout          = "us",
        kb_variant         = "altgr-intl",
        numlock_by_default = true,
        repeat_rate        = 40,
        repeat_delay       = 300,

        follow_mouse = 1,
        accel_profile = "flat",

        touchpad = {
            natural_scroll        = true,
            tap_to_click          = true,
            disable_while_typing  = true,
            clickfinger_behavior  = true,
        },
    },

    cursor = {
        inactive_timeout  = 5,
        hide_on_key_press = true,
    },
})

hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
