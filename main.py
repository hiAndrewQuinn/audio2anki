#!/usr/bin/env python3
"""Backward-compat shim. Prefer `uv run audio2anki` or installed `audio2anki`."""

from audio2anki.cli import main

if __name__ == "__main__":
    main()
