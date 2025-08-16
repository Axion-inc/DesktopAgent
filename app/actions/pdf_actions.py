from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from pypdf import PdfReader, PdfWriter


def pdf_merge(inputs: Iterable[str], out: str) -> str:
    writer = PdfWriter()
    for src in inputs:
        reader = PdfReader(src)
        for page in reader.pages:
            writer.add_page(page)
    out_path = Path(out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)
    return str(out_path)


def pdf_extract_pages(input_path: str, pages: str, out: str) -> str:
    # pages syntax: "1,3-5" 1-based
    reader = PdfReader(input_path)
    writer = PdfWriter()
    to_extract: List[int] = []
    for part in pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) - 1
            end = int(b) - 1
            to_extract.extend(list(range(start, end + 1)))
        else:
            to_extract.append(int(part) - 1)
    for i in to_extract:
        if 0 <= i < len(reader.pages):
            writer.add_page(reader.pages[i])
    out_path = Path(out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)
    return str(out_path)

