"""Entry point: python -m deepsight_tools.emu_console"""

from deepsight_tools.emu_console.app import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
