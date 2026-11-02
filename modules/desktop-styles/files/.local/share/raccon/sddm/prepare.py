#!/usr/bin/env python3
"""Prepare a self-contained SDDM theme from the active Raccon appearance."""
import argparse
import configparser
import json
from pathlib import Path
import re
import shutil
import subprocess


def prepare(home, output, background='solid'):
    source = Path(__file__).resolve().parent / 'raccon'
    if output.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(output.resolve()):
        raise ValueError('Output must be separate from the source theme')
    output.mkdir(parents=True, exist_ok=True)
    for path in source.rglob('*'):
        if path.is_file():
            target = output / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(source / 'theme.conf')
    values = parser['General']
    try:
        tokens = json.loads((home / '.config/desktop-style/current/tokens.json').read_text())
    except (OSError, ValueError):
        tokens = {}
    colors = tokens.get('colors', {})
    roles = dict(background='background', surface='surface_container', field='surface_container_high',
                 foreground='on_surface', muted='on_surface_variant', accent='primary',
                 onAccent='on_primary', outline='outline_variant', error='error')
    for key, role in roles.items():
        color = colors.get(role, '')
        if re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            values[key] = color
    values['font'] = tokens.get('font', values['font'])
    values['radius'] = str(max(0, min(32, int(tokens.get('radius', 14)))))
    values['border'] = str(max(0, min(3, int(tokens.get('border', 1)))))
    values['animations'] = str(not tokens.get('strict', False)).lower()
    # A font in HOME is invisible to the greeter; bundle it and its license.
    match = subprocess.run(['fc-match', '-f', '%{file}', values['font']], capture_output=True, text=True, check=True)
    font = Path(match.stdout.strip())
    if font.is_file():
        target = output / 'assets' / ('font' + font.suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(font, target)
        values['fontFile'] = str(target.relative_to(output))
        for filename in ('OFL.txt', 'LICENSE', 'LICENSE.txt', 'COPYING'):
            license_file = font.parent / filename
            if license_file.is_file():
                shutil.copyfile(license_file, output / 'assets' / filename)
    values['wallpaper'] = ''
    if background == 'wallpaper':
        current = home / '.cache/current-wallpaper'
        image = Path(current.read_text().strip()) if current.is_file() else Path('/nonexistent')
        if image.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp', '.bmp'):
            image = home / '.cache/wallpaper-frame.png'
        if not image.is_file():
            raise ValueError('No readable wallpaper still image is available')
        target = output / 'assets' / ('wallpaper' + image.suffix.lower())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image, target)
        values['wallpaper'] = str(target.relative_to(output))
    # The user's requested solid appearance never includes a wallpaper snapshot.
    else:
        for old in (output / 'assets').glob('wallpaper.*'):
            old.unlink()
    for icon in (output / 'icons').glob('*.svg'):
        svg = re.sub(r'#[0-9a-fA-F]{6}', values['foreground'], icon.read_text())
        icon.write_text(svg)
    with (output / 'theme.conf').open('w') as stream:
        parser.write(stream, space_around_delimiters=False)
    # SDDM runs as its own user. No asset may inherit a private umask.
    for path in [output, *output.rglob('*')]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--output', type=Path, default=Path.home() / '.local/share/sddm/themes/raccon')
    parser.add_argument('--background', choices=('solid', 'wallpaper'), default='solid')
    args = parser.parse_args()
    print(prepare(args.home, args.output, args.background))


if __name__ == '__main__':
    main()
