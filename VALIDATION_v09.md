# TaxaLens v0.9 validation snapshot

Проверено после добавления Muscidae, Tachinidae и безопасного переиспользования
уже скачанного BIOSCAN:

- Python `compileall`: passed;
- полный тестовый набор: **48 passed**;
- целевой scope содержит ровно 20 уникальных семейств;
- Muscidae и Tachinidae обязательны в итоговом training plan;
- `bioscan-topup` сохраняет существующие 30k, выбирает только Muscidae и
  Tachinidae и передаёт downloader только недостающие targeted rows;
- merge сохраняет прежние specimen IDs и удаляет дубликаты.

Это технические проверки кода. Biological accuracy остаётся pending до первого
полного обучения и held-out evaluation.
