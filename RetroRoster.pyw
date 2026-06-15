#!/usr/bin/env pythonw
"""Double-clickable Windows launcher for the RETRO ROSTER GUI.

A ``.pyw`` file opens with ``pythonw`` on Windows, so it brings up the graphical
board with no console window.  (On macOS/Linux you can run it with ``python3``.)
"""

import os
import sys

# Make sure the bundled ``retro`` package is importable no matter where this is
# launched from (e.g. double-clicked from Explorer).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retro.gui import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
