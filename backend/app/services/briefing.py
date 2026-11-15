"""Proactive morning briefing: deterministic facts -> LLM script (Hindi) -> Sarvam TTS -> stored."""
import logging
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import fmt_inr, log, utcnow
from app.models import Briefing, Merchant
from app.services import actions, analytics, growth, inventory, khata, sarvam

logger = logging.getLogger("briefing")
WEEKDAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]


def build_facts(s: Session, mid: int) -> dict[str, Any]:
    y = analytics.yesterday(s, mid)
    risks = inventory.at_risk(s, mid)
    od = sorted(khata.overdue(s, mid), key=lambda e: -e["days_pending"])
    lapsed = growth.lapsed_customers(s, mid)
    return {
        "date": y.date,
        "weekday_idx": (analytics.ist_today() - timedelta(days=1)).weekday(),
        "sales_paise": y.total_paise, "pct_vs_last_week": y.pct_vs_last_week,
        "at_risk": [{"name": r["name"], "days": r["days_of_cover"]} for r in risks[:2]],
        "overdue_count": len(od), "overdue_total_paise": sum(e["amount_paise"] for e in od),
        "top_overdue": {"name": od[0]["name"], "amount_paise": od[0]["amount_paise"], "days": od[0]["days_pending"]} if od else None,
        "lapsed_count": len(lapsed),
        "expiring": [{"name": r["name"], "days": r["days_left"]} for r in inventory.expiring(s, mid, 7) if r["units_at_risk"] > 0][:2],
    }


def fallback_script(f: dict[str, Any], lang: str, owner: str) -> str:
    pct = f["pct_vs_last_week"]
    if lang == "en":
        parts = [f"Good morning {owner}! Yesterday you sold {fmt_inr(f['sales_paise'])}"
                 + (f", {abs(pct):.0f}% {'up' if pct >= 0 else 'down'} on last week." if pct is not None else ".")]
        for r in f["at_risk"][:1]:
            parts.append(f"{r['name']} will run out in about {r['days']:g} days.")
        for r in f.get("expiring", [])[:1]:
            parts.append(f"{r['name']} expires in {r['days']} days; a clearance discount is ready.")
        if f["top_overdue"]:
            t = f["top_overdue"]
            parts.append(f"{t['name']} owes {fmt_inr(t['amount_paise'])} for {t['days']} days. Shall I send reminders?")
        return " ".join(parts)
    wd = WEEKDAYS_HI[(f["weekday_idx"] + 0) % 7]
    parts = [f"सुप्रभात {owner}! कल {fmt_inr(f['sales_paise'])} की बिक्री हुई"
             + (f", पिछले {wd} से {abs(pct):.0f} प्रतिशत {'ज़्यादा' if pct >= 0 else 'कम'}।" if pct is not None else "।")]
    for r in f["at_risk"][:2]:
        parts.append(f"{r['name']} {r['days']:g} दिन में खत्म हो जाएगा।")
    for r in f.get("expiring", [])[:1]:
        parts.append(f"{r['name']} {r['days']} दिन में एक्सपायर होगा, छूट का ऑफर तैयार है।")
    if f["top_overdue"]:
        t = f["top_overdue"]
        parts.append(f"{t['name']} का {fmt_inr(t['amount_paise'])} उधार {t['days']} दिन से बाकी है। कुल {f['overdue_count']} लोगों का उधार पेंडिंग है।")
    if f["lapsed_count"]:
        parts.append(f"{f['lapsed_count']} पुराने ग्राहक एक महीने से नहीं आए।")
    parts.append("रिमाइंडर और ऑर्डर तैयार हैं। मंज़ूरी दूँ?")
    return " ".join(parts)


UP_WORDS = ("ज़्यादा", "ज्यादा", "अधिक", "बढ़", "more", "up", "higher", "जास्त", "அதிக")
DOWN_WORDS = ("कम", "घट", "less", "down", "lower", "குறை")


def _numbers(text: str) -> set[str]:
    import re

    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*\.?\d*", text)}


def validate_script(text: str, f: dict[str, Any]) -> bool:
    """The LLM may phrase the briefing, but every key figure and the up/down direction must be correct."""
    nums = _numbers(text)
    required = {str(round(f["sales_paise"] / 100))}
    if f["overdue_count"]:
        required.add(str(f["overdue_count"]))
    if f["lapsed_count"]:
        required.add(str(f["lapsed_count"]))
    if not required <= nums:
        return False
    pct = f["pct_vs_last_week"]
    if pct is not None:
        pct_s = f"{abs(pct):g}"
        idx = text.find(pct_s)
        if idx < 0:
            return False
        window = text[idx + len(pct_s): idx + len(pct_s) + 60].lower()
        good, bad = (UP_WORDS, DOWN_WORDS) if pct >= 0 else (DOWN_WORDS, UP_WORDS)
        if not any(w in window for w in good) or any(w in window for w in bad):
            return False
    return True


def _oldest_txt(f: dict[str, Any]) -> str:
    t = f.get("top_overdue")
    return f"{t['name']} owes {round(t['amount_paise'] / 100)} rupees for {t['days']} days" if t else "none"


def write_script(f: dict[str, Any], lang: str, owner: str) -> str:
    pct = f["pct_vs_last_week"]
    direction = "UP (more than)" if pct is not None and pct >= 0 else "DOWN (less than)"
    facts_txt = (
        f"Yesterday sales: {round(f['sales_paise'] / 100)} rupees"
        + (f", {abs(pct):g} percent {direction} the same weekday last week. " if pct is not None else ". ")
        + f"At-risk stock: {f['at_risk']}. Near-expiry products (name, days left): {f.get('expiring', [])}. Overdue udhaar: {f['overdue_count']} customers owing {round(f['overdue_total_paise'] / 100)} rupees in total; "
        f"oldest: {_oldest_txt(f)}. Lapsed regular customers: {f['lapsed_count']}."
    )
    system = ("You write a 30-second spoken morning briefing for a small shopkeeper, from Munim AI. "
              "Use ONLY the facts given; never change a number or the up/down direction. "
              "Write ALL numbers as digits (for example 21473 or 8.9), never as words. "
              "Right after the percentage say clearly whether sales are more or less than last week. "
              "Max 5 short sentences, plain speakable text, no markdown or emojis. "
              f"Language: {sarvam_lang_name(lang)}. Mention stock alert, near-expiry products, udhaar, and lapsed customers if present. "
              "End by asking if they want to approve the prepared reminders and reorder.")
    try:
        text = sarvam.complete(system, f"Merchant name: {owner}\nFacts: {facts_txt}", None, 900)
        if len(text) > 40 and validate_script(text, f):
            return text
        logger.warning("briefing script failed validation; using deterministic script")
    except Exception:  # noqa: BLE001
        logger.warning("briefing LLM unavailable; using deterministic script")
    return fallback_script(f, lang, owner)


def sarvam_lang_name(lang: str) -> str:
    return {"hi": "simple Hindi in Devanagari", "mr": "simple Marathi in Devanagari", "ta": "simple Tamil", "en": "simple English"}.get(lang, "simple Hindi")


def _today_briefing(s: Session, mid: int, lang: str) -> Briefing | None:
    day_start = utcnow() - timedelta(hours=20)
    return s.scalar(select(Briefing).where(Briefing.merchant_id == mid, Briefing.language == lang, Briefing.created_at >= day_start)
                    .order_by(Briefing.id.desc()))


def generate(s: Session, mid: int, lang: str | None = None, force: bool = False) -> Briefing:
    m = s.get(Merchant, mid)
    assert m is not None
    lang = lang or m.language
    if not force and (b := _today_briefing(s, mid, lang)):
        return b
    facts = build_facts(s, mid)
    # prepare the approvable actions the briefing will talk about
    actions.propose_khata_reminders(s, mid)
    actions.propose_reorders(s, mid)
    actions.propose_winback(s, mid)
    actions.propose_clearance(s, mid)
    text = write_script(facts, lang, m.owner_name)
    b = Briefing(merchant_id=mid, language=lang, text=text, facts=facts)
    s.add(b)
    s.flush()
    try:
        fname = f"briefing_{b.id}_{secrets.token_hex(4)}.mp3"
        sarvam.synthesize(text, lang, get_settings().audio_dir / fname)
        b.audio_file = fname
    except Exception as exc:  # noqa: BLE001
        logger.warning("briefing audio unavailable: %s", exc)
    log(logger, "briefing generated", merchant_id=mid, language=lang, has_audio=bool(b.audio_file))
    return b
