-- hypr-canvas: infinite canvas over floating windows (daemon starts in autostart.lua).
local mod = "SUPER"
local bin = "~/.local/bin/hypr-canvas"
local function canvas(args) return hl.dsp.exec_cmd(bin .. " " .. args) end

hl.bind(mod .. " + Z",         hl.dsp.focus({ workspace = "-1" }))
hl.bind(mod .. " + X",         hl.dsp.focus({ workspace = "+1" }))
hl.bind(mod .. " + SHIFT + Z", hl.dsp.window.move({ workspace = "-1" }))
hl.bind(mod .. " + SHIFT + X", hl.dsp.window.move({ workspace = "+1" }))

hl.bind(mod .. " + C",         canvas("center"))
hl.bind(mod .. " + R",         canvas("home"))
hl.bind(mod .. " + BackSpace", canvas("back"))

for _, dir in ipairs({ "left", "right", "up", "down" }) do
    local d = ({ left = { -60, 0 }, right = { 60, 0 }, up = { 0, -60 }, down = { 0, 60 } })[dir]
    hl.bind(mod .. " + " .. dir,                canvas("look " .. dir))
    hl.bind(mod .. " + ALT + " .. dir,          canvas("pan " .. dir),  { repeating = true })
    hl.bind(mod .. " + SHIFT + " .. dir,        canvas("move " .. dir), { repeating = true })
    hl.bind(mod .. " + CTRL + " .. dir,         hl.dsp.window.resize({ x = d[1], y = d[2], relative = true }), { repeating = true })
end

-- Drag the empty desktop (Super+Alt+left button) or push the canvas with a dragged window (Super+left button).
-- Window drag itself stays Hyprland's own (windows.lua); these binds only pass the event along.
hl.bind(mod .. " + ALT + mouse:272", canvas("drag-start pan"),  { non_consuming = true })
hl.bind(mod .. " + ALT + mouse:272", canvas("drag-end"),        { release = true, non_consuming = true })
hl.bind(mod .. " + mouse:272",       canvas("drag-start edge"), { non_consuming = true })
hl.bind(mod .. " + mouse:272",       canvas("drag-end"),        { release = true, non_consuming = true })
