# Raccon Dots — base Zsh configuration.
# Installing the zsh module replaces ~/.zshrc with this file (a backup is kept).
# Put machine-specific settings below the personal marker at the end: the
# installer keeps that block and `rdot capture` never copies this file.

export PATH="$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
export EDITOR=nvim VISUAL=nvim

# ── Oh My Zsh with the native Raccon prompt ─────────────────────────────────
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="raccon"

# Plugin settings before loading
fastfile_var_prefix="${fastfile_var_prefix:-?}"

# Plugins to load (add more plugins here or via plugins+=(...) in ~/.zshrc.plugins)
plugins=(
  git
  copyfile
  copybuffer
  copypath
  fastfile
  sudo
  zsh-autosuggestions
  zsh-syntax-highlighting
)

# Optional user plugins hook before Oh My Zsh loads (allows plugins+=(...) and custom settings)
[[ -r "$HOME/.zshrc.plugins" ]] && source "$HOME/.zshrc.plugins"

if [[ -r "$ZSH/oh-my-zsh.sh" ]]; then
  source "$ZSH/oh-my-zsh.sh"
else
  autoload -Uz compinit && compinit
  bindkey -e
fi

# ── Plugin configuration (applied AFTER plugins are loaded) ─────────────────
# Fallback to system packages if not loaded by Oh My Zsh:
if ! (( $+functions[_zsh_autosuggest_suggest] )) && [[ -r /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
fi
if (( $+functions[_zsh_autosuggest_suggest] )); then
  ZSH_AUTOSUGGEST_STRATEGY=(history completion)
  ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=8'
fi

if ! (( $+functions[_zsh_highlight] )) && [[ -r /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
fi

if [[ -r /usr/share/zsh/plugins/zsh-history-substring-search/zsh-history-substring-search.zsh ]] && ! (( $+functions[history-substring-search-up] )); then
  source /usr/share/zsh/plugins/zsh-history-substring-search/zsh-history-substring-search.zsh
fi
if (( $+functions[history-substring-search-up] )); then
  bindkey '^[[A' history-substring-search-up
  bindkey '^[[B' history-substring-search-down
  [[ -n ${terminfo[kcuu1]} ]] && bindkey "${terminfo[kcuu1]}" history-substring-search-up
  [[ -n ${terminfo[kcud1]} ]] && bindkey "${terminfo[kcud1]}" history-substring-search-down
fi

# ── Greeting in Kitty only ───────────────────────────────────────────────────
if [[ $TERM == xterm-kitty && -o interactive && -z $NVIM && -z $VSCODE_PID && $TERM_PROGRAM != "vscode" && -z $RACCON_NO_FETCH ]]; then
  command -v fastfetch >/dev/null && fastfetch
fi

# ── General aliases ──────────────────────────────────────────────────────────
alias zshconfig="$EDITOR ~/.zshrc"
alias v=nvim vi=nvim vim=nvim
command -v lazygit >/dev/null && alias lg=lazygit

# ── Tools (each one only when installed) ────────────────────────────────────
if command -v eza >/dev/null; then
  alias ls='eza --icons=auto --group-directories-first'
  alias ll='eza -l --icons=auto --git --group-directories-first'
  alias la='eza -la --icons=auto --git --group-directories-first'
  alias lt='eza --tree --level=2 --icons=auto'
fi
command -v bat >/dev/null && alias cat='bat --paging=never --style=plain'
if command -v fzf >/dev/null; then
  source <(fzf --zsh)
  export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
  export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
  export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
  export FZF_CTRL_T_OPTS="--preview 'bat --color=always --style=numbers --line-range=:200 {}'"
fi
command -v zoxide >/dev/null && eval "$(zoxide init zsh)"
if command -v yazi >/dev/null; then
  # `y` opens yazi and moves the shell to the folder you leave it in.
  y() {
    local tmp cwd
    tmp="$(mktemp -t yazi-cwd.XXXXXX)"
    yazi "$@" --cwd-file="$tmp"
    if cwd="$(cat -- "$tmp")" && [[ -n "$cwd" && "$cwd" != "$PWD" ]]; then builtin cd -- "$cwd"; fi
    rm -f -- "$tmp"
  }
fi
if [[ -x ~/.local/bin/explore ]]; then
  alias explore='~/.local/bin/explore' open='~/.local/bin/explore'
  alias files='~/.local/bin/explore' fm='~/.local/bin/explore'
fi

# Helper function to load additional plugins dynamically from the personal section:
load_plugins() {
  local p dir
  for p in "$@"; do
    for dir in "$ZSH_CUSTOM/plugins/$p" "$ZSH/plugins/$p" "/usr/share/zsh/plugins/$p"; do
      if [[ -f "$dir/$p.plugin.zsh" ]]; then
        source "$dir/$p.plugin.zsh"
        break
      elif [[ -f "$dir/$p.zsh" ]]; then
        source "$dir/$p.zsh"
        break
      fi
    done
  done
}

# >>> personal (kept on reinstall, never captured)
