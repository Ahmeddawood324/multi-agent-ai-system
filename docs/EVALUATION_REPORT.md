# Evaluation Report

## 1. Reliability
- 10/10 consecutive runs completed with all outputs created and the fact check passed (100%).

## 2. Accuracy (agent vs independent pandas calculation)

| Check | Result |
|---|---|
| total revenue | PASS |
| total units | PASS |
| orders count | PASS |
| revenue by region | PASS |
| revenue by product | PASS |
| top region | PASS |
| worst product | PASS |
| feedback comments parsed | PASS |

Accuracy: 8/8 checks passed.

## 3. Failure injection (robustness)

| Scenario | Result |
|---|---|
| API down -> cached rates used | PASS |
| PDF missing -> report still produced | PASS |
| LLM hallucination -> caught by validator | PASS |
| LLM timeouts -> retried | PASS |
| Sheet missing -> report still produced | PASS |

## 4. Efficiency
- Average end-to-end time (offline LLM): 0.46 s
- With 0.3 s simulated LLM latency per call: sequential 3.30 s vs parallel 2.97 s (speed-up x1.11).

## Conclusion
Numbers are computed by code and only *narrated* by the LLM, then fact-checked by a validator agent, which gives high accuracy; retries and fallbacks make the pipeline robust to source and LLM failures; parallel stages reduce total latency.