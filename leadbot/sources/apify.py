"""Apify actors – read public Facebook groups and Instagram hashtags directly.

https://apify.com – free plan gives ~$5 of monthly credit, enough for a few groups/day.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import Lead
from .base import Source, log

RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def _first(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if isinstance(v, dict):
            v = v.get("name") or v.get("username") or ""
        if v:
            return v
    return default


def _is_recent(ts: str, days: int = 2) -> bool:
    if not ts:
        return True
    try:
        if str(ts).isdigit():
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(days=days)
    except ValueError:
        return True


class _ApifySource(Source):
    env_vars = ("APIFY_TOKEN",)
    actor = ""

    def run_actor(self, payload: dict) -> list[dict]:
        actor = self.cfg.get("actor", self.actor)
        try:
            r = self.http.post(
                RUN_URL.format(actor=actor),
                params={"token": self.env("APIFY_TOKEN")},
                json=payload, timeout=600,
            )
            r.raise_for_status()
            return r.json() or []
        except Exception as e:
            log.warning("[%s] actor %s failed: %s", self.name, actor, e)
            return []


class ApifyFacebookGroups(_ApifySource):
    name = "apify_facebook_groups"
    actor = "apify~facebook-groups-scraper"

    def fetch(self) -> list[Lead]:
        groups = self.cfg.get("groups") or []
        if not groups:
            log.info("[%s] no groups configured in config.yaml", self.name)
            return []
        items = self.run_actor({
            "startUrls": [{"url": g} for g in groups],
            "resultsLimit": int(self.cfg.get("results_per_group", 40)),
            "viewOption": "CHRONOLOGICAL",
        })
        leads = []
        for it in items:
            ts = _first(it, "time", "timestamp", "date")
            if not _is_recent(ts):
                continue
            leads.append(Lead(
                source=self.name, platform="facebook",
                url=_first(it, "url", "postUrl", "facebookUrl"),
                text=_first(it, "text", "message", "postText"),
                title=_first(it, "groupTitle", "groupName"),
                author=_first(it, "user", "authorName", "author"),
                published=str(ts),
            ))
        return leads


class ApifyInstagramHashtags(_ApifySource):
    name = "apify_instagram_hashtags"
    actor = "apify~instagram-hashtag-scraper"

    def fetch(self) -> list[Lead]:
        tags = [t.lstrip("#") for t in (self.cfg.get("hashtags") or [])]
        if not tags:
            return []
        items = self.run_actor({
            "hashtags": tags,
            "resultsLimit": int(self.cfg.get("results_per_hashtag", 30)),
            "resultsType": "posts",
        })
        leads = []
        for it in items:
            ts = _first(it, "timestamp", "takenAt")
            if not _is_recent(ts):
                continue
            leads.append(Lead(
                source=self.name, platform="instagram",
                url=_first(it, "url"),
                text=_first(it, "caption", "text"),
                author=_first(it, "ownerUsername", "ownerFullName"),
                published=str(ts),
            ))
        return leads
