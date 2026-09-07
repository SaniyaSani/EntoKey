# TaxaLens v0.7 — источники данных и DINOv3

Текущий pipeline больше **не требует anatomy segmentation**. Главная задача — собрать лицензируемый, source-balanced корпус Diptera и сначала проверить сильный whole-fly baseline.

## Что входит в foundation corpus

| Источник | Цель v0.7 | Роль |
|---|---:|---|
| BIOSCAN | 30 000 | стандартизированные specimen images, preserved domain |
| iNaturalist | 30 000 | field-photo domain и широкий taxonomic coverage |
| GBIF | 25 000 | музейные/коллекционные preserved specimens |
| DiSSCo | 15 000 | digital specimens и museum-media domain |

Итого: **100 000 изображений** до дедупликации/фильтрации. Если конкретный источник не даёт достаточно качественных лицензируемых Diptera, planner не должен слепо добивать квоту плохими данными: оставляем недобор и фиксируем его в отчёте.

## 1. BIOSCAN

Если selective 30k уже скачивается, ничего менять не надо. После завершения ожидаются:

```text
raw/bioscan/diptera_30k_images/
raw/bioscan/bioscan_diptera_30k_manifest.parquet
```

Проверка:

```bash
python scripts/source_status_v07.py --config configs/sources_wholefly_v07.example.json
```

## 2. iNaturalist — НЕ скрапим API

Для большого корпуса используем официальный iNaturalist Open Data snapshot. Сначала скачиваются только metadata tables, затем `ingest_inat.py` выбирает Diptera и строит image URLs.

```bash
python scripts/download_inat_metadata.py \
  --out-dir /content/drive/MyDrive/TaxaLens/Foundation_v07/raw/inaturalist

python scripts/ingest_inat.py \
  --observations /content/drive/MyDrive/TaxaLens/Foundation_v07/raw/inaturalist/observations.csv.gz \
  --photos /content/drive/MyDrive/TaxaLens/Foundation_v07/raw/inaturalist/photos.csv.gz \
  --taxa /content/drive/MyDrive/TaxaLens/Foundation_v07/raw/inaturalist/taxa.csv.gz \
  --observers /content/drive/MyDrive/TaxaLens/Foundation_v07/raw/inaturalist/observers.csv.gz \
  --out /content/drive/MyDrive/TaxaLens/Foundation_v07/corpus/inat_raw.parquet
```

После нормализации downloader берёт только выбранные planner-ом изображения, а не весь iNaturalist bucket.

## 3. GBIF

Для десятков тысяч specimen records используем asynchronous GBIF occurrence download, а не `/occurrence/search` как массовый downloader.

Сначала создаём воспроизводимый request:

```bash
export GBIF_USER='...'
export GBIF_PASSWORD='...'
export GBIF_EMAIL='...'

python scripts/request_gbif_download.py --submit
```

Когда download готов, распаковываем DwC-A и указываем `occurrence.txt` + `multimedia.txt` в `sources_wholefly_v07.json`.

## 4. DiSSCo

DiSSCo нужен нам именно как **specimen/media domain**. Основной ingestor `ingest_dissco.py` специально не привязан к единственному API endpoint: он принимает openDS JSON/JSONL либо flattened export из DiSSCover. Это более устойчиво, чем делать обучение зависимым от конкретной версии search API.

```bash
python scripts/ingest_dissco.py \
  --input /content/drive/MyDrive/TaxaLens/Foundation_v07/raw/dissco/diptera_export.jsonl \
  --out /content/drive/MyDrive/TaxaLens/Foundation_v07/corpus/dissco_raw.parquet
```

`scripts/download_dissco.py` оставлен как convenience harvester, но перед большим harvest нужно проверить текущую API-схему. Если DiSScover даёт export — export предпочтительнее.

## 5. DINOv3 — это не пятый dataset

DINOv3 — **vision backbone**, который превращает whole-fly image в embedding. В v0.7 default:

```text
facebook/dinov3-vits16-pretrain-lvd1689m
```

Более тяжёлый вариант для хорошего GPU:

```text
facebook/dinov3-vitb16-pretrain-lvd1689m
```

DINOv3 checkpoint на Hugging Face gated: сначала нужно принять условия модели в своём HF account, затем залогиниться в Colab/машине.

```bash
huggingface-cli login
python scripts/cache_backbone.py
```

Если DINOv3 временно недоступен, код сохраняет совместимость с DINOv2 как ablation/fallback, но основной v0.7 experiment — DINOv3.

## 6. Порядок, который я бы использовала сейчас

```text
BIOSCAN download finishes
        │
        ├── iNaturalist metadata → Diptera manifest
        ├── GBIF async download → occurrence + multimedia
        └── DiSSCo export → openDS/JSONL
                    │
                    ▼
          normalize + deduplicate
                    │
                    ▼
            100k training plan
                    │
                    ▼
           DINOv3 embeddings
                    │
                    ▼
      family → genus → species heads
                    │
              ┌─────┴─────┐
              ▼           ▼
          retrieval    open-set
              │
              ▼
     error analysis by family/source
              │
              ▼
 optional wing/head module ONLY where needed
```

## Важный anti-leakage принцип

Несколько фото одного observation/specimen не должны попадать в разные train/val/test splits. Для iNaturalist group key = observation; для museum sources = specimen/catalogue object; BIOSCAN сохраняет официальный split там, где он есть.
