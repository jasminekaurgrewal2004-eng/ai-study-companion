"""
analytics/ml/study_time.py
===========================
Compute per-user peak study-focus window from activity timestamps.

Pipeline
--------
1. Collect timestamps from ChatHistory, FlashcardReview, QuizAttempt.
2. Convert UTC → local timezone (default Asia/Kolkata).
3. Build a 7×24 weighted count matrix:
      weight = 0.6 * log1p_activity  +  0.4 * avg_quiz_score_at_hour
   Fallback to activity-only when no quiz data exist.
4. Run statsmodels seasonal_decompose (period=24) on the hourly series.
5. Detect the best contiguous 2-3 h block and top-3 peak weekdays.
6. confidence = min(1.0, n_events / 50)
7. Optional Prophet forecast if ≥30 days history (silently skipped otherwise).

Public API
----------
compute_pattern(user_id: int) -> StudyPattern
get_recommendation(user_id: int) -> dict
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

_LOCAL_TZ = "Asia/Kolkata"
_MIN_EVENTS_FOR_RESULT = 10
_CONFIDENCE_TARGET = 50          # events needed for confidence = 1.0
_PEAK_WINDOW_MIN = 2             # minimum block length (hours)
_PEAK_WINDOW_MAX = 3             # maximum block length (hours)

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DAY_SHORT  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _collect_timestamps(user_id: int) -> tuple[list[datetime], dict[int, float]]:
    """
    Return (timestamps_local, hour_to_avg_score).

    timestamps_local : list of timezone-aware datetimes in Asia/Kolkata
    hour_to_avg_score: {local_hour: mean quiz score 0-100} — empty if no quizzes
    """
    import zoneinfo
    from django.contrib.auth.models import User
    from core.models import ChatHistory, FlashcardReview, QuizAttempt

    tz = zoneinfo.ZoneInfo(_LOCAL_TZ)
    timestamps: list[datetime] = []

    # --- ChatHistory ---
    for ts in ChatHistory.objects.filter(user_id=user_id).values_list("timestamp", flat=True):
        timestamps.append(ts.astimezone(tz))

    # --- FlashcardReview ---
    for ts in FlashcardReview.objects.filter(user_id=user_id).values_list("reviewed_at", flat=True):
        timestamps.append(ts.astimezone(tz))

    # --- QuizAttempt (also builds hour→score map) ---
    hour_scores: dict[int, list[float]] = {}
    for ts, score in QuizAttempt.objects.filter(user_id=user_id).values_list("attempted_at", "score"):
        local_ts = ts.astimezone(tz)
        timestamps.append(local_ts)
        hour_scores.setdefault(local_ts.hour, []).append(float(score))

    hour_to_avg: dict[int, float] = {h: float(np.mean(v)) for h, v in hour_scores.items()}
    return timestamps, hour_to_avg


def _build_matrix(timestamps: list[datetime], hour_to_avg: dict[int, float]) -> np.ndarray:
    """
    Return a (7, 24) float32 weight matrix normalised to [0, 1].

    Rows = weekday (0=Mon … 6=Sun), Columns = hour (0-23).
    weight = 0.6 * activity_norm  +  0.4 * quiz_score_norm
    Falls back to activity-only when no quiz data.
    """
    raw = np.zeros((7, 24), dtype=np.float32)
    for dt in timestamps:
        raw[dt.weekday(), dt.hour] += 1.0

    # log1p activity
    activity = np.log1p(raw)
    act_max = activity.max()
    if act_max > 0:
        activity /= act_max

    if not hour_to_avg:
        return activity

    # quiz-score layer (per hour, broadcast across days)
    score_vec = np.zeros(24, dtype=np.float32)
    for h, s in hour_to_avg.items():
        score_vec[h] = s / 100.0          # normalise to 0-1
    score_layer = np.tile(score_vec, (7, 1))

    combined = 0.6 * activity + 0.4 * score_layer
    m = combined.max()
    return (combined / m).astype(np.float32) if m > 0 else combined


def _hourly_series(matrix: np.ndarray) -> np.ndarray:
    """Flatten 7×24 to a 168-length series (Mon-0 … Sun-23)."""
    return matrix.flatten()


def _seasonal_decompose_trend(series: np.ndarray) -> np.ndarray:
    """
    Run additive seasonal decomposition (period=24).
    Returns trend component or original series on failure.
    """
    try:
        from statsmodels.tsa.seasonal import seasonal_decompose
        import pandas as pd
        s = pd.Series(series.astype(float))
        if s.sum() == 0:
            return series
        result = seasonal_decompose(s, model="additive", period=24, extrapolate_trend="freq")
        trend = result.trend.fillna(0).values.astype(np.float32)
        mn = trend.min()
        mx = trend.max()
        if mx > mn:
            trend = (trend - mn) / (mx - mn)
        return trend
    except Exception as exc:
        logger.debug("seasonal_decompose skipped: %s", exc)
        return series


def _best_window(hourly_signal: np.ndarray) -> tuple[int, int]:
    """
    Find the best contiguous window of length 2-3 hours inside the 24-hour
    averaged signal (summed over all weekdays).

    Returns (start_hour, end_hour) with end_hour exclusive.
    """
    # Collapse to 24-hour profile
    profile = hourly_signal.reshape(7, 24).mean(axis=0)

    best_score = -1.0
    best_start = 0
    best_end   = 2

    for length in range(_PEAK_WINDOW_MIN, _PEAK_WINDOW_MAX + 1):
        for start in range(24):
            indices = [(start + i) % 24 for i in range(length)]
            score = float(profile[indices].sum())
            if score > best_score:
                best_score = score
                best_start = start
                best_end   = (start + length) % 24 or 24

    return best_start, best_end


def _peak_days(matrix: np.ndarray, top_n: int = 3) -> list[int]:
    """Return top-N weekday indices (0=Mon) sorted by total intensity."""
    day_totals = matrix.sum(axis=1)
    return [int(d) for d in np.argsort(day_totals)[::-1][:top_n]]


def _matrix_to_json(matrix: np.ndarray) -> dict[str, dict[str, float]]:
    """Convert 7×24 ndarray to JSON-serialisable nested dict."""
    return {
        str(day): {str(hour): round(float(matrix[day, hour]), 4) for hour in range(24)}
        for day in range(7)
    }


def _hour_label(h: int) -> str:
    """Return '9 AM', '2 PM', '12 PM', etc."""
    if h == 0:
        return "12 AM"
    if h == 12:
        return "12 PM"
    return f"{h} AM" if h < 12 else f"{h - 12} PM"


def _build_message(peak_start: int, peak_end: int, peak_day_indices: list[int]) -> str:
    """Generate a human-readable recommendation sentence."""
    start_lbl = _hour_label(peak_start)
    end_lbl   = _hour_label(peak_end)

    if not peak_day_indices:
        return f"Your peak focus window appears to be {start_lbl}–{end_lbl}."

    day_labels = [_DAY_NAMES[d] for d in peak_day_indices]
    weekdays = {0, 1, 2, 3, 4}
    weekend  = {5, 6}
    day_set  = set(peak_day_indices)

    if day_set.issubset(weekdays):
        day_str = "weekdays"
    elif day_set.issubset(weekend):
        day_str = "weekends"
    elif len(day_labels) == 1:
        day_str = day_labels[0] + "s"
    elif len(day_labels) == 2:
        day_str = f"{day_labels[0]} and {day_labels[1]}"
    else:
        day_str = ", ".join(day_labels[:-1]) + f", and {day_labels[-1]}"

    return f"Your peak focus is {start_lbl}–{end_lbl} on {day_str}."


# ─────────────────────────────────────────────────────────────────────────────
# Optional Prophet forecast
# ─────────────────────────────────────────────────────────────────────────────

def _maybe_prophet(timestamps: list[datetime]) -> dict[str, Any] | None:
    """
    Run Prophet on daily event counts if ≥30 distinct days of history.
    Returns a dict with 7-day forecast or None if Prophet not installed / data too sparse.
    """
    try:
        from prophet import Prophet          # type: ignore
        import pandas as pd
    except ImportError:
        return None

    if not timestamps:
        return None

    dates = [dt.date() for dt in timestamps]
    if len(set(dates)) < 30:
        return None

    try:
        df = pd.Series(dates).value_counts().reset_index()
        df.columns = ["ds", "y"]
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds").reset_index(drop=True)

        m = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=False)
        m.fit(df)
        future = m.make_future_dataframe(periods=7)
        forecast = m.predict(future).tail(7)[["ds", "yhat"]].copy()
        forecast["ds"] = forecast["ds"].dt.strftime("%Y-%m-%d")
        return {"forecast_7d": forecast.to_dict(orient="records")}
    except Exception as exc:
        logger.debug("Prophet forecast failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_pattern(user_id: int):
    """
    Compute and upsert a StudyPattern for the given user.

    Returns the StudyPattern instance (or None on unrecoverable error).
    Falls back gracefully for sparse users (<10 events).
    """
    from django.utils import timezone as dj_tz
    from core.models import StudyPattern

    try:
        timestamps, hour_to_avg = _collect_timestamps(user_id)
        n_events = len(timestamps)
        confidence = min(1.0, n_events / _CONFIDENCE_TARGET)

        if n_events < _MIN_EVENTS_FOR_RESULT:
            pattern, _ = StudyPattern.objects.update_or_create(
                user_id=user_id,
                defaults=dict(
                    peak_hour_start=20,
                    peak_hour_end=22,
                    peak_days=[0, 1, 2],
                    weekly_intensity={},
                    productivity_score=0.0,
                    confidence=confidence,
                    computed_at=dj_tz.now(),
                ),
            )
            return pattern

        matrix   = _build_matrix(timestamps, hour_to_avg)
        series   = _hourly_series(matrix)
        trend    = _seasonal_decompose_trend(series)
        p_start, p_end = _best_window(trend)
        p_days   = _peak_days(matrix)

        # Productivity score: mean intensity at the peak window across peak days
        prod_vals: list[float] = []
        for d in p_days:
            for h in range(p_start, p_end if p_end > p_start else p_end + 24):
                prod_vals.append(float(matrix[d, h % 24]))
        productivity = float(np.mean(prod_vals)) if prod_vals else 0.0

        pattern, _ = StudyPattern.objects.update_or_create(
            user_id=user_id,
            defaults=dict(
                peak_hour_start=p_start,
                peak_hour_end=p_end,
                peak_days=p_days,
                weekly_intensity=_matrix_to_json(matrix),
                productivity_score=round(productivity, 4),
                confidence=round(confidence, 4),
                computed_at=dj_tz.now(),
            ),
        )
        return pattern

    except Exception as exc:
        logger.exception("compute_pattern failed for user %s: %s", user_id, exc)
        return None


def get_recommendation(user_id: int) -> dict[str, Any]:
    """
    Return the study-time recommendation dict for the API response.

    Recomputes if pattern is >24 h old.
    Returns {status: 'warming_up'} if no data yet and computation is deferred.
    """
    from django.utils import timezone as dj_tz
    from datetime import timedelta
    from core.models import StudyPattern

    STALE_HOURS = 24

    try:
        pattern = StudyPattern.objects.get(user_id=user_id)
        age_h = (dj_tz.now() - pattern.computed_at).total_seconds() / 3600
        if age_h > STALE_HOURS:
            pattern = compute_pattern(user_id) or pattern
    except StudyPattern.DoesNotExist:
        pattern = compute_pattern(user_id)

    if pattern is None:
        return {"status": "warming_up"}

    if pattern.confidence == 0 and not pattern.weekly_intensity:
        return {
            "status": "warming_up",
            "message": "Keep studying — we need more data to find your peak focus time.",
            "confidence": 0,
        }

    message = _build_message(pattern.peak_hour_start, pattern.peak_hour_end, pattern.peak_days)

    # Heatmap as flat list for the frontend: 168 floats (7 days × 24 hours)
    heatmap: list[float] = []
    intensity = pattern.weekly_intensity
    for day in range(7):
        day_data = intensity.get(str(day), {})
        for hour in range(24):
            heatmap.append(float(day_data.get(str(hour), 0.0)))

    peak_day_labels = [_DAY_SHORT[d] for d in (pattern.peak_days or [])]

    return {
        "peak_window": {
            "start": pattern.peak_hour_start,
            "end":   pattern.peak_hour_end,
            "start_label": _hour_label(pattern.peak_hour_start),
            "end_label":   _hour_label(pattern.peak_hour_end),
        },
        "peak_days":         peak_day_labels,
        "heatmap":           heatmap,           # 168 floats, index = day*24 + hour
        "message":           message,
        "confidence":        pattern.confidence,
        "productivity_score": pattern.productivity_score,
    }
