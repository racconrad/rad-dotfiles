local paths = require("config.paths")

return {
  {
    "folke/snacks.nvim",
    opts = function(_, opts)
      opts.picker = opts.picker or {}
      opts.picker.sources = opts.picker.sources or {}
      local dirs = {
        "~/projects",
        "~/dev",
        "~/work",
        "~/src",
        "~/.config",
      }
      local vault = paths.vault()
      if vault and not vim.tbl_contains(dirs, vault) then
        table.insert(dirs, vault)
      end
      opts.picker.sources.projects = { dirs = dirs }
      return opts
    end,
    keys = {
      { "<leader>p", function() Snacks.picker.projects() end, desc = "Projects (Quick Switch)" },
      {
        "<leader>fo",
        function()
          local vault = paths.vault()
          if vault then
            Snacks.picker.files({ cwd = vault })
          else
            vim.notify("No Obsidian vault found. Set vim.g.obsidian_vault or OBSIDIAN_VAULT", vim.log.levels.WARN)
          end
        end,
        desc = "Find Obsidian Notes",
      },
      {
        "<leader>so",
        function()
          local vault = paths.vault()
          if vault then
            Snacks.picker.grep({ cwd = vault })
          else
            vim.notify("No Obsidian vault found. Set vim.g.obsidian_vault or OBSIDIAN_VAULT", vim.log.levels.WARN)
          end
        end,
        desc = "Search Obsidian Vault",
      },
      { "<leader>x", function() Snacks.bufdelete() end, desc = "Close Current Buffer" },
    },
  },
}
