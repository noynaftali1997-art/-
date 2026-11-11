from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

from .models import Lead

FIELDS = ["score", "event_type", "platform", "source", "url", "title", "author",
          "published", "text", "reasons"]


class SeenStore:
    """Remembers lead hashes so the same post is never reported twice."""

    def __init__(self, path: str, retention_days: int = 90):
        self.path = Path(path)
        self.retention = retention_days
        self.data: dict[str, str] = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def add(self, key: str, today: date) -> None:
        self.data[key] = today.isoformat()

    def save(self, today: date) -> None:
        cutoff = (today - timedelta(days=self.retention)).isoformat()
        self.data = {k: v for k, v in self.data.items() if v >= cutoff}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=0, sort_keys=True), encoding="utf-8")


def write_csv(leads: list[Lead], out_dir: str, today: date) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"leads-{today.isoformat()}.csv"
    # utf-8-sig so Excel shows Hebrew correctly
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for lead in leads:
            w.writerow(lead.to_row())
    return path
