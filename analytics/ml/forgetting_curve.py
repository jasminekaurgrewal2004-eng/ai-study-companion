"""F1 — CoxPH survival wrapper for flashcard recall prediction.

Lazy-loads models/forgetting_curve.pkl on first call (thread-safe).
Falls back to exponential decay when the model file is missing.

Public API
----------
predict_recall(user_id, topic) -> {'p_recall': float, 'optimal_review_in_days': int}
predict_card_recall(card_id, user_id) -> {'p_recall': float, 'optimal_review_in_days': int}
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import numpy as np

_MODEL_PATH = Path(__file__).resolve().parents[2] / 'models' / 'forgetting_curve.pkl'
_model = None
_model_lock = threading.Lock()


def _load_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                if _MODEL_PATH.exists():
                    import joblib
                    _model = joblib.load(_MODEL_PATH)
    return _model


def _exp_fallback(hours_since: float, avg_grade: float) -> dict:
    """Exponential decay P(recall) = exp(-Δt / S), S driven by avg_grade."""
    stability_days = max(0.5, avg_grade * 1.5)
    days_since = hours_since / 24.0
    p = float(np.exp(-days_since / stability_days))
    optimal = max(1, int(stability_days * 1.5))
    return {'p_recall': round(min(1.0, max(0.0, p)), 4), 'optimal_review_in_days': optimal}


def _covariate_df(avg_grade: float, num_prior: int, hours_since: float, topic: str):
    """Build a single-row covariate DataFrame for the CoxPH model."""
    import pandas as pd
    from analytics.ml.feature_engineering import TOPIC_DIFFICULTY
    return pd.DataFrame([{
        'avg_grade': float(avg_grade),
        'num_prior_reviews': int(num_prior),
        'hours_since_last_review': float(hours_since),
        'skill': min(1.0, float(avg_grade) / 5.0),
        'topic_difficulty': TOPIC_DIFFICULTY.get(topic, 0.6),
    }])


def _cox_predict(model, cov_df, hours_since: float) -> dict:
    """Run CoxPH prediction and derive optimal review day."""
    days_since = hours_since / 24.0
    try:
        sf_now = model.predict_survival_function(cov_df, times=[days_since])
        p_recall = float(sf_now.iloc[0, 0])

        # Find first day where S(t) drops below 0.9 (10 % forget threshold)
        times = np.arange(0.25, 31.0, 0.25)
        sf_curve = model.predict_survival_function(cov_df, times=times)
        below = np.where(sf_curve.values[:, 0] < 0.9)[0]
        optimal = max(1, int(times[below[0]])) if len(below) else 7
        return {
            'p_recall': round(min(1.0, max(0.0, p_recall)), 4),
            'optimal_review_in_days': optimal,
        }
    except Exception:
        return None


# ── public API ────────────────────────────────────────────────────────────────

def predict_recall(user_id: int, topic: str) -> dict:
    """
    Predict recall probability for the most-due card on *topic* for *user_id*.

    Returns
    -------
    dict with keys: p_recall (float), optimal_review_in_days (int)
    """
    from django.utils import timezone
    from django.db.models import Avg
    from core.models import Flashcard, FlashcardReview

    now = timezone.now()

    cards = Flashcard.objects.filter(user_id=user_id, subject=topic).order_by('next_review')
    if not cards.exists():
        return {'p_recall': 1.0, 'optimal_review_in_days': 1}

    card = cards.first()
    reviews = FlashcardReview.objects.filter(flashcard=card, user_id=user_id).order_by('-reviewed_at')

    if not reviews.exists():
        return {'p_recall': 1.0, 'optimal_review_in_days': 1}

    last = reviews.first()
    hours_since = (now - last.reviewed_at).total_seconds() / 3600
    agg = reviews[:10].aggregate(avg=Avg('grade'))
    avg_grade = float(agg['avg'] or 2.5)
    num_prior = reviews.count()

    model = _load_model()
    if model is None:
        return _exp_fallback(hours_since, avg_grade)

    cov = _covariate_df(avg_grade, num_prior, hours_since, topic)
    result = _cox_predict(model, cov, hours_since)
    return result or _exp_fallback(hours_since, avg_grade)


def predict_card_recall(card_id: int, user_id: int) -> dict:
    """
    Per-card variant used by the review-queue endpoint.

    Returns
    -------
    dict with keys: p_recall (float), optimal_review_in_days (int)
    """
    from django.utils import timezone
    from django.db.models import Avg
    from core.models import Flashcard, FlashcardReview
    from analytics.ml.feature_engineering import TOPIC_DIFFICULTY

    now = timezone.now()
    try:
        card = Flashcard.objects.get(pk=card_id, user_id=user_id)
    except Flashcard.DoesNotExist:
        return {'p_recall': 1.0, 'optimal_review_in_days': 1}

    topic = card.subject
    reviews = FlashcardReview.objects.filter(flashcard=card, user_id=user_id).order_by('-reviewed_at')

    if not reviews.exists():
        # New card — due immediately
        return {'p_recall': 1.0, 'optimal_review_in_days': 1}

    last = reviews.first()
    hours_since = (now - last.reviewed_at).total_seconds() / 3600
    agg = reviews[:10].aggregate(avg=Avg('grade'))
    avg_grade = float(agg['avg'] or 2.5)
    num_prior = reviews.count()

    model = _load_model()
    if model is None:
        return _exp_fallback(hours_since, avg_grade)

    cov = _covariate_df(avg_grade, num_prior, hours_since, topic)
    result = _cox_predict(model, cov, hours_since)
    return result or _exp_fallback(hours_since, avg_grade)
