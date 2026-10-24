import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_system import config  # noqa: E402
from agent_system.llm import MockBackend  # noqa: E402
from agent_system.orchestrator import Orchestrator  # noqa: E402


class HallucinatingLLM(MockBackend):
    """Always writes a number that is not in the data -> validator must catch it."""
    name = "hallucinating"

    def complete(self, system, prompt):
        text = super().complete(system, prompt)
        return text + "\n- Revenue grew 987654 percent." if "TASK:executive" in system else text


class FlakyLLM(MockBackend):
    """Fails the first 2 calls of each run -> retry logic must absorb it."""
    name = "flaky"

    def __init__(self):
        super().__init__()
        self.calls = 0

    def complete(self, system, prompt):
        self.calls += 1
        if self.calls <= 2:
            raise TimeoutError("simulated API timeout")
        return super().complete(system, prompt)


def run(tmp_path, **kw):
    return Orchestrator(llm=kw.pop("llm", MockBackend()), output_dir=tmp_path, **kw).run()


def oracle():
    df = pd.read_csv(config.DATA_DIR / "sales.csv")
    df = df.dropna(subset=["units", "revenue"]).drop_duplicates()
    df = df[(df.units > 0) & (df.revenue > 0)]
    return df


def test_numbers_match_independent_pandas_calculation(tmp_path):
    f = run(tmp_path)["sales"]["facts"]
    df = oracle()
    assert f["total_revenue"] == pytest.approx(df.revenue.sum())
    assert f["n_orders"] == len(df)
    assert f["by_region"] == pytest.approx(df.groupby("region").revenue.sum().to_dict())
    assert f["top_product"] == df.groupby("product").revenue.sum().idxmax()


def test_bad_rows_are_cleaned(tmp_path):
    raw_rows = len(pd.read_csv(config.DATA_DIR / "sales.csv"))
    f = run(tmp_path)["sales"]["facts"]
    assert f["rows_dropped"] >= 3  # duplicate + empty + negative rows were injected on purpose
    assert f["rows_dropped"] + f["n_orders"] == raw_rows


def test_all_outputs_created(tmp_path):
    run(tmp_path)
    for name in ["report.md", "report.html", "dashboard.json", "email.eml", "run_log.json"]:
        assert (tmp_path / name).stat().st_size > 100


def test_pdf_parsed_completely(tmp_path):
    assert run(tmp_path)["feedback"]["facts"]["n_comments"] == 20


def test_api_failure_falls_back(tmp_path):
    r = run(tmp_path, api_url="http://127.0.0.1:9/none")
    assert r["market"]["facts"]["rates_source"] == "cached fallback"
    assert any("API unavailable" in w for w in r["meta"]["warnings"])


def test_missing_pdf_degrades_gracefully(tmp_path):
    r = run(tmp_path, pdf_source=str(tmp_path / "missing.pdf"))
    assert r["feedback"] is None and r["sales"] is not None
    assert "unavailable" in r["executive"]["text"]
    assert (tmp_path / "report.html").exists()


def test_sheet_and_pdf_down_api_fallback_still_reports(tmp_path):
    o = Orchestrator(llm=MockBackend(), output_dir=tmp_path, sheet_source="nope.csv",
                     pdf_source="nope.pdf")
    o.api_url = "http://127.0.0.1:9/none"
    # API still has cached fallback, so only sheet+pdf fail and the report is still produced
    assert o.run()["market"] is not None


def test_hallucination_is_caught_and_replaced(tmp_path):
    r = run(tmp_path, llm=HallucinatingLLM())
    assert "987654" not in r["executive"]["text"]
    assert r["validation"]["ok"]
    assert any("fact check" in w.lower() for w in r["meta"]["warnings"])


def test_flaky_llm_is_retried(tmp_path):
    r = run(tmp_path, llm=FlakyLLM())
    assert r["validation"]["ok"] and r["sales"] is not None


def test_parallel_is_faster_than_sequential(tmp_path):
    # The real API is replaced by an instant local failure (cached rates), so network jitter cannot hide
    # the difference between parallel and sequential execution.
    slow = MockBackend(latency=0.3)
    offline = "http://127.0.0.1:9/none"
    import time
    t = time.perf_counter(); run(tmp_path / "a", llm=slow, parallel=True, api_url=offline); par = time.perf_counter() - t
    t = time.perf_counter(); run(tmp_path / "b", llm=slow, parallel=False, api_url=offline); seq = time.perf_counter() - t
    assert par < seq
