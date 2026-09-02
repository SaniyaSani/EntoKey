#!/usr/bin/env python3
"""Orchestrate planning, resumable DINOv2 shards and hierarchical training."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("+", shlex.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-manifest", required=True)
    parser.add_argument("--config", default="configs/foundation_corpus_v06.json")
    parser.add_argument("--work-dir", default="data/foundation_v06")
    parser.add_argument("--model-dir", default="models_foundation_v06")
    parser.add_argument("--stage", choices=["all", "plan", "embed", "train"], default="all")
    parser.add_argument("--max-shards", type=int, default=0, help="Process at most N unfinished shards in this session; 0 means all")
    parser.add_argument("--force-plan", action="store_true")
    parser.add_argument("--allow-partial-train", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    profile = json.loads(config_path.read_text(encoding="utf-8"))
    work = Path(args.work_dir)
    if not work.is_absolute():
        work = ROOT / work
    model_dir = Path(args.model_dir)
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    work.mkdir(parents=True, exist_ok=True)
    plan = work / "training_plan.parquet"
    shards_dir = work / "manifest_shards"
    embedded_root = work / "embedding_shards"

    if args.stage in {"all", "plan"}:
        if args.force_plan or not plan.exists():
            run([
                sys.executable, "scripts/plan_foundation_corpus.py",
                "--input", args.master_manifest,
                "--config", str(config_path),
                "--out", str(plan),
                "--report", str(work / "training_plan_report.json"),
            ])
        if args.force_plan or not (shards_dir / "shards.json").exists():
            run([
                sys.executable, "scripts/make_embedding_shards.py",
                "--input", str(plan),
                "--out-dir", str(shards_dir),
                "--shard-size", str(profile.get("shard_size", 2_000)),
                "--seed", str(profile.get("seed", 42)),
            ])
        run([
            sys.executable, "scripts/corpus_report.py",
            "--input", str(plan),
            "--out-json", str(work / "corpus_report.json"),
            "--out-md", str(work / "corpus_report.md"),
        ])
        if args.stage == "plan":
            return

    if args.stage in {"all", "embed"}:
        if not (shards_dir / "shards.json").exists():
            raise SystemExit("run --stage plan first")
        embedding = profile.get("embedding", {})
        processed = 0
        for manifest in sorted(shards_dir.glob("shard_*.parquet")):
            out = embedded_root / manifest.stem
            if (out / "complete.json").exists():
                continue
            if args.max_shards and processed >= args.max_shards:
                break
            command = [
                sys.executable, "scripts/process_embedding_shard.py",
                "--manifest", str(manifest),
                "--out-dir", str(out),
                "--model", str(embedding.get("model", "facebook/dinov2-base")),
                "--image-size", str(embedding.get("image_size", 518)),
                "--tile-grid", str(embedding.get("tile_grid", 2)),
                "--batch-size", str(embedding.get("batch_size", 2)),
            ]
            if not embedding.get("include_whole", True):
                command.append("--no-whole")
            run(command)
            processed += 1
        index = json.loads((shards_dir / "shards.json").read_text(encoding="utf-8"))
        completed = len(list(embedded_root.glob("shard_*/complete.json")))
        print(f"completed embedding shards: {completed}/{index['shard_count']}")
        if args.stage == "embed":
            return

    if args.stage in {"all", "train"}:
        if not (shards_dir / "shards.json").exists():
            raise SystemExit("run --stage plan first")
        expected = int(json.loads((shards_dir / "shards.json").read_text(encoding="utf-8"))["shard_count"])
        completed = len(list(embedded_root.glob("shard_*/complete.json")))
        if completed < expected and not args.allow_partial_train:
            raise SystemExit(f"only {completed}/{expected} embedding shards are complete; resume embedding first")
        run([
            sys.executable, "scripts/merge_embedding_shards.py",
            "--shard-root", str(embedded_root),
            "--out-dir", str(model_dir),
        ])
        training = profile.get("training", {})
        run([
            sys.executable, "scripts/train_hierarchical.py",
            "--model-dir", str(model_dir),
            "--min-family", str(training.get("min_family", 50)),
            "--min-genus", str(training.get("min_genus", 25)),
            "--min-species", str(training.get("min_species", 12)),
            "--species-label-quality", str(training.get("species_label_quality", "A,B")),
        ])
        run([sys.executable, "scripts/build_retrieval_index.py", "--model-dir", str(model_dir)])
        print(f"foundation model ready -> {model_dir}")


if __name__ == "__main__":
    main()
