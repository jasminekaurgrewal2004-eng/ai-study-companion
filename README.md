# AI Study Companion

A Django-based adaptive study platform that uses machine learning to predict
forgetting, surface confusion patterns, and flag at-risk learners.

## Quick Start

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py generate_synthetic_data   # seed 50 demo users
python manage.py train_forgetting_curve
python manage.py train_confusion_clusters
python manage.py train_risk_model
python manage.py runserver
```

## Machine Learning

Three ML subsystems run behind the dashboard. Each has an exploratory notebook,
a training management command, a lazy-loading inference wrapper, and a JSON
endpoint consumed by the frontend.

---

### F1 — Forgetting Curve (Smart Review Queue)

Predicts the probability a user will still recall a flashcard right now, and
recommends the optimal next review day using a Cox Proportional-Hazards
survival model.

| Artefact | Path |
|---|---|
| Notebook | [`notebooks/01_forgetting_curve.ipynb`](notebooks/01_forgetting_curve.ipynb) |
| Inference wrapper | [`analytics/ml/forgetting_curve.py`](analytics/ml/forgetting_curve.py) |
| Train command | `python manage.py train_forgetting_curve` |
| Saved model | `models/forgetting_curve.pkl` |
| API endpoint | `GET /api/analytics/review-queue/` |

**Model**: `lifelines.CoxPHFitter(penalizer=0.1)`  
**Covariates**: avg\_grade, num\_prior\_reviews, hours\_since\_last\_review, skill, topic\_difficulty  
**Target metric**: Concordance index ≥ 0.70  (achieved **C-index = 0.89** on synthetic data)

**Response schema**:
```json
{
  "review_queue": [
    {"card_id": 1, "topic": "calculus", "p_recall": 0.34, "optimal_review_in_days": 2}
  ]
}
```

---

### F2 — Confusion Clustering (What You Struggle With)

Groups a user's chat questions into semantic clusters to surface recurring
confusion topics. Uses sentence-transformers embeddings + OPTICS density
clustering + TF-IDF labels.

| Artefact | Path |
|---|---|
| Notebook | [`notebooks/02_confusion_clustering.ipynb`](notebooks/02_confusion_clustering.ipynb) |
| Inference wrapper | [`analytics/ml/confusion_clusters.py`](analytics/ml/confusion_clusters.py) |
| Train command | `python manage.py train_confusion_clusters` |
| Saved model | `models/confusion_optics.pkl`, `models/confusion_embeddings.npy`, `models/confusion_labels.json`, `models/confusion_centroids.npy` |
| API endpoint | `GET /api/analytics/confusion-map/` |

**Model**: `sklearn.cluster.OPTICS` on `sentence-transformers/all-MiniLM-L6-v2` embeddings (384-dim)  
**Labelling**: Top-5 TF-IDF bi-gram terms per cluster  
**Target metric**: Silhouette score ≥ 0.35 (achieved **0.45** on synthetic data)

**Response schema**:
```json
{
  "clusters": [
    {
      "label": "integration · calculus · limits",
      "count": 42,
      "example_question": "How do I solve integration by parts?",
      "suggested_topic": "calculus",
      "suggested_action": "Review calculus flashcards"
    }
  ]
}
```

---

### F3 — Risk Score (At-Risk Badge)

Produces a per-user risk probability (low / medium / high) and SHAP-based
top-3 explanatory factors. Uses an XGBoost binary classifier trained on
7 behavioural features.

| Artefact | Path |
|---|---|
| Notebook | [`notebooks/03_risk_modeling.ipynb`](notebooks/03_risk_modeling.ipynb) |
| Inference wrapper | [`analytics/ml/risk_score.py`](analytics/ml/risk_score.py) |
| Train command | `python manage.py train_risk_model` |
| Saved model | `models/risk_xgb.pkl`, `models/risk_shap_explainer.pkl` |
| API endpoint | `GET /api/analytics/risk-score/` |

**Model**: `XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05)`  
**Features**: avg\_quiz\_score\_30d, sessions\_7d, avg\_session\_len, review\_streak, pct\_grade\_low, hours\_since\_activity, topic\_diversity  
**CV results**: ROC-AUC = 0.94, F1 = 0.92 (5-fold stratified, synthetic data)

**Response schema**:
```json
{
  "risk": 0.72,
  "band": "high",
  "top_factors": [
    {"name": "avg_quiz_score_30d", "impact": 1.38, "direction": "negative"}
  ]
}
```

---

### Additional Endpoints

| Method | URL | Description |
|---|---|---|
| `POST` | `/api/analytics/log-review/` | Record a flashcard review and update PredictionLog |

**POST body**: `{"card_id": 1, "grade": 4, "response_time_ms": 1500}`

---

## Running Tests

```bash
pip install pytest pytest-django
python -m pytest analytics/tests/test_endpoints.py -v
# 9 passed
```

## Feature Engineering

All ORM → pandas extraction lives in
[`analytics/ml/feature_engineering.py`](analytics/ml/feature_engineering.py):

- `get_review_features(user_id=None)` — FlashcardReview rows with computed covariates
- `get_quiz_features(user_id=None)` — QuizAttempt rows, score normalised to \[0, 1\]
- `get_chat_features(user_id=None)` — user-role ChatHistory messages
- `build_user_risk_features(as_of=None)` — one row per user with all 7 risk features

## Project Layout

```
analytics/
  management/commands/
    generate_synthetic_data.py   # seed demo data (50 users)
    train_forgetting_curve.py    # F1 training
    train_confusion_clusters.py  # F2 training
    train_risk_model.py          # F3 training
  ml/
    feature_engineering.py
    forgetting_curve.py          # F1 inference
    confusion_clusters.py        # F2 inference
    risk_score.py                # F3 inference
  tests/
    test_endpoints.py
  urls.py
  views.py
core/
  models.py        # Flashcard, FlashcardReview, QuizAttempt, ChatHistory, PredictionLog
  views.py
  urls.py
notebooks/
  01_forgetting_curve.ipynb
  02_confusion_clustering.ipynb
  03_risk_modeling.ipynb
models/            # saved .pkl / .npy artefacts (gitignored binaries)
data/
  raw/             # synthetic_reviews.csv, synthetic_quizzes.csv
```
