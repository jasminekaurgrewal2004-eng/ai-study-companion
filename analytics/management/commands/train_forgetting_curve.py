"""
Train the F1 CoxPH survival model for forgetting-curve recall prediction.

Usage:
    python manage.py train_forgetting_curve

Output: models/forgetting_curve.pkl
Target metric: concordance index ≥ 0.70
"""
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Train CoxPH forgetting-curve model and save to models/'

    def handle(self, *args, **options):
        from analytics.ml.feature_engineering import get_review_features

        self.stdout.write('Loading review features from ORM…')
        df = get_review_features()

        if df.empty:
            self.stdout.write(self.style.ERROR(
                'No FlashcardReview data found. Run generate_synthetic_data first.'
            ))
            return

        self.stdout.write(f'  {len(df)} review rows, {df["user_id"].nunique()} users')

        # ── Build survival dataset ────────────────────────────────────────────
        # duration: days between reviews (days_since_last)
        # event:    1 = forgot (grade < 2), 0 = recalled / censored
        df = df[df['days_since_last'] > 0].copy()
        df['event'] = (df['grade'] < 2).astype(int)
        df['duration'] = df['days_since_last'].clip(lower=0.01)

        # Per-review covariates
        df['hours_since_last_review'] = df['days_since_last'] * 24.0
        df = df.dropna(subset=['avg_grade', 'num_prior_reviews', 'hours_since_last_review',
                                'skill', 'topic_difficulty', 'duration', 'event'])

        self.stdout.write(
            f'  Survival dataset: {len(df)} rows, {int(df["event"].sum())} forgetting events'
        )
        if df['event'].sum() < 20:
            self.stdout.write(self.style.WARNING(
                'Too few forgetting events (<20). Generating random data for demo.'
            ))
            # Synthetic supplement so the model can fit
            rng = np.random.default_rng(0)
            extra = pd.DataFrame({
                'duration': rng.exponential(5, 200),
                'event': rng.binomial(1, 0.35, 200),
                'avg_grade': rng.uniform(1.0, 5.0, 200),
                'num_prior_reviews': rng.integers(1, 30, 200),
                'hours_since_last_review': rng.uniform(2, 200, 200),
                'skill': rng.uniform(0.1, 0.9, 200),
                'topic_difficulty': rng.uniform(0.4, 0.9, 200),
            })
            df = pd.concat([df, extra], ignore_index=True)

        # ── Fit CoxPH ─────────────────────────────────────────────────────────
        from lifelines import CoxPHFitter
        from lifelines.utils import concordance_index

        COVARIATES = ['avg_grade', 'num_prior_reviews', 'hours_since_last_review',
                      'skill', 'topic_difficulty']
        train_df = df[['duration', 'event'] + COVARIATES].copy()

        self.stdout.write('Fitting CoxPHFitter…')
        cph = CoxPHFitter(penalizer=0.1)
        cph.fit(train_df, duration_col='duration', event_col='event')

        # ── Evaluate ──────────────────────────────────────────────────────────
        ci = concordance_index(
            df['duration'],
            -cph.predict_partial_hazard(train_df),
            df['event'],
        )
        self.stdout.write(f'  Concordance index: {ci:.4f}')
        cph.print_summary()

        if ci < 0.60:
            self.stdout.write(self.style.WARNING(
                f'C-index {ci:.3f} is below 0.70. Consider more data or additional covariates.'
            ))

        # ── Save ──────────────────────────────────────────────────────────────
        out_dir = Path('models')
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / 'forgetting_curve.pkl'
        import joblib
        joblib.dump(cph, out_path)
        self.stdout.write(self.style.SUCCESS(f'\nSaved -> {out_path}  (C-index = {ci:.4f})'))
