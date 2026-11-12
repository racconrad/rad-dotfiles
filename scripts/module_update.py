"""Refresh explicitly selected module files without replacing the saved setup."""
import sys

import install
from terminal_ui import Terminal


def pick_modules(installed, plain=False):
    modules = sorted(set(installed) & set(install.CATALOG["modules"]))
    if not modules:
        raise ValueError("No installed modules are recorded in the receipt.")
    chosen, cursor = set(), 0
    with Terminal(plain=plain) as ui:
        while True:
            ui.render(version=install.RELEASE["version"], page="UPDATE INSTALLED MODULES", tabs=[],
                      rows=[{"label": name, "mark": "x" if name in chosen else " "} for name in modules],
                      cursor=cursor, details=["Choose installed modules to refresh.",
                      "Numbers / Space select. v reviews changed files. q cancels.",
                      "No packages, setup or saved preferences will change."],
                      summary=f"{len(chosen)} selected", notice="")
            action = ui.read()
            if action == "q":
                return []
            if action in ("up", "down"):
                cursor = max(0, min(len(modules) - 1, cursor + (1 if action == "down" else -1)))
            elif action in ("v", "i") and chosen:
                return sorted(chosen)
            elif action == "toggle" or (action.isdigit() and 1 <= int(action) <= len(modules)):
                name = modules[cursor if action == "toggle" else int(action) - 1]
                if name in chosen:
                    chosen.remove(name)
                else:
                    chosen.add(name)


def inspect_plan(home, plan, receipt):
    baseline, conflicts = {}, []
    for relative, value in plan.items():
        path = install.safe_destination(home, relative)
        baseline[relative] = install.digest(path)
        if install.unchanged(path, *value):
            continue
        print(f"  {'add' if baseline[relative] == 'missing' else 'replace'} {relative}")
        previous = receipt.get("files", {}).get(relative, {})
        expected = str(previous.get("sha256", "")) + ":" + oct(previous.get("mode", 0))
        if baseline[relative] != "missing" and baseline[relative] != expected:
            conflicts.append(relative)
    baseline[".rdot"] = install.digest(install.safe_destination(home, ".rdot"))
    return baseline, conflicts


def run(args):
    incompatible = (args.restore, args.profile, args.save_profile, args.packages is not None,
                    args.setup, args.extra_packages, args.tinywidgets_source, args.widget_profile,
                    args.widget_theme, args.widget_motion, args.widget_install, args.widget_components,
                    args.list, *(getattr(args, key) for key in install.CATALOG['choices']))
    if any(value is not None and value is not False for value in incompatible):
        raise ValueError('--update cannot change packages, setup, profiles or alternatives.')
    receipt_baseline = install.digest(install.safe_destination(args.target, '.rdot'))
    receipt = install.read_receipt(args.target)
    installed = receipt.get('modules', [])
    if not args.modules or not args.modules.strip():
        if not sys.stdin.isatty():
            raise ValueError('--update requires --modules outside an interactive terminal.')
        modules = pick_modules(installed, getattr(args, 'plain', False))
        if not modules:
            return 0
    else:
        modules = list(dict.fromkeys(name.strip() for name in args.modules.split(',')))
    unknown = set(modules) - set(install.CATALOG['modules'])
    if unknown:
        raise ValueError('Unknown modules: ' + ', '.join(sorted(unknown)))
    missing = set(modules) - set(installed)
    if missing:
        raise ValueError('Modules are not installed: ' + ', '.join(sorted(missing)))
    selection = install.load_selection(args.target)
    choices = selection['choices']
    plan = install.file_plan(args.target, modules, choices, selection, render_modules=installed)
    install.preview(args.target, modules, choices, plan, args.files)
    print('Changed files:')
    baseline, conflicts = inspect_plan(args.target, plan, receipt)
    baseline['.rdot'] = receipt_baseline
    if conflicts:
        print('Locally modified or untracked files: ' + ', '.join(conflicts))
    if args.dry_run or args.check:
        print('Preview only: no files written, packages installed or app setup executed.')
        return 0
    if conflicts and not getattr(args, 'force_update', False):
        raise ValueError('Refusing to overwrite locally modified files; review them or use --force-update with backups.')
    if not args.yes:
        if not sys.stdin.isatty():
            raise ValueError('Use --yes to update or --dry-run to preview.')
        if input('Update these module files and back up existing files? [y/N]: ').lower() != 'y':
            return 0
    install.apply_plan(args.target, plan, modules, choices, partial=True, expected=baseline)
    return 0
