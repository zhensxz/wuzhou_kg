from __future__ import annotations

"""
Fetch 'Zizhi Tongjian' text from Chinese Wikisource and dump as "one item per paragraph".

Design goals (per course project needs):
- Keep it simple: no heavy preprocessing/NLP, just get many short "source text items".
- Separate by source: outputs go to ./sources/wikisource_zztj/...
- Avoid extra dependencies: use Python stdlib only (works well with conda base env).

Output:
  sources/wikisource_zztj/raw/資治通鑑_卷203.wikitext
  sources/wikisource_zztj/items/資治通鑑_卷203.jsonl

Each JSONL line has:
  id, source, work, volume, page_title, url, kind, text
where kind is "heading" or "paragraph".
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
WORK = "資治通鑑"


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
            # MediaWiki returns {"error": ...} on failures
            if "error" in data:
                raise RuntimeError(f"API error for {page_title}: {data['error']}")
            return (data.get("parse", {}) or {}).get("wikitext", {}).get("*", "") or ""
        except Exception as e:
            last_err = e
            # exponential backoff (cap ~20s)
            time.sleep(min(20.0, 1.6**attempt))
    raise last_err  # type: ignore[misc]


_RE_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_REF = re.compile(r"<ref\b[^>/]*?/?>.*?</ref>|<ref\b[^>]*/>", re.DOTALL | re.IGNORECASE)
_RE_TAGS = re.compile(r"</?[^>]+>")
_RE_TEMPLATES = re.compile(r"\{\{[^{}]*\}\}")


def wikitext_to_plain_lines(wikitext: str) -> list[str]:
    """
    Best-effort cleanup for Wikisource wikitext.
    We intentionally keep it shallow; downstream LLM can do the heavy lifting.
    """
    t = wikitext or ""
    t = _RE_COMMENT.sub("", t)
    t = _RE_REF.sub("", t)

    # Drop common non-content markup lines early (files, categories)
    lines = t.splitlines()
    kept: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            kept.append("")
            continue
        if s.startswith("[[Category:") or s.startswith("[[分類:"):
            continue
        if s.startswith("[[File:") or s.startswith("[[Image:") or s.startswith("[[檔案:"):
            continue
        kept.append(ln)
    t = "\n".join(kept)

    # Remove simple templates iteratively (shallow only)
    for _ in range(5):
        new_t = _RE_TEMPLATES.sub("", t)
        if new_t == t:
            break
        t = new_t

    # Replace wiki links: [[A|B]] -> B ; [[A]] -> A
    t = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\]]+)\]\]", r"\1", t)

    # Replace external links: [url label] -> label ; [url] -> url
    t = re.sub(r"\[(https?://[^\s\]]+)\s+([^\]]+)\]", r"\2", t)
    t = re.sub(r"\[(https?://[^\s\]]+)\]", r"\1", t)

    # Basic emphasis cleanup
    t = t.replace("''", "")

    # Strip any leftover HTML tags
    t = _RE_TAGS.sub("", t)

    # Normalize whitespace
    out_lines = []
    for ln in t.splitlines():
        ln = ln.replace("\u00a0", " ")
        ln = re.sub(r"[ \t]+", " ", ln).strip()
        # Drop MediaWiki "magic words" (e.g. __TOC__)
        if re.fullmatch(r"__\w+__", ln):
            continue
        ln = ln.replace("__TOC__", "").replace("__NOTOC__", "").strip()
        out_lines.append(ln)
    return out_lines


def lines_to_items(lines: list[str]) -> list[dict[str, str]]:
    """
    Convert cleaned lines to items.
    - Headings: lines like "== xxx ==" become kind=heading
    - Paragraphs: non-empty text blocks separated by blank lines
    """
    items: list[dict[str, str]] = []
    buf: list[str] = []

    def flush_paragraph() -> None:
        nonlocal buf
        text = " ".join([x for x in buf if x]).strip()
        if text:
            items.append({"kind": "paragraph", "text": text})
        buf = []

    heading_pat = re.compile(r"^=+\s*(.*?)\s*=+$")

    for ln in lines:
        if not ln:
            flush_paragraph()
            continue
        m = heading_pat.match(ln)
        if m:
            flush_paragraph()
            title = m.group(1).strip()
            if title:
                items.append({"kind": "heading", "text": title})
            continue
        # Skip table syntax lines that sometimes appear in navigation boxes
        if ln.startswith("{|") or ln.startswith("|}") or ln.startswith("|") or ln.startswith("!"):
            continue
        buf.append(ln)
    flush_paragraph()
    return items


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--volumes",
        default="203-209",
        help="Volume range, e.g. 203-209 or comma list like 203,204,208",
    )
    ap.add_argument(
        "--out-root",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sources", "wikisource_zztj"),
        help="Output root directory",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Sleep seconds between requests",
    )
    args = ap.parse_args()

    # Parse volumes
    vols: list[int] = []
    s = str(args.volumes).strip()
    if "-" in s and "," not in s:
        a, b = s.split("-", 1)
        vols = list(range(int(a), int(b) + 1))
    else:
        vols = [int(x.strip()) for x in s.split(",") if x.strip()]

    out_root = os.path.abspath(args.out_root)
    raw_dir = os.path.join(out_root, "raw")
    item_dir = os.path.join(out_root, "items")
    ensure_dir(raw_dir)
    ensure_dir(item_dir)

    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()

    total_items = 0
    for vol in vols:
        # Wikisource titles are like "資治通鑑/卷203"
        page_title = f"{WORK}/卷{vol}"
        wt = fetch_wikitext(page_title)
        if not wt.strip():
            raise SystemExit(f"Empty wikitext for {page_title}. Check page exists.")

        dump_text(os.path.join(raw_dir, f"{WORK}_卷{vol}.wikitext"), wt)

        lines = wikitext_to_plain_lines(wt)
        base_items = lines_to_items(lines)

        url = page_url(page_title)
        rows = []
        for i, it in enumerate(base_items, start=1):
            rows.append(
                {
                    "id": f"wikisource_zztj_{vol}_{i:05d}",
                    "source": "wikisource",
                    "work": WORK,
                    "volume": str(vol),
                    "page_title": page_title,
                    "url": url,
                    "kind": it["kind"],
                    "text": it["text"],
                    "fetched_at": fetched_at,
                }
            )

        dump_jsonl(os.path.join(item_dir, f"{WORK}_卷{vol}.jsonl"), rows)
        total_items += len(rows)

        time.sleep(max(0.0, float(args.sleep)))

    print(f"Done. Wrote {len(vols)} volumes, {total_items} items to: {out_root}")


if __name__ == "__main__":
    main()

