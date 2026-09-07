# TaxaLens v0.8 validation snapshot

Validated after switching the default representation to whole-image only.

Checks completed:

- Python compile check for `src/`, `scripts/`, and `app/`.
- `tests/test_wholefly_v08.py`: **5 passed**.
- `run_wholefly_v08.py --help` executes successfully.
- `source_status_v08.py` executes successfully on the example config.
- Default config is explicitly `strategy = whole_image_only`, `tile_grid = 1`, `include_whole = true`.
- Anatomy segmentation and specimen cropping are not required.
- Multi-crop/tiles remain code-supported only as a later explicit ablation.

Note: the full legacy test suite contains older training tests that can be slow; v0.8-specific tests were run separately and passed.
