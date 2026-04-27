"""F3 — XGBoost + SHAP risk-score wrapper.

Lazy-loads models/risk_xgb.pkl and models/risk_shap_explainer.pkl (thread-safe).
Falls back to a rule-based heuristic when files are missing.

Public API
----------
predict_risk(user_id) ->
    {'risk': float, 'band': 'low|medium|high',
     'top_factors': [{'name': str, 'impact': float, 'direction': 'up|down'}]}
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

_MODELS_DIR = Path(__file__).resolve().parents[2] / 'models'
_XGB_PATH = _MODELS_DIR / 'risk_xgb.pkl'
_SHAP_PATH = _MODELS_DIR / 'risk_shap_explainer.pkl'

_xgb_model = None
_shap_explainer = None
_models_lock = threading.Lock()


def _load_models():
    global _xgb_model, _shap_explainer
    if _xgb_model is None:
        with _models_lock:
            if _xgb_model is None:
                if _XGB_PATH.exists():
                    import joblib
                    _xgb_model = joblib.load(_XGB_PATH)
                    if _SHAP_PATH.exists():
                        _shap_explainer = joblib.load(_SHAP_PATH)
    return _xgb_model, _shap_explainer


def _band(risk: float) -> str:
    if risk < 0.35:
        return 'low'
    if risk < 0.65:
        return 'medium'
    return 'high'


def _rule_based_risk(feats: dict) -> dict:
    """Heuristic fallback when model not trained."""
    score = 0.5
    # Low activity → higher risk
    if feats['hours_since_activity'] > 48:
        score += 0.15
    if feats['avg_quiz_score_30d'] < 0.6:
        score += 0.20
    if feats['review_streak'] >= 3:
        score -= 0.10
    if feats['pct_grade_low'] > 0.5:
        score += 0.15
    risk = float(np.clip(score, 0.0, 1.0))
    return {
        'risk': round(risk, 3),
        'band': _band(risk),
        'top_factors': [
            {'name': 'avg_quiz_score_30d', 'impact': 0.20,
             'direction': 'up' if feats['avg_quiz_score_30d'] < 0.6 else 'down'},
            {'name': 'hours_since_activity', 'impact': 0.15,
             'direction': 'up' if feats['hours_since_activity'] > 48 else 'down'},
            {'name': 'pct_grade_low', 'impact': 0.15,
             'direction': 'up' if feats['pct_grade_low'] > 0.5 else 'down'},
        ],
    }


def _get_user_features(user_id: int) -> dict:
    """Compute the 7 risk features for a single user on-the-fly."""
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Avg
    from core.models import FlashcardReview, QuizAttempt, ChatSession, ChatHistory
    from analytics.ml.feature_engineering import TOPIC_DIFFICULTY

    now = timezone.now()
    cutoff_30d = now - timedelta(days=30)
    cutoff_7d = now - timedelta(days=7)

    reviews = FlashcardReview.objects.filter(user_id=user_id)
    quizzes = QuizAttempt.objects.filter(user_id=user_id)
    sessions = ChatSession.objects.filter(user_id=user_id)

    # avg_quiz_score_30d
    rq = quizzes.filter(attempted_at__gte=cutoff_30d)
    if rq.exists():
        raw = rq.aggregate(a=Avg('score'))['a'] or 50.0
        avg_quiz_score_30d = raw / 100.0 if raw > 1.0 else raw
    else:
        avg_quiz_score_30d = 0.5

    # sessions_7d
    sessions_7d = float(sessions.filter(created_at__gte=cutoff_7d).count())

    # avg_session_len
    n_sess = sessions.count()
    avg_session_len = (
        ChatHistory.objects.filter(user_id=user_id).count() / n_sess
        if n_sess else 0.0
    )

    # review_streak
    review_days = {r.reviewed_at.date() for r in reviews.order_by('-reviewed_at')[:90]}
    streak = 0
    from datetime import date
    day = now.date()
    while day in review_days:
        streak += 1
        day -= timedelta(days=1)

    # pct_grade_low
    tot = reviews.count()
    pct_grade_low = reviews.filter(grade__lte=1).count() / tot if tot else 0.5

    # hours_since_activity
    ts = []
    lr = reviews.order_by('-reviewed_at').first()
    ls = sessions.order_by('-created_at').first()
    lq = quizzes.order_by('-attempted_at').first()
    if lr:
        ts.append(lr.reviewed_at)
    if ls:
        ts.append(ls.created_at)
    if lq:
        ts.append(lq.attempted_at)
    hours_since_activity = (
        (now - max(ts)).total_seconds() / 3600 if ts else 720.0
    )

    # topic_diversity
    rt = {r.flashcard.subject for r in reviews.select_related('flashcard')}
    qt = {q.subject for q in quizzes}
    topic_diversity = float(len(rt | qt))

    return {
        'avg_quiz_score_30d': avg_quiz_score_30d,
        'sessions_7d': sessions_7d,
        'avg_session_len': avg_session_len,
        'review_streak': float(streak),
        'pct_grade_low': pct_grade_low,
        'hours_since_activity': hours_since_activity,
        'topic_diversity': topic_diversity,
    }


# ── public API ────────────────────────────────────────────────────────────────

def predict_risk(user_id: int) -> dict:
    """
    Predict at-risk probability for *user_id*.

    Returns
    -------
    dict with keys: risk (float 0-1), band (str), top_factors (list)
    """
    from analytics.ml.feature_engineering import RISK_FEATURE_COLS
    import pandas as pd

    feats = _get_user_features(user_id)
    xgb, shap_exp = _load_models()

    if xgb is None:
        return _rule_based_risk(feats)

    X = pd.DataFrame([[feats[c] for c in RISK_FEATURE_COLS]], columns=RISK_FEATURE_COLS)
    risk = float(xgb.predict_proba(X)[0, 1])

    # SHAP factors
    top_factors = []
    if shap_exp is not None:
        try:
            shap_vals = shap_exp.shap_values(X)
            if isinstance(shap_vals, list):
                sv = shap_vals[1][0]
            else:
                sv = shap_vals[0]
            pairs = sorted(zip(RISK_FEATURE_COLS, sv), key=lambda x: abs(x[1]), reverse=True)
            for name, impact in pairs[:3]:
                top_factors.append({
                    'name': name,
                    'impact': round(float(abs(impact)), 4),
                    'direction': 'up' if impact > 0 else 'down',
                })
        except Exception:
            pass

    if not top_factors:
        # Fallback: rank by feature magnitude contribution
        for name in RISK_FEATURE_COLS[:3]:
            top_factors.append({
                'name': name,
                'impact': round(float(abs(feats[name])) * 0.1, 4),
                'direction': 'up',
            })

    return {
        'risk': round(risk, 3),
        'band': _band(risk),
        'top_factors': top_factors,
    }
