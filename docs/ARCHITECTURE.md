# Architecture

## Pipeline

| Stage | Agents | Mode | Output |
|---|---|---|---|
| 1. Retrieve | SheetRetrievalAgent, PDFRetrievalAgent, APIRetrievalAgent | **parallel** | clean rows, parsed comments, FX rates |
| 2. Analyse | SalesAnalystAgent, FeedbackAnalystAgent (parallel) -> MarketAnalystAgent | parallel then sequential (Market needs the sales total) | facts (numbers) + narrative (LLM text) |
| 3. Synthesise | ExecutiveSummaryAgent | sequential | executive summary |
| 4. Validate | ValidatorAgent | sequential | ok / issues; retry once, then safe fallback |
| 5. Act | ActionAgent | sequential | report.md, report.html, dashboard.json, email.eml / SMTP |

```
            ┌──────────────┐
            │ Orchestrator │  (timing log, warnings, retries, fallbacks)
            └──────┬───────┘
   ┌───────────────┼────────────────┐         STAGE 1 (parallel)
 Sheet           PDF              API
   │               │                │
 Sales          Feedback         Market        STAGE 2 (Sales+Feedback parallel, Market after Sales)
   └───────────────┼────────────────┘
            Executive Summary                  STAGE 3
                   │
               Validator  ──fail──> retry ──fail──> safe offline summary      STAGE 4
                   │
              Action Agent ──> report / dashboard / email                     STAGE 5
```

## Key design decisions
1. **Code computes, LLM explains.** All numbers (sums, averages, percentages) are computed in Python; the LLM only
   receives them as `FACTS_JSON` and writes the interpretation. This avoids arithmetic hallucinations.
2. **Validator agent.** Every non-trivial number in the LLM text must exist in the source facts, otherwise the text is
   regenerated once and finally replaced by a deterministic safe summary.
3. **Graceful degradation.** If one source fails (missing PDF, sheet error) the run continues and the report states what
   is missing. API failure uses cached rates. LLM failures are retried 3 times then use an offline writer.
4. **Pluggable LLM.** `AnthropicBackend` (real Claude) or `MockBackend` (offline, deterministic, used in tests).
5. **Parallelism.** Independent agents run in a `ThreadPoolExecutor`; measured speed-up is in `EVALUATION_REPORT.md`.
6. **Observability.** `output/run_log.json` holds every agent's status and duration.

## Data contracts
* Sheet agent -> `{rows:[{date,region,product,units,revenue}], rows_dropped}`
* PDF agent -> `{comments:[{city,rating,text}]}`
* API agent -> `{rates:{EGP,EUR,SAR}, source}`
* Analyst agents -> `{facts:{...numbers...}, narrative:"- bullet..."}`
* Executive agent -> `{facts:{sales,feedback,market}, text:"markdown"}`
* Validator -> `{ok:bool, issues:[...]}`
