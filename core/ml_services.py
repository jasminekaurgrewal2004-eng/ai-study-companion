"""
ML services for the three DS features:
  1. ForgettingCurvePredictor  — SM-2 spaced repetition + logistic regression
  2. ConfusionTopicAnalyzer    — TF-IDF + KMeans clustering of chat questions
  3. PerformanceRiskScorer     — rule-based + feature-engineered risk scoring
"""
import math
from datetime import timedelta
from django.utils import timezone


# ---------------------------------------------------------------------------
# 1. FORGETTING CURVE PREDICTOR
# ---------------------------------------------------------------------------

class ForgettingCurvePredictor:
    """
    Implements SM-2 algorithm for immediate use (works with 0 data).
    Recall probability follows Ebbinghaus: P = e^(-t / S), where S (stability)
    grows with each successful repetition.
    """

    @staticmethod
    def sm2_update(card, grade: int):
        """
        Update a Flashcard's SM-2 state after a review.
        grade 0-2 → reset streak; grade 3-5 → advance interval.
        Returns the modified (unsaved) card.
        """
        if grade < 3:
            card.repetitions = 0
            card.interval = 1
        else:
            if card.repetitions == 0:
                card.interval = 1
            elif card.repetitions == 1:
                card.interval = 6
            else:
                card.interval = round(card.interval * card.ease_factor)
            card.repetitions += 1

        card.ease_factor = max(
            1.3,
            card.ease_factor + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02),
        )
        card.next_review = timezone.now() + timedelta(days=card.interval)
        return card

    @staticmethod
    def recall_probability(days_elapsed: float, interval: int, repetitions: int) -> float:
        """
        P(recall) = exp(-days_elapsed / stability)
        Stability grows with repetitions so well-drilled cards decay slower.
        """
        stability = max(1.0, interval * (1.0 + 0.15 * repetitions))
        prob = math.exp(-days_elapsed / stability)
        return round(min(1.0, max(0.0, prob)), 3)

    @classmethod
    def get_due_cards(cls, user):
        """Return cards currently due for review with their recall probability."""
        from .models import Flashcard
        now = timezone.now()
        due = Flashcard.objects.filter(user=user, next_review__lte=now).order_by('next_review')
        results = []
        for card in due[:10]:
            days_overdue = max(0, (now - card.next_review).total_seconds() / 86400)
            days_elapsed = card.interval + days_overdue
            prob = cls.recall_probability(days_elapsed, card.interval, card.repetitions)
            results.append({
                'id': card.id,
                'front': card.front,
                'back': card.back,
                'subject': card.subject,
                'recall_probability': prob,
                'days_overdue': round(days_overdue, 1),
                'interval': card.interval,
                'repetitions': card.repetitions,
            })
        return results

    @classmethod
    def deck_summary(cls, user):
        """High-level summary of the user's flashcard deck health."""
        from .models import Flashcard
        now = timezone.now()
        total = Flashcard.objects.filter(user=user).count()
        due = Flashcard.objects.filter(user=user, next_review__lte=now).count()
        upcoming_3d = Flashcard.objects.filter(
            user=user, next_review__gt=now,
            next_review__lte=now + timedelta(days=3),
        ).count()

        # Average recall probability across all due cards
        due_cards = Flashcard.objects.filter(user=user, next_review__lte=now)
        if due_cards.exists():
            probs = []
            for card in due_cards[:50]:
                days_elapsed = card.interval + max(0, (now - card.next_review).total_seconds() / 86400)
                probs.append(cls.recall_probability(days_elapsed, card.interval, card.repetitions))
            avg_recall = round(sum(probs) / len(probs), 3)
        else:
            avg_recall = 1.0

        return {
            'total': total,
            'due_now': due,
            'due_next_3_days': upcoming_3d,
            'avg_recall_probability': avg_recall,
            'health': 'Good' if due == 0 else ('Needs attention' if due <= 5 else 'Critical'),
        }

    @classmethod
    def forgetting_curve_points(cls, card):
        """Return (day, probability) points for plotting the card's decay curve."""
        points = []
        for day in range(0, card.interval * 3 + 1):
            points.append({
                'day': day,
                'probability': cls.recall_probability(day, card.interval, card.repetitions),
            })
        return points


# ---------------------------------------------------------------------------
# 2. CONFUSION TOPIC ANALYZER
# ---------------------------------------------------------------------------

class ConfusionTopicAnalyzer:
    """
    TF-IDF on user chat questions + KMeans clustering.
    Returns the top topics the user struggles with most.
    """

    EXTRA_STOP_WORDS = {
        'explain', 'tell', 'give', 'please', 'help', 'understand', 'understand',
        'difference', 'between', 'example', 'examples', 'using', 'use', 'used',
        'make', 'get', 'like', 'just', 'also', 'want', 'know', 'need', 'write',
        'code', 'show', 'does', 'work', 'means', 'mean', 'called', 'called',
        'way', 'ways', 'best', 'good', 'bad', 'better', 'simply', 'simple',
        'basic', 'basics', 'concept', 'concepts', 'thing', 'things',
    }

    @classmethod
    def analyze(cls, user, n_clusters: int = 5):
        """
        Cluster the user's chat questions and return topic labels.
        Returns a dict with 'status' and 'topics' keys.
        """
        from .models import ChatHistory
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        import numpy as np

        messages = list(
            ChatHistory.objects.filter(user=user, role='user')
            .values_list('content', flat=True)
            .order_by('-timestamp')[:300]
        )

        if len(messages) < 5:
            return {
                'status': 'insufficient_data',
                'min_required': 5,
                'current': len(messages),
                'topics': [],
            }

        k = min(n_clusters, max(2, len(messages) // 4))

        vectorizer = TfidfVectorizer(
            max_features=300,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z_+#\-\.]{2,}\b',
        )
        try:
            X = vectorizer.fit_transform(messages)
        except ValueError:
            return {'status': 'insufficient_data', 'min_required': 5, 'current': len(messages), 'topics': []}

        if X.shape[0] < k:
            k = max(2, X.shape[0])

        km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        labels = km.fit_predict(X)

        feature_names = vectorizer.get_feature_names_out()
        topics = []

        for cluster_id in range(k):
            indices = [i for i, lb in enumerate(labels) if lb == cluster_id]
            cluster_msgs = [messages[i] for i in indices]
            if not cluster_msgs:
                continue

            center = km.cluster_centers_[cluster_id]
            top_idx = center.argsort()[-8:][::-1]
            top_terms = [
                feature_names[i] for i in top_idx
                if feature_names[i].lower() not in cls.EXTRA_STOP_WORDS
            ][:3]

            label = ' / '.join(top_terms) if top_terms else f'Topic {cluster_id + 1}'
            topics.append({
                'topic': label.title(),
                'count': len(cluster_msgs),
                'example': cluster_msgs[0][:140],
                'cluster_id': int(cluster_id),
            })

        topics.sort(key=lambda x: x['count'], reverse=True)
        return {
            'status': 'ok',
            'topics': topics[:5],
            'total_questions': len(messages),
            'clusters_found': k,
        }


# ---------------------------------------------------------------------------
# 3. PERFORMANCE RISK SCORER
# ---------------------------------------------------------------------------

class PerformanceRiskScorer:
    """
    Engineers features from activity data and produces a risk score (0–100).
    Works with any amount of data; rule-based fallback when data is sparse.
    """

    @classmethod
    def _compute_features(cls, user):
        from .models import ChatHistory, ChatSession, JournalEntry, Flashcard, FlashcardReview, QuizAttempt
        from django.db.models import Avg

        now = timezone.now()
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)

        sessions_7d = ChatSession.objects.filter(user=user, created_at__gte=d7).count()
        sessions_30d = ChatSession.objects.filter(user=user, created_at__gte=d30).count()
        msgs_7d = ChatHistory.objects.filter(user=user, role='user', timestamp__gte=d7).count()
        avg_msgs = round(msgs_7d / max(1, sessions_7d), 1)

        last = ChatHistory.objects.filter(user=user).order_by('-timestamp').first()
        days_since_last = (now - last.timestamp).days if last else 30

        journals_7d = JournalEntry.objects.filter(user=user, date__gte=d7).count()

        cards_total = Flashcard.objects.filter(user=user).count()
        cards_due = Flashcard.objects.filter(user=user, next_review__lte=now).count()
        reviews_7d = FlashcardReview.objects.filter(user=user, reviewed_at__gte=d7).count()

        recent_quizzes = QuizAttempt.objects.filter(user=user, attempted_at__gte=d30)
        avg_quiz_score = recent_quizzes.aggregate(avg=Avg('score'))['avg']

        return {
            'sessions_7d': sessions_7d,
            'sessions_30d': sessions_30d,
            'avg_msgs_per_session': avg_msgs,
            'days_since_last': days_since_last,
            'journals_7d': journals_7d,
            'cards_total': cards_total,
            'cards_due': cards_due,
            'reviews_7d': reviews_7d,
            'avg_quiz_score': avg_quiz_score,
        }

    @classmethod
    def score(cls, user):
        """
        Returns risk_score (0–100), risk_level, color, a message, and top factors.
        Lower score = lower risk.
        """
        f = cls._compute_features(user)
        risk_points = 0
        factors = []

        # --- Recency (0–30 pts) ---
        if f['days_since_last'] <= 1:
            factors.append({'label': 'Active today', 'impact': 'positive', 'value': 'Studying regularly'})
        elif f['days_since_last'] <= 3:
            risk_points += 10
            factors.append({'label': 'Short study gap', 'impact': 'low', 'value': f"{f['days_since_last']}d since last session"})
        elif f['days_since_last'] <= 7:
            risk_points += 20
            factors.append({'label': 'Study gap detected', 'impact': 'medium', 'value': f"{f['days_since_last']}d since last session"})
        else:
            risk_points += 30
            factors.append({'label': 'Long study break', 'impact': 'high', 'value': f"{f['days_since_last']} days since last session"})

        # --- Session frequency (0–25 pts) ---
        if f['sessions_7d'] >= 5:
            factors.append({'label': 'Strong study streak', 'impact': 'positive', 'value': f"{f['sessions_7d']} sessions this week"})
        elif f['sessions_7d'] >= 3:
            risk_points += 5
        elif f['sessions_7d'] == 1:
            risk_points += 15
            factors.append({'label': 'Low frequency', 'impact': 'medium', 'value': 'Only 1 session last 7 days'})
        elif f['sessions_7d'] == 0:
            risk_points += 25
            factors.append({'label': 'No recent sessions', 'impact': 'high', 'value': '0 sessions in last 7 days'})

        # --- Reflection habit (0–15 pts) ---
        if f['journals_7d'] == 0 and f['sessions_7d'] > 0:
            risk_points += 15
            factors.append({'label': 'Missing reflection', 'impact': 'medium', 'value': 'No journal entries this week'})
        elif f['journals_7d'] >= 3:
            factors.append({'label': 'Great reflection habit', 'impact': 'positive', 'value': f"{f['journals_7d']} journal entries"})

        # --- Flashcard overdue (0–20 pts) ---
        if f['cards_total'] > 0:
            overdue_ratio = f['cards_due'] / f['cards_total']
            if overdue_ratio > 0.5:
                risk_points += 20
                factors.append({'label': 'Many overdue cards', 'impact': 'high', 'value': f"{f['cards_due']}/{f['cards_total']} cards need review"})
            elif overdue_ratio > 0.2:
                risk_points += 10
                factors.append({'label': 'Cards need review', 'impact': 'medium', 'value': f"{f['cards_due']} overdue flashcards"})
            elif f['cards_due'] == 0:
                factors.append({'label': 'Flashcards up to date', 'impact': 'positive', 'value': 'All cards reviewed on time'})

        # --- Quiz performance (0–10 pts) ---
        if f['avg_quiz_score'] is not None:
            if f['avg_quiz_score'] < 60:
                risk_points += 10
                factors.append({'label': 'Low quiz scores', 'impact': 'high', 'value': f"Avg {f['avg_quiz_score']:.0f}% on recent quizzes"})
            elif f['avg_quiz_score'] >= 80:
                factors.append({'label': 'Strong quiz scores', 'impact': 'positive', 'value': f"Avg {f['avg_quiz_score']:.0f}%"})

        risk_score = min(100, risk_points)

        if risk_score <= 20:
            level, color = 'Low', 'mint'
            message = "You're on track. Keep up the consistent study habit!"
        elif risk_score <= 50:
            level, color = 'Medium', 'gold'
            message = "Some gaps detected. A focused session today would help a lot."
        else:
            level, color = 'High', 'coral'
            message = "Significant study gaps. Time to get back on track — start with just 20 minutes."

        return {
            'risk_score': risk_score,
            'risk_level': level,
            'risk_color': color,
            'message': message,
            'factors': [f for f in factors if f['impact'] != 'positive'][:3],
            'strengths': [f for f in factors if f['impact'] == 'positive'][:2],
            'features': f,
        }
