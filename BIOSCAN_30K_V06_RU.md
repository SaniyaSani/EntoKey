> **LEGACY / reference:** этот документ сохранён для воспроизводимости старого pipeline. Для текущей архитектуры используй `README_RU.md` и `WHOLE_FLY_PIPELINE_RU.md`.

# TaxaLens v0.6 — правильный BIOSCAN Diptera 30k

Эта версия готовит **30 000 лицензированных изображений Diptera из BIOSCAN-5M** до начала обучения.

Главное изменение: полный многогигабайтный корпус изображений BIOSCAN скачивать не нужно. Workflow один раз получает официальные метаданные, делает по ним два потоковых прохода и выбирает ровно 30 000 записей. После этого из официальных ZIP-архивов по HTTP Range загружаются только выбранные JPEG.

## Что именно выбирается

| Официальный BIOSCAN split | Количество |
| --- | ---: |
| pretrain | 12 000 |
| train | 12 000 |
| val | 1 500 |
| test | 1 500 |
| key_unseen | 750 |
| val_unseen | 750 |
| test_unseen | 750 |
| other_heldout | 750 |
| **Всего** | **30 000** |

Внутри каждого split выборка балансируется по самому глубокому надёжному рангу: species → genus → family. Placeholder-определения вроде `sp.`, `cf.`, `aff.` и `BOLD:` не считаются достоверными species labels. Один таксон по умолчанию не может занять больше 500 изображений.

Выбор детерминированный (`seed=42`): повтор на тех же метаданных создаёт тот же список specimen ID. BIOSCAN official unseen splits сохраняются и позднее могут использоваться для open-set проверки.

## Самый простой запуск в Colab

Открой:

`notebooks/BIOSCAN_30K_SELECTIVE_v06_Colab.ipynb`

И выполняй ячейки сверху вниз. Папка с изображениями, selection, checkpoint и manifest сохраняется на Google Drive, поэтому закрытие Colab не уничтожает прогресс.

## Одна команда в Terminal / Codespace / Mac

```bash
python -m pip install -r requirements-foundation.txt
python scripts/run_bioscan_30k.py --root ~/TaxaLensData/bioscan
```

Финальный успешный вывод:

```text
BIOSCAN 30k READY: .../bioscan_diptera_30k_manifest.parquet
```

Повтор той же команды:

- повторно проверит metadata checksum;
- сохранит уже созданную выборку;
- проверит существующие JPEG;
- пропустит целые файлы;
- продолжит недостающие;
- заново соберёт нормализованный manifest.

## Сначала проверить выборку, не скачивая JPEG

```bash
python scripts/run_bioscan_30k.py \
  --root ~/TaxaLensData/bioscan \
  --selection-only
```

Проверь:

- `diptera_30k_selection_report.json` — количество, splits и taxonomic coverage;
- `diptera_30k_selection.csv` — точные specimen ID и ZIP member path.

Затем убери `--selection-only` и повтори команду для изображений.

## Если Colab/прокси не принимает suffix range

Обычно ничего менять не нужно. Если download report показывает ошибку HTTP suffix range, повтори:

```bash
python scripts/run_bioscan_30k.py \
  --root ~/TaxaLensData/bioscan \
  --no-suffix-range
```

Скрипт использует HEAD и абсолютные ranges, но по-прежнему не скачивает полный ZIP.

## Что появится на диске

```text
bioscan/
  bioscan5m/metadata/...                         official metadata
  diptera_30k_selection.csv                     неизменяемый список 30k
  diptera_30k_selection_report.json             контроль выборки
  diptera_30k_progress.json                     checkpoint загрузки
  diptera_30k_download_report.json               контроль байтов/ошибок
  diptera_30k_images/<processid>.jpg             только выбранные JPEG
  diptera_30k_downloaded.csv                     только успешно загруженные
  bioscan_diptera_30k_manifest.parquet           готово для master corpus
```

## Научные и лицензионные ограничения

- Автоматический слой v0.6 использует официальные `cropped_256` archives: это разумный первый foundation pass, но 256 px не создают микроморфологические детали, которых нет в исходном кадре.
- Для криптических micro-Diptera следующим слоем нужны full-resolution museum/microscope images, diagnostic views и expert/DNA verification.
- Метаданные и изображения BIOSCAN-5M сохраняют provenance. В manifest записаны `CC BY 3.0`, `CBG Photography Group`, `CBG Robotic Imager` и `Centre for Biodiversity Genomics`.
- Не запускай `download_bioscan.py --full-images`, если сознательно не хочешь полный пакет.
- Не удаляй `diptera_30k_selection.csv` и progress JSON между Colab-сессиями.

Официальные источники: [BIOSCAN-5M](https://github.com/bioscan-ml/BIOSCAN-5M), [официальный Python loader](https://github.com/bioscan-ml/dataset), [RemoteZip](https://github.com/gtsystem/python-remotezip).
