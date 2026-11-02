"""Σημείωμα προπονητή από το Claude (προαιρετικό).

Κάθε πρωί, αν υπάρχει το secret ANTHROPIC_API_KEY, στέλνει μια σύνοψη των δεδομένων (σημερινή προπόνηση,
ετοιμότητα, φορτίο, πρόσφατα τρεξίματα, αγώνας) και παίρνει πίσω 2–4 προτάσεις σχολίου στα ελληνικά.
Το σημείωμα είναι μόνο κείμενο: ΔΕΝ αλλάζει την προπόνηση. Τις προπονήσεις τις αποφασίζουν οι κανόνες.
Αν κάτι αποτύχει, επιστρέφει None και η ενημέρωση συνεχίζει κανονικά.
"""
from __future__ import annotations

import json
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = (
    "Είσαι έμπειρος προπονητής ορεινού τρεξίματος. Γράφεις ένα σύντομο πρωινό σημείωμα στα ελληνικά, "
    "στον ενικό, προς τον αθλητή. 2 έως 4 προτάσεις, χωρίς επικεφαλίδες, λίστες ή emoji. "
    "Σχολίασε τι σημαίνουν τα σημερινά δεδομένα (ετοιμότητα, φορτίο, πρόσφατα τρεξίματα) για τη σημερινή προπόνηση "
    "και τον στόχο, και δώσε μία πρακτική συμβουλή εκτέλεσης (ρυθμός, τεχνική, διατροφή ή ανάκαμψη). "
    "ΜΗΝ αλλάζεις και μην προτείνεις άλλη προπόνηση από αυτή που δίνεται: έχει ήδη αποφασιστεί από το πρόγραμμα. "
    "Μην επινοείς αριθμούς που δεν υπάρχουν στα δεδομένα. Μην δίνεις ιατρικές διαγνώσεις· αν τα δεδομένα δείχνουν "
    "έντονη κούραση, πες απλά να ακούσει το σώμα του και να ξεκουραστεί αν νιώθει άρρωστος."
)


def _summary(data: dict, today_iso: str) -> dict:
    day = next((d for w in data["plan"] for d in w["days"] if d["date"] == today_iso), None) or {}
    week = next((w for w in data["plan"] if any(d["date"] == today_iso for d in w["days"])), None) or {}
    imp = data.get("impact") or {}
    rd = imp.get("readiness") or {}
    return {
        "σήμερα": today_iso,
        "σημερινή_προπόνηση": {k: day.get(k) for k in ("dow", "title", "desc", "minutes", "gain", "adjust", "adjusted_from") if day.get(k)},
        "εβδομάδα": {"φάση": week.get("label"), "λεπτά": week.get("minutes"), "υψομετρική": week.get("gain"),
                     "υπόλοιπες_μέρες": [f"{d['dow']}: {d['title']}" for d in week.get("days", []) if d["date"] > today_iso]},
        "ετοιμότητα_ρολογιού": data.get("wellness"),
        "φόρμα_κούραση_φρεσκάδα": imp.get("now"),
        "ετοιμότητα_αγώνα": {"σκορ": rd.get("score"), "σκέλη": [f"{p['label']}: {p['value']}" for p in rd.get("parts", [])]},
        "αγώνας": data.get("race"),
        "τελευταία_τρεξίματα": [{k: r.get(k) for k in ("date", "name", "km", "gain", "minutes", "avg_hr")} for r in (data.get("recent") or [])[:7]],
        "προσαρμογές_προγράμματος": (data.get("status") or {}).get("advice"),
    }


def note(data: dict, today_iso: str, api_key: str, model: str | None = None, timeout: int = 40) -> str | None:
    if not api_key:
        return None
    body = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": 400,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": "Δεδομένα σήμερα:\n" + json.dumps(_summary(data, today_iso), ensure_ascii=False, indent=1)}],
    }
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        res = json.loads(r.read().decode("utf-8"))
    text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text").strip()
    return text[:1200] or None
