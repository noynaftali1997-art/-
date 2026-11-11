"""Generic RSS/Atom – works with Google Alerts ("Deliver to: RSS feed") and rss.app
(which can turn Facebook groups / Instagram profiles into feeds)."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

from ..models import Lead, platform_from_url
from .base import Source, log

_TAG_RE = re.compile(r"<[^>]+>")
ATOM = "{http://www.w3.org/2005/Atom}"


def _clean(s: str | None) -> str:
    return html.unescape(_TAG_RE.sub(" ", s or "")).strip()


def _real_url(url: str) -> str:
    # Google Alerts wraps links: https://www.google.com/url?...&url=REAL&...
    m = re.search(r"[?&]url=([^&]+)", url or "")
    if m and "google." in url:
        from urllib.parse import unquote
        return unquote(m.group(1))
    return url


def parse_feed(xml_text: str, source: str = "rss") -> list[Lead]:
    root = ET.fromstring(xml_text)
    leads = []
    for it in root.iter("item"):
        url = _real_url(it.findtext("link") or "")
        title = _clean(it.findtext("title"))
        leads.append(Lead(source=source, platform=platform_from_url(url), url=url, title=title,
                          text=f"{title} {_clean(it.findtext('description'))}",
                          published=it.findtext("pubDate") or ""))
    for e in root.iter(f"{ATOM}entry"):
        link = e.find(f"{ATOM}link")
        url = _real_url(link.get("href", "") if link is not None else "")
        title = _clean(e.findtext(f"{ATOM}title"))
        body = _clean(e.findtext(f"{ATOM}content") or e.findtext(f"{ATOM}summary"))
        leads.append(Lead(source=source, platform=platform_from_url(url), url=url, title=title,
                          text=f"{title} {body}",
                          published=e.findtext(f"{ATOM}updated") or e.findtext(f"{ATOM}published") or ""))
    return leads


class RSS(Source):
    name = "rss"

    def fetch(self) -> list[Lead]:
        leads = []
        for feed in self.cfg.get("feeds") or []:
            try:
                r = self.http.get(feed, timeout=30)
                r.raise_for_status()
                leads.extend(parse_feed(r.text, self.name))
            except Exception as e:
                log.warning("[rss] %s -> %s", feed, e)
        return leads
