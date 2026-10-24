"""All agents. Each agent has one job and a clear input/output contract.

Retrieval agents : SheetRetrievalAgent, PDFRetrievalAgent, APIRetrievalAgent
Analysis agents  : SalesAnalystAgent, FeedbackAnalystAgent, MarketAnalystAgent
Synthesis agent  : ExecutiveSummaryAgent
Quality agent    : ValidatorAgent
"""
import csv
import io
import json
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from . import config
from .llm import INSTRUCTIONS, MockBackend
from .utils import facts_numbers, extract_numbers, retry


class Agent:
    name = "agent"

    def __init__(self, llm=None):
        self.llm = llm or MockBackend()
        self.warnings = []

    def narrate(self, task, facts):
        """Ask the LLM to write about already-computed facts. Retries; falls back to the offline writer."""
        system = f"TASK:{task}\n{INSTRUCTIONS[task]}"
        prompt = "FACTS_JSON:" + json.dumps(facts, ensure_ascii=False)
        last = None
        for _ in range(3):
            try:
                return self.llm.complete(system, prompt)
            except Exception as exc:  # noqa: BLE001
                last = exc
        self.warnings.append(f"{self.name}: LLM failed ({last}); used offline fallback writer")
        return MockBackend().complete(system, prompt)


def _fetch_text(src, timeout=10):
    if str(src).startswith("http"):
        with urllib.request.urlopen(src, timeout=timeout) as r:
            return r.read().decode("utf-8")
    return Path(src).read_text(encoding="utf-8")


# ======================= RETRIEVAL AGENTS =======================
class SheetRetrievalAgent(Agent):
    name = "SheetRetrievalAgent"

    @retry(attempts=2)
    def run(self, source=None):
        raw = _fetch_text(source or config.SHEET_SOURCE)
        rows, seen, dropped = [], set(), 0
        for r in csv.DictReader(io.StringIO(raw)):
            try:
                units = int(float(r["units"]))
                revenue = float(r["revenue"])
                if units <= 0 or revenue <= 0 or not r["region"].strip() or not r["product"].strip():
                    raise ValueError
                key = (r["date"], r["region"], r["product"], units, revenue)
                if key in seen:
                    raise ValueError("duplicate")
                seen.add(key)
                rows.append({"date": r["date"], "region": r["region"].strip(), "product": r["product"].strip(),
                             "units": units, "revenue": revenue})
            except (ValueError, KeyError, TypeError):
                dropped += 1
        if not rows:
            raise ValueError("sheet contains no valid rows")
        return {"rows": rows, "rows_dropped": dropped}


class PDFRetrievalAgent(Agent):
    name = "PDFRetrievalAgent"
    PATTERN = re.compile(
        r"(\d+)\.\s*\[([^\]]+)\]\s*Rating\s*(\d)/5\s*-\s*(.*?)(?=\s\d+\.\s*\[|\Z)", re.S)

    @retry(attempts=2)
    def run(self, source=None):
        path = Path(source or config.PDF_SOURCE)
        if not path.exists():
            raise FileNotFoundError(path)
        from pypdf import PdfReader
        text = " ".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
        text = re.sub(r"\s+", " ", text)
        comments = [{"city": m.group(2).strip(), "rating": int(m.group(3)), "text": m.group(4).strip()}
                    for m in self.PATTERN.finditer(text)]
        if not comments:
            raise ValueError("no comments could be parsed from the PDF")
        return {"comments": comments}


class APIRetrievalAgent(Agent):
    name = "APIRetrievalAgent"

    def run(self, url=None):
        try:
            data = json.loads(_fetch_text(url or config.API_URL, timeout=6))
            rates = data["rates"]
            return {"rates": {k: rates[k] for k in ("EGP", "EUR", "SAR")}, "source": "live API"}
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"{self.name}: API unavailable ({type(exc).__name__}); used cached rates")
            data = json.loads(config.FALLBACK_RATES.read_text())
            return {"rates": data["rates"], "source": "cached fallback"}


# ======================= ANALYSIS AGENTS =======================
class SalesAnalystAgent(Agent):
    name = "SalesAnalystAgent"

    def run(self, sheet):
        rows = sheet["rows"]
        total = sum(r["revenue"] for r in rows)
        by_region, by_product, by_month = defaultdict(float), defaultdict(float), defaultdict(float)
        for r in rows:
            by_region[r["region"]] += r["revenue"]
            by_product[r["product"]] += r["revenue"]
            by_month[r["date"][:7]] += r["revenue"]
        months = sorted(by_month)
        last, prev = by_month[months[-1]], by_month[months[-2]] if len(months) > 1 else None
        growth = round((last - prev) / prev * 100, 1) if prev else 0.0
        top_r, worst_r = max(by_region, key=by_region.get), min(by_region, key=by_region.get)
        top_p, worst_p = max(by_product, key=by_product.get), min(by_product, key=by_product.get)
        facts = {
            "total_revenue": round(total, 2), "total_units": sum(r["units"] for r in rows),
            "n_orders": len(rows), "rows_dropped": sheet["rows_dropped"],
            "by_region": {k: round(v, 2) for k, v in by_region.items()},
            "by_product": {k: round(v, 2) for k, v in by_product.items()},
            "by_month": {k: round(by_month[k], 2) for k in months},
            "top_region": top_r, "worst_region": worst_r,
            "top_region_share_pct": round(by_region[top_r] / total * 100, 1),
            "top_product": top_p, "worst_product": worst_p,
            "top_product_revenue": round(by_product[top_p], 2),
            "last_month": months[-1], "growth_last_month_pct": growth,
        }
        return {"facts": facts, "narrative": self.narrate("sales", facts)}


POSITIVE = {"great", "excellent", "fast", "love", "good", "amazing", "helpful", "perfect", "happy", "friendly", "reliable", "cheap"}
NEGATIVE = {"slow", "late", "bad", "poor", "broken", "expensive", "terrible", "rude", "damaged", "worst", "disappointed", "unresponsive", "crashes"}
TOPICS = {
    "delivery": {"delivery", "shipping", "late", "courier", "arrived"},
    "price": {"price", "expensive", "cheap", "cost", "value"},
    "quality": {"quality", "broken", "damaged", "defective", "build"},
    "support": {"support", "service", "agent", "staff", "rude", "helpful"},
    "app": {"app", "website", "checkout", "crashes", "login"},
}


class FeedbackAnalystAgent(Agent):
    name = "FeedbackAnalystAgent"

    @staticmethod
    def sentiment(c):
        words = set(re.findall(r"[a-z]+", c["text"].lower()))
        score = len(words & POSITIVE) - len(words & NEGATIVE)
        if c["rating"] >= 4 and score >= 0:
            return "positive"
        if c["rating"] <= 2 or score < 0:
            return "negative"
        return "neutral"

    def run(self, pdf):
        cs = pdf["comments"]
        n = len(cs)
        sent = Counter(self.sentiment(c) for c in cs)
        topics, neg_topics = Counter(), Counter()
        for c in cs:
            words = set(re.findall(r"[a-z]+", c["text"].lower()))
            for t, kw in TOPICS.items():
                if words & kw:
                    topics[t] += 1
                    if self.sentiment(c) == "negative":
                        neg_topics[t] += 1
        city = defaultdict(list)
        for c in cs:
            city[c["city"]].append(c["rating"])
        city_avg = {k: round(sum(v) / len(v), 2) for k, v in city.items()}
        facts = {
            "n_comments": n, "avg_rating": round(sum(c["rating"] for c in cs) / n, 2),
            "pct_positive": round(sent["positive"] / n * 100, 1),
            "pct_neutral": round(sent["neutral"] / n * 100, 1),
            "pct_negative": round(sent["negative"] / n * 100, 1),
            "topic_counts": dict(topics), "negative_topic_counts": dict(neg_topics),
            "top_topic": topics.most_common(1)[0][0] if topics else "n/a",
            "worst_topic": neg_topics.most_common(1)[0][0] if neg_topics else "n/a",
            "city_avg_rating": city_avg,
            "best_city": max(city_avg, key=city_avg.get), "worst_city": min(city_avg, key=city_avg.get),
        }
        return {"facts": facts, "narrative": self.narrate("feedback", facts)}


class MarketAnalystAgent(Agent):
    name = "MarketAnalystAgent"

    def run(self, api, sales):
        r = api["rates"]
        total = sales["facts"]["total_revenue"] if sales else 0
        facts = {
            "usd_egp": round(r["EGP"], 2), "usd_eur": round(r["EUR"], 3), "usd_sar": round(r["SAR"], 3),
            "rates_source": api["source"], "total_revenue_usd": total,
            "total_revenue_egp": round(total * r["EGP"], 0),
        }
        return {"facts": facts, "narrative": self.narrate("market", facts)}


# ======================= SYNTHESIS + QUALITY =======================
class ExecutiveSummaryAgent(Agent):
    name = "ExecutiveSummaryAgent"

    def run(self, sales, feedback, market):
        facts = {"sales": sales["facts"] if sales else None,
                 "feedback": feedback["facts"] if feedback else None,
                 "market": market["facts"] if market else None}
        return {"facts": facts, "text": self.narrate("executive", facts)}


class ValidatorAgent(Agent):
    """Fact-checks the LLM text: every non-trivial number must exist in the source facts."""
    name = "ValidatorAgent"

    def run(self, text, facts):
        issues = []
        if len(text.strip()) < 80:
            issues.append("summary is too short")
        allowed = facts_numbers(facts)
        for n in sorted(extract_numbers(text)):
            f = float(n)
            if f == int(f) and (0 <= f <= 10 or 2000 <= f <= 2100):
                continue  # small counts / years are harmless
            if n not in allowed:
                issues.append(f"number {n} does not appear in the source data")
        return {"ok": not issues, "issues": issues}
