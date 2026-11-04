# integrations — Endpoints (`CR-069`, 2026-09-03)

**31 endpoints across four edges, plus one that must never exist.** ⚠ **The confirmation table left this
row *provisional* because the design document was read only to about page 106 of ~310** — its own §2.7
lists the fourteen below marked *design §2.7* and describes the partner surface as *"not one endpoint but a
surface"*; the rest are the routes the thirty-four stories need and are marked *story*. Four of the
fourteen are already ratified law (`BR-INT-002`, A11 addendum) **and none of them exists in code** —
`apps/integrations/api.py` is one docstring line.

**Every one returns the existing error envelope** `{code, message_key, params, field_errors, br_ref,
trace_id}` — none invents a response shape (`core/errors.py`). Every refusal is ≤ 6 words (B14 rule 33)
and its `message_key` is in all eleven catalogues (`g15`). **`api.py` raises catalogue exceptions only;
`services.py` is the only write path** (Figure 16, B1).

| Edge | Where | Count | Who may call it |
|---|---|---|---|
| Connection surface | `apps/integrations/api.py` | **24** | A System Admin in the staff app (Settings). ⚠ `OQ-INT-1479` asks whether a clerk may press *Test it now* |
| Inbound door | `apps/integrations/inbound.py` | **1** (mounted at partner-declared paths) | A provider, authenticated as its operation declares |
| Partner surface | `apps/integrations/partner_api.py` | **3** | A machine credential we issued (`US-INT-040`), scoped to one tenant — ⚠ blocked `OQ-INT-1481` |
| Customer portal (conditional) | `apps/portal/api.py` | **3** | A portal session — ⚠ conditional `OQ-INT-1482` |

---

## 1 · Connection surface — 24

| # | Endpoint | Does | Refuses when | Source | Story |
|---|---|---|---|---|---|
| 1 | `GET /integrations` | The card grid: every manifest, plus this tenant's connection state **and per-operation state** for each. The consumer read-model | — | design §2.7 · **RATIFIED** (`BR-INT-002`) | US-INT-001 · 013 · 018 |
| 2 | `POST /integrations/{key}/connect` | Validate shape (`adapter.validate`), encrypt the secret, write connection + credential v1, audit with masked refs | Key unknown · **key is coming-soon** · already connected · field errors. **Zero secret persistence on refusal** | design §2.7 · **RATIFIED** | US-INT-002 · 017 · 019 |
| 3 | `POST /integrations/{key}/test` | Enqueue the adapter's `test()` — the smallest real instance — `202` + poll url; a run row with its outcome and a clerk-readable sentence | Not connected · coming-soon · the test action needs a recipient and none was typed | design §2.7 · **RATIFIED** | US-INT-015 · 016 |
| 4 | `DELETE /integrations/{key}` | Destroy every credential version, set `off`, keep every run row, audit it | Not connected | design §2.7 · **RATIFIED** | US-INT-003 · 025 |
| 5 | `PATCH /integrations/{key}` | Change non-secret config: label, environment, cadence, enabled, allowlist, budget override. Audited before/after | Coming-soon · unknown field · cadence outside `nightly · hourly · manual` · **enabling a partner-read connection (`OQ-INT-1481`)** | design §2.7 | US-INT-029 · 030 · 041 |
| 6 | `POST /integrations/{key}/credential` | Rotate: write credential v(n+1), deactivate v(n). Re-runs `test()` | Not connected · field errors | design §2.7 | US-INT-024 |
| 7 | `POST /integrations/{key}/credential/rollback` | Re-activate the previous version — one row, no re-authorisation | No previous version · previous version expired | design §2.7 | US-INT-024 |
| 8 | `POST /integrations/{key}/oauth/start` | The redirect placement: returns the provider's authorisation URL bound to a one-time state | Auth mode is not `redirect` · coming-soon | story (`BR-INT-043`) | US-INT-019 · 027 |
| 9 | `GET /integrations/oauth/callback` | The return trip: exchanges the code, writes credential v(n+1) on the **same** connection, keeps the run history | Unknown or expired state · provider error (recorded as a run) | story (`BR-INT-042`) | US-INT-027 |
| 10 | `GET /integrations/{key}/runs` | The last N runs: operation, direction, trigger, five counts, outcome, sentence, artifact link, trace id. Paginated through the existing kernel; filter by operation · outcome · trigger · direction (`inbound_read` = *who has been reading*) | — | design §2.7 | US-INT-020 · 041 · **BUILT 2026-09-04** (`apps/integrations/runs_api.py`; `q` searches the trace id ACROSS THE TENANT and each row names its own connection — decision log 2026-09-04) |
| 11 | `GET /integrations/{key}/runs/{run_id}` | One run with its per-item results, `provider_error` (scrubbed, owning tenant only) and artifact | Another tenant's run → 404 identical to absent | story (`BR-INT-039`) | US-INT-020 · **BUILT 2026-09-04** (`apps/integrations/runs_api.py`) |
| 12 | `POST /integrations/{key}/run` | Trigger a manual run of an operation. **Enqueues a job; never executes inline.** `202` + poll url | Not connected · a run already in flight · **sandbox connection handed a real batch** · budget cannot finish · breaker open | design §2.7 | US-INT-016 · 026 · 030 |
| 13 | `POST /integrations/{key}/runs/{run_id}/check` | The companion outcome query for an **indeterminate** run — *Ask the processor* — writes a new run row with the answer | Run is not indeterminate · **`OQ-INT-1476` unread** (the operation raises) | story (`BR-INT-052`) | US-INT-045 |
| 14 | `GET /integrations/{key}/mappings` | *Their words for our things*: every target-reference row for the connection's target, unmapped first | Unknown target | design §2.7 (ADDED) | US-INT-037 |
| 15 | `PUT /integrations/{key}/mappings` | Set one or more rows: their word → our value | A value that is not ours · a second meaning for one of their words (UNIQUE) · **`R02` (`OQ-INT-1487`)** | design §2.7 (ADDED) | US-INT-037 · 038 |
| 16 | `GET /integrations/{key}/differences` | The GIS queue — *Waiting for a decision*: premises, field, we hold, the city says, class, night seen | — | story (`BR-INT-051`) | US-INT-043 |
| 17 | `POST /integrations/{key}/differences/{id}/decide` | Accept (write through metering's service) or keep ours; audited | A money-path column (`inside_city_limits`, `city`, `state`) — **never**, names the column · **`OQ-INT-1470` open** (raises) | story (`BR-INT-051`) | US-INT-043 |
| 18 | `GET /integrations/{key}/lookup?q=` | An **inline** operation with a latency budget — address candidates in under a second; **writes nothing** | Breaker open (*the city's address service is not answering*) · budget exceeded → the declared empty answer, never a spinner | story (`BR-INT-048`) | US-INT-042 |
| 19 | `POST /integrations/{key}/key` | Issue or replace the key **we** give a partner. **Returned once and never again.** ⚠ **Body carries `scope` — which of this connector's operations the key may call (`CR-110-BRC04`, 2026-09-16), REQUIRED** | Not a partner-read connection · **nothing ticked** (`integrations.refusal.fields`) — ⚠ the drawing's *"leave blank for everything"* is refused under hard-won law 3 · **a name this connector does not do** (`integrations.refusal.unknown_operation`) | design §2.7 (ADDED) · `CR-110-BRC04` | US-INT-040 |
| 20 | `DELETE /integrations/{key}/key` | Revoke the issued key; the partner's very next call is refused | No key issued | story (`BR-INT-053`) | US-INT-040 |
| 21 | `GET /integrations/{key}/access` | Who has been reading from us: when, what, how many records, under which key — the `inbound_read` runs, summarised with totals | — | design §2.7 (ADDED) | US-INT-041 |
| 22 | `GET /integrations/conformance` | The conformance report, **regenerated from the registry** — each claimed standard with its claim level and evidence; never hand-maintained | — | story (`BR-INT-053`, `C7`) | US-INT-013 |
| 23 | `GET /integrations/consents` | The staff consent list (S145): customer, grantee, scope, until, state | **`OQ-INT-1482` open** (not mounted) | story (`BR-INT-036`) | US-INT-046 |
| 24 | `POST /integrations/consents/{id}/revoke` | Revoke on the customer's behalf (*the customer will ring up rather than log in*); `revoked_at`, never a delete | Already revoked · **`OQ-INT-1482`** | story (`BR-INT-036`) | US-INT-046 |

## 2 · The inbound door — 1

| # | Endpoint | Does | Refuses when | Source | Story |
|---|---|---|---|---|---|
| 25 | `POST /integrations/inbound/{key}/{operation}` ✅ **BUILT 2026-09-06 (`2.202.0`), at `POST /api/{utility}/integrations/inbound/{key}/{operation}`** — the utility is in the path for the reason wave `S` records and one more: this door WRITES, so a row landing under no tenant is somebody else's money in somebody else's book. ⚠ **AND IT STOPS AFTER `dedupe`** (`BR-INT-058`, `OQ-INT-1729` (a)): *process async through the owning module's one write path*, below, is **Runbooks' and is NOT built** — the door persists the raw envelope and applies nothing. | Shape D, phase 5. The guard pipeline in the declared order: **authenticate** (credential header · signature · allowlist, as the operation declares) → **dedupe** on the declared key → **reply** at `respond_after` with the declared status → **persist raw** → **process async** through the owning module's one write path. ⚠ **A partner that dictates its own paths (the kiosk calls three) has them declared on its operations and mounted as aliases of this one handler** — the design's `POST /integrations/webhooks/{key}` spelling is this door for a single-operation provider | Bad credential or signature · outside the allowlist (**reveals nothing**) · outside the replay window · event id already seen → the **declared** duplicate status (`409` for the kiosk, `200` for a generic webhook) and nothing written | design §2.7 (PHASE 5) · `C3` · `C6` | US-INT-044 · 023 |
| 25a | `GET /api/partner/v1/account-lookup` · `POST /api/partner/v1/add-payment` · `POST /api/partner/v1/add-return` (each also with a trailing `/`) ✅ **BUILT 2026-10-07 (`2.561.5`, `DEF-INT-10020`) — US Payments (Prime), the SAME door as row 25 at the address its operations publish.** No utility and no vendor in the path (the 2026-09-16 partner-URL rule; PO 2026-10-07, *"go - for USPayments partner API URL Fix"*): the key in the `password` header, value as issued and no `Bearer`, is looked up in `integration_key_directory` before the view runs and opens its utility; `username` is a label and is never checked. Each address is its operation's `served_path` on `manifests/pay_uspayments.py` and `partner_urls` builds the route from it, so a published operation is refused at row 25's per-utility address (logged with where it moved) — one partner, one address. The generic kiosk declares no `served_path` and stays at row 25. | Everything row 25 refuses, unchanged (live key, `enterpriseId`/`companyId` when sent, allowlist, rate limit, verb, `409` on a repeated `paymentId`), in the same words and the same padded time; another verb is DRF's `405` | PO ruling 2026-10-07 · `CR-174-BRC10` | DEF-INT-10020 |

## 3 · The partner surface — 3 (⚠ blocked `OQ-INT-1481`)

| # | Endpoint | Does | Refuses when | Source | Story |
|---|---|---|---|---|---|
| 26 | `GET /api/v1/payments` | Payments filtered by type · tender type · date range, in the **partner's declared envelope** (`{total_records, page, page_size, total_pages}`); `tenderType` and `accountString` through the mapping rows; `projectType` constant *Utility Billing*. Every page is an `inbound_read` run | Not authenticated · outside the allowlist · over the rate limit (`429` + `Retry-After`) · outside the granted scope. **An unknown account answers in the operation's declared way, which may not be 404** | design §2.7 (*the partner surface*) · §2.2.6 Figure 22 | US-INT-041 |
| 27 | `GET /api/v1/billing` | Bills, the same way | Same | design §2.7 | US-INT-041 |
| 28 | `GET /api/v1/openapi.json` | The published specification of the surface — *"described by a published specification rather than a bespoke document"* | — | design §2.7 | US-INT-041 |

## 4 · The customer portal — 3 (⚠ conditional `OQ-INT-1482`)

| # | Endpoint | Does | Refuses when | Source | Story |
|---|---|---|---|---|---|
| 29 | `GET /portal/consents` | The customer's own consents, including ended ones — *who could see my data last year* | — | story (`BR-INT-036`) | US-INT-046 |
| 30 | `POST /portal/consents` | Grant: grantee, scope (what, how much history), until | Grantee not a registered partner · scope wider than the account set | story | US-INT-046 |
| 31 | `POST /portal/consents/{id}/revoke` | Stop sharing; the grantee's very next request is refused | Already revoked | story | US-INT-046 |

---

## The endpoint that must not exist

**There is no `POST /integrations/{key}/send`, and there must never be one.** `BR-INT-008` makes the
dispatcher the only sender; a synchronous send endpoint would let a screen bypass the queue, the per-item
key and the run record all at once. *"Minting one is a build failure, not a shortcut — and it is the kind
that passes review because it looks convenient."* A gate asserts no route matching `/integrations/*/send`
exists in the shipped bundle (doc TC-INT-26); prove it RED first by mounting one (law 7).

⚠ **AMENDED 2026-10-02 — `POST /integrations/{key}/export` IS LAWFUL, AND IT IS THE ONLY ONE.** The PO, shown a
clerk sending July's journal to QuickBooks from it: *"B · Keep it and change the rule, because it only passes the
job on."* `BR-INT-008` now lets this module hand an export job to the runner; the door carries no figure and no
file. `G79` names that one route in that one file as a ruled exception; `/send` is exactly as forbidden as above.

## Why 31 and not fourteen

The design's §2.7 was written before four real specifications: it had no redirect round trip, no run
detail, no outcome query, no GIS queue, no inline lookup, no revocation route, no conformance report and
no consent at all. Each row above marked *story* is a route a story in `06-epics/` needs and names; none
is new scope. The partner surface's count (3) is the smallest that satisfies the finance partner's own
document — payments, bills, and the specification they read to build against.
