"""Δομημένες προπονήσεις σαν του TrainingPeaks: βήματα με διάρκεια, ζώνη και στόχο παλμών (bpm).

Οι ζώνες υπολογίζονται από το όριο γαλακτικού (LTHR). Με LTHR = 155 βγαίνουν ακριβώς τα bpm
που φαίνονται στις προπονήσεις σου στο TrainingPeaks (π.χ. ζέσταμα 101–119, έντονο 165–175).
Κάθε βήμα:  {"name", "sec", "hr": [χαμηλό, υψηλό] ή None, "zone", "lvl", "note"}
Επανάληψη:  {"repeat": φορές, "steps": [...]}
"""
from __future__ import annotations

import re

DEFAULT_LTHR = 155

# (χαμηλό, υψηλό) ως ποσοστό του LTHR, όνομα ζώνης
BANDS = {
    "rec": (0.54, 0.65, "Zone 1: Recovery"),
    "warm": (0.65, 0.77, "Zone 1: Recovery"),
    "easy": (0.75, 0.86, "Zone 1: Recovery-Zone 2: Aerobic"),
    "tempo": (0.90, 0.94, "Zone 3: Tempo"),
    "ladder": (0.92, 0.97, "Zone 4: SubThreshold"),
    "thresh": (0.95, 1.00, "Zone 4: SubThreshold"),
    "hill": (1.00, 1.06, "Zone 5A-5B: Threshold-Aerobic Capacity"),
    "stride": (1.06, 1.155, "Zone 5C: Anaerobic Capacity"),
}


# Ζώνες από τα νορβηγικά πρωτόκολλα, ως ποσοστό των μέγιστων παλμών (HRmax).
MAX_BANDS = {
    "vo2": (0.90, 0.95, "Zone 5: VO2max (90–95% HRmax)"),
    "lt2": (0.82, 0.87, "Zone 4: Κατώφλι LT2 (82–87% HRmax)"),
    "sublt": (0.80, 0.85, "Zone 4: Υπο-κατώφλι (80–85% HRmax)"),
}
LTHR_TO_MAX = 0.833  # LTHR / HRmax όταν δεν είναι γνωστοί οι μέγιστοι παλμοί (155 / 186)


def _mstep(name: str, sec: int, band: str, lthr: int, hrmax: int | None, note: str | None = None) -> dict:
    lo, hi, zone = MAX_BANDS[band]
    hm = hrmax or round(lthr / LTHR_TO_MAX)
    s = {"name": name, "sec": int(sec), "zone": zone, "hr": [round(lo * hm), round(hi * hm)],
         "lvl": round((lo + hi) / 2 * hm / lthr, 2)}
    if note:
        s["note"] = note
    return s


def _effort(name: str, sec: int, lvl: float, note: str) -> dict:
    """Σύντομο έντονο βήμα με στόχο την αίσθηση (RPE): οι παλμοί δεν προλαβαίνουν να ανέβουν."""
    return {"name": name, "sec": int(sec), "lvl": lvl, "zone": None, "hr": None, "note": note}


def _step(name: str, sec: int, band: str, lthr: int, note: str | None = None) -> dict:
    lo, hi, zone = BANDS[band]
    s = {"name": name, "sec": int(sec), "lvl": round((lo + hi) / 2, 2), "zone": zone,
         "hr": [round(lo * lthr), round(hi * lthr)]}
    if note:
        s["note"] = note
    return s


def _free(name: str, sec: int, note: str) -> dict:
    """Βήμα χωρίς στόχο παλμών (π.χ. κατηφόρα, όπου οι παλμοί δεν δείχνουν την προσπάθεια)."""
    return {"name": name, "sec": int(sec), "lvl": 0.62, "zone": None, "hr": None, "note": note}


def _rep(times: int, steps: list) -> dict:
    return {"repeat": int(times), "steps": steps}


def total_sec(steps: list) -> int:
    t = 0
    for s in steps:
        t += s["repeat"] * total_sec(s["steps"]) if "repeat" in s else s["sec"]
    return t


def _wrap(head, main, tail, total, lthr, band="easy", name="Εύκολο τρέξιμο", before_main=False):
    """Συμπληρώνει τη διάρκεια με ένα σταθερό, εύκολο βήμα ώστε να βγαίνει η συνολική διάρκεια."""
    gap = (total - total_sec(head) - total_sec(main) - total_sec(tail)) // 60 * 60
    mid = [_step(name, gap, band, lthr)] if gap >= 120 else []
    return head + (mid + main if before_main else main + mid) + tail


def _num(pattern: str, text: str, default: int) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else default


def build(title: str, minutes: int, lthr: int = DEFAULT_LTHR, hrmax: int | None = None) -> list | None:
    """Επιστρέφει τη δομή της προπόνησης ή None (ξεκούραση, ενδυνάμωση, αγώνας)."""
    total = int(minutes) * 60

    def warm(m): return _step("Ζέσταμα", m * 60, "warm", lthr)
    def cool(m): return _step("Αποψύχρανση", m * 60, "rec", lthr)

    if title.startswith("Εύκολο στην άσφαλτο + ζωηρά"):
        strides = [_rep(6, [_step("Ζωηρά βήματα", 20, "stride", lthr), _step("Εύκολο", 100, "rec", lthr)])]
        return _wrap([warm(5)], strides, [cool(5)], total, lthr, before_main=True)
    if title.startswith("Πολύ εύκολο"):
        return _wrap([_step("Ζέσταμα", 300, "rec", lthr)], [], [cool(5)], total, lthr, band="warm", name="Εύκολο")
    if title.startswith(("Εύκολο στην άσφαλτο", "Εύκολο τρέξιμο", "Μέτριο")):
        return _wrap([warm(5)], [], [cool(5)], total, lthr)
    if title.startswith("Νορβηγικό"):
        n = _num(r"(\d+)×", title, 4)
        m = _num(r"×(\d+)'", title, 4)
        main = [_rep(n, [_free("Ανέβασμα παλμών", 90, "Κανόνας 90″: όχι σπριντ, ανέβασε σταδιακά την ένταση στην ανηφόρα 6–10%"),
                         _mstep("VO2max στην ανηφόρα", m * 60 - 90, "vo2", lthr, hrmax, "Σταθερά στο 90–95% HRmax ως το τέλος, RPE 8,5/10"),
                         _free("Χαλαρό τρέξιμο", 180, "Κατέβα ή τρέξε χαλαρά, πλήρης ανάσα")])]
        main[0]["steps"][0]["lvl"] = 0.95
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Micro 30/15"):
        n = _num(r"3×(\d+)", title, 10)
        blk = _rep(n, [_effort("30″ δυνατά", 30, 1.12, "RPE 9/10, ο παλμός ανεβαίνει σταδιακά στο 90–95% HRmax"),
                       _free("15″ χαλαρά", 15, "Πολύ αργό τρέξιμο ή στάση")])
        sep = _free("Χαλαρό ανάμεσα στα σετ", 180, "3 λεπτά χαλαρό τρέξιμο")
        main = [blk, sep, _rep(n, [dict(x) for x in blk["steps"]]), dict(sep), _rep(n, [dict(x) for x in blk["steps"]])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Bakken ανηφόρες"):
        n = _num(r"(\d+)×", title, 15)
        sec = _num(r"×(\d+)″", title, 45)
        main = [_rep(n, [_effort("Απότομη ανηφόρα", sec, 1.14, "Πολύ δυνατά με καλή τεχνική, RPE 9/10"),
                         _free("Περπάτημα κάτω", 70, "Κατέβα περπατώντας, 60–75″")])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Bakken κατώφλι"):
        n = _num(r"(\d+)×", title, 10)
        main = [_rep(n, [_mstep("Κατώφλι LT2", 180, "lt2", lthr, hrmax, "«Σκληρό αλλά ελεγχόμενο», να μπορείς να κάνεις άλλα δύο"),
                         _free("Χαλαρό τρέξιμο", 60, "Ενεργή ανάκαμψη")])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Σκάλα κατωφλίου"):
        six = _num(r"(\d+)×6'", title, 3)
        ez = lambda s=60: _free("Χαλαρό τρέξιμο", s, "Ενεργή ανάκαμψη")  # noqa: E731
        main = [_rep(2, [_effort("Ζωηρά βήματα", 30, 1.08, "Χαλαρά γρήγορα, όχι σπριντ"), _step("Εύκολο", 120, "rec", lthr)])]
        if "10'+" in title:
            main += [_step("Κατώφλι 10′", 600, "ladder", lthr, "Λίγο κάτω από το κατώφλι, σταθερά"), ez(120)]
        main += [_rep(six, [_step("Κατώφλι 6′", 360, "ladder", lthr, "Λίγο κάτω από το κατώφλι"), ez()]),
                 _rep(3, [_step("Κατώφλι 3′", 180, "thresh", lthr, "Στο κατώφλι, σκληρό αλλά ελεγχόμενο"), ez()]),
                 _rep(3, [_effort("Ζωηρό 1′", 60, 1.05, "Λίγο πιο γρήγορα από το κατώφλι, RPE 8/10"), ez()])]
        return _wrap([warm(10)], main, [cool(10)], total, lthr)
    if title.startswith("Bakken μακρύ κατώφλι"):
        n = _num(r"(\d+)×", title, 5)
        m = _num(r"×(\d+)'", title, 6)
        main = [_rep(n, [_mstep("Υπο-κατώφλι", m * 60, "sublt", lthr, hrmax, "Σταθερή ένταση σε κυματιστό έδαφος, όχι αγώνας"),
                         _free("Πολύ αργό τρέξιμο", 90, "Ενεργή ανάκαμψη")])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Ανηφορικά σπριντ"):
        n = _num(r"(\d+)×", title, 8)
        main = [_rep(n, [_step("Σπριντ σε ανηφόρα", 12, "stride", lthr, "Απότομη ανηφόρα 8–12%, σχεδόν τέρμα, χαλαρό πάνω σώμα"),
                         _free("Περπάτημα κάτω", 108, "Πλήρης ανάκαμψη: περπάτα πίσω στην αφετηρία")])]
        return _wrap([warm(15)], main, [cool(5)], total, lthr)
    if title.startswith("Ανηφόρες VO2"):
        n = _num(r"(\d+)×", title, 5)
        m = _num(r"×(\d+)'", title, 3)
        main = [_rep(n, [_step("Ανηφόρα δυνατά", m * 60, "hill", lthr, "Κλίση 6–10%, δύσκολο αλλά σταθερό ως το τέλος"),
                         _free("Κατέβασμα χαλαρά", m * 60, "Τρέξιμο ή περπάτημα προς τα κάτω, πλήρης ανάκαμψη")])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Ανηφορικό κατώφλι"):
        n = _num(r"(\d+)×", title, 3)
        m = _num(r"×(\d+)'", title, 12)
        main = [_rep(n, [_step("Ανάβαση στο κατώφλι", m * 60, "thresh", lthr, "Συνεχής ανηφόρα. Όπου η κλίση ξεπερνά ~20%, γρήγορο περπάτημα με μπατόν"),
                         _free("Κατέβασμα", max(180, m * 30), "Χαλαρό κατέβασμα με καλή τεχνική")])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Ανάβαση tempo"):
        m = _num(r"tempo (\d+)'", title, 30)
        main = [_step("Συνεχής ανάβαση tempo", m * 60, "tempo", lthr, "Ρυθμός αγώνα στην ανηφόρα: τρέξιμο και power hiking στα απότομα"),
                _free("Κατηφόρα γρήγορα και ελεγχόμενα", max(600, m * 30), "Μικρά γρήγορα βήματα, χαλαρά γόνατα, μάτια 3–4 μ. μπροστά")]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Κατώφλι"):
        n = _num(r"(\d+)×", title, 4)
        m = _num(r"×(\d+)'", title, 8)
        main = [_rep(n, [_step("Κατώφλι", m * 60, "thresh", lthr), _step("Χαλαρό τρέξιμο", 120, "rec", lthr)])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Medium long"):
        return _wrap([warm(10)], [], [cool(5)], total, lthr, name="Σταθερό αερόβιο")
    if title.startswith("Ανηφόρες"):
        n = _num(r"(\d+)×", title, 5)
        main = [_rep(n, [_step("Ανηφόρα", 180, "hill", lthr),
                         _free("Κατηφόρα (τεχνική)", 180, "Μικρά γρήγορα βήματα, χαλαρά γόνατα")])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Tempo"):
        tm = _num(r"Tempo (\d+)", title, 20)
        return _wrap([warm(15)], [_step("Tempo", tm * 60, "tempo", lthr)], [cool(10)], total, lthr)
    if title.startswith("Διαλείμματα κατωφλίου"):
        n = _num(r"(\d+)×", title, 4)
        main = [_rep(n, [_step("Κατώφλι", 360, "thresh", lthr), _step("Εύκολο", 120, "rec", lthr)])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Κατηφόρες"):
        n = _num(r"(\d+)×", title, 4)
        main = [_rep(n, [_free("Κατηφόρα (τεχνική)", 90, "Κατηφόρα 6–10%, κορμός ελαφρά μπροστά, μάτια 3–4 μ. μπροστά"),
                         _step("Επιστροφή πάνω", 180, "easy", lthr)])]
        return _wrap([warm(15)], main, [cool(10)], total, lthr)
    if title.startswith("Ελαφρύ fartlek"):
        main = [_rep(6, [_step("Έντονο", 60, "thresh", lthr), _step("Εύκολο", 120, "rec", lthr)])]
        return _wrap([warm(10)], main, [cool(5)], total, lthr)
    if title.startswith("Ελαφριά ποιότητα"):
        main = [_rep(4, [_step("Ανηφόρα", 120, "hill", lthr), _step("Χαλαρά", 120, "rec", lthr)])]
        return _wrap([warm(10)], main, [cool(10)], total, lthr)
    if title.startswith("Μακρύ"):
        return _wrap([warm(10)], [], [cool(5)], total, lthr, name="Μακρύ τρέξιμο")
    if title.startswith("Ελαφρύ ξεμούδιασμα"):
        strides = [_rep(4, [_step("Ζωηρά βήματα", 20, "stride", lthr), _step("Εύκολο", 100, "rec", lthr)])]
        return _wrap([warm(5)], strides, [], total, lthr, before_main=True)
    return None
