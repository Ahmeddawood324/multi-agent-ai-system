"""LLM backends.

* AnthropicBackend - real Claude (needs `pip install anthropic` and ANTHROPIC_API_KEY).
* MockBackend      - deterministic offline "LLM" so the whole pipeline can run/test without a key.

Agents always send the already-computed numbers as `FACTS_JSON:` and ask the LLM only to
interpret and write. Numbers are computed with code (reliable), language is written by the LLM.
"""
import json
import os
import re
import time

from . import config
from .utils import num

INSTRUCTIONS = {
    "sales": "You are a sales analyst. Using ONLY the numbers in FACTS_JSON write 4-5 short bullet points "
             "('- ...') about revenue, best/worst regions and products, and the monthly trend. Do not invent numbers.",
    "feedback": "You are a customer-experience analyst. Using ONLY the numbers in FACTS_JSON write 4-5 short "
                "bullet points ('- ...') about ratings, sentiment, main topics and pain points. Do not invent numbers.",
    "market": "You are a finance analyst. Using ONLY the numbers in FACTS_JSON write 2-3 short bullet points "
              "('- ...') about the exchange rates and the revenue converted to EGP. Do not invent numbers.",
    "executive": "You are the chief analyst. Using ONLY the numbers in FACTS_JSON write an executive summary in "
                 "Markdown: a one-sentence headline, 'Key findings' (3-5 bullets), 'Recommendations' (3 bullets), "
                 "'Risks' (1-2 bullets). Do not invent numbers. If a source is missing say so.",
}


class MockBackend:
    name = "mock"

    def __init__(self, latency=0.0):
        self.latency = latency

    def complete(self, system, prompt):
        if self.latency:
            time.sleep(self.latency)
        task = re.search(r"TASK:(\w+)", system).group(1)
        facts = json.loads(prompt.split("FACTS_JSON:", 1)[1].strip())
        return getattr(self, "_" + task)(facts)

    # ---- task writers -------------------------------------------------
    def _sales(self, f):
        trend = "grew" if f["growth_last_month_pct"] >= 0 else "fell"
        return "\n".join([
            f"- Total revenue is {num(f['total_revenue'])} from {num(f['total_units'])} units in {num(f['n_orders'])} valid orders.",
            f"- Top region is {f['top_region']} with {num(f['top_region_share_pct'])}% of revenue; weakest region is {f['worst_region']}.",
            f"- Best product is {f['top_product']} ({num(f['top_product_revenue'])} revenue); weakest product is {f['worst_product']}.",
            f"- Revenue {trend} {num(abs(f['growth_last_month_pct']))}% in the latest month ({f['last_month']}) vs the month before.",
            f"- Data quality: {num(f['rows_dropped'])} invalid or duplicate rows were removed before analysis.",
        ])

    def _feedback(self, f):
        return "\n".join([
            f"- {num(f['n_comments'])} customer comments were analysed; the average rating is {num(f['avg_rating'])} out of 5.",
            f"- Sentiment: {num(f['pct_positive'])}% positive, {num(f['pct_neutral'])}% neutral, {num(f['pct_negative'])}% negative.",
            f"- Most discussed topic is {f['top_topic']}; the topic with the most complaints is {f['worst_topic']}.",
            f"- Highest rated city is {f['best_city']}; lowest rated city is {f['worst_city']}.",
        ])

    def _market(self, f):
        return "\n".join([
            f"- 1 USD equals {num(f['usd_egp'])} EGP, {num(f['usd_eur'])} EUR and {num(f['usd_sar'])} SAR (rates source: {f['rates_source']}).",
            f"- Total revenue of {num(f['total_revenue_usd'])} USD is about {num(f['total_revenue_egp'])} EGP.",
        ])

    def _executive(self, f):
        s, c, m = f.get("sales"), f.get("feedback"), f.get("market")
        lines = []
        head = "Business performance summary."
        if s:
            head = (f"Revenue reached {num(s['total_revenue'])} with {s['top_region']} leading "
                    f"and {s['top_product']} as the best product.")
        lines += [head, "", "### Key findings"]
        if s:
            lines.append(f"- {s['top_region']} generates {num(s['top_region_share_pct'])}% of revenue; {s['worst_region']} is the weakest region.")
            trend = "up" if s["growth_last_month_pct"] >= 0 else "down"
            lines.append(f"- Revenue is {trend} {num(abs(s['growth_last_month_pct']))}% in {s['last_month']} versus the previous month.")
        else:
            lines.append("- Sales data was unavailable in this run.")
        if c:
            lines.append(f"- Customers rate us {num(c['avg_rating'])} out of 5 with {num(c['pct_negative'])}% negative comments; main pain point: {c['worst_topic']}.")
        else:
            lines.append("- Customer feedback data was unavailable in this run.")
        if m:
            lines.append(f"- At {num(m['usd_egp'])} EGP per USD the revenue equals about {num(m['total_revenue_egp'])} EGP.")
        lines += ["", "### Recommendations"]
        if s:
            lines.append(f"- Run a growth campaign in {s['worst_region']} and for {s['worst_product']}.")
        if c:
            lines.append(f"- Prioritise fixing {c['worst_topic']} issues, the biggest source of complaints.")
        lines.append("- Review pricing against currency movements every month.")
        lines += ["", "### Risks", "- Small feedback sample; treat sentiment figures as indicative.",
                  "- Exchange-rate volatility can change the EGP value of revenue."]
        return "\n".join(lines)


class AnthropicBackend:
    name = "claude"

    def __init__(self):
        import anthropic  # imported lazily so the project runs without it
        self.client = anthropic.Anthropic()

    def complete(self, system, prompt):
        task = re.search(r"TASK:(\w+)", system).group(1)
        r = self.client.messages.create(
            model=config.MODEL, max_tokens=900,
            system=INSTRUCTIONS[task],
            messages=[{"role": "user", "content": prompt}],
        )
        return r.content[0].text


def get_llm(force_mock=None):
    force_mock = config.FORCE_MOCK if force_mock is None else force_mock
    if not force_mock and os.getenv("ANTHROPIC_API_KEY"):
        try:
            return AnthropicBackend()
        except Exception as exc:  # noqa: BLE001
            print(f"[llm] could not start Claude ({exc}); using mock backend")
    return MockBackend()
