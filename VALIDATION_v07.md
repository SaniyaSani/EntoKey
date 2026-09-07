# TaxaLens v0.7 validation snapshot

Validation run: 2026-09-04

## Code checks

- Python `compileall`: passed for `src/`, `scripts/`, and `app/`.
- Whole-fly/corpus/ingestor test group: **15 passed**.
- Training/foundation/microdiptera/BIOSCAN compatibility test group: **17 passed**.
- Total verified in the two test groups: **32 passed**.

## Corpus readiness at packaging time

The code is ready, but large external inputs are intentionally not bundled into the repository archive.
At packaging time the local paths for iNaturalist, GBIF, DiSSCo and the BIOSCAN normalized 30k manifest were not present in this working copy.
Use `scripts/source_status_v07.py` after downloads are placed in Drive/local storage.

## Architecture check

- Mandatory anatomy segmentation: **disabled**.
- Default backbone: `facebook/dinov3-vits16-pretrain-lvd1689m`.
- Whole-image context plus a 2×2 tile grid is the default embedding strategy.
- Hierarchy: family → genus → species.
- Open-set rejection and nearest-neighbour retrieval remain in the main path.
- Wing/head/anatomy modules are optional and should only be added after error analysis shows a concrete need.
