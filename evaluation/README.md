## Оценка качества (gold dataset + метрики)

Эта папка содержит инструменты для **ручной разметки (gold dataset)** и **расчёта метрик** качества NER.

### Как использовать

- **Шаг 1 — gold**

Используем готовый gold:
`evaluation/gold/gold_dataset_50x3_unlabeled.json`

- **Шаг 2 — получить predictions новой модели**

`python evaluation/run_pipeline_on_gold.py --engine model --local-files-only --gold evaluation/gold/gold_dataset_50x3_unlabeled.json --out evaluation/reports/predictions_on_gold_model_50x3.json`

- **Шаг 3 — посчитать метрики**

`python evaluation/metrics_evaluator.py --gold evaluation/gold/gold_dataset_50x3_unlabeled.json --pred evaluation/reports/predictions_on_gold_model_50x3.json --out evaluation/reports/metrics_report_model_50x3.json`

Сводка результатов: `evaluation/reports/RESULTS.md`


