"""
Generate realistic synthetic study data for 50 users.

Usage:
    python manage.py generate_synthetic_data
    python manage.py generate_synthetic_data --users 20 --clear

Algorithm
---------
* Each user has skill ~ Beta(2, 5)  (right-skewed → most users below average)
* Flashcard reviews follow the Ebbinghaus forgetting curve:
    recall_prob = exp(-Δt / stability)
    stability grows with grade, shrinks on failure
* Quiz scores correlate with recent review activity and skill
* Chat messages drawn from 20 confusion-phrase templates × 8 topics
"""
import csv
import os
import random
from datetime import timedelta
from pathlib import Path

import numpy as np
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    ChatHistory, ChatSession, Flashcard, FlashcardReview, QuizAttempt,
)

TOPICS = [
    'calculus', 'linear_algebra', 'machine_learning',
    'operating_systems', 'databases', 'networks',
    'object_oriented_programming', 'statistics',
]

TOPIC_DIFFICULTY = {
    'calculus': 0.75, 'linear_algebra': 0.65, 'machine_learning': 0.80,
    'operating_systems': 0.60, 'databases': 0.55, 'networks': 0.58,
    'object_oriented_programming': 0.50, 'statistics': 0.70,
}

CONFUSION_PHRASES = [
    "I'm confused about {topic}, can you explain the basics?",
    "I don't understand {topic} at all, where do I start?",
    "Can you help me with {topic}? It's really hard.",
    "What is the key idea behind {topic}?",
    "Why does {topic} work that way?",
    "I keep forgetting how {topic} works.",
    "Can you give me an example of {topic}?",
    "I struggle with {topic} every time it comes up.",
    "How do I apply {topic} in practice?",
    "What's the difference between the main concepts in {topic}?",
    "I'm lost when it comes to {topic}.",
    "Could you simplify {topic} for me?",
    "I made errors on the quiz about {topic}, help?",
    "My notes on {topic} don't make sense to me anymore.",
    "I understand the basics of {topic} but get stuck on the advanced parts.",
    "What are the most important things to know about {topic}?",
    "I keep mixing up the terms in {topic}.",
    "Please walk me through a problem in {topic}.",
    "How does {topic} connect to the other subjects?",
    "I reviewed {topic} but I'm still confused.",
]

FLASHCARD_TEMPLATES = {
    'calculus': [
        ("What is the derivative of sin(x)?", "cos(x)"),
        ("State the chain rule.", "d/dx[f(g(x))] = f'(g(x))·g'(x)"),
        ("What is the integral of x^n?", "x^(n+1)/(n+1) + C (n≠-1)"),
        ("Define a limit.", "lim_{x→a} f(x) = L if f(x) approaches L as x→a"),
        ("Product rule for derivatives?", "(uv)' = u'v + uv'"),
        ("What is a definite integral?", "∫_a^b f(x)dx — net signed area under f from a to b"),
    ],
    'linear_algebra': [
        ("What is a vector space?", "A set V with addition and scalar mult. satisfying 8 axioms"),
        ("Define the dot product.", "a·b = |a||b|cos(θ) = Σ aᵢbᵢ"),
        ("What is the null space of A?", "The set of all x such that Ax = 0"),
        ("Eigenvalue equation?", "Av = λv, where v is the eigenvector"),
        ("What is an orthogonal matrix?", "A square matrix where A^T A = I"),
        ("State the rank-nullity theorem.", "rank(A) + nullity(A) = number of columns"),
    ],
    'machine_learning': [
        ("What is overfitting?", "Model learns noise; poor generalisation to unseen data"),
        ("Bias-variance tradeoff?", "High bias → underfitting; high variance → overfitting"),
        ("Define cross-entropy loss.", "-Σ y_i log(ŷ_i) — measures distribution divergence"),
        ("What is gradient descent?", "Iterative optimisation: θ ← θ - α∇L(θ)"),
        ("What is a kernel in SVMs?", "A function computing similarity in a high-dim feature space"),
        ("Define precision and recall.", "Precision=TP/(TP+FP); Recall=TP/(TP+FN)"),
    ],
    'operating_systems': [
        ("What is a process?", "A program in execution with its own address space"),
        ("Define deadlock.", "Circular waiting for resources held by other processes"),
        ("What is virtual memory?", "Abstraction giving each process an isolated address space"),
        ("LRU page replacement?", "Evict the page Least Recently Used"),
        ("What is a semaphore?", "Synchronisation primitive — counter controlling access"),
        ("Difference: process vs thread?", "Threads share address space; processes are isolated"),
    ],
    'databases': [
        ("What is ACID?", "Atomicity, Consistency, Isolation, Durability"),
        ("Define a foreign key.", "Attribute referencing the primary key of another table"),
        ("What is normalisation?", "Organising tables to reduce redundancy and dependency"),
        ("SQL JOIN types?", "INNER, LEFT, RIGHT, FULL OUTER"),
        ("What is an index?", "Data structure for fast row lookup (e.g. B-tree, hash)"),
        ("What is a transaction?", "Sequence of operations treated as a single unit"),
    ],
    'networks': [
        ("OSI model layers?", "Physical, Data-Link, Network, Transport, Session, Presentation, Application"),
        ("TCP vs UDP?", "TCP: reliable, ordered; UDP: fast, connectionless"),
        ("What is DNS?", "Domain Name System — translates hostnames to IP addresses"),
        ("Define subnetting.", "Dividing an IP network into smaller sub-networks"),
        ("What is a MAC address?", "Hardware address uniquely identifying a NIC"),
        ("HTTP vs HTTPS?", "HTTPS adds TLS encryption over HTTP"),
    ],
    'object_oriented_programming': [
        ("Four OOP pillars?", "Encapsulation, Abstraction, Inheritance, Polymorphism"),
        ("What is encapsulation?", "Bundling data and methods; hiding internal state"),
        ("Difference: interface vs abstract class?", "Interface: pure contract; abstract class: partial impl."),
        ("What is method overriding?", "Subclass provides specific implementation of a superclass method"),
        ("Define polymorphism.", "Same interface, different underlying implementations"),
        ("What is the Liskov substitution principle?", "Subtypes must be usable in place of their base type"),
    ],
    'statistics': [
        ("Central Limit Theorem?", "Sample mean → Normal as n→∞ regardless of population dist."),
        ("What is p-value?", "P(data as extreme | H₀ true) — small → reject H₀"),
        ("Define variance.", "E[(X-μ)²] — average squared deviation from mean"),
        ("Bayes' theorem?", "P(A|B) = P(B|A)·P(A) / P(B)"),
        ("What is Type I vs Type II error?", "Type I: false positive; Type II: false negative"),
        ("Define correlation.", "Pearson r ∈ [-1,1] — linear dependence strength & direction"),
    ],
}


def _simulate_reviews(user, card, topic, skill, now):
    """Simulate an Ebbinghaus review history for one card."""
    difficulty = TOPIC_DIFFICULTY[topic]
    stability = max(0.5, skill * 4.0 / (difficulty + 0.1))
    n_reviews = random.randint(3, 20)
    start = now - timedelta(days=n_reviews * stability * 1.3)
    current = start

    reviews_created = []
    for k in range(n_reviews):
        delta_t = stability * random.uniform(0.7, 1.5)
        review_time = current + timedelta(days=delta_t)
        if review_time > now:
            break

        recall_prob = np.exp(-delta_t / stability)
        # Skill modulates actual recall probability
        recalled = random.random() < (recall_prob * 0.5 + skill * 0.5)

        if recalled:
            grade = random.choices([2, 3, 4, 5], weights=[0.10, 0.30, 0.40, 0.20])[0]
            stability = min(stability * random.uniform(1.5, 2.5), 30.0)
        else:
            grade = random.choices([0, 1], weights=[0.40, 0.60])[0]
            stability = max(0.5, stability * random.uniform(0.4, 0.6))

        days_since = (review_time - current).total_seconds() / 86400
        rt_ms = random.randint(500, 15_000)

        # Use create with explicit reviewed_at (auto_now_add can't be overridden easily)
        rev = FlashcardReview(
            user=user, flashcard=card,
            grade=grade,
            days_since_last=round(days_since, 3),
            response_time_ms=rt_ms,
        )
        # Override auto_now_add by saving with update_fields after setting reviewed_at
        rev.save()
        FlashcardReview.objects.filter(pk=rev.pk).update(reviewed_at=review_time)
        reviews_created.append((grade, stability, review_time))
        current = review_time

    # Update card SM-2 state from last review
    if reviews_created:
        last_grade, last_stab, last_time = reviews_created[-1]
        card.repetitions = len(reviews_created)
        card.interval = max(1, int(last_stab))
        card.ease_factor = max(1.3, min(2.5, 2.5 * skill + random.gauss(0, 0.1)))
        card.next_review = last_time + timedelta(days=last_stab)
        card.save()

    return len(reviews_created)


class Command(BaseCommand):
    help = 'Generate realistic synthetic study data (50 users)'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=50)
        parser.add_argument('--clear', action='store_true',
                            help='Delete existing synth_user_* accounts first')
        parser.add_argument('--seed', type=int, default=42)

    def handle(self, *args, **options):
        np.random.seed(options['seed'])
        random.seed(options['seed'])
        now = timezone.now()
        n_users = options['users']

        if options['clear']:
            deleted, _ = User.objects.filter(username__startswith='synth_user_').delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing synth users.'))

        review_rows = []
        quiz_rows = []

        for i in range(n_users):
            skill = float(np.random.beta(2, 5))
            username = f'synth_user_{i:03d}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@synth.example.com'},
            )
            if created:
                user.set_password('synthpass123')
                user.save()

            # ── Flashcards + reviews ──────────────────────────────────────────
            for topic in TOPICS:
                templates = FLASHCARD_TEMPLATES[topic]
                n_cards = random.randint(2, len(templates))
                for j in range(n_cards):
                    front, back = templates[j % len(templates)]
                    card = Flashcard.objects.create(
                        user=user, front=front, back=back, subject=topic,
                    )
                    n_rev = _simulate_reviews(user, card, topic, skill, now)
                    # collect for CSV
                    for rev in FlashcardReview.objects.filter(flashcard=card).order_by('reviewed_at'):
                        review_rows.append({
                            'user': username, 'topic': topic,
                            'grade': rev.grade, 'days_since_last': rev.days_since_last,
                            'response_time_ms': rev.response_time_ms,
                            'reviewed_at': str(rev.reviewed_at),
                        })

            # ── Quiz attempts ─────────────────────────────────────────────────
            n_quizzes = random.randint(5, 25)
            for _ in range(n_quizzes):
                topic = random.choice(TOPICS)
                difficulty = TOPIC_DIFFICULTY[topic]
                recent_rev = FlashcardReview.objects.filter(
                    user=user,
                    reviewed_at__gte=now - timedelta(days=30),
                ).count()
                activity_bonus = min(0.25, recent_rev / 60.0)
                base = skill * (1.0 - difficulty * 0.3) + activity_bonus
                score_01 = float(np.clip(base + np.random.normal(0, 0.12), 0.0, 1.0))
                n_q = random.choice([5, 10, 15, 20])
                attempt = QuizAttempt(
                    user=user, subject=topic,
                    score=round(score_01 * 100.0, 1),
                    total_questions=n_q,
                    correct_answers=int(score_01 * n_q),
                    time_taken_seconds=random.randint(120, 900),
                )
                attempt.save()
                QuizAttempt.objects.filter(pk=attempt.pk).update(
                    attempted_at=now - timedelta(days=random.uniform(0, 60))
                )
                quiz_rows.append({
                    'user': username, 'topic': topic,
                    'score': round(score_01, 4), 'num_questions': n_q,
                    'attempted_at': str(attempt.attempted_at),
                })

            # ── Chat history ──────────────────────────────────────────────────
            n_sessions = random.randint(2, 6)
            for s in range(n_sessions):
                sess_time = now - timedelta(days=random.uniform(0, 30))
                session = ChatSession(user=user, title=f'Study Session {s + 1}')
                session.save()
                ChatSession.objects.filter(pk=session.pk).update(created_at=sess_time)
                n_msgs = random.randint(3, 15)
                for m in range(n_msgs):
                    topic = random.choice(TOPICS)
                    phrase = random.choice(CONFUSION_PHRASES).format(topic=topic)
                    msg_time = sess_time + timedelta(minutes=m * random.randint(2, 10))
                    ch = ChatHistory(user=user, session=session, role='user', content=phrase)
                    ch.save()
                    ChatHistory.objects.filter(pk=ch.pk).update(timestamp=msg_time)
                    # brief assistant reply
                    ar = ChatHistory(
                        user=user, session=session, role='assistant',
                        content=f'Great question about {topic}! Let me explain the key idea…',
                    )
                    ar.save()
                    ChatHistory.objects.filter(pk=ar.pk).update(
                        timestamp=msg_time + timedelta(seconds=random.randint(5, 30))
                    )

            if (i + 1) % 10 == 0:
                self.stdout.write(f'  Created {i + 1}/{n_users} users…')

        # ── Dump CSVs for inspection ──────────────────────────────────────────
        raw_dir = Path('data/raw')
        raw_dir.mkdir(parents=True, exist_ok=True)

        self._write_csv(raw_dir / 'synthetic_reviews.csv', review_rows,
                        ['user', 'topic', 'grade', 'days_since_last', 'response_time_ms', 'reviewed_at'])
        self._write_csv(raw_dir / 'synthetic_quizzes.csv', quiz_rows,
                        ['user', 'topic', 'score', 'num_questions', 'attempted_at'])

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! {n_users} synthetic users created.\n'
            f'  Reviews: {len(review_rows)}  |  Quizzes: {len(quiz_rows)}\n'
            f'  CSVs written to data/raw/'
        ))

    @staticmethod
    def _write_csv(path, rows, fieldnames):
        if not rows:
            return
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
