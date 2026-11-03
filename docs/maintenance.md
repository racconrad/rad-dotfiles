# Maintaining your dots

## Bring changes from your main machine

```sh
./rdot changes                        # what changed, writes nothing
./rdot changes --modules ai,zsh --diff
./rdot capture --modules ai,zsh       # copy changed files into the repo
```

Capture backs up the previous files first, including uncommitted edits.

## AI skills

The optional **ai** module stores only the list of skills installed with skills.sh. No MCP servers, settings or credentials are saved. It is not in the default profile.

```sh
python3 scripts/capture.py --from-home "$HOME" --ai-only
./install.sh --modules ai --setup ai-skills --yes
```

## What is never shipped

Credentials, SSH/GPG keys, browser profiles, app sessions, shell history, caches, wallpapers, private widget content and Git identity. Run `python3 scripts/inventory.py` to list every shipped file. [`modules.json`](../modules.json) defines modules, dependencies and alternatives.

## Development

Edit `modules/MODULE/files/` as the source of truth.

```sh
# Try an install in a throwaway HOME
./install.sh --target /tmp/raccon-preview-home --modules tinywidgets \
  --widget-install configure --widget-profile Personal --no-packages --setup none --yes

python3 -m unittest discover -s tests -v
```

Tests use disposable homes and mock package and app commands.
