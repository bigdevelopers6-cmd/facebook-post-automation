#!/usr/bin/env python3
"""Print pipeline step status from n8n execution JSON (stdin or file path arg)."""
import json
import sys
from pathlib import Path

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
        "tagCategory", "filterArticles", "checkNeedsFallback", "fetchFallbackNews",
        "fillRemainingSlots", "passthroughNoFallback", "mergeScheduleWithArticles",
    ]),
    ("slot", "4. Posting slot & wait", [
        "splitInBatches", "prepareSlotWait", "checkHalted", "waitForSlot",
    ]),
    ("token", "5. Facebook token check", [
        "checkFBToken", "parseFBToken", "tokenGate", "skipInvalidToken",
    ]),
    ("caption", "6. AI caption (Claude → Groq → Gemini)", [
        "generateCaptionWithFallback", "checkCaptionGenerated", "prePublishReviewWithFallback",
        "checkLlmHalt", "rewriteCaptionWithFallback",
    ]),
    ("review", "7. Compliance review", [
        "reviewGate", "markCaptionReviewPassed", "captionReviewReadyGate",
        "logSkippedCompliance",
    ]),
    ("image", "8. Image (NewsAPI photo)", [
        "buildImagePrompt", "imageReview", "parseImageReview", "imageReviewGate",
        "applyImageFallback", "mergeImagePaths", "finalPublishGate", "logBlockedPublish",
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



def extract_run_data(root):
    data = root.get("data", root)
    if isinstance(data, str):
        data = json.loads(data)
    inner = data.get("data")
    if isinstance(inner, str):
        inner = json.loads(inner)
    rd = {}
    if isinstance(inner, dict):
        rd = inner.get("resultData") or inner
    elif isinstance(data.get("resultData"), dict):
        rd = data["resultData"]
    run = rd.get("runData", {}) if isinstance(rd, dict) else {}
    last = rd.get("lastNodeExecuted") if isinstance(rd, dict) else None
    status = data.get("status") if isinstance(data, dict) else root.get("status")
    exec_status = status or root.get("status")
    return run if isinstance(run, dict) else {}, last, exec_status, data


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


def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ("-", "--stdin"):
        root = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        root = json.loads(sys.stdin.read())

    run, last, exec_status, _ = extract_run_data(root)
    elapsed = None
    if len(sys.argv) > 2:
        try:
            elapsed = float(sys.argv[2])
        except ValueError:
            pass
    print(render_progress(run, last, exec_status, elapsed))


if __name__ == "__main__":
    main()
