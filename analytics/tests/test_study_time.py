"""
Tests for analytics/ml/study_time.py
=====================================
Cases:
  (a) user with no data
  (b) user with 5 events (below threshold)
  (c) user with 200 events (full pipeline)
  (d) timezone conversion correctness
  (e) _build_message generates sensible strings
"""

import pytest
from datetime import datetime, timezone as dt_tz
from unittest.mock import patch, MagicMock

import numpy as np


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_ts(year, month, day, hour, tz_name="Asia/Kolkata"):
    """Return a UTC-aware datetime that corresponds to the given local time."""
    import zoneinfo
    tz = zoneinfo.ZoneInfo(tz_name)
    local = datetime(year, month, day, hour, 0, 0, tzinfo=tz)
    return local.astimezone(dt_tz.utc)


def _fake_collect(n_events: int, peak_hour: int = 20):
    """Return (timestamps_local, hour_to_avg) with n_events all at peak_hour."""
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    timestamps = [
        datetime(2024, 1, (i % 28) + 1, peak_hour, 0, 0, tzinfo=tz)
        for i in range(n_events)
    ]
    return timestamps, {}


# ─── (a) user with NO data ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_compute_pattern_no_data(django_user_model):
    from analytics.ml.study_time import compute_pattern

    user = django_user_model.objects.create_user(username="nodata_user", password="x")

    pattern = compute_pattern(user.id)

    assert pattern is not None
    assert pattern.confidence == 0.0
    assert pattern.weekly_intensity == {}


# ─── (b) user with 5 events (sparse) ────────────────────────────────────────

@pytest.mark.django_db
def test_compute_pattern_sparse(django_user_model):
    from analytics.ml.study_time import compute_pattern, _collect_timestamps

    user = django_user_model.objects.create_user(username="sparse_user", password="x")

    fake_ts, fake_scores = _fake_collect(5, peak_hour=14)
    with patch("analytics.ml.study_time._collect_timestamps", return_value=(fake_ts, fake_scores)):
        pattern = compute_pattern(user.id)

    assert pattern is not None
    # 5 events → confidence = 5/50 = 0.1
    assert abs(pattern.confidence - 0.1) < 1e-6
    # Not enough data for full matrix → weekly_intensity is empty
    assert pattern.weekly_intensity == {}


# ─── (c) user with 200 events (full pipeline) ────────────────────────────────

@pytest.mark.django_db
def test_compute_pattern_full(django_user_model):
    from analytics.ml.study_time import compute_pattern, _collect_timestamps

    user = django_user_model.objects.create_user(username="full_user", password="x")

    fake_ts, fake_scores = _fake_collect(200, peak_hour=20)
    with patch("analytics.ml.study_time._collect_timestamps", return_value=(fake_ts, fake_scores)):
        pattern = compute_pattern(user.id)

    assert pattern is not None
    assert pattern.confidence == 1.0
    assert pattern.peak_hour_start == 20
    assert isinstance(pattern.weekly_intensity, dict)
    assert len(pattern.weekly_intensity) == 7   # 7 days
    assert pattern.productivity_score >= 0.0


# ─── (d) timezone conversion correctness ────────────────────────────────────

def test_tz_conversion():
    """UTC 18:30 = IST 00:00 (next day, midnight)."""
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    utc_ts = datetime(2024, 6, 15, 18, 30, 0, tzinfo=dt_tz.utc)
    local_ts = utc_ts.astimezone(tz)
    assert local_ts.hour == 0
    assert local_ts.day == 16


# ─── (e) _build_message output ───────────────────────────────────────────────

def test_build_message_weekdays():
    from analytics.ml.study_time import _build_message
    msg = _build_message(20, 22, [0, 1, 2, 3, 4])
    assert "8 PM" in msg
    assert "10 PM" in msg
    assert "weekday" in msg.lower()


def test_build_message_weekend():
    from analytics.ml.study_time import _build_message
    msg = _build_message(10, 12, [5, 6])
    assert "weekend" in msg.lower()


def test_build_message_no_days():
    from analytics.ml.study_time import _build_message
    msg = _build_message(9, 11, [])
    assert "9 AM" in msg
    assert "11 AM" in msg


# ─── matrix / heatmap shapes ────────────────────────────────────────────────

def test_build_matrix_shape():
    from analytics.ml.study_time import _build_matrix
    import zoneinfo
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    timestamps = [datetime(2024, 1, i + 1, h, 0, tzinfo=tz) for i in range(7) for h in range(24)]
    matrix = _build_matrix(timestamps, {})
    assert matrix.shape == (7, 24)
    assert matrix.max() <= 1.0
    assert matrix.min() >= 0.0


def test_get_recommendation_returns_heatmap(django_user_model):
    from analytics.ml.study_time import get_recommendation, _collect_timestamps

    import pytest
    pytest.importorskip("django")

    from django.contrib.auth.models import User
    user = User.objects.create_user(username="hm_user", password="x")

    fake_ts, fake_scores = _fake_collect(200, peak_hour=19)
    with patch("analytics.ml.study_time._collect_timestamps", return_value=(fake_ts, fake_scores)):
        result = get_recommendation(user.id)

    assert "heatmap" in result
    assert len(result["heatmap"]) == 168
    assert "message" in result
    assert "peak_window" in result
