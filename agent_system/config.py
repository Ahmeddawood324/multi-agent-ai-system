"""Central configuration. Everything can be overridden with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

# Source 1: Google Sheet. Either a local CSV path or a published/exported Google Sheets CSV URL, e.g.
# https://docs.google.com/spreadsheets/d/<ID>/export?format=csv
SHEET_SOURCE = os.getenv("SHEET_SOURCE", str(DATA_DIR / "sales.csv"))

# Source 2: PDF report with customer feedback.
PDF_SOURCE = os.getenv("PDF_SOURCE", str(DATA_DIR / "customer_feedback.pdf"))

# Source 3: REST API (live USD exchange rates). Falls back to data/fallback_rates.json if unreachable.
API_URL = os.getenv("API_URL", "https://open.er-api.com/v6/latest/USD")
FALLBACK_RATES = DATA_DIR / "fallback_rates.json"

# LLM. With ANTHROPIC_API_KEY set, real Claude is used; otherwise the offline MockLLM is used.
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
FORCE_MOCK = os.getenv("FORCE_MOCK", "0") == "1"

# Email action. If SMTP_HOST is not set the email is only saved as output/email.eml
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "ai-agent@example.com")
EMAIL_TO = os.getenv("EMAIL_TO", "manager@example.com")
