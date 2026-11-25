-- Entry point. One file per concern under conf/; edit those, not this file.
-- Check changes with: Hyprland --verify-config -c ~/.config/hypr/hyprland.lua

require("conf.monitors")
require("conf.environment")
require("conf.input")
require("conf.look")
require("conf.animations")
require("conf.layouts")
require("conf.rules")
require("conf.binds.apps")
require("conf.binds.windows")
require("conf.binds.canvas")
require("conf.binds.workspaces")
require("conf.binds.media")
require("conf.autostart")
