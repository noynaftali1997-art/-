from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field


@dataclass
class Lead:
    source: str              # serper / google_cse / apify_facebook_groups / ...
    platform: str            # facebook / instagram / reddit / ...
    url: str
    text: str
    title: str = ""
    author: str = ""
    published: str = ""      # ISO date/time when known
    trusted_match: bool = False  # came from an exact-phrase search query
    score: int = 0
    event_type: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Stable id for de-duplication (URL without tracking params)."""
        url = re.sub(r"[?#].*$", "", self.url or "").rstrip("/").lower()
        url = url.replace("://m.", "://www.").replace("://web.", "://www.")
        basis = url or (self.text or "")[:300]
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]

    def to_row(self) -> dict:
        d = asdict(self)
        d.pop("trusted_match")
        d["reasons"] = ",".join(self.reasons)
        d["text"] = re.sub(r"\s+", " ", self.text or "")[:1000]
        return d


def platform_from_url(url: str) -> str:
    u = (url or "").lower()
    for name, needle in [
        ("facebook", "facebook.com"), ("facebook", "fb.com"), ("instagram", "instagram.com"),
        ("tiktok", "tiktok.com"), ("threads", "threads.net"), ("x", "x.com/"),
        ("x", "twitter.com"), ("reddit", "reddit.com"), ("linkedin", "linkedin.com"),
    ]:
        if needle in u:
            return name
    return "web"
