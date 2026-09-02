# EntoKey Foundation Model v0.5

> **Обновление v0.6:** BIOSCAN больше не требует полный image package. До запуска этого workflow сначала выполни [BIOSCAN_30K_V06_RU.md](BIOSCAN_30K_V06_RU.md). Новый selective downloader получает только выбранные 30 000 JPEG и сохраняет готовый `bioscan_diptera_30k_manifest.parquet`.

v0.5 соединяет ранее раздельные части проекта в один исследовательский workflow:

1. официальный iNaturalist Open Data;
2. BIOSCAN-5M images + DNA barcodes/BIN;
3. GBIF `PRESERVED_SPECIMEN + StillImage` download;
4. DiSSCo openDS Digital Specimens + Digital Media Objects;
5. taxonomy/license harmonization и cross-source deduplication;
6. source/taxon-balanced training plan;
7. resumable DINOv2-base embedding shards;
8. conditional family → genus → species heads + open-set gates;
9. nearest verified specimen retrieval.

## Что изменилось относительно 720-image pilot

`720` было только проверкой механики. Новый профиль `foundation-100k-v0.6` по умолчанию планирует:

| Источник | Изображений |
| --- | ---: |
| iNaturalist | 30 000 |
| BIOSCAN-5M | 30 000 |
| GBIF | 25 000 |
| DiSSCo | 15 000 |
| **Итого** | **100 000** |

Это первый research-scale pass, а не потолок. В `configs/foundation_corpus_v05.json` можно поставить 250k, 500k или полный доступный корпус после проверки storage/GPU budget. Sampler иерархический: A/B species балансируются по species, остальные записи — по genus или family, поэтому огромный common taxon не съедает весь источник.

Для прохода **без sample cap** уже есть `configs/foundation_corpus_full_v05.json`. Значение `total_images: 0` означает: включить каждый eligible record из всех четырёх источников. Этот профиль пишет план потоково и не держит весь многомиллионный manifest в RAM; embedding shards рассчитаны на облачный worker pool.

## Нужно ли скачивать все JPEG сразу

Нет. Сначала сохраняются только metadata/manifests. Затем training plan разбивается примерно на 50 шардов по 2 000 изображений. Для URL-based sources worker:

1. получает одну картинку;
2. декодирует её в памяти;
3. строит whole-image + four-tile representation;
4. получает DINOv2 embedding;
5. отбрасывает JPEG;
6. сохраняет компактный vector и provenance.

BIOSCAN v0.6 selection и отдельные JPEG обычно лежат в Drive/object storage. Полные image packages для 30k прохода больше не нужны. Готовые embedding shards сохраняются в Drive, поэтому обрыв Colab не уничтожает уже обработанные части.

## Два notebook-а

### 1. Источники и master manifest

Открой:

`notebooks/Foundation_Corpus_v05_SETUP_Colab.ipynb`

Он отдельно готовит каждый официальный источник. GBIF download асинхронный и требует бесплатный GBIF account. BIOSCAN сначала готовится отдельным v0.6 selective notebook. Финальная ячейка не создаст master manifest, пока отсутствует хотя бы один из четырёх источников.

### 2. DINOv2 и обучение

Открой:

`notebooks/Foundation_Corpus_v05_TRAIN_Colab.ipynb`

Он строит 100k plan, проверяет source coverage, создаёт group-safe shards и возобновляет DINOv2-base embeddings. Для T4 разумно обрабатывать 1–2 шарда за сессию; на A100/L4 число можно увеличить.

## Одна команда после готового master manifest

```bash
python scripts/run_foundation_v06.py \
  --master-manifest /path/to/master_manifest.parquet \
  --work-dir /persistent/foundation_v06 \
  --model-dir /persistent/models_foundation_v06 \
  --stage all
```

Ограничить одну облачную сессию двумя ещё не обработанными шардами:

```bash
python scripts/run_foundation_v06.py \
  --master-manifest /path/to/master_manifest.parquet \
  --work-dir /persistent/foundation_v06 \
  --model-dir /persistent/models_foundation_v06 \
  --stage embed \
  --max-shards 2
```

Повтор той же команды продолжит со следующего незавершённого шарда.

## Почему не обучаем species на всём подряд

- BIOSCAN/DNA-backed и проверенные музейные labels получают A/B quality.
- iNaturalist Research Grade полезен для representation, family и genus, но для криптических видов не объявляется автоматически species truth.
- `key_unseen`, `val_unseen`, `test_unseen` BIOSCAN сохраняются как open-world material.
- несколько views одного specimen и cross-source duplicates никогда не расходятся между train/val/test.

Для настоящих cryptic species всё равно потребуются diagnostic views, genitalia/chaetotaxy/wing characters и иногда DNA. Модель должна уметь сказать «не знаю», а не выдавать красивую ложную уверенность.

## Масштабирование после 100k

Меняется только `configs/foundation_corpus_v05.json`:

- `total_images` — общий бюджет;
- `source_targets` — квоты четырёх доменов;
- `shard_size` — размер возобновляемой работы;
- `embedding.model` — backbone;
- `training.*` — минимальная поддержка heads.

При 500k+ embeddings лучше запускать на university/cloud object storage и GPU worker pool. Кодовая база, manifests, reports и configs остаются в GitHub; JPEG, vectors и checkpoints — вне GitHub.
