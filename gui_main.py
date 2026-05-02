"""Entry point used by `flet build` to package the desktop GUI.

Flet's packager looks for a top-level module (default `main.py`) in the app
directory. The existing `main.py` shim runs the CLI, so this separate file
exists purely so the bundled Windows/macOS/Linux GUI app boots into the GUI.
"""

from audio2anki.gui import main

if __name__ == "__main__":
    main()
