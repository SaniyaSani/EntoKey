# Swiss Diptera ID Workbench 🪰

## Новое в v0.3: One-Command Training Kit

v0.3 превращает корпусный pipeline в запускаемый workflow:

- точный адаптер официальных четырёх таблиц iNaturalist Open Data;
- BIOSCAN exporter через официальный Python package;
- полный GBIF download lifecycle;
- конфиг `configs/pilot.json` и единая команда `prepare_corpus.py`;
- multi-domain обучение с балансировкой источников;
- Colab notebook для быстрого proof-of-training.

Начни здесь: [ONE_COMMAND_TRAINING_RU.md](ONE_COMMAND_TRAINING_RU.md).

## Diptera Foundation Corpus (добавлено в v0.2)

Добавлен рабочий bulk-ingestion pipeline для **iNaturalist + BIOSCAN-5M + GBIF preserved specimens + DiSSCo**:

- единая master schema и Parquet/CSV streaming;
- disk-backed occurrence ↔ multimedia joins;
- license normalization/filtering;
- DNA/BIN и source splits BIOSCAN;
- openDS media expansion для DiSSCo;
- taxonomy harmonization;
- cross-source deduplication;
- deterministic specimen-group splits;
- domain-balanced pilot sampling;
- licensed image cache downloader.

Полная инструкция: [CORPUS_PIPELINE_RU.md](CORPUS_PIPELINE_RU.md).

Важно: v0.2 содержит **pipeline**, а не сами многомиллионные datasets и не притворяется уже обученной global model. Сначала собираются официальные bulk exports и пилот, затем embeddings/training запускаются на подходящем storage/GPU.

Это **не фейковый идентификатор**. Проект намеренно не возвращает mock-ID, если реальные ML-артефакты ещё не обучены.

## Что уже собрано

1. **License-aware iNaturalist pilot dataset builder** для Diptera (`taxon_id=47822`).
2. **DINOv2-small** как frozen visual backbone → 384-dimensional normalized embeddings.
3. Независимые classifiers для **family → genus → species** на frozen embeddings.
4. **Nearest-neighbour specimen search** по cosine similarity (FAISS, с NumPy fallback).
5. Web UI + FastAPI: загрузка фото → AI candidates → похожие specimens → morphology checklist.
6. Консервативное правило: если species score слабый, интерфейс **не делает вид, что species определён**.
7. Manifest хранит источник, observer, photo license, attribution и URL наблюдения.
8. Поддержка твоих собственных microscope/pinned images через `add_local_specimens.py`.

## Почему DINOv2-small

На Mac это намного реалистичнее, чем ViT-L/G: backbone достаточно сильный для первого прототипа, а embedding всего 384 чисел. Потом можно сравнить `dinov2-base`, BioCLIP и специализированные insect encoders.

---

## Быстрый запуск

### 1. Создать environment

```bash
cd swiss-diptera-id-workbench
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

> На Apple Silicon, если `faiss-cpu` не установится, это **не блокер**: retrieval автоматически использует NumPy cosine similarity.

### 2. Скачать маленький реальный pilot dataset

```bash
python scripts/build_inat_pilot.py --place-id 7236 --pages 5 --per-page 100 --download
```

В примере `place-id 7236` ограничивает выборку Швейцарией. Убери `--place-id 7236`, если нужен мировой корпус. По умолчанию берутся только `cc0, cc-by, cc-by-sa`. `CC-BY-NC` специально не включён, чтобы будущий open-source проект не оказался случайно привязан к non-commercial training media.

Для серьёзного корпуса (тысячи/миллионы фото) **не надо скрейпить API**: используй официальный iNaturalist Licensed Observation Images dataset или GBIF/DwC-A export и преобразуй его в такой же manifest.

### 3. Сделать реальные DINOv2 embeddings

```bash
python scripts/embed_dataset.py --manifest data/inat_pilot_manifest.csv
```

Первый запуск скачает pretrained `facebook/dinov2-small`.

### 4. Обучить family/genus/species classifiers

```bash
python scripts/train_classifiers.py --min-images-per-class 8
```

Скрипт сначала оценивает top-1/top-5 на group-based holdout (одна observation не течёт одновременно в train/test), потом переобучает classifier на всех пригодных данных.

### 5. Построить reference-specimen search

```bash
python scripts/build_retrieval_index.py
```

### 6. Запустить workbench

```bash
PYTHONPATH=src uvicorn app.api:app --reload
```

Открыть:

```text
http://127.0.0.1:8000
```

---

# Добавление твоих собственных specimens

Допустим, у тебя есть папка фотографий проверенного `Syrphidae / Eristalis / Eristalis tenax`:

```bash
python scripts/add_local_specimens.py \
  --image-dir /path/to/Eristalis_tenax \
  --family Syrphidae \
  --genus Eristalis \
  --species "Eristalis tenax" \
  --collector "Sanny" \
  --voucher-prefix BIOBLITZ26_ETENAX
```

Объединить iNat + local:

```bash
python scripts/merge_manifests.py \
  data/inat_pilot_manifest.csv \
  data/local_specimens_manifest.csv \
  --out data/training_manifest.csv
```

Потом заново:

```bash
python scripts/embed_dataset.py --manifest data/training_manifest.csv
python scripts/train_classifiers.py
python scripts/build_retrieval_index.py
```

## Очень важно для pinned material

iNaturalist в основном содержит field photos. Твои specimens — pinned/dead/stereo-microscope views. Это **domain shift**. Поэтому следующая настоящая цель — собрать multi-view reference set:

- dorsal habitus
- lateral habitus
- head frontal/lateral
- wing
- antenna/arista
- legs / key diagnostic structures
- genitalia, если это необходимо для taxon

И хранить `specimen_id`, чтобы разные виды одного specimen не попадали одновременно в train и test.

---

# Как выглядит pipeline

```text
photo
  ↓
DINOv2-small
  ↓
384-d normalized embedding
  ├── family classifier
  ├── genus classifier
  ├── species classifier
  └── cosine nearest-neighbour index
           ↓
      similar verified specimens

AI candidate
  ↓
Morphology checklist
  ↓
Key / publication
  ↓
Human-confirmed identification
```

# Следующий scientific upgrade

1. **Hierarchical conditional heads**: genus classifier только внутри predicted family; species только внутри genus.
2. **Open-set rejection**: модель должна уметь сказать «этого taxon нет в training set».
3. **Domain-balanced training**: iNaturalist field photos + museum pinned specimens + microscope views.
4. **Geographic prior**: Switzerland/canton/altitude/phenology как отдельный score, а не как замена morphology.
5. **Multi-view specimen fusion**: несколько фото одного specimen → один combined embedding / prediction.
6. **Active learning**: uncertain specimens складываются в очередь для ручной проверки; после верификации попадают обратно в training set.
7. **Key routing**: family/genus candidate автоматически открывает нужный couplet/page/diagnostic characters.

## Что означает confidence

`predict_proba` в этой версии — **model score**, а не вероятность того, что определение истинно. Для species принят более высокий порог, но окончательное подтверждение должно идти через morphology/key.
