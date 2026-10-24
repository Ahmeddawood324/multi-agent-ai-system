"""Evaluation of the system: reliability, accuracy, efficiency.   python evaluate.py
Writes docs/EVALUATION_REPORT.md"""
import tempfile
import time
from pathlib import Path

import pandas as pd

from agent_system import config
from agent_system.llm import MockBackend
from agent_system.orchestrator import Orchestrator
from tests.test_pipeline import FlakyLLM, HallucinatingLLM

RUNS = 10
tmp = Path(tempfile.mkdtemp())


def go(name, **kw):
    t = time.perf_counter()
    try:
        r = Orchestrator(output_dir=tmp / name, **kw).run()
        return r, time.perf_counter() - t
    except Exception:  # noqa: BLE001
        return None, time.perf_counter() - t


# 1) Reliability: repeated normal runs
ok = 0
results = []
for i in range(RUNS):
    r, sec = go(f"n{i}", llm=MockBackend())
    if r and r["validation"]["ok"] and all((tmp / f"n{i}" / f).exists() for f in r["outputs"]["files"]):
        ok += 1
    results.append((r, sec))

# 2) Accuracy against an independent pandas oracle
df = pd.read_csv(config.DATA_DIR / "sales.csv").dropna(subset=["units", "revenue"]).drop_duplicates()
df = df[(df.units > 0) & (df.revenue > 0)]
f = results[0][0]["sales"]["facts"]
checks = {
    "total revenue": abs(f["total_revenue"] - df.revenue.sum()) < 0.01,
    "total units": f["total_units"] == df.units.sum(),
    "orders count": f["n_orders"] == len(df),
    "revenue by region": all(abs(f["by_region"][k] - v) < 0.01 for k, v in df.groupby("region").revenue.sum().items()),
    "revenue by product": all(abs(f["by_product"][k] - v) < 0.01 for k, v in df.groupby("product").revenue.sum().items()),
    "top region": f["top_region"] == df.groupby("region").revenue.sum().idxmax(),
    "worst product": f["worst_product"] == df.groupby("product").revenue.sum().idxmin(),
    "feedback comments parsed": results[0][0]["feedback"]["facts"]["n_comments"] == 20,
}

# 3) Failure injection
scen = {}
r, _ = go("f1", llm=MockBackend(), api_url="http://127.0.0.1:9/x")
scen["API down -> cached rates used"] = bool(r and r["market"]["facts"]["rates_source"] == "cached fallback")
r, _ = go("f2", llm=MockBackend(), pdf_source="missing.pdf")
scen["PDF missing -> report still produced"] = bool(r and r["feedback"] is None and r["sales"])
r, _ = go("f3", llm=HallucinatingLLM())
scen["LLM hallucination -> caught by validator"] = bool(r and r["validation"]["ok"] and "987654" not in r["executive"]["text"])
r, _ = go("f4", llm=FlakyLLM())
scen["LLM timeouts -> retried"] = bool(r and r["validation"]["ok"])
r, _ = go("f5", llm=MockBackend(), sheet_source="missing.csv")
scen["Sheet missing -> report still produced"] = bool(r and r["sales"] is None and r["feedback"])

# 4) Efficiency: parallel vs sequential with simulated 0.3s LLM latency
slow = MockBackend(latency=0.3)
offline = "http://127.0.0.1:9/none"  # remove network jitter from the comparison
_, par = go("p", llm=slow, parallel=True, api_url=offline)
_, seq = go("s", llm=slow, parallel=False, api_url=offline)
avg = sum(s for _, s in results) / RUNS

lines = ["# Evaluation Report", "", "## 1. Reliability",
         f"- {ok}/{RUNS} consecutive runs completed with all outputs created and the fact check passed ({ok / RUNS:.0%}).", "",
         "## 2. Accuracy (agent vs independent pandas calculation)", "", "| Check | Result |", "|---|---|"]
lines += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in checks.items()]
lines += ["", f"Accuracy: {sum(checks.values())}/{len(checks)} checks passed.", "",
          "## 3. Failure injection (robustness)", "", "| Scenario | Result |", "|---|---|"]
lines += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in scen.items()]
lines += ["", "## 4. Efficiency", f"- Average end-to-end time (offline LLM): {avg:.2f} s",
          f"- With 0.3 s simulated LLM latency per call: sequential {seq:.2f} s vs parallel {par:.2f} s "
          f"(speed-up x{seq / par:.2f}).", "",
          "## Conclusion",
          "Numbers are computed by code and only *narrated* by the LLM, then fact-checked by a validator agent, "
          "which gives high accuracy; retries and fallbacks make the pipeline robust to source and LLM failures; "
          "parallel stages reduce total latency."]
out = Path(__file__).parent / "docs" / "EVALUATION_REPORT.md"
out.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
