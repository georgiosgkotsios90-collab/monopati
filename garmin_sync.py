"""Στέλνει τις προπονήσεις του προγράμματος στο ημερολόγιο του Garmin Connect, ώστε να περνούν στο ρολόι.

Κάθε πρωί:
  1. σβήνει τις προπονήσεις που είχε ανεβάσει το Μονοπάτι (όνομα που αρχίζει με PREFIX),
  2. ανεβάζει τις προπονήσεις τρεξίματος των επόμενων ημερών με βήματα και στόχο παλμών,
  3. τις προγραμματίζει στην ημερομηνία τους και ζητά αποστολή στις συσκευές.
Στο ρολόι, όταν ξεκινάς Τρέξιμο, εμφανίζεται η σημερινή προπόνηση· πατάς έναρξη και σε καθοδηγεί.
Ό,τι άλλο υπάρχει στο Garmin Connect δεν πειράζεται.
"""
from __future__ import annotations

from datetime import date, timedelta

PREFIX = "Μονοπάτι · "
RUNNING = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
STEP = {
    "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery", "displayOrder": 4},
    "repeat": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
}
TIME = {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True}
ITER = {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False}
NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}
HR_TARGET = {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone", "displayOrder": 1}


def _kind(s: dict, in_repeat: bool, first_in_repeat: bool) -> str:
    name = s.get("name", "")
    if name.startswith("Ζέσταμα"):
        return "warmup"
    if name.startswith("Αποψύχρανση"):
        return "cooldown"
    if in_repeat and not first_in_repeat and (s.get("hr") is None or (s.get("lvl") or 0) < 0.75):
        return "recovery"
    return "interval"


def _steps(steps: list, counter: list[int], in_repeat: bool = False) -> list[dict]:
    out = []
    for idx, s in enumerate(steps):
        counter[0] += 1
        order = counter[0]
        if "repeat" in s:
            out.append({
                "type": "RepeatGroupDTO", "stepOrder": order, "stepType": STEP["repeat"],
                "numberOfIterations": int(s["repeat"]), "smartRepeat": False,
                "endCondition": ITER, "endConditionValue": float(s["repeat"]),
                "workoutSteps": _steps(s["steps"], counter, True),
            })
            continue
        st = {
            "type": "ExecutableStepDTO", "stepOrder": order,
            "stepType": STEP[_kind(s, in_repeat, idx == 0)],
            "endCondition": TIME, "endConditionValue": float(s["sec"]),
            "targetType": NO_TARGET,
        }
        # Στόχος παλμών μόνο σε βήματα ≥ 90″: στα σύντομα σπριντ οι παλμοί αργούν και θα χτυπούσε άσκοπα.
        if s.get("hr") and s["sec"] >= 90:
            st["targetType"] = HR_TARGET
            st["targetValueOne"] = float(s["hr"][0])
            st["targetValueTwo"] = float(s["hr"][1])
        note = " · ".join(x for x in (s.get("name"), s.get("note")) if x)
        if note:
            st["description"] = note[:250]
        out.append(st)
    return out


def total_sec(steps: list) -> int:
    return int(sum(s["repeat"] * total_sec(s["steps"]) if "repeat" in s else s["sec"] for s in steps))


def to_garmin(day: dict) -> dict:
    counter = [0]
    return {
        "workoutName": (PREFIX + day["title"])[:60],
        "description": day.get("desc", "")[:1000],
        "sportType": RUNNING,
        "estimatedDurationInSecs": total_sec(day["steps"]),
        "workoutSegments": [{"segmentOrder": 1, "sportType": RUNNING, "workoutSteps": _steps(day["steps"], counter)}],
    }


def _list(res) -> list:
    if isinstance(res, dict):
        for k in ("workouts", "workoutList", "items"):
            if isinstance(res.get(k), list):
                return res[k]
        return []
    return res or []


def sync(api, plan: list[dict], today: date, days: int = 7) -> dict:
    """Επιστρέφει {"deleted": n, "scheduled": [ημερομηνίες]}."""
    deleted = 0
    start = 0
    while True:
        batch = _list(api.get_workouts(start, 100))
        for w in batch:
            if str(w.get("workoutName", "")).startswith(PREFIX):
                api.delete_workout(w["workoutId"])
                deleted += 1
        if len(batch) < 100:
            break
        start += 100

    last = today + timedelta(days=days - 1)
    scheduled = []
    for w in plan:
        for d in w["days"]:
            dd = date.fromisoformat(d["date"])
            if not (today <= dd <= last) or d.get("done") or d.get("kind") == "race":
                continue
            if not d.get("steps") or (d.get("km") or 0) <= 0:
                continue
            res = api.upload_workout(to_garmin(d))
            wid = (res or {}).get("workoutId")
            if not wid:
                raise RuntimeError(f"Το Garmin δεν επέστρεψε workoutId για {d['date']}")
            api.schedule_workout(wid, d["date"])
            scheduled.append(d["date"])
    try:
        api.send_scheduled_workouts_to_devices()
    except Exception:  # προαιρετικό: το ρολόι τις παίρνει και με τον κανονικό συγχρονισμό
        pass
    return {"deleted": deleted, "scheduled": scheduled}
