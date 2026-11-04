# notifications — Flows & States

Screens: cross-cutting (A15 matrix) + S8 dispatch home + designers S94–S106/S67 (details: A1 screen inventory, A9 navigation map).
State machines: extracted below from the ratified rules (BR-NOT-005, BR-BIL-016/026/027, BR-PAY-016/017/018, BR-NOT-001..004). A5 predates the queue model; the queue lifecycle here is law per B2 r10 #8 / r12 #16.

## 1. Outbound-queue row lifecycle (BR-NOT-005, US-NOT-001/002)
```
[any module event] → queue-write (idempotent, one row per recipient × channel)
  → QUEUED ──(dispatcher batch, tenant-config default 500, provider pace)──→ SENT
       │                                                                      ├→ DELIVERED
       │  (held marker: bad-address paper suppression — BR-PAY-018;           ├→ FAILED   (after retry ×3 backoff; provider error stored)
       │   dispatch-not-before; deferred channel email W6 / SMS v1.1)         └→ BOUNCED  (W6 provider webhook)
       │
  FAILED/BOUNCED ──(re-queue action, audited — US-NOT-013/US-BIL-024)──→ QUEUED
  HELD ──(address verified, US-PAY-016)──→ released → normal dispatch
```
Forward-only statuses; the re-queue ACTION is the only reset; nothing ever sends inline; no row is ever lost.

## 2. Template lifecycle — every designer S91+ (BR-BIL-026/027 via A19 addendum b; BR-NOT-002; US-NOT-006)
```
DRAFT (Clerk edits + test-renders; every edit = NEW append-only version)
  → PUBLISHED (System Admin only; exactly one published per template; affects FUTURE renders only)
  → ARCHIVED (auto on next publish, or manual)
Pinning: issue/send/sign stamps template + version on the document/row/contract
  → pinned version renders forever (reprint/re-send) and can NEVER be deleted (audit-lock)
Contracts (S67): versions carry effective_from — generation picks the version in effect (BR-NOT-002)
Resolution at render: account override → consumer-category default → published version (BR-BIL-025)
```

## 3. Notice ladder — rendering side (BR-PAY-017/035, BR-REP-016, BR-CUS-039; US-NOT-009/010)
```
ladder (tenant-config, payments-owned evaluation — US-PAY-014):
  due+3 reminder ──→ late fee (billing) ──→ 10-day ──→ 5-day ──→ 48h certified FINAL
render mapping (one mapping for engine + S35 manual tones — free text does not exist):
  friendly = due+3 (dunning/reminder class, NO regulatory footer)
  firm     = 10-day   ┐
  final    = 5-day/48h┘ regulated disconnect class (A19 §2 tiers, regulatory footer,
                         certified mail FORCED on final; SMS supplements, never replaces)
exclusions: medical-hold → generation REFUSES + notice_history records the SKIP
every send AND skip → notice_history append (r12 #7; J4 step 2 contract)
day numbers: cadence seeds 7/14/30 + ladder seeds due+3/10/5/48h — always tenant config, never constants
plan pause: active+current payment plan pauses the ladder (US-PAY-019); void resumes it
```

## 4. Bounce / returned-mail → bad-address (BR-PAY-018; US-NOT-014 → US-PAY-016)
```
paper letter returned (staff marks, single/bulk)  ┐
email bounce webhook (W6) → row status BOUNCED    ┘→ delivery-return event (r12 #8)
  → payments consumes → accounts.bad_address ON → needs-attention queue + S21 banner
  → tenant config suppress_paper_on_bad_address ON → new paper rows HELD (written, skipped, kept)
  → address verified → flag cleared → held rows RELEASED → next batch dispatches
balances unaffected throughout; every step audited
```

## 5. Contract generation (BR-NOT-001..004, BR-CUS-044; US-NOT-012)
```
trigger (plan S24 / move-in / deposit / autopay enroll)
  → pick type (①plan ②service ③deposit ④autopay-authorization)
  → variant by account consumer category (Res/Com/Ind/Gov → default fallback)
  → version in effect on generation date (effective_from)
  → render (A19 §3 for ①) → e-sign envelope (DocuSign seam, B7)
  → customer e-signature ALONE executes (no countersign — A19 addendum c)
  → signed PDF → account documents; contract permanently references the exact version
```

## 6. Dispatch-home (S8 Notifications tab — BR-TEN-041 #8; US-NOT-004/013)
Config half: batch size (seed 500) · channel activation (print live / email W6 / SMS v1.1 badges) · provider status (read from integrations) · A15 "(opt)" toggles.
Dashboard half: platform-wide counts type × channel × status · failures/bounces list · re-queue (row/bulk, audited, never bypasses batching, never releases held rows).
