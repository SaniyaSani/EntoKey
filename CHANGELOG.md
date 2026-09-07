
## v0.9.0 — Multi-source PoC + Genus Key Finder

- Added one resumable entry point for BIOSCAN-5M, iNaturalist, GBIF and DiSSCo.
- Fixed the PoC allocation at 30k + 30k + 25k + 15k = 100k images.
- Switched the declared v0.9 baseline to one padded 512×512 DINOv3 ViT-B/16 image.
- Added automatic genus-key discovery from the top genus candidates.
- Added curated/offline references plus optional Crossref and OpenAlex discovery.
- Added a `/keys/search` API endpoint and automatic non-blocking key results in the UI.
- Added source-wise Markdown evaluation output for the Science IT / Overleaf report.
- Kept cached images and embedding shards resumable.

## v0.8.0 — Whole-Image Baseline First

- Changed the **default representation to one complete image -> one DINOv3 embedding**.
- Disabled 2x2 tiles in the default configuration (`tile_grid=1`).
- Kept multi-crop code only as a later ablation; it must be enabled explicitly.
- Kept anatomy segmentation disabled and made specimen cropping non-required.
- Updated Colab, runner, source status, API wording and docs to the v0.8 baseline.
- Preserved aspect ratio with square padding before DINOv3, avoiding destructive center crops.
- Added a validation rule: crop/tiles/specialist modules are kept only if they improve the same held-out split.

## v0.7.0 — Whole-Fly Foundation

- Removed anatomy segmentation from the required training path.
- Switched the default frozen backbone to DINOv3-small (`facebook/dinov3-vits16-pretrain-lvd1689m`).
- Added a heavier DINOv3-Base profile for larger GPUs.
- Whole-image + 2×2 high-resolution tiles are now the default representation strategy.
- Kept hierarchical family → genus → species heads, source balancing, open-set centroid gates and nearest-specimen retrieval.
- Added per-source / source-split evaluation and top confusion pairs to hierarchical reports.
- Added source readiness checker for BIOSCAN + iNaturalist + GBIF + DiSSCo.
- Added a backbone cache/preflight script.
- Added a dedicated v0.7 Colab notebook and explicit error-driven morphology policy.
- Anatomy, head and wing specialist models are now optional modules to be added only after baseline error analysis.

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
