#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-foundation.txt
printf '
TaxaLens v0.8 whole-image baseline ready.

'
printf '1) Check sources:
   python scripts/source_status_v08.py --config configs/sources_wholefly_v08.example.json

'
printf '2) When master manifest exists:
   python scripts/run_wholefly_v08.py --master-manifest data/corpus_v08/master_manifest.parquet --stage plan

'
printf 'Read WHOLE_FLY_PIPELINE_RU.md for the full workflow.
'
