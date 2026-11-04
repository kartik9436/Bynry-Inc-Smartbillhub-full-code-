# Correction case numbers — walk (DEF-BIL-10147, G3)

Walked 2026-10-14 on a **private copy** of the dev database (`smartbillhub_ccno`,
dropped afterwards), Brazos Bend Utilities, as Dana Whitfield (System Admin, who
sends and approves), at 1440 px, through
`10-scripts/def_bil_10147_case_numbers_walk.mjs` against a backend on :8012 and
the production join (`server.mjs`, `vite build --mode compose`) on :8092.

The ruling (PO 2026-10-14, G3): a correction case takes its number at Send from a
new series **Correction case**, default `CC-{YYYY}-{000}`; existing cases are
numbered once, oldest first; a deleted series leaves a case unnumbered and never
blocks.

## Existing cases — numbered by the migration

`migrate` on the copy applied `tenancy.0062` (the series row) and `billing.0043`
(the backfill). The copy held **23 cases, all unnumbered**, opened 11–13 Oct 2026.
After the migration they read **CC-2026-001 … CC-2026-023** in the order they were
opened, and the series stood at **next 24, restart yearly, counting 2026**.

## One customer (Hugo Hollis, AC-2026-00008, BL-2610-000204 — goodwill credit $10.00)

| Shot | What it shows |
|---|---|
| `1-single-1-bills.png` … `1-single-3-send.png` | Bills → Fix → Send, as before |
| `1-single-4-sent.png` | *Corrections so far*: **CC-2026-024 · Waiting for approval** at the top, under it the backfilled CC-2026-023 … |
| `1-single-5-approver.png` | the approver's view of the case |
| `1-single-6-done.png` | the result: **Case CC-2026-024** (was *Not numbered yet*); credit note CM-0146 |
| `1-single-7-bill-page.png` | the bill page, *What happened*: **Correction opened · case CC-2026-024** |

## Bulk — a price mistake (local tax, Sep 2026; missed AFTER-HRS $75.00 on every bill)

| Shot | What it shows |
|---|---|
| `2-bulk-1-bills.png` | 47 bills on 47 accounts |
| `2-bulk-3-fix-priced.png`, `2-bulk-4-check.png`, `2-bulk-5-send.png` | priced in the background, checked, sent |
| `2-bulk-6-sent.png` | sent; the Send ran as the background job |
| `2-bulk-8-done.png` | **47 bills corrected · Case CC-2026-025**; *Corrections so far* row **CC-2026-025 · Re-price · 47 · −$1,771.92 · Done** |
| `2-bulk-9-bill-page.png` | Ben Bennett's BL-2610-000109: **Correction opened · case CC-2026-025** |

## Settings → Numbering

`3-settings-numbering.png` — the new row **Correction case #** is the last row of
*Billing & payments* (after *Write-off #* and *Settlement #*), format
`CC-{YYYY}-{000}`, options `CC-{YY}-{0000}` · `FIX-{YYYY}-{0000}` · `CC-{00000}` ·
`{000000}`, restart *Yearly*, preview **Next number will be CC-2026-026**.

## The unnumbered path, met by accident — `x-unnumbered/`

The first single Send (Grace Gagnon, AC-2026-00007, goodwill $10.00) went to a
backend that had started while the lane's red-proof mutation was in place (every
allocation answering *series missing*). The case **opened anyway, unnumbered**,
and its audit row says `numbering_gap: numbering_series_missing` — the ruling's
*never blocking* half, in a browser. *Corrections so far* shows it as **No case
number yet** (`1-single-4-sent.png` in the main folder shows both rows together).
The backend was restarted on the real code before every other step; that case was
left waiting for approval and went with the copy.

## Records checked on the copy

| Check | Result |
|---|---|
| `correction_cases` | 26 rows, 25 numbered, 25 distinct numbers; CC-2026-024 `account`, CC-2026-025 `price_mistake` |
| `number_series` `correction_case` | `CC-{YYYY}-{000}` · next **26** · yearly · counting 2026 |
| `audit_log` `correction.case_sent` | `case_no` CC-2026-025 and CC-2026-024 with no gap; the accidental one `case_no` null with `numbering_gap` `numbering_series_missing` |

**Noticed, not changed:** a case waiting for approval does not appear on the bill
page at all — the *What happened* table draws only once a credit note or a
replacement exists — so the bill page shows the number from approval on.
