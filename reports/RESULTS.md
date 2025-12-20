## Результаты оценки (кратко)

### Что сравнивали
- **Gold**: `evaluation/gold/gold_dataset_50x3_unlabeled.json` (150 статей, 50/50/50)
- **Predictions**: `evaluation/reports/predictions_on_gold_50x3.json`
- **Отчёт JSON**: `evaluation/reports/metrics_report_50x3.json`

Предсказания получали командой:
`python evaluation/run_pipeline_on_gold.py --disable-davlan --gold evaluation/gold/gold_dataset_50x3_unlabeled.json --out evaluation/reports/predictions_on_gold_50x3.json`

> Примечание: `--disable-davlan` использован из‑за сетевых таймаутов при скачивании Davlan‑модели через `cas-bridge.xethub.hf.co`.

### Итоговые метрики (NER)
Считаются по типам `persons/organizations/locations` (micro-агрегация, fuzzy matching).

- **person**: Precision **49.7%**, Recall **70.2%**, F1 **58.2%** (support 325)
- **organization**: Precision **0.0%**, Recall **0.0%**, F1 **0.0%** (support 655)
- **location**: Precision **57.9%**, Recall **20.7%**, F1 **30.5%** (support 512)
- **overall**: Precision **52.0%**, Recall **22.4%**, F1 **31.3%** (support 1492)

### Coverage (диагностика “извлекаем ли вообще”)
- **Aligned articles**: 150 (все статьи есть и в gold, и в predictions)
- **Articles with ANY prediction**: **90.0%** (пустых по всем типам: **10.0%**)
- **persons**: pred_nonempty **73.3%**, gold_nonempty **78.7%**, avg_pred **3.06**, avg_gold **2.17**
- **organizations**: pred_nonempty **0.0%**, gold_nonempty **100.0%**, avg_pred **0.00**, avg_gold **4.37**
- **locations**: pred_nonempty **62.7%**, gold_nonempty **98.0%**, avg_pred **1.22**, avg_gold **3.41**

### Короткая интерпретация
- **ORG = 0%** — это не “ошибка метрик”, а **нулевое покрытие по организациям** (coverage показывает 0% статей с ORG в predictions при 100% в gold).
- **Recall по location низкий** — пайплайн часто не извлекает/не нормализует локации так, как они размечены в gold (разная схема типов/формулировок).


