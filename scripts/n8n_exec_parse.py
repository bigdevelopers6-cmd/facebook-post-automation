#!/usr/bin/env python3
"""Extract runData / lastNodeExecuted from n8n REST execution JSON (incl. n8n 2.x nesting)."""
import json
from typing import Any, Optional, Tuple


def _run_data_looks_valid(rd: dict) -> bool:
    if not rd:
        return False
    sample = next(iter(rd.values()), None)
    return isinstance(sample, list) and (not sample or isinstance(sample[0], dict))


def deep_find_run_data(obj: Any, depth: int = 0) -> Optional[Tuple[dict, Optional[str]]]:
    if depth > 25:
        return None
    if isinstance(obj, dict):
        rd = obj.get("runData")
        if isinstance(rd, dict) and _run_data_looks_valid(rd):
            return rd, obj.get("lastNodeExecuted")
        for key in ("resultData", "executionData", "data"):
            if key in obj:
                found = deep_find_run_data(obj[key], depth + 1)
                if found:
                    return found
        for v in obj.values():
            if isinstance(v, (dict, list)):
                found = deep_find_run_data(v, depth + 1)
                if found:
                    return found
    elif isinstance(obj, list):
        for item in obj[:80]:
            found = deep_find_run_data(item, depth + 1)
            if found:
                return found
    elif isinstance(obj, str) and len(obj) > 50:
        try:
            parsed = json.loads(obj)
        except json.JSONDecodeError:
            return None
        return deep_find_run_data(parsed, depth + 1)
    return None


def parse_execution(root: dict) -> Tuple[dict, Optional[str], Optional[str], dict]:
    """Return (runData, lastNodeExecuted, status, data envelope)."""
    data = root.get("data", root)
    if isinstance(data, str):
        data = json.loads(data)

    status = data.get("status") if isinstance(data, dict) else root.get("status")
    inner = data.get("data") if isinstance(data, dict) else None

    found = deep_find_run_data(data)
    if not found and inner is not None:
        found = deep_find_run_data(inner)
    if not found:
        found = deep_find_run_data(root)

    if found:
        run, last = found
        return run, last, status, data

    # Legacy flat path
    if isinstance(inner, str):
        inner = json.loads(inner)
    rd = {}
    if isinstance(inner, dict):
        rd = inner.get("resultData") or inner
    elif isinstance(data.get("resultData"), dict):
        rd = data["resultData"]
    run = rd.get("runData", {}) if isinstance(rd, dict) else {}
    last = rd.get("lastNodeExecuted") if isinstance(rd, dict) else None
    return (run if isinstance(run, dict) else {}), last, status, data


def extract_execution_error(root: dict, raw_text: str = "") -> list[str]:
    """Best-effort error messages from n8n execution payload."""
    import re

    lines: list[str] = []
    data = root.get("data", root) if isinstance(root, dict) else {}
    if isinstance(data, dict):
        err = data.get("error")
        if err:
            if isinstance(err, dict):
                lines.append(f"data.error: {err.get('message', err)}")
            else:
                lines.append(f"data.error: {err}")

    if raw_text:
        for pat in (
            r'"lastNodeExecuted"\s*:\s*"([^"]+)"',
            r'"__fatalCodeError"\s*:\s*true',
            r'"node"\s*:\s*"([^"]+)"[^}]*"message"\s*:\s*"([^"]{10,400})"',
            r'"description"\s*:\s*"([^"]{15,400})"',
            r'"message"\s*:\s*"((?:FILTER|MERGE|GATE|HALT|FATAL|NewsAPI|Error)[^"]{10,400})"',
            r'"message"\s*:\s*"([^"]*(?:articles|token|API|halt)[^"]{5,400})"',
        ):
            for m in re.finditer(pat, raw_text, re.I):
                lines.append(m.group(1) if m.lastindex == 1 else m.group(0)[:400])

        trace_block = re.search(r'"pipelineTrace"\s*:\s*\[(.*?)\]', raw_text, re.S)
        if trace_block:
            entries = re.findall(r'"([^"]{20,200})"', trace_block.group(1))
            if entries:
                lines.append("--- pipelineTrace from execution ---")
                lines.extend(entries[-15:])

        plog = re.search(r'"pipelineLog"\s*:\s*\[(.*?)\]', raw_text, re.S)
        if plog:
            entries = re.findall(r'"([^"]{15,250})"', plog.group(1))
            if entries:
                lines.append("--- pipelineLog in staticData ---")
                lines.extend(entries[-20:])

    seen = set()
    out: list[str] = []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    return out[:25]


def scan_raw_execution(raw_text: str) -> dict:
    """Mine execution JSON text when runData is missing (n8n 2.x)."""
    import re

    out: dict = {
        "last_nodes": re.findall(r'"lastNodeExecuted"\s*:\s*"([^"]+)"', raw_text),
        "errors": re.findall(r'"message"\s*:\s*"((?:[^"\\]|\\.){10,300})"', raw_text),
        "pipeline_lines": re.findall(r'\[PIPELINE\][^\n"]{10,200}', raw_text),
    }
    for name in (
        "webhookSetup", "evaluateProductionApis", "filterArticles", "mergeNewsFeeds",
        "mergeScheduleWithArticles", "prepareSlotWait", "publishToFacebook", "skipHalted",
    ):
        c = raw_text.count(f'"{name}"')
        if c:
            out.setdefault("node_hits", {})[name] = c
    return out


def format_node_list(run: dict) -> str:
    if not run:
        return "(no runData — workflow may have saved without node details)"
    lines = []
    for name, runs in sorted(run.items(), key=lambda x: x[0]):
        r = runs[0] if runs else {}
        st = r.get("executionStatus", "?")
        err = r.get("error")
        line = f"  [{st}] {name}"
        if err:
            msg = err.get("message", str(err))[:120] if isinstance(err, dict) else str(err)[:120]
            line += f"  ERR: {msg}"
        lines.append(line)
    return "\n".join(lines)
