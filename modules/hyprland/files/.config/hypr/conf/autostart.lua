-- https://wiki.hypr.land/configuring/core/autostart/
hl.on("hyprland.start", function()
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP XDG_SESSION_TYPE DISPLAY")
    hl.exec_cmd("systemctl --user start hyprpolkitagent.service")

    hl.exec_cmd("awww-daemon")
    hl.exec_cmd("sh -c 'sleep 0.5; ~/.local/bin/wallpaper-restore'")

    hl.exec_cmd("swaync")
    hl.exec_cmd("swayosd-server")

    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")

    hl.exec_cmd("hypridle")

    hl.exec_cmd("~/.local/bin/hypr-canvas daemon")

    hl.exec_cmd("qs -c raccon --no-duplicate")
    hl.exec_cmd("hyprpm reload -n")
    hl.exec_cmd("~/.local/bin/desktop-power daemon")
end)
