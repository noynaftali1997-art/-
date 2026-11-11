"""Entry point:  python -m leadbot  [--config config.yaml] [--dry-run]"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

from .classifier import Classifier
from .models import Lead
from .notify import send_email, send_telegram
from .sources import ALL_SOURCES
from .storage import SeenStore, write_csv

log = logging.getLogger("leadbot")


def collect(cfg: dict) -> list[Lead]:
    raw: list[Lead] = []
    for name, cls in ALL_SOURCES.items():
        scfg = (cfg.get("sources") or {}).get(name) or {}
        if not scfg.get("enabled", False):
            continue
        src = cls(scfg, cfg)
        if not src.is_configured():
            continue
        try:
            found = src.fetch()
        except Exception as e:  # one broken source must not kill the run
            log.exception("[%s] crashed: %s", name, e)
            continue
        log.info("[%s] %d raw results", name, len(found))
        raw.extend(found)
    return raw


def filter_leads(raw: list[Lead], clf: Classifier, seen: SeenStore | None = None) -> list[Lead]:
    out, keys = [], set()
    for lead in raw:
        if not lead.url and not lead.text:
            continue
        k = lead.key
        if k in keys or (seen is not None and k in seen):
            continue
        v = clf.classify(f"{lead.title} {lead.text}", trusted_match=lead.trusted_match)
        if not v.is_lead:
            log.debug("drop %s %s", lead.url, v.reasons)
            continue
        lead.score, lead.event_type, lead.reasons = v.score, v.event_type, v.reasons
        keys.add(k)
        out.append(lead)
    out.sort(key=lambda l: (-l.score, l.platform not in ("facebook", "instagram")))
    return out


def run(config_path: str = "config.yaml", dry_run: bool = False) -> list[Lead]:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    today = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Jerusalem"))).date()
    clf = Classifier(cfg.get("classifier") or {})
    seen = SeenStore(cfg.get("seen_file", "data/seen.json"), int(cfg.get("seen_retention_days", 90)))

    leads = filter_leads(collect(cfg), clf, seen)
    log.info("✅ %d new leads", len(leads))
    csv_path = write_csv(leads, cfg.get("output_dir", "output"), today)
    log.info("CSV: %s", csv_path)
    if dry_run:
        for l in leads:
            print(f"[{l.score}] {l.platform:9} {l.event_type:12} {l.url}\n     {l.text[:160]}")
        return leads

    limit = int(cfg.get("max_leads_in_message", 30))
    for sender in (lambda: send_telegram(leads, today.isoformat(), limit, csv_path),
                   lambda: send_email(leads, today.isoformat(), csv_path)):
        try:
            sender()
        except Exception as e:
            log.exception("notification failed: %s", e)
    for l in leads:
        seen.add(l.key, today)
    seen.save(today)
    return leads


def cli() -> None:
    p = argparse.ArgumentParser(description="Find people looking for a photographer")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--dry-run", action="store_true", help="print leads, don't notify or mark as seen")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    run(a.config, a.dry_run)


if __name__ == "__main__":
    cli()
