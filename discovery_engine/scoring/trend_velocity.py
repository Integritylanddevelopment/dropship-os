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
    """0..1 score. Rises fast over 3d relative to 14d = high score.

    When all timestamps are stale (>30d old, e.g. from frozen Pullpush data),
    falls back to engagement-based velocity: high-scoring posts with many
    comments indicate PAST velocity even if we can't measure recency.
    """
    c = window_counts(signals)
    d14 = max(c["14d"], 1)
    d3 = c["3d"]
    d7 = c["7d"]

    # Check if we have ANY recent signals
    has_recent = c["14d"] > 0

    if has_recent:
        # Normal recency-based velocity
        accel = d3 / d14
        breadth = min(1.0, d7 / 7.0)
        return min(1.0, 0.7 * accel + 0.3 * breadth)

    # Fallback: engagement-based velocity for stale timestamps
    # High scores + high comment counts = product HAD velocity
    # Cap at 0.4 since we can't confirm it's CURRENT
    scores = [s.get("score") or 0 for s in signals]
    comments = [s.get("comments") or 0 for s in signals]
    if not scores:
        return 0.0
    avg_score = sum(scores) / len(scores)
    avg_comments = sum(comments) / len(comments)
    # Normalize: 100+ avg score = strong engagement
    score_factor = min(1.0, avg_score / 100.0)
    comment_factor = min(1.0, avg_comments / 30.0)
    return min(0.4, 0.6 * score_factor + 0.4 * comment_factor)