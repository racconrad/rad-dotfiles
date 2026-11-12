import argparse
import sys

from wayfire_config import config_home, sync
from wayfire_config.watch import watch


def main():
    parser = argparse.ArgumentParser(description='Compose Raccon and user Wayfire configuration.')
    parser.add_argument('action', choices=('sync', 'watch'), nargs='?', default='sync')
    args = parser.parse_args()
    try:
        if args.action == 'watch':
            watch(config_home())
        else:
            sync(config_home())
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
