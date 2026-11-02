#!/usr/bin/env bash
set -euo pipefail
(( EUID == 0 )) || { echo 'Run through extras/install-sddm.sh --apply.' >&2; exit 1; }
source_theme=${1:?Missing prepared theme}
[[ -f "$source_theme/Main.qml" && -f "$source_theme/theme.conf" ]] || { echo 'Prepared theme is incomplete.' >&2; exit 1; }
backup=$(mktemp -d /var/backups/raccon-sddm-XXXXXXXX)
theme=/usr/share/sddm/themes/raccon
config=/etc/sddm.conf.d/zz-raccon-theme.conf
[[ ! -e "$theme" ]] || cp -a -- "$theme" "$backup/theme"
[[ ! -e "$config" ]] || cp -a -- "$config" "$backup/zz-raccon-theme.conf"
# /etc/sddm.conf overrides conf.d, so back it up and update its Theme/Current
# only when that higher-priority file already sets Current.
if [[ -f /etc/sddm.conf ]]; then cp -a /etc/sddm.conf "$backup/sddm.conf"; fi
install -d -m755 "$theme" /etc/sddm.conf.d
cp -a -- "$source_theme/." "$theme/"
chown -R root:root "$theme"
find "$theme" -type d -exec chmod 755 {} +
find "$theme" -type f -exec chmod 644 {} +
printf '[Theme]\nCurrent=raccon\n' > "$config"
chmod 644 "$config"
python3 - <<'PY'
from pathlib import Path
import re
p=Path('/etc/sddm.conf')
if p.is_file():
    section=''
    lines=p.read_text().splitlines(keepends=True)
    for i,line in enumerate(lines):
        m=re.match(r'\s*\[([^]]+)\]',line)
        if m:section=m[1]
        elif section=='Theme' and re.match(r'\s*Current\s*=',line):
            lines[i]='Current=raccon\n'
    p.write_text(''.join(lines))
PY
cat > "$backup/restore.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
(( EUID == 0 )) || { echo 'Run this restore script with sudo.' >&2; exit 1; }
saved=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
rm -rf /usr/share/sddm/themes/raccon
if [[ -d "$saved/theme" ]]; then cp -a "$saved/theme" /usr/share/sddm/themes/raccon; fi
if [[ -f "$saved/zz-raccon-theme.conf" ]]; then
  cp -a "$saved/zz-raccon-theme.conf" /etc/sddm.conf.d/zz-raccon-theme.conf
else
  rm -f /etc/sddm.conf.d/zz-raccon-theme.conf
fi
if [[ -f "$saved/sddm.conf" ]]; then cp -a "$saved/sddm.conf" /etc/sddm.conf; fi
echo 'Previous SDDM theme restored. No session was restarted.'
SH
chmod 700 "$backup/restore.sh"
printf 'Raccon selected for the next login. Your session is still running.\nBackup: %s\nUndo: sudo %q/restore.sh\n' "$backup" "$backup"
