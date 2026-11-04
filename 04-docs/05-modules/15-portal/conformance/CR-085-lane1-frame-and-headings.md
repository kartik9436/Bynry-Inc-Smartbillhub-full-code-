# CR-085 lane 1 · The frame and the heading count — all 50 portal addresses, at 390 and 1280

**Walked in a browser on 2026-09-11 against the bundle the shared stack serves** (built from
tip `b4063d1e6`), every one of the 50 addresses in `screenIds.ts`, at **390 and 1280**, with
the two frame reads stubbed live because `brazosbend` has 0 customers and 0 `portal_settings`
rows. Each screen's OWN read was left to fail, so every number here is the frame's.

---

## 1 · What renders, counted

| | at 390 | at 1280 |
|---|---|---|
| addresses walked | **50** | **50** |
| render the **signed-in shell** | **34** | **34** |
| render the **guest frame** | **13** | **13** |
| render **no frame at all** | **3** | **3** |

The three with no frame are `/help/:slug`, `/visit` and `/visit/:slug`, all answering *"We
could not find that"* — correct on this tenant, which publishes no help answers and no
service centres. `portalRoutes.tsx` records that `/visit` 404s outright when no centre is
shown, *"which is why the visit page cannot exist empty"*.

---

## 2 · The heading count, verified

**The figure to carry forward is 13 of 34, not 28** — identical at both widths, and **no
screen anywhere draws more than one `<h1>`.**

| | count |
|---|---|
| signed-in screens rendering **no `<h1>`** | **13 of 34** |
| guest screens rendering no `<h1>` | **1 of 13** — `/start-service/:draft`, which has no draft to read |
| screens rendering **two or more `<h1>`** | **0** |

**The 13 split three ways and only the third group is a fault:**

| group | screens | why |
|---|---|---|
| **headless by design** (1) | `/home` (CWP-022) | the drawing opens `PortalShell` → `KpiRow`, no page head — a title above the balance strip would push the one figure the page exists for below the fold |
| **step bar instead of a head** (2) | `/pay-now` (CWP-038), `/ask-for-a-plan` (CWP-042) | `08-screen-layouts.md` gives these a `Stepper`; a page head would say where you are twice and disagree |
| **the head is inside the success branch only** (10) | `/payment-methods`, `/account`, `/bills/:number`, `/bills/:number/document`, `/my-details`, `/my-details/preferences`, `/usage`, `/readings`, `/equipment`, `/payments` | `if (failed) return (…)` is declared **before** the `<PageHeader>` in every one of those files, so a failed or loading read throws the heading away with the content |

**Three signed-in screens already do the third group's job correctly and are the model:**
`/overdue`, `/protections` and `/money-back` each render their kicker and title **above** the
failure sentence. Filed as `DEF-CWP-4926`, which generalises the two per-screen rows a
sibling lane filed (`DEF-CWP-4846` for CWP-033/034/037, `DEF-CWP-4859` for CWP-028) into one
eight-file pass.

### And the source census says something different, on purpose

Over all 52 files carrying `data-screen`: **40 compose `@/components/PageHeader`**, **4**
write their own `<h1>` (the T7 cards), **8** write neither — of which 7 are documented and
**one is genuinely outstanding**, `usage/Usage.tsx` (CWP-033), the single remaining entry in
`pageHeadCensus.test.ts`'s `AWAITING_ANOTHER_LANE`. ⚠ **And one of that file's four
exception lists is already stale** — `STEP_BAR_INSTEAD` still lists
`requests/DisputeBill.tsx` as drawing no page head, and that file has composed
`PageHeader` since the wave-R work. Only `AWAITING_ANOTHER_LANE` is asserted in the
negative, so nothing goes red. Filed as `DEF-CWP-4927`.

⚠ **The two numbers measure different things and both are true.** The census proves
COMPOSITION; the walk proves RENDERING. `DEF-CWP-4000`'s *"28 signed-in screens carry no
heading"* was a rendering count taken on 2026-09-05 and it no longer holds — the sweep that
followed it moved the number to 13, and 3 of those 13 are correct.

---

## 3 · The two heading bars, against the blueprint

The blueprint's standards block D draws exactly two bars *"because a third would mean a
customer could not tell at a glance whether they are signed in"*. Both exist. What is in
them differs.

### The guest bar

| the blueprint draws | the product renders |
|---|---|
| `Silver Creek Water · Pay a bill · Report a problem · Prices · Help · Visit us` then `🌐 English · ☎ (281) 555-0164 · Sign in` | `Brazos Bend Utilities · Home · Help · Visit us · Pay a bill · Report a problem · Ask us for something · Track` then `English · Español · Sign in` |

Read from the DOM at 1280. Differences, in order:

* the product adds **Home**, **Ask us for something** and **Track**, which the drawing does
  not have;
* the drawing has **Prices**, which the product does not;
* the language control is **two words side by side** (`English` `Español`) rather than one
  `🌐` control — which is `DEF-CWP-4442`'s ruling working (*"currently in drop down show only
  2 elnglish and spanish"*), and it costs two slots in a row that is already full;
* the emergency phone is **not in the bar**. It is an `EmergencyBand` inside `<main>`, drawn
  first, before the screen's own heading.

**Measured height: 147px at 390 — three rows — and 96px at 1280 — two.** `DEF-CWP-4468`
records this as *"two rows in English because the nav was already full before the language
control was added"*; two rows is the DESKTOP case, and the phone case is three.

### The signed-in bar, the menu and the account line

DOM order, read from the running app: **`<header>` → `<nav>` (the six tabs) → the account
line → `<main>`.**

| band | contents | 390 | 1280 |
|---|---|---|---|
| `<header>` | brand (links to `/home`) · `Help` · `Sign out` · a two-letter avatar | **57px** | **57px** |
| `<nav>` | `Home · Bills · Usage · Payments · Requests · My details`, `gap-x-6`, wrapping | **100px** (three rows) | **50px** (one row) |
| account line | `Account 4417-0092` · `1841 Quarry Hill Ct, Silver Creek, TX 78611` | **72px** (two rows) | **40px** (one row) |

**That is 229px of frame at 390 and 147px at 1280**, before `main`'s own 24px of top padding
— **253px total on a 390 × 844 phone, 30% of the viewport.**

Against the drawing:

* **the menu is a row of its own, not in the header row.** The blueprint says *"Seven
  sections, in the header row itself, between the utility's name and the language control"*.
  The product has six tabs in a second row and `Help` in the header. **This matches the PO's
  own ruling of 2026-09-08 read literally** — *"here header bar should ahve menu - and below
  that we should have a line for account"* — so it is recorded and not filed.
* **the account line carries two of the drawing's four facts.** It has the account number and
  the service address; the customer's **name** appears only as an avatar's initials, and the
  **amount due and its due date** are absent from the frame entirely. The drawing puts
  `Marcus Bell · 1841 Quarry Hill Ct… · Account 4417-0092` on the left and `$191.00 due Aug
  22` on the right. Filed as `DEF-CWP-4925`.
* the switcher is a LABEL rather than a control on a one-account login, which is
  `09-component-inventory.md` §1 working exactly as written.

---

## 4 · A finding this lane filed and then withdrew, recorded because the reasoning is the useful part

**`DEF-CWP-4924` — *a signed-in customer has no language control anywhere in the frame* — is
filed as `invalid`, and the observation behind it is true.** `PortalShell.tsx` contains no
reference to language at all; `GuestFrame.tsx` renders `GuestLanguage`. Grepping one file and
not the other is how that became a defect row.

`GuestFrame.tsx` answers it in a comment beside the control:

> ⚠ **AND IT IS THE GUEST FRAME ONLY.** A signed-in customer changes theirs on `CWP-024`,
> where the choice is STORED on their account and reaches their letters too — the PO's own
> *"Signed customer should get their own references"*. Two controls for one setting, one of
> them forgetful, is how a product tells one person two things.

So it is a **deliberate, reasoned divergence from blueprint block D** (*"Language first,
because somebody who cannot read the page must be able to fix that from anywhere"*), taken
with a PO ruling behind it and written down where the next reader would meet it. That is not
an escaped defect. **It is still a divergence the PO may want to revisit in this redesign**,
because the drawing's reason and the code's reason are both good and they disagree, so it is
named here rather than closed silently.

⚠ **The row is left in the register as `invalid` rather than deleted** — a deleted row
invites the same finding again, which is the reasoning the blueprint's own appendix uses for
its struck rows.

---

## 5 · Two things that are working, recorded so nobody spends a wave on them

* **No horizontal overflow at either width, on any of the 50 addresses.**
  `document.documentElement.scrollWidth` equals `clientWidth` everywhere. The `flex-wrap` fix
  in `PortalShell.tsx` — written after the 2026-09-08 walk measured **461px inside a 390px
  viewport** on six signed-in screens — is holding.
* **The front page's held cards are held correctly.** With the server told all six errand
  cards are `available`, two still render as disabled `Start →` buttons carrying
  `data-held="true"` — `check_my_area` and `what_things_cost`, both of which have a row in
  `holds.ts` with a reason and, for the first, a screen id to watch. That is hard-won law 2's
  mirror being managed rather than ignored.
