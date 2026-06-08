# Corrected Final Eval (250-sample) — measurement-scope correction

**Derived offline** from `post_fix_sweep_2/online_cell_a0.55_u0.76_full250.json`
(zero LLM calls). Model: `openai/gpt-oss-120b`; clean run
(contaminated=False, model_mix={'gpt-oss-120b': 449},
runtime_error_count=0).

## Result

| Metric              | Baseline        | Corrected           | Δ           |
| ------------------- | --------------- | ------------------- | ----------- |
| Fully Correct       | 218/250 = 0.872 | **224/250 = 0.896** | +2.4pp      |
| Deadline Exact      | 0.8802          | **0.9009**          | +0.0207     |
| Deadline Near (±1d) | 0.9050          | 0.9138              | +0.0088     |
| Title F1            | 0.9738          | 0.9738              | (unchanged) |
| Assignee F1         | 0.9746          | 0.9746              | (unchanged) |
| Conflict F1         | 0.7805          | 0.7805              | (unchanged) |
| ECE                 | 0.1023          | 0.1023              | (unchanged) |

**Samples flipped to correct (6)**: pr-216, pr-211, pr-209, pr-218, pr-215, pr-214
— each an `edge_priority` sample that was failing _only_ on the uncurated deadline
label (model read the text correctly).

Deadline denominator excludes 232 scored deadlines
(was 242); the difference is the excluded edge_priority labels.
