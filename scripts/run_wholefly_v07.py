#!/usr/bin/env python3
"""TaxaLens v0.7: plan → DINOv3 whole-fly embeddings → hierarchical heads → retrieval."""
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


def resolve(path: str | Path) -> Path:
    value = Path(path).expanduser()
    return value if value.is_absolute() else ROOT / value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-manifest", required=True)
    parser.add_argument("--config", default="configs/wholefly_foundation_v07.json")
    parser.add_argument("--work-dir", default="data/wholefly_v07")
    parser.add_argument("--model-dir", default="models_wholefly_v07")
    parser.add_argument("--stage", choices=["all", "plan", "embed", "train"], default="all")
    parser.add_argument("--max-shards", type=int, default=0, help="Process at most N unfinished embedding shards; 0 means all")
    parser.add_argument("--force-plan", action="store_true")
    parser.add_argument("--allow-partial-train", action="store_true")
    args = parser.parse_args()

    config_path = resolve(args.config)
    profile = json.loads(config_path.read_text(encoding="utf-8"))
    embedding = profile.get("embedding", {})
    if embedding.get("segmentation_required") is True:
        raise SystemExit("v0.7 whole-fly profile must not require anatomy segmentation")

    work = resolve(args.work_dir)
    model_dir = resolve(args.model_dir)
    work.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    plan = work / "training_plan.parquet"
    shards_dir = work / "manifest_shards"
    embedded_root = work / "embedding_shards"

    if args.stage in {"all", "plan"}:
        if args.force_plan or not plan.exists():
            run([
                sys.executable, "scripts/plan_foundation_corpus.py",
                "--input", str(resolve(args.master_manifest)),
                "--config", str(config_path),
                "--out", str(plan),
                "--report", str(work / "training_plan_report.json"),
            ])
        if args.force_plan or not (shards_dir / "shards.json").exists():
            run([
                sys.executable, "scripts/make_embedding_shards.py",
                "--input", str(plan),
                "--out-dir", str(shards_dir),
                "--shard-size", str(profile.get("shard_size", 2000)),
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
        index_file = shards_dir / "shards.json"
        if not index_file.exists():
            raise SystemExit("run --stage plan first")
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
                "--model", str(embedding.get("model", "facebook/dinov3-vits16-pretrain-lvd1689m")),
                "--image-size", str(embedding.get("image_size", 512)),
                "--tile-grid", str(embedding.get("tile_grid", 2)),
                "--batch-size", str(embedding.get("batch_size", 2)),
            ]
            if not embedding.get("include_whole", True):
                command.append("--no-whole")
            run(command)
            processed += 1
        index = json.loads(index_file.read_text(encoding="utf-8"))
        completed = len(list(embedded_root.glob("shard_*/complete.json")))
        print(f"completed whole-fly embedding shards: {completed}/{index['shard_count']}")
        if args.stage == "embed":
            return

    if args.stage in {"all", "train"}:
        index_file = shards_dir / "shards.json"
        if not index_file.exists():
            raise SystemExit("run --stage plan first")
        expected = int(json.loads(index_file.read_text(encoding="utf-8"))["shard_count"])
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
            "--gate-quantile", str(training.get("gate_quantile", 0.05)),
            "--gate-margin", str(training.get("gate_margin", 0.02)),
        ])
        run([sys.executable, "scripts/build_retrieval_index.py", "--model-dir", str(model_dir)])
        print(f"whole-fly foundation model ready -> {model_dir}")


if __name__ == "__main__":
    main()
