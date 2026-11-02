"""Πρωινός έλεγχος ετοιμότητας: αλλάζει τη σημερινή προπόνηση όταν το σώμα δείχνει κούραση.

Σήματα από το ρολόι (της νύχτας που πέρασε):
    HRV         κατάσταση Garmin LOW/POOR → κόκκινο, UNBALANCED → κίτρινο,
                ή HRV νύχτας κάτω από το κατώτερο όριο της «ισορροπημένης» ζώνης σου → κίτρινο
    Ύπνος       σκορ < 50 → κόκκινο, < 60 → κίτρινο
    Παλμοί ηρ.  ≥ 5 πάνω από τον μέσο όρο 7 ημερών → κόκκινο, ≥ 3 → κίτρινο
    Ετοιμότητα  Garmin < 25 → κόκκινο, < 40 → κίτρινο

    Κατηφόρα   πάνω από max(800 m, 2× τον συνηθισμένο σου) αρνητική υψομετρική τις τελευταίες 48 ώρες → κίτρινο
                και οι σημερινές κατηφόρες γίνονται «κατέβασμα περπατώντας» (οι τετρακέφαλοι θέλουν 48–72 ώρες
                μετά από έντονη εκκεντρική καταπόνηση, Eston et al., 2003· Giandolini et al., 2016)

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

from datetime import date, timedelta

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


def descent_load(acts: list[dict], today: date) -> tuple[float, float]:
    """(αρνητική υψομετρική τελευταίων 48 ωρών, συνηθισμένη 48ωρη τιμή των τελευταίων 4 εβδομάδων)."""
    def loss(a):
        v = a.get("loss")
        return float(v if v is not None else (a.get("gain") or 0))
    runs = [a for a in acts if ("run" in a.get("type", "") or "hik" in a.get("type", ""))]
    recent = sum(loss(a) for a in runs if today - timedelta(days=2) <= date.fromisoformat(a["date"]) <= today)
    month = sum(loss(a) for a in runs if today - timedelta(days=30) <= date.fromisoformat(a["date"]) < today - timedelta(days=2))
    return recent, month / 14.0


def _no_downhill(day: dict, lthr: int, original: str) -> None:
    """Κρατά την ανηφόρα, βγάζει το τρέξιμο στην κατηφόρα."""
    WALK = "Κατέβασμα περπατώντας: χθες/προχθές είχες πολλή κατηφόρα, δώσε χρόνο στους τετρακέφαλους"
    title = day["title"]
    if title.startswith("Κατηφόρες") or title.startswith("Ανάβαση tempo"):
        m = 25 if title.startswith("Κατηφόρες") else max(20, int("".join(c for c in title.split("tempo")[1].split("'")[0] if c.isdigit()) or 25))
        main = [workouts._step("Συνεχής ανάβαση tempo", m * 60, "tempo", lthr, "Ανηφόρα σε ρυθμό αγώνα, power hiking στα απότομα"),
                workouts._free("Κατέβασμα περπατώντας", max(600, m * 40), WALK)]
        day["steps"] = workouts._wrap([workouts._step("Ζέσταμα", 900, "warm", lthr)], main,
                                      [workouts._step("Αποψύχρανση", 600, "rec", lthr)], day["minutes"] * 60, lthr)
        day["title"] = f"Ανάβαση tempo {m}' χωρίς κατηφόρα (προσαρμογή)"
        day["desc"] = (f"Αντί για «{original}»: ζέσταμα, {m} λεπτά συνεχούς ανάβασης σε ρυθμό αγώνα και κατέβασμα περπατώντας. "
                       "Η καρδιά δουλεύει κανονικά, οι τετρακέφαλοι ξεκουράζονται από την κατηφόρα.")
    else:
        def walk(steps):
            for st in steps:
                if "repeat" in st:
                    walk(st["steps"])
                elif st.get("hr") is None and "Κατ" in st.get("name", ""):
                    st["name"], st["note"] = "Κατέβασμα περπατώντας", WALK
        walk(day.get("steps") or [])
        if day["kind"] == "long":
            day["gain"] = int(day.get("gain", 0) * 0.7)
            day["desc"] = day["desc"] + " Σήμερα διάλεξε διαδρομή με λιγότερη κατηφόρα ή κατέβαινε περπατώντας τα απότομα."
        else:
            day["desc"] = day["desc"] + " Σήμερα κατέβαινε περπατώντας μετά από κάθε ανηφόρα."
        day["title"] = day["title"] + " (χωρίς κατηφόρα)"


def _easy(day: dict, minutes: int, title: str, desc: str, lthr: int, band_title: str = "Εύκολο τρέξιμο") -> None:
    day.update({"kind": "easy", "title": title, "desc": desc, "minutes": minutes,
                "gain": min(day.get("gain", 0), 100), "km": max(1.0, round(minutes / 7.0, 1))})
    day["steps"] = workouts.build(band_title, minutes, lthr)
    day.pop("session", None)


def adjust_today(plan: list[dict], today_iso: str, wellness: dict, lthr: int, acts: list[dict] | None = None) -> dict | None:
    """Αλλάζει (στη θέση της) τη σημερινή ημέρα του προγράμματος. Επιστρέφει περίληψη ή None."""
    day = next((d for w in plan for d in w["days"] if d["date"] == today_iso), None)
    if not day or day.get("done") or day.get("kind") == "race" or (day.get("km") or 0) <= 0:
        return None
    red, amber = signals(wellness)
    heavy_descent = False
    if acts:
        recent, usual = descent_load(acts, date.fromisoformat(today_iso))
        if recent >= max(800.0, 2 * usual):
            heavy_descent = True
            amber.append(f"{recent:.0f} m κατηφόρα τις τελευταίες 48 ώρες")
    if not red and len(amber) < 2:
        if heavy_descent and day["kind"] in ("quality", "long", "mlr", "medium"):
            original = day["title"]
            _no_downhill(day, lthr, original)
            day["adjust"] = "Προσαρμογή: " + amber[-1] + ". Ανηφόρα κανονικά, κατέβασμα περπατώντας."
            day["why"] = ("Μετά από πολλή κατηφόρα οι τετρακέφαλοι έχουν εκκεντρική μυϊκή βλάβη που χρειάζεται 48–72 ώρες. "
                          "Η ανηφόρα δεν την επιβαρύνει, η κατηφόρα ναι (Eston et al., 2003· Giandolini et al., 2016).")
            day["adjusted_from"] = original
            return {"from": original, "to": day["title"], "reasons": [amber[-1]]}
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
