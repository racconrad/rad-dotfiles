-- Window actions. Arrow-key focus, move and resize live in canvas.lua.
local mod = "SUPER"

hl.bind(mod .. " + Q",      hl.dsp.window.close())
hl.bind(mod .. " + Delete", hl.dsp.exit())
hl.bind(mod .. " + T",      hl.dsp.window.float({ action = "toggle" }))
hl.bind(mod .. " + SHIFT + P", hl.dsp.window.pseudo())
hl.bind(mod .. " + J",      hl.dsp.layout("togglesplit"))

hl.bind(mod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind(mod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })
