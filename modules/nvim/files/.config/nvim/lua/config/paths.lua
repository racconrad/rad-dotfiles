local M = {}

---Resolve active Obsidian vault path dynamically without hardcoded user mounts.
---Checks user variable, environment variables, Obsidian config, and standard home folders.
---@return string|nil
function M.vault()
  if vim.g.obsidian_vault and vim.fn.isdirectory(vim.g.obsidian_vault) == 1 then
    return vim.g.obsidian_vault
  end
  for _, env in ipairs({ "OBSIDIAN_VAULT", "TASHNOTES_VAULT", "AI_DOCS_VAULT" }) do
    local v = vim.env[env]
    if v and vim.fn.isdirectory(v) == 1 then
      return v
    end
  end
  local confs = {
    vim.fn.expand("~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json"),
    vim.fn.expand("~/.config/obsidian/obsidian.json"),
  }
  for _, c in ipairs(confs) do
    if vim.fn.filereadable(c) == 1 then
      local ok, data = pcall(function()
        return vim.json.decode(table.concat(vim.fn.readfile(c), "\n"))
      end)
      if ok and data and data.vaults then
        for _, v in pairs(data.vaults) do
          if v.open and v.path and vim.fn.isdirectory(v.path) == 1 then
            return v.path
          end
        end
        for _, v in pairs(data.vaults) do
          if v.path and vim.fn.isdirectory(v.path) == 1 then
            return v.path
          end
        end
      end
    end
  end
  for _, cand in ipairs({ "~/notes", "~/obsidian", "~/vault", "~/Documents/notes" }) do
    local p = vim.fn.expand(cand)
    if vim.fn.isdirectory(p) == 1 then
      return p
    end
  end
  return nil
end

---Resolve dotfiles directory dynamically without hardcoded user mounts.
---@return string
function M.dotfiles()
  if vim.g.dotfiles_dir and vim.fn.isdirectory(vim.g.dotfiles_dir) == 1 then
    return vim.g.dotfiles_dir
  end
  for _, env in ipairs({ "DOTFILES_DIR", "DOTFILES" }) do
    local d = vim.env[env]
    if d and vim.fn.isdirectory(d) == 1 then
      return d
    end
  end
  for _, cand in ipairs({ "~/projects/raccon-dots", "~/.dotfiles", "~/dotfiles" }) do
    local p = vim.fn.expand(cand)
    if vim.fn.isdirectory(p) == 1 then
      return p
    end
  end
  return vim.fn.stdpath("config")
end

return M
