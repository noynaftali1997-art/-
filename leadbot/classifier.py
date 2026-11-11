"""Decides whether a piece of text is someone looking to hire a photographer.

Rules (all configurable in config.yaml -> classifier):
  * an "intent" word (מחפשת / צריך / ממליצים / looking ...) must appear within
    ``max_distance`` words of a "photographer" word (צלם / צלמת / photographer ...)
  * any job-hunting / hiring phrase disqualifies the text
  * any self-promotion phrase (photographers advertising) disqualifies the text
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Hebrew one-letter prefixes: ו ה ל ב ש כ מ  (e.g. "לצלם", "והצלמת", "שמחפשת")
HEB_PREFIXES = "והלבשכמ"
_TOKEN_RE = re.compile(r"[\w\"'״׳-]+", re.UNICODE)
_NIQQUD_RE = re.compile(r"[֑-ׇ]")


def normalize(text: str) -> str:
    text = text or ""
    text = _NIQQUD_RE.sub("", text)
    text = text.replace("״", '"').replace("׳", "'").replace("“", '"').replace("”", '"')
    text = text.replace("‏", " ").replace("‎", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_hebrew(s: str) -> bool:
    return any("֐" <= ch <= "׿" for ch in s)


def _phrase_regex(phrase: str) -> re.Pattern:
    phrase = normalize(phrase)
    body = re.escape(phrase).replace(r"\ ", r"\s+")
    prefix = f"[{HEB_PREFIXES}]{{0,3}}" if _is_hebrew(phrase) else ""
    return re.compile(rf"(?<![\w]){prefix}{body}(?![\w])", re.UNICODE)


def _token_in(token: str, vocab: set[str]) -> bool:
    if token in vocab:
        return True
    t = token
    for _ in range(3):
        if len(t) > 2 and t[0] in HEB_PREFIXES:
            t = t[1:]
            if t in vocab:
                return True
        else:
            break
    return False


@dataclass
class Verdict:
    is_lead: bool
    score: int = 0
    event_type: str = ""
    reasons: list[str] = field(default_factory=list)


class Classifier:
    def __init__(self, cfg: dict):
        self.intent = {normalize(w) for w in cfg.get("intent_words", [])}
        self.photo = {normalize(w) for w in cfg.get("photographer_words", [])}
        self.max_distance = int(cfg.get("max_distance", 5))
        self.min_score = int(cfg.get("min_score", 1))
        self.job_rx = [(p, _phrase_regex(p)) for p in cfg.get("job_exclusions", [])]
        self.promo_rx = [(p, _phrase_regex(p)) for p in cfg.get("promo_exclusions", [])]
        self.events = {
            name: [_phrase_regex(k) for k in kws]
            for name, kws in (cfg.get("event_types") or {}).items()
        }

    def _first_hit(self, text: str, rules) -> str | None:
        for phrase, rx in rules:
            if rx.search(text):
                return phrase
        return None

    def classify(self, text: str, trusted_match: bool = False) -> Verdict:
        """``trusted_match``: the search engine already guaranteed one of our exact
        phrases appears in the page, so a short snippet without it is still OK."""
        norm = normalize(text)
        if not norm:
            return Verdict(False, reasons=["empty"])

        hit = self._first_hit(norm, self.job_rx)
        if hit:
            return Verdict(False, reasons=[f"job:{hit}"])
        hit = self._first_hit(norm, self.promo_rx)
        if hit:
            return Verdict(False, reasons=[f"promo:{hit}"])

        tokens = [t.strip("\"'-") for t in _TOKEN_RE.findall(norm)]
        intent_idx = [i for i, t in enumerate(tokens) if _token_in(t, self.intent)]
        photo_idx = [i for i, t in enumerate(tokens) if _token_in(t, self.photo)]

        score, reasons = 0, []
        pairs = [(i, j) for i in intent_idx for j in photo_idx if abs(i - j) <= self.max_distance]
        if pairs:
            score += 2
            reasons.append("intent+photographer")
            if any(i < j for i, j in pairs):
                score += 1  # "מחפשת צלם" is a stronger signal than "צלם מומלץ"
        elif trusted_match and photo_idx:
            score += 1
            reasons.append("search-phrase")
        else:
            return Verdict(False, reasons=["no-intent"])

        event = ""
        for name, rxs in self.events.items():
            if any(rx.search(norm) for rx in rxs):
                event = name
                score += 1
                break
        if "?" in norm:
            score += 1
            reasons.append("question")

        return Verdict(score >= self.min_score, score, event, reasons)
