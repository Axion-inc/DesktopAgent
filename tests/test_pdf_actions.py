from pathlib import Path
from pypdf import PdfWriter

from app.actions.pdf_actions import pdf_merge, pdf_extract_pages


def make_pdf(path: Path, pages: int = 1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=72, height=72)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        w.write(f)


def test_pdf_merge_and_extract(tmp_path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    make_pdf(a, 2)
    make_pdf(b, 3)
    out = tmp_path / "out.pdf"
    out2 = tmp_path / "out_digest.pdf"
    merged = pdf_merge([str(a), str(b)], str(out))
    assert Path(merged).exists()
    extracted = pdf_extract_pages(merged, "1,3-4", str(out2))
    assert Path(extracted).exists()

