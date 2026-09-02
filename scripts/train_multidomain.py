#!/usr/bin/env python3
"""Train source-balanced family/genus/species heads on frozen embeddings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GroupShuffleSplit


RANKS = ("family", "genus", "species")


def balanced_weights(labels: np.ndarray, sources: np.ndarray) -> np.ndarray:
    """Approximately equalize both taxon and source contributions."""
    label_counts = pd.Series(labels).value_counts()
    source_counts = pd.Series(sources).value_counts()
    weights = np.array([
        1.0 / (float(label_counts[label]) * float(source_counts[source])) ** 0.5
        for label, source in zip(labels, sources)
    ], dtype=np.float64)
    weights /= weights.mean()
    return np.clip(weights, 0.1, 10.0)


def top_k_accuracy(y_true: np.ndarray, probabilities: np.ndarray, classes: np.ndarray, k: int) -> float:
    lookup = {label: index for index, label in enumerate(classes)}
    truth = np.array([lookup[label] for label in y_true])
    winners = np.argsort(-probabilities, axis=1)[:, :k]
    return float(np.mean(np.any(winners == truth[:, None], axis=1)))


def per_source_accuracy(y_true: np.ndarray, predicted: np.ndarray, sources: np.ndarray) -> dict[str, float]:
    return {
        source: float(accuracy_score(y_true[sources == source], predicted[sources == source]))
        for source in sorted(set(sources))
        if np.any(sources == source)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--manifest", help="Defaults to MODEL_DIR/embedded_manifest.csv")
    parser.add_argument("--embeddings", help="Defaults to MODEL_DIR/embeddings.npy")
    parser.add_argument("--out", help="Defaults to MODEL_DIR/classifiers_multidomain.joblib")
    parser.add_argument("--min-images-per-class", type=int, default=8)
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    manifest_path = Path(args.manifest) if args.manifest else model_dir / "embedded_manifest.csv"
    embedding_path = Path(args.embeddings) if args.embeddings else model_dir / "embeddings.npy"
    out = Path(args.out) if args.out else model_dir / "classifiers_multidomain.joblib"
    frame = pd.read_csv(manifest_path).fillna("")
    embeddings = np.load(embedding_path).astype(np.float32)
    if len(frame) != len(embeddings):
        raise SystemExit("embedded manifest and embeddings.npy have different row counts")
    source = frame.get("source", pd.Series(["unknown"] * len(frame))).astype(str)

    models: dict[str, LogisticRegression] = {}
    report: dict[str, dict] = {}
    for rank in RANKS:
        labels = frame[rank].astype(str)
        if "split" in frame.columns and frame["split"].astype(str).str.len().gt(0).any():
            training_candidate = frame["split"].astype(str).str.lower().eq("train")
            evaluation_candidate = frame["split"].astype(str).str.lower().isin({"val", "test"})
        else:
            training_candidate = pd.Series([True] * len(frame), index=frame.index)
            evaluation_candidate = pd.Series([False] * len(frame), index=frame.index)
        counts = labels[training_candidate & labels.ne("")].value_counts()
        allowed = set(counts[counts >= args.min_images_per_class].index)
        eligible = labels.isin(allowed)
        train_mask = training_candidate & eligible
        eval_mask = evaluation_candidate & eligible

        if not eval_mask.any() and train_mask.sum() > 1:
            indices = np.flatnonzero(train_mask.to_numpy())
            groups = frame.loc[train_mask, "split_group"].astype(str).to_numpy() if "split_group" in frame else indices
            splitter = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=42)
            fit_local, eval_local = next(splitter.split(indices, labels.iloc[indices], groups=groups))
            train_indices = indices[fit_local]
            eval_indices = indices[eval_local]
        else:
            train_indices = np.flatnonzero(train_mask.to_numpy())
            eval_indices = np.flatnonzero(eval_mask.to_numpy())

        train_labels = labels.iloc[train_indices].to_numpy()
        if len(set(train_labels)) < 2 or len(eval_indices) == 0:
            print(f"skip {rank}: need at least two trained classes and a holdout")
            continue
        train_sources = source.iloc[train_indices].to_numpy()
        weights = balanced_weights(train_labels, train_sources)
        model = LogisticRegression(max_iter=3000, C=2.0)
        model.fit(embeddings[train_indices], train_labels, sample_weight=weights)

        eval_labels = labels.iloc[eval_indices].to_numpy()
        seen = np.isin(eval_labels, model.classes_)
        eval_indices = eval_indices[seen]
        eval_labels = eval_labels[seen]
        if len(eval_indices) == 0:
            print(f"skip {rank}: holdout contains no trained classes")
            continue
        probabilities = model.predict_proba(embeddings[eval_indices])
        predicted = model.classes_[np.argmax(probabilities, axis=1)]
        eval_sources = source.iloc[eval_indices].to_numpy()
        metrics = {
            "train_images": int(len(train_indices)),
            "evaluation_images": int(len(eval_indices)),
            "classes": int(len(model.classes_)),
            "top1_accuracy": float(accuracy_score(eval_labels, predicted)),
            "top5_accuracy": top_k_accuracy(eval_labels, probabilities, model.classes_, min(5, len(model.classes_))),
            "top1_by_source": per_source_accuracy(eval_labels, predicted, eval_sources),
        }
        print(rank, metrics)
        models[rank] = model
        report[rank] = metrics

    if not models:
        raise SystemExit("No classifier could be trained; inspect class counts and split labels")
    payload = {
        "models": models,
        "metadata": {
            "backbone": "facebook/dinov2-small",
            "training": "source-and-class-balanced frozen embeddings",
            "confidence_note": "predict_proba is a model score, not taxonomic certainty",
            "evaluation": report,
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, out)
    report_path = out.with_name("training_report_multidomain.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
