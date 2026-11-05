"""Προσωπικό μοντέλο κλίσης, αντοχή στην κόπωση (durability) και πρόβλεψη χρόνου αγώνα.

Όλα βγαίνουν από τα δικά σου τρεξίματα στο Garmin, όχι από μέσους όρους πληθυσμού.

1. Κάθε τρέξιμο σπάει σε κομμάτια των ~200 m (οριζόντια απόσταση). Για κάθε κομμάτι κρατάμε κλίση,
   ταχύτητα, μέσους παλμούς και σε ποιο λεπτό του τρεξίματος έγινε. Οι στάσεις πετιούνται.
2. Μοντέλο κλίσης: για κάθε «κουτί» κλίσης (π.χ. 7–12%) η ταχύτητά σου στα τρεξίματα αντοχής
   (≥ 70 λεπτά, όχι διαλειμματικές). Το 50ό εκατοστημόριο είναι το «ρεαλιστικό», το 65ο το «αισιόδοξο»,
   το 35ο το «συντηρητικό». Όπου δεν υπάρχουν αρκετά δεδομένα, χρησιμοποιείται γενική καμπύλη (τύπου GAP)
   προσαρμοσμένη στη δική σου ταχύτητα στο επίπεδο.
3. Κόπωση: πόσο πέφτει η ταχύτητά σου (σε σχέση με το μοντέλο) ανά ώρα μετά τις 2 πρώτες ώρες,
   από τα τρεξίματα ≥ 2,5 ωρών.
4. Durability: αποσύνδεση ρυθμού–παλμών (decoupling) στα τρεξίματα ≥ 90 λεπτών. Συγκρίνει την
   «απόδοση» (ταχύτητα προσαρμοσμένη στην κλίση ανά παλμό) στο πρώτο και στο δεύτερο μισό.
   Κάτω από ~5% θεωρείται συνήθως καλή αερόβια αντοχή.
5. Πρόβλεψη: για κάθε σκέλος του αγώνα (σταθμός σε σταθμό) χρόνος = ανηφόρα / v(κλίση ανηφόρας)
   + κατηφόρα / v(κλίση κατηφόρας), με κόπωση ανά ώρα και στάσεις στους σταθμούς.
"""
from __future__ import annotations

import math
import random
import statistics
from datetime import date, timedelta

SEG_M = 200            # μήκος κομματιού (οριζόντια μέτρα)
DAYS = 180             # πόσο πίσω κοιτάμε
MAX_NEW = 40           # πόσες νέες δραστηριότητες κατεβάζουμε ανά ενημέρωση
MIN_BIN = 10           # ελάχιστα κομμάτια σε ένα κουτί για να μετρήσει το προσωπικό μοντέλο
ENDURANCE_MIN = 70     # λεπτά: από εκεί και πάνω ένα τρέξιμο μετρά ως «αντοχής»
LONG_MIN = 90          # λεπτά: από εκεί και πάνω υπολογίζεται decoupling

# Κέντρα κουτιών κλίσης (%) και γενικός συντελεστής κόστους (1 = επίπεδο), τύπου GAP.
CENTERS = [-35, -25, -18, -12, -7, -3, 0, 3, 7, 12, 18, 25, 35]
DEFAULT_COST = {-40: 1.6, -35: 1.45, -30: 1.3, -25: 1.17, -20: 1.05, -15: 0.95, -9: 0.88, -5: 0.9,
                0: 1.0, 5: 1.2, 10: 1.45, 15: 1.75, 20: 2.05, 25: 2.4, 30: 2.75, 35: 3.1, 40: 3.5}


def _interp(table: dict, x: float) -> float:
    ks = sorted(table)
    if x <= ks[0]:
        return table[ks[0]]
    if x >= ks[-1]:
        return table[ks[-1]]
    for a, b in zip(ks, ks[1:]):
        if a <= x <= b:
            t = (x - a) / (b - a)
            return table[a] + (table[b] - table[a]) * t
    return 1.0


def default_cost(g: float) -> float:
    return _interp(DEFAULT_COST, g)


def _edges():
    mids = [(a + b) / 2 for a, b in zip(CENTERS, CENTERS[1:])]
    return [-1e9] + mids + [1e9]


EDGES = _edges()


def bin_of(g: float) -> int:
    for i in range(len(CENTERS)):
        if EDGES[i] <= g < EDGES[i + 1]:
            return i
    return len(CENTERS) - 1


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def is_run_type(t: str) -> bool:
    t = (t or "").lower()
    return "run" in t and "treadmill" not in t and "indoor" not in t and "virtual" not in t


# --- 1. Από τα δεδομένα του Garmin σε κομμάτια ------------------------------------------------
def _pow10(x: float) -> float:
    """Στρογγυλεύει έναν λόγο κλίμακας στη πλησιέστερη δύναμη του 10 (για μονάδες cm/m, ms/s κ.λπ.)."""
    if not x or x <= 0 or not math.isfinite(x):
        return 1.0
    return 10.0 ** round(math.log10(x))


def parse_details(details: dict, act: dict) -> dict | None:
    """Μετατρέπει την απάντηση get_activity_details σε κομμάτια [κλίση‰, ταχύτητα cm/s, παλμοί, λεπτό]."""
    idx = {}
    for d in (details or {}).get("metricDescriptors") or []:
        k, i = d.get("key"), d.get("metricsIndex")
        if isinstance(k, str) and isinstance(i, int) and not isinstance(i, bool) and i >= 0:
            idx[k] = i
    rows = (details or {}).get("activityDetailMetrics") or []
    if "sumDistance" not in idx or "directElevation" not in idx or not rows:
        return None
    tkey = "sumDuration" if "sumDuration" in idx else "sumElapsedDuration" if "sumElapsedDuration" in idx else "directTimestamp"
    if tkey not in idx:
        return None

    def val(r, k):
        m = r.get("metrics") or []
        i = idx.get(k)
        return m[i] if i is not None and i < len(m) else None

    pts = []
    for r in rows:
        t, d, e = val(r, tkey), val(r, "sumDistance"), val(r, "directElevation")
        if t is None or d is None or e is None:
            continue
        pts.append([float(t), float(d), float(e), val(r, "directHeartRate")])
    if len(pts) < 20:
        return None
    pts.sort(key=lambda p: p[0])
    t0 = pts[0][0]
    for p in pts:
        p[0] -= t0
    # Μονάδες: σύγκριση με τα σύνολα της δραστηριότητας (απόσταση, διάρκεια).
    dscale = _pow10((act.get("km") or 0) * 1000.0 / pts[-1][1]) if pts[-1][1] else 1.0
    tscale = _pow10((act.get("minutes") or 0) * 60.0 / pts[-1][0]) if pts[-1][0] else 1.0
    raw_gain = sum(max(0.0, b[2] - a[2]) for a, b in zip(pts, pts[1:]))
    escale = _pow10((act.get("gain") or 0) / raw_gain) if raw_gain and act.get("gain") else 1.0
    if escale > 1:  # το θόρυβο τον έχει μόνο η σειρά, οπότε μόνο σμίκρυνση (π.χ. εκατοστά) έχει νόημα
        escale = 1.0
    for p in pts:
        p[0] *= tscale
        p[1] *= dscale
        p[2] *= escale
    # Εξομάλυνση υψομέτρου (κινητός μέσος 5 σημείων).
    ele = [p[2] for p in pts]
    sm = []
    for i in range(len(ele)):
        w = ele[max(0, i - 2): i + 3]
        sm.append(sum(w) / len(w))

    segs = []
    i0 = 0
    for i in range(1, len(pts)):
        dd = pts[i][1] - pts[i0][1]
        if dd < SEG_M:
            continue
        dt = pts[i][0] - pts[i0][0]
        if dt > 0:
            v = dd / dt
            hrs = [p[3] for p in pts[i0:i + 1] if p[3]]
            hr = round(sum(hrs) / len(hrs)) if hrs else 0
            g = (sm[i] - sm[i0]) / dd * 100.0
            if 0.5 <= v <= 7.0 and -60 <= g <= 60:  # στάσεις και λάθη GPS έξω
                segs.append([round(g * 10), round(v * 100), hr, round(pts[i0][0] / 60.0, 1), round(dt)])
        i0 = i
    if len(segs) < 5:
        return None
    return {"id": act.get("id"), "date": act["date"], "type": act.get("type"), "name": act.get("name", ""),
            "minutes": act.get("minutes"), "km": act.get("km"), "gain": act.get("gain"),
            "avg_hr": act.get("avg_hr"), "segs": segs}


def update_cache(cache: dict, acts: list[dict], api, today: date, log=print) -> int:
    """Κατεβάζει λεπτομέρειες για τρεξίματα που δεν υπάρχουν ακόμα στην cache (νεότερα πρώτα)."""
    store = cache.setdefault("acts", {})
    since = (today - timedelta(days=DAYS)).isoformat()
    for k in [k for k, a in store.items() if a.get("date", "") < since]:
        del store[k]
    tried = cache.setdefault("failed", {})  # id → ημερομηνία τελευταίας αποτυχίας· ξαναδοκιμάζεται μετά από 7 μέρες
    retry_after = (today - timedelta(days=7)).isoformat()
    todo = [a for a in sorted(acts, key=lambda a: a["date"], reverse=True)
            if a.get("id") and is_run_type(a.get("type")) and a["date"] >= since
            and str(a["id"]) not in store and tried.get(str(a["id"]), "") < retry_after
            and (a.get("minutes") or 0) >= 20]
    n = 0
    for a in todo[:MAX_NEW]:
        try:
            det = api.get_activity_details(str(a["id"]), maxchart=4000, maxpoly=0)
            res = parse_details(det, a)
        except Exception as e:  # μία δραστηριότητα που αποτυγχάνει δεν σταματά τις υπόλοιπες
            log(f"[terrain] {a['date']} {a.get('name', '')}: {type(e).__name__}: {e}")
            res = None
        if res:
            store[str(a["id"])] = res
            n += 1
        else:
            tried[str(a["id"])] = today.isoformat()
    return n


# --- 2. Μοντέλο κλίσης ----------------------------------------------------------------------------
def _endurance(a: dict, lthr: int) -> bool:
    if (a.get("minutes") or 0) < ENDURANCE_MIN:
        return False
    hr = a.get("avg_hr")
    return not hr or hr <= 0.93 * lthr


def build_model(runs: list[dict], lthr: int) -> dict:
    speeds: list[list[float]] = [[] for _ in CENTERS]
    run_ids: list[set] = [set() for _ in CENTERS]
    for a in runs:
        if not _endurance(a, lthr):
            continue
        for g10, v100, hr, tmin, dt in a["segs"]:
            if tmin < 5 or tmin > 360 or (hr and hr > 0.97 * lthr):
                continue
            b = bin_of(g10 / 10.0)
            speeds[b].append(v100 / 100.0)
            run_ids[b].add(a["date"])
    flat_i = CENTERS.index(0)
    near_flat = speeds[flat_i] + speeds[flat_i - 1] + speeds[flat_i + 1]
    v0 = statistics.median(near_flat) if len(near_flat) >= MIN_BIN else 2.6
    bins = []
    for i, g in enumerate(CENTERS):
        xs = speeds[i]
        if len(xs) >= MIN_BIN and len(run_ids[i]) >= 2:
            p35, p50, p65 = _pct(xs, 0.35), _pct(xs, 0.5), _pct(xs, 0.65)
            src = "personal"
        else:
            p50 = v0 / default_cost(g)
            p35, p65 = p50 * 0.9, p50 * 1.1
            src = "default"
        bins.append({"g": g, "n": len(xs), "runs": len(run_ids[i]), "src": src,
                     "p35": round(p35, 3), "p50": round(p50, 3), "p65": round(p65, 3)})
    # Κουτιά χωρίς αρκετά δεδομένα: γενική καμπύλη, αλλά ξεκινώντας από την πλησιέστερη προσωπική κλίση
    # (π.χ. το 25% βγαίνει από τη δική σου ταχύτητα στο 18%, όχι από το επίπεδο).
    pers = [i for i, b in enumerate(bins) if b["src"] == "personal"]
    for i, b in enumerate(bins):
        if b["src"] == "personal" or not pers:
            continue
        j = min(pers, key=lambda q: (abs(q - i), 0 if (CENTERS[q] >= 0) == (CENTERS[i] >= 0) else 1))
        r = default_cost(CENTERS[j]) / default_cost(CENTERS[i])
        for key in ("p35", "p50", "p65"):
            b[key] = round(bins[j][key] * r, 3)
        b["src"] = "scaled"
    # Στην ανηφόρα η ταχύτητα δεν μπορεί να ανεβαίνει όσο ανεβαίνει η κλίση.
    for key in ("p35", "p50", "p65"):
        for i in range(flat_i + 1, len(bins)):
            bins[i][key] = min(bins[i][key], bins[i - 1][key])
    model = {"v0": round(v0, 3), "bins": bins,
             "personal": sum(1 for b in bins if b["src"] == "personal"),
             "runs": len({a["date"] for a in runs if _endurance(a, lthr)})}
    model["fatigue"] = fatigue_rate(runs, model)
    return model


def speed(model: dict, g: float, key: str = "p50") -> float:
    """Ταχύτητα (m/s) για κλίση g (%) με γραμμική παρεμβολή ανάμεσα στα κέντρα των κουτιών."""
    bs = model["bins"]
    if g <= bs[0]["g"]:
        v = bs[0][key] * default_cost(bs[0]["g"]) / default_cost(g)
        return max(0.15, v)
    if g >= bs[-1]["g"]:
        return max(0.15, bs[-1][key] * default_cost(bs[-1]["g"]) / default_cost(g))
    for a, b in zip(bs, bs[1:]):
        if a["g"] <= g <= b["g"]:
            t = (g - a["g"]) / (b["g"] - a["g"])
            return a[key] + (b[key] - a[key]) * t
    return model["v0"]


def cost(model: dict, g: float) -> float:
    """Προσωπικός συντελεστής κόστους: πόσο πιο αργά πας σε κλίση g σε σχέση με το επίπεδο."""
    return model["v0"] / max(0.15, speed(model, g))


def fatigue_rate(runs: list[dict], model: dict) -> dict:
    """Πτώση ταχύτητας ανά ώρα (κλάσμα) μετά τις 2 ώρες, από τα τρεξίματα ≥ 150 λεπτών."""
    rates = []
    for a in runs:
        if (a.get("minutes") or 0) < 150:
            continue
        pts = [(tmin / 60.0, (v100 / 100.0) / speed(model, g10 / 10.0)) for g10, v100, hr, tmin, dt in a["segs"]
               if -25 <= g10 / 10.0 <= 30 and tmin >= 10]
        early = [r for h, r in pts if h < 1.5]
        late = [(h, r) for h, r in pts if h >= 1.5]
        if len(early) < 10 or len(late) < 10:
            continue
        base = statistics.median(early)
        xs = [h for h, _ in late]
        ys = [r / base for _, r in late]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        var = sum((x - mx) ** 2 for x in xs)
        if var <= 0:
            continue
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
        rates.append((max(0.0, min(0.12, -slope)), a["minutes"], a["date"]))
    if not rates:
        return {"per_hour": 0.04, "src": "default", "runs": 0}
    w = sum(m for _, m, _ in rates)
    k = sum(r * m for r, m, _ in rates) / w
    return {"per_hour": round(max(0.01, min(0.10, k)), 3), "src": "personal", "runs": len(rates)}


# --- 3. Durability ----------------------------------------------------------------------------
def decoupling(a: dict, model: dict) -> dict | None:
    segs = [s for s in a["segs"] if s[3] >= 10 and s[2] and -10 <= s[0] / 10.0 <= 30]
    if len(segs) < 12:
        return None
    end = max(s[3] for s in segs)
    half = (10 + end) / 2

    def eff(part):
        tt = sum(s[4] for s in part)
        if tt <= 0:
            return None, None
        vg = sum((s[1] / 100.0) * cost(model, s[0] / 10.0) * s[4] for s in part) / tt
        hr = sum(s[2] * s[4] for s in part) / tt
        return vg / hr, hr

    e1, h1 = eff([s for s in segs if s[3] < half])
    e2, h2 = eff([s for s in segs if s[3] >= half])
    if not e1 or not e2:
        return None
    return {"date": a["date"], "name": a.get("name", ""), "minutes": a.get("minutes"), "km": a.get("km"),
            "gain": a.get("gain"), "decoupling": round((e1 - e2) / e1 * 100, 1),
            "hr1": round(h1), "hr2": round(h2)}


def durability(runs: list[dict], model: dict) -> dict:
    items = []
    for a in sorted(runs, key=lambda x: x["date"]):
        if (a.get("minutes") or 0) >= LONG_MIN:
            d = decoupling(a, model)
            if d:
                items.append(d)
    items = items[-16:]
    recent = [x["decoupling"] for x in items[-4:]]
    return {"runs": items, "recent": round(statistics.median(recent), 1) if recent else None}


# --- 4. Πρόβλεψη αγώνα ------------------------------------------------------------------------
SCEN = {
    "opt": {"label": "Αισιόδοξο", "key": "p65", "fat": 0.7, "stop": 1.0},
    "real": {"label": "Ρεαλιστικό", "key": "p50", "fat": 1.0, "stop": 2.0},
    "cons": {"label": "Συντηρητικό", "key": "p35", "fat": 1.4, "stop": 4.0},
}


def _leg_parts(km: float, gain: float, loss: float) -> list[tuple[float, float]]:
    """Χωρίζει ένα σκέλος σε ανηφόρα και κατηφόρα: [(μέτρα, κλίση %)]."""
    m = km * 1000.0
    if m <= 0:
        return []
    gain, loss = max(0.0, gain), max(0.0, loss)
    if gain + loss < 1:
        return [(m, 0.0)]
    up = m * gain / (gain + loss)
    dn = m - up
    out = []
    if up > 1:
        out.append((up, min(45.0, gain / up * 100.0)))
    if dn > 1:
        out.append((dn, -min(45.0, loss / dn * 100.0)))
    return out


def predict(model: dict, checkpoints: list[dict], start: str = "06:05", calib: float = 1.0, start_alt: float = 0.0) -> dict:
    out = {}
    for sk, sc in SCEN.items():
        t = 0.0  # λεπτά
        rows = []
        prev_km, prev_alt, prev_asc = 0.0, float(start_alt), 0.0
        k = model["fatigue"]["per_hour"] * sc["fat"]
        for cp in checkpoints:
            km, alt, asc = cp["km"], cp["alt"], cp["asc"]
            gain = asc - prev_asc
            loss = gain - (alt - prev_alt)
            for meters, g in _leg_parts(km - prev_km, gain, loss):
                steps = max(1, int(meters // 250))
                for _ in range(steps):
                    hours = t / 60.0
                    slow = 1.0 + k * max(0.0, hours - 2.0)
                    v = speed(model, g, sc["key"]) / slow
                    t += (meters / steps) / v / 60.0
            arrive = t * (calib if sk == "real" else 1.0)
            last = cp is checkpoints[-1]
            rows.append({"name": cp["name"], "km": km, "alt": alt, "asc": asc,
                         "at": round(arrive), "cutoff": cp.get("cutoff")})
            if not last:
                t += sc["stop"]
            prev_km, prev_alt, prev_asc = km, alt, asc
        total = rows[-1]["at"]
        out[sk] = {"label": sc["label"], "minutes": total, "rows": rows}
    # Ώρα ημέρας και περιθώριο από τα όρια αποκλεισμού (με βάση το συντηρητικό σενάριο).
    h0, m0 = (int(x) for x in start.split(":"))
    for sk in out:
        for r in out[sk]["rows"]:
            tod = h0 * 60 + m0 + r["at"]
            r["clock"] = f"{(tod // 60) % 24:02d}:{tod % 60:02d}"
            if r.get("cutoff"):
                ch, cm = (int(x) for x in r["cutoff"].split(":"))
                r["margin"] = ch * 60 + cm - r["at"]
    return {"start": start, "scenarios": out, "calib": round(calib, 3)}


def calibrate(runs: list[dict], model: dict) -> dict | None:
    """Έλεγχος μοντέλου: πόσο θα πρόβλεπε για τα δικά σου τρεξίματα ≥ 4 ωρών, σε σχέση με τον πραγματικό χρόνο κίνησης."""
    checks = []
    k = model["fatigue"]["per_hour"]
    for a in runs:
        if (a.get("minutes") or 0) < 240:
            continue
        t = 0.0
        actual = 0.0
        for g10, v100, hr, tmin, dt in a["segs"]:
            d = v100 / 100.0 * dt
            slow = 1.0 + k * max(0.0, t / 60.0 - 2.0)
            t += d / (speed(model, g10 / 10.0) / slow) / 60.0
            actual += dt / 60.0
        if t > 0:
            checks.append({"date": a["date"], "name": a.get("name", ""), "km": a.get("km"),
                           "pred": round(t), "actual": round(actual), "ratio": actual / t})
    if not checks:
        return None
    ratio = statistics.median(c["ratio"] for c in checks)
    return {"ratio": round(max(0.85, min(1.2, ratio)), 3), "checks": checks[-3:]}


# --- Όλα μαζί ----------------------------------------------------------------------------------
def build(cache: dict, cfg: dict, today: date) -> dict | None:
    lthr = int(cfg.get("lthr") or 155)
    since = (today - timedelta(days=DAYS)).isoformat()
    runs = [a for a in (cache.get("acts") or {}).values() if a.get("date", "") >= since and a.get("segs")]
    if not runs:
        return None
    model = build_model(runs, lthr)
    dura = durability(runs, model)
    cal = calibrate(runs, model)
    out = {"model": model, "durability": dura, "calibration": cal, "analysed": len(runs)}
    cps = cfg.get("race_checkpoints")
    if cps:
        pred = predict(model, cps, cfg.get("race_start", "06:05"), cal["ratio"] if cal else 1.0, cfg.get("race_start_alt", 0))
        pred["source"] = cfg.get("race_checkpoints_source")
        hist = cache.setdefault("pred_hist", {})
        hist[today.isoformat()] = pred["scenarios"]["real"]["minutes"]
        for k in sorted(hist)[:-120]:
            del hist[k]
        pred["history"] = [{"date": k, "minutes": hist[k]} for k in sorted(hist)]
        out["prediction"] = pred
    return out


# --- Δοκιμαστικά δεδομένα ------------------------------------------------------------------------
def demo_cache(acts: list[dict], seed: int = 3) -> dict:
    """Ψεύτικα κομμάτια για τα ψεύτικα τρεξίματα του update.py --demo."""
    rnd = random.Random(seed)
    store = {}
    for n, a in enumerate(acts):
        if not is_run_type(a.get("type")):
            continue
        meters = (a.get("km") or 0) * 1000.0
        gain = a.get("gain") or 0
        segs, t = [], 0.0
        nseg = max(5, int(meters // SEG_M))
        # Εναλλασσόμενες ανηφόρες και κατηφόρες με μέση κλίση που δίνει την υψομετρική του τρεξίματος.
        mean_up = gain / (meters / 2) * 100 if meters else 0
        for i in range(nseg):
            up = (i // 6) % 2 == 0
            g = (mean_up * rnd.uniform(0.4, 1.6)) * (1 if up else -1) + rnd.uniform(-2, 2)
            hours = t / 3600
            v = 2.85 / default_cost(g) * (1 - 0.035 * max(0, hours - 2)) * rnd.uniform(0.9, 1.1)
            v = max(0.5, v)
            dt = SEG_M / v
            hr = int(138 + 12 * min(1.5, max(-0.5, default_cost(g) - 1)) + 2.5 * hours + rnd.uniform(-4, 4))
            segs.append([round(g * 10), round(v * 100), hr, round(t / 60, 1), round(dt)])
            t += dt
        store[f"demo{n}"] = {"id": f"demo{n}", "date": a["date"], "type": a["type"], "name": a.get("name", ""),
                             "minutes": round(t / 60, 1), "km": a.get("km"), "gain": gain,
                             "avg_hr": a.get("avg_hr"), "segs": segs}
    return {"acts": store}
