"""Πρωινός έλεγχος ετοιμότητας: αλλάζει τη σημερινή προπόνηση όταν το σώμα δείχνει κούραση.

Σήματα από το ρολόι (της νύχτας που πέρασε):
    HRV         κατάσταση Garmin LOW/POOR → κόκκινο, UNBALANCED → κίτρινο,
                ή HRV νύχτας κάτω από το κατώτερο όριο της «ισορροπημένης» ζώνης σου → κίτρινο
    Ύπνος       σκορ < 50 → κόκκινο, < 60 → κίτρινο
    Παλμοί ηρ.  ≥ 5 πάνω από τον μέσο όρο 7 ημερών → κόκκινο, ≥ 3 → κίτρινο
    Ετοιμότητα  Garmin < 25 → κόκκινο, < 40 → κίτρινο

Απόφαση (μόνο για σήμερα):
    2+ κόκκινα          → «πολύ εύκολο 30'» (ή ξεκούραση)
    1 κόκκινο ή 2+ κίτρινα → η δύσκολη μέρα γίνεται εύκολη: διαλειμματική → εύκολο 40',
                          medium long → 60' εύκολο, μακρύ → 65% της διάρκειας σε ζώνη 1–2
    αλλιώς               → καμία αλλαγή
Η χαμένη ποιότητα δεν «χρωστιέται»: δεν στριμώχνεται σε άλλη μέρα (ασφαλέστερο από το να φορτωθεί η εβδομάδα).
Η τεκμηρίωση: η καθοδήγηση της προπόνησης με το HRV δίνει ίσα ή καλύτερα αποτελέσματα με λιγότερη
δύσκολη προπόνηση (Kiviniemi et al., 2007· Vesterinen et al., 2016· Javaloyes et al., 2019).
"""
from __future__ import annotations

import workouts

HARD = ("quality", "mlr", "long", "medium")


def signals(w: dict) -> tuple[list[str], list[str]]:
    red, amber = [], []
    st = (w.get("hrv_status") or "").upper()
    if st in ("LOW", "POOR"):
        red.append("HRV χαμηλό")
    elif st == "UNBALANCED":
        amber.append("HRV εκτός ισορροπίας")
    elif w.get("hrv") is not None and w.get("hrv_baseline_low") and w["hrv"] < w["hrv_baseline_low"]:
        amber.append(f"HRV νύχτας {w['hrv']:.0f} ms, κάτω από το συνηθισμένο σου")
    sl = w.get("sleep_score")
    if sl is not None:
        if sl < 50:
            red.append(f"ύπνος {sl:.0f}/100")
        elif sl < 60:
            amber.append(f"ύπνος {sl:.0f}/100")
    rhr, avg = w.get("resting_hr"), w.get("resting_hr_7d")
    if rhr is not None and avg:
        diff = rhr - avg
        if diff >= 5:
            red.append(f"παλμοί ηρεμίας +{diff:.0f} από τον μέσο όρο")
        elif diff >= 3:
            amber.append(f"παλμοί ηρεμίας +{diff:.0f} από τον μέσο όρο")
    rd = w.get("readiness")
    if rd is not None:
        if rd < 25:
            red.append(f"ετοιμότητα Garmin {rd:.0f}")
        elif rd < 40:
            amber.append(f"ετοιμότητα Garmin {rd:.0f}")
    return red, amber


def _easy(day: dict, minutes: int, title: str, desc: str, lthr: int, band_title: str = "Εύκολο τρέξιμο") -> None:
    day.update({"kind": "easy", "title": title, "desc": desc, "minutes": minutes,
                "gain": min(day.get("gain", 0), 100), "km": max(1.0, round(minutes / 7.0, 1))})
    day["steps"] = workouts.build(band_title, minutes, lthr)
    day.pop("session", None)


def adjust_today(plan: list[dict], today_iso: str, wellness: dict, lthr: int) -> dict | None:
    """Αλλάζει (στη θέση της) τη σημερινή ημέρα του προγράμματος. Επιστρέφει περίληψη ή None."""
    day = next((d for w in plan for d in w["days"] if d["date"] == today_iso), None)
    if not day or day.get("done") or day.get("kind") == "race" or (day.get("km") or 0) <= 0:
        return None
    red, amber = signals(wellness)
    if not red and len(amber) < 2:
        return None
    reasons = red + amber
    original = day["title"]
    why = ("Η καθοδήγηση της προπόνησης από το HRV και την ανάκαμψη δίνει ίσα ή καλύτερα αποτελέσματα με λιγότερη κούραση "
           "(Kiviniemi et al., 2007· Vesterinen et al., 2016· Javaloyes et al., 2019). Η δύσκολη προπόνηση δεν «χρωστιέται»: "
           "συνεχίζεις κανονικά από αύριο.")
    if len(red) >= 2:
        _easy(day, 30, "Πολύ εύκολο 30' ή ξεκούραση (προσαρμογή)",
              "Το σώμα σου δείχνει έντονη κούραση. Κάνε 30 λεπτά πολύ χαλαρά σε επίπεδο ή ξεκουράσου τελείως. "
              "Αν νιώθεις άρρωστος (πυρετός, πόνος σε όλο το σώμα), μην τρέξεις.", lthr, "Πολύ εύκολο")
    elif day["kind"] in ("quality",):
        _easy(day, 40, "Εύκολο 40' (προσαρμογή)",
              f"Αντί για «{original}»: 40 λεπτά άνετα, να μπορείς να μιλάς. Η ποιοτική προπόνηση σήμερα θα κόστιζε περισσότερο απ' όσο θα έδινε.", lthr)
    elif day["kind"] in ("mlr", "medium"):
        _easy(day, 60, "Εύκολο 60' (προσαρμογή)",
              f"Αντί για «{original}»: 60 λεπτά άνετα σε ήπιο ανάγλυφο.", lthr)
    elif day["kind"] == "long":
        m = int(5 * round(day["minutes"] * 0.65 / 5))
        day.update({"title": f"Μακρύ, χαλαρό {m}' (προσαρμογή)", "minutes": m, "gain": int(day.get("gain", 0) * 0.6),
                    "km": round(day["km"] * 0.65, 1),
                    "desc": f"Αντί για «{original}»: {m} λεπτά σε ζώνη 1–2, περπάτα τις ανηφόρες. Κράτα τη διατροφή όπως σε κανονικό μακρύ."})
        day["steps"] = workouts.build("Μακρύ", m, lthr)
    elif red:
        _easy(day, 30, "Πολύ εύκολο 30' (προσαρμογή)", "Σήμερα μόνο 30 λεπτά πολύ χαλαρά.", lthr, "Πολύ εύκολο")
    else:
        return None
    day["adjust"] = "Προσαρμογή ετοιμότητας: " + ", ".join(reasons) + "."
    day["why"] = why
    day["adjusted_from"] = original
    return {"from": original, "to": day["title"], "reasons": reasons}
