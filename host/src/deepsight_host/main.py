"""DeepSight Host — entry point."""

from __future__ import annotations

import sys

from deepsight_host.app import HostApp


def main():
    app = HostApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
