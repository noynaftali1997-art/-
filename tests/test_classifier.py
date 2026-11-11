import pathlib

import pytest
import yaml

from leadbot.classifier import Classifier
from leadbot.main import filter_leads
from leadbot.models import Lead
from leadbot.sources.google import build_queries
from leadbot.sources.rss import parse_feed

CFG = yaml.safe_load((pathlib.Path(__file__).parent.parent / "config.yaml").read_text(encoding="utf-8"))
clf = Classifier(CFG["classifier"])

LEADS = [
    "היי בנות, מחפשת צלמת לחתונה באוגוסט באזור המרכז, ממליצות?",
    "אני מחפש צלם לבר מצווה של הבן שלי",
    "מישהו מכיר צלם טוב לצילומי משפחה בחיפה?",
    "ממליצים על צלם לאירוע חברה קטן?",
    "צריכה צלמת ניו בורן דחוף בירושלים",
    "דרוש צלם לאירוע יום הולדת 50 בשבוע הבא",
    "חיפוש צלם לתמונות תדמית ללינקדאין",
    "Looking for a photographer for our engagement shoot in Tel Aviv",
    "Can anyone recommend a wedding photographer in Israel?",
    "שלום לכולם! ומחפשים צלם לברית בשבת",
]

NOT_LEADS = [
    "צלם מחפש עבודה באזור המרכז, ניסיון של 5 שנים",
    "דרושים צלמים לחברת הפקות, משרה מלאה, שכר גבוה",
    "מחפשת עבודה כצלמת, יש לי תיק עבודות",
    "דרוש צלם למשרה חלקית בסטודיו, לשלוח קורות חיים",
    "Hiring: full-time photographer, salary $50k",
    "[For Hire] wedding photographer available in Haifa",
    "נשארו תאריכים פנויים לחתונות 2027! צלמת מומלצת",
    "מבצע חבילות צילום לבר מצווה – צלם מקצועי",
    "קורס צילום למתחילים – מחפשים משתתפים",
    "איזה יום יפה היה היום בים",
    "מחפשת מעצבת שיער לחתונה",
]


@pytest.mark.parametrize("text", LEADS)
def test_leads(text):
    v = clf.classify(text)
    assert v.is_lead, (text, v)


@pytest.mark.parametrize("text", NOT_LEADS)
def test_not_leads(text):
    v = clf.classify(text)
    assert not v.is_lead, (text, v)


def test_event_type_detected():
    assert clf.classify("מחפשת צלם לחתונה").event_type == "חתונה"
    assert clf.classify("מחפש צלם לבר מצווה").event_type == "בר/בת מצווה"


def test_trusted_search_snippet_without_intent_word():
    text = "צלם לחתונה בצפון - קבוצת כלות 2027"
    assert not clf.classify(text).is_lead
    assert clf.classify(text, trusted_match=True).is_lead


def test_queries_cover_every_site_and_phrase():
    qs = build_queries(CFG)
    assert any(q.startswith("site:facebook.com") for q in qs)
    assert any(q.startswith("site:instagram.com") for q in qs)
    for p in CFG["search_phrases"]:
        assert any(f'"{p}"' in q for q in qs if q.startswith("site:facebook.com"))


def test_dedupe_by_url():
    raw = [
        Lead("serper", "facebook", "https://www.facebook.com/groups/1/posts/2?ref=x", "מחפשת צלם לחתונה"),
        Lead("google_cse", "facebook", "https://m.facebook.com/groups/1/posts/2/", "מחפשת צלם לחתונה"),
    ]
    assert len(filter_leads(raw, clf)) == 1


def test_google_alerts_rss():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>&lt;b&gt;מחפשת צלם&lt;/b&gt; לחתונה</title>
      <link href="https://www.google.com/url?rct=j&amp;url=https://www.facebook.com/groups/1/posts/9&amp;ct=ga"/>
      <content>מישהו מכיר?</content><updated>2026-11-11T08:00:00Z</updated></entry></feed>"""
    leads = parse_feed(xml)
    assert leads[0].url == "https://www.facebook.com/groups/1/posts/9"
    assert leads[0].platform == "facebook"
    assert len(filter_leads(leads, clf)) == 1
