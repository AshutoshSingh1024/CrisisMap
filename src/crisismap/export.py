from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Assessment


def save_assessment(assessment: Assessment, path: str | Path) -> None:
    payload = {
        "application": "CrisisMap",
        "version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notice": "Educational assessment only; not a prediction or emergency warning.",
        "assessment": assessment.to_dict(),
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
