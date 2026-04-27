"""
ML-driven quiz generation and score prediction using F1/F2 artefacts.

Public API
----------
get_smart_topics(user_id) ->
    [{'topic': str, 'priority': float, 'predicted_score_pct': float, 'reason': str}]

generate_quiz_questions(user_id, topic, count=10) ->
    [{'id': int, 'q': str, 'opts': list[str], 'correct': int,
      'diff': str, 'hint': str, 'explain': str,
      'card_id': int, 'p_recall': float}]

predict_score(card_ids, user_id) ->
    {'predicted_score': int, 'predicted_accuracy': float,
     'max_score': int, 'confidence': str}
"""
from __future__ import annotations

import random


def get_smart_topics(user_id: int) -> list[dict]:
    """Rank topics by learning need: low recall + frequent confusion = high priority."""
    from analytics.ml.forgetting_curve import predict_recall
    from analytics.ml.confusion_clusters import get_user_clusters
    from analytics.ml.feature_engineering import TOPIC_DIFFICULTY

    topics = list(TOPIC_DIFFICULTY.keys())

    clusters = get_user_clusters(user_id)
    confused_topics: set[str] = set()
    if clusters and not (len(clusters) == 1 and 'status' in clusters[0]):
        for c in clusters:
            t = c.get('suggested_topic', '')
            if t and t != 'General':
                confused_topics.add(t)

    results = []
    for topic in topics:
        recall_data = predict_recall(user_id, topic)
        p_recall = recall_data.get('p_recall', 0.7)
        confusion_boost = 0.2 if topic in confused_topics else 0.0
        priority = (1.0 - p_recall) + confusion_boost

        reason_parts = []
        if p_recall < 0.5:
            reason_parts.append('low recall')
        if topic in confused_topics:
            reason_parts.append('frequent confusion')
        reason = ', '.join(reason_parts) if reason_parts else 'scheduled review'

        results.append({
            'topic': topic,
            'priority': round(priority, 3),
            'predicted_score_pct': round(p_recall * 100, 1),
            'reason': reason,
        })

    return sorted(results, key=lambda x: x['priority'], reverse=True)


def generate_quiz_questions(user_id: int, topic: str, count: int = 10) -> list[dict]:
    """
    Build MCQ questions from flashcards for the given topic.

    Front of card = question stem.
    Back of card = correct answer.
    Distractors = backs of other cards from the same subject.
    Difficulty label is derived from the per-card CoxPH recall probability.
    """
    from core.models import Flashcard, FlashcardReview
    from analytics.ml.forgetting_curve import predict_card_recall

    topic_cards = list(
        Flashcard.objects.filter(subject__iexact=topic)
        .values('id', 'front', 'back', 'subject')
    )
    all_backs = [c['back'].strip() for c in topic_cards if c['back'].strip()]

    if len(topic_cards) < 4:
        return []

    reviewed_ids = set(
        FlashcardReview.objects.filter(
            user_id=user_id,
            flashcard__subject__iexact=topic,
        ).values_list('flashcard_id', flat=True).distinct()
    )
    reviewed = [c for c in topic_cards if c['id'] in reviewed_ids]
    unreviewed = [c for c in topic_cards if c['id'] not in reviewed_ids]
    random.shuffle(reviewed)
    random.shuffle(unreviewed)
    selected = (reviewed + unreviewed)[:count]

    questions = []
    for card in selected:
        correct_ans = card['back'].strip()
        distractors = [b for b in all_backs if b != correct_ans]
        random.shuffle(distractors)
        wrong_opts = distractors[:3]

        if len(wrong_opts) < 3:
            continue

        opts = wrong_opts + [correct_ans]
        random.shuffle(opts)
        correct_idx = opts.index(correct_ans)

        recall_data = predict_card_recall(card['id'], user_id)
        p_recall = recall_data.get('p_recall', 0.7)

        if p_recall >= 0.75:
            diff_label = 'EASY'
        elif p_recall >= 0.45:
            diff_label = 'MEDIUM'
        else:
            diff_label = 'HARD'

        questions.append({
            'id': len(questions),
            'q': card['front'],
            'opts': opts,
            'correct': correct_idx,
            'diff': f'{diff_label} · +4/−1',
            'hint': f"Think about {topic.replace('_', ' ')}",
            'explain': f'The correct answer is: {correct_ans}',
            'card_id': card['id'],
            'p_recall': round(p_recall, 3),
        })

    return questions


def predict_score(card_ids: list[int], user_id: int) -> dict:
    """
    Predict quiz score from per-card CoxPH recall probabilities.

    Scoring mirrors the frontend: +4 per correct, -1 per wrong.
    Confidence reflects what fraction of cards have actual review history.
    """
    from analytics.ml.forgetting_curve import predict_card_recall
    from core.models import FlashcardReview

    if not card_ids:
        return {
            'predicted_score': 0,
            'predicted_accuracy': 0.0,
            'max_score': 0,
            'confidence': 'low',
        }

    recalls = [
        predict_card_recall(cid, user_id).get('p_recall', 0.7)
        for cid in card_ids
    ]
    n = len(recalls)
    expected_correct = sum(recalls)
    expected_wrong = n - expected_correct
    predicted_score = max(0, round(expected_correct * 4 - expected_wrong))
    max_score = n * 4
    predicted_accuracy = round(expected_correct / n * 100, 1)

    reviewed_count = (
        FlashcardReview.objects
        .filter(flashcard_id__in=card_ids, user_id=user_id)
        .values('flashcard_id').distinct().count()
    )
    coverage = reviewed_count / n if n > 0 else 0
    confidence = 'high' if coverage > 0.7 else ('medium' if coverage > 0.3 else 'low')

    return {
        'predicted_score': predicted_score,
        'predicted_accuracy': predicted_accuracy,
        'max_score': max_score,
        'confidence': confidence,
    }
