"""Review and capture portable changes from the owner's primary machine."""
import argparse
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

import capture as desktop
from capture_ai import SKILL_LOCK, SECRET
import capture_widget_presets as widgets
from install import atomic_write, safe_destination

ROOT = Path(__file__).resolve().parents[1]
WIDGET_MODULES = {'widgets', 'widgets-profiles', 'widgets-themes', 'widgets-motion'}
MODULES = set(desktop.CONFIGS) | set(desktop.SCRIPTS) | WIDGET_MODULES | {'ai', 'desktop-styles'}


@dataclass
class Change:
    path: str
    before: bytes | None
    after: bytes | None
    old_mode: int | None
    new_mode: int | None

    @property
    def status(self):
        return 'added' if self.before is None else 'deleted' if self.after is None else 'modified'

    @property
    def module(self):
        return self.path.split('/')[1] if self.path.startswith('modules/') else 'widgets'


def snapshot(master, target, selected):
    """Run existing exporters in a temporary tree; source and checkout stay untouched."""
    missing = []
    enabled = set(selected)
    ai_present = (master / SKILL_LOCK).is_file()
    if 'ai' in enabled and not ai_present:
        enabled.remove('ai')
        missing.append('ai: no hay ' + SKILL_LOCK + ' en este HOME')
    original_desktop, original_widgets = desktop.ROOT, widgets.ROOT
    try:
        desktop.ROOT = widgets.ROOT = target
        with redirect_stdout(io.StringIO()):
            desktop.capture(master, modules=enabled - WIDGET_MODULES, missing=missing)
            if enabled & WIDGET_MODULES:
                required = ['instances.json', 'style.json', 'animation.json', 'editor.json']
                absent = [name for name in required if not (master / '.config/eww' / name).is_file()]
                if absent:
                    missing.append('widgets: faltan ' + ', '.join(absent))
                else:
                    widgets.capture(master)
    finally:
        desktop.ROOT, widgets.ROOT = original_desktop, original_widgets
    return missing


def safe_path(root, relative):
    path = Path(relative)
    if (path.is_absolute() or '..' in path.parts or
            (relative != 'widget-presets.json' and
             (len(path.parts) < 4 or path.parts[0] != 'modules' or path.parts[2] != 'files'))):
        raise ValueError(f'Ruta de captura no válida: {relative}')
    destination = safe_destination(root, relative)
    if destination.is_symlink():
        raise ValueError(f'Revisa el enlace del repositorio antes de capturar: {relative}')
    return destination


def read_state(path):
    if not path.exists():
        return None, None
    return path.read_bytes(), path.stat().st_mode & 0o777


def compare(root, staged, selected):
    candidates = {}
    for source in sorted(staged.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(staged).as_posix()
        module = relative.split('/')[1] if relative.startswith('modules/') else 'widgets'
        if module not in selected and relative != 'widget-presets.json':
            continue
        candidates[relative] = source
    # The AI exporter regenerates its whole snapshot, including removed skills.
    if 'ai' in selected and (staged / 'modules/ai/files').is_dir():
        for source in (root / 'modules/ai/files').rglob('*'):
            if source.is_file():
                candidates.setdefault(source.relative_to(root).as_posix(), None)
    changes = []
    for relative, source in sorted(candidates.items()):
        before, old_mode = read_state(safe_path(root, relative))
        after, new_mode = read_state(source) if source else (None, None)
        if (before, old_mode) == (after, new_mode):
            continue
        if after is not None:
            try:
                text = after.decode()
            except UnicodeDecodeError:
                pass
            else:
                if SECRET.search(text):
                    raise ValueError(f'Posible credencial en {relative}; captura detenida')
        changes.append(Change(relative, before, after, old_mode, new_mode))
    return changes


def apply_changes(root, changes, backup_base):
    if not changes:
        return None
    # Compare with the working files, including uncommitted edits, never with HEAD.
    for change in changes:
        if read_state(safe_path(root, change.path)) != (change.before, change.old_mode):
            raise ValueError(f'El repositorio cambió durante la revisión: {change.path}; vuelve a revisar')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    backup = backup_base / stamp
    records = []
    for change in changes:
        if change.before is not None:
            atomic_write(safe_path(backup / 'files', change.path), change.before, change.old_mode)
        records.append({'path': change.path, 'status': change.status, 'old_mode': change.old_mode,
                        'new_mode': change.new_mode,
                        'after_sha256': hashlib.sha256(change.after).hexdigest() if change.after is not None else None})
    atomic_write(backup / 'manifest.json', (json.dumps({'repository': str(root), 'files': records},
                 ensure_ascii=False, indent=2) + '\n').encode(), 0o600)
    written = []
    try:
        for change in changes:
            destination = safe_path(root, change.path)
            if read_state(destination) != (change.before, change.old_mode):
                raise ValueError(f'El archivo cambió durante la captura: {change.path}')
            written.append(change)
            if change.after is None:
                destination.unlink()
            else:
                atomic_write(destination, change.after, change.new_mode)
    except BaseException:
        for change in reversed(written):
            destination = safe_path(root, change.path)
            if change.before is None:
                destination.unlink(missing_ok=True)
            else:
                atomic_write(destination, change.before, change.old_mode)
        raise
    return backup


def show(changes, missing, diff=False):
    if not changes:
        print('Sin cambios portables pendientes.')
    else:
        print(f'{len(changes)} cambios portables: ' + ', '.join(
            f'{name}: {count}' for name, count in sorted(Counter(c.module for c in changes).items())))
        labels = {'added': '+', 'modified': '~', 'deleted': '-'}
        for change in changes:
            print(f'  {labels[change.status]} {change.path}')
            if diff:
                try:
                    before = (change.before or b'').decode().splitlines(keepends=True)
                    after = (change.after or b'').decode().splitlines(keepends=True)
                except UnicodeDecodeError:
                    print('    [archivo binario]')
                else:
                    print(''.join(difflib.unified_diff(before, after, fromfile='repo/' + change.path,
                                                      tofile='master/' + change.path)), end='')
                if change.old_mode != change.new_mode:
                    print(f'    permisos: {change.old_mode!s} → {change.new_mode!s}')
    if missing:
        print(f'{len(missing)} fuentes ausentes: se conserva su copia en el repositorio.')
        for path in missing:
            print('  ' + path)


def run_doctor(home, root, as_json=False):
    import shutil
    import subprocess
    checks = []

    def check(category, name, ok, warn=False, detail='', hint=''):
        status = 'ok' if ok else ('warn' if warn else 'fail')
        checks.append({
            'category': category, 'name': name, 'status': status,
            'detail': detail, 'hint': hint
        })

    # 1. Wayland & Compositor
    w_display = os.environ.get('WAYLAND_DISPLAY')
    check('Compositor', 'WAYLAND_DISPLAY', bool(w_display), detail=w_display or 'No definido')

    wayfire_run = subprocess.run(['pgrep', '-x', 'wayfire'], capture_output=True).returncode == 0
    check('Compositor', 'Wayfire compositor', wayfire_run, detail='En ejecución' if wayfire_run else 'No encontrado')

    runtime_dir = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
    wf_socket_env = os.environ.get('WAYFIRE_SOCKET')
    wf_sockets = [Path(wf_socket_env)] if wf_socket_env and Path(wf_socket_env).exists() else list(runtime_dir.glob('wayfire-*.sock*'))
    check('Compositor', 'Wayfire IPC Socket', bool(wf_sockets), detail=wf_sockets[0].name if wf_sockets else 'No detectado')

    tile_sock = runtime_dir / 'wf-tile/control.sock'
    check('Compositor', 'Servicio wf-tile', tile_sock.exists(), warn=True,
          detail='Socket activo' if tile_sock.exists() else 'Inactivo',
          hint='Inicia con: wf-tile-ctl status')

    # 2. Desktop Daemons
    for proc, label, warn in [
        ('waybar', 'Waybar', False),
        ('swaync', 'SwayNC (notificaciones)', False),
        ('swayosd-server', 'SwayOSD', True),
        ('awww-daemon', 'awww (wallpaper)', True),
    ]:
        running = subprocess.run(['pgrep', '-f', proc], capture_output=True).returncode == 0
        check('Daemons', label, running, warn=warn,
              detail='En ejecución' if running else 'Detenido')

    # 3. Herramientas del Sistema
    for cmd, label, warn in [
        ('kitty', 'Terminal kitty', False),
        ('zsh', 'Shell zsh', False),
        ('starship', 'Prompt starship', False),
        ('fastfetch', 'Fastfetch', False),
        ('matugen', 'Motor de temas matugen', False),
        ('fzf', 'Buscador fzf', True),
        ('zoxide', 'Navegación zoxide', True),
        ('paru', 'AUR helper (paru/yay)', True),
    ]:
        found = bool(shutil.which(cmd))
        if cmd == 'paru' and not found:
            found = bool(shutil.which('yay'))
            cmd = 'yay' if found else 'paru'
        check('Herramientas', label, found, warn=warn,
              detail=shutil.which(cmd) or 'No instalado')

    updater = home / '.local/bin/raccon-update'
    check('Herramientas', 'raccon-update', updater.is_file() and os.access(updater, os.X_OK),
          detail='Presente' if updater.exists() else 'Falta script')

    # Comprobar actualizaciones pendientes usando la caché optimizada
    updates_ok = True
    updates_detail = 'Al día (0 pendientes)'
    if updater.is_file():
        try:
            res = subprocess.run([str(updater), 'count'], capture_output=True, text=True, timeout=2)
            cnt = res.stdout.strip()
            if cnt and cnt.isdigit() and int(cnt) > 0:
                updates_ok = False
                updates_detail = f'{cnt} pendientes (clic en Waybar o raccon-update run)'
        except Exception:
            pass
    check('Herramientas', 'Estado de paquetes', updates_ok, warn=True,
          detail=updates_detail, hint='Actualiza con: raccon-update run')

    # 4. Temas y Paletas
    matugen_cfg = home / '.config/matugen/config.toml'
    check('Temas', 'Configuración Matugen', matugen_cfg.is_file(),
          detail='~/.config/matugen/config.toml')

    ff_cfg = home / '.config/fastfetch/config.jsonc'
    ff_art = home / '.config/fastfetch/raccoon.txt'
    check('Temas', 'Fastfetch tema y mascota', ff_cfg.is_file() and ff_art.is_file(),
          detail='Archivos presentes' if ff_cfg.exists() and ff_art.exists() else 'Incompleto')

    cur_wall = home / '.cache/current-wallpaper'
    wall_ok = cur_wall.is_file() and Path(cur_wall.read_text().strip()).is_file() if cur_wall.is_file() else False
    check('Temas', 'Fondo de pantalla activo', wall_ok, warn=True,
          detail=cur_wall.read_text().strip() if wall_ok else 'No registrado')

    if as_json:
        print(json.dumps({'checks': checks}, indent=2, ensure_ascii=False))
        return 0

    print('\033[1;35m:: Raccon Dots Doctor — Diagnóstico del Sistema\033[0m\n')
    current_cat = None
    ok_count = warn_count = fail_count = 0

    for c in checks:
        if c['category'] != current_cat:
            current_cat = c['category']
            print(f'\033[1m[{current_cat}]\033[0m')
        if c['status'] == 'ok':
            ok_count += 1
            print(f'  \033[32m✓\033[0m {c["name"]}: {c["detail"]}')
        elif c['status'] == 'warn':
            warn_count += 1
            print(f'  \033[33m⚠\033[0m {c["name"]}: {c["detail"]}' + (f' ({c["hint"]})' if c['hint'] else ''))
        else:
            fail_count += 1
            print(f'  \033[31m✗\033[0m {c["name"]}: {c["detail"]}' + (f' ({c["hint"]})' if c['hint'] else ''))

    print(f'\n\033[1mResumen:\033[0m \033[32m{ok_count} correctos\033[0m, '
          f'\033[33m{warn_count} advertencias\033[0m, '
          f'\033[31m{fail_count} errores\033[0m.')
    return 1 if fail_count > 0 else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    doc_cmd = commands.add_parser('doctor', help='Diagnóstico y salud del sistema Raccon Dots')
    doc_cmd.add_argument('--json', action='store_true', help='Salida en JSON')
    for name, help_text in [('master', 'Registrar el HOME del equipo principal'),
                            ('changes', 'Revisar cambios sin modificar el repositorio'),
                            ('capture', 'Traer cambios al repositorio con respaldo')]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument('--from-home', type=Path, help='HOME local o montado de la instancia master')
        if name != 'master':
            command.add_argument('--modules', help='Módulos separados por comas; por defecto todos los exportables')
        if name == 'changes':
            formats = command.add_mutually_exclusive_group()
            formats.add_argument('--diff', action='store_true', help='Mostrar las diferencias de contenido')
            formats.add_argument('--json', action='store_true', help='Salida para scripts')
    args = parser.parse_args(argv)
    config = Path.home() / '.config/raccon-dots/master.json'
    settings = json.loads(config.read_text()) if config.exists() else {}
    default_master = settings.get('home', str(Path.home())) if settings.get('repository') == str(ROOT) else str(Path.home())
    from_home = getattr(args, 'from_home', None)
    master = (from_home or Path(default_master)).expanduser().resolve()
    if not master.is_dir():
        raise ValueError(f'No existe el HOME master: {master}')
    if args.command == 'doctor':
        return run_doctor(master, ROOT, getattr(args, 'json', False))
    if args.command == 'master':
        safe_destination(Path.home(), '.config/raccon-dots/master.json')
        atomic_write(config, (json.dumps({'repository': str(ROOT), 'home': str(master)}, indent=2) + '\n').encode(), 0o600)
        print(f'Master: {master}\nRepositorio: {ROOT}\nRevisa los cambios con: rdot changes')
        return 0
    selected = {name.strip() for name in args.modules.split(',')} if args.modules else set(MODULES)
    if unknown := selected - MODULES:
        raise ValueError('Módulos sin exportador: ' + ', '.join(sorted(unknown)))
    if 'widgets' in selected:
        selected |= WIDGET_MODULES
    with tempfile.TemporaryDirectory(prefix='raccon-master-') as temporary:
        staged = Path(temporary)
        missing = snapshot(master, staged, selected)
        changes = compare(ROOT, staged, selected)
        if args.command == 'changes' and args.json:
            print(json.dumps({'master': str(master), 'repository': str(ROOT), 'missing': missing,
                              'changes': [{'path': c.path, 'module': c.module, 'status': c.status} for c in changes]},
                             ensure_ascii=False, indent=2))
        else:
            show(changes, missing, getattr(args, 'diff', False))
        if args.command == 'capture':
            relative = '.local/state/raccon-dots/master-backups'
            backup_base = safe_destination(Path.home(), relative + '/.check').parent
            backup = apply_changes(ROOT, changes, backup_base)
            if backup:
                print(f'Cambios incorporados. Respaldo: {backup}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        sys.exit(f'rdot: {error}')
