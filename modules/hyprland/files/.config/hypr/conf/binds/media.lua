-- Volume and brightness go through swayosd so the on-screen indicator keeps working.
local run  = hl.dsp.exec_cmd
local held = { locked = true, repeating = true }
local once = { locked = true }

hl.bind("XF86AudioRaiseVolume",  run("swayosd-client --output-volume raise"),       held)
hl.bind("XF86AudioLowerVolume",  run("swayosd-client --output-volume lower"),       held)
hl.bind("XF86AudioMute",         run("swayosd-client --output-volume mute-toggle"), once)
hl.bind("XF86AudioMicMute",      run("swayosd-client --input-volume mute-toggle"),  once)
hl.bind("XF86MonBrightnessUp",   run("swayosd-client --brightness raise"),          held)
hl.bind("XF86MonBrightnessDown", run("swayosd-client --brightness lower"),          held)

hl.bind("XF86AudioPlay",  run("playerctl play-pause"), once)
hl.bind("XF86AudioPause", run("playerctl play-pause"), once)
hl.bind("XF86AudioNext",  run("playerctl next"),       once)
hl.bind("XF86AudioPrev",  run("playerctl previous"),   once)
