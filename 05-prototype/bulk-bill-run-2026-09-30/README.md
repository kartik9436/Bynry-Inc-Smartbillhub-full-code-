# Bulk bill run — drawing images (D1, 2026-09-30)

The drawn spec for the bulk bill run redesign (`04-docs/05-modules/07-billing/14-bulk-bill-run-changes.md`
rows 1–43, build plan `15-bulk-bill-run-build-plan.md`), captured from the mock-up the PO
reviewed screen by screen on 2026-09-30 (https://claude.ai/artifact/NXYoLbAzQEC3FGyyLhjv4X;
source `mockup.html` in this folder). The PO approved the 36 states × 2 widths in the words
*"im good with thsi - Screens to capture: 36 states, each at 2 screen widths = 72 images"*
(decision log, 2026-09-30). **Build from these images, not from text** (B14 rule 42), in our UI
standard (rule 44): the images say what is on the screen and how it is arranged; spacing, sizes,
type and components come from our kit. Every figure, name and date is example data (rule 37).

One product page, four steps (Scope · Check · Sign off · Send) with a Calculating panel between
Check and Sign off. These are its **states**, not separate screens. The element-by-element read of
them, including what is deliberately absent, is `inventory.md`.

## How to open the mock-up

- **Click through it:** open `mockup.html` in any browser (it is self-contained; its only external
  request is the Archivo webfont, and without network it falls back to the system sans-serif —
  which is what these PNGs show). The dashed strip at the top switches the Scope states
  (Continuous · Gap · Overlap · Warnings · Problems) and the Check states (Checking · Results ·
  Module down); everything else is reached by clicking, as a clerk would.
- **Drive a state from a script** (how these PNGs were made, in a scratch copy that is never
  committed): replace the line `function render(){` with
  `window.__S=S;window.__r=()=>render();function render(){`, load the copy in Playwright
  (Chromium at `/opt/pw-browsers`, `reducedMotion: 'reduce'`), set fields on `window.__S`
  (`step` 0–3, `scope`, `check`, `tag`, `sel`, `fixed`, `drawer`, `list`, `open`, `loF`, `conf`,
  `ack`, `sending`, `sent`, `catchup`, `pricing`/`pp`, `prog`) and call `window.__r()`.
  Screenshots are full page, scrolled to the top, no field focused.

## Capture faults — do not copy

- **Side panels (Nobody to bill, Missing meter, Failed to draft, Fix account) are `position: fixed`**,
  so a full-page screenshot draws them — and their grey scrim — only over the first 900px of the
  page. In the product the panel and scrim cover the viewport at whatever scroll position the clerk
  is at.
- **The Check category list is cut at the panel's height** (it scrolls inside the left column), so
  the lower categories are not visible in most Check images. `17` (Blocked tile) shows Meter history
  to Accounts & units; `19` is captured with Payments & balances and Readings closed so the passed
  checks (a `✓` in place of the count) are in frame; `18` shows the search narrowing the list.
- In `18` the right pane still shows **No reading** although the search hides that tag from the list.
  In the product, a search that hides the open tag opens the first tag it does show.
- In `14` the toast reads *"Opens Meter Reads, account filled in in a new tab."* — the mock-up's own
  string assembly; a link outside the run simply opens the screen in a new tab (no toast).
- The dashed demo strip at the top of every image is a mock-up control, never built (inventory §0).

## Index — 36 states × 2 widths = 72 images

| # | Step | State | 1440 | 1280 |
|---|---|---|---|---|
| 01 | Scope | continuous | [01-scope-continuous-1440.png](01-scope-continuous-1440.png) | [01-scope-continuous-1280.png](01-scope-continuous-1280.png) |
| 02 | Scope | gap | [02-scope-gap-1440.png](02-scope-gap-1440.png) | [02-scope-gap-1280.png](02-scope-gap-1280.png) |
| 03 | Scope | overlap (Previous runs opened) | [03-scope-overlap-1440.png](03-scope-overlap-1440.png) | [03-scope-overlap-1280.png](03-scope-overlap-1280.png) |
| 04 | Scope | warnings | [04-scope-warnings-1440.png](04-scope-warnings-1440.png) | [04-scope-warnings-1280.png](04-scope-warnings-1280.png) |
| 05 | Scope | problems | [05-scope-problems-1440.png](05-scope-problems-1440.png) | [05-scope-problems-1280.png](05-scope-problems-1280.png) |
| 06 | Scope | panels collapsed | [06-scope-panels-collapsed-1440.png](06-scope-panels-collapsed-1440.png) | [06-scope-panels-collapsed-1280.png](06-scope-panels-collapsed-1280.png) |
| 07 | Scope | Nobody to bill panel | [07-scope-nobody-to-bill-panel-1440.png](07-scope-nobody-to-bill-panel-1440.png) | [07-scope-nobody-to-bill-panel-1280.png](07-scope-nobody-to-bill-panel-1280.png) |
| 08 | Scope | Missing meter panel | [08-scope-missing-meter-panel-1440.png](08-scope-missing-meter-panel-1440.png) | [08-scope-missing-meter-panel-1280.png](08-scope-missing-meter-panel-1280.png) |
| 09 | Check | checking progress | [09-check-checking-progress-1440.png](09-check-checking-progress-1440.png) | [09-check-checking-progress-1280.png](09-check-checking-progress-1280.png) |
| 10 | Check | module down | [10-check-module-down-1440.png](10-check-module-down-1440.png) | [10-check-module-down-1280.png](10-check-module-down-1280.png) |
| 11 | Check | decision tag (No reading) | [11-check-decision-tag-no-reading-1440.png](11-check-decision-tag-no-reading-1440.png) | [11-check-decision-tag-no-reading-1280.png](11-check-decision-tag-no-reading-1280.png) |
| 12 | Check | decision with rows selected | [12-check-decision-rows-selected-1440.png](12-check-decision-rows-selected-1440.png) | [12-check-decision-rows-selected-1280.png](12-check-decision-rows-selected-1280.png) |
| 13 | Check | blocking tag fixed on the row (No plan) | [13-check-blocking-fixed-on-row-1440.png](13-check-blocking-fixed-on-row-1440.png) | [13-check-blocking-fixed-on-row-1280.png](13-check-blocking-fixed-on-row-1280.png) |
| 14 | Check | blocking tag fixed on another screen (Meter swapped) | [14-check-blocking-fixed-elsewhere-1440.png](14-check-blocking-fixed-elsewhere-1440.png) | [14-check-blocking-fixed-elsewhere-1280.png](14-check-blocking-fixed-elsewhere-1280.png) |
| 15 | Check | warning tag (Base charge $0.00) | [15-check-warning-tag-1440.png](15-check-warning-tag-1440.png) | [15-check-warning-tag-1280.png](15-check-warning-tag-1280.png) |
| 16 | Check | payments tag (Paid after cut-off) | [16-check-payments-tag-1440.png](16-check-payments-tag-1440.png) | [16-check-payments-tag-1280.png](16-check-payments-tag-1280.png) |
| 17 | Check | filtered by the Blocked tile | [17-check-filtered-blocked-1440.png](17-check-filtered-blocked-1440.png) | [17-check-filtered-blocked-1280.png](17-check-filtered-blocked-1280.png) |
| 18 | Check | problem search ("meter") | [18-check-problem-search-1440.png](18-check-problem-search-1440.png) | [18-check-problem-search-1280.png](18-check-problem-search-1280.png) |
| 19 | Check | passed checks shown | [19-check-passed-checks-shown-1440.png](19-check-passed-checks-shown-1440.png) | [19-check-passed-checks-shown-1280.png](19-check-passed-checks-shown-1280.png) |
| 20 | Check | Ready to bill | [20-check-ready-to-bill-1440.png](20-check-ready-to-bill-1440.png) | [20-check-ready-to-bill-1280.png](20-check-ready-to-bill-1280.png) |
| 21 | Check | a ready account left out | [21-check-ready-left-out-1440.png](21-check-ready-left-out-1440.png) | [21-check-ready-left-out-1280.png](21-check-ready-left-out-1280.png) |
| 22 | Check | Fix-account panel | [22-check-fix-account-panel-1440.png](22-check-fix-account-panel-1440.png) | [22-check-fix-account-panel-1280.png](22-check-fix-account-panel-1280.png) |
| 23 | Check | a fixed, re-checked row (No size) | [23-check-fixed-rechecked-row-1440.png](23-check-fixed-rechecked-row-1440.png) | [23-check-fixed-rechecked-row-1280.png](23-check-fixed-rechecked-row-1280.png) |
| 24 | Calculating | progress | [24-calculating-progress-1440.png](24-calculating-progress-1440.png) | [24-calculating-progress-1280.png](24-calculating-progress-1280.png) |
| 25 | Sign off | summary with all sections open | [25-signoff-summary-all-open-1440.png](25-signoff-summary-all-open-1440.png) | [25-signoff-summary-all-open-1280.png](25-signoff-summary-all-open-1280.png) |
| 26 | Sign off | Who is billed | [26-signoff-who-is-billed-1440.png](26-signoff-who-is-billed-1440.png) | [26-signoff-who-is-billed-1280.png](26-signoff-who-is-billed-1280.png) |
| 27 | Sign off | Usage and charges | [27-signoff-usage-and-charges-1440.png](27-signoff-usage-and-charges-1440.png) | [27-signoff-usage-and-charges-1280.png](27-signoff-usage-and-charges-1280.png) |
| 28 | Sign off | Payments and balances | [28-signoff-payments-and-balances-1440.png](28-signoff-payments-and-balances-1440.png) | [28-signoff-payments-and-balances-1280.png](28-signoff-payments-and-balances-1280.png) |
| 29 | Sign off | Not in this run filtered to Nobody to bill | [29-signoff-not-in-run-nobody-to-bill-1440.png](29-signoff-not-in-run-nobody-to-bill-1440.png) | [29-signoff-not-in-run-nobody-to-bill-1280.png](29-signoff-not-in-run-nobody-to-bill-1280.png) |
| 30 | Sign off | Failed to draft panel | [30-signoff-failed-to-draft-panel-1440.png](30-signoff-failed-to-draft-panel-1440.png) | [30-signoff-failed-to-draft-panel-1280.png](30-signoff-failed-to-draft-panel-1280.png) |
| 31 | Sign off | confirmations ticked | [31-signoff-confirmations-ticked-1440.png](31-signoff-confirmations-ticked-1440.png) | [31-signoff-confirmations-ticked-1280.png](31-signoff-confirmations-ticked-1280.png) |
| 32 | Send | not ticked | [32-send-not-ticked-1440.png](32-send-not-ticked-1440.png) | [32-send-not-ticked-1280.png](32-send-not-ticked-1280.png) |
| 33 | Send | ticked | [33-send-ticked-1440.png](33-send-ticked-1440.png) | [33-send-ticked-1280.png](33-send-ticked-1280.png) |
| 34 | Send | sending | [34-send-sending-1440.png](34-send-sending-1440.png) | [34-send-sending-1280.png](34-send-sending-1280.png) |
| 35 | Send | sent, with Not in this run | [35-send-sent-not-in-run-1440.png](35-send-sent-not-in-run-1440.png) | [35-send-sent-not-in-run-1280.png](35-send-sent-not-in-run-1280.png) |
| 36 | Send | catch-up run started | [36-send-catch-up-started-1440.png](36-send-catch-up-started-1440.png) | [36-send-catch-up-started-1280.png](36-send-catch-up-started-1280.png) |

Counted: 8 Scope + 15 Check + 1 Calculating + 7 Sign off + 5 Send = **36**, each at 1440 and
1280 = **72** PNGs, matching the plan's table.

## Where the drawing is behind a ruling (build the ruling, not the picture)

- **Bill date before the period ends is a Scope refusal** (decision log 2026-09-30; changes row
  43). The drawing has no state showing it; it is listed in the Scope checks in `inventory.md` §2.
- **The Problems state (`05`) draws five of the fourteen refusals** in changes row 43. The rest
  (not allowed to run bills, cycle missing, period missing, same cycle and period already run,
  cycle has no units, cycle has no accounts to bill, Meter Reads or Customers not answering) are
  built from row 43 in the same boxes, on their own fields.
- **Period ends after today, first run for this cycle** are warnings in row 43; only the first
  is drawn (`04`, inside the Period line).
