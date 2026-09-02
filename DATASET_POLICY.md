# Dataset policy

- Prefer images whose licenses permit the intended project use.
- Default pilot filter: CC0, CC BY, CC BY-SA.
- Keep photo attribution and original observation URL in every manifest row.
- Do not remove provenance when merging datasets.
- Do not use the iNaturalist API as a bulk scraper. For large corpora, use iNaturalist's official licensed image dataset or GBIF/DwC-A exports.
- Split by observation/specimen identifier, never by image alone, to reduce leakage from near-duplicate views.
- Maintain a separate `local_verified` source for microscope/pinned specimens.
- Treat community/research-grade labels as useful training labels, not infallible truth; expert-verified vouchers should receive higher trust in future training.
- For cryptic MicroDiptera, supervised species heads use A/B labels by default. Research Grade (C) remains useful for family/genus representation until reviewed.
- Store `view_type` and keep all diagnostic views under one `specimen_group_id`.
- Store media license separately from occurrence metadata license. A reusable occurrence record does not automatically make its image reusable.
- Keep DNA/BIN fields, but do not treat every barcoded placeholder taxon as a verified species name.
- Keep all views from one observation/specimen/duplicate group in one evaluation split.
- Record excluded rows and reasons during auditing; supervised training consumes only `eligible_supervised=true`.
- Re-check source terms before every bulk refresh. The manifest is provenance, not a substitute for the source's current terms.
