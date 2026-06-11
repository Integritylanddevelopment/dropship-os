"""Trend velocity over 3/7/14-day windows.

Given a list of signals with `created_utc`, compute counts in each window and the
acceleration ratio. Higher acceleration = earlier in the wave."""
import time

def _epoch_now() -> float:
    return time.time()

def window_counts(signals: list[dict], now: float | None = None) -> dict:
    now = now or _epoch_now()
    DAY = 86400
    counts = {"3d": 0, "7d": 0, "14d": 0}
    for s in signals:
        ts = s.get("created_utc")
        if not ts:
            continue
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            continue
        age = now - ts
        if age < 3 * DAY:
            counts["3d"] += 1
        if age < 7 * DAY:
            counts["7d"] += 1
        if age < 14 * DAY:
            counts["14d"] += 1
    return counts

def velocity_score(signals: list[dict]) -> float:
    """0..1 score. Rises fast over 3d relative to 14d = high score."""
    c = window_counts(signals)
    d14 = max(c["14d"], 1)
    d3 = c["3d"]
    d7 = c["7d"]
    # acceleration: a young distribution skews to short windows
    # ideal early wave: d3/d14 > 0.5 (3 of 14 days carry >50% of mentions)
    accel = d3 / d14
    breadth = min(1.0, d7 / 7.0)  # at least one signal per day in last week
    return min(1.0, 0.7 * accel + 0.3 * breadth)