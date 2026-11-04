# CR-182-BRC10 · High consumption: the customer is alerted as soon as a reading is flagged — portal message, email, bill note, reading tag

**Raised:** 2026-10-14 by the Product Owner, in chat, put with Susan Cook's case (AC-2026-00551; normal 5,513–7,637 gal; a 10× reading ≈ 70,000 gal billed "as is").
**Requester's words (verbatim):** *"A1 … when we get high consumption expectation is we will immedately send it high consumption alert to get in portal in app msage or warning and possible email also. plus you can show her option 1; A2 … option 1 - just say - high usage ; A3 … high conumption alert; A4 … send her Email; A5 … Option 2 Tell them as soon as the reading is flagged. - this is corerct"*
**Ruling record:** decision log 2026-10-14 *"HIGH CONSUMPTION: THE CUSTOMER IS ALERTED AS SOON AS A READING IS FLAGGED — PORTAL MESSAGE, EMAIL, BILL NOTE, READING TAG (A1–A5)"*; answers `OQ-262`'s high-usage half (daily digest and security alerts stay OPEN).

## 1 · Classification
A **change**: a capability the product never had. Until now BR-MET-020's 200% flag held a READING for a clerk and was never a customer message; SET-12's *High usage alert* row was drawn and refused (`trigger_blocked_by="OQ-262"`). Not a defect: the product did what its rules said.

## 2 · What is reversed or added
| Before | After |
|---|---|
| A reading flagged high (above 200% of normal AND above the service's absolute floor, BR-MET-020/120) is seen only by staff | **A5/A6** — the same flag, at the moment the reading is saved, alerts the customer. Staff and customer always agree on what "high" is because it is one rule. |
| SET-12 *High usage alert* — drawn, refused, "no trigger exists" | **A4** — a live EMAIL event (SMS not chosen), queued through the normal outbound queue with a delivery record, switchable by the utility's own rule. |
| Portal Home says nothing about usage | **A1** — *Needs your attention* carries *High consumption alert · Water reading on 09/19/2026 was much higher than usual* while the flagged reading is the meter's latest and not yet billed; once a bill carrying it exists, *Your last bill is higher than usual · See why →* to the bill's comparison. |
| Bill detail says nothing | **A2** — *High usage* near the top of a bill that priced a flagged reading, beside the existing *Why is this bill different?* link. |
| Usage → Readings says nothing | **A3** — a *High consumption alert* tag on the flagged reading's row. |
| Staff *Bill as is / Investigate* | **Unchanged.** |

## 3 · Tasks
| # | Task |
|---|---|
| B1 | Metering: one door that, after a reading is written (batch post, correction, cascade recompute), queues the alert email when the new head is flagged high and has an account — idempotent on the reading; not re-sent when the reading it replaced was already flagged. Through `metering/seams.queue_document`, never the notifications ORM. |
| B2 | Notifications: `high_usage_alert` un-blocked — email only, template class `email_high_usage_alert` (catalogue + palette + seeded body), source kind `usage_alert` (no print floor), the utility's rule read at queue time. |
| B3 | Metering portal read: which readings are flagged; the open alerts for an account's meters (latest head, flagged, not billed). |
| B4 | Portal: Home attention kinds `high_consumption` and `high_bill`; bill detail `high_usage`; readings row `high_consumption`. |
| F1 | Portal Home, bill detail and Readings render the three; strings in all eleven catalogues. |
| T1 | Backend (SQLite + PostgreSQL): flag → email queued once; re-save idempotent; corrected-not-high resolves; rule off = no email but the portal still shows it; cross-tenant isolation. Portal dom tests under `/:tenant/portal/...`. |
| E1 | Walk on a private DB copy: a 10× reading, Home message, readings tag, queued email; bill it; bill note + Home bill notice. `05-prototype/high-consumption-alert-2026-10-14/`. |

## 4 · Status — BUILT, NOT RELEASED (lane HIGHUSE, 2026-10-14)

No version bumped and no CHANGELOG line — the release lane does both. Our judgments: decision log *"HIGH CONSUMPTION ALERT — HOW A1–A5 WERE BUILT: SEVEN JUDGMENTS OF OURS"*.

| # | Built |
|---|---|
| B1 | `apps/metering/high_consumption.py` — `notify_if_flagged(read, replaced=…)`, called from `_post_row`, `_supersede_row` and the cascade recompute; queues through `seams.queue_document` in its own savepoint and never raises. No alert table: the alert IS the flagged reading (judgment 1); not re-sent when the replaced reading was already flagged (judgment 2). |
| B2 | `rule_catalog` `high_usage_alert` live — email only, `email_high_usage_alert`, source `usage_alert` (no print floor); catalogue listing + palette, seeded body (default variant), kept document kind `high_usage_alert` (`tenancy/0062`), `notifications/0022` switches the row on for untouched utilities. BR-NOT-018 amended. |
| B3 | `high_consumption.open_alerts_for_accounts` / `flagged_read_ids`; `portal_reads` row `high_consumption`. |
| B4 | `portal.selectors.home` attention `high_consumption` (service, date) and `high_bill` (number); `billing_seam.bill_detail_for` `high_usage`; `last_bill_high_usage`. |
| F1 | Home `HighUsageNotice`, bill detail *High usage* chip beside *Why is this different?*, Readings `HighConsumptionTag` (table + phone card); 8 keys × 11 catalogues. |
| T1 | `tests/test_cr182_high_consumption_alert.py` — 11 cases (SQLite; PostgreSQL see lane report). Red first: removing the `_post_row` hook, the told-once check, the bill's `high_usage` or the not-billed condition turned 5 + 2 cases red. `portal/home/HighUsage.dom.test.tsx` — 8 cases under `/:tenant/portal/...`; red first (5 failed with the three screens' branches disabled). Counts moved in `test_cr_009_notification_rules.py` (blocked rows 8 → 7) and `test_cr048_print_floor.py` (`usage_alert` classified). |
| E1 | `05-prototype/high-consumption-alert-2026-10-14/` — Ana Alvarez's 10× water reading (80 kgal vs 8), Home alert, readings tag, ONE queued email; billed BL-2610-000251 $780.10 → *High usage* + *Your last bill is higher than usual*. |

**Open items:**
1. Existing utilities need the operator seed (`seed_notice_templates`, via `manage.py seed_demo --tenant <x>`) for the email wording; until then the queued alert holds with the missing-template reason.
2. `notifications/0022` has no dedicated migration test (ledger row says so).
3. The Home sentence formats the date in the browser locale (*Oct 11, 2026*), like the other Home sentences, not in the utility's format.
