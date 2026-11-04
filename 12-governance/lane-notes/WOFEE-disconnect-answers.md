# Lane WOFEE — two answers for the PO (2026-09-25)

Read-only lane. Nothing built, nothing changed. Worktree from tip `9215840a1`.
DB evidence from a clone `sbh_wofee` (TEMPLATE smartbillhub), tenant
`01a0d239-8294-72dc-acdc-a6e9bb863397` Brazos Bend Utilities, every read inside
`BEGIN; SET LOCAL app.tenant_id = …; … COMMIT`.

## Q1 — a failed visit

1. **Work order statuses.** `work_orders` carries three independent axes,
   declared in `06-backend/apps/metering/connections.py`:
   * `state` — planned · in_progress · blocked · completed · cancelled
     (lines 443–456; the docstring says these are "REPORTED, not signed" —
     the design never listed them).
   * `outcome` — passed · failed · partially_done · cancelled ·
     waiting_on_someone_else (lines 425–438).
   * `dispatch_state` — queued · scheduled · en_route · on_site · complete ·
     on_hold · cancelled (lines 476–491).
   So *attended and could not complete* IS expressible: `dispatch_state`
   reaching `on_site` proves attendance, `outcome = failed` /
   `waiting_on_someone_else` / `partially_done` says the job did not happen.
   ⚠ `outcome` has **no database CHECK constraint** — `pg_constraint` on
   `work_orders` holds only `ck_work_orders_dispatch_state`,
   `ck_work_orders_has_anchor`, `ck_work_orders_one_assignee`,
   `ck_work_orders_source`. Live data already holds `outcome='completed'`,
   which is not one of the five tokens (1 row of 39).

2. **Is a work order raised for a DISCONNECT? NO.**
   `apps/work/from_flows.py` declares six flow kinds — service_request,
   move_out, move_in, transfer, **reconnect**, meter_read. There is no
   `disconnect`. `WORK_ORDER_SOURCES` (connections.py 600–618) has sixteen
   tokens including `reconnect` and `move_out` and **no `disconnect`**.
   `apps/customers/disconnects.py` calls the work seam exactly once, at line
   5376, `flow_kind="reconnect"`, inside `mark_reconnecting`. The disconnect
   wizard's steps folder has no field-work panel: `FieldVisitOrders` is mounted
   by MoveOutWizard, MoveInWizard and TransferWizard and by no disconnect file.
   Live data: 39 work orders on this tenant, **`source` NULL on all 39**.

3. **Does a work-order status reach the disconnect case or the list? NO —
   and it does not need to, because the gap was closed a different way.**
   * `apps/customers/disconnect_reads.py` (the Disconnects list and its six
     segments) contains **0** references to `DisconnectVisit`, `work_orders`
     or any work seam.
   * The seam direction customers→work exists and is write-only-by-asking:
     `apps/customers/seams.py` 2008–2098 — `propose_flow_work_orders`,
     `raise_flow_work_orders`, `raise_flow_order_rows`,
     `flow_work_acceptance`, `flow_work_not_raised`. Nothing on the disconnect
     side calls `flow_work_acceptance`.
   * **The gap was closed on 2026-09-20 by `BR-CUS-1083`, not by work orders.**
     `apps/customers/disconnect_visits.py` + `customers/0062`, table
     `disconnect_visits`, door `POST /accounts/{id}/disconnect-case/visit`,
     screen `RecordVisitDialog.tsx` mounted by `DisconnectRecordPage.tsx:507`,
     routed in `App.tsx:1171`. Four outcomes: locked_gate · access_refused ·
     paid_at_door · disputed. Three clear the cut date and return the case to
     `notice_sent`; `disputed` stops the ladder via `stop_by_hand`.
     `VISIT_RAISES_NO_FOLLOW_UP` states in its own words that it raises no work
     order and re-dispatches nobody.
   * Residual gap: after a locked-gate visit the case reads `notice_sent`,
     which is **identical on the list to a case never attended**. The
     "Due to cut" count self-corrects; "which of these were attempted" is still
     not answerable from the list. Live: 0 rows in `disconnect_visits`.

## Q2 — the three fees

Measured on the clone, tenant charge catalogue:

| Code | Configured? | Amount | Rule | GL |
|---|---|---|---|---|
| RECON | **yes** | 75.000000 | flat | mapped |
| DISC | **yes** | 45.000000 | flat | mapped |
| FIELD | **no row at all** | — | — | — |

* `RECONNECT_CHARGE_CODE` is `"RECON"` (disconnects.py:946) since the PO ruling
  of 2026-09-21 (*"reconnection fee is $75 - fix the code and seed"*,
  `OQ-CUS-12518` CLOSED). `rating/0042` moved every existing tenant's row from
  45.000000 to 75.0000, leaving a tenant's own edited figure alone.
* `charge_by_code` (rating/selectors.py:7524) would therefore return the row:
  not deleted, `amount_rule='flat'`, amount present.
* `FeesAndConsequencesStep.tsx` **does** call `getReconnectionTerms` and the
  wizard **does** pass `client` (DisconnectWizard.tsx:533). The in-file
  comments at lines 73–86 still describe `CC-RECON` / DEF-700 / "every cut
  refuses today" — those comments are STALE by four days.
* Timing already ruled: the fee is owed **at the cut**, not at restoration —
  `FEE_TIMING_RULED` / `reconnection_fee_lands_at_the_cut` (disconnects.py
  ~1101–1115), signed by `BR-CUS-104`, PO 2026-08-25 on `A-11340`'s
  $8,240.00 + $75.00 = $8,315.00. `commit_cut` records
  `reconnection_fee_amount` / `reconnection_fee_code` and calls
  `seams.raise_and_issue_charge_fee` (disconnects.py 4503–4516), which drafts
  and ISSUES a `fee` bill so the amount reaches AR (DEF-708, PO 2026-08-27).
* Not proved on live data: **0** cases on this tenant have ever reached a cut
  (`reconnection_fee_amount IS NOT NULL` → 0; case states are notice_sent 2,
  scheduled 2), and **0** invoice lines match reconnect/reconnection. So the
  posting path is proved by code and by the DEF-708 tests, not by a row.
* Disconnection fee: code configured at $45, and **nothing raises it** — no
  call site anywhere charges `DISCONNECT_CHARGE_CODE`.
* Field-visit fee: no code, no price ruled, and nothing raises it.
