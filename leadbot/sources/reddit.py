from __future__ import annotations

from datetime import datetime, timezone

from ..models import Lead
from .base import Source, log


class Reddit(Source):
    """Reddit public search (no key). Mostly English-speaking posts."""
    name = "reddit"

    def fetch(self) -> list[Lead]:
        leads = []
        for q in self.cfg.get("queries") or []:
            try:
                r = self.http.get("https://www.reddit.com/search.json",
                                  params={"q": q, "sort": "new", "t": "day", "limit": 50},
                                  timeout=30)
                r.raise_for_status()
            except Exception as e:
                log.warning("[reddit] %s -> %s", q, e)
                continue
            for child in r.json().get("data", {}).get("children", []):
                d = child.get("data", {})
                leads.append(Lead(
                    source=self.name, platform="reddit",
                    url="https://www.reddit.com" + d.get("permalink", ""),
                    title=d.get("title", ""),
                    text=f'{d.get("title", "")}\n{d.get("selftext", "")}',
                    author=d.get("author", ""),
                    published=datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).isoformat(),
                ))
        return leads
