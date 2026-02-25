from __future__ import annotations

"""
Volume-level extraction with qwen3-max deep thinking mode + async concurrency.

Features:
- Async API calls with controlled concurrency (default 4 sections in parallel)
- Streaming with enable_thinking
- Thread-safe file writing
- Resume support
"""

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
import time
from glob import glob
from typing import Any, Iterable, Optional


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def iter_jsonl(path: str) -> Iterable[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            s = (ln or "").strip()
            if not s:
                continue
            yield json.loads(s)


def norm_name(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("\u00a0", " ").replace(" ", "")
    s = s.replace("(", "（").replace(")", "）")
    return s


def load_done_section_ids(out_jsonl: str) -> set[str]:
    done: set[str] = set()
    if not os.path.exists(out_jsonl):
        return done
    with open(out_jsonl, "r", encoding="utf-8") as f:
        for ln in f:
            s = (ln or "").strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
                sid = (obj.get("section_id") or "").strip()
                if sid:
                    done.add(sid)
            except Exception:
                continue
    return done


def build_sections(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build sections by heading."""
    sections: list[dict[str, Any]] = []
    current_heading: Optional[str] = None
    current_heading_item_id: Optional[str] = None
    buf: list[dict[str, Any]] = []
    sec_idx = 0

    def flush() -> None:
        nonlocal sec_idx, current_heading, current_heading_item_id, buf
        if not buf and not current_heading:
            return
        sec_idx += 1
        joined = []
        item_ids = []
        if current_heading:
            joined.append(current_heading)
            if current_heading_item_id:
                item_ids.append(current_heading_item_id)
        for it in buf:
            item_ids.append(it.get("id", ""))
            joined.append(it.get("text", ""))
        section_text = "\n".join([t for t in joined if (t or "").strip()]).strip()
        if not section_text:
            current_heading = None
            current_heading_item_id = None
            buf = []
            return
        sections.append(
            {
                "section_id": f"sec_{sec_idx:04d}",
                "section_title": current_heading or "",
                "item_ids": item_ids,
                "text": section_text,
            }
        )
        current_heading = None
        current_heading_item_id = None
        buf = []

    for it in items:
        kind = (it.get("kind") or "").strip()
        text = (it.get("text") or "").strip()
        if not text:
            continue

        if kind == "heading":
            flush()
            current_heading = text
            current_heading_item_id = it.get("id", "")
            continue

        if kind == "paragraph":
            buf.append(it)

    flush()
    return sections


def build_messages(*, work: str, volume: str, section: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "你是一名面向知识图谱构建的史料信息抽取助手。"
        "输入是一卷史书中的一个完整小节（以小标题为单位）。"
        "请从文本中提炼出：时间、地点、人物、人物关系、人物遭遇/行动与事件，并提供可追溯证据。"
        "要求：只依据原文；不要编造；只输出严格 JSON。"
    )

    user_content = f"""从以下史料中抽取结构化信息：

【小节标题】{section.get('section_title', '')}

【小节内容】
{section.get('text', '')}

要求输出格式（严格JSON）：
{{
  "time_anchors": [{{"text": "...", "normalized": "...", "evidence": "...", "confidence": 0.9}}],
  "people": [{{"name": "...", "aliases": [...], "roles": [...], "offices": [...], "evidence": [...]}}],
  "places": [{{"name": "...", "aliases": [...], "type": "PLACE|BUILDING|REGION|OTHER", "evidence": [...]}}],
  "relations": [{{"type": "PERSON_PERSON|PERSON_OFFICE|PERSON_PLACE|PERSON_EVENT", "from": "...", "to": "...", "relation": "...", "time": "...", "place": "...", "evidence": "...", "confidence": 0.9}}],
  "events": [{{"event_name": "...", "event_type": "...", "time": "...", "place": "...", "participants": [...], "description": "...", "outcomes": [...], "evidence": [...], "confidence": 0.9}}]
}}

规则：section_title 包含关键时间信息，对相对时间要结合标题给出明确 time"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user_content}]


async def call_model_stream_async(
    *,
    client: Any,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    timeout_s: float,
    section_id: str,
    quiet: bool = False,
) -> tuple[str, Optional[dict[str, Any]], float]:
    """Async streaming call with thinking mode."""
    t0 = time.time()
    
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout_s,
        extra_body={"enable_thinking": True},
        stream=True,
    )
    
    thinking_chars = 0
    content_chars = 0
    full_content = ""
    is_answering = False
    
    async for chunk in stream:
        delta = chunk.choices[0].delta
        
        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
            thinking_chars += len(delta.reasoning_content)
        
        if hasattr(delta, "content") and delta.content:
            if not is_answering:
                is_answering = True
            content_chars += len(delta.content)
            full_content += delta.content
    
    elapsed = time.time() - t0
    
    usage = {
        "thinking_chars": thinking_chars,
        "content_chars": content_chars,
        "estimated_thinking_tokens": int(thinking_chars / 1.5),
        "estimated_content_tokens": int(content_chars / 1.5),
    }
    
    return full_content, usage, elapsed


async def process_section(
    *,
    client: Any,
    work: str,
    volume: str,
    page_title: str,
    url: str,
    section: dict[str, Any],
    idx: int,
    total: int,
    args: Any,
    write_lock: asyncio.Lock,
    out_f: Any,
) -> dict[str, Any]:
    """Process one section asynchronously."""
    sec_id = section["section_id"]
    title_preview = (section.get("section_title") or "无标题")[:30]
    
    print(f"[{idx}/{total}] {sec_id} [{title_preview}] 启动...", flush=True)
    
    messages = build_messages(work=work, volume=volume, section=section)
    
    try:
        content, usage, elapsed = await call_model_stream_async(
            client=client,
            model=args.model,
            messages=messages,
            temperature=float(args.temperature),
            timeout_s=float(args.timeout),
            section_id=sec_id,
            quiet=args.quiet,
        )
        
        content_stripped = content.strip()
        if content_stripped.startswith("```"):
            lines = content_stripped.split("\n")
            content_stripped = "\n".join(lines[1:-1]) if len(lines) > 2 else content_stripped
        
        parsed = json.loads(content_stripped) if content_stripped else {}
        extraction = parsed.get("extraction") if isinstance(parsed.get("extraction"), dict) else parsed
        
        row = {
            "work": work,
            "volume": volume,
            "page_title": page_title,
            "url": url,
            "section_id": sec_id,
            "section_title": section.get("section_title", ""),
            "item_ids": section.get("item_ids", []),
            "model": args.model,
            "usage": usage,
            "created_at": utc_now_iso(),
            "extraction": extraction,
        }
        
        async with write_lock:
            out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            out_f.flush()
        
        print(f"[{idx}/{total}] {sec_id} ✓ ({elapsed:.0f}s)", flush=True)
        return row
        
    except json.JSONDecodeError as e:
        error = f"invalid_json: {e}"
        print(f"[{idx}/{total}] {sec_id} ✗ JSON解析失败", flush=True)
    except Exception as e:
        error = f"{e.__class__.__name__}: {e}"
        print(f"[{idx}/{total}] {sec_id} ✗ {e.__class__.__name__}", flush=True)
    
    row = {
        "work": work,
        "volume": volume,
        "page_title": page_title,
        "url": url,
        "section_id": sec_id,
        "section_title": section.get("section_title", ""),
        "item_ids": section.get("item_ids", []),
        "model": args.model,
        "usage": None,
        "created_at": utc_now_iso(),
        "extraction": {},
        "error": error,
    }
    
    async with write_lock:
        out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
        out_f.flush()
    
    return row


def merge_volume(*, meta: dict[str, Any], section_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge section-level JSON into consolidated volume JSON."""
    people: dict[str, dict[str, Any]] = {}
    places: dict[str, dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    time_anchors: list[dict[str, Any]] = []

    def upsert_entity(store: dict[str, dict[str, Any]], obj: dict[str, Any], *, key_field: str = "name") -> None:
        name = norm_name(str(obj.get(key_field, "") or ""))
        if not name:
            return
        cur = store.get(name)
        if cur is None:
            store[name] = obj
            store[name][key_field] = name
            if isinstance(store[name].get("aliases"), list):
                store[name]["aliases"] = list({norm_name(x) for x in store[name]["aliases"] if x and norm_name(x)})
            return
        for lf in ["aliases", "roles", "offices", "evidence"]:
            if lf in obj and isinstance(obj.get(lf), list):
                a = cur.get(lf, [])
                if not isinstance(a, list):
                    a = []
                merged = list({*(a), *(obj.get(lf) or [])})
                cur[lf] = merged

    for row in section_rows:
        sec = row.get("extraction") or {}
        if isinstance(sec.get("time_anchors"), list):
            time_anchors.extend(sec["time_anchors"])
        if isinstance(sec.get("people"), list):
            for p in sec["people"]:
                if isinstance(p, dict):
                    upsert_entity(people, p, key_field="name")
        if isinstance(sec.get("places"), list):
            for pl in sec["places"]:
                if isinstance(pl, dict):
                    upsert_entity(places, pl, key_field="name")
        if isinstance(sec.get("relations"), list):
            relations.extend([r for r in sec["relations"] if isinstance(r, dict)])
        if isinstance(sec.get("events"), list):
            events.extend([e for e in sec["events"] if isinstance(e, dict)])

    rel_seen: set[str] = set()
    rel_out: list[dict[str, Any]] = []
    for r in relations:
        key = "|".join(
            [
                str(r.get("type", "")),
                norm_name(str(r.get("from", ""))),
                norm_name(str(r.get("to", ""))),
                str(r.get("relation", "")),
                str(r.get("evidence", "")),
            ]
        )
        if key in rel_seen:
            continue
        rel_seen.add(key)
        r["from"] = norm_name(str(r.get("from", "")))
        r["to"] = norm_name(str(r.get("to", "")))
        rel_out.append(r)

    evt_seen: set[str] = set()
    evt_out: list[dict[str, Any]] = []
    for e in events:
        ev0 = ""
        if isinstance(e.get("evidence"), list) and e["evidence"]:
            ev0 = str(e["evidence"][0])
        key = "|".join([str(e.get("event_name", "")), str(e.get("time", "")), str(e.get("place", "")), ev0])
        if key in evt_seen:
            continue
        evt_seen.add(key)
        if isinstance(e.get("participants"), list):
            e["participants"] = [norm_name(x) for x in e["participants"] if x and norm_name(x)]
        evt_out.append(e)

    return {
        "work": meta.get("work", ""),
        "volume": meta.get("volume", ""),
        "page_title": meta.get("page_title", ""),
        "url": meta.get("url", ""),
        "generated_at": utc_now_iso(),
        "time_anchors": time_anchors,
        "people": list(people.values()),
        "places": list(places.values()),
        "relations": rel_out,
        "events": evt_out,
        "sections": [
            {
                "section_id": row.get("section_id", ""),
                "section_title": row.get("section_title", ""),
                "item_ids": row.get("item_ids", []),
            }
            for row in section_rows
        ],
    }


async def process_one_volume(*, input_path: str, client: Any, args: Any) -> None:
    """Process one volume file asynchronously."""
    items = list(iter_jsonl(input_path))
    if not items:
        print(f"[skip] {input_path}: empty file")
        return

    meta0 = items[0]
    work = (meta0.get("work") or "UNKNOWN").strip() or "UNKNOWN"
    volume = (meta0.get("volume") or "UNKNOWN").strip() or "UNKNOWN"
    page_title = meta0.get("page_title", "")
    url = meta0.get("url", "")

    sections = build_sections(items)
    if not sections:
        print(f"[skip] {work} 卷{volume}: no sections")
        return

    out_root = os.path.abspath(args.out_root)
    out_dir = os.path.join(out_root, work)
    ensure_dir(out_dir)
    out_sections_path = os.path.join(out_dir, f"{work}_卷{volume}.sections.extractions.jsonl")
    out_volume_path = os.path.join(out_dir, f"{work}_卷{volume}.volume.json")

    done_sec = load_done_section_ids(out_sections_path) if args.resume else set()
    
    # Filter out already done sections
    pending_sections = [(i+1, sec) for i, sec in enumerate(sections) if sec["section_id"] not in done_sec]
    
    if args.max_sections:
        pending_sections = pending_sections[:int(args.max_sections)]
    
    if not pending_sections:
        print(f"\n[vol] {work} 卷{volume}: all sections already done, skipping\n")
        return

    print(f"\n{'='*60}")
    print(f"[vol] {work} 卷{volume}: {len(sections)} sections total, {len(done_sec)} done, {len(pending_sections)} pending")
    print(f"{'='*60}")

    extracted_rows: list[dict[str, Any]] = []
    
    # Load existing rows if resuming
    if args.resume and os.path.exists(out_sections_path):
        for r in iter_jsonl(out_sections_path):
            extracted_rows.append(r)

    # Semaphore to control concurrency
    sem = asyncio.Semaphore(int(args.concurrency))
    write_lock = asyncio.Lock()
    
    async def process_with_semaphore(idx: int, sec: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            with open(out_sections_path, "a", encoding="utf-8") as out_f:
                result = await process_section(
                    client=client,
                    work=work,
                    volume=volume,
                    page_title=page_title,
                    url=url,
                    section=sec,
                    idx=idx,
                    total=len(sections),
                    args=args,
                    write_lock=write_lock,
                    out_f=out_f,
                )
                await asyncio.sleep(float(args.sleep))
                return result
    
    # Process all pending sections concurrently
    tasks = [process_with_semaphore(idx, sec) for idx, sec in pending_sections]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for r in results:
        if isinstance(r, dict):
            extracted_rows.append(r)
        elif isinstance(r, Exception):
            print(f"[error] Task failed: {r}")

    merged = merge_volume(
        meta={"work": work, "volume": volume, "page_title": page_title, "url": url},
        section_rows=[r for r in extracted_rows if not r.get("error")],
    )
    with open(out_volume_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n[vol] ✓ {work} 卷{volume}: {len(merged['people'])} people, {len(merged['events'])} events, {len(merged['relations'])} relations")
    print(f"[vol] wrote: {out_volume_path}\n")


async def main_async(args: Any, client: Any, input_files: list[str]) -> None:
    """Main async coordinator."""
    volumes_processed = 0
    for in_path in input_files:
        try:
            await process_one_volume(input_path=in_path, client=client, args=args)
            volumes_processed += 1
            if args.max_volumes and volumes_processed >= int(args.max_volumes):
                break
        except KeyboardInterrupt:
            print("\n\n[interrupted] Stopping...")
            break
        except Exception as e:
            print(f"\n[error] {in_path}: {e.__class__.__name__}: {e}")
            continue

    print(f"\n{'='*60}")
    print(f"All done! Processed {volumes_processed} volumes")
    print(f"{'='*60}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="sources/**/items/*.jsonl", help="Input glob pattern")
    ap.add_argument(
        "--out-root",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "llm_outputs", "qwen3_thinking_async"),
        help="Output root directory",
    )
    ap.add_argument("--model", default="qwen3-max", help="Model name")
    ap.add_argument(
        "--base-url",
        default=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        help="DashScope base_url",
    )
    ap.add_argument("--api-key", default=os.getenv("DASHSCOPE_API_KEY", ""), help="DashScope API key")
    ap.add_argument("--concurrency", type=int, default=4, help="Max concurrent sections (default 4)")
    ap.add_argument("--max-sections", type=int, default=0, help="Process at most N sections per volume (0=all)")
    ap.add_argument("--max-volumes", type=int, default=0, help="Process at most N volumes (0=all)")
    ap.add_argument("--sleep", type=float, default=0.5, help="Sleep seconds after each section completes")
    ap.add_argument("--temperature", type=float, default=0.05, help="Temperature")
    ap.add_argument("--timeout", type=float, default=600.0, help="Per-section timeout seconds")
    ap.add_argument("--resume", action="store_true", help="Resume: skip already extracted sections")
    ap.add_argument("--quiet", action="store_true", help="Disable verbose output")
    args = ap.parse_args()

    input_files = sorted(glob(args.inputs, recursive=True))
    if not input_files:
        raise SystemExit(f"No input files matched: {args.inputs}")

    if not args.api_key:
        raise SystemExit("Missing API key. Set env DASHSCOPE_API_KEY or pass --api-key.")

    from openai import AsyncOpenAI  # type: ignore

    client = AsyncOpenAI(api_key=args.api_key, base_url=args.base_url)

    print(f"\n{'='*60}")
    print(f"Async Deep Thinking Extraction (qwen3-max)")
    print(f"Concurrency: {args.concurrency} sections in parallel")
    print(f"Input files: {len(input_files)}")
    print(f"Timeout: {args.timeout}s per section")
    print(f"Output: {args.out_root}")
    print(f"{'='*60}\n")

    asyncio.run(main_async(args, client, input_files))


if __name__ == "__main__":
    main()
