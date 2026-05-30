#!/usr/bin/env python3
"""Print pipeline step status from n8n execution JSON (stdin or file path arg)."""
import json
import sys
from pathlib import Path

from n8n_exec_parse import parse_execution

# Logical steps shown in console (order matters)
PIPELINE = [
    ("trigger", "1. Trigger & setup", [
        "webhookTrigger", "webhookSetup", "manualTrigger", "autoTestOne", "autoRunNow",
    ]),
    ("gate", "2. Production gate (NewsAPI + Facebook)", [
        "productionGateNewsAPI", "productionGateMeta", "evaluateProductionApis",
        "productionGatePass", "haltProduction",
    ]),
    ("news", "3. Fetch & filter US news", [
        "prepareCategory", "fetchPoliticsNews", "fetchCelebritiesNews", "mergeNewsFeeds",
        "tagCategory", "filterArticles", "logFilterStats", "checkNeedsFallback", "fetchFallbackNews",
        "fillRemainingSlots", "passthroughNoFallback", "mergeScheduleWithArticles", "logMergeStats",
    ]),
    ("slot", "4. Posting slot & wait", [
        "splitInBatches", "prepareSlotWait", "checkHalted", "waitForSlot",
    ]),
    ("token", "5. Facebook token check", [
        "checkFBToken", "parseFBToken", "tokenGate", "skipInvalidToken",
    ]),
    ("caption", "6. AI caption (Claude → Groq → Gemini)", [
        "captionAnthropic", "captionGroq", "captionGemini",
        "extractCaptionFromApi", "extractCaptionGroq", "extractCaptionGemini",
        "checkCaptionGenerated", "gateCaptionGroq", "gateCaptionGemini",
        "prePublishAuto", "haltLlmFailed",
    ]),
    ("review", "7. Compliance review", [
        "prePublishAuto", "markCaptionReviewPassed", "reviewGate",
    ]),
    ("image", "8. Image (NewsAPI photo)", [
        "buildImagePrompt", "applyImageFallback", "mergeImagePaths", "finalPublishGate",
    ]),
    ("publish", "9. Publish to Facebook", [
        "publishToFacebook", "handlePublishSuccess", "handlePublishError",
    ]),
    ("finish", "10. Post-publish log", [
        "postPublishAudit", "parsePostPublishAudit", "appendAuditLog",
        "updatePostedURLs", "loopBack",
    ]),
]

SKIP_NODES = {
    "haltProduction", "skipInvalidToken", "skipHalted", "logSkippedCompliance",
    "logBlockedPublish", "prepareHaltEmail", "emailProductionHalted",
}

# Runtime trace tokens when n8n 2.x returns empty runData
RAW_TRACE_MARKERS = [
    ("prepareCategory: start fetch", "news", "done"),
    ("mergeNewsFeeds:", "news", "done"),
    ("filterArticles:", "news", "done"),
    ("pickFirstArticle:", "news", "done"),
    ("logMergeStats: items=", "news", "done"),
    ("prepareSlotWait: forcePostTest", "slot", "done"),
    ("parseFBToken: valid=false", "token", "failed"),
    ("SKIP_TOKEN_INVALID", "token", "skipped"),
    ("SKIP_HALTED:", "slot", "skipped"),
    ("BLOCKED_PUBLISH:", "image", "skipped"),
    ("webhookEnsurePublish:", "image", "done"),
    ("LOOP_EMPTY", "slot", "failed"),
]



def extract_run_data(root):
    run, last, exec_status, data = parse_execution(root)
    return run, last, exec_status, data


def node_status(run, node_name):
    runs = run.get(node_name)
    if not runs:
        return None
    r = runs[0] if runs else {}
    if r.get("error"):
        return "failed"
    st = r.get("executionStatus", "success")
    return st


def step_state(step_nodes, run, last_node, exec_status):
    ran = [n for n in step_nodes if n in run]
    if not ran:
        return "pending", None

    failed = [n for n in ran if node_status(run, n) == "failed" or run[n][0].get("error")]
    if failed:
        err = run[failed[0]][0].get("error")
        msg = err.get("message", str(err))[:80] if isinstance(err, dict) else str(err)[:80]
        return "failed", msg

    skipped = [n for n in ran if n in SKIP_NODES]
    if skipped:
        return "skipped", skipped[0]

    if last_node and last_node in step_nodes and exec_status in ("running", "waiting", None):
        return "processing", last_node

    if last_node in step_nodes and exec_status == "running":
        return "processing", last_node

    # All nodes in this step that ran are successful
    if all(node_status(run, n) in ("success", None) for n in ran):
        return "done", ran[-1]

    return "done", ran[-1]


def render_progress(run, last_node, exec_status, elapsed_s=None):
    icons = {
        "done": "[OK] ",
        "processing": "[>>] ",
        "pending": "[..] ",
        "failed": "[!!] ",
        "skipped": "[--] ",
    }
    lines = []
    header = "=== Pipeline progress ==="
    if elapsed_s is not None:
        header += f"  ({elapsed_s:.0f}s elapsed, execution: {exec_status or 'unknown'})"
    lines.append(header)
    lines.append("")

    current_found = False
    for key, label, nodes in PIPELINE:
        state, detail = step_state(nodes, run, last_node, exec_status)
        if state == "pending" and not current_found and run:
            # infer processing: first pending after some done
            prev_done = True
            for k2, l2, n2 in PIPELINE:
                if k2 == key:
                    break
                st2, _ = step_state(n2, run, last_node, exec_status)
                if st2 != "done" and st2 != "skipped":
                    prev_done = False
            if prev_done and exec_status in ("running", "waiting"):
                state = "processing"
                detail = last_node

        if state == "processing":
            current_found = True

        icon = icons.get(state, "[??] ")
        suffix = ""
        if state == "processing" and detail:
            suffix = f"  <- {detail}"
        elif state == "failed" and detail:
            suffix = f"  ERR: {detail}"
        elif state == "skipped" and detail:
            suffix = f"  ({detail})"
        elif state == "done" and detail:
            suffix = f"  ({detail})"

        status_word = {
            "done": "DONE",
            "processing": "IN PROGRESS",
            "pending": "PENDING",
            "failed": "FAILED",
            "skipped": "SKIPPED",
        }.get(state, state.upper())

        lines.append(f"{icon}{label:<42} {status_word}{suffix}")

    lines.append("")
    if last_node:
        lines.append(f"Last n8n node: {last_node}")
    lines.append(f"Nodes executed: {len(run)}")
    return "\n".join(lines)


def infer_from_raw(raw: str, exec_status: str | None) -> dict[str, tuple[str, str | None]]:
    """Step key -> (state, detail) from pipelineLog strings in execution blob."""
    import re

    states: dict[str, tuple[str, str | None]] = {}
    runtime = []
    for m in re.finditer(
        r'(?:BUILD=|prepareCategory|mergeNewsFeeds|filterArticles|logMergeStats|prepareSlotWait|parseFBToken|SKIP_|BLOCKED_|webhookEnsure|PUBLISH_OK|WEBHOOK_TEST)[^"\\]{8,120}',
        raw,
    ):
        t = m.group(0).replace("\\n", " ")
        if "const __sd" in t or "return [{ json" in t:
            continue
        runtime.append(t)
    blob = " | ".join(runtime)
    if not blob:
        return states

    order = ["trigger", "gate", "news", "slot", "token", "caption", "review", "image", "publish", "finish"]
    for marker, step_key, default_state in RAW_TRACE_MARKERS:
        if marker in blob:
            states[step_key] = (default_state, marker[:60])

    if re.search(r"PUBLISH_OK postId=\d{6,}", blob):
        states["publish"] = ("done", "PUBLISH_OK")
        states["finish"] = ("done", "published")
    elif exec_status == "error" and "WEBHOOK_TEST_NO_POST" in blob:
        states["finish"] = ("failed", "WEBHOOK_TEST_NO_POST")

    # Mark pending steps after last known
    if states:
        last_idx = max(order.index(k) for k in states if k in order)
        for k in order[last_idx + 1 :]:
            if k not in states:
                states[k] = ("pending", None)
    return states


def render_progress_with_raw(run, last_node, exec_status, elapsed_s=None, raw: str = ""):
    if run:
        return render_progress(run, last_node, exec_status, elapsed_s)
    inferred = infer_from_raw(raw, exec_status)
    if not inferred:
        return render_progress(run, last_node, exec_status, elapsed_s)

    icons = {"done": "[OK] ", "processing": "[>>] ", "pending": "[..] ", "failed": "[!!] ", "skipped": "[--] "}
    lines = ["=== Pipeline progress (inferred from trace — n8n runData empty) ===", ""]
    if elapsed_s is not None:
        lines[0] += f"  ({elapsed_s:.0f}s, {exec_status or 'unknown'})"
    for key, label, _nodes in PIPELINE:
        state, detail = inferred.get(key, ("pending", None))
        icon = icons.get(state, "[??] ")
        suffix = f"  ({detail})" if detail else ""
        word = state.upper() if state != "done" else "DONE"
        lines.append(f"{icon}{label:<42} {word}{suffix}")
    lines.append("")
    lines.append("Nodes executed: 0 (use trace line above — not n8n runData)")
    return "\n".join(lines)


def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ("-", "--stdin"):
        path = Path(sys.argv[1])
        root = json.loads(path.read_text(encoding="utf-8"))
        raw = path.read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
        root = json.loads(raw)

    run, last, exec_status, _ = extract_run_data(root)
    elapsed = None
    if len(sys.argv) > 2:
        try:
            elapsed = float(sys.argv[2])
        except ValueError:
            pass
    print(render_progress_with_raw(run, last, exec_status, elapsed, raw))


if __name__ == "__main__":
    main()
