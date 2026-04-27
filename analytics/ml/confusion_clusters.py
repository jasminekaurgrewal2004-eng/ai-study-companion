"""F2 — sentence-transformers + OPTICS confusion cluster wrapper.

Lazy-loads artefacts from models/ on first call (thread-safe).
Falls back gracefully when model files are missing.

Saved artefacts
---------------
models/confusion_optics.pkl       – fitted OPTICS instance
models/confusion_embeddings.npy   – corpus embeddings (shape N×384)
models/confusion_labels.json      – {str(cluster_id): label_string}
models/confusion_centroids.npy    – per-cluster mean embeddings

Public API
----------
get_user_clusters(user_id) ->
    [{'label': str, 'count': int,
      'example_question': str, 'suggested_topic': str}]
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

import numpy as np

_MODELS_DIR = Path(__file__).resolve().parents[2] / 'models'
_OPTICS_PATH = _MODELS_DIR / 'confusion_optics.pkl'
_LABELS_PATH = _MODELS_DIR / 'confusion_labels.json'
_CENTROIDS_PATH = _MODELS_DIR / 'confusion_centroids.npy'

_artefacts = None
_artefacts_lock = threading.Lock()

# sentence-transformers model name (no internet needed after first download)
_EMBED_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'


def _load_artefacts():
    """Returns (embedder, optics_model, centroids, labels_dict) or None."""
    global _artefacts
    if _artefacts is None:
        with _artefacts_lock:
            if _artefacts is None:
                if not (_OPTICS_PATH.exists() and _LABELS_PATH.exists() and _CENTROIDS_PATH.exists()):
                    _artefacts = 'missing'
                else:
                    try:
                        import joblib
                        from sentence_transformers import SentenceTransformer
                        embedder = SentenceTransformer(_EMBED_MODEL)
                        optics = joblib.load(_OPTICS_PATH)
                        centroids = np.load(str(_CENTROIDS_PATH))
                        with open(_LABELS_PATH) as f:
                            labels = json.load(f)
                        _artefacts = (embedder, optics, centroids, labels)
                    except Exception as exc:
                        _artefacts = 'missing'
    return None if _artefacts == 'missing' else _artefacts


def _cosine_assign(emb: np.ndarray, centroids: np.ndarray, threshold: float = 0.6) -> int:
    """Assign embedding to nearest centroid if cosine ≥ threshold, else -1."""
    if len(centroids) == 0:
        return -1
    norms = np.linalg.norm(centroids, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    c_norm = centroids / norms
    e_norm = emb / (np.linalg.norm(emb) + 1e-9)
    sims = c_norm @ e_norm
    best = int(np.argmax(sims))
    return best if sims[best] >= threshold else -1


def _infer_suggested_topic(label: str) -> str:
    """Heuristic: pick the study topic most represented in the cluster label."""
    from analytics.ml.feature_engineering import TOPICS
    label_lower = label.lower()
    for t in TOPICS:
        key = t.replace('_', ' ')
        if key in label_lower or t in label_lower:
            return t
    return 'General'


# ── public API ────────────────────────────────────────────────────────────────

def get_user_clusters(user_id: int) -> list[dict]:
    """
    Assign the user's chat messages to confusion clusters.

    Returns
    -------
    List of dicts sorted by count descending.
    Each dict: {'label', 'count', 'example_question', 'suggested_topic'}
    """
    from core.models import ChatHistory

    messages_qs = ChatHistory.objects.filter(user_id=user_id, role='user').order_by('timestamp')
    messages = list(messages_qs.values_list('content', flat=True))

    if not messages:
        return []

    artefacts = _load_artefacts()
    if artefacts is None:
        return [{'status': 'warming_up'}]

    embedder, _, centroids, labels = artefacts

    embeddings = embedder.encode(messages, show_progress_bar=False, batch_size=64)

    cluster_data: dict[str, dict] = {}
    for msg, emb in zip(messages, embeddings):
        cid = _cosine_assign(emb, centroids)
        label = labels.get(str(cid), 'Other')
        if label not in cluster_data:
            cluster_data[label] = {'count': 0, 'examples': []}
        cluster_data[label]['count'] += 1
        cluster_data[label]['examples'].append(msg)

    output = []
    for label, data in cluster_data.items():
        output.append({
            'label': label,
            'count': data['count'],
            'example_question': data['examples'][0],
            'suggested_topic': _infer_suggested_topic(label),
        })

    return sorted(output, key=lambda x: x['count'], reverse=True)
