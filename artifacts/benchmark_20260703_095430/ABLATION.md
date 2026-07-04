# Epis-KG — Prior Ablation (LIAR test split)

Isolating the contribution of the Bayesian source-credibility prior. All conditions reuse the SAME cached LLM extractions (no re-running), prior coverage = 100.0% of test statements.

| Condition | Pearson r (95% CI) | Spearman ρ | AUC-ROC (95% CI) | n |
|---|---|---|---|---|
| A · neutral prior + default weights | 0.160 [0.105, 0.213] | 0.145 | 0.546 [0.524, 0.567] | 1252 |
| B · speaker-credibility prior + default weights | 0.535 [0.492, 0.574] | 0.498 | 0.794 [0.770, 0.817] | 1252 |
| C · speaker-credibility prior + tuned weights | 0.534 [0.491, 0.573] | 0.497 | 0.794 [0.769, 0.817] | 1252 |

Tuned weights (C), selected on the validation split under the credibility prior: α=0.576, β=1.296, γ=0.836, λ=0.206, prior_strength=11.98.

**Reading:** condition A is the content-only EIS (rhetoric-driven only, since isolated LIAR statements have no evidence/contradiction graph). B/C add the speaker's historical credibility as the Bayesian prior — standard, non-leaking LIAR metadata (counts exclude the current statement). This is an honest ablation: numbers are whatever the data yields, computed only on schema-valid extractions.
