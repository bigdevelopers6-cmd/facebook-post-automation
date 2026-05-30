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


_PUBLISH_OK_RE = r"PUBLISH_OK postId=[0-9]{8,}(?:_[0-9]+)?"


def read_pipeline_log(path: str = "data/reports/pipeline.log") -> str:
    from pathlib import Path

    p = Path(path)
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


def extract_publish_post_id(text: str) -> str | None:
    import re

    m = re.search(_PUBLISH_OK_RE, text)
    return m.group(0).split("=", 1)[1] if m else None


def runtime_publish_ok(raw_text: str = "", *, log_path: str = "data/reports/pipeline.log") -> bool:
    """True when pipeline.log or execution trace has a real PUBLISH_OK postId."""
    import re

    combined = (read_pipeline_log(log_path) or "") + "\n" + (raw_text or "")
    return bool(re.search(_PUBLISH_OK_RE, combined))


def runtime_publish_failed(raw_text: str = "", *, log_path: str = "data/reports/pipeline.log") -> bool:
    """True only when trace shows publish failed and no successful post id."""
    if runtime_publish_ok(raw_text, log_path=log_path):
        return False
    log = read_pipeline_log(log_path)
    if "PUBLISH_FAIL:" in log and "PUBLISH_OK postId=" not in log:
        return True
    return "PUBLISH_FAIL:" in (raw_text or "") and not runtime_publish_ok(raw_text, log_path=log_path)


def deep_find_key(obj: Any, key: str, depth: int = 0) -> list[Any]:
    """Collect all values for a key nested in execution JSON."""
    if depth > 30:
        return []
    found: list[Any] = []
    if isinstance(obj, dict):
        if key in obj:
            found.append(obj[key])
        for v in obj.values():
            found.extend(deep_find_key(v, key, depth + 1))
    elif isinstance(obj, list):
        for item in obj[:100]:
            found.extend(deep_find_key(item, key, depth + 1))
    elif isinstance(obj, str) and len(obj) > 80:
        try:
            found.extend(deep_find_key(json.loads(obj), key, depth + 1))
        except json.JSONDecodeError:
            pass
    return found


def extract_execution_error(root: dict, raw_text: str = "") -> list[str]:
    """Best-effort error messages from n8n execution payload."""
    import re

    lines: list[str] = []
    data = root.get("data", root) if isinstance(root, dict) else {}
    if isinstance(data, dict):
        err = data.get("error")
        if err:
            if isinstance(err, dict):
                msg = err.get("message", err)
                lines.append(f"data.error: {msg}")
                if "WEBHOOK_TEST_NO_POST" in str(msg):
                    lines.append("--- webhook failure (actionable) ---")
                    if "Trace:" in str(msg):
                        lines.append(str(msg).split("Trace:", 1)[-1].strip()[:1200])
            else:
                lines.append(f"data.error: {err}")

    for msg in deep_find_key(root, "message"):
        text = str(msg)
        if "WEBHOOK_TEST_NO_POST" in text and text not in lines:
            lines.append(f"nested error.message: {text[:1500]}")

    if raw_text:
        compact = raw_text.replace("\\n", " ")
        wh = re.search(r'WEBHOOK_TEST_NO_POST_[A-Z_]+ Trace=[^"\\]{20,800}', compact)
        if wh:
            lines.append("runtime: " + wh.group(0)[:1200])
        elif "WEBHOOK_TEST_NO_POST_" in compact and "+ hint +" not in compact:
            wh2 = re.search(r'WEBHOOK_TEST_NO_POST_[A-Z_]+[^"\\]{0,400}', compact)
            if wh2:
                lines.append("runtime: " + wh2.group(0)[:800])
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
            runtime = [
                e for e in entries
                if "const __sd" not in e
                and "prepareCategory\\" not in e
                and "return [{ json" not in e
                and len(e) < 220
            ]
            if runtime:
                lines.append("--- pipelineLog (runtime) ---")
                lines.extend(runtime[-20:])
            elif entries:
                lines.append("--- pipelineLog (may include workflow definition noise) ---")
                lines.extend(entries[-8:])

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
        "assertWebhookPost", "PUBLISH_OK", "WEBHOOK_TEST_NO_POST",
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
