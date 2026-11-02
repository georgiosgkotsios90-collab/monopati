#!/usr/bin/env python3
"""Καθημερινή ενημέρωση: τραβά δεδομένα από τη Garmin, φτιάχνει πρόγραμμα, το κρυπτογραφεί.

Μεταβλητές περιβάλλοντος (στο GitHub: Settings → Secrets):
    GARMIN_EMAIL, GARMIN_PASSWORD   στοιχεία Garmin Connect
    APP_PASSWORD                    κωδικός της εφαρμογής (τουλάχιστον 10 χαρακτήρες)
    NTFY_TOPIC                      προαιρετικό: θέμα ntfy.sh για ειδοποιήσεις στο κινητό
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import random
import sys
import traceback
import unicodedata
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

sys.path.insert(0, str(Path(__file__).resolve().parent))
import impact  # noqa: E402
import readiness  # noqa: E402
import planner  # noqa: E402

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Athens")
PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LEN = 10


def encrypt(plain: bytes, password: str) -> dict:
    """AES-256-GCM με κλειδί από PBKDF2-SHA256. Αποκρυπτογραφείται στο κινητό με WebCrypto."""
    password = unicodedata.normalize("NFC", password)
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=PBKDF2_ITERATIONS).derive(password.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, plain, None)  # ciphertext + tag
    b64 = lambda x: base64.b64encode(x).decode("ascii")  # noqa: E731
    return {"v": 1, "iter": PBKDF2_ITERATIONS, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def notify(topic: str | None, title: str, message: str, priority: int = 3) -> None:
    if not topic:
        return
    body = json.dumps({"topic": topic, "title": title, "message": message,
                       "priority": priority, "tags": ["running_shoe"]}).encode("utf-8")
    req = urllib.request.Request("https://ntfy.sh/", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:  # οι ειδοποιήσεις δεν πρέπει να χαλούν την ενημέρωση
        print(f"[ntfy] απέτυχε: {e}", file=sys.stderr)


def demo_data(today):
    """Ψεύτικα δεδομένα για δοκιμή χωρίς Garmin."""
    rnd = random.Random(7)
    sessions = [(1, 8, 150, "running"), (2, 9, 350, "trail_running"), (3, 7, 100, "running"),
                (5, 16, 700, "trail_running"), (6, 10, 250, "trail_running")]
    acts = []
    for w in range(0, 17):
        wk = planner.monday_of(today) - timedelta(weeks=w)
        scale = 0.6 + 0.03 * (16 - w)
        for dow, km, gain, typ in sessions:
            d = wk + timedelta(days=dow)
            if d >= today or rnd.random() < 0.1:
                continue
            k = round(km * scale * rnd.uniform(0.92, 1.08), 1)
            g = int(gain * scale * rnd.uniform(0.9, 1.1))
            acts.append({"date": d.isoformat(), "type": typ, "name": "Δοκιμαστικό τρέξιμο",
                         "km": k, "gain": g, "loss": int(g * rnd.uniform(0.9, 1.05)), "minutes": round(planner.effort(k, g) * 6.6, 1),
                         "avg_hr": rnd.randint(138, 158)})
        cd = wk + timedelta(days=3)
        if cd < today and w % 2 == 0:
            acts.append({"date": cd.isoformat(), "type": "cycling", "name": "Ποδήλατο", "km": 25.0,
                         "gain": 200, "loss": 200, "minutes": 60.0, "avg_hr": 125})
    wellness = {"readiness": 62, "sleep_score": 78, "resting_hr": 49, "hrv": 61, "hrv_status": "BALANCED"}
    return acts, wellness


def morning_message(plan: list[dict], today) -> tuple[str, str] | None:
    for w in plan:
        for d in w["days"]:
            if d["date"] == today.isoformat():
                if d["km"] <= 0:
                    return f"Σήμερα: {d['title']}", d["desc"]
                h, m = divmod(d["minutes"], 60)
                dur = f"{h}ω {m:02d}λ" if h else f"{m} λεπτά"
                return f"Σήμερα: {d['title']}", f"{dur} · +{d['gain']} m"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="ψεύτικα δεδομένα, χωρίς σύνδεση στη Garmin")
    ap.add_argument("--out", default=str(ROOT / "data.enc"))
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    password = os.environ.get("APP_PASSWORD", "")
    topic = None if args.no_notify else os.environ.get("NTFY_TOPIC")
    now = datetime.now(TZ)
    today = now.date()

    try:
        if not args.demo and len(password) < MIN_PASSWORD_LEN:
            raise SystemExit(f"Το APP_PASSWORD πρέπει να έχει τουλάχιστον {MIN_PASSWORD_LEN} χαρακτήρες "
                             "(τα κρυπτογραφημένα δεδομένα είναι δημόσια, οπότε ο κωδικός είναι η μόνη προστασία).")
        api = None
        if args.demo:
            acts, wellness = demo_data(today)
            password = password or "demo-password"
        else:
            import garmin_source
            email, gpw = os.environ.get("GARMIN_EMAIL"), os.environ.get("GARMIN_PASSWORD")
            if not email or not gpw:
                raise SystemExit("Λείπουν τα GARMIN_EMAIL / GARMIN_PASSWORD.")
            api = garmin_source.login(email, gpw)
            acts, wellness = garmin_source.fetch(email, gpw, today, api=api)

        profile = planner.build_profile(acts, today)
        status = planner.build_status(acts, profile, today, wellness)
        plan = planner.build_plan(profile, cfg, today, status, acts)

        # Πρωινός έλεγχος ετοιμότητας (HRV, ύπνος, παλμοί ηρεμίας): αλλάζει τη σημερινή προπόνηση αν χρειάζεται.
        adj = readiness.adjust_today(plan, today.isoformat(), wellness, int(cfg.get("lthr") or 155))
        if adj:
            status["advice"].insert(0, f"Σήμερα: «{adj['from']}» έγινε «{adj['to']}» λόγω: {', '.join(adj['reasons'])}.")
            print("Προσαρμογή ετοιμότητας:", adj)

        load = impact.build(acts, plan, cfg, today, profile)

        race_date = cfg.get("race_date")
        race = None
        if race_date:
            days_left = (planner.to_date(race_date) - today).days
            if days_left >= 0:
                race = {"name": cfg.get("race_name", "Αγώνας"), "date": race_date, "days_left": days_left,
                        "km": cfg.get("race_km", 40), "gain": cfg.get("race_gain", 3000)}

        runs = sorted((a for a in acts if planner.is_run(a)), key=lambda a: a["date"], reverse=True)
        data = {
            "generated_at": now.isoformat(timespec="minutes"),
            "demo": args.demo,
            "race": race,
            "status": status,
            "wellness": wellness,
            "profile": {k: profile[k] for k in ("base_km", "base_minutes", "base_gain", "pace", "longest_km", "has_data")},
            "history": list(reversed(profile["weeks"])),  # από την παλιότερη προς τη νεότερη
            "recent": runs[:10],
            "plan": plan,
            "impact": load,
            "lthr": int(cfg.get("lthr") or 155),
            "max_hr": (cfg.get("history") or {}).get("max_hr"),
        }
        blob = encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8"), password)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(blob), encoding="utf-8")
        print(f"OK: {len(acts)} δραστηριότητες, {len(plan)} εβδομάδες προγράμματος → {out}")

        # Αποστολή των προπονήσεων στο ρολόι (ημερολόγιο Garmin Connect). Αν αποτύχει, τα δεδομένα έχουν ήδη σωθεί.
        if not args.demo and cfg.get("garmin_sync", True):
            try:
                import garmin_sync
                res = garmin_sync.sync(api, plan, today, int(cfg.get("garmin_sync_days", 7)))
                print(f"Garmin: σβήστηκαν {res['deleted']}, προγραμματίστηκαν {len(res['scheduled'])}: {', '.join(res['scheduled'])}")
            except Exception as e:
                traceback.print_exc()
                notify(topic, "Μονοπάτι: οι προπονήσεις δεν πέρασαν στο ρολόι",
                       f"{type(e).__name__}: {e}"[:300], priority=4)

        msg = morning_message(plan, today)
        if msg:
            notify(topic, *msg)
        return 0
    except SystemExit:
        raise
    except Exception as e:
        traceback.print_exc()
        notify(topic, "Trail Coach: αποτυχία ενημέρωσης", f"{type(e).__name__}: {e}"[:300], priority=4)
        return 1


if __name__ == "__main__":
    sys.exit(main())
