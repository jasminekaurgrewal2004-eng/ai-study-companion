"""
Train the F2 sentence-transformers + OPTICS confusion-cluster model.

Usage:
    python manage.py train_confusion_clusters

Outputs (models/):
    confusion_optics.pkl
    confusion_embeddings.npy
    confusion_labels.json
    confusion_centroids.npy

Note: Uses sklearn OPTICS (no C++ compilation required) instead of HDBSCAN.
      Both algorithms produce hierarchical density-based clusters with noise (-1).
"""
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Train OPTICS confusion clusters from chat history'

    def handle(self, *args, **options):
        from analytics.ml.feature_engineering import get_chat_features

        self.stdout.write('Loading chat messages from ORM…')
        df = get_chat_features()

        if df.empty:
            self.stdout.write(self.style.ERROR(
                'No chat data found. Run generate_synthetic_data first.'
            ))
            return

        messages = df['content'].tolist()
        self.stdout.write(f'  {len(messages)} user messages across {df["user_id"].nunique()} users')

        # ── Embed ─────────────────────────────────────────────────────────────
        self.stdout.write('Embedding with all-MiniLM-L6-v2…')
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        embeddings = embedder.encode(messages, show_progress_bar=True, batch_size=64)
        self.stdout.write(f'  Embeddings shape: {embeddings.shape}')

        # ── OPTICS clustering ─────────────────────────────────────────────────
        self.stdout.write('Clustering with sklearn OPTICS…')
        from sklearn.cluster import OPTICS
        min_sz = max(5, len(messages) // 40)
        clusterer = OPTICS(
            min_samples=min_sz,
            min_cluster_size=min_sz,
            metric='euclidean',
            cluster_method='xi',
            xi=0.05,
        )
        labels_arr = clusterer.fit_predict(embeddings)
        n_clusters = len(set(labels_arr)) - (1 if -1 in labels_arr else 0)
        noise_pct = (labels_arr == -1).sum() / len(labels_arr) * 100
        self.stdout.write(f'  Clusters found: {n_clusters}  |  Noise: {noise_pct:.1f}%')

        # ── TF-IDF labels ─────────────────────────────────────────────────────
        from sklearn.feature_extraction.text import TfidfVectorizer

        labels_dict: dict[str, str] = {'-1': 'Other'}
        cluster_centroids = []

        unique_ids = sorted(set(labels_arr))
        for cid in unique_ids:
            if cid == -1:
                cluster_centroids.append(np.zeros(embeddings.shape[1]))
                continue
            mask = labels_arr == cid
            cluster_msgs = [m for m, b in zip(messages, mask) if b]
            cluster_embs = embeddings[mask]
            centroid = cluster_embs.mean(axis=0)
            cluster_centroids.append(centroid)

            try:
                vec = TfidfVectorizer(
                    max_features=300, stop_words='english', ngram_range=(1, 2)
                )
                tfidf = vec.fit_transform(cluster_msgs)
                mean_scores = np.asarray(tfidf.mean(axis=0)).ravel()
                top_idx = mean_scores.argsort()[::-1][:5]
                terms = [vec.get_feature_names_out()[i] for i in top_idx]
                label = ' · '.join(terms)
            except Exception:
                label = f'Cluster {cid}'

            labels_dict[str(cid)] = label
            self.stdout.write(f'  Cluster {cid:3d} ({mask.sum():4d} msgs): {label}')

        centroids_arr = (
            np.vstack(cluster_centroids) if cluster_centroids
            else np.zeros((1, embeddings.shape[1]))
        )

        # ── Silhouette score ──────────────────────────────────────────────────
        non_noise = labels_arr != -1
        if non_noise.sum() > 1 and n_clusters > 1:
            from sklearn.metrics import silhouette_score
            sil = silhouette_score(embeddings[non_noise], labels_arr[non_noise])
            self.stdout.write(f'  Silhouette (non-noise): {sil:.4f}')

        # ── Save ──────────────────────────────────────────────────────────────
        import json, joblib
        out_dir = Path('models')
        out_dir.mkdir(exist_ok=True)

        joblib.dump(clusterer, out_dir / 'confusion_optics.pkl')
        np.save(str(out_dir / 'confusion_embeddings.npy'), embeddings)
        np.save(str(out_dir / 'confusion_centroids.npy'), centroids_arr)
        with open(out_dir / 'confusion_labels.json', 'w') as f:
            json.dump(labels_dict, f, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f'\nSaved OPTICS model + embeddings + labels to models/  '
            f'({n_clusters} clusters, {noise_pct:.0f}% noise)'
        ))
