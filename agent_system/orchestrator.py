"""Orchestrator: coordinates all agents.

Stage 1  RETRIEVE   (parallel)   sheet + pdf + api
Stage 2  ANALYSE    (parallel)   sales + feedback            -> then market (needs sales total)
Stage 3  SYNTHESISE (sequential) executive summary
Stage 4  VALIDATE   (sequential) fact-check, retry once, then safe fallback
Stage 5  ACT        (sequential) report, dashboard, email

A failing source does NOT crash the run: the pipeline degrades gracefully and records a warning.
"""
import time
from concurrent.futures import ThreadPoolExecutor

from . import config
from .actions import ActionAgent
from .agents import (APIRetrievalAgent, ExecutiveSummaryAgent, FeedbackAnalystAgent, MarketAnalystAgent,
                     PDFRetrievalAgent, SalesAnalystAgent, SheetRetrievalAgent, ValidatorAgent)
from .llm import MockBackend, get_llm


class Orchestrator:
    def __init__(self, llm=None, parallel=True, output_dir=None, sheet_source=None, pdf_source=None, api_url=None):
        self.llm = llm or get_llm()
        self.parallel = parallel
        self.output_dir = output_dir or config.OUTPUT_DIR
        self.sheet_source, self.pdf_source, self.api_url = sheet_source, pdf_source, api_url
        self.log, self.warnings = [], []

    # ---- helpers ----
    def _timed(self, stage, agent, fn, *args):
        t = time.perf_counter()
        try:
            result = fn(*args)
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            result, status = None, f"failed: {type(exc).__name__}: {exc}"
            self.warnings.append(f"{agent.name} failed ({type(exc).__name__}: {exc}); continuing without it")
        self.warnings.extend(getattr(agent, "warnings", []))
        agent.warnings = []
        self.log.append({"stage": stage, "agent": agent.name, "status": status,
                         "seconds": round(time.perf_counter() - t, 3)})
        return result

    def _run_parallel(self, jobs):
        if not self.parallel:
            return [self._timed(*j) for j in jobs]
        with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
            futures = [ex.submit(self._timed, *j) for j in jobs]
            return [f.result() for f in futures]

    # ---- main ----
    def run(self):
        t0 = time.perf_counter()
        llm = self.llm
        sheet_a, pdf_a, api_a = SheetRetrievalAgent(llm), PDFRetrievalAgent(llm), APIRetrievalAgent(llm)

        sheet, pdf, api = self._run_parallel([
            ("1-retrieve", sheet_a, sheet_a.run, self.sheet_source),
            ("1-retrieve", pdf_a, pdf_a.run, self.pdf_source),
            ("1-retrieve", api_a, api_a.run, self.api_url),
        ])

        sales_a, fb_a, mk_a = SalesAnalystAgent(llm), FeedbackAnalystAgent(llm), MarketAnalystAgent(llm)
        jobs, keys = [], []
        if sheet:
            jobs.append(("2-analyse", sales_a, sales_a.run, sheet))
            keys.append("sales")
        if pdf:
            jobs.append(("2-analyse", fb_a, fb_a.run, pdf))
            keys.append("feedback")
        results = dict(zip(keys, self._run_parallel(jobs))) if jobs else {}
        sales, feedback = results.get("sales"), results.get("feedback")
        market = self._timed("2-analyse", mk_a, mk_a.run, api, sales) if api else None

        if not any([sales, feedback, market]):
            raise RuntimeError("All data sources failed; nothing to report.")

        exec_a, val_a = ExecutiveSummaryAgent(llm), ValidatorAgent(llm)
        executive = self._timed("3-synthesise", exec_a, exec_a.run, sales, feedback, market)
        validation = self._timed("4-validate", val_a, val_a.run, executive["text"], executive["facts"])
        attempts = 1
        while not validation["ok"] and attempts < 2:  # one retry with the LLM
            attempts += 1
            self.warnings.append("Fact check failed (" + "; ".join(validation["issues"][:3]) + "); regenerating")
            executive = self._timed("3-synthesise", exec_a, exec_a.run, sales, feedback, market)
            validation = self._timed("4-validate", val_a, val_a.run, executive["text"], executive["facts"])
        if not validation["ok"]:  # safe fallback: deterministic writer that only uses real numbers
            self.warnings.append("LLM output still failed the fact check; used the safe offline summary instead")
            text = MockBackend().complete("TASK:executive", "FACTS_JSON:" + __import__("json").dumps(executive["facts"]))
            executive = {"facts": executive["facts"], "text": text}
            validation = val_a.run(text, executive["facts"])

        meta = {"llm": getattr(llm, "name", "custom"), "parallel": self.parallel, "warnings": self.warnings,
                "validation_ok": validation["ok"], "attempts": attempts,
                "seconds": round(time.perf_counter() - t0, 2), "log": self.log}
        actions = ActionAgent(self.output_dir)
        meta["seconds"] = round(time.perf_counter() - t0, 2)
        outputs = actions.run(executive, sales, feedback, market, meta)
        import json
        (actions.out / "run_log.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return {"sales": sales, "feedback": feedback, "market": market, "executive": executive,
                "validation": validation, "outputs": outputs, "meta": meta}
