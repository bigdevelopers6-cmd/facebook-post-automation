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
