-- Colorscheme from the wallpaper palette (matugen writes lua/matugen_colors.lua).
function _G.MatugenReload()
  package.loaded["matugen_colors"] = nil
  local ok, colors = pcall(require, "matugen_colors")
  if ok then
    require("base16-colorscheme").setup(colors)
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
