"""Φορτίο βουνού: ένας δείκτης φορτίου για trail, όχι μόνο απόσταση.

Κάθε τρέξιμο (και πεζοπορία στο βουνό) παίρνει μονάδες φορτίου από δύο πηγές:
  1. Καρδιαγγειακό φορτίο: διάρκεια × (μέσοι παλμοί / LTHR)², ώστε 1 ώρα στο κατώφλι = 100.
     Οι ανηφόρες ανεβάζουν τους παλμούς, άρα μετρούν ήδη εδώ.
  2. Μυϊκό φορτίο της κατηφόρας: 2,5 μονάδες ανά 100 m αρνητικής υψομετρικής.
     Η κατηφόρα κουράζει τους τετρακέφαλους (εκκεντρική σύσπαση) χωρίς να ανεβάζει τους παλμούς.

Οι άλλες αερόβιες δραστηριότητες (ποδήλατο, κολύμπι κ.λπ.) μετρούν ξεχωριστά ως «Άλλη αερόβια»,
ώστε να μη φουσκώνουν την εικόνα του τρεξίματος.

Από το καθημερινό φορτίο βγαίνουν (εκθετικοί μέσοι όροι):
  Φόρμα     = 42 ημερών (η φυσική κατάσταση που έχεις χτίσει)
  Κούραση   = 7 ημερών  (το πρόσφατο φορτίο)
  Φρεσκάδα  = Φόρμα − Κούραση (θετικό: ξεκούραστος, πολύ αρνητικό: κουρασμένος)
"""
from __future__ import annotations

from datetime import date, timedelta

DESCENT_PER_100M = 2.5
CTL_DAYS, ATL_DAYS = 42, 7
DEFAULT_IF = 0.78

# Αναμενόμενη ένταση (ως κλάσμα του LTHR) για ημέρες χωρίς δομή βημάτων.
PLAN_IF = {"mlr": 0.78, "easy": 0.78, "easy2": 0.8, "quality": 0.9, "long": 0.8, "medium": 0.78,
           "shakeout": 0.72, "race": 0.86}


def _d(s) -> date:
    return s if isinstance(s, date) else date.fromisoformat(str(s)[:10])


def is_mountain(a: dict) -> bool:
    t = a.get("type", "")
    return ("run" in t or "hik" in t or "mountaineering" in t) and (a.get("km") or 0) >= 0.5


def is_cardio(a: dict) -> bool:
    t = a.get("type", "")
    if is_mountain(a) or "strength" in t or "yoga" in t or "breath" in t:
        return False
    return (a.get("minutes") or 0) >= 10


def hr_load(minutes: float, intensity: float) -> float:
    i = min(1.15, max(0.5, intensity))
    return minutes / 60.0 * i * i * 100.0


def activity_load(a: dict, lthr: int) -> float:
    hr = a.get("avg_hr")
    i = hr / lthr if hr else DEFAULT_IF
    base = hr_load(a.get("minutes") or 0, i)
    if "hik" in a.get("type", ""):
        base *= 0.85
    loss = a.get("loss")
    if loss is None:
        loss = a.get("gain") or 0
    return round(base + loss / 100.0 * DESCENT_PER_100M, 1)


def steps_intensity(steps: list) -> float | None:
    tot = sq = 0.0

    def walk(ss, mult=1):
        nonlocal tot, sq
        for s in ss:
            if "repeat" in s:
                walk(s["steps"], mult * s["repeat"])
            else:
                tot += s["sec"] * mult
                sq += s["sec"] * mult * (s.get("lvl") or DEFAULT_IF) ** 2
    walk(steps)
    return (sq / tot) ** 0.5 if tot else None


def planned_load(day: dict) -> float:
    if (day.get("km") or 0) <= 0 or not day.get("minutes"):
        return 0.0
    i = (steps_intensity(day["steps"]) if day.get("steps") else None) or PLAN_IF.get(day.get("kind"), DEFAULT_IF)
    return round(hr_load(day["minutes"], i) + (day.get("gain") or 0) / 100.0 * DESCENT_PER_100M, 1)


def _ewma(prev: float, x: float, n: int) -> float:
    return prev + (x - prev) / n


def build(acts: list[dict], plan: list[dict], cfg: dict, today: date, profile: dict) -> dict:
    lthr = int(cfg.get("lthr") or 155)
    daily: dict[str, float] = {}
    cardio: dict[str, float] = {}
    longest: dict[str, float] = {}
    for a in acts:
        if is_mountain(a):
            L = activity_load(a, lthr)
            daily[a["date"]] = daily.get(a["date"], 0) + L
            a["impact"] = L
            longest[a["date"]] = max(longest.get(a["date"], 0), a.get("minutes") or 0)
        elif is_cardio(a):
            hr = a.get("avg_hr")
            cardio[a["date"]] = cardio.get(a["date"], 0) + hr_load(a.get("minutes") or 0, hr / lthr if hr else 0.7)

    dates = [_d(x) for x in daily] or [today]
    start = min(min(dates), today - timedelta(days=CTL_DAYS))
    ctl = atl = 0.0
    series = []
    d = start
    while d <= today:
        x = daily.get(d.isoformat(), 0.0)
        ctl, atl = _ewma(ctl, x, CTL_DAYS), _ewma(atl, x, ATL_DAYS)
        series.append({"date": d.isoformat(), "load": round(x), "ctl": round(ctl, 1), "atl": round(atl, 1),
                       "tsb": round(ctl - atl, 1)})
        d += timedelta(days=1)
    now = dict(series[-1])
    # Τα πρώτα ~6 εβδομάδες «ζεσταίνουν» τους μέσους όρους, οπότε στέλνω μόνο τις τελευταίες 12 εβδομάδες.
    series = series[-84:]

    # Προγραμματισμένο φορτίο ανά ημέρα και πρόβλεψη μέχρι το τέλος του προγράμματος.
    planned: dict[str, float] = {}
    for w in plan:
        tot = 0.0
        for day in w["days"]:
            p = planned_load(day)
            day["impact"] = round(p)
            if day.get("done"):
                day["done"]["impact"] = round(daily.get(day["date"], 0))
            planned[day["date"]] = p
            tot += p
        w["impact"] = round(tot)
    proj = []
    pc, pa = ctl, atl
    if daily.get(today.isoformat(), 0) == 0 and planned.get(today.isoformat()):
        # Η σημερινή προπόνηση δεν έχει γίνει ακόμα: ξαναϋπολογίζω τη σημερινή μέρα με το πρόγραμμα.
        prev = series[-2] if len(series) > 1 else {"ctl": 0, "atl": 0}
        pc = _ewma(prev["ctl"], planned[today.isoformat()], CTL_DAYS)
        pa = _ewma(prev["atl"], planned[today.isoformat()], ATL_DAYS)
    for ds in sorted(k for k in planned if _d(k) > today):
        x = planned[ds]
        pc, pa = _ewma(pc, x, CTL_DAYS), _ewma(pa, x, ATL_DAYS)
        proj.append({"date": ds, "load": round(x), "ctl": round(pc, 1), "atl": round(pa, 1), "tsb": round(pc - pa, 1)})

    # Εβδομαδιαίο φορτίο (τρέξιμο και άλλη αερόβια χωριστά), τελευταίες 12 εβδομάδες.
    mon = today - timedelta(days=today.weekday())
    weeks = []
    for k in range(11, -1, -1):
        ws = mon - timedelta(weeks=k)
        rng = [(ws + timedelta(days=j)).isoformat() for j in range(7)]
        weeks.append({"week_start": ws.isoformat(), "impact": round(sum(daily.get(x, 0) for x in rng)),
                      "cardio": round(sum(cardio.get(x, 0) for x in rng))})

    readiness = race_readiness(cfg, today, profile, now, proj, longest, acts)
    return {"now": now, "series": series, "projection": proj, "weeks": weeks, "readiness": readiness}


def _score(ratio: float) -> int:
    return int(round(max(0.0, min(1.0, ratio)) * 100))


def race_readiness(cfg: dict, today: date, profile: dict, now: dict, proj: list, longest: dict, acts: list) -> dict | None:
    if not cfg.get("race_date"):
        return None
    race = _d(cfg["race_date"])
    if race < today:
        return None
    km, gain = float(cfg.get("race_km", 40)), float(cfg.get("race_gain", 3000))
    pace = profile.get("pace") or 7.0
    race_min = (km + gain / 100.0) * pace * 1.08  # λίγο πιο αργά από τις προπονήσεις λόγω διάρκειας
    weekly_h = max(5.0, min(11.0, race_min / 60.0 * 0.9))
    target_ctl = round(weekly_h * 100 * 0.8 ** 2 / 7 + gain * 0.8 * DESCENT_PER_100M / 100 / 7)

    at_race = next((p for p in proj if p["date"] == race.isoformat()), None)
    if at_race is None and proj:
        at_race = proj[-1]
    # Οι τιμές του πρωινού του αγώνα, πριν μετρήσει ο ίδιος ο αγώνας.
    eve = next((p for p in proj if p["date"] == (race - timedelta(days=1)).isoformat()), at_race)
    race_ctl = eve["ctl"] if eve else now["ctl"]
    race_tsb = eve["tsb"] if eve else now["tsb"]

    since = today - timedelta(days=70)
    long_min = max((m for ds, m in longest.items() if _d(ds) >= since), default=0)
    weeks = profile.get("weeks", [])[:6]
    best_gain = max((w["gain"] for w in weeks), default=0)
    full = profile.get("weeks", [])[1:5]
    runs_avg = sum(w["runs"] for w in full) / len(full) if full else 0
    days = int(cfg.get("days_per_week") or 5)

    fresh = 1.0 if 0 <= race_tsb <= 25 else max(0.0, 1 - (abs(race_tsb) - (0 if race_tsb < 0 else 25)) / 25)
    parts = [
        {"key": "fitness", "label": "Φόρμα την ημέρα του αγώνα", "score": _score(race_ctl / target_ctl),
         "value": f"{race_ctl:.0f} από στόχο {target_ctl}", "weight": 0.35},
        {"key": "long", "label": "Μακρύτερο τρέξιμο (10 εβδ.)", "score": _score(long_min / (race_min * 0.6)),
         "value": f"{long_min / 60:.1f} ώρ από στόχο {race_min * 0.6 / 60:.1f}", "weight": 0.2},
        {"key": "vert", "label": "Υψομετρική εβδομάδας (6 εβδ.)", "score": _score(best_gain / (gain * 0.8)),
         "value": f"{best_gain:.0f} m από στόχο {gain * 0.8:.0f}", "weight": 0.2},
        {"key": "consistency", "label": "Συνέπεια (4 εβδ.)", "score": _score(runs_avg / days),
         "value": f"{runs_avg:.1f} από {days} τρεξίματα/εβδ.", "weight": 0.1},
        {"key": "fresh", "label": "Φρεσκάδα την ημέρα του αγώνα", "score": _score(fresh),
         "value": f"{race_tsb:+.0f} (ιδανικά 0 έως +25)", "weight": 0.15},
    ]
    total = int(round(sum(p["score"] * p["weight"] for p in parts)))
    return {"score": total, "parts": parts, "target_ctl": target_ctl, "race_ctl": race_ctl,
            "race_tsb": race_tsb, "est_minutes": int(round(race_min))}
