import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PATH_RE = re.compile(r"(/[^\s]+)+")
NAME_RE = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d\-\s]{7,}\d)\b")


def mask(text: str) -> str:
    if not text:
        return text
    # Replace entire email with a generic token (no @ remains)
    t = EMAIL_RE.sub("***", text)
    t = NAME_RE.sub("*** **", t)
    t = PATH_RE.sub("/…/…", t)
    t = PHONE_RE.sub("***-***-****", t)
    return t
