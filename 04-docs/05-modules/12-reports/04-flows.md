# reports — Flows & States

Screens: S44 library · S45 scheduled & runs · S46 viewer · S47 builder · S7 dashboard (+ S32 chip/label consumption) — details: A1 screen inventory + addenda, A9 navigation map. Extracted at pack authoring 2026-08-09 (BR-REP-001..018).

## 1. Report run flow (US-REP-001/002 — the only render path)
```
S44 card (canned | saved custom)                       S47 builder → Run
  → S46 viewer: param bar (live vocabularies, BR-REP-006; IS-4 URL state)
     → Run report → read-model query AT RUN TIME (BR-REP-002; NFR-26 rollups for closed periods)
        → KPI strip + table (built reports, EP-REP-02) | generic viewer (column-unknown, A14)
        → EVERY money header carries its date-basis label (BR-REP-001):
             billing-side (billed/revenue/AR/aging/collection %) = POSTING
             cash-side (cash today/method mix/deposits/bank)      = CLEARING
  Finance cards route OUT: TB→S56 · Account ledger→S59 · By-premises→S60 · Remittance→S41 (ledger stories)
```

## 2. Download flow (US-REP-003 — IS-11, every report)
```
↓ Export / Print → streamed under RLS (BR-SHL-016: 50k cap; money export → audit_log)
  → CSV always: one snake_case header row · 2dp plain money · ISO dates · no metadata rows
       filename {tenant}_{report}_{period}_{basis}_{generated}.csv
  → PDF where layout matters: letterhead · title · period · filters echoed · BASIS LABEL ·
       generated-at (tenant TZ) + by whom · page X/Y · totals footer (IS-8 formats)
  → NO XLSX v1 (A14 "Excel" corrected, IS-11)
  → report_run row → S45 Recent runs
```

## 3. Run-record + retention lifecycle (US-REP-004)
```
generated (file stored, run row written, By = user | Scheduled)
  --tenant retention window (default 3 days, IS-11)--> downloadable from S45
  --expiry--> file DELETED · run row REMAINS (history) · Download disabled (re-run affordance)
```

## 4. Scheduling flow (US-REP-013/014/015 — J5)
```
schedule (report + cadence + formats CSV/PDF + recipients)
  active --cadence tick (overnight, tenant TZ)--> run: recompute → identical IS-11 files → run row + retention
        --Run now--> same pipeline, By = acting user
        --Pause--> held (no runs, no queue rows)   --Delete (IS-6)--> schedule gone, history stays
  run complete + recipients → outbound_messages rows (BR-NOT-005 — NEVER inline send)
        marked deferred → W6 (BR-REP-017) · v1 delivery = S45 download
        W6: US-NOT-002 dispatcher batches → queued→sent→delivered/failed/bounced
  generation failure → IS-7 failed-with-retry on S45, never silent
```

## 5. Builder flow (US-REP-010/011/012)
```
dataset (six A14 datasets, CLOSED list — new entities = canned only, BR-REP-007)
  → columns (identity always on, IS-5; payments = both dates BR-PAY-021; reads = channel + unit)
  → filter / group / date range (named date field on Payments) / sort
  → Run → S46 generic render (money runs basis-labeled)
  → Save (params only, never rows) → S44 listing · IS-4 share URL
  → Save & schedule → flow 4
```

## 6. Dashboard read-model flow (US-REP-016/017/018)
```
S7: KPI strip + panels ← ruled sources only (BR-REP-002):
  AR/MTD revenue = posting dimensions · Cash today = cleared payments (BR-REP-010) ·
  active accounts = A+MD+VH (BR-REP-012) · billing status = bill_runs · exceptions = S31.3 ·
  write-offs = approved write_offs · intents = "autopay scheduled", excluded (A14 item 10)
S7 + S32 ops chips (BR-REP-015, no new screen): delivery health · pending billing ·
  returned mail · corrections pending · tie-out drift (red, undismissable — clears only
  when the explaining entry posts, BR-LED-007/US-LED-004)
S32 labels: Today total = POSTING · Method mix MTD = CLEARING (BR-REP-010);
  dunning stage day numbers = tenant cadence config, 7/14/30 seeded (BR-REP-016)
```

State machines relevant here: A5 (sources) + queue statuses (BR-BIL-016/BR-NOT-005) consumed read-only; schedule lifecycle (active/paused/deleted) + run lifecycle (generated/failed/expired) per flows 3–4.
