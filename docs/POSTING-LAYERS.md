# Mandatory Posting Layers & Cost Guard

## Production Cost Guard

Runs at the **start of every daily run** and every **`/auto run-now`** / **`/auto test-one`**:

| Node | Checks |
|------|--------|
| `productionGateNewsAPI` | NewsAPI key valid |
| `productionGateAnthropic` | Anthropic key valid |
| `productionGateOpenAI` | OpenAI key valid |
| `productionGateMeta` | Facebook token valid (`debug_token`) |
| `evaluateProductionApis` | All four must pass |
| `productionGatePass` | If false → `haltProduction` → `alertStopServer` |

**Static data flags:** `productionHalted`, `apisHealthy`, `lastApiGateFailures`

**Your action when halted:** `docker compose down` (see `scripts/stop-server.sh`)

## Per-slot API checks (before spending)

| Node | When |
|------|------|
| `slotApiGateAnthropic` | Before `generateCaption` |
| `slotApiGateOpenAI` | Before `generateImage` (skipped on image fallback path) |

Failure sets `productionHalted` and triggers the same halt path.

## Mandatory AI review (no bypass)

| Layer | Node | Blocks publish if |
|-------|------|-------------------|
| Caption compliance | `prePublishReview` + `reviewGate` | Not approved or risk=high |
| Caption clearance flag | `markCaptionReviewPassed` + `captionReviewReadyGate` | `aiCaptionApproved` false |
| Image prompt compliance | `imageReview` + `imageReviewGate` | Uses fallback only if rejected |
| Final gate | `finalPublishGate` | Any required field missing |

`publishToFacebook` is **only** wired from `finalPublishGate` (true branch).

## Reset after fixing keys

Manual command: **`reset-errors`** — clears `productionHalted`, `circuitBreakerHalted`, and `errorLog`.
