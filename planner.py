"""Σχεδιασμός προπόνησης για trail 40 km / 3000 m D+ (5 προπονήσεις την εβδομάδα).

Το module δεν ξέρει τίποτα για τη Garmin: δουλεύει με μια λίστα από "κανονικοποιημένες"
δραστηριότητες, δηλαδή dicts της μορφής
    {"date": "2026-10-31", "type": "trail_running", "name": "...",
     "km": 18.4, "gain": 720, "minutes": 142.0, "avg_hr": 148}
"""
from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta

# --- Όρια του προγράμματος ---------------------------------------------------
PEAK_KM = 62.0           # μέγιστος εβδομαδιαίος όγκος (km)
PEAK_GAIN = 2500.0       # μέγιστη εβδομαδιαία θετική υψομετρική (m)
PEAK_RATIO = 40.0        # m D+ ανά km στην κορύφωση
LONG_RUN_MAX_KM = 28.0
GROWTH_KM = 1.08         # αύξηση όγκου ανά εβδομάδα ανάπτυξης
GROWTH_GAIN = 1.10
MIN_BASE_KM = 15.0
DEFAULT_PACE = 7.0       # λεπτά ανά "km προσπάθειας" αν δεν υπάρχουν δεδομένα
LOW_READINESS = 35

DAYS_GR = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]

# Εβδομαδιαία δομή: ημέρα (0=Δευτέρα) -> (είδος, ποσοστό km, ποσοστό D+)
TEMPLATE = {
    1: ("easy", 0.13, 0.08),
    2: ("quality", 0.16, 0.27),
    3: ("easy2", 0.11, 0.06),
    5: ("long", 0.38, 0.43),
    6: ("medium", 0.22, 0.16),
}
REST_DAYS = {0: "rest", 4: "strength"}


# --- Βοηθητικά ---------------------------------------------------------------
def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def to_date(s) -> date:
    if isinstance(s, date):
        return s
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def effort(km: float, gain: float) -> float:
    """'Km προσπάθειας': 100 m θετικής υψομετρικής ≈ 1 km."""
    return km + gain / 100.0


def is_run(a: dict) -> bool:
    return "run" in a["type"] and a["km"] >= 0.5


def _r5(x: float) -> float:
    return round(x * 2) / 2


def _r10(x: float) -> int:
    return int(round(x / 10.0) * 10)


# --- Ιστορικό και προφίλ -----------------------------------------------------
def weekly_history(acts: list[dict], today: date, weeks: int = 8) -> list[dict]:
    """Επιστρέφει [τρέχουσα εβδομάδα, προηγούμενη, ...]."""
    runs = [a for a in acts if is_run(a)]
    out = []
    for w in range(weeks):
        start = monday_of(today) - timedelta(weeks=w)
        end = start + timedelta(days=6)
        items = [a for a in runs if start <= to_date(a["date"]) <= end]
        out.append({
            "week_start": start.isoformat(),
            "km": round(sum(a["km"] for a in items), 1),
            "gain": int(sum(a["gain"] for a in items)),
            "runs": len(items),
        })
    return out


def build_profile(acts: list[dict], today: date) -> dict:
    hist = weekly_history(acts, today, 8)
    full = hist[1:5]  # οι τελευταίες 4 ολοκληρωμένες εβδομάδες
    km = statistics.mean(w["km"] for w in full)
    gain = statistics.mean(w["gain"] for w in full)
    recent = [a for a in acts if is_run(a) and to_date(a["date"]) >= today - timedelta(days=56)]
    paces = [a["minutes"] / effort(a["km"], a["gain"]) for a in recent if a["minutes"] > 0]
    paces = [p for p in paces if 3.5 <= p <= 12]
    pace = statistics.median(paces) if paces else DEFAULT_PACE
    return {
        "base_km": round(km, 1),
        "base_gain": int(gain),
        "pace": round(pace, 2),
        "longest_km": round(max((a["km"] for a in recent), default=0.0), 1),
        "weeks": hist,
        "has_data": km > 0,
    }


def build_status(acts: list[dict], profile: dict, today: date, wellness: dict) -> dict:
    runs = [a for a in acts if is_run(a)]

    def load(d0: date, d1: date) -> float:
        return sum(effort(a["km"], a["gain"]) for a in runs if d0 <= to_date(a["date"]) <= d1)

    acute = load(today - timedelta(days=6), today)
    chronic = load(today - timedelta(days=27), today) / 4.0
    acwr = round(acute / chronic, 2) if chronic > 0 else None
    last_full = profile["weeks"][1]

    advice: list[str] = []
    hold = reduce = False
    if not profile["has_data"]:
        advice.append("Δεν βρέθηκαν πρόσφατες διαδρομές στη Garmin. Το πρόγραμμα ξεκινά από ένα συντηρητικό επίπεδο.")
    else:
        if last_full["runs"] < 3:
            hold = True
            advice.append(
                f"Την προηγούμενη εβδομάδα έτρεξες {last_full['runs']} φορές (λιγότερο από 3). "
                "Δεν αυξάνω τον όγκο αυτή την εβδομάδα και στην επόμενη."
            )
        if acwr is not None and acwr > 1.5:
            reduce = True
            advice.append("Το φορτίο των τελευταίων 7 ημερών είναι πολύ πάνω από τον μέσο όρο σου. Το πρόγραμμα μειώνεται κατά 15%.")
        elif acwr is not None and acwr < 0.6:
            advice.append("Το φορτίο των τελευταίων 7 ημερών είναι αισθητά χαμηλότερο από το συνηθισμένο.")
    readiness = wellness.get("readiness")
    if readiness is not None and readiness < LOW_READINESS:
        advice.append(f"Η ετοιμότητα προπόνησης της Garmin είναι χαμηλή ({readiness}). Σήμερα προτίμησε εύκολο τρέξιμο ή ξεκούραση.")

    return {"acwr": acwr, "hold": hold, "reduce": reduce, "advice": advice,
            "readiness": readiness, "low_readiness": readiness is not None and readiness < LOW_READINESS}


# --- Περιγραφές προπονήσεων ----------------------------------------------------
def describe(kind: str, i: int, mode: str, left: int | None, cfg: dict) -> tuple[str, str]:
    if kind == "rest":
        return "Ξεκούραση", "Πλήρης ξεκούραση ή 20 λεπτά ελαφριά κινητικότητα."
    if kind == "strength":
        return ("Ξεκούραση / ενδυνάμωση",
                "Προαιρετικά 20–30 λεπτά ενδυνάμωση (καθίσματα, βήματα σε σκαλοπάτι, core) ή πλήρης ξεκούραση. Κράτα τα πόδια φρέσκα για το Σάββατο.")
    if kind == "recover":
        return "Αποκατάσταση", "Περπάτημα, ξεκούραση και καλό φαγητό. Μπράβο σου!"
    if kind == "prerace":
        return "Ξεκούραση πριν τον αγώνα", "Ετοίμασε εξοπλισμό και τροφές, φάε καλά και κοιμήσου νωρίς."
    if kind == "shakeout":
        return "Ελαφρύ ξεμούδιασμα", "20–25 λεπτά πολύ άνετα και 4 ζωηρά βήματα (strides) στο τέλος."
    if kind == "race":
        return (f"ΑΓΩΝΑΣ: {cfg.get('race_name', 'Trail')}",
                "Ξεκίνα συντηρητικά τα πρώτα χιλιόμετρα, φάε και πιες από νωρίς, περπάτα τις απότομες ανηφόρες. Απόλαυσε το!")
    if kind == "easy":
        return ("Εύκολο τρέξιμο",
                "Άνετος ρυθμός, να μπορείς να μιλάς χωρίς κόπο. Περπάτα τις απότομες ανηφόρες αν ανεβαίνει ο παλμός.")
    if kind == "easy2":
        return ("Εύκολο + ζωηρά βήματα",
                "Άνετο τρέξιμο και στο τέλος 6×20 δευτερόλεπτα ζωηρά βήματα (strides) σε επίπεδο, με πλήρη ανάρρωση ανάμεσα.")
    if kind == "quality":
        if mode == "down":
            return "Ελαφρύ fartlek", "Άνετο τρέξιμο με 6×1 λεπτό ζωηρά, 2 λεπτά χαλαρά ανάμεσα."
        if mode == "taper":
            return ("Ελαφριά ποιότητα",
                    "Ζέσταμα 10 λεπτά, 4×2 λεπτά γρήγορη ανηφόρα (ελεγχόμενα), χαλαρή κατηφόρα, 10 λεπτά αποψύχρανση.")
        if i % 2 == 0:
            reps = min(10, 5 + i // 2)
            return (f"Ανηφόρες {reps}×3'",
                    f"Ζέσταμα 15 λεπτά, {reps}×3 λεπτά γρήγορη ανηφόρα (δύσκολο αλλά ελεγχόμενο), κατηφόρα χαλαρά για ανάρρωση, 10 λεπτά αποψύχρανση.")
        tm = int(5 * round(min(35, 15 + 2 * i) / 5))
        return (f"Tempo {tm}'",
                f"Ζέσταμα 15 λεπτά, {tm} λεπτά σε ρυθμό «άνετα σκληρό», 10 λεπτά αποψύχρανση.")
    if kind == "long":
        if mode == "down":
            return "Μακρύ (αποφόρτιση)", "Πιο σύντομο και χαλαρό μακρύ σε ανάγλυφο. Άφησε τα πόδια να ανακάμψουν."
        if mode == "taper":
            return "Μακρύ, ελαφρύ", "Μέτριο τρέξιμο σε ανάγλυφο, χωρίς πίεση. Κράτα τα πόδια φρέσκα για τον αγώνα."
        if left is not None and left <= 8:
            return ("Μακρύ trail: προσομοίωση αγώνα",
                    "Μακρύ σε ανάγλυφο όσο πιο κοντά στο προφίλ του αγώνα. Περπάτα τις απότομες ανηφόρες (power hiking) και δοκίμασε τον εξοπλισμό και την ίδια τροφή και υγρά που θα έχεις στον αγώνα.")
        return ("Μακρύ trail",
                "Μακρύ σε ανάγλυφο, άνετος ρυθμός. Περπάτα τις απότομες ανηφόρες και εξάσκησε τη λήψη τροφής και υγρών.")
    if kind == "medium":
        if mode in ("down", "taper"):
            return "Εύκολο τρέξιμο", "Χαλαρό και σύντομο."
        return ("Μέτριο σε κουρασμένα πόδια",
                "Άνετο τρέξιμο την επομένη του μακρύ. Σκοπός είναι ο χρόνος στα πόδια, όχι ο ρυθμός.")
    return kind, ""


# --- Το πρόγραμμα ----------------------------------------------------------------
def build_plan(profile: dict, cfg: dict, today: date, status: dict, acts: list[dict]) -> list[dict]:
    race = to_date(cfg["race_date"]) if cfg.get("race_date") else None
    if race and race < today:
        race = None
    mon0 = monday_of(today)
    race_mon = monday_of(race) if race else None
    n_weeks = 6 if not race else max(1, min(26, (race_mon - mon0).days // 7 + 1))
    pace = profile["pace"]

    km_level = min(PEAK_KM, max(profile["base_km"], MIN_BASE_KM))
    gain_level = min(PEAK_GAIN, max(profile["base_gain"], km_level * 12))
    base_ratio = gain_level / km_level
    if status["reduce"]:
        km_level *= 0.85
        gain_level *= 0.85
    skip_growth = status["hold"]

    done_by_date: dict[str, dict] = {}
    for a in acts:
        if is_run(a):
            d = done_by_date.setdefault(a["date"], {"km": 0.0, "gain": 0, "minutes": 0.0})
            d["km"] += a["km"]
            d["gain"] += a["gain"]
            d["minutes"] += a["minutes"]

    weeks: list[dict] = []
    up_count = 0
    for i in range(n_weeks):
        wk = mon0 + timedelta(weeks=i)
        left = (race_mon - wk).days // 7 if race else None

        if left is not None and left <= 2:
            mode = "taper"
            frac = {2: 0.75, 1: 0.55, 0: 0.35}[left]
            label = "Εβδομάδα αγώνα" if left == 0 else "Αποκλιμάκωση (taper)"
            wk_km, wk_gain = km_level * frac, gain_level * frac
        else:
            is_down = i > 0 and ((left is not None and left > 3 and (left - 3) % 4 == 0) or (left is None and i % 4 == 3))
            if is_down:
                mode, label = "down", "Αποφόρτιση"
                wk_km, wk_gain = km_level * 0.7, gain_level * 0.7
            else:
                mode = "build"
                if up_count > 0:
                    if skip_growth:
                        skip_growth = False
                    else:
                        km_level = min(PEAK_KM, km_level * GROWTH_KM)
                        floor_ratio = min(PEAK_RATIO, base_ratio + 1.5 * i)
                        gain_level = min(PEAK_GAIN, max(gain_level * GROWTH_GAIN, km_level * floor_ratio))
                up_count += 1
                label = "Ειδική προετοιμασία" if (left is not None and left <= 8) else "Ανάπτυξη"
                wk_km, wk_gain = km_level, gain_level

        days = []
        for dow in range(7):
            d = wk + timedelta(days=dow)
            kind, km, gain = "rest", 0.0, 0
            if race and left == 0:
                if d == race:
                    kind, km, gain = "race", float(cfg.get("race_km", 40)), int(cfg.get("race_gain", 3000))
                elif d > race:
                    kind = "recover"
                else:
                    before = (race - d).days
                    if before == 1:
                        kind = "prerace"
                    elif before == 2:
                        kind, km, gain = "shakeout", 4.0, 50
                    elif before == 4:
                        kind, km, gain = "easy", 6.0, 100
            elif dow in TEMPLATE:
                kind, fk, fg = TEMPLATE[dow]
                km, gain = _r5(wk_km * fk), _r10(wk_gain * fg)
                if kind == "long":
                    km = min(km, LONG_RUN_MAX_KM)
            else:
                kind = REST_DAYS.get(dow, "rest")

            title, desc = describe(kind, i, mode, left, cfg)
            minutes = int(5 * round(effort(km, gain) * pace / 5)) if km > 0 else 0
            day = {
                "date": d.isoformat(), "dow": DAYS_GR[dow], "kind": kind,
                "title": title, "desc": desc, "km": km, "gain": gain, "minutes": minutes,
            }
            done = done_by_date.get(d.isoformat())
            if done and d <= today:
                day["done"] = {"km": round(done["km"], 1), "gain": int(done["gain"]), "minutes": int(done["minutes"])}
            if d == today and status["low_readiness"] and kind in ("quality", "long", "medium", "easy", "easy2"):
                day["adjust"] = ("Η ετοιμότητα σου είναι χαμηλή. Αν νιώθεις κουρασμένος, κάνε 30–40 λεπτά πολύ εύκολο τρέξιμο ή ξεκουράσου.")
            days.append(day)

        weeks.append({
            "week_start": wk.isoformat(), "label": label, "mode": mode, "weeks_left": left,
            "km": round(sum(x["km"] for x in days), 1), "gain": int(sum(x["gain"] for x in days)),
            "days": days,
        })
    return weeks
