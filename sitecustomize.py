"""Make the src-layout package importable when running from this folder."""

from pathlib import Path
import sys

SRC = Path(__file__).resolve().parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
