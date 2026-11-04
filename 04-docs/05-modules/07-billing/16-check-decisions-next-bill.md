# Bulk bill run — does a Check decision affect the next bill? (2026-09-30)

Status: **ANALYSIS, traced from code; the ⚠ rows are under two-month tests** (check-engine lane).
Asked by the PO: *"will this have any impact on subsequent bill"*. Rulings: decision log 2026-09-30.

**How the next bill starts.** A cycle run anchors each meter to the reading the account's
last ISSUED bill closed on (`runs.billed_positions`, from `bill_payload.services[].read_id`).
A decision that changes the quantity without a real reading behind it leaves nothing to anchor to.

## 1 · Carry into next month's usage — one cause, one fix (DEF-BIL-8280) — ✅ fix CONFIRMED by the PO 2026-09-30 (*"this this is correct"*)

| Decision | Risk | Fix (PO direction: keep it in the register) |
|---|---|---|
| No reading → Estimate | Estimated usage billed again next month (Aug 1,000 · Sep est. 5 · Oct 1,012 → bills 12, should bill 7) | At ISSUE, write the estimate into Meter Reads through its service as an ESTIMATED reading (meter, date, run, bill, clerk); Meter Reads' true-up (BR-MET-029) subtracts it at the next real reading; next bill says "true-up of September's estimate" |
| Disputed reading → Bill on an estimate | Same | Same |
| Reading went down (not a rollover) → Estimate | Same | Same |
| Meter swapped, reading missing → Estimate the missing part | Same, on the old meter's part | Same |

## 2 · Can lose or double a fixed charge — ✅ all five RULED by the PO 2026-09-30; two-month tests assert these

| Decision | Risk | Proposed fix (money: back to the PO before changing) |
|---|---|---|
| Bill without it (skip a service) | That month's base for the service never billed | ✅ **RULED 2026-09-30 (A):** bill the base this month; usage waits; bill says "Water usage: no reading, billed next bill" |
| Standing charges only → Leave out | That month's base never billed | ✅ **RULED 2026-09-30 (B, Waive):** the clerk decides it is not billed — reason required, warning, "Waived $26" on Sign off, logged; nothing carried forward. Principle: a clerk's deliberate choice is final for that month; next month bills normally |
| Hold / Leave for next cycle | Held month's base may be lost | ✅ **RULED 2026-09-30 (A, one base):** the next bill starts the day after the account's last bill (Sep 1 – Oct 31) — all usage since then, ONE base charge only; the held month's base is not billed |
| Gap or overlap → Bill as is (overlap) | Overlap days' base billed twice | ✅ **RULED 2026-09-30 (A):** bill from the day after the account's last bill (Oct 1–14), base prorated 14/30 ($3.73 water); "Bill as is" removed for overlaps |
| Plan instalment → Skip this month | Two instalments next month, or one lost | ✅ **RULED 2026-09-30 (B):** extend the plan by one month — still $45 a month, one more instalment, total unchanged; the next bill says the plan now ends a month later |

## 3 · No effect on the next bill — ✅ RATIFIED by the PO 2026-09-30 (*"im good with these"*)

Real readings (rollover accepted, meter swap with both readings, time-of-use → flat total, bill as read,
Meter Reads' own estimate kept) anchor correctly. Price-only decisions (multiplier 1, earlier price
version, period-end price, $0 base, default plan, bill other services, city limits, unit from meter)
carry nothing forward — the problem returns next month until someone uses **Fix**; a wrong multiplier
under-bills every month, so Check keeps flagging it. Payments are booked once in the ledger
("apply to this bill" is tested for double counting). Hold → catch-up run bills the held period exactly.
