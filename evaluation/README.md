## Оценка качества (gold dataset + метрики)

Эта папка содержит инструменты для **ручной разметки (gold dataset)** и **расчёта метрик** качества NER.

### Как использовать

- **Шаг 1 — создать шаблон gold**

Запуск (из корня проекта или из этой папки):
`python3 evaluation/create_gold_dataset.py`

Будет создан файл `evaluation/gold/gold_dataset.json` — его нужно **заполнить вручную** (списки сущностей) и поставить `manually_verified: true` для размеченных статей.

- **Шаг 2 — прогнать пайплайн и получить предсказания на этих 30 статьях**

`python3 evaluation/run_pipeline_on_gold.py`

Скрипт сохранит предсказания в `evaluation/reports/predictions_on_gold.json`.

- **Шаг 3 — посчитать метрики**

По умолчанию `metrics_evaluator.py` читает `results_hybrid_final.json`. Поэтому:
- либо **скопируйте** `evaluation/reports/predictions_on_gold.json` в `results_hybrid_final.json`,
- либо (лучше) поменяйте путь в `evaluation/metrics_evaluator.py` под ваш файл предсказаний.

Запуск:
`python3 evaluation/metrics_evaluator.py`

Вывод: таблица precision/recall/F1 + файл отчёта `evaluation/reports/metrics_report.json`.


