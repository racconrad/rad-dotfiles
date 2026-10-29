if test -r /usr/share/cachyos-fish-config/cachyos-config.fish
    source /usr/share/cachyos-fish-config/cachyos-config.fish
end
fish_add_path $HOME/.local/bin $HOME/go/bin
set -gx EDITOR nvim
set -gx VISUAL nvim
if command -q starship
    starship init fish | source
end
if command -q zoxide
    zoxide init fish | source
end
