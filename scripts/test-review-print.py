#!/usr/bin/env python
"""Prove that every print-first memo actually renders A4 with 'N / M' on every page.

WHY THIS EXISTS
    scripts/review-print.css claims Edge renders CSS paged-media margin boxes. That
    claim contradicts most of what is written about Chromium, so it needs evidence,
    not a docstring -- CLAUDE.md: "A claimed safety property needs a forced failure."
    This renders the real memos through the real Edge and reads the real PDFs.

    It also runs the FORCED FAILURE: one memo is copied to a temp dir with the
    injected block stripped out, rendered, and asserted to come out UNNUMBERED. A
    check that has only ever been seen passing has not been shown to work.

WHY IT IS NOT WIRED TO CI
    Same reason as scripts/apply-review-print-css.py: public/_review/ is gitignored
    and exists only on Pip's box, and no runner has Edge on a known path. A CI job
    would find nothing and go green having checked nothing. It stays a local tool
    and says SKIP out loud when it cannot run.

USAGE
    python scripts/test-review-print.py
    (needs pypdf: python -m pip install pypdf)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows console is cp1252; a non-ASCII print dies on the FIRST print. See CLAUDE.md.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO = Path(__file__).resolve().parent.parent
REVIEW_DIR = REPO / "public" / "_review"
MM_PER_PT = 25.4 / 72.0

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_edge():
    for c in EDGE_CANDIDATES:
        if os.path.exists(c):
            return c
    return None


def render(edge, src: Path, out_pdf: Path) -> bool:
    if out_pdf.exists():
        out_pdf.unlink()
    uri = "file:///" + str(src).replace("\\", "/")
    subprocess.run(
        [edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={out_pdf}", uri],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90,
    )
    return out_pdf.exists()


def inspect(pdf: Path):
    """-> (page_count, is_a4, [pages missing their 'i / n'])"""
    from pypdf import PdfReader
    r = PdfReader(str(pdf))
    n = len(r.pages)
    box = r.pages[0].mediabox
    w, h = float(box.width) * MM_PER_PT, float(box.height) * MM_PER_PT
    a4 = abs(w - 210) < 2 and abs(h - 297) < 2
    missing = []
    for i, page in enumerate(r.pages, 1):
        text = (page.extract_text() or "").replace("\n", " ")
        if f"{i} / {n}" not in text:
            missing.append(i)
    return n, a4, missing


def main() -> int:
    try:
        import pypdf  # noqa: F401
    except ImportError:
        print("SKIP: pypdf is not installed, so the PDFs cannot be read.")
        print("      python -m pip install pypdf")
        return 0

    edge = find_edge()
    if not edge:
        print("SKIP: no Edge or Chrome found; nothing can be rendered.")
        return 0
    if not REVIEW_DIR.is_dir():
        print(f"SKIP: no {REVIEW_DIR} on this checkout (gitignored; only on Pip's box).")
        return 0

    memos = [p for p in sorted(REVIEW_DIR.glob("*.html"))
             if re.search(r"@page\s*\{", p.read_text(encoding="utf-8"))]
    if not memos:
        print(f"SKIP: {REVIEW_DIR} holds no print-first memo (none carries an @page rule).")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="review-print-test-"))
    failures = []
    try:
        for src in memos:
            pdf = tmp / (src.stem + ".pdf")
            if not render(edge, src, pdf):
                failures.append(src.name)
                print(f"FAIL {src.name:32s} Edge produced no PDF")
                continue
            n, a4, missing = inspect(pdf)
            ok = a4 and not missing
            if not ok:
                failures.append(src.name)
            print(f"{'OK  ' if ok else 'FAIL'} {src.name:32s} {n}pp  A4={a4}  "
                  f"numbered={n - len(missing)}/{n}"
                  + (f"  MISSING on {missing}" if missing else ""))

        # --- forced failure -------------------------------------------------
        # Strip the injected block from a copy and assert the numbers DISAPPEAR.
        # If they survive, this test is measuring something other than what it
        # claims to measure and every OK above is worthless.
        probe_src = memos[0]
        html = probe_src.read_text(encoding="utf-8")
        stripped = re.sub(r"/\* BEGIN review-print\.css.*?/\* END review-print\.css \*/\n?",
                          "", html, flags=re.DOTALL)
        if stripped == html:
            print("\nFAIL forced-failure probe: no injected block found in "
                  f"{probe_src.name}; run scripts/apply-review-print-css.py first.")
            failures.append("forced-failure probe")
        else:
            naked = tmp / ("naked-" + probe_src.name)
            naked.write_text(stripped, encoding="utf-8")
            npdf = tmp / "naked.pdf"
            if not render(edge, naked, npdf):
                print("\nFAIL forced-failure probe: Edge produced no PDF")
                failures.append("forced-failure probe")
            else:
                _, _, nmissing = inspect(npdf)
                if nmissing:
                    print(f"\nOK   forced-failure probe: block removed -> "
                          f"page numbers gone from pages {nmissing}, as required")
                else:
                    print("\nFAIL forced-failure probe: numbers survived the block being "
                          "removed, so this test is not measuring the block")
                    failures.append("forced-failure probe")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"FAILED: {failures}")
        return 1
    print(f"PASS: {len(memos)} print-first memo(s) render A4 with a page number on every page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
