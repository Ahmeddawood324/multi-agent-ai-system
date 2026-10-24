"""Small helpers: retry, number formatting, number extraction (used by the validator)."""
import functools
import json
import re
import time


def retry(attempts=3, delay=0.1, no_retry=(FileNotFoundError,)):
    """Retry a function with exponential backoff. Errors in `no_retry` are raised immediately."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last = None
            for i in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except no_retry:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last = exc
                    time.sleep(delay * (2 ** i))
            raise last
        return wrapper
    return deco


def num(v):
    """Format a number the same way everywhere: 12,345.5 (no trailing zeros)."""
    s = f"{v:,.2f}".rstrip("0").rstrip(".")
    return s


_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalize_number(s):
    s = s.replace(",", "").strip(".")
    try:
        f = float(s)
    except ValueError:
        return None
    return str(int(f)) if f == int(f) else str(f)


def extract_numbers(text):
    out = set()
    for m in _NUM_RE.findall(text):
        n = normalize_number(m)
        if n is not None:
            out.add(n)
    return out


def facts_numbers(facts):
    return extract_numbers(json.dumps(facts, ensure_ascii=False))
