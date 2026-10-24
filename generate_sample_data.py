"""Creates the demo data: data/sales.csv, data/customer_feedback.pdf, data/fallback_rates.json.
Run once:  python generate_sample_data.py   (needs reportlab)"""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)
random.seed(42)

# ---------- sales.csv (this is what you would normally keep in a Google Sheet) ----------
regions = {"Cairo": 1.5, "Alexandria": 1.0, "Giza": 0.9, "Delta": 0.6}
products = {"Laptop": 900, "Phone": 500, "Tablet": 350, "Headset": 80}
rows = []
d0 = date(2026, 7, 1)
for i in range(150):
    d = d0 + timedelta(days=random.randint(0, 91))
    region = random.choices(list(regions), weights=regions.values())[0]
    product = random.choice(list(products))
    units = random.randint(1, 6)
    rows.append([d.isoformat(), region, product, units, units * products[product]])
rows.append(rows[3][:])                          # exact duplicate -> must be removed
rows.append(["2026-08-10", "Cairo", "Phone", "", ""])    # missing values -> must be removed
rows.append(["2026-08-11", "Giza", "Laptop", -2, -1800])  # negative -> must be removed
with open(DATA / "sales.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "region", "product", "units", "revenue"])
    w.writerows(rows)

# ---------- customer_feedback.pdf ----------
comments = [
    ("Cairo", 5, "Great product and the delivery was fast. Excellent quality."),
    ("Cairo", 4, "Good value for the price, very happy with the laptop."),
    ("Cairo", 2, "The delivery was late and the courier was rude."),
    ("Alexandria", 5, "Amazing support, the agent was friendly and helpful."),
    ("Alexandria", 3, "The price is fine but nothing special about the quality."),
    ("Alexandria", 1, "Package arrived damaged and support was unresponsive."),
    ("Giza", 4, "Fast shipping and reliable service. Love the headset."),
    ("Giza", 2, "The app crashes during checkout, really disappointed."),
    ("Giza", 5, "Perfect quality, will order again."),
    ("Delta", 1, "Terrible delivery experience, very slow and late."),
    ("Delta", 2, "Too expensive for what you get, poor build quality."),
    ("Delta", 3, "Okay product, the website is easy to use."),
    ("Cairo", 5, "Helpful staff and a great price on the phone."),
    ("Alexandria", 4, "Good quality and the checkout in the app was easy."),
    ("Giza", 1, "Worst support ever, nobody answered. Broken screen on arrival."),
    ("Delta", 4, "Friendly agent and fast delivery to my city."),
    ("Cairo", 3, "Average experience, delivery took a while but arrived."),
    ("Alexandria", 2, "Bad app, login fails and support is slow."),
    ("Giza", 5, "Excellent value, cheap but reliable."),
    ("Delta", 2, "Late delivery again, disappointed with the courier."),
]
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(DATA / "customer_feedback.pdf"), pagesize=A4)
    y = 800
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Customer Feedback Report - Q3 2026")
    y -= 30
    c.setFont("Helvetica", 9)
    for i, (city, rating, text) in enumerate(comments, 1):
        c.drawString(40, y, f"{i}. [{city}] Rating {rating}/5 - {text}")
        y -= 18
    c.save()
except ImportError:
    print("reportlab not installed: customer_feedback.pdf was not regenerated")

(DATA / "fallback_rates.json").write_text(json.dumps({"rates": {"EGP": 48.5, "EUR": 0.86, "SAR": 3.75}}))
print("sample data written to", DATA)
