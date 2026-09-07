# BIOSCAN top-up: Muscidae и Tachinidae

Текущее состояние уже готово и не пересобирается:

```text
/content/drive/MyDrive/EntoKey/Foundation_v06/manifests/bioscan_raw.parquet
```

В нём находятся 30 000 BIOSCAN изображений с полным набором official splits:
12 000 pretrain, 12 000 train, 1 500 val, 1 500 test и по 750 в четырёх
held-out/unseen категориях.

## Что делает новый top-up

Он обеспечивает минимум **1 500 Muscidae и 1 500 Tachinidae** в доступном
BIOSCAN pool:

1. считает уже скачанные валидные JPEG этих семейств;
2. сначала использует подходящие строки из существующего 30k selection;
3. при нехватке выбирает дополнительные записи только этих двух семейств из
   уже скачанных BIOSCAN metadata;
4. скачивает только отсутствующие JPEG через selective range downloader;
5. объединяет их с готовым manifest без дубликатов;
6. заново записывает `manifests/bioscan_raw.parquet`.

Исходный `diptera_30k_selection.csv`, существующие изображения и split labels
не удаляются и не перезаписываются. Команду можно безопасно повторять: уже
скачанные валидные JPEG будут пропущены.

## Самый простой запуск в Colab

Открой `notebooks/TaxaLens_v0.9_Multisource_PoC_Colab.ipynb` и выполняй ячейки
сверху вниз. Вторая рабочая ячейка запускает только BIOSCAN top-up.

Эквивалентная команда:

```bash
python scripts/run_multisource_poc_v09.py \
  --stage bioscan-topup \
  --data-root /content/drive/MyDrive/EntoKey/Foundation_v06 \
  --bioscan-root /content/drive/MyDrive/EntoKey/Foundation_v06/raw/bioscan \
  --bioscan-manifest /content/drive/MyDrive/EntoKey/Foundation_v06/manifests/bioscan_raw.parquet
```

Отчёты появятся здесь:

```text
.../raw/bioscan/diptera_added_families_topup_selection_report.json
.../raw/bioscan/diptera_added_families_topup_download_report.json
.../raw/bioscan/diptera_added_families_topup_progress.json
```

После top-up нужно заново выполнить `ingest`, `assemble` и `plan`, потому что
старый master corpus был создан до добавления этих изображений. Локальный
BIOSCAN pool может стать немного больше 30 000, но строгий multi-source plan
выберет из него ровно 30 000; общий PoC поэтому останется равным 100 000.

Не запускай старый BIOSCAN 30k notebook заново и не удаляй существующие
selection/progress файлы.
