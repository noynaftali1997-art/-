"""Delivery: Telegram bot and/or e-mail. Each channel is used only if configured."""
from __future__ import annotations

import html
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

import requests

from .models import Lead
from .sources.base import log

ICONS = {"facebook": "📘", "instagram": "📸", "tiktok": "🎵", "reddit": "👽",
         "x": "✖️", "threads": "🧵", "linkedin": "💼"}


def _snippet(text: str, n: int = 220) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[:n] + "…"


def format_telegram(leads: list[Lead], day: str, limit: int) -> list[str]:
    header = f"📷 <b>לידים לצלם – {day}</b>\nנמצאו {len(leads)} לידים חדשים\n"
    if not leads:
        return [header + "\nאין לידים חדשים היום."]
    blocks = []
    for i, l in enumerate(leads[:limit], 1):
        ev = f" | {html.escape(l.event_type)}" if l.event_type else ""
        blocks.append(
            f"{i}. {ICONS.get(l.platform, '🌐')} <b>{html.escape(l.platform)}</b>{ev} "
            f"(ציון {l.score})\n{html.escape(_snippet(l.text))}\n"
            f'<a href="{html.escape(l.url, quote=True)}">לפוסט</a>'
        )
    if len(leads) > limit:
        blocks.append(f"…ועוד {len(leads) - limit} בקובץ ה-CSV")
    # Telegram limit is 4096 chars per message
    messages, cur = [], header
    for b in blocks:
        if len(cur) + len(b) + 2 > 3900:
            messages.append(cur)
            cur = ""
        cur += "\n" + b + "\n"
    messages.append(cur)
    return messages


def send_telegram(leads: list[Lead], day: str, limit: int, csv_path: Path | None) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        log.info("[telegram] not configured")
        return
    api = f"https://api.telegram.org/bot{token}"
    for msg in format_telegram(leads, day, limit):
        r = requests.post(f"{api}/sendMessage", timeout=30, data={
            "chat_id": chat, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": "true"})
        if not r.ok:
            log.warning("[telegram] %s", r.text[:300])
    if csv_path and leads:
        with csv_path.open("rb") as f:
            requests.post(f"{api}/sendDocument", timeout=60,
                          data={"chat_id": chat}, files={"document": (csv_path.name, f)})
    log.info("[telegram] sent")


def send_email(leads: list[Lead], day: str, csv_path: Path | None) -> None:
    host, to = os.environ.get("SMTP_HOST"), os.environ.get("EMAIL_TO")
    user, pwd = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
    if not (host and to and user and pwd):
        log.info("[email] not configured")
        return
    rows = "".join(
        f"<tr><td>{l.score}</td><td>{html.escape(l.platform)}</td><td>{html.escape(l.event_type)}</td>"
        f"<td>{html.escape(_snippet(l.text, 300))}</td>"
        f'<td><a href="{html.escape(l.url, quote=True)}">קישור</a></td></tr>'
        for l in leads)
    body = (f'<div dir="rtl"><h2>לידים לצלם – {day}</h2><p>נמצאו {len(leads)} לידים חדשים.</p>'
            f'<table border="1" cellpadding="6" style="border-collapse:collapse">'
            f"<tr><th>ציון</th><th>רשת</th><th>סוג</th><th>טקסט</th><th>קישור</th></tr>{rows}</table></div>")
    msg = EmailMessage()
    msg["Subject"] = f"📷 {len(leads)} לידים חדשים לצלם – {day}"
    msg["From"] = os.environ.get("EMAIL_FROM", user)
    msg["To"] = to
    msg.set_content(f"{len(leads)} new leads – see HTML version / attached CSV.")
    msg.add_alternative(body, subtype="html")
    if csv_path and leads:
        msg.add_attachment(csv_path.read_bytes(), maintype="text", subtype="csv", filename=csv_path.name)
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=60) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)
    log.info("[email] sent to %s", to)


def format_whatsapp(leads: list[Lead], day: str, limit: int) -> list[str]:
    """Plain-text messages, kept short (CallMeBot handles ~1,500 chars well)."""
    header = f"📷 לידים לצלם – {day}\nנמצאו {len(leads)} לידים חדשים\n"
    if not leads:
        return [header + "\nאין לידים חדשים היום."]
    blocks = []
    for i, l in enumerate(leads[:limit], 1):
        ev = f" | {l.event_type}" if l.event_type else ""
        blocks.append(f"{i}. {ICONS.get(l.platform, '🌐')} {l.platform}{ev}\n{_snippet(l.text, 160)}\n{l.url}")
    if len(leads) > limit:
        blocks.append(f"…ועוד {len(leads) - limit} לידים")
    messages, cur = [], header
    for b in blocks:
        if len(cur) + len(b) + 2 > 1400:
            messages.append(cur)
            cur = ""
        cur += "\n" + b + "\n"
    messages.append(cur)
    return messages


def send_whatsapp(leads: list[Lead], day: str, limit: int) -> None:
    """WhatsApp to your own phone via CallMeBot (free, personal use)."""
    phone, key = os.environ.get("WHATSAPP_PHONE"), os.environ.get("WHATSAPP_APIKEY")
    if not (phone and key):
        log.info("[whatsapp] not configured")
        return
    import time
    for msg in format_whatsapp(leads, day, limit):
        r = requests.get("https://api.callmebot.com/whatsapp.php", timeout=60,
                         params={"phone": phone, "text": msg, "apikey": key})
        if not r.ok:
            log.warning("[whatsapp] HTTP %s %s", r.status_code, r.text[:200])
        time.sleep(3)  # CallMeBot asks for a gap between messages
    log.info("[whatsapp] sent")
