"""Gnomecaster desktop app: the window, the tray icon and the companion in one program.
This is the entry point the Windows build packages (build/gnomecaster.spec)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from gnomecaster.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
