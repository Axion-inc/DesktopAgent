from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional


def find_files(query: str, roots: List[str], limit: int = 100) -> List[str]:
    # Minimal: ignore query expression and just collect PDFs if specified
    exts = None
    if "kind:pdf" in query:
        exts = {".pdf"}
    results: List[str] = []
    for root in roots:
        p = Path(root).expanduser()
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.is_file():
                if exts is None or f.suffix.lower() in exts:
                    results.append(str(f))
                    if len(results) >= limit:
                        return results
    return results


def rename(files: List[str], rule: str) -> List[str]:
    # Caller provides mapping context with {date},{index},{basename}
    # Here, just compute new basenames; actual renaming happens in runner for safety
    return files


def move_to(files: List[str], dest: str, newnames: Optional[List[str]] = None) -> List[str]:
    out = []
    d = Path(dest).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    for idx, src in enumerate(files):
        s = Path(src)
        base = s.name
        if newnames and idx < len(newnames) and newnames[idx]:
            base = newnames[idx]
        target = d / base
        i = 1
        while target.exists():
            target = d / f"{s.stem}_{i}{s.suffix}"
            i += 1
        shutil.copy2(s, target)
        out.append(str(target))
    return out


def zip_folder(folder: str, out_zip: str) -> str:
    base = Path(out_zip).expanduser()
    base.parent.mkdir(parents=True, exist_ok=True)
    shutil.make_archive(str(base.with_suffix("")), "zip", folder)
    if base.suffix != ".zip":
        base = base.with_suffix(".zip")
    return str(base)
