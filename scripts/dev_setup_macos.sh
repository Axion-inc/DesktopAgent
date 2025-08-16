#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path
from pypdf import PdfWriter

root = Path('sample_data')
root.mkdir(parents=True, exist_ok=True)
for i in range(1, 11):
    p = root / f'sample_{i:02d}.pdf'
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(p, 'wb') as f:
        w.write(f)
print('Generated sample PDFs in', root)
PY

echo "Done."

