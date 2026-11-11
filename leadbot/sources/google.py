"""Google search restricted to social sites (site:facebook.com "מחפשת צלם" ...).

Public Facebook / Instagram posts that Google has indexed in the last day are the
most reliable way to reach those networks without breaking their terms of use.
"""
from __future__ import annotations

from ..models import Lead, platform_from_url
from .base import Source, log


def build_queries(cfg: dict) -> list[str]:
    phrases = cfg.get("search_phrases", [])
    per = max(1, int(cfg.get("phrases_per_query", 5)))
    chunks = [phrases[i:i + per] for i in range(0, len(phrases), per)]
    queries = []
    for site in cfg.get("search_sites", []):
        for chunk in chunks:
            ors = " OR ".join(f'"{p}"' for p in chunk)
            queries.append(f"site:{site} ({ors})")
    return queries


class Serper(Source):
    """https://serper.dev – 2,500 free searches, then ~$1 per 1,000."""
    name = "serper"
    env_vars = ("SERPER_API_KEY",)
    URL = "https://google.serper.dev/search"

    def fetch(self) -> list[Lead]:
        window = self.global_cfg.get("search_time_window", "d")
        leads = []
        for q in build_queries(self.global_cfg):
            try:
                r = self.http.post(
                    self.URL,
                    headers={"X-API-KEY": self.env("SERPER_API_KEY")},
                    json={"q": q, "gl": "il", "hl": "iw", "tbs": f"qdr:{window}", "num": 20},
                    timeout=30,
                )
                r.raise_for_status()
            except Exception as e:  # keep going with other queries
                log.warning("[serper] %s -> %s", q, e)
                continue
            for item in r.json().get("organic", []):
                url = item.get("link", "")
                leads.append(Lead(
                    source=self.name, platform=platform_from_url(url), url=url,
                    title=item.get("title", ""), text=f'{item.get("title", "")} {item.get("snippet", "")}',
                    published=item.get("date", ""), trusted_match=True,
                ))
        return leads


class GoogleCSE(Source):
    """Google Programmable Search JSON API – 100 free queries/day."""
    name = "google_cse"
    env_vars = ("GOOGLE_API_KEY", "GOOGLE_CSE_ID")
    URL = "https://www.googleapis.com/customsearch/v1"

    def fetch(self) -> list[Lead]:
        window = self.global_cfg.get("search_time_window", "d")
        leads = []
        for q in build_queries(self.global_cfg):
            try:
                r = self.http.get(self.URL, params={
                    "key": self.env("GOOGLE_API_KEY"), "cx": self.env("GOOGLE_CSE_ID"),
                    "q": q, "dateRestrict": f"{window}1", "gl": "il", "num": 10,
                }, timeout=30)
                r.raise_for_status()
            except Exception as e:
                log.warning("[google_cse] %s -> %s", q, e)
                continue
            for item in r.json().get("items", []):
                url = item.get("link", "")
                leads.append(Lead(
                    source=self.name, platform=platform_from_url(url), url=url,
                    title=item.get("title", ""), text=f'{item.get("title", "")} {item.get("snippet", "")}',
                    trusted_match=True,
                ))
        return leads
