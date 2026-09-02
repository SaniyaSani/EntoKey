# Diptera Foundation Corpus v0.3

Эта версия превращает Workbench из маленького iNaturalist pilot в **воспроизводимый ingestion pipeline** для четырёх источников:

- iNaturalist field photographs;
- BIOSCAN-5M specimens + DNA barcodes/BIN;
- GBIF preserved specimens + multimedia;
- DiSSCo openDS digital specimens + media objects.

Код готовит метаданные и изображения к обучению. Сам архив **не содержит многомиллионные исходные datasets и не заявляет, что глобальная модель уже обучена**: получение больших выгрузок, storage и GPU запускаются отдельно владельцем проекта.

## 1. Лёгкое окружение только для corpus pipeline

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-corpus.txt
```

Полный `requirements.txt` нужен позже для DINOv2, classifiers и API.

## 2. Источники

### iNaturalist

Для полного корпуса используй официальный bulk dataset, а не `build_inat_pilot.py`. iNaturalist прямо указывает, что API предназначен для приложений, не для scraping, и перечисляет weekly GBIF DwC-A и monthly Licensed Observation Images dataset:

- https://www.inaturalist.org/pages/developers
- https://github.com/inaturalist/inaturalist-open-data

Скачать и безопасно извлечь официальный monthly metadata bundle:

```bash
python scripts/download_inat_metadata.py --out-dir data/raw/inaturalist
```

Затем обработать настоящие четыре official tables:

```bash
python scripts/ingest_inat.py \
  --observations data/raw/inaturalist/observations.csv.gz \
  --photos data/raw/inaturalist/photos.csv.gz \
  --taxa data/raw/inaturalist/taxa.csv.gz \
  --observers data/raw/inaturalist/observers.csv.gz \
  --out data/corpus/inat_raw.parquet
```

Official files имеют TSV-разделитель несмотря на suffix `.csv.gz`. Коннектор строит
полную taxonomic lineage из `taxa`, оставляет Diptera descendants и соединяет photos
через observation UUID. Старые flattened DwC-A exports тоже поддерживаются без
`--taxa`; `--assume-diptera` допустим только для уже отфильтрованной выгрузки.

### BIOSCAN-5M

Официальный dataset публикует metadata CSV/JSON-LD, image packages и Python dataset package. В metadata есть `processid`, DNA barcode, BIN, taxonomy, geography и official split:

- https://github.com/bioscan-ml/BIOSCAN-5M
- https://zenodo.org/records/11973457

```bash
python scripts/ingest_bioscan.py \
  --metadata /data/bioscan/BIOSCAN_5M_Insect_Dataset_metadata.csv \
  --image-root /data/bioscan/cropped_256 \
  --out data/corpus/bioscan_raw.parquet
```

Скрипт оставляет только `order=Diptera`, сохраняет `dna_barcode`, `dna_bin` и `source_split`, а placeholder species не превращает в фальшивые species labels.

### GBIF preserved specimens

Сначала генерируем воспроизводимый download request:

```bash
python scripts/gbif_download.py request
```

Он создаст `data/requests/gbif_preserved_diptera.json`. Его можно загрузить через интерфейс GBIF или отправить программно после задания переменных окружения:

```bash
export GBIF_USER="your_username"
export GBIF_PASSWORD="your_password"
export GBIF_EMAIL="your_email@example.org"
python scripts/gbif_download.py request --submit
```

GBIF download API создаёт асинхронную выгрузку и требует зарегистрированный аккаунт. Проверить и получить её можно командами `gbif_download.py status KEY` и `gbif_download.py fetch KEY`. Официальная документация: https://techdocs.gbif.org/en/data-use/api-downloads

После готовности DWCA распакуй его и ingest-ируй occurrence + multimedia:

```bash
python scripts/ingest_gbif.py \
  --occurrence /data/gbif/occurrence.txt \
  --multimedia /data/gbif/multimedia.txt \
  --out data/corpus/gbif_raw.parquet
```

### DiSSCo

Коннектор принимает openDS JSON/JSONL или flattened tabular export. Он намеренно не привязан к одному experimental search endpoint: openDS — основной межсистемный контракт.

- https://terms.dissco.tech/
- https://dissco.tech/documentation/

```bash
python scripts/ingest_dissco.py \
  --input /data/dissco/digital_specimens.jsonl \
  --out data/corpus/dissco_raw.parquet
```

Вложенные media objects разворачиваются в отдельные image rows, но сохраняют общий `specimen_group_id`.

## 3. Harmonization → merge → deduplication → split

Для каждого source можно применить проверенную таблицу синонимов:

```bash
python scripts/harmonize_taxonomy.py \
  --input data/corpus/inat_raw.parquet \
  --synonyms data/taxonomy/reviewed_synonyms.csv \
  --out data/corpus/inat_harmonized.parquet
```

Минимальные columns synonym table:

```text
original_name,accepted_name,accepted_genus,accepted_family,accepted_taxon_id
```

Собираем источники в один manifest:

```bash
python scripts/build_master_manifest.py \
  data/corpus/inat_harmonized.parquet \
  data/corpus/bioscan_harmonized.parquet \
  data/corpus/gbif_harmonized.parquet \
  data/corpus/dissco_harmonized.parquet \
  --out data/corpus/combined.parquet
```

Удаляем cross-source duplicates. Операция disk-backed и не держит весь manifest в RAM:

```bash
python scripts/deduplicate_records.py \
  --input data/corpus/combined.parquet \
  --out data/corpus/deduplicated.parquet
```

После deduplication повторно назначаем deterministic group splits, чтобы весь specimen/observation/duplicate group оставался только в одном split:

```bash
python scripts/build_master_manifest.py \
  data/corpus/deduplicated.parquet \
  --out data/corpus/master_manifest.parquet
```

## 4. Pilot перед миллионами изображений

```bash
python scripts/sample_training_subset.py \
  --input data/corpus/master_manifest.parquet \
  --rank species \
  --min-per-taxon 8 \
  --max-per-taxon 250 \
  --max-per-source-taxon 150 \
  --out data/corpus/pilot_manifest.csv
```

Sampler сначала ограничивает каждый source внутри taxon, поэтому один визуальный домен не съедает весь pilot.

Скачать только отобранные licensed images:

```bash
python scripts/download_images.py \
  --manifest data/corpus/pilot_manifest.csv \
  --max-images 10000 \
  --out data/corpus/pilot_downloaded.parquet
```

После этого уже работает существующий ML pipeline:

```bash
python scripts/embed_dataset.py --manifest data/corpus/pilot_downloaded.parquet
python scripts/train_classifiers.py --min-images-per-class 8
python scripts/build_retrieval_index.py
```

## 5. Master manifest

Каждая строка соответствует одному изображению. Основные группы полей:

| Группа | Примеры |
| --- | --- |
| provenance | `record_id`, `source`, `source_record_id`, `source_image_id`, `source_url` |
| image | `image_url`, `local_path`, `image_sha256`, `image_license`, `attribution` |
| taxonomy | `order`, `family`, `subfamily`, `tribe`, `genus`, `species`, `accepted_scientific_name` |
| confidence | `identification_level`, `label_quality`, `identified_by`, `eligible_supervised` |
| specimen | `basis_of_record`, `specimen_group_id`, `duplicate_group_id` |
| context | `country`, `latitude`, `longitude`, `event_date`, `sex`, `life_stage` |
| molecular | `dna_barcode`, `dna_bin` |
| evaluation | `source_split`, `split_group`, `split` |

`label_quality` convention:

- `A`: strong DNA-backed or project-verified label;
- `B`: curated specimen identification;
- `C`: iNaturalist Research Grade;
- `D`: useful family/genus label, but not species truth;
- `E`: excluded/uncertain.

Это не утверждение, что каждый BIOSCAN barcode автоматически гарантирует правильное species name. Placeholder/open-world taxa остаются lower-rank training material.

## 6. Что хранить в GitHub, а что нет

В GitHub:

- код;
- schema/configs;
- небольшие manifests и fixtures;
- training reports;
- checksums/model cards.

Не в GitHub:

- миллионы JPEG;
- полные Parquet/DWCA archives;
- DINO embeddings;
- большие checkpoints/indexes.

Для них нужен object storage или university/NAS storage. Перед глобальным GPU training обязательно прогнать pilot end-to-end и проверить domain-balanced metrics отдельно для field photos и pinned specimens.
