"""ActionAgent: turns the processed result into real outputs (report, dashboard, email)."""
import html
import json
import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from . import config
from .utils import num


def md_to_html(md):
    out, in_list = [], False
    for line in md.splitlines():
        s = line.rstrip()
        if s.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(s[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if s.startswith("### "):
            out.append(f"<h3>{html.escape(s[4:])}</h3>")
        elif s.startswith("## "):
            out.append(f"<h2>{html.escape(s[3:])}</h2>")
        elif s.startswith("# "):
            out.append(f"<h1>{html.escape(s[2:])}</h1>")
        elif s:
            out.append(f"<p>{html.escape(s)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def bar_chart(title, data):
    if not data:
        return ""
    mx = max(data.values())
    rows = "".join(
        f"<div class='row'><span class='lbl'>{html.escape(str(k))}</span>"
        f"<div class='bar' style='width:{v / mx * 100:.0f}%'></div><span class='val'>{num(v)}</span></div>"
        for k, v in data.items())
    return f"<div class='card'><h3>{html.escape(title)}</h3>{rows}</div>"


CSS = """body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:30px auto;padding:0 16px;color:#1f2933}
h1{color:#0b3d91}h2{border-bottom:2px solid #dde3ec;padding-bottom:4px;margin-top:32px}
.card{background:#f5f7fb;border-radius:10px;padding:12px 16px;margin:12px 0}
.row{display:flex;align-items:center;gap:8px;margin:5px 0}.lbl{width:110px;font-size:14px}
.bar{height:16px;background:#2f6fdb;border-radius:4px}.val{font-size:13px;color:#52606d}
.warn{background:#fff4e5;border-left:4px solid #f5a623;padding:8px 12px;margin:8px 0}"""


class ActionAgent:
    name = "ActionAgent"

    def __init__(self, output_dir=None):
        self.out = Path(output_dir or config.OUTPUT_DIR)
        self.out.mkdir(parents=True, exist_ok=True)

    def run(self, executive, sales, feedback, market, meta):
        today = date.today().isoformat()
        sections = [f"# Weekly Business Intelligence Report - {today}", "## Executive Summary", executive["text"]]
        if sales:
            sections += ["## Sales Analysis", sales["narrative"]]
        if feedback:
            sections += ["## Customer Feedback Analysis", feedback["narrative"]]
        if market:
            sections += ["## Market & Currency", market["narrative"]]
        if meta["warnings"]:
            sections += ["## Warnings"] + [f"- {w}" for w in meta["warnings"]]
        sections += ["## Run Information",
                     f"- LLM backend: {meta['llm']}", f"- Total run time: {meta['seconds']} seconds",
                     f"- Fact check passed: {meta['validation_ok']}"]
        md = "\n".join(sections)
        (self.out / "report.md").write_text(md, encoding="utf-8")

        charts = ""
        if sales:
            f = sales["facts"]
            charts = (bar_chart("Revenue by region", f["by_region"]) + bar_chart("Revenue by product", f["by_product"])
                      + bar_chart("Revenue by month", f["by_month"]))
        if feedback:
            charts += bar_chart("Average rating by city", feedback["facts"]["city_avg_rating"])
        page = (f"<!doctype html><html><head><meta charset='utf-8'><title>BI Report</title><style>{CSS}</style></head>"
                f"<body>{md_to_html(md)}<h2>Dashboard</h2>{charts}</body></html>")
        (self.out / "report.html").write_text(page, encoding="utf-8")

        dashboard = {"generated": today, "sales": sales["facts"] if sales else None,
                     "feedback": feedback["facts"] if feedback else None,
                     "market": market["facts"] if market else None, "meta": meta}
        (self.out / "dashboard.json").write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")

        sent = self._email(executive["text"], today)
        return {"files": ["report.md", "report.html", "dashboard.json", "email.eml"], "email_sent": sent}

    def _email(self, summary, today):
        msg = EmailMessage()
        msg["Subject"] = f"Weekly Business Intelligence Report - {today}"
        msg["From"], msg["To"] = config.EMAIL_FROM, config.EMAIL_TO
        msg.set_content("Hello,\n\nThe AI agent system finished its analysis. Executive summary:\n\n"
                        + summary + "\n\nThe full report is attached.\n")
        msg.add_attachment((self.out / "report.html").read_bytes(), maintype="text", subtype="html",
                           filename="report.html")
        (self.out / "email.eml").write_bytes(bytes(msg))
        if not config.SMTP_HOST:
            return False
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
            s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(msg)
        return True
