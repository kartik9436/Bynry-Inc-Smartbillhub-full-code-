# integrations — User Stories (INDEX)
> Pack authored 2026-08-09 against the ratified rule set (BR-INT-001..016 — consolidated BY CITATION from B7 + addendum, A1/A11/A15 addenda, OQ-015/073/074 closures, BR-LED-004/014/020, BR-PAY-019/023/028, BR-NOT-005, NFR-13/20/21/27, TD-8/9/10, soc2 §5; governing ruling = **CL-1(a) v1 connector matrix**, PO 2026-08-08).

**Stories live inside their epic files in [`06-epics/`](06-epics/).** This index is generated from story frontmatter at each pack merge — do not hand-edit story content here.

| Story | Title | Epic file | Status | Wave |
|---|---|---|---|---|
| US-INT-001 | S8 Integrations tab: the card grid — v1-REAL vs coming-soon per the CL-1 connector matrix | [EP-INT-01-connections-surface.md](06-epics/EP-INT-01-connections-surface.md) | draft | W4 |
| US-INT-002 | The connect modal: method/environment/cadence → save encrypts, test-connection, Failed · Retry | [EP-INT-01-connections-surface.md](06-epics/EP-INT-01-connections-surface.md) | draft | W4 |
| US-INT-003 | Disconnect: IS-6 confirm + consequence messaging; nothing queued or recorded is ever lost | [EP-INT-01-connections-surface.md](06-epics/EP-INT-01-connections-surface.md) | draft | W4 |
| US-INT-004 | Connection events → audit_log (masked) + consumer read-model + subprocessor-register feed | [EP-INT-01-connections-surface.md](06-epics/EP-INT-01-connections-surface.md) | draft | W4 |
| US-INT-005 | BYO mailbox connect: Google OAuth / Microsoft OAuth / custom SMTP — send from the tenant's OWN address | [EP-INT-02-comms-connections.md](06-epics/EP-INT-02-comms-connections.md) | draft | W5 |
| US-INT-006 | Transactional ESP connect: API key + sending-domain checklist (the 6k–10k volume path) | [EP-INT-02-comms-connections.md](06-epics/EP-INT-02-comms-connections.md) | draft | W5 |
| US-INT-007 | Channel activation: the adapter binding the dispatcher reads + provider health for the delivery dashboard | [EP-INT-02-comms-connections.md](06-epics/EP-INT-02-comms-connections.md) | draft | W5 |
| US-INT-008 | Bank & lockbox import connection profiles: per-bank format profile, upload-or-SFTP source | [EP-INT-03-file-channels.md](06-epics/EP-INT-03-file-channels.md) | draft | W4 |
| US-INT-009 | Accounting export target profiles: QBO-file / Xero-file / CSV / IIF + the export-code hand-off | [EP-INT-03-file-channels.md](06-epics/EP-INT-03-file-channels.md) | draft | W5 |
| US-INT-010 | File-channel profile lifecycle: IS-1 deactivate-first, idempotency alignment, audited edits | [EP-INT-03-file-channels.md](06-epics/EP-INT-03-file-channels.md) | draft | W5 |
| US-INT-011 | Payment rails cards: Stripe + Plaid — "Coming soon · W7", gating, and what unlock requires | [EP-INT-04-future-seams.md](06-epics/EP-INT-04-future-seams.md) | **deferred** | W7 |
| US-INT-012 | v1.1/v2 seams: Twilio SMS · QBO/Xero live sync · Itron/Sensus MDM (NFR-27 gate) · Okta/Azure AD SSO | [EP-INT-04-future-seams.md](06-epics/EP-INT-04-future-seams.md) | **deferred** | v1.1/v2 |

**12 stories · 4 epics.** *(Part 1, 2026-08-09 — see Part 2 below for the 34 substrate stories.)* Rules: [`02-business-rules.md`](02-business-rules.md) · Fields: [`03-field-map.md`](03-field-map.md) · Flows: [`04-flows.md`](04-flows.md) · Traceability: [`../../10-traceability-matrix.md`](../../10-traceability-matrix.md)

Deferred-wave map (the connect SURFACE + coming-soon signage are v1; only gated connects defer): email SENDING → **W6** (OQ-073/074; connections may be made early) · Stripe/Plaid → **W7** (OQ-015/TD-9) · Twilio SMS → **v1.1** · QBO/Xero live sync → **v2** (BR-LED-020) · Itron/Sensus MDM → **v2** (NFR-27 gate) · Okta/Azure AD SSO → **v2** (BR-IDN-028/029 consistency).

## Part 2 · The substrate — 34 stories, 9 epics (`CR-069`, 2026-09-03)

**`US-INT-013`–`046`, in `EP-INT-05`–`13`.** Phase is `CR-069` §12's (1–5; *GL* = the partner track, which
*"is not a phase — it is a different project wearing the same word"*). ⚠ marks a story implemented **to the
boundary and stubbed** — `raise NotImplementedError("OQ-INT-####")` — because a question it needs is open.

**Where to look for a screen's layout:** every story names its screens by `S` id; the frames of *The Integrations
Surface* (the wireframe pack the PO exported 2026-09-03 — 41 frames, 24 figures) are `wireframes/frame-NN-N.png`,
the layout written from them is `08-screen-layouts.md` (one entry per screen: S8 grid · S141 modal · S142 detail ·
S143 mappings and the GIS queue · S144 who has been reading · S145/S146 consent · the address lookup on the premises
form), and every component named there is defined once, as Tailwind, in `09-component-inventory.md`. A builder
opens all three beside the story — the frame is what hard-won law 6 says to diff the running app against. Where a
frame and a B14 rule or an open question disagree, the rule wins and the layout entry says so.

| Story | Title | Epic file | Status | Phase |
|---|---|---|---|---|
| US-INT-013 | The manifest registry: a provider is one declarative object, and seven readers read it | [EP-INT-05-the-substrate.md](06-epics/EP-INT-05-the-substrate.md) | ready | 1 |
| US-INT-014 | The five tables, and why not one — anchored in the schema brief BEFORE the migration | [EP-INT-05-the-substrate.md](06-epics/EP-INT-05-the-substrate.md) | ready | 1 |
| US-INT-015 | The adapter protocol: validate, test, execute, describe — and nothing else | [EP-INT-05-the-substrate.md](06-epics/EP-INT-05-the-substrate.md) | ready | 1 |
| US-INT-016 | Job kinds and a dedicated queue — and the consuming worker, or neither | [EP-INT-05-the-substrate.md](06-epics/EP-INT-05-the-substrate.md) | ready | 1 |
| US-INT-017 | Server-side gating of coming-soon providers: refused by the API, zero secret persistence | [EP-INT-05-the-substrate.md](06-epics/EP-INT-05-the-substrate.md) | ready | 1 |
| US-INT-018 | Operations, not providers, are the unit: one card, one credential, several things it does (C1) | [EP-INT-05-the-substrate.md](06-epics/EP-INT-05-the-substrate.md) | ready | 1 |
| US-INT-019 | The connect/manage modal (S141): one frame, a field slot from the manifest, three field kinds (C2, T27) | [EP-INT-05-the-substrate.md](06-epics/EP-INT-05-the-substrate.md) | ready | 1 |
| US-INT-020 | The run record and its five counts — and the connection detail screen (S142) | [EP-INT-06-the-run-record.md](06-epics/EP-INT-06-the-run-record.md) | ready | 1 |
| US-INT-021 | The unconfirmed outcome: a run whose numbers cannot be reconciled says so | [EP-INT-06-the-run-record.md](06-epics/EP-INT-06-the-run-record.md) | ready | 1 |
| US-INT-022 | Per-connection concurrency cap, hard timeouts and the breaker | [EP-INT-06-the-run-record.md](06-epics/EP-INT-06-the-run-record.md) | ready | 2 |
| US-INT-023 | Email feedback — delivery and bounce — and the *not reported* that stays until it exists (C28) | [EP-INT-06-the-run-record.md](06-epics/EP-INT-06-the-run-record.md) | **ready to the boundary** — `OQ-INT-1729` ruled 2026-09-06 (a): the send half is built and the feedback DOOR is built here; **marking rows `delivered`/`bounced` and the suppression list wait for Runbooks** | 2 |
| US-INT-024 | Credential versioning, rotation and rollback | [EP-INT-07-credentials-have-a-lifecycle.md](06-epics/EP-INT-07-credentials-have-a-lifecycle.md) | ready | 2 |
| US-INT-025 | Offboarding: disconnect destroys the credential immediately and keeps the run history | [EP-INT-07-credentials-have-a-lifecycle.md](06-epics/EP-INT-07-credentials-have-a-lifecycle.md) | ready | 2 |
| US-INT-026 | Fold the email sender card into the connection model (C35) | [EP-INT-07-credentials-have-a-lifecycle.md](06-epics/EP-INT-07-credentials-have-a-lifecycle.md) | ready | 2 |
| US-INT-027 | The expiry warning sweep: eleven days before a token lapses, in words, with the date | [EP-INT-07-credentials-have-a-lifecycle.md](06-epics/EP-INT-07-credentials-have-a-lifecycle.md) | ready | 3 |
| US-INT-028 | Token exchange and the fetch plan: a ten-minute token across a two-hour walk (C11, C12) | [EP-INT-07-credentials-have-a-lifecycle.md](06-epics/EP-INT-07-credentials-have-a-lifecycle.md) | ready | 4 |
| US-INT-029 | The scheduling model: their night, spread, skipped not doubled, never replayed six times (C29) | [EP-INT-08-scheduling.md](06-epics/EP-INT-08-scheduling.md) | ready | 3 |
| US-INT-030 | The request budget: knowing the allowance has run out before readings stop on a Thursday | [EP-INT-08-scheduling.md](06-epics/EP-INT-08-scheduling.md) | ready | 3 |
| US-INT-031 | Completion: immediate, or submit–poll–collect — a result that is a link, or a handle (C10, C20) | [EP-INT-08-scheduling.md](06-epics/EP-INT-08-scheduling.md) | ready | 4 |
| US-INT-032 | Per-item savepoints on import: row 412 stops row 412 and nothing else — proved on PostgreSQL | [EP-INT-09-files-in-files-out.md](06-epics/EP-INT-09-files-in-files-out.md) | ready | 4 |
| US-INT-033 | Files out and files in on the substrate: period + target, and a hash before parse | [EP-INT-09-files-in-files-out.md](06-epics/EP-INT-09-files-in-files-out.md) | ready | 4 |
| US-INT-034 | Readings that arrive late: idempotency with a mode, a billed reading that does not move (C13, C21) 🔒 | [EP-INT-09-files-in-files-out.md](06-epics/EP-INT-09-files-in-files-out.md) | ready | 4 |
| US-INT-035 | Safety-relevant parameters explicit; a fetch that changes their world recorded as a write (C18, C19) 🔒 | [EP-INT-09-files-in-files-out.md](06-epics/EP-INT-09-files-in-files-out.md) | ready | 4 |
| US-INT-036 | The meter list, kept in step: the supplier's record fills the size a bill is blocked for | [EP-INT-09-files-in-files-out.md](06-epics/EP-INT-09-files-in-files-out.md) | **blocked** `OQ-INT-1485` | 4 |
| US-INT-037 | Their words for our things: a foreign name is a row, never a column (S143) | [EP-INT-10-their-words-for-our-things.md](06-epics/EP-INT-10-their-words-for-our-things.md) | ready | 1 |
| US-INT-038 | Unknown values degrade inbound and refuse outbound; Nacha codes as rows, camt.053 as a codec (C4, C36) | [EP-INT-10-their-words-for-our-things.md](06-epics/EP-INT-10-their-words-for-our-things.md) | ready | 4 |
| US-INT-039 | Format is a parameter: projection × codec × packaging (C8) | [EP-INT-10-their-words-for-our-things.md](06-epics/EP-INT-10-their-words-for-our-things.md) | ready | 1 |
| US-INT-040 | Machine authentication for a partner: a key we issue, scoped to one tenant, shown once (C30) | [EP-INT-11-the-partner-reading-from-us.md](06-epics/EP-INT-11-the-partner-reading-from-us.md) | **blocked** `OQ-INT-1481` | GL |
| US-INT-041 | A partner reading from us: the surface, the allowlist, the rate limit, the record of who read what (C5, C33) | [EP-INT-11-the-partner-reading-from-us.md](06-epics/EP-INT-11-the-partner-reading-from-us.md) | **BUILT `2.199.0`** (integrations half; the payload's meaning is Runbooks' per `CR-069` §20.4) — was *blocked* on `OQ-INT-1481`, CLOSED 2026-09-04 option (a) | GL |
| US-INT-042 | Executor: server or browser; the inline address search; a result offered, not loaded (C14–C16) | [EP-INT-12-gis-and-the-map.md](06-epics/EP-INT-12-gis-and-the-map.md) | ⚠ **BUILT 2026-09-06** (`CR-069` wave M, `2.205.0`–`2.208.1`) — the manifest declarations refused at load, the generated page policy served on the document, the inline runner with one run row per search session, the breaker, and Priya's Create. Both branches walked in a browser: candidates in **814 ms** against a **1,000 ms** budget, and the premises count **79 before the pick and 79 after**. `OQ-INT-1471` closed 2026-09-04 (*type it, marked unchecked* — a BUILD, and `premises.gis_unchecked` is the mark); `OQ-INT-1728` closed 2026-09-06 (a): the Create write stays with integrations. ⚠ **AND THE FIRST BUILD WAS UNUSABLE BY A BILLING CLERK** — both routes carried the *settings* permission class, so the search answered `403`, the panel read that as *no City here* and removed itself (`DEF-INT-4267`, fixed at `2.208.1`; proved as a clerk over HTTP — search `200` with 4 candidates, create `201`, premises 79 → 80). She still cannot reach any SCREEN: `DEF-SHL-4272`, older and not this wave's. ⚠ **NOT built and not stubbed:** the same job as a scheduled batch and as a run-once batch — both Runbooks', named in the same ruling, sized nowhere | 4 |
| US-INT-043 | The nightly GIS reconciliation: per-field authority, membership, seven classes, the money-path columns (C17, C22–C25) 🔒 | [EP-INT-12-gis-and-the-map.md](06-epics/EP-INT-12-gis-and-the-map.md) | **blocked** `OQ-INT-1470`–`1472` | 5 |
| US-INT-044 | The inbound door: a kiosk payment applied once, 409 on replay, a return not mistaken for a duplicate (C3, C6, C31) | [EP-INT-13-the-inbound-door.md](06-epics/EP-INT-13-the-inbound-door.md) | ready | 5 |
| US-INT-045 | Indeterminate — a third outcome — and the key generated before the charge leaves (C26, C27) 🔒 | [EP-INT-13-the-inbound-door.md](06-epics/EP-INT-13-the-inbound-door.md) | **blocked** `OQ-INT-1476`, `1478` (contingent) | 5 |
| US-INT-046 | A customer letting someone else see their usage: a consent checked on every request (C9) | [EP-INT-13-the-inbound-door.md](06-epics/EP-INT-13-the-inbound-door.md) | **blocked** `OQ-INT-1482` (conditional) | 5 |

**34 stories · 9 epics · 11 blocked** (nine wholly, two on one branch). With Part 1: **46 stories · 13 epics.**
Rules: [`02-business-rules.md`](02-business-rules.md) Part 2 · Fields: [`03-field-map.md`](03-field-map.md) Part 2 ·
Flows: [`04-flows.md`](04-flows.md) Part 2 · Endpoints: [`07-endpoints.md`](07-endpoints.md).
