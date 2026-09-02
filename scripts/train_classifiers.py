#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, top_k_accuracy_score
from sklearn.model_selection import GroupShuffleSplit

RANKS = ("family", "genus", "species")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", default="models")
    p.add_argument("--min-images-per-class", type=int, default=8)
    p.add_argument("--test-size", type=float, default=0.2)
    args = p.parse_args()

    model_dir = Path(args.model_dir)
    x = np.load(model_dir / "embeddings.npy").astype(np.float32)
    df = pd.read_csv(model_dir / "embedded_manifest.csv").fillna("")

    models = {}
    report = {}
    for rank in RANKS:
        labels = df[rank].astype(str)
        counts = labels.value_counts()
        allowed = counts[counts >= args.min_images_per_class].index
        mask = labels.isin(allowed) & (labels != "")
        x_rank = x[mask.to_numpy()]
        y_rank = labels[mask].to_numpy()
        groups = df.loc[mask, "split_group"].astype(str).to_numpy() if "split_group" in df.columns else np.arange(len(y_rank))

        if len(np.unique(y_rank)) < 2:
            print(f"skip {rank}: need >= 2 classes after filtering")
            continue

        splitter = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=42)
        train_idx, test_idx = next(splitter.split(x_rank, y_rank, groups=groups))
        model = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0)
        model.fit(x_rank[train_idx], y_rank[train_idx])

        pred = model.predict(x_rank[test_idx])
        proba = model.predict_proba(x_rank[test_idx])
        topk = min(5, len(model.classes_))
        metrics = {
            "n_images": int(len(y_rank)),
            "n_classes": int(len(model.classes_)),
            "top1_accuracy": float(accuracy_score(y_rank[test_idx], pred)),
            "top5_accuracy": float(top_k_accuracy_score(y_rank[test_idx], proba, labels=model.classes_, k=topk)),
        }
        print(rank, metrics)

        # Refit on all eligible data after evaluation.
        model.fit(x_rank, y_rank)
        models[rank] = model
        report[rank] = metrics

    payload = {
        "models": models,
        "metadata": {
            "backbone": "facebook/dinov2-small",
            "confidence_note": "predict_proba is a model score, not taxonomic certainty",
            "evaluation": report,
        },
    }
    joblib.dump(payload, model_dir / "classifiers.joblib")
    (model_dir / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved classifiers -> {model_dir / 'classifiers.joblib'}")


if __name__ == "__main__":
    main()
