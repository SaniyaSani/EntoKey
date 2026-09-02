# Changelog

## 0.6.0 — Selective BIOSCAN Diptera 30k

- Added a deterministic two-pass metadata selector for exactly 30,000 taxonomically balanced Diptera records.
- Preserved official BIOSCAN train/pretrain/validation/test/unseen partitions.
- Added HTTP Range extraction of selected JPEG members without downloading complete BIOSCAN image archives.
- Added JPEG validation, atomic writes, checkpoints, reports, and safe stop/resume behavior.
- Changed the legacy BIOSCAN downloader to metadata-only by default; full archives now require `--full-images`.
- Added a one-command BIOSCAN 30k runner, official archive configuration, tests, Russian guide, and dedicated Colab notebook.

## 0.5.0 — Foundation Corpus 100k

- Connected iNaturalist, BIOSCAN-5M, GBIF and DiSSCo ingestion to one strict workflow.
- Added a configurable 100,000-image source-balanced profile.
- Added an uncapped full-corpus profile that streams every eligible record.
- Added a two-pass streaming sampler for million-row manifests.
- Added deterministic specimen-group-safe manifest shards.
- Added URL-streamed DINOv2-base embedding workers with retry and completion markers.
- Added disk-backed merging of completed embedding shards.
- Added source/licence/label/taxonomy corpus audits.
- Added a public DiSSCo paginated search + full Digital Media export client.
- Added setup and training Colab notebooks backed by Google Drive.
- Kept curated A/B-only species heads and explicit open-set gates.

## 0.4.0 — MicroDiptera

- Added a bounded, family-balanced iNaturalist MicroDiptera pilot builder.
- Added a reviewed target configuration covering 18 small-fly families.
- Added 518 px whole-image plus tile embeddings for fine morphological detail.
- Added specimen-level fusion of dorsal/lateral/head/wing/terminalia views.
- Added filename-based diagnostic view detection for verified local specimens.
- Added conditional family → genus → species classifiers.
- Added class-centroid open-set rejection gates.
- Restricted species heads to curated A/B labels by default.
- Added a dedicated MicroDiptera Colab notebook and fixed the v0.3 quick trainer cell.

## 0.3.0 — One-Command Training Kit

- Fixed iNaturalist bulk ingestion for the real four-table Open Data schema.
- Added safe official iNaturalist metadata download/extraction.
- Added bounded BIOSCAN-5M Diptera image + DNA export through `bioscan-dataset`.
- Added GBIF request, status, download and safe extraction lifecycle.
- Preserved official BIOSCAN validation/test/unseen splits during corpus assembly.
- Added JSON-configured four-source corpus orchestrator.
- Added source-balanced multi-domain classifier training and per-source metrics.
- Added a Colab notebook and Russian end-to-end runbook.

## 0.2.0 — Diptera Foundation Corpus

- Added streaming iNaturalist bulk ingestion.
- Added BIOSCAN-5M Diptera + DNA/BIN ingestion.
- Added disk-backed GBIF occurrence/multimedia ingestion and request generator.
- Added DiSSCo openDS JSON/JSONL media ingestion.
- Added canonical master manifest schema and Parquet/CSV writers.
- Added license normalization and supervised-eligibility flags.
- Added taxonomy harmonization with reviewed synonym tables.
- Added disk-backed cross-source deduplication.
- Added deterministic specimen/duplicate-group splits.
- Added source-balanced pilot sampling and licensed image caching.
- Added corpus-only dependencies and automated tests.
