"""Shared ORM → pandas feature extraction for all three ML models."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from django.utils import timezone


TOPICS = [
    'calculus', 'linear_algebra', 'machine_learning',
    'operating_systems', 'databases', 'networks',
    'object_oriented_programming', 'statistics',
]

TOPIC_DIFFICULTY: dict[str, float] = {
    'calculus': 0.75, 'linear_algebra': 0.65, 'machine_learning': 0.80,
    'operating_systems': 0.60, 'databases': 0.55, 'networks': 0.58,
    'object_oriented_programming': 0.50, 'statistics': 0.70,
}


def _topic(obj) -> str:
    """Return canonical topic string from a Flashcard or QuizAttempt."""
    return getattr(obj, 'subject', 'General') or 'General'


def get_review_features(user_id: Optional[int] = None) -> pd.DataFrame:
    """
    All FlashcardReview rows with derived columns.

    Columns: review_id, user_id, flashcard_id, topic, grade,
             days_since_last, reviewed_at, response_time_ms,
             skill (approx), topic_difficulty, num_prior_reviews.
    """
    from core.models import FlashcardReview

    qs = FlashcardReview.objects.select_related('flashcard', 'user')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)

    if not qs.exists():
        return pd.DataFrame()

    rows = []
    # Pre-compute per-flashcard cumulative review count
    card_count: dict[int, int] = {}
    for r in qs.order_by('reviewed_at'):
        cid = r.flashcard_id
        card_count[cid] = card_count.get(cid, 0) + 1
        topic = _topic(r.flashcard)
        rows.append({
            'review_id': r.id,
            'user_id': r.user_id,
            'flashcard_id': cid,
            'topic': topic,
            'grade': r.grade,
            'days_since_last': float(r.days_since_last),
            'reviewed_at': r.reviewed_at,
            'response_time_ms': int(r.response_time_ms),
            'skill': min(1.0, float(r.grade) / 5.0),
            'topic_difficulty': TOPIC_DIFFICULTY.get(topic, 0.6),
            'num_prior_reviews': card_count[cid],
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df['avg_grade'] = (
            df.groupby('flashcard_id')['grade']
            .transform(lambda x: x.expanding().mean().shift(1).fillna(2.5))
        )
    return df


def get_quiz_features(user_id: Optional[int] = None) -> pd.DataFrame:
    """
    All QuizAttempt rows normalised to 0-1 score.

    Columns: attempt_id, user_id, topic, score, num_questions, duration_sec, attempted_at.
    """
    from core.models import QuizAttempt

    qs = QuizAttempt.objects.all()
    if user_id is not None:
        qs = qs.filter(user_id=user_id)

    if not qs.exists():
        return pd.DataFrame()

    rows = []
    for q in qs:
        raw_score = float(q.score)
        score_01 = raw_score / 100.0 if raw_score > 1.0 else raw_score
        rows.append({
            'attempt_id': q.id,
            'user_id': q.user_id,
            'topic': _topic(q),
            'score': score_01,
            'num_questions': int(q.total_questions),
            'duration_sec': int(q.time_taken_seconds),
            'attempted_at': q.attempted_at,
        })

    return pd.DataFrame(rows)


def get_chat_features(user_id: Optional[int] = None) -> pd.DataFrame:
    """
    User-role ChatHistory messages for confusion clustering.

    Columns: chat_id, user_id, content, timestamp, session_id.
    """
    from core.models import ChatHistory

    qs = ChatHistory.objects.filter(role='user')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)

    if not qs.exists():
        return pd.DataFrame()

    rows = [
        {
            'chat_id': c.id,
            'user_id': c.user_id,
            'content': c.content,
            'timestamp': c.timestamp,
            'session_id': c.session_id,
        }
        for c in qs
    ]
    return pd.DataFrame(rows)


def build_user_risk_features(as_of: Optional[datetime] = None) -> pd.DataFrame:
    """
    One row per non-staff active user with the 7 risk features + target.

    Features:
        avg_quiz_score_30d, sessions_7d, avg_session_len, review_streak,
        pct_grade_low, hours_since_activity, topic_diversity
    Target:
        at_risk  (1 = most-recent quiz score < 0.6)
    """
    from django.contrib.auth.models import User
    from django.db.models import Avg
    from core.models import FlashcardReview, QuizAttempt, ChatSession, ChatHistory

    if as_of is None:
        as_of = timezone.now()

    cutoff_30d = as_of - timedelta(days=30)
    cutoff_7d = as_of - timedelta(days=7)

    users = User.objects.filter(is_active=True, is_staff=False)
    rows = []

    for user in users:
        reviews = FlashcardReview.objects.filter(user=user)
        quizzes = QuizAttempt.objects.filter(user=user)
        sessions = ChatSession.objects.filter(user=user)

        # avg quiz score last 30 days
        recent_q = quizzes.filter(attempted_at__gte=cutoff_30d)
        if recent_q.exists():
            raw_avg = recent_q.aggregate(a=Avg('score'))['a'] or 50.0
            avg_quiz_score_30d = raw_avg / 100.0 if raw_avg > 1.0 else raw_avg
        else:
            avg_quiz_score_30d = 0.5

        # sessions last 7 days
        sessions_7d = int(sessions.filter(created_at__gte=cutoff_7d).count())

        # avg session length (messages per session)
        n_sessions = sessions.count()
        if n_sessions > 0:
            n_msgs = ChatHistory.objects.filter(user=user).count()
            avg_session_len = float(n_msgs) / n_sessions
        else:
            avg_session_len = 0.0

        # review streak (consecutive days with ≥ 1 review, counting back from as_of)
        review_days = {
            r.reviewed_at.date()
            for r in reviews.order_by('-reviewed_at')[:90]
        }
        streak = 0
        day = as_of.date()
        while day in review_days:
            streak += 1
            day -= timedelta(days=1)

        # pct low-grade reviews (grade ≤ 1)
        total_rev = reviews.count()
        pct_grade_low = reviews.filter(grade__lte=1).count() / total_rev if total_rev else 0.5

        # hours since last activity
        timestamps = []
        lr = reviews.order_by('-reviewed_at').first()
        ls = sessions.order_by('-created_at').first()
        lq = quizzes.order_by('-attempted_at').first()
        if lr:
            timestamps.append(lr.reviewed_at)
        if ls:
            timestamps.append(ls.created_at)
        if lq:
            timestamps.append(lq.attempted_at)
        hours_since_activity = (
            (as_of - max(timestamps)).total_seconds() / 3600
            if timestamps else 720.0
        )

        # topic diversity
        rev_topics = {_topic(r.flashcard) for r in reviews.select_related('flashcard')}
        quiz_topics = {_topic(q) for q in quizzes}
        topic_diversity = len(rev_topics | quiz_topics)

        # target: was most-recent quiz below 0.6?
        latest_quiz = quizzes.order_by('-attempted_at').first()
        if latest_quiz:
            raw = float(latest_quiz.score)
            score_01 = raw / 100.0 if raw > 1.0 else raw
            at_risk = int(score_01 < 0.6)
        else:
            at_risk = 0

        rows.append({
            'user_id': user.id,
            'avg_quiz_score_30d': avg_quiz_score_30d,
            'sessions_7d': sessions_7d,
            'avg_session_len': avg_session_len,
            'review_streak': streak,
            'pct_grade_low': pct_grade_low,
            'hours_since_activity': hours_since_activity,
            'topic_diversity': float(topic_diversity),
            'at_risk': at_risk,
        })

    return pd.DataFrame(rows)


RISK_FEATURE_COLS = [
    'avg_quiz_score_30d', 'sessions_7d', 'avg_session_len',
    'review_streak', 'pct_grade_low', 'hours_since_activity', 'topic_diversity',
]
