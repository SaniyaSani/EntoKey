# Whole-Fly Pipeline v0.8 — DEFAULT baseline

## Главное решение

Первый эксперимент **не режет изображение на tiles и не сегментирует анатомию**.
Одна фотография целой мухи даёт один DINOv3 embedding.

```text
BIOSCAN ─┐
iNat ────┼─> normalize -> license gate -> deduplicate -> group-safe split
GBIF ────┤                                              |
DiSSCo ──┘                                              v
                                              balanced training plan
                                                      |
                                                      v
                                            COMPLETE IMAGE
                                                      |
                                             square pad/resize
                                                      |
                                                      v
                                                    DINOv3
                                                      |
                                                      v
                                             one image embedding
                                                      |
                          +---------------------------+-------------------+
                          v                           v                   v
                       family                 genus | family       species | genus
                          |                           |                   |
                          +--------------- open-set / confidence --------+
                                                      |
                                                      v
                                          nearest specimen retrieval
```

## Почему так

Это настоящий baseline: минимум предположений и минимум preprocessing. Он отвечает на главный вопрос — насколько хорошо DINOv3 умеет идентифицировать Diptera по целой картинке сам.

Мы **не предполагаем заранее**, что tiles улучшат результат. Разрезание может увеличить детали, но может также разорвать wing venation, proportions и spatial context. Поэтому tiles теперь только отдельная ablation-ветка после baseline.

## Что делает preprocessing

DINOv3 получает **всю исходную фотографию**. Код сохраняет aspect ratio: изображение вписывается в квадрат с padding, а не center-crop'ается. Поэтому кончики крыльев/ног не должны исчезать из-за обязательного crop.

## Первый эксперимент A

`A = whole image only`

Config:

```text
configs/wholefly_foundation_v08.json
```

Ключевые параметры:

```json
{
  "strategy": "whole_image_only",
  "tile_grid": 1,
  "include_whole": true,
  "segmentation_required": false,
  "specimen_crop_required": false
}
```

## Что НЕ делаем до результатов A

- anatomy masks;
- head/thorax/abdomen segmentation;
- 2x2 tiles;
- automatic specimen crop;
- wing/head specialist model.

## Что сравним потом

Только после фиксированного validation baseline:

- **B: specimen crop** — целая муха, но меньше пустого/фонового пространства;
- **C: whole + tiles** — multi-crop ablation;
- specialist modules — только для устойчивых confusion pairs.

Оставляем B/C только если они улучшают **тот же самый held-out validation set**.

## Evaluation

Минимум:

- family top-1 / top-5;
- genus top-1 / top-5;
- curated species top-1 / top-5;
- per-source accuracy;
- confusion table;
- open-set rejection;
- BIOSCAN official held-out/unseen отдельно;
- field-photo vs preserved-specimen domain gap.

## Leakage rules

- Все изображения одного specimen/observation остаются в одном split.
- Cross-source duplicates не могут быть одновременно train и validation/test.
- Official BIOSCAN held-out splits не переносятся в train.
- Species heads используют только разрешённые quality labels.
