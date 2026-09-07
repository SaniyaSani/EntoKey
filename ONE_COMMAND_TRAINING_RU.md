> **LEGACY / reference:** этот документ сохранён для воспроизводимости старого pipeline. Для текущей архитектуры используй `README_RU.md` и `WHOLE_FLY_PIPELINE_RU.md`.

# Как обучить Workbench на iNaturalist + BIOSCAN-5M + GBIF + DiSSCo

## Что означает «обучить на четырёх источниках»

Мы не смешиваем четыре архива в безымянную папку. Сначала каждый источник
превращается в одну schema, затем удаляются дубликаты, сохраняются specimen-level
splits, скачиваются только разрешённые изображения, считаются DINOv2 embeddings и
обучаются family/genus/species heads.

Полное мировое обучение потребует object storage и GPU. Начинай с bounded pilot:
50 000 iNaturalist observations, до 5 000 BIOSCAN Diptera specimens и ограниченной
выборки GBIF/DiSSCo. Когда pipeline прошёл end-to-end, увеличивай лимиты.

## 1. Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -r requirements-corpus.txt
```

Для прямого BIOSCAN export:

```bash
pip install -r requirements-downloaders.txt
```

## 2. iNaturalist Open Data

Официальный monthly bundle очень большой. Команда скачивает metadata, безопасно
извлекает четыре нужные таблицы и не скачивает сотни миллионов фотографий:

```bash
python scripts/download_inat_metadata.py --out-dir data/raw/inaturalist
```

В `configs/pilot.json` включи `sources.inat.enabled` и оставь
`max_observations: 50000`. Адаптер:

- читает настоящие TSV-in-GZIP таблицы;
- строит ancestry из `taxa.csv.gz`;
- оставляет taxon 47822 (Diptera) и его потомков;
- по умолчанию оставляет research grade;
- строит официальный S3 URL каждого photo;
- фильтрует CC0 / CC-BY / CC-BY-SA.

`max_observations` — технический cap, а не статистически стратифицированная
выборка. Финальная балансировка делается после объединения.

## 3. BIOSCAN-5M

Pilot export из официального dataset package:

```bash
python scripts/export_bioscan.py \
  --root data/raw/bioscan \
  --split train \
  --max-records 5000 \
  --download
```

Скрипт оставляет Diptera, сохраняет cropped specimen images и плоскую metadata
таблицу с DNA barcode/BIN. Затем включи `sources.bioscan.enabled`.

Для научной оценки экспортируй также `val`, `test` и unseen splits отдельными
запусками и объедини metadata. Сборщик защищает эти BIOSCAN splits от попадания
в train.

## 4. GBIF preserved specimens

Создай GBIF account и задай credentials только через environment variables:

```bash
export GBIF_USER="..."
export GBIF_PASSWORD="..."
export GBIF_EMAIL="..."
python scripts/gbif_download.py request --submit
```

Команда вернёт download key. Проверка и получение:

```bash
python scripts/gbif_download.py status YOUR_DOWNLOAD_KEY
python scripts/gbif_download.py fetch YOUR_DOWNLOAD_KEY
```

После extraction проверь пути `occurrence.txt` и `multimedia.txt`, затем включи
`sources.gbif.enabled`. Image license проверяется отдельно от occurrence license.

## 5. DiSSCo

DiSSCo deployments и export routes ещё не дают одного универсального bulk URL,
поэтому toolkit не притворяется, что умеет выкачать весь DiSSCo одной неизвестной
командой. Экспортируй Diptera records/media из используемого DiSSCover/openDS
endpoint в JSON, JSONL, CSV, TSV или Parquet и положи, например, сюда:

```text
data/raw/dissco/diptera_export.jsonl
```

После этого включи `sources.dissco.enabled`. Адаптер раскрывает nested openDS media
objects в отдельные image rows и применяет тот же license filter.

## 6. Одна команда сборки

Открой `configs/pilot.json`, включи только реально подготовленные источники и
проверь пути. Сначала безопасная репетиция:

```bash
python scripts/prepare_corpus.py --config configs/pilot.json --dry-run
```

Потом выполнение:

```bash
python scripts/prepare_corpus.py --config configs/pilot.json
```

Результат:

```text
data/corpus/pilot_manifest.csv
```

## 7. Изображения, embeddings и обучение

BIOSCAN images уже локальные. Для разрешённых remote media:

```bash
python scripts/download_images.py \
  --manifest data/corpus/pilot_manifest.csv \
  --out data/corpus/pilot_downloaded.csv \
  --image-root data/images/pilot
```

Дальше:

```bash
python scripts/embed_dataset.py \
  --manifest data/corpus/pilot_downloaded.csv \
  --out-dir models

python scripts/train_multidomain.py \
  --model-dir models \
  --min-images-per-class 8

python scripts/build_retrieval_index.py --model-dir models
```

Multi-domain trainer обучается только на train, балансирует влияние taxa и
источников и сообщает accuracy отдельно для iNaturalist, BIOSCAN, GBIF и DiSSCo.
`predict_proba` остаётся model score, а не доказательством taxonomic certainty.

## 8. Правильный порядок масштабирования

1. Family pilot на 10–50 тысячах изображений.
2. Проверка source-specific accuracy и nearest neighbours.
3. Genus pilot с более строгими label filters.
4. Species только для taxa с достаточным числом A/B/C labels.
5. Frozen DINOv2 на полном curated corpus.
6. Selective fine-tuning backbone на сбалансированном subset.

Не начинай с полного fine-tuning на всех изображениях: сначала докажи, что
taxonomy, licenses, joins, splits и deduplication работают корректно.
