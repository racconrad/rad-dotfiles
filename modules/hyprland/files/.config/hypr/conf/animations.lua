-- https://wiki.hypr.land/configuring/core/animations/
hl.curve("easeOutQuint", { type = "bezier", points = { {0.23, 1},   {0.32, 1} } })
hl.curve("almostLinear", { type = "bezier", points = { {0.5, 0.5},  {0.75, 1} } })
hl.curve("quick",        { type = "bezier", points = { {0.15, 0},   {0.1, 1}  } })
hl.curve("easy",         { type = "spring", mass = 1, stiffness = 238.1191, damping = 24.21279333 })

local function set_speed(factor)
    hl.config({ animations = { enabled = factor > 0 } })
    if factor == 0 then return end
    local speed = 1 / factor
    hl.animation({ leaf = "global",        enabled = true, speed = speed * 10,   bezier = "default" })
    hl.animation({ leaf = "border",        enabled = true, speed = speed * 5.39, bezier = "easeOutQuint" })
    hl.animation({ leaf = "windows",       enabled = true, speed = speed * 4.79, spring = "easy" })
    hl.animation({ leaf = "windowsIn",     enabled = true, speed = speed * 4.1,  spring = "easy", style = "popin 87%" })
    hl.animation({ leaf = "windowsOut",    enabled = true, speed = speed * 1.49, bezier = "linear", style = "popin 87%" })
    hl.animation({ leaf = "fade",          enabled = true, speed = speed * 3.03, bezier = "quick" })
    hl.animation({ leaf = "layers",        enabled = true, speed = speed * 3.81, bezier = "easeOutQuint" })
    hl.animation({ leaf = "layersIn",      enabled = true, speed = speed * 4,    bezier = "easeOutQuint", style = "fade" })
    hl.animation({ leaf = "layersOut",     enabled = true, speed = speed * 1.5,  bezier = "linear", style = "fade" })
    hl.animation({ leaf = "workspaces",    enabled = true, speed = speed * 1.94, bezier = "almostLinear", style = "fade" })
end

set_speed(1)
return set_speed
