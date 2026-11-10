local paths = require("config.paths")

return {
  {
    "nvimdev/dashboard-nvim",
    opts = function(_, opts)
      local logo = [[
⠀⠀⠀⠀⢀⣠⠤⠒⠒⠒⠒⠒⠒⠤⠤⣀⣀⣀⣀⣀⡤⠤⠤⠄⠤⡤⣲⣽⡇⠀
⠀⠀⡠⠖⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠁⠉⠁⠀⠀⠚⠛⠿⠰⠟⣿⡇⠀
⠀⡴⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡏⠀⠀⠀⠀⠙⡄⠀
⢰⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣇⠀⢸⣿⣷⣦⡇⠀
⣼⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡿⠷⣄⠉⠛⠈⠀⠀
⣇⠀⠀⠀⠀⣧⠀⠀⠀⠀⠀⠈⢦⠀⠀⠀⠀⠀⠀⠀⠀⣼⣆⠀⠈⢂⠀⣀⣡⠀
⠹⣴⣿⣶⣶⣿⣆⠀⠀⠀⠀⠀⠈⣷⡀⠀⠀⠀⠀⠀⠰⠿⠿⠦⠤⠶⣷⣿⣧⣄
⠀⢻⣩⣶⣿⣾⣏⠢⠀⠀⠀⠀⠀⢻⠈⠑⢄⠀⠀⢀⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠈⠿⢋⣥⣶⣿⣆⠑⡀⠀⠀⠀⡞⠀⠀⠈⢶⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠈⢼⡿⠋⢀⣠⣵⡘⢦⣤⣬⣤⣴⣤⣄⠘⠿⠶⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠁⢴⣿⡟⠉⢑⡌⠉⠉⠉⠛⠳⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠙⢄⣾⡿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀

                  R A C C O O N
]]

      logo = string.rep("\n", 2) .. logo .. "\n"

      opts.config = opts.config or {}
      opts.config.header = vim.split(logo, "\n")

      opts.config.center = {
        { action = "lua Snacks.picker.projects()", desc = " Projects", icon = " ", key = "p" },
        {
          action = function()
            local vault = paths.vault()
            if vault then
              Snacks.picker.files({ cwd = vault })
            else
              vim.notify("No Obsidian vault found. Set vim.g.obsidian_vault or OBSIDIAN_VAULT", vim.log.levels.WARN)
            end
          end,
          desc = " Obsidian Vault",
          icon = "󱓧 ",
          key = "o",
        },
        {
          action = function()
            Snacks.picker.files({ cwd = paths.dotfiles() })
          end,
          desc = " Dotfiles",
          icon = " ",
          key = "d",
        },
        { action = "lua LazyVim.pick()()", desc = " Find File", icon = " ", key = "f" },
        { action = 'lua LazyVim.pick("oldfiles")()', desc = " Recent Files", icon = " ", key = "r" },
        { action = 'lua LazyVim.pick("live_grep")()', desc = " Find Text (Grep)", icon = " ", key = "g" },
        { action = "lua LazyVim.pick.config_files()()", desc = " Config Files", icon = " ", key = "c" },
        { action = 'lua require("persistence").load()', desc = " Restore Session", icon = " ", key = "s" },
        { action = "Lazy", desc = " Lazy Plugins", icon = "󰒲 ", key = "l" },
        { action = function() vim.api.nvim_input("<cmd>qa<cr>") end, desc = " Quit", icon = " ", key = "q" },
      }

      for _, button in ipairs(opts.config.center) do
        button.desc = button.desc .. string.rep(" ", 43 - #button.desc)
        button.key_format = "  %s"
      end

      return opts
    end,
  },
}
