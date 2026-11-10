-- Colorscheme from the wallpaper palette (matugen writes lua/matugen_colors.lua).
function _G.MatugenReload()
  package.loaded["matugen_colors"] = nil
  local ok, colors = pcall(require, "matugen_colors")
  if ok then
    require("base16-colorscheme").setup(colors)
    vim.api.nvim_set_hl(0, "DashboardHeader", { fg = colors.base0B, bold = true })
    vim.api.nvim_set_hl(0, "DashboardKey", { fg = colors.base0A, bold = true })
    vim.api.nvim_set_hl(0, "DashboardIcon", { fg = colors.base0D })
    vim.api.nvim_set_hl(0, "DashboardDesc", { fg = colors.base05 })
    vim.api.nvim_set_hl(0, "DashboardFooter", { fg = colors.base03, italic = true })
    vim.api.nvim_set_hl(0, "FloatBorder", { fg = colors.base03 })
  else
    vim.cmd.colorscheme("tokyonight")
  end
end

return {
  {
    "RRethy/base16-nvim",
    lazy = false,
    priority = 1000,
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = function()
        _G.MatugenReload()
      end,
    },
  },
}
