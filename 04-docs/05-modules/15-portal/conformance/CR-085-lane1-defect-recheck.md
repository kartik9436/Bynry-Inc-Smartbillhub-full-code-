# CR-085 lane 1 · The frame-related defect slice, re-opened on the running product

**Both existing audits — `13-wireframe-delta.md` and `14-layout-audit.md` — are dated
2026-09-05 and say of themselves: *"before citing a row here as current, open the screen."***
This file does that for the frame-shaped rows among the 82 open and partially-fixed
`DEF-CWP` defects, at tip `b4063d1e6` on 2026-09-11.

⚠ **WHERE THE PRODUCT WAS READ RATHER THAN OPENED, THE ROW SAYS SO.** The shared stack's
`brazosbend` tenant has **0 customers, 0 accounts, 0 invoices and 0 rows in
`portal_settings`**, so no signed-in portal screen renders there and the guest half answers
the holding page. The frame was measured with the two frame reads (`portal/public/front`,
`portal/session`) stubbed live in the browser against the real built bundle; anything deeper
than the frame could not be rendered and was read in the source instead.

---

## Verdict table

| defect | status in the register | verdict now | evidence |
|---|---|---|---|
| **DEF-CWP-4000** — 28 signed-in screens carry no heading | partially-fixed, high | **Largely fixed. The headline number no longer holds.** | Source census over all 52 files carrying `data-screen`: **40 compose `@/components/PageHeader`**, 4 write their own `<h1>` (the four T7 cards), **8 write neither** — and 7 of those 8 are documented (step-bar screens, the two whose head lives on the `*Page.tsx` wrapper, and `CWP-022` which the drawing deliberately heads with the balance strip). **One is genuinely outstanding: `usage/Usage.tsx` (CWP-033)**, which is the one entry still in the census's `AWAITING_ANOTHER_LANE`. See the caveat below — a source census proves composition, not rendering. |
| **DEF-CWP-3986** — six components the drawing names have never been built | partially-fixed, medium | **Fixed. All six now exist.** | `KpiRow`/`KpiTile` (`portal/components/primitives.tsx`, and used on `home/Home.tsx` line 222 and `usage/Usage.tsx`) · `DocumentPreview` (primitives, used by `bills/PrintedBill.tsx`) · `WarningBar` and `ToggleChips` (`features/tenancy/SettingsServiceCentres.tsx`) · `DialInput` (primitives, used by `signin/Enrol.tsx`). The row's own wording — *"verified — Enrol.tsx renders the code as a plain TextInput"* — is now false. |
| **DEF-CWP-3988** — ten drawn screens have no address | partially-fixed, medium | **Still real, and unchanged.** | `portalRoutes.tsx` still registers **50** routes and `screenIds.ts` still holds **50** rows. None of the ten named screens (accept an invitation, people with access, send your own reading, moving out, documents we need from you, messages, answers while signed in, an answer attached to a bill, a usage tip, everything we sent you) has gained an address. `holds.ts` still carries the rows that stand in for three of them. |
| **DEF-CWP-4190** — CWP-032 draws no heading on the branch that has a final bill | open, medium | **Fixed.** | `bills/FinalBill.tsx` now renders `{head}` in **four** places, lines 106, 116, 130 and **159 — the success return** — and carries a comment naming this defect and the general lesson (*"when a sweep adds one element to a component with early returns, the branch that matters is the LAST one"*). |
| **DEF-CWP-4144** — CWP-057 prints the same heading twice | open, low | **Fixed.** | `arrears/Overdue.tsx` heads the page `portal.overdue.title` = *"Past due"*; the card that used to repeat it is gone and the file records the change in a comment. The `whereThingsStand` key survives as the LINK LABEL on `CWP-027` and Home, which is correct. |
| **DEF-CWP-4183** — four wave-M screens print their own title twice | open, low | **Half fixed — two of the four are still live.** | **Still duplicated:** `plans/YourPlan.tsx` heads *"Your payment plan"* (line 114) and titles its first card with the identical key (line 225); `plans/PlanOffer.tsx` heads *"A plan we have offered you"* (line 122) and repeats it at line 217. **Fixed:** `plans/LevelPay.tsx` now heads *"Budget billing"* with the card titled *"This month, either way"*. `plans/AskForPlan.tsx` (CWP-042) draws a step bar instead of a head, so it cannot duplicate one. |
| **DEF-CWP-4468** — the guest header is two rows in English | open, low | **Still real and understated.** | Measured at **390px: the guest header is 147px tall** — three rows, before any content. At 1280 it is one row. The signed-in header is 56px at both widths, but the signed-in frame adds an account line and a tab strip under it (see `CR-085-lane1-spacing-anchors.md` §5). |
| **DEF-CWP-4203** — the requests hub has no door to the full list | open, low | **Still real.** | The source door map finds `/requests` linked from `accounts/YourAccount` and `shell/PortalShell` (the tab). No control on `CWP-046` points at a full list — the component's comment *"the door to the full list is the page lane's"* is still there, which is hard-won law 1's shape: a plan nobody is holding. |

---

## The caveat that matters on DEF-CWP-4000, stated plainly

**A source census proves that a file composes `PageHeader`. It does not prove a heading
renders.** `pageHeadCensus.test.ts` says this about itself and is right to.

Opened in a browser with the frame reads stubbed, several signed-in screens sit in a
**loading branch that draws no heading at all** — `/pay-now` renders the frame, the account
line, the tab strip and the single sentence *"Reading what you owe…"*, with **no `<h1>`
anywhere on the page**. That is `DEF-CWP-4190`'s mechanism one level out: the head is inside
the branch that has data, and the branch a customer sees on a slow phone has none.

**That is a different finding from the one DEF-CWP-4000 records**, and it is filed
separately rather than folded into that row.

---

## One stale exception list, found while verifying the above

`pageHeadCensus.test.ts` keeps four lists of screens that legitimately draw no page head.
Three of the four are asserted in the negative, so they cannot rot. **`STEP_BAR_INSTEAD` is
not**, and it is already stale: it lists `requests/DisputeBill.tsx` as *"CWP-055 — step bar
(T2)"*, and that file has composed `PageHeader` since the wave-R work (line 25 imports it,
line 209 renders it) **as well as** a `Stepper` at line 247. Nothing goes red, because the
only negative assertion in that file covers `AWAITING_ANOTHER_LANE`.

The cost is small today and the shape is the one the repo keeps paying for: an exception list
that is only ever read as permission.
