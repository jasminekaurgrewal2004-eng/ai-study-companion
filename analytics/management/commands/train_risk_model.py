"""
Train the F3 XGBoost risk-scoring model.

Usage:
    python manage.py train_risk_model

Outputs (models/):
    risk_xgb.pkl
    risk_shap_explainer.pkl

Evaluation: 5-fold stratified CV — ROC-AUC, precision, recall, F1, confusion matrix,
            SHAP summary (text).
"""
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Train XGBoost risk model with 5-fold CV and SHAP'

    def handle(self, *args, **options):
        from analytics.ml.feature_engineering import (
            build_user_risk_features, RISK_FEATURE_COLS,
        )

        self.stdout.write('Building user risk feature matrix…')
        df = build_user_risk_features()

        if df.empty or len(df) < 10:
            self.stdout.write(self.style.ERROR(
                'Too few users. Run generate_synthetic_data first.'
            ))
            return

        self.stdout.write(
            f'  {len(df)} users  |  at-risk: {df["at_risk"].sum()} ({df["at_risk"].mean()*100:.1f}%)'
        )

        X = df[RISK_FEATURE_COLS].fillna(0).values
        y = df['at_risk'].values

        # ── 5-fold stratified CV ──────────────────────────────────────────────
        from sklearn.model_selection import StratifiedKFold, cross_validate
        from sklearn.metrics import make_scorer, roc_auc_score, confusion_matrix
        import xgboost as xgb

        clf = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric='logloss',
            random_state=42,
        )
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        cv_results = cross_validate(
            clf, X, y, cv=skf,
            scoring={
                'roc_auc': 'roc_auc',
                'precision': 'precision',
                'recall': 'recall',
                'f1': 'f1',
            },
            return_train_score=False,
        )

        self.stdout.write('\n── 5-fold CV results ───────────────────────────────')
        for metric in ['roc_auc', 'precision', 'recall', 'f1']:
            vals = cv_results[f'test_{metric}']
            self.stdout.write(f'  {metric:12s}: {vals.mean():.4f} ± {vals.std():.4f}')

        # ── Full-data refit ───────────────────────────────────────────────────
        self.stdout.write('\nRefitting on full dataset…')
        clf.fit(X, y)

        # Confusion matrix on full data
        y_pred = clf.predict(X)
        cm = confusion_matrix(y, y_pred)
        self.stdout.write(f'  Confusion matrix (full train):\n{cm}')

        # ── SHAP ──────────────────────────────────────────────────────────────
        self.stdout.write('\nComputing SHAP values…')
        import shap, pandas as pd
        explainer = shap.TreeExplainer(clf)
        X_df = pd.DataFrame(X, columns=RISK_FEATURE_COLS)
        shap_values = explainer.shap_values(X_df)
        if isinstance(shap_values, list):
            sv = shap_values[1]
        else:
            sv = shap_values

        mean_abs = np.abs(sv).mean(axis=0)
        self.stdout.write('\n── SHAP feature importance ─────────────────────────')
        for name, val in sorted(zip(RISK_FEATURE_COLS, mean_abs), key=lambda x: -x[1]):
            bar = '█' * int(val * 40 / (mean_abs.max() + 1e-9))
            self.stdout.write(f'  {name:30s} {val:.4f}  {bar}')

        # ── Save ──────────────────────────────────────────────────────────────
        import joblib
        out_dir = Path('models')
        out_dir.mkdir(exist_ok=True)
        joblib.dump(clf, out_dir / 'risk_xgb.pkl')
        joblib.dump(explainer, out_dir / 'risk_shap_explainer.pkl')

        self.stdout.write(self.style.SUCCESS('\nSaved risk_xgb.pkl + risk_shap_explainer.pkl to models/'))
