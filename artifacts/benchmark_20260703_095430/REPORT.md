# Epis-KG — Empirical Evaluation Report

*Generated 20260703_095430 UTC · commit `9d1008c632` · model `deepseek-v4-flash` via `deepseek`*

## 1. Dataset

Benchmark: **LIAR** (Wang, 2017). Test n = **1267**, validation n = **120**. Six-point veracity labels mapped to a continuous [0,1] scale (pants-fire=0.0 … true=1.0).

Test label distribution: `{'true': 208, 'false': 249, 'half-true': 265, 'pants-fire': 92, 'barely-true': 212, 'mostly-true': 241}`

## 1b. Pipeline reliability

Metrics are computed **only on schema-valid extractions**. LLM connection/parse failures and extractions that failed validation after all self-correction attempts are excluded and reported here — no row is ever assigned a fabricated score.

- Test: `{'requested': 1267, 'scored_ok': 1252, 'invalid': 15, 'errors': 0, 'failed': 15, 'success_rate': 0.9882}`
- Validation: `{'requested': 120, 'scored_ok': 120, 'invalid': 0, 'errors': 0, 'failed': 0, 'success_rate': 1.0}`

## 2. Method

Each statement is decomposed by the multi-agent LangGraph pipeline into atomic claims + rhetoric; the Epistemic Integrity Score (EIS) is computed by the `epistemic_math` engine. We report the correlation of the EIS with ground-truth veracity and the AUC-ROC of the EIS as a truthfulness classifier (true-ish = veracity ≥ 0.5). 95% CIs are bootstrap (2000 resamples).

## 3. Results (held-out test split)

| Configuration | Pearson r (95% CI) | Spearman ρ | AUC-ROC (95% CI) | n |
|---|---|---|---|---|
| Default weights | 0.535 [0.492, 0.572] | 0.499 | 0.796 [0.771, 0.819] | 1252 |
| **Optuna-tuned** | 0.535 [0.492, 0.574] | 0.498 | 0.794 [0.770, 0.817] | 1252 |

## 4. Tuned hyperparameters

Selected on the validation split (best Pearson r = 0.564):

- α (rhetoric) = **0.574**
- β (contradiction) = **0.596**
- γ (temporal) = **0.917**
- λ (decay const) = **0.282**
- prior strength = **11.398**

## 5. Reproducibility & artifacts

This report ships with: `signals_{test,validation}.json` (cached per-claim signals), `predictions.csv` (per-statement EIS vs truth), `tuned_params.json`, `report.json`, and `run.log` (JSON-lines trace). Package versions: `{'datasets': '5.0.0', 'optuna': '4.9.0', 'scikit-learn': '1.9.0', 'scipy': '1.18.0', 'numpy': '2.5.0', 'openai': '2.44.0'}`.

## 6. Notes & limitations

- LIAR labels rate *claim veracity*; the EIS measures *epistemic integrity* (evidence, rhetoric, contradiction, decay). Correlation is expected but the constructs are not identical — the EIS additionally penalises manipulative-but-true and rewards well-sourced framing.
- Extraction is LLM-based; consensus mode (two models) can be enabled to further reduce extraction variance.
