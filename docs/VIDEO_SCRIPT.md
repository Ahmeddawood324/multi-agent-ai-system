# Face-cam Video Script (about 6-8 minutes)

Keep your camera on the whole time. Share your screen when demonstrating.

**0:00 - Intro (30 s)**
"Hi, I'm <name>. My final project is a Multi-Agent AI system that automatically turns raw data from a Google Sheet,
a PDF and an API into an executive report, a dashboard and an email."

**0:30 - The problem (30 s)**
"Managers waste hours collecting numbers from different places. My agents do it in under a second and can be
scheduled every week."

**1:00 - Architecture (2 min)** *(show docs/ARCHITECTURE.md diagram)*
- Stage 1: three retrieval agents run in parallel.
- Stage 2: sales and feedback analysts run in parallel, then the market agent converts revenue to EGP.
- Stage 3: executive summary agent writes the final text with the LLM.
- Stage 4: validator agent fact-checks every number; retry, then safe fallback.
- Stage 5: action agent creates report, dashboard and email.
- Key idea: code computes numbers, the LLM only explains them, so no arithmetic hallucinations.

**3:00 - Live demo (2 min)**
1. Show `data/sales.csv` (point out the 3 bad rows) and `data/customer_feedback.pdf`.
2. Run `python run.py` and show the pipeline log with timings.
3. Open `output/report.html` (charts), `output/email.eml`, `output/dashboard.json`.

**5:00 - Testing & evaluation (1.5 min)**
Run `python -m pytest -q` (10 passed) and show `docs/EVALUATION_REPORT.md`: 100% reliability, 8/8 accuracy checks vs
pandas, failure injection (API down, PDF missing, LLM hallucination, LLM timeouts), parallel speed-up.

**6:30 - Wrap up (30 s)**
"Limitations: keyword sentiment and a small sample. Future work: more sources, a database, scheduling, and
LLM-based sentiment. Thank you!"
