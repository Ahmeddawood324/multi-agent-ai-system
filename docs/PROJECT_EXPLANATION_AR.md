# شرح المشروع بالعربي

## المطلوب في المشروع باختصار
المطلوب إنك تبني **نظام AI Agents** بيعمل شغل متعدد الخطوات لوحده (مش مجرد سؤال وجواب زي الـ Midterm).
يعني عدة "وكلاء" (Agents) كل واحد له وظيفة، وفي منسّق (Orchestrator) بينسّق بينهم.

| # | الهدف | معناه ببساطة | اتنفذ فين في مشروعنا |
|---|---|---|---|
| 1 | Data Retrieval | تجيب بيانات من مصادر مختلفة (PDF / Google Sheets / API / قاعدة بيانات) | 3 agents: Sheet و PDF و API |
| 2 | Processing & Summarization | تستخدم LLM يحلل ويلخّص البيانات | Analysts + Executive Summary |
| 3 | Automated Actions | النظام يعمل حاجة لوحده: إيميل / تقرير / تحديث Dashboard | ActionAgent (تقرير HTML + dashboard.json + إيميل) |
| 4 | Workflow Orchestration | تنسيق الخطوات بالترتيب أو بالتوازي بنتايج منطقية | `orchestrator.py` |
| 5 | Presentation | توثيق + فيديو بوجهك بتشرح فيه الشغل والمعمارية | `docs/VIDEO_SCRIPT.md` + `ARCHITECTURE.md` |
| 6 | Testing & Evaluation | تقيّم الدقة والاعتمادية والسرعة | `tests/` + `evaluate.py` |

## فكرة مشروعنا
نظام **تقرير ذكاء أعمال أسبوعي** بيعمل التالي لوحده:
1. يقرا المبيعات من Sheet (CSV أو Google Sheets) وينضّفها (يشيل الصفوف المكررة والفاضية والغلط).
2. يقرا آراء العملاء من PDF.
3. يجيب أسعار العملات من API.
4. يحلل كل مصدر (agents بتشتغل بالتوازي)، وبعدين agent بيكتب ملخص تنفيذي.
5. Agent مراجع (Validator) يتأكد إن كل رقم في الملخص موجود فعلاً في البيانات (يمنع الهلوسة).
6. يطلّع تقرير HTML فيه رسومات + ملف dashboard + إيميل جاهز للإرسال.

## أهم فكرة تقولها في الفيديو
"الأرقام بتتحسب بالكود، والـ LLM بس بيشرحها ويكتبها، وبعدين Validator بيراجعها" ← ده بيخلي النتيجة دقيقة.

## إزاي تشغّله
```bash
pip install -r requirements.txt
python run.py --mock        # من غير API key (تجربة أوفلاين)
```
افتح `output/report.html` في المتصفح.

لو عايز Claude حقيقي: اعمل `ANTHROPIC_API_KEY` وشغّل `python run.py`.
لو عايز بياناتك: غيّر `SHEET_SOURCE` و `PDF_SOURCE` (التفاصيل في README.md).

## خطوات التسليم
1. شغّل `python run.py` و `python -m pytest -q` و `python evaluate.py` وتأكد إنهم شغالين عندك.
2. سجّل الفيديو بالكاميرا (اتبع `docs/VIDEO_SCRIPT.md`) — لازم وشك يظهر.
3. سلّم الـ ZIP + لينك الفيديو.

## تنبيه مهم
شوف المطلوب من الدكتور: لو عايز مصدر بيانات معين (Google Sheet حقيقي مثلاً) أو أداة معينة (n8n / LangChain)،
قوللي وأعدّل المشروع عليها.
