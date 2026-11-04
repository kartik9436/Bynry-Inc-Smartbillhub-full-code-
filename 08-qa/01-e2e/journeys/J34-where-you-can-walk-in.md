# J34 — Where you can walk in, on a day one counter is closed (three centres, two shown, Thanksgiving typed by nobody, and four of five rows saying *no*)

---
id: J34
tier: 2
rules: [BR-CWP-096, BR-CWP-093, BR-CWP-022, BR-CWP-007]
stories: [US-CWP-001, US-CWP-069, US-CWP-074]
# Wiring: every story above cites `J34` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J34.spec.ts`. Release 1.
# ⚠ THE DRAWING AND ITS OWN HOURS TABLE DISAGREE, AND THIS JOURNEY ASSERTS THE
# CLOCK. `wireframes/CWP-014.png` marks Wednesday as TODAY and reads "Closed
# today. Opens Tuesday at 9:00am" while its hours table shows Thursday 9:00am–
# 1:00pm. 2 Sep 2026 IS a Wednesday, so the sentence computed from the clock and
# the hours must read "Opens THURSDAY at 9:00am". `US-CWP-074` TC-2 repeats the
# drawing's "Tuesday". The rule (BR-CWP-096: from the clock, not a typed field)
# wins over the drawing — step 4 asserts Thursday, and the slip was filed as
# DEF-CWP-3604 and the story corrected 2026-09-03.
---

**Intent.** Nothing in this product models a physical place, so the record is new and the
screen is not — a card in Reference data with a list and an editor behind it. What nobody
publishes, and this journey does, is **what a counter cannot do**: *you cannot open or close
an account here* is the sentence that saves the journey nobody wants to make twice. Two
states carry the rest: **hidden is a real state, not a deletion** (the depot stays in the
back-office list and off the public page), and **holiday closures are typed by nobody** —
they come from the holiday calendar the utility already keeps.

**Upstream leaves (handoff in).** Tenant `pine-hill` live. Three `service_centre` rows: 1
**Main office**, `214 Cedar St, Austin TX 78702`, `(512) 555-0148`, Mon–Fri 8:00am–5:00pm,
takes cash · cheque · card · money order, allowed actions = all five, **shown**, note
*parking behind the building*. 2 **North counter**, `1190 Palm Ct, Austin TX 78758`, Tue
& Thu 9:00am–1:00pm, takes cash · cheque, allowed actions = *Pay a bill* only, **shown**. 3
**Depot — not public**, `44 Works Rd`, no hours, **`is_shown_to_customers = false`**.
Holiday calendar (Reference data, already kept): **26 November 2026 — Thanksgiving**.
Today **Wednesday 2 Sep 2026**, 10:00am tenant time. Tenant `oak-ridge` with its own two
centres.

**This journey leaves (handoff out).** Nothing money-bearing. `service_centre` row 3
re-ordered/hidden/shown as the steps say, every back-office change audited (`BR-TEN-016`
family). `CWP-038`'s *pay in person* line (release 5) reads this same record and names only
the centres that **take money**.

**Fixture.** `CWP-013` (`/pine-hill/visit`) and `CWP-014` (`/pine-hill/visit/north-counter`);
back office `CWP-074` / `CWP-075` in the **staff** app under *Reference data › Service
centres* (System Admin Sarah Miller). Clock fixture: 2 Sep 2026 (Wed), 26 Nov 2026 (Thu,
Thanksgiving), 1 Sep 2026 (Tue, 10:00am).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (record · calendar · audit) | Rule |
|---|---|---|---|---|
| 1 | Guest opens `/pine-hill` → *Visit us* → `CWP-013` | Subtitle *Two places, and what each one can do.* **Two** `CentreCard`s — the depot is **absent**. Main office: `OPEN UNTIL 5:00PM`, phone, *Monday to Friday, 8:00am – 5:00pm*, **YOU CAN HERE** five chips, *Takes Cash · Cheque · Card · Money order*. North counter: `CLOSED TODAY`, one chip *Pay a bill*, **Not here:** *you cannot open or close an account here*, *Takes Cash · Cheque* | The header link *Visit us* exists **only because** a centre is shown. The depot is **still in the back-office list** (`CWP-074`) with `StatusChip` HIDDEN — a real state, not a deletion. Public order follows the back-office **position** | BR-CWP-096 · BR-CWP-093 |
| 2 | Opens *See this centre →* on the north counter (`CWP-014`) | Back link **← WHERE YOU CAN WALK IN**, kicker **NORTH COUNTER**, title `1190 Palm Ct, Austin TX 78758`. **WHAT YOU CAN DO HERE**: *Pay a bill ✓* · *Set up a payment plan —* · *Start or close an account —* · *Hand in documents —* · *Report a problem —*, footer *One of five. The rest are at the Main office.* **TAKES PAYMENT BY** chips *Cash · Cheque*, note *No card machine here.* | **Four of the five rows say no, and that is the screen doing its job.** An unticked action renders as **cannot**, not as absent. The *Call* action is a plain outline, not brand — rule 6 reserves the brand outline for destructive commits (the layout entry records the deviation) | `US-CWP-074` TC-4/6 · B14 rule 6 |
| 3 | **the clock** — the grey status line and the hours panel | Hours × 7 with **Wednesday TODAY** bold and *Closed*; Tue and Thu *9:00am – 1:00pm*; footer *Closed 26 November — Thanksgiving*; rail ⓘ *Holiday closures are not typed in here. They come from the calendar the utility already keeps.* | The status line is **computed from the clock and the hours**, never a typed field. On **Wednesday 2 Sep 2026** the next opening is **Thursday**, so it reads *Closed today. Opens **Thursday** at 9:00am.* — ⚠ the drawing says *Tuesday*; the rule wins (frontmatter note). On Tue 1 Sep at 10:00am it reads *Open until 1:00pm* | BR-CWP-096 · `US-CWP-074` TC-2 |
| 4 | **the holiday** — the clock fixture moves to **Thursday 26 Nov 2026** | **Both** centres read closed — the main office on a weekday it is normally open — **and nobody edited the page**. Assert the closure comes from the tenant holiday calendar row, not from `service_centre_hour` | `service_centre_hour` holds **no** holiday row. Deleting the calendar row reopens both; adding one for 25 Dec closes both again. The footer sentence follows the calendar | BR-CWP-096 · `US-CWP-074` TC-3 |
| 5 | Sarah (System Admin) — `CWP-074` back office | Three rows: Main office ON THE PORTAL · North counter ON THE PORTAL · **Depot HIDDEN** (greyed). Row actions icons ✎ 👁 −. `WarningBar` *hidden is a state*; `InfoBar` holiday calendar. Reorders North counter above Main office | The public page follows the new position. An audit row for the reorder. A Billing Clerk opening this screen is refused — Settings is System Admin only (A1) | `US-CWP-074` TC-8 · BR-TEN-016 |
| 6 | **negative · hide everything** | Sarah sets `is_shown_to_customers = false` on both remaining centres | `/pine-hill/visit` and its header link, `CWP-060`'s *Where you can walk in* route and `CWP-014`'s pages are **all absent** — no empty page. All three rows remain in the back office | BR-CWP-093 · `US-CWP-074` TC-5 |
| 7 | **negative · removal is the danger tier** — Sarah presses **Remove** on a centre customers have seen | `Button(danger)` with a warning that a **printed address may still be in circulation**; the screen **prefers hiding**. Removal is audited; hiding is the recommended path | Rule 6: the brand outline on a destructive commit and nowhere else on the screen | `US-CWP-074` TC-9 · B14 rule 6 |
| 8 | **negative · the guard** | The 61st `GET /public/service-centres` in one minute is refused, five or six words | Every guest endpoint sits behind the anonymous throttle; these two take no reference, so no lockout applies | BR-CWP-022 |
| 9 | **tenant isolation** | `/oak-ridge/visit` shows Oak Ridge's two centres and Oak Ridge's holiday calendar; a Pine Hill centre slug under `/oak-ridge` → not found; Sarah's Oak Ridge counterpart sees Oak Ridge's rows only | RLS `FORCE` on `service_centre`, `service_centre_hour`; `app.tenant_id` from the path before the query | hard rule 1 · `US-CWP-074` TC-7 |
| 10 | **INVARIANCE** | No database id was ever a visible value — the URL and the page use the **slug** and the **name** (B14 rule 31). Nothing money-bearing changed. Every back-office edit wrote an audit row. `CWP-038`'s *pay in person* line (release 5) names **only** the centres that take money and what they take | The depot never appeared on any public surface in any step | B14 rule 31 · hard rule 7 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | *Pay in person* on `CWP-038` naming the two centres | Rails — release 5. The record it reads is asserted here |
| b | *Get directions* opening a map | An external link (`↗`); nothing of ours to assert beyond the address |

## Walked, in a browser — added 2026-09-04 by the CR-068 wave D build lane

`10-scripts/render-checks/cr068-d-help-tips-centres.mjs`, steps 6, 7 and 8, with
the server's clock pinned to **Wednesday 18 November 2026**
(`PORTAL_CLOCK_OVERRIDE`, honoured only under `DEBUG` and therefore never on a
deployed build). ⚠ **The pin is not a convenience — it is the only way to SEE
the rule.** *Closed today · Opens Thursday at 9:00am* and *Closed November 26 —
Thanksgiving Day* are computed from the clock and the tenant's calendar, so they
can only be observed on a Wednesday in November.

⚠ **AND THE FIXTURE WRITES NO HOLIDAY ROW.** Provisioning already seeds the
eleven US federal holidays (`apps/tenancy/us_holidays.py`, PO ruling
2026-08-11), and the fourth Thursday of November 2026 is 26 November — so a
brand-new Pine Hill closes both counters on Thanksgiving having done nothing at
all, which is a better demonstration of `BR-CWP-096` than the fixture would have
been. The calendar spells it **Thanksgiving Day**, not *Thanksgiving* as
`US-CWP-074` §4 abbreviates it; the screen shows the utility's own word.
