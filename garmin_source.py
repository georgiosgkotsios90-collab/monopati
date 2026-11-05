"""Ανάγνωση δεδομένων από το Garmin Connect μέσω της ανεπίσημης βιβλιοθήκης garminconnect."""
from __future__ import annotations

from datetime import date, timedelta


class GarminError(RuntimeError):
    pass


def _get(obj, *path):
    """Ασφαλής πρόσβαση σε φωλιασμένα dict/list. Επιστρέφει None αν λείπει κάτι."""
    for p in path:
        try:
            obj = obj[p]
        except (KeyError, IndexError, TypeError):
            return None
    return obj


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def _login(email: str, password: str):
    from garminconnect import Garmin

    def ask_mfa():
        raise GarminError(
            "Ο λογαριασμός Garmin ζητά κωδικό επαλήθευσης 2 βημάτων (MFA), "
            "κάτι που δεν μπορεί να γίνει αυτόματα με κωδικό πρόσβασης."
        )

    try:
        api = Garmin(email, password, prompt_mfa=ask_mfa)
    except TypeError:  # παλαιότερη έκδοση χωρίς prompt_mfa
        api = Garmin(email, password)
    api.login()
    return api


def _normalize(raw) -> list[dict]:
    out = []
    for a in raw or []:
        start = a.get("startTimeLocal") or a.get("startTimeGMT") or ""
        if not start:
            continue
        hr = a.get("averageHR")
        out.append({
            "id": a.get("activityId"),
            "date": start[:10],
            "type": (_get(a, "activityType", "typeKey") or "").lower(),
            "name": a.get("activityName") or "",
            "km": round((a.get("distance") or 0) / 1000.0, 2),
            "gain": int(a.get("elevationGain") or 0),
            "loss": int(a.get("elevationLoss") or 0) if a.get("elevationLoss") is not None else None,
            "minutes": round((a.get("duration") or 0) / 60.0, 1),
            "avg_hr": int(hr) if hr else None,
        })
    return out


def login(email: str, password: str):
    return _login(email, password)


def fetch(email: str, password: str, today: date, days: int = 120, api=None) -> tuple[list[dict], dict]:
    """Επιστρέφει (δραστηριότητες, δείκτες ευεξίας). Οι δείκτες ευεξίας είναι προαιρετικοί."""
    api = api or _login(email, password)
    start = today - timedelta(days=days)
    acts = _normalize(api.get_activities_by_date(start.isoformat(), today.isoformat()))

    d = today.isoformat()
    ready = _safe(api.get_training_readiness, d)
    if isinstance(ready, list):
        ready = ready[0] if ready else None
    sleep = _safe(api.get_sleep_data, d)
    rhr = _safe(api.get_rhr_day, d)
    hrv = _safe(api.get_hrv_data, d)
    summary = _safe(api.get_user_summary, d)

    wellness = {
        "readiness": _get(ready, "score"),
        "sleep_score": _get(sleep, "dailySleepDTO", "sleepScores", "overall", "value"),
        "resting_hr": _get(rhr, "allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE", 0, "value"),
        "hrv": _get(hrv, "hrvSummary", "lastNightAvg"),
        "hrv_status": _get(hrv, "hrvSummary", "status"),
        "hrv_baseline_low": _get(hrv, "hrvSummary", "baseline", "balancedLow"),
        "hrv_weekly": _get(hrv, "hrvSummary", "weeklyAvg"),
        "resting_hr_7d": _get(summary, "lastSevenDaysAvgRestingHeartRate"),
    }
    if wellness.get("resting_hr") is None:
        wellness["resting_hr"] = _get(summary, "restingHeartRate")
    return acts, {k: v for k, v in wellness.items() if v is not None}
