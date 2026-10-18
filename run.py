"""Run CrisisMap directly from a source checkout."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from crisismap.app import main  # noqa: E402

raise SystemExit(main())
