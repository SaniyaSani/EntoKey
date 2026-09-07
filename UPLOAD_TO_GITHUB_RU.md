# Как безопасно обновить GitHub до v0.8

## Не загружай ZIP как проект

ZIP нужен только как способ передать тебе папку проекта. В GitHub должны попасть **распакованные source files**, чтобы Git видел diff и историю изменений.

Raw datasets, изображения, embeddings и model weights в repository не коммитим. `.gitignore` v0.8 уже исключает `data/raw/`, `data/corpus_v08/`, `data/wholefly_v08/`, `models_wholefly_v08/`, Parquet и model weight files.

## Самый безопасный вариант: отдельная branch

В твоём существующем локальном TaxaLens repository:

```bash
git status
git checkout -b whole-image-v08
```

Распакуй `TaxaLens_Foundation_v0.8_WholeImage_Default.zip` **рядом**, не поверх repository вслепую. Затем скопируй содержимое папки `TaxaLens_v0.8/` в корень существующего repo.

После копирования:

```bash
git status
git diff --stat
```

Проверь, что в staged candidates **нет** BIOSCAN/iNat/GBIF/DiSSCo images, `.parquet`, embeddings или model weights.

Затем:

```bash
git add .
git status
git commit -m "Make whole-image DINOv3 the default baseline"
git push -u origin whole-image-v08
```

На GitHub создай Pull Request `whole-image-v08 -> main`. Пока PR не merged, текущий `main` не ломается.

## Главные новые v0.8 files

```text
configs/wholefly_foundation_v08.json
configs/sources_wholefly_v08.example.json
scripts/run_wholefly_v08.py
scripts/source_status_v08.py
notebooks/WholeFly_Foundation_v08_Colab.ipynb
PROJECT_STATUS_v08.json
```

`tile_grid` в default config равен `1`: baseline использует одно полное изображение, а не 2x2 tiles.
