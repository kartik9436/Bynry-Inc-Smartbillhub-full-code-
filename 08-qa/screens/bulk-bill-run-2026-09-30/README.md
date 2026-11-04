# Bulk bill run — the built page, captured (2026-09-30)

The redrawn bill run (`07-frontend/src/features/billing/bulkRun/`), captured at the
drawing's 36 states × 1440 and 1280 = **72 PNGs**, named exactly as the drawing's own
images in `05-prototype/bulk-bill-run-2026-09-30/` so the two pair one to one.

**How they were made:** `node 10-scripts/bulk_bill_run_capture.mjs` against
`07-frontend/bulk-run-harness.html` (the REAL page and stylesheets, the API answered from
`bulkRun/__fixtures__/bulkRunFixtures.ts`; start `npx vite --port 5231` first). The harness
mounts the page without the app frame (sidebar, top bar) — the same method the one-time
bill used. Figures are example data (B14 rule 37).

## Mismatches against the drawing, and why

**Our UI standard wins on construction (B14 rule 44), so these are expected, not defects:**
panels are the kit `Panel` (grey surface, 1px border); the rail is `WizardFrame`'s (a done
step shows its number on black, not a ✓; the current step is accent text, not an
underline); tiles are the kit `KPIStrip` (a pressed tile is an accent outline); segmented
filters are the kit `SegmentedControl` (accent fill, not black); pagination is the kit
`ListPager` (50 rows a page, not 8); dates follow the tenant's regional format
(`09/01/2026`, not `Sep 1`); the reason under a disabled forward button sits **under** the
action row (the frame's rule), not to its left; the `Fix N things first.` line and
`N blocked stay out.` do the same.

**A section the drawing shows and nothing serves yet — shown as "Not available yet.",
never as a zero (each filed):**

| Image(s) | What | Defect |
|---|---|---|
| 07, 08 | Nobody to bill / Missing meter panels list no rows — only the counts are served | DEF-BIL-8221 |
| 01–08 | Bill template offers the tenant's one template only | DEF-BIL-8222 |
| 09 | Checking shows no `n of N` (Check is one request) | DEF-BIL-8224 |
| 11–23 | The category list and tag counts are grouped in the browser from `/findings` + `/exceptions` | DEF-BIL-8216 |
| 11, 16 | The nine Payments & balances tags: `9 checks: Not available yet.` (only *Late fee due* is served) | DEF-BIL-8211 |
| 15 | Warnings tile and warning tags (Base charge $0.00 …) | DEF-BIL-8210 |
| 13, 23 | No inline fix on the row (choose plan / size / unit …); each row links to the owning screen, then Re-check | DEF-BIL-8218 |
| 13, 14, 23 | Re-check reads the whole run again, not the named accounts | DEF-BIL-8219 |
| 20, 21 | Ready to bill has no Leave out / Put back, no Regular/Master filter and no Unit column (the ready rows carry neither kind nor unit) | DEF-BIL-8217 |
| 25–28 | Payments applied, Amount due, Regular · master, Units billed, usage/base split, taxes and fees, Payments and balances | DEF-BIL-8220 |
| 32, 35 | Delivery and Autopay figures on Send / Sent | DEF-BIL-8220 |
| 34 | Sending shows no `n of N` | DEF-BIL-8224 |
| 35 | Leave for next cycle | DEF-BIL-8223 |

**Changed by rulings later than the drawing (changes rows 44–46, PO 2026-09-30):** Check
shows `Checked N accounts at HH:MM` with **Check again**; decision rows show what was found
and a **suggested answer** with **Accept** and **Accept suggestion for all N**; disputed
reading, meter swapped, no plan, plan not published, no price for a service, no charge for
type, no price in force, no multiplier, time-of-use unmatched and city limits are DECISION
tags (amber), not blocking. Where the engine still reports one of those as blocked, its rows
carry only the Fix link until the engine lane serves the case.

**Waive and Bill without it (PO 2026-09-30, fixed-charge cases 1–2):** on *Standing charges
only* the leave-out answer reads **Waive**; choosing it opens a **Reason** box whose Save stays
disabled until a reason is typed, the reason travels on the resolve, and an answered row shows
the warning line *Base not billed this month.* Sign off lists `N bills: base waived.` under
its warnings with **See**, which returns to that tag. The drawing's `Waived $26` shows a COUNT
here, not an amount — no served read carries the waived base total (DEF-BIL-8220). On *No
reading* the answer *Bill without it* reads **Bill base, usage later**, and an answered row
shows *Usage: no reading, billed next bill.* The PNGs above were captured before this ruling
and do not show either wording.

**States the build cannot reach, captured as the nearest real state:** `13` and `23`
(a row fixed inline → the tag with its Fix links; inline fixes not served), `21` (a ready
account left out → Ready to bill via its tile), `15` (a warning tag → the Warnings tile
pressed, nothing to list).

**Smaller differences:** the run header line and the aside's run name read `—` on a
re-opened run (the run read serves no label); `Bill day` reads `Day 1`, not `1st`; the
aside has no *Last run total* row; the Scope aside's services are the utility's enabled
services (no per-cycle list is served).
