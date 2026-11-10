"""Σχεδιασμός προπόνησης για ορεινό αγώνα (Olympus Marathon 44 km / +3350 m), περιοδοποίηση στο periodization.py.

Το module δεν ξέρει τίποτα για τη Garmin: δουλεύει με μια λίστα από "κανονικοποιημένες"
δραστηριότητες, δηλαδή dicts της μορφής
    {"date": "2026-10-31", "type": "trail_running", "name": "...",
     "km": 18.4, "gain": 720, "minutes": 142.0, "avg_hr": 148}
"""
from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta

import periodization as pz
import workouts

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

# Η εβδομαδιαία δομή ορίζεται στο config.json (week_template) και στο periodization.py.

DESCENT_TIP = ("Στις κατηφόρες: μικρά γρήγορα βήματα, πόδια κάτω από το σώμα, χαλαρά γόνατα, "
               "μάτια 3–4 μέτρα μπροστά, χωρίς φρένο στις φτέρνες.")


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
            "minutes": int(round(sum(a["minutes"] for a in items))),
            "gain": int(sum(a["gain"] for a in items)),
            "runs": len(items),
        })
    return out


def build_profile(acts: list[dict], today: date) -> dict:
    hist = weekly_history(acts, today, 8)
    full = hist[1:5]  # οι τελευταίες 4 ολοκληρωμένες εβδομάδες
    km = statistics.mean(w["km"] for w in full)
    minutes = statistics.mean(w["minutes"] for w in full)
    gain = statistics.mean(w["gain"] for w in full)
    recent = [a for a in acts if is_run(a) and to_date(a["date"]) >= today - timedelta(days=56)]
    paces = [a["minutes"] / effort(a["km"], a["gain"]) for a in recent if a["minutes"] > 0]
    paces = [p for p in paces if 3.5 <= p <= 12]
    pace = statistics.median(paces) if paces else DEFAULT_PACE
    return {
        "base_km": round(km, 1),
        "base_minutes": int(round(minutes)),
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
        if mode in ("taper", "recovery"):
            return ("Ελαφριά κινητικότητα",
                    "20 λεπτά κινητικότητα και ελαφρύ core. Όχι βαριά κατεβάσματα πριν τον αγώνα.")
        s = 2 if mode == "down" else min(4, 2 + i // 6)
        return ("Ενδυνάμωση για κατηφόρες",
                f"35 λεπτά, {s} σετ στο καθένα, αργές κινήσεις: "
                f"καθίσματα σε ένα πόδι με 3 δευτερόλεπτα κάθοδο (8), "
                f"αργά κατεβάσματα από σκαλοπάτι (10 ανά πόδι), "
                f"Bulgarian split squat (8 ανά πόδι), "
                f"ανύψωση φτέρνας σε σκαλί (12 ανά πόδι), "
                f"γέφυρα γλουτών σε ένα πόδι (10) και σανίδα 40 δευτερόλεπτα. "
                f"Η αργή κάθοδος δυναμώνει τους τετρακέφαλους που φρενάρουν στις κατηφόρες. "
                f"Αν την επόμενη μέρα πονούν πολύ, κάν' το πιο ελαφρύ την επόμενη φορά.")
    if kind == "recover":
        return "Ξεκούραση", "Ξεκούραση ή ελαφρύ περπάτημα 20–30 λεπτά. Κανένα τρέξιμο. Φάε και πιες καλά."
    if kind == "prerace":
        return "Ξεκούραση πριν τον αγώνα", "Ετοίμασε εξοπλισμό και τροφές, φάε καλά και κοιμήσου νωρίς."
    if kind == "shakeout":
        return "Ελαφρύ ξεμούδιασμα", "20–25 λεπτά πολύ άνετα και 4 ζωηρά βήματα (strides) στο τέλος."
    if kind == "race":
        return (f"ΑΓΩΝΑΣ: {cfg.get('race_name', 'Trail')}",
                "Ξεκίνα συντηρητικά τα πρώτα χιλιόμετρα, φάε και πιες από νωρίς, περπάτα τις απότομες ανηφόρες. Απόλαυσε το!")
    if kind == "easy":
        if mode == "recovery":
            return ("Πολύ εύκολο τρέξιμο",
                    "Πολύ χαλαρά, 20–40 λεπτά σε επίπεδο. Αν πονούν οι μύες ή οι αρθρώσεις, περπάτησε. Χωρίς ανηφόρες, ταχύτητες ή κατηφόρες.")
        if mode == "taper":
            return "Εύκολο τρέξιμο", "Άνετος ρυθμός, να μπορείς να μιλάς χωρίς κόπο."
        return ("Εύκολο στην άσφαλτο",
                "Άνετος ρυθμός σε άσφαλτο ή χωματόδρομο χωρίς έντονες κλίσεις, να μπορείς να μιλάς χωρίς κόπο. Η άσφαλτος δίνει συχνότητα βήματος και ανάρρωση για το βουνό.")
    if kind == "easy2":
        return ("Εύκολο στην άσφαλτο + ζωηρά βήματα",
                "Άνετο τρέξιμο σε άσφαλτο και στο τέλος 6×20 δευτερόλεπτα ζωηρά βήματα (strides) σε επίπεδο ή ελαφριά κατηφόρα, με πλήρη ανάρρωση ανάμεσα. Εξάσκηση στην ταχύτητα των ποδιών.")
    if kind == "quality":
        if mode == "down":
            return "Ελαφρύ fartlek", "Άνετο τρέξιμο με 6×1 λεπτό ζωηρά, 2 λεπτά χαλαρά ανάμεσα."
        if mode == "taper":
            return ("Ελαφριά ποιότητα",
                    "Ζέσταμα 10 λεπτά, 4×2 λεπτά γρήγορη ανηφόρα (ελεγχόμενα), χαλαρή κατηφόρα, 10 λεπτά αποψύχρανση.")
        cyc = i % 3
        if cyc == 0:
            reps = min(10, 5 + i // 3)
            return (f"Ανηφόρες {reps}×3' (μονοπάτι)",
                    f"Ζέσταμα 15 λεπτά, {reps}×3 λεπτά γρήγορη ανηφόρα (δύσκολο αλλά ελεγχόμενο). "
                    f"Η κατηφόρα είναι προπόνηση τεχνικής, όχι ανάπαυση: μικρά γρήγορα βήματα και χαλαρά γόνατα. "
                    f"10 λεπτά αποψύχρανση.")
        if cyc == 1:
            if (i // 3) % 2 == 0:
                tm = int(5 * round(min(35, 15 + 2 * i) / 5))
                return (f"Tempo {tm}' (άσφαλτος)",
                        f"Ζέσταμα 15 λεπτά, {tm} λεπτά σε ρυθμό «άνετα σκληρό» σε επίπεδη άσφαλτο ή ποδηλατόδρομο, 10 λεπτά αποψύχρανση.")
            n = min(6, 3 + i // 6)
            return (f"Διαλείμματα κατωφλίου {n}×6' (άσφαλτος)",
                    f"Ζέσταμα 15 λεπτά, {n}×6 λεπτά σε ρυθμό κατωφλίου (δύσκολο αλλά σταθερό) με 2 λεπτά χαλαρό τρέξιμο ανάμεσα, 10 λεπτά αποψύχρανση. Σε επίπεδο, ώστε να κρατάς τον ρυθμό.")
        reps = min(10, 4 + i // 4)
        return (f"Κατηφόρες {reps}× (τεχνική)",
                f"Ζέσταμα 15 λεπτά και ανηφόρα προς μια κατηφόρα 6–10% και 150–300 μέτρα, σε μονοπάτι χωρίς πολλές πέτρες. "
                f"{reps} κατεβάσματα με γρήγορα μικρά βήματα, κορμός ελαφρά μπροστά από τους αστραγάλους (όχι κάθετος), "
                f"πόδια κάτω από το σώμα, μάτια 3–4 μέτρα μπροστά. Γύρνα πάνω περπατώντας ή τρέχοντας εύκολα. "
                f"Τις πρώτες φορές κάν' τα ελεγχόμενα, όχι στο όριο: οι τετρακέφαλοι πονούν 1–2 μέρες. "
                f"10 λεπτά αποψύχρανση.")
    if kind == "long":
        if mode == "down":
            return "Μακρύ (αποφόρτιση)", "Πιο σύντομο και χαλαρό μακρύ σε ανάγλυφο. Άφησε τα πόδια να ανακάμψουν."
        if mode == "taper":
            return "Μακρύ, ελαφρύ", "Μέτριο τρέξιμο σε ανάγλυφο, χωρίς πίεση. Κράτα τα πόδια φρέσκα για τον αγώνα."
        if left is not None and left <= 8:
            return ("Μακρύ trail: προσομοίωση αγώνα",
                    "Μακρύ σε ανάγλυφο όσο πιο κοντά στο προφίλ του αγώνα. Περπάτα τις απότομες ανηφόρες (power hiking) και δοκίμασε τον εξοπλισμό και την ίδια τροφή και υγρά που θα έχεις στον αγώνα. " + DESCENT_TIP)
        return ("Μακρύ trail",
                "Μακρύ σε ανάγλυφο, άνετος ρυθμός. Περπάτα τις απότομες ανηφόρες και εξάσκησε τη λήψη τροφής και υγρών. " + DESCENT_TIP)
    if kind == "medium":
        if mode in ("down", "taper"):
            return "Εύκολο τρέξιμο", "Χαλαρό και σύντομο."
        return ("Μέτριο σε κουρασμένα πόδια",
                "Άνετο τρέξιμο την επομένη του μακρύ. Σκοπός είναι ο χρόνος στα πόδια, όχι ο ρυθμός.")
    return kind, ""


# --- Το πρόγραμμα ----------------------------------------------------------------
def light_week_mlr(mode: str, b_race, after_b) -> bool:
    return mode in ("down", "taper") or bool(b_race) or bool(after_b)


def build_plan(profile: dict, cfg: dict, today: date, status: dict, acts: list[dict]) -> list[dict]:
    race = to_date(cfg["race_date"]) if cfg.get("race_date") else None
    if race and race < today:
        race = None
    mon0 = monday_of(today)
    race_mon = monday_of(race) if race else None
    n_weeks = 6 if not race else max(1, min(40, (race_mon - mon0).days // 7 + 1))
    pace = profile["pace"]
    lthr = int(cfg.get("lthr") or workouts.DEFAULT_LTHR)  # όριο γαλακτικού: δίνει τα bpm κάθε ζώνης
    hrmax = int((cfg.get("history") or {}).get("max_hr") or 0) or None  # μέγιστοι παλμοί για τα νορβηγικά πρωτόκολλα
    week_tpl = list(cfg.get("week_template") or pz.DEFAULT_WEEK)
    race_name = cfg.get("race_name", "Αγώνας")

    # Πρόσφατος αγώνας: δίνω χρόνο ανάκαμψης (π.χ. 7 ώρες αγώνας → 2 εβδομάδες χωρίς ένταση).
    last = cfg.get("last_race") or {}
    rec_start = rec_end = None
    post_recovery = False  # η ανάκαμψη μόλις τελείωσε: η πρώτη εβδομάδα ξεκινά από το 80% και ανεβαίνει
    if last.get("date"):
        lr = to_date(last["date"])
        hours = float(last.get("hours") or 0)
        rdays = 14 if hours >= 6 else 10 if hours >= 4 else 7 if hours >= 2 else 4
        end = monday_of(lr + timedelta(days=rdays)) + timedelta(days=6)
        if last.get("recovery_until"):
            # Χειροκίνητο τέλος ανάκαμψης (config.json → last_race.recovery_until), π.χ. για να ξεκινήσει νωρίτερα η ανάπτυξη.
            end = to_date(last["recovery_until"])
        if end >= today:
            rec_start, rec_end = lr, end
        elif (today - end).days <= 7:
            post_recovery = True

    # Όρια από το ιστορικό σου (TrainingPeaks): ό,τι έχεις ήδη αντέξει καθορίζει το ταβάνι.
    hist = cfg.get("history") or {}
    peak_km, peak_gain, long_max = PEAK_KM, PEAK_GAIN, LONG_RUN_MAX_KM
    typical = 0.0
    if hist.get("peak_4wk_km"):
        peak_km = max(PEAK_KM, min(90.0, float(hist["peak_4wk_km"]) * 1.03))
        peak_gain = max(PEAK_GAIN, min(3200.0, peak_km * 37))
    if hist.get("peak_week_gain"):
        # Ταβάνι υψομετρικής από ό,τι έχεις ήδη αντέξει (Garmin/TrainingPeaks), με 10% περιθώριο ασφαλείας.
        peak_gain = max(peak_gain, min(4000.0, float(hist["peak_week_gain"]) * 0.9))
        typical = float(hist.get("typical_week_km") or 0)
    if hist.get("longest_run_km"):
        long_max = max(LONG_RUN_MAX_KM, min(38.0, float(hist["longest_run_km"]) * 0.7))

    peak_min = float(hist.get("peak_4wk_minutes") or 0) * 1.05
    # Προφίλ: αν οι πρόσφατες εβδομάδες σου είναι πολύ κάτω από τις συνηθισμένες, λιγότερες επαναλήψεις στα διαλείμματα.
    typ_min = float(hist.get("typical_week_minutes") or 0)
    q_scale = 0.8 if (typ_min and profile["base_minutes"] < 0.6 * typ_min) else 1.0
    long_max_min = min(float(pz.LONG_MAX_MIN), float(hist.get("longest_run_minutes") or 0) * 0.7 or pz.LONG_MAX_MIN)

    km_level = min(peak_km, max(profile["base_km"], MIN_BASE_KM))
    gain_level = min(peak_gain, max(profile["base_gain"], km_level * 12))
    base_ratio = gain_level / km_level
    # Μετά από αγώνα το φορτίο της εβδομάδας είναι φυσιολογικά υψηλό και δεν σημαίνει υπερπροπόνηση.
    if status["reduce"] and not rec_start and not post_recovery:
        km_level *= 0.85
        gain_level *= 0.85
    skip_growth = status["hold"] and not rec_start and not post_recovery
    in_recovery = post_recovery

    # Αγώνες προετοιμασίας (config.json → b_races) και μεγάλες μέρες στο βουνό (config.json → big_days).
    b_races = {to_date(r["date"]): r for r in (cfg.get("b_races") or []) if to_date(r["date"]) >= mon0}
    big_days = {to_date(b["date"]): b for b in (cfg.get("big_days") or [])}

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

        wk_end = wk + timedelta(days=6)
        b_race = next(((d0, r) for d0, r in b_races.items() if wk <= d0 <= wk_end), None)
        after_b = next((d0 for d0 in b_races if wk - timedelta(days=7) <= d0 < wk), None)
        big_week = any(wk <= b0 <= wk_end for b0 in big_days)
        rec_week = bool(rec_start) and sum(
            1 for k in range(7) if rec_start < wk + timedelta(days=k) <= rec_end) >= 4
        if rec_week:
            n1 = (wk - rec_start).days
            mode, label = "recovery", "Ανάκαμψη μετά τον αγώνα"
            frac = 0.25 if n1 < 7 else 0.45
            wk_km, wk_gain = km_level * frac, gain_level * 0.2
            in_recovery = True
        elif left is not None and left <= 2:
            mode = "taper"
            frac = {2: 0.75, 1: 0.55, 0: 0.35}[left]
            label = "Εβδομάδα αγώνα" if left == 0 else "Αποκλιμάκωση (taper)"
            wk_km, wk_gain = km_level * frac, gain_level * frac
        else:
            if in_recovery:  # πρώτη εβδομάδα μετά την ανάκαμψη: ξεκινάω χαμηλότερα και ανεβαίνω
                km_level *= 0.8
                gain_level *= 0.8
                in_recovery = False
            is_down = i > 0 and ((left is not None and left > 3 and (left - 3) % 4 == 0) or (left is None and i % 4 == 3))
            if post_recovery:
                # Η ανάκαμψη τελείωσε νωρίτερα: η πρώτη εβδομάδα είναι ελαφριά επιστροφή και το πρόγραμμα
                # προχωρά μία εβδομάδα μπροστά, χωρίς δεύτερη αποφόρτιση αμέσως μετά.
                is_down = i == 0 or (is_down and i > 1)
            if after_b:
                is_down = True  # η εβδομάδα μετά από αγώνα προετοιμασίας είναι πάντα ελαφριά
            if is_down:
                mode = "down"
                label = ("Επιστροφή στην προπόνηση" if (post_recovery and i == 0)
                         else "Ανάκαμψη μετά τον αγώνα" if after_b else "Αποφόρτιση")
                wk_km, wk_gain = km_level * 0.7, gain_level * 0.7
            else:
                mode = "build"
                if up_count > 0:
                    if skip_growth:
                        skip_growth = False
                    else:
                        # Επιστροφή στο παλιό επίπεδό σου: λίγο πιο γρήγορη αύξηση μέχρι το 85% του συνηθισμένου όγκου.
                        growth = 1.12 if (typical and km_level < typical * 0.85) else GROWTH_KM
                        km_level = min(peak_km, km_level * growth)
                        floor_ratio = min(PEAK_RATIO, base_ratio + 1.5 * i)
                        gain_level = min(peak_gain, max(gain_level * (GROWTH_GAIN if growth == GROWTH_KM else 1.14), km_level * floor_ratio))
                up_count += 1
                label = pz.PHASE_LABEL[pz.phase_of(left)[0]]
                wk_km, wk_gain = km_level, gain_level
            if b_race:
                label = f"{label} · αγώνας προετοιμασίας"

        # Ταβάνι σε χρόνο: ό,τι ώρες την εβδομάδα έχεις ήδη αντέξει (με 5% περιθώριο).
        # Στις εβδομάδες αποφόρτισης και στο taper το ταβάνι μειώνεται αναλογικά, ώστε η μείωση να είναι πραγματική
        # (taper: −25% → −45% → αγώνας, Bosquet et al. 2007). Στην ειδική φάση επιτρέπεται +10% για τα μεγάλα μακριά.
        if peak_min and mode != "recovery":
            cap = peak_min * ({"down": 0.72, "taper": frac if mode == "taper" else 1.0}.get(mode, 1.0))
            if mode == "build" and pz.phase_of(left)[0] == "specific":
                cap *= 1.10
            est = effort(wk_km, wk_gain) * pace
            if est > cap:
                wk_km, wk_gain = wk_km * cap / est, wk_gain * cap / est

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
            elif week_tpl[dow] in pz.SHARE:
                slot = week_tpl[dow]
                kind = "quality" if slot in ("q1", "q2") else slot
                fk, fg = pz.SHARE[slot]
                km, gain = _r5(wk_km * fk), _r10(wk_gain * fg)
                if kind == "long":
                    km = min(km, long_max)
                    est = effort(km, gain) * pace
                    if long_max_min and est > long_max_min:
                        km, gain = _r5(km * long_max_min / est), _r10(gain * long_max_min / est)
            else:
                kind = "strength" if week_tpl[dow] == "gym" else "rest"

            rec_n = (d - rec_start).days if rec_start and rec_start < d <= rec_end else 0
            if rec_n and kind != "race":
                wd = d.weekday()
                if rec_n <= 7:
                    kind, km, gain = ("easy", 4.0, 50) if rec_n in (5, 7) else ("recover", 0.0, 0)
                elif week_tpl[wd] in ("q1", "q2"):
                    kind, km, gain = "easy", 6.0, 80
                elif week_tpl[wd] == "long":
                    kind, km, gain = "easy", 10.0, 150
                elif week_tpl[wd] == "gym":
                    kind, km, gain = "strength", 0.0, 0
                else:
                    kind, km, gain = "recover", 0.0, 0

            title, desc = describe(kind, i, "recovery" if rec_n else mode, left, cfg)
            why, session, fixed_min = None, None, None
            slot = week_tpl[dow]
            if not rec_n and not (race and left == 0):
                ph, k = pz.phase_of(left)
                if mode == "taper":
                    ph = "taper"
                if slot in ("q1", "q2") and kind == "quality":
                    title, desc, why = pz.quality(slot, ph, k, mode, q_scale, race_name)
                elif slot == "mlr" and kind == "mlr":
                    title, desc, why, fixed_min = pz.mlr(ph, k, mode)
                    km = max(3.0, _r5(fixed_min / pace - gain / 100.0))
                elif slot == "gym" and kind == "strength":
                    title, desc, why, session, fixed_min = pz.gym(ph, mode)
                elif kind == "long":
                    why = pz.long_why(ph)
                elif kind == "easy":
                    title, desc, why = "Εύκολο τρέξιμο", "Άνετος ρυθμός σε επίπεδο, 40–50 λεπτά. Να μπορείς να μιλάς χωρίς κόπο.", pz.EASY_WHY
            if rec_start and d == rec_start:
                kind, km, gain = "rest", 0.0, 0
                title, desc = f"Αγώνας {last.get('km', '')} km", "Ολοκληρώθηκε."
            if rec_n == 1 and kind == "recover":
                title = "Ανάκαμψη μετά τον αγώνα"
                desc = (f"Μπράβο για τα {last.get('km', '')} km! Για τις επόμενες 2–3 μέρες κανένα τρέξιμο: "
                        "περπάτημα 20–30 λεπτά, πολύ νερό, φαγητό με υδατάνθρακες και πρωτεΐνη, και ύπνος.")
            minutes = int(5 * round(effort(km, gain) * pace / 5)) if km > 0 else 0
            if fixed_min and kind != "mlr":
                minutes = fixed_min
            elif fixed_min:
                minutes = fixed_min
            light_week = mode in ("down", "taper") or bool(b_race) or bool(after_b)
            if kind == "quality" and not rec_n and not light_week:
                # Διαλειμματικές στις κανονικές εβδομάδες: 1:30 ή 1:45, ανάλογα με το πόσο μεγάλο είναι το κυρίως μέρος
                # (ζέσταμα + κομμάτια + αποψύχρανση). Ο χρόνος που περισσεύει γίνεται εύκολο τρέξιμο μετά τα κομμάτια.
                need = workouts.total_sec(workouts.build(title, 0, lthr, hrmax) or []) / 60
                target = pz.QUALITY_MIN_MIN if need <= 75 else pz.QUALITY_MAX_MIN
                if big_week and dow == 4:
                    target = pz.QUALITY_MIN_MIN  # την παραμονή της μεγάλης μέρας στο βουνό, στο ελάχιστο
                if minutes > 0:
                    km, gain = _r5(km * target / minutes), _r10(gain * target / minutes)
                minutes = target
            elif kind == "quality" and minutes > pz.QUALITY_MAX_MIN:
                # Ελαφριές εβδομάδες: έως 1:45, χωρίς ελάχιστο. Τα km μειώνονται αναλογικά.
                km, gain = _r5(km * pz.QUALITY_MAX_MIN / minutes), _r10(gain * pz.QUALITY_MAX_MIN / minutes)
                minutes = pz.QUALITY_MAX_MIN
            if kind == "long":
                cap = pz.LONG_MAX_MIN
                if left is not None and not rec_n and mode != "down":
                    ph_l, k_l = pz.phase_of(left)
                    if ph_l == "base":
                        cap = min(cap, 150 + 10 * k_l)  # σταδιακή άνοδος στη Βάση: 2:30 → 3:00 σε 4 εβδομάδες
                if minutes > cap:
                    km, gain = _r5(km * cap / minutes), _r10(gain * cap / minutes)
                    minutes = cap
            if kind == "mlr" and big_week and not light_week_mlr(mode, b_race, after_b):
                minutes = 90  # εβδομάδα με μεγάλη μέρα στο βουνό: το μεσαίο μακρύ στο ελάχιστο
                km = max(3.0, _r5(minutes / pace - gain / 100.0))
                title = "Medium long 1ώρ 30"
                desc = desc.replace(desc.split(" λεπτά")[0], "90", 1)
            if kind == "easy" and not rec_n and not (race and left == 0) and minutes < pz.EASY_MIN_MIN:
                # Εύκολο τρέξιμο: τουλάχιστον 40 λεπτά (εκτός ανάκαμψης μετά από αγώνα και εβδομάδας αγώνα).
                minutes = pz.EASY_MIN_MIN
                km = max(km, _r5(minutes / pace - gain / 100.0))
            if kind == "strength" and not fixed_min:
                minutes = 20 if (mode in ("taper", "recovery") or rec_n) else 35
            elif kind == "recover" and rec_n and rec_n <= 7:
                minutes = 30  # ελαφρύ περπάτημα
            # Αγώνας προετοιμασίας: ελαφριές οι δύο μέρες πριν, ξεκούραση και κινητικότητα τις δύο μέρες μετά.
            if b_race and not rec_n:
                gap = (b_race[0] - d).days
                r = b_race[1]
                if gap == 0:
                    kind, km, gain = "race", float(r.get("km") or 30), int(r.get("gain") or 1500)
                    minutes = int(r.get("minutes") or 5 * round(effort(km, gain) * pace / 5))
                    title = f"ΑΓΩΝΑΣ: {r.get('name', 'Αγώνας προετοιμασίας')}"
                    desc = ("Αγώνας προετοιμασίας για τον " + race_name + ": δοκίμασε τον ρυθμό στις ανηφόρες, τη διατροφή (60–90 g υδατάνθρακες την ώρα), "
                            "τα μπατόν και τον εξοπλισμό. Τρέξε δυνατά αλλά όχι στο όριο τις πρώτες 2 ώρες.")
                    why = ("Ένας αγώνας 4–5 ωρών 10 εβδομάδες πριν είναι η καλύτερη πρόβα: ρυθμός, στομάχι και κατηφόρα με κουρασμένα πόδια "
                           "σε πραγματικές συνθήκες. Η εβδομάδα πριν είναι ελαφριά και η επόμενη ανάκαμψης.")
                elif gap == 1:
                    kind, km, gain, minutes = "shakeout", 4.0, 50, 25
                    title, desc = describe("shakeout", i, mode, left, cfg)
                    why = None
                elif gap == 2:
                    kind, km, gain, minutes = "easy", max(3.0, _r5(40 / pace)), 50, 40
                    title = "Εύκολο στην άσφαλτο + ζωηρά βήματα"
                    desc = "40 λεπτά άνετα και 6×20″ ζωηρά βήματα στο τέλος. Τίποτα κουραστικό πριν τον αγώνα."
                    why = None
                elif gap == 4 and kind == "mlr":
                    minutes = min(minutes, 70)
                    km = max(3.0, _r5(minutes / pace - gain / 100.0))
                    title = "Medium long 1ώρ 10"
                    desc = desc.replace(desc.split(" λεπτά")[0], str(minutes), 1)
            if after_b and not rec_n:
                since = (d - after_b).days
                if since == 1:
                    kind, km, gain, minutes = "recover", 0.0, 0, 30
                    title, desc, why = "Ανάκαμψη μετά τον αγώνα", "Κανένα τρέξιμο: περπάτημα 20–30 λεπτά, νερό, υδατάνθρακες και πρωτεΐνη, ύπνος.", None
                elif since == 2 and kind == "strength":
                    title, desc, why, session, minutes = pz.gym("taper", mode)
                elif since == 3 and kind == "mlr":
                    kind, minutes, gain = "easy", 45, 50
                    km = max(3.0, _r5(minutes / pace - gain / 100.0))
                    title, desc, why = "Εύκολο τρέξιμο", "45 λεπτά άνετα σε επίπεδο. Αν τα πόδια πονούν ακόμα, περπάτησε.", pz.EASY_WHY

            # Μεγάλη μέρα στο βουνό (Απρίλιος–Μάιος): πάνω από το όριο των 3:00, για αντοχή στην κατηφόρα μετά από ώρες.
            if d in big_days and kind == "long" and not rec_n:
                b = big_days[d]
                minutes, gain = int(b.get("minutes") or 270), int(b.get("gain") or 2200)
                km = max(km, _r5(minutes / pace - gain / 100.0))
                h, mm = divmod(minutes, 60)
                title = f"Μακρύ στο βουνό {h}ώρ{f' {mm:02d}' if mm else ''}"
                desc = (f"Μεγάλη μέρα στο βουνό: {h}ώρ{f' {mm:02d}' if mm else ''} με περίπου +{gain} m, όσο πιο κοντά στο προφίλ του {race_name} "
                        "(συνεχής ανάβαση πάνω από 1.000 m και μεγάλη τεχνική κατηφόρα). Power hiking με μπατόν στα απότομα, "
                        "60–90 g υδατάνθρακες την ώρα, ίδιος εξοπλισμός με τον αγώνα. Η κατηφόρα στο τέλος, με κουρασμένα πόδια, είναι το πιο σημαντικό κομμάτι. " + DESCENT_TIP)
                why = ("Για στόχο κάτω από 6:30 χρειάζεσαι πόδια που αντέχουν την κατηφόρα από το Καταφύγιο Α ως τα Πριόνια μετά από 4 ώρες. "
                       "Αυτό χτίζεται μόνο με λίγες, αραιές μέρες 4–5 ωρών στο βουνό (Koop, 2016), με ελαφριά μέρα πριν και μετά.")

            steps = workouts.build(title, minutes, lthr, hrmax) if (km > 0 and kind != "race") else None
            if steps:
                minutes = max(minutes, int(round(workouts.total_sec(steps) / 60)))
            day = {
                "date": d.isoformat(), "dow": DAYS_GR[dow], "kind": kind,
                "title": title, "desc": desc, "km": km, "gain": gain, "minutes": minutes,
            }
            if steps:
                day["steps"] = steps
            if kind == "strength":
                day["session"] = session or ("mobility" if minutes <= 20 else "eccentric")
            if why:
                day["why"] = why
            done = done_by_date.get(d.isoformat())
            if done and d <= today:
                day["done"] = {"km": round(done["km"], 1), "gain": int(done["gain"]), "minutes": int(done["minutes"])}
            if d == today and status["low_readiness"] and kind in ("quality", "long", "medium", "mlr", "easy", "easy2"):
                day["adjust"] = ("Η ετοιμότητα σου είναι χαμηλή. Αν νιώθεις κουρασμένος, κάνε 30–40 λεπτά πολύ εύκολο τρέξιμο ή ξεκουράσου.")
            days.append(day)

        weeks.append({
            "week_start": wk.isoformat(), "label": label, "mode": mode, "weeks_left": left,
            "km": round(sum(x["km"] for x in days), 1),
            "minutes": int(sum(x["minutes"] for x in days if x["km"] > 0)), "gain": int(sum(x["gain"] for x in days)),
            "days": days,
        })
    return weeks
