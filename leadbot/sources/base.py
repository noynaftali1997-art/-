from __future__ import annotations

import logging
import os

import requests

from ..models import Lead

log = logging.getLogger("leadbot")
USER_AGENT = "Mozilla/5.0 (compatible; leadbot/1.0)"


class Source:
    name = "base"
    env_vars: tuple[str, ...] = ()

    def __init__(self, cfg: dict, global_cfg: dict):
        self.cfg = cfg or {}
        self.global_cfg = global_cfg
        self.http = requests.Session()
        self.http.headers["User-Agent"] = USER_AGENT

    def env(self, name: str) -> str:
        return os.environ.get(name, "").strip()

    def is_configured(self) -> bool:
        missing = [v for v in self.env_vars if not self.env(v)]
        if missing:
            log.info("[%s] skipped – missing env: %s", self.name, ", ".join(missing))
            return False
        return True

    def fetch(self) -> list[Lead]:
        raise NotImplementedError
