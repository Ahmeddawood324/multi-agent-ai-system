# Multi-Agent Business Intelligence System

Final Project (Week 6) - *Developing a Multi-Agent AI Agent System*

An AI agent system that automatically **collects** data from 3 different sources, **analyses and summarises**
it with an LLM, **fact-checks** the result, and **acts** by producing a report, a dashboard and an email.

```
 Sheet (CSV/Google Sheets) ─┐                                   ┌─> report.md / report.html (dashboard)
 PDF customer feedback ─────┼─> Analysts ─> Executive Summary ─> Validator ─> Action Agent ─┼─> dashboard.json
 REST API (exchange rates) ─┘   (parallel)                      (fact-check)               └─> email.eml (+ SMTP send)
```

## Quick start
```bash
pip install -r requirements.txt
python run.py --mock          # offline demo, no API key needed
```
Results appear in `output/`: open `output/report.html` in a browser.

### Use real Claude
```bash
export ANTHROPIC_API_KEY=sk-ant-...      # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python run.py
```
### Use your own data
| What | How |
|---|---|
| Google Sheet | Publish it, then `export SHEET_SOURCE="https://docs.google.com/spreadsheets/d/<ID>/export?format=csv"` (columns: `date,region,product,units,revenue`) |
| PDF | `export PDF_SOURCE=/path/feedback.pdf` (lines like `1. [Cairo] Rating 4/5 - text`) |
| API | `export API_URL=...` (default: open.er-api.com USD rates; cached fallback if offline) |
| Send real email | `export SMTP_HOST=smtp.gmail.com SMTP_USER=... SMTP_PASS=<app password> EMAIL_TO=...` |

## Requirement -> where it is implemented
| Project objective | Implementation |
|---|---|
| 1. Data retrieval | `SheetRetrievalAgent`, `PDFRetrievalAgent`, `APIRetrievalAgent` in `agent_system/agents.py` |
| 2. Processing & summarisation | `SalesAnalystAgent`, `FeedbackAnalystAgent`, `MarketAnalystAgent`, `ExecutiveSummaryAgent` (LLM writes from computed facts) |
| 3. Automated actions | `ActionAgent` in `agent_system/actions.py`: report (MD+HTML with charts), dashboard JSON, email |
| 4. Workflow orchestration | `agent_system/orchestrator.py` - parallel + sequential stages, retries, fallbacks |
| 5. Presentation & explanation | `docs/ARCHITECTURE.md`, `docs/VIDEO_SCRIPT.md`, `docs/PROJECT_EXPLANATION_AR.md` |
| 6. Testing & evaluation | `tests/test_pipeline.py` (10 tests), `evaluate.py` -> `docs/EVALUATION_REPORT.md` |

## Run tests / evaluation
```bash
python -m pytest -q
python evaluate.py
```

## Project layout
```
run.py                     entry point
evaluate.py                reliability / accuracy / efficiency evaluation
generate_sample_data.py    recreates data/ (sales.csv, customer_feedback.pdf, fallback_rates.json)
agent_system/              agents.py, orchestrator.py, actions.py, llm.py, config.py, utils.py
tests/                     pytest suite incl. failure injection
docs/                      architecture, evaluation, video script, Arabic explanation
output/                    generated report, dashboard, email, run log
```
