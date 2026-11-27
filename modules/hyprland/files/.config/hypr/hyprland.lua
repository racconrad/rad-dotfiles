-- Entry point. One file per concern under conf/; edit those, not this file.
-- Check changes with: Hyprland --verify-config -c ~/.config/hypr/hyprland.lua

require("conf.monitors")
require("conf.environment")
require("conf.input")
require("conf.look")
require("conf.animations")

local config = os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")
local function source_optional(path)
    local file = io.open(path, "r")
    if file then
        file:close()
        dofile(path)
    end
end
source_optional(config .. "/matugen/out/hyprland-colors.lua")
source_optional(config .. "/hypr/desktop-style.lua")
source_optional(config .. "/hypr/desktop-power.lua")

require("conf.layouts")
require("conf.rules")
require("conf.binds.apps")
require("conf.binds.windows")
require("conf.binds.canvas")
require("conf.binds.workspaces")
require("conf.binds.media")
require("conf.autostart")
source_optional(config .. "/hypr/custom.lua")
