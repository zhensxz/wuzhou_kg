from __future__ import annotations

"""
Fetch 'Xin Tang Shu' (新唐書) from Chinese Wikisource.

Principles (per user requirement):
- Separate by source: outputs go to ./sources/wikisource_xintangshu/...
- Keep raw text intact: store original wikitext per volume.
- Avoid complex preprocessing: only minimal normalization (trim whitespace, drop magic words).

Output:
  sources/wikisource_xintangshu/raw/新唐書_卷001.wikitext
  sources/wikisource_xintangshu/items/新唐書_卷001.jsonl

Each JSONL line:
  id, source, work, volume, page_title, url, kind, text, fetched_at
where kind is "heading" or "paragraph".

Note:
- On Chinese Wikisource, Xin Tang Shu volume pages are titled like "新唐書/卷001" (3-digit padding).
"""

import argparse
import datetime as dt
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Iterable, Optional


WIKISOURCE_API = "https://zh.wikisource.org/w/api.php"
WORK = "新唐書"


def http_get_json(url: str, params: dict[str, str], timeout_s: int = 60) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    full = f"{url}?{query}"
    req = urllib.request.Request(
        full,
        headers={
            "User-Agent": "WuZhouKG-data-acq/0.1 (educational; contact: local)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def fetch_wikitext(page_title: str, max_retries: int = 6) -> str:
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            data = http_get_json(
                WIKISOURCE_API,
                {
                    "action": "parse",
                    "format": "json",
                    "page": page_title,
                    "prop": "wikitext",
                    "redirects": "1",
                },
            )
            if "error" in data:
                raise RuntimeError(f"API error for {page_title}: {data['error']}")
            return (data.get("parse", {}) or {}).get("wikitext", {}).get("*", "") or ""
        except Exception as e:
            last_err = e
            time.sleep(min(20.0, 1.6**attempt))
    raise last_err  # type: ignore[misc]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def dump_text(path: str, text: str) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def dump_jsonl(path: str, rows: Iterable[dict[str, Any]]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def page_url(page_title: str) -> str:
    return "https://zh.wikisource.org/wiki/" + urllib.parse.quote(page_title, safe="")


def minimal_lines(wikitext: str) -> list[str]:
    """
    Minimal normalization:
    - strip line whitespace
    - drop MediaWiki magic words (e.g. __TOC__)
    - keep everything else (templates/links/tables)
    """
    out: list[str] = []
    for ln in (wikitext or "").splitlines():
        s = ln.replace("\u00a0", " ").rstrip()
        s = s.strip()
        if not s:
            out.append("")
            continue
        # magic words
        if re.fullmatch(r"__\w+__", s):
            continue
        s = s.replace("__TOC__", "").replace("__NOTOC__", "").strip()
        if not s:
            continue
        # drop categories/files (non-content metadata)
        if s.startswith("[[Category:") or s.startswith("[[分類:"):
            continue
        if s.startswith("[[File:") or s.startswith("[[Image:") or s.startswith("[[檔案:"):
            continue
        out.append(s)
    return out


def lines_to_items(lines: list[str]) -> list[dict[str, str]]:
    """
    Convert lines into items.
    - Headings: MediaWiki headings (=...=) and possible markdown headings (# ...)
    - Paragraphs: text blocks separated by blank lines
    """
    items: list[dict[str, str]] = []
    buf: list[str] = []

    def flush_paragraph() -> None:
        nonlocal buf
        text = "\n".join([x for x in buf if x]).strip()
        if text:
            items.append({"kind": "paragraph", "text": text})
        buf = []

    mw_heading = re.compile(r"^=+\s*(.*?)\s*=+$")
    md_heading = re.compile(r"^#{1,6}\s*(.+?)\s*$")

    for ln in lines:
        if not ln:
            flush_paragraph()
            continue
        m = mw_heading.match(ln)
        if m:
            flush_paragraph()
            title = m.group(1).strip()
            if title:
                items.append({"kind": "heading", "text": title})
            continue
        m2 = md_heading.match(ln)
        if m2:
            flush_paragraph()
            title = m2.group(1).strip()
            if title:
                items.append({"kind": "heading", "text": title})
            continue
        buf.append(ln)

    flush_paragraph()
    return items


def parse_volumes(spec: str) -> list[int]:
    s = (spec or "").strip()
    if not s:
        return []
    if "-" in s and "," not in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--volumes", default="1-10", help="Volume range, e.g. 1-10 or comma list like 1,2,3")
    ap.add_argument(
        "--out-root",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sources",
            "wikisource_xintangshu",
        ),
        help="Output root directory",
    )
    ap.add_argument("--sleep", type=float, default=0.5, help="Sleep seconds between requests")
    args = ap.parse_args()

    vols = parse_volumes(args.volumes)
    if not vols:
        raise SystemExit("No volumes specified.")

    out_root = os.path.abspath(args.out_root)
    raw_dir = os.path.join(out_root, "raw")
    item_dir = os.path.join(out_root, "items")
    ensure_dir(raw_dir)
    ensure_dir(item_dir)

    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()

    total_items = 0
    for vol in vols:
        page_title = f"{WORK}/卷{vol:03d}"
        wt = fetch_wikitext(page_title)
        if not wt.strip():
            raise SystemExit(f"Empty wikitext for {page_title}. Check page exists.")

        dump_text(os.path.join(raw_dir, f"{WORK}_卷{vol:03d}.wikitext"), wt)

        lines = minimal_lines(wt)
        base_items = lines_to_items(lines)

        url = page_url(page_title)
        rows = []
        for i, it in enumerate(base_items, start=1):
            rows.append(
                {
                    "id": f"wikisource_xintangshu_{vol:03d}_{i:05d}",
                    "source": "wikisource",
                    "work": WORK,
                    "volume": f"{vol:03d}",
                    "page_title": page_title,
                    "url": url,
                    "kind": it["kind"],
                    "text": it["text"],
                    "fetched_at": fetched_at,
                }
            )

        dump_jsonl(os.path.join(item_dir, f"{WORK}_卷{vol:03d}.jsonl"), rows)
        total_items += len(rows)
        time.sleep(max(0.0, float(args.sleep)))

    print(f"Done. Wrote {len(vols)} volumes, {total_items} items to: {out_root}")


if __name__ == "__main__":
    main()

