# Changelog

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
