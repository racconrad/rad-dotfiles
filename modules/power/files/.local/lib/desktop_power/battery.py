from pathlib import Path


def read_battery(root=Path('/sys/class/power_supply')):
    batteries, sources, statuses = [], [], []
    for path in root.iterdir():
        try:
            kind = (path / 'type').read_text().strip()
            if (path / 'scope').exists() and (path / 'scope').read_text().strip() == 'Device':
                continue  # Mouse/headset batteries must not drive laptop power policy.
            if kind == 'Battery':
                if (path / 'present').exists() and (path / 'present').read_text().strip() == '0':
                    continue
                percent = int((path / 'capacity').read_text())
                if not 0 <= percent <= 100:
                    continue
                batteries.append((path, percent))
                statuses.append((path / 'status').read_text().strip())
            elif (path / 'online').exists():
                sources.append((path / 'online').read_text().strip() == '1')
        except (OSError, ValueError):
            continue
    plugged = any(sources) if sources else (True if 'Charging' in statuses else False if 'Discharging' in statuses else None)
    percent = round(sum(p for _, p in batteries) / len(batteries)) if batteries else None
    if len(batteries) > 1:
        try:
            now = sum(int((p / 'energy_now').read_text()) for p, _ in batteries)
            full = sum(int((p / 'energy_full').read_text()) for p, _ in batteries)
            if full:
                percent = max(0, min(100, round(now / full * 100)))
        except (OSError, ValueError):
            pass
    return {'percent': percent, 'plugged': plugged, 'batteries': len(batteries)}
