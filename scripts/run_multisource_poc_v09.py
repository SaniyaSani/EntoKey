#!/usr/bin/env python3
"""TaxaLens v0.9: resumable four-source PoC from download through evaluation."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], dry_run: bool = False) -> None:
    print("+", shlex.join(command), flush=True)
    if not dry_run:
        subprocess.run(command, cwd=ROOT, check=True)


def paths(
    data_root: str | Path,
    bioscan_root: str | Path | None = None,
    bioscan_manifest: str | Path | None = None,
) -> dict[str, Path]:
    root = Path(data_root).expanduser().resolve()
    bioscan = Path(bioscan_root).expanduser().resolve() if bioscan_root else root / "bioscan"
    normalized_bioscan = (
        Path(bioscan_manifest).expanduser().resolve()
        if bioscan_manifest
        else bioscan / "bioscan_diptera_30k_manifest.parquet"
    )
    poc = root / "poc_v09"
    return {
        "root": root,
        "bioscan": bioscan,
        "bioscan_manifest": normalized_bioscan,
        "inat": root / "inaturalist",
        "gbif": root / "gbif",
        "dissco": root / "dissco",
        "poc": poc,
        "corpus": poc / "corpus",
        "plan": poc / "training_plan.parquet",
        "cached_plan": poc / "training_plan_cached.parquet",
        "shards": poc / "manifest_shards",
        "embedded": poc / "embedding_shards",
        "models": root / "models_poc_v09",
    }


def source_config(layout: dict[str, Path]) -> dict:
    return {
        "output_dir": str(layout["corpus"]),
        "sources": {
            "inat": {
                "enabled": True,
                "observations": str(layout["inat"] / "observations.csv.gz"),
                "photos": str(layout["inat"] / "photos.csv.gz"),
                "taxa": str(layout["inat"] / "taxa.csv.gz"),
                "observers": str(layout["inat"] / "observers.csv.gz"),
                "quality_grades": "research",
            },
            "bioscan": {"enabled": False},
            "gbif": {
                "enabled": True,
                "occurrence": str(layout["gbif"] / "extracted" / "occurrence.txt"),
                "multimedia": str(layout["gbif"] / "extracted" / "multimedia.txt"),
            },
            "dissco": {"enabled": True, "input": str(layout["dissco"] / "diptera_full.jsonl")},
            "normalized_manifests": [str(layout["bioscan_manifest"])],
        },
        "pilot": {"rank": "family", "max_per_taxon": 5000, "min_per_taxon": 8, "max_per_source_taxon": 5000, "seed": 42},
    }


def write_runtime_config(layout: dict[str, Path]) -> Path:
    destination = layout["poc"] / "sources_v09.runtime.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(source_config(layout), indent=2), encoding="utf-8")
    return destination


def doctor(layout: dict[str, Path]) -> int:
    checks = {
        "BIOSCAN manifest": layout["bioscan_manifest"],
        "iNaturalist observations": layout["inat"] / "observations.csv.gz",
        "iNaturalist photos": layout["inat"] / "photos.csv.gz",
        "GBIF occurrence": layout["gbif"] / "extracted" / "occurrence.txt",
        "GBIF multimedia": layout["gbif"] / "extracted" / "multimedia.txt",
        "DiSSCo export": layout["dissco"] / "diptera_full.jsonl",
        "100k training plan": layout["plan"],
        "cached image plan": layout["cached_plan"],
        "trained classifiers": layout["models"] / "classifiers.joblib",
        "genus key catalog": ROOT / "data" / "key_catalog_v09.json",
        "20-family scope": ROOT / "configs" / "target_diptera_families.json",
    }
    missing = 0
    print(f"{'COMPONENT':<28} STATUS  PATH")
    print("-" * 100)
    for name, path in checks.items():
        ready = path.exists()
        missing += not ready
        print(f"{name:<28} {'ready' if ready else 'missing':<7} {path}")
    print("-" * 100)
    print(f"{len(checks) - missing}/{len(checks)} components ready")
    return missing


def make_shards(layout: dict[str, Path], profile: dict, manifest: Path, dry_run: bool) -> None:
    run([
        sys.executable, "scripts/make_embedding_shards.py", "--input", str(manifest),
        "--out-dir", str(layout["shards"]), "--shard-size", str(profile["shard_size"]),
        "--seed", str(profile["seed"]),
    ], dry_run)


def reuse_existing_bioscan(layout: dict[str, Path], dry_run: bool) -> None:
    """Create the normalized BIOSCAN manifest from local files only."""
    root = layout["bioscan"]
    selection = root / "diptera_30k_selection.csv"
    downloaded = root / "diptera_30k_downloaded.csv"
    images = root / "diptera_30k_images"
    normalized = layout["bioscan_manifest"]
    if normalized.exists():
        print("BIOSCAN already normalized; reusing without download:", normalized)
        return
    if not downloaded.exists():
        if not selection.exists():
            run([
                sys.executable, "scripts/run_bioscan_30k.py", "--root", str(root),
                "--max-records", "30000", "--selection-only", "--skip-metadata-download",
            ], dry_run)
        run([
            sys.executable, "scripts/index_existing_bioscan.py",
            "--selection", str(selection), "--image-dir", str(images),
            "--out-manifest", str(downloaded),
            "--report", str(root / "diptera_30k_existing_report.json"),
            "--allow-partial",
        ], dry_run)
    run([
        sys.executable, "scripts/ingest_bioscan.py", "--metadata", str(downloaded),
        "--out", str(normalized),
    ], dry_run)


def find_bioscan_metadata(root: Path) -> Path:
    preferred = root / "bioscan5m" / "metadata" / "csv" / "BIOSCAN_5M_Insect_Dataset_metadata.csv"
    if preferred.exists():
        return preferred
    candidates = sorted(root.rglob("*metadata*.csv"))
    if not candidates:
        raise SystemExit(
            f"BIOSCAN metadata was not found under {root}; the family top-up will not download metadata automatically"
        )
    return candidates[0]


def topup_bioscan_families(layout: dict[str, Path], profile: dict, dry_run: bool) -> None:
    """Download only missing Muscidae/Tachinidae rows and preserve the existing 30k cache."""
    root = layout["bioscan"]
    selection = root / "diptera_30k_selection.csv"
    images = root / "diptera_30k_images"
    downloaded = root / "diptera_30k_downloaded.csv"
    normalized = layout["bioscan_manifest"]
    topup_selection = root / "diptera_added_families_topup_selection.csv"
    topup_downloaded = root / "diptera_added_families_topup_downloaded.csv"
    if not selection.exists() and not dry_run:
        raise SystemExit(f"existing BIOSCAN selection not found: {selection}")
    metadata = find_bioscan_metadata(root) if not dry_run else root / "bioscan5m" / "metadata" / "csv" / "BIOSCAN_5M_Insect_Dataset_metadata.csv"
    if not downloaded.exists():
        run([
            sys.executable, "scripts/index_existing_bioscan.py",
            "--selection", str(selection), "--image-dir", str(images),
            "--out-manifest", str(downloaded),
            "--report", str(root / "diptera_30k_existing_report.json"),
            "--allow-partial",
        ], dry_run)
    settings = profile.get("bioscan_family_topup", {})
    families = [str(value).strip() for value in settings.get("families", ["Muscidae", "Tachinidae"]) if str(value).strip()]
    minimum = int(settings.get("min_images_per_family", 1500))
    max_per_taxon = int(settings.get("max_per_taxon", 250))
    run([
        sys.executable, "scripts/select_bioscan_family_topup.py",
        "--metadata", str(metadata), "--base-selection", str(selection),
        "--image-dir", str(images), "--families", ",".join(families),
        "--min-per-family", str(minimum), "--max-per-taxon", str(max_per_taxon),
        "--out", str(topup_selection),
        "--report", str(root / "diptera_added_families_topup_selection_report.json"),
    ], dry_run)
    run([
        sys.executable, "scripts/download_bioscan_subset.py",
        "--selection", str(topup_selection), "--image-dir", str(images),
        "--out-manifest", str(topup_downloaded),
        "--report", str(root / "diptera_added_families_topup_download_report.json"),
        "--progress", str(root / "diptera_added_families_topup_progress.json"),
        "--allow-partial",
    ], dry_run)
    run([
        sys.executable, "scripts/merge_bioscan_manifests.py",
        str(downloaded), str(topup_downloaded), "--out", str(downloaded),
    ], dry_run)
    run([
        sys.executable, "scripts/ingest_bioscan.py", "--metadata", str(downloaded),
        "--out", str(normalized),
    ], dry_run)
    print(
        "BIOSCAN family top-up complete: existing images were preserved; "
        f"only missing rows for {', '.join(families)} were requested."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=["doctor", "bioscan-topup", "download", "ingest", "assemble", "plan", "cache", "embed", "train", "evaluate", "keys"])
    parser.add_argument("--data-root", default="~/TaxaLensData")
    parser.add_argument("--bioscan-root", help="Existing BIOSCAN raw folder; may be outside --data-root")
    parser.add_argument(
        "--bioscan-manifest",
        help="Existing normalized BIOSCAN parquet, e.g. Foundation_v06/manifests/bioscan_raw.parquet",
    )
    parser.add_argument(
        "--reuse-existing-bioscan",
        action="store_true",
        help="Never download BIOSCAN; index and normalize only files already on disk",
    )
    parser.add_argument("--config", default="configs/multisource_poc_v09.json")
    parser.add_argument("--submit-gbif-request", action="store_true")
    parser.add_argument("--gbif-download-key")
    parser.add_argument("--max-shards", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--family", default="")
    parser.add_argument("--genera", default="")
    args = parser.parse_args()

    layout = paths(args.data_root, args.bioscan_root, args.bioscan_manifest)
    profile_path = Path(args.config)
    if not profile_path.is_absolute():
        profile_path = ROOT / profile_path
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if sum(profile["source_targets"].values()) != profile["total_images"]:
        raise SystemExit("source targets do not add up to total_images")
    for path in (layout["root"], layout["poc"], layout["models"]):
        path.mkdir(parents=True, exist_ok=True)

    if args.stage == "doctor":
        doctor(layout)
        return

    if args.stage == "bioscan-topup":
        topup_bioscan_families(layout, profile, args.dry_run)
        return

    if args.stage == "download":
        if args.reuse_existing_bioscan:
            reuse_existing_bioscan(layout, args.dry_run)
        elif not layout["bioscan_manifest"].exists():
            run([sys.executable, "scripts/run_bioscan_30k.py", "--root", str(layout["bioscan"]), "--max-records", "30000", "--allow-partial"], args.dry_run)
        if not (layout["inat"] / "observations.csv.gz").exists():
            run([sys.executable, "scripts/download_inat_metadata.py", "--out-dir", str(layout["inat"])], args.dry_run)
        run([sys.executable, "scripts/download_dissco.py", "--out", str(layout["dissco"] / "diptera_full.jsonl"), "--max-records", "15000", "--resume"], args.dry_run)
        if args.gbif_download_key:
            run([sys.executable, "scripts/gbif_download.py", "fetch", args.gbif_download_key, "--out", str(layout["gbif"] / "gbif_download.zip"), "--extract", str(layout["gbif"] / "extracted")], args.dry_run)
        else:
            command = [sys.executable, "scripts/request_gbif_download.py", "--out", str(layout["gbif"] / "request.json")]
            if args.submit_gbif_request:
                command.append("--submit")
            run(command, args.dry_run)
        return

    runtime_config = write_runtime_config(layout)
    if args.stage in {"ingest", "assemble"}:
        run([sys.executable, "scripts/prepare_corpus.py", "--config", str(runtime_config), "--stage", args.stage], args.dry_run)
        return

    if args.stage == "plan":
        master = layout["corpus"] / "master_manifest.parquet"
        if not master.exists() and not args.dry_run:
            raise SystemExit("master manifest missing; run --stage assemble first")
        run([sys.executable, "scripts/plan_foundation_corpus.py", "--input", str(master), "--config", str(profile_path), "--out", str(layout["plan"]), "--report", str(layout["poc"] / "training_plan_report.json")], args.dry_run)
        run([sys.executable, "scripts/corpus_report.py", "--input", str(layout["plan"]), "--out-json", str(layout["poc"] / "corpus_report.json"), "--out-md", str(layout["poc"] / "corpus_report.md")], args.dry_run)
        make_shards(layout, profile, layout["plan"], args.dry_run)
        return

    if args.stage == "cache":
        if not layout["plan"].exists() and not args.dry_run:
            raise SystemExit("training plan missing; run --stage plan first")
        run([sys.executable, "scripts/download_images.py", "--manifest", str(layout["plan"]), "--out", str(layout["cached_plan"]), "--image-root", str(layout["root"] / "images"), "--max-images", "0", "--allow-unbounded"], args.dry_run)
        make_shards(layout, profile, layout["cached_plan"], args.dry_run)
        return

    if args.stage == "embed":
        embedding = profile["embedding"]
        processed = 0
        manifests = sorted(layout["shards"].glob("shard_*.parquet"))
        if not manifests and not args.dry_run:
            raise SystemExit("embedding shards missing; run --stage cache first")
        for manifest in manifests:
            out = layout["embedded"] / manifest.stem
            if (out / "complete.json").exists():
                continue
            if args.max_shards and processed >= args.max_shards:
                break
            run([sys.executable, "scripts/process_embedding_shard.py", "--manifest", str(manifest), "--out-dir", str(out), "--model", embedding["model"], "--image-size", str(embedding["image_size"]), "--tile-grid", "1", "--batch-size", str(embedding["batch_size"])], args.dry_run)
            processed += 1
        return

    if args.stage == "train":
        training = profile["training"]
        run([sys.executable, "scripts/merge_embedding_shards.py", "--shard-root", str(layout["embedded"]), "--out-dir", str(layout["models"])], args.dry_run)
        run([sys.executable, "scripts/train_hierarchical.py", "--model-dir", str(layout["models"]), "--min-family", str(training["min_family"]), "--min-genus", str(training["min_genus"]), "--min-species", str(training["min_species"]), "--species-label-quality", training["species_label_quality"], "--gate-quantile", str(training["gate_quantile"]), "--gate-margin", str(training["gate_margin"])], args.dry_run)
        run([sys.executable, "scripts/build_retrieval_index.py", "--model-dir", str(layout["models"])], args.dry_run)
        return

    if args.stage == "evaluate":
        run([sys.executable, "scripts/render_evaluation_v09.py", "--report", str(layout["models"] / "training_report_hierarchical.json"), "--out", str(layout["models"] / "evaluation_by_source.md")], args.dry_run)
        return

    if args.stage == "keys":
        if not args.family and not args.genera:
            raise SystemExit("--stage keys requires --family and/or --genera")
        command = [sys.executable, "scripts/find_genus_keys.py", "--family", args.family, "--genera", args.genera]
        run(command, args.dry_run)


if __name__ == "__main__":
    main()
