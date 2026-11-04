# CR-085 step 1 · lane 4 — **defect re-verification · the 24 specifications · the 12 unratified rules**

<!-- ── Trace ──────────────────────────────────────────────
     Change:  CR-085 step 1 lane 4 — IDENTIFY ONLY.
     Rules:   the audits 13-wireframe-delta.md and 14-layout-audit.md are
              dated 2026-09-05 and say "before citing a row here as current,
              open the screen." Every row below was re-read at b4063d1e6 and,
              where it names something a browser can see, opened at
              http://127.0.0.1:8401 on 2026-09-11.
     ───────────────────────────────────────────────────── -->

## 1 · The open / partially-fixed `DEF-CWP` rows that touch this lane

The register holds **274 `DEF-CWP` rows, 82 of them `open` or
`partially-fixed`**. Searched two ways — by the six screen ids
(`CWP-020`, `CWP-022`, `CWP-023`, `CWP-024`, `CWP-025`, `CWP-065`) and by the six
component paths — **six rows** land in this lane. Each was re-verified, not
re-quoted.

---

### `DEF-CWP-3986` — *"six components the drawing names have never been built"* · `partially-fixed`

**THE PART THIS LANE OWNS IS FIXED, AND THE ROW ALREADY SAYS SO.** The lane
brief flagged `KpiRow`/`KpiTile` on Home as *"squarely yours — verify it."*

**Verified three ways:**

* `07-frontend/src/portal/components/primitives.tsx:2062` exports `KpiRow` and
  `:2095` exports `KpiTile`;
* `Home.tsx` imports and composes both;
* **and they render.** Measured on `/brazosbend/portal/home` at 1280:
  `[data-kpi-row]` is `display:grid`, `grid-template-columns:
  253px 253px 253px 253px`; `[data-kpi="balance"]` is present with
  `data-kpi-lead="true"`.

The row's own `prevention` column already records this — *"PART FIXED
2026-09-05: KpiRow/KpiTile landed with CWP-022 and CWP-033 now composes them —
the two screens the row named for that piece."* **No further action for this
lane.** What keeps the row open is `WarningBar`, which needs a consumer and a
sentence, and which belongs to `CWP-036` / `CWP-049` / `CWP-017` — none of them
mine.

⚠ **What the row does NOT say, and what this lane found, is a spacing
divergence in the piece that was built** — the tile's side padding and the row's
gap. That is `CR-085-lane4-04-spacing-rule-39.md`, and it is a new finding rather
than a re-opening of this row.

---

### `DEF-CWP-4000` — *"28 signed-in portal screens carry no heading of any kind"* · `partially-fixed`

**STILL OPEN, AND `CWP-022` IS THE ONE THAT IS LEFT IN THIS LANE.** Counted at
the tip:

| Screen | `PageHeader` | `<h1>` | Verdict |
|---|---|---|---|
| `CWP-022` Home | **0** | **0** | ⚠ **still no heading** |
| `CWP-023` All my accounts | 3 | — | fixed (renders *All my accounts*) |
| `CWP-065` Your account | 2 | 1 | fixed |
| `CWP-020` Add another account | 3 | — | fixed |
| `CWP-024` My details | 4 | — | fixed |
| `CWP-025` How we contact you | 3 | — | fixed |

Measured in the browser at both widths: Home's first visible words below the
account line are **`YOUR ACCOUNT`** — a `SectionTitle` inside a card — at 390 and
**`YOUR ACCOUNT`** at 1280. Five of six repaired; **one to go, and it is the
screen the lane brief calls the one a customer in difficulty lands on.**

---

### `DEF-CWP-4205` — *"G13 is red at the tip … `listTable.tsx` renders a column heading behind `props.iconsHeading` and nothing passes it"* · `open`

**THE PROP IS GONE.** `grep -rn "iconsHeading" 07-frontend/src/` at `b4063d1e6`
returns **one hit and it is a comment** — `listTable.tsx:239`, *"`iconsHeading?:
string` override here from the day this component…"*. There is no prop
declaration and no read.

**So the dead-UI half of the row is fixed.** ⚠ **The other half — *"G13 IS RED
AT THE TIP"* — is a claim about the gate, not about this file, and this lane did
not run the gate suite** (its brief is identify-only and running the full suite
against a shared checkout is not this lane's to do). **Whoever closes this row
must read `G13`'s output, not this paragraph.** Recorded exactly that way
because hard-won law 7's *"proved red, then never read"* is what turns a fixed
file into a row nobody dares close.

---

### `DEF-CWP-4362` — *"two live documents cite `DEF-CWP-4137` for the `CWP-024` sign-in controls, and that id is a different defect that is already fixed"* · `open`

**BOTH HALVES CONFIRMED, AND THE UNDERLYING GAP IS REAL.**

* The citation error stands: `13-wireframe-delta.md` row 24.1 and
  `10-execution-plan.md`'s *LEFT OPEN* paragraph both point at `DEF-CWP-4137`,
  which is the `CWP-063` plan-ends copy defect, `fixed` in `873ee0a5`.
* **And the thing they describe is true.** Measured on `/my-details` at both
  widths: the `YOUR SIGN-IN` panel renders *Password changed · Sep 11, 2026*,
  *Codes go to · Your mobile*, *Devices signed in · 2* — **three facts and not
  one control.** There is no *Change password*, no *Sign out everywhere*, and
  nothing to act on the two signed-in devices the panel names.

This is **B14's own rule about control rows read backwards**: *"a row of
controls holds only things a person can PRESS"* — here a row of facts that
invites a press and offers none. Delta **M-08**.

---

### `DEF-CWP-4469` — *"`MyAccounts.dom.test.tsx` fails intermittently in a full-suite run and passes alone"* · `open` · low

**NOT RE-VERIFIED, AND SAYING SO IS THE HONEST ANSWER.** Reproducing it needs a
full-suite run against a shared checkout, which this lane's brief excludes. The
row names *the case named `DEF-CWP-3954`, the door to `CWP-020`* — and **that
door is live**: measured on `/accounts` at both widths, `Add another account`
renders and resolves to `/brazosbend/portal/accounts/add`, which opens
`CWP-020`. So the behaviour under test is correct in a browser; the flake is a
test-isolation question and it stays open.

---

### `DEF-CWP-4491` — *"the portal's own preference endpoint stores ANY string as a customer's language, including one no catalogue can draw"* · `open` · low

**STILL OPEN; A BROWSER CANNOT SEE IT AND THIS LANE DID NOT WRITE TO THE SERVER
TO PROVE IT.** What the browser does show is the screen it reaches:
`/my-details/preferences` offers **`Not chosen yet` · English · Español** — *2
languages available* — which is the tenant's own set, so the picker itself
cannot produce the bad value. The row is about
`portal_self_service.update_delivery_preferences` accepting one from elsewhere.
Backend validation, another lane's surface.

---

## 2 · The 24 specifications — which touch these six screens

The register is blueprint section 12. Every row reads `UNVERIFIED` and the
document says so of itself: *"engineering fills this column in from the code,
one row at a time, and **several are expected to come back already done**."*

**By the `SCREENS` column, exactly one specification names this lane's screens —
and it names all of them.** A second reaches them by its own text.

| Spec | Its own `SCREENS` | Touches this lane? | Built · part-built · not |
|---|---|---|---|
| **CPB-23** — *Every screen carries its How-you-get-here row* | **`all`** | **YES — all six** | **NOT BUILT, and not buildable as written.** The spec's own text is the finding: *"⚠ THE DOCUMENT CLAIMS THIS IS ALREADY DONE AND IT IS NOT. Rule E says every screen's spec now carries a How you get here row; **23 of the 60 do**."* **All five of this lane's drawn screens (25, 27, 28, 29, 57, 58, 59) carry `No door named.`** — they are seven of the 37. ⚠ **The spec asks for a row in the DOCUMENT, and what would make it true is a DOOR IN THE PRODUCT.** This lane found the doors as built and they are in the table below. |
| **CPB-17** — *A signed-out visitor at a signed-in address is offered a sign-in* | `53 · 54` | **YES by its own words** — *"True of every signed-in screen, not just one."* | **NOT BUILT.** Measured signed-out at both widths on all six: *"**Failed** · We could not open this page. · You're signed out. Sign in again to continue. · [Retry] [Download error report] [Cancel]"*. Exactly the grey failure panel the spec describes, including the *Download error report* control. |
| CPB-01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 24 | 6, 7, 8, 32, 34, 35, 36, 37, 40, 43, 44, 47, 48, 50, 51, 52, 53, 55, 56, 60, 1, 3 | **no** | — |

⚠ **Two of them are pointed AT by this lane's screens without naming them, and a
reader should know which:** the drawn `Set up autopay` on Home 25 is the door
into **CPB-02**'s flow (`Autopay can actually draft a payment`, screen 40), and
the drawn `Pay $191.00 now` on Home 25 and One account 28 is the door into
**CPB-01** (`A customer can pay by card`). **Neither door is built** (deltas
**H-03** and **O-06**) — so if `CPB-01` and `CPB-02` were finished tomorrow,
**nothing on Home or on One account would point at them**, which is hard-won law
2's mirror waiting to happen on the two most expensive specifications in the
register.

### The doors this lane's screens actually have, read out of the running app

| Screen | Inbound doors found | Outbound doors found |
|---|---|---|
| `CWP-022` Home | frame nav *Home* | `/bills` `/usage` `/payments` `/requests` `/my-details` `/ask-for-a-plan` `/overdue` · `/accounts` **only when the login holds more than one account** |
| `CWP-023` All my accounts | `/my-details` (*All my accounts*) · Home's lead-tile sub-line, multi-account only | `/accounts/add` (twice) |
| `CWP-065` Your account | **`/my-details` and nowhere else** | `/final-bill` `/stop-or-restart` `/bills` `/usage` `/equipment` `/requests` `/documents` |
| `CWP-020` Add another account | `/accounts`, from both copies of the button | `/accounts` (back) · `/visit` |
| `CWP-024` My details | frame nav *My details* | `/my-details/preferences` `/accounts` `/account` `/stop-or-restart` |
| `CWP-025` How we contact you | `/my-details` | `/my-details` (back) only |

**The one that matters:** `CWP-065` — the whole picture of one property — is
reachable from **one link on one screen**, and the drawing puts its door on Home
(*→ Everything about this account*). See delta **H-07**.

---

## 3 · The 12 unratified drawn rules — which of these screens depend on them

Appendix table A, the `home` column. **These are PROPOSALS, not law.** Twelve of
the twenty-four rules the blueprint states are marked `NO HOME — stated only
here`, meaning nothing in this repository states them. Ten of the twelve reach
this lane's screens.

| Rule | As stated | This lane | Where it bites |
|---|---|---|---|
| **R-05** | *Amount due and due date appear in the same place on every screen.* | **DEPENDS — and it is already broken** | Home calls the figure **`BALANCE`**, `/account` calls the same `KpiTile lead` **`WHAT YOU OWE`** (delta **O-07**). One shape, two words, two screens. If R-05 is ratified this is a defect; today it is a proposal being missed. |
| **R-06** | *Never ask a customer to compute — show the difference, not two numbers.* | **DEPENDS** | Home's drawn usage tile is *5% less than July · 12% more than last August* — a difference, not a figure. Not built (and gated behind `CPB-06`/`CPB-07`). |
| **R-07** | *One filled button per screen.* | **DEPENDS — all six** | Drawn primaries: `Pay $191.00 now` (25, 28), `Pay all three` (27), `Add it` (29), `Save` (57, 58). Built: `/my-details` has **one** filled (`Save changes ✓`) and four outline errands — correct; `/preferences` has **one** (`Save language ✓`); `/accounts/add` has **one**; **Home and `/account` and `/accounts` have NONE**, because the drawn primary is the one that is missing (**H-03**, **O-06**, **A-05**). |
| **R-09** | *Never make a customer remember an account number to do something.* | **DEPENDS — and `/accounts/add` is the live tension** | The screen asks for the account number **of another property**, which the drawing itself draws, so the rule as stated would forbid the screen the same document draws. **This is a rule that needs a scope clause before it could be ratified**, and this lane is the screen that shows why. |
| **R-10** | *Bad news never appears without the way out beside it.* Appendix: *"stated only here, and it is the strongest rule on the page."* | **DEPENDS** | Home's `PAST DUE` state: *"the help link sits **inside it**, not elsewhere"*; `/account`'s: *"the past-due treatment, with **the three ways out**"*. Neither is built (no balance on this fixture, and no such branch in either component). What Home does have is the `Paying by instalments?` rail with `Ask for a plan` and `Where things stand` — the right instinct, in the wrong place: it is beside the rail, not beside the news. |
| **R-13** | *A route existing is not a door.* Appendix: *"the finding that produced this whole block. **Nothing in the repo states it.**"* | **DEPENDS — all six** | Every drawn screen in this lane carries `No door named.` This lane read the doors out of the running app rather than out of the document — see the table in §2 — and found one screen (`CWP-065`) with a single inbound link. **This is the rule whose absence from the repo the blueprint most wants fixed.** |
| **R-15** | *Position, order and wording never move; a back-link sits under the bar, never inside it.* | **DEPENDS** | Built: `/accounts/add` (*← All my accounts*) and `/preferences` (*← My details*) both place it under the bar, correctly. **`/account` has no back-link at all** though the drawing gives it *← Accounts* (delta **O-02**). |
| **R-19** | *The portal is a second channel; every bill is printed regardless.* | **DEPENDS — `CWP-025`** | This is the rule the built `/preferences` screen actually implements — *"Turning these off stops the email or the text, never the letter. **We post everything, always.**"* — and it is **incompatible with the drawing's `ONE OF THESE MUST STAY ON`** (delta **P-03**). **R-19 and screen 58 cannot both be right.** |
| **R-22** | *Three states — loading, empty, failed — can never render as the same picture.* | **DEPENDS — Home** | `HomeView` draws one bare `Card` with one grey sentence for **all three** (delta **H-16**). The words differ; the picture does not. The drawing asks for *"skeleton cards of the right height"* and none exists. |
| **R-23** | *No sentence states a fact it does not derive.* Appendix: *"with its own evidence: twenty-three of thirty-eight were wrong."* | **DEPENDS — `CWP-025` and `CWP-065`** | `/preferences` states *"Your bills and letters use the language above; **this site follows it**"* — a claim the product enforces today but which the same document's screen 59 says is false in principle (delta **P-09**). And `/account`'s drawn consequence sentences (*"a paper bill costs $2.00 a month"*, *"you would pay $171.40 a month"*) are figures the screen would have to derive and does not have — which is **why they are not built**, and that is R-23 being obeyed rather than broken. |
| R-04 | *No emoji as a section marker.* | no | The drawing uses 🏠 ⚡ 💧 🚿 🗑 as **values**, not as section markers; built uses none. |
| R-18 | *Assistance is a first-class path, not a page behind a sign-in.* | no | `/help-paying` and `/protections` — another lane. Home links to `/overdue`, which is the nearest this lane comes. |

### The one recommendation this section carries

**R-13 is the only one of the twelve that is already half-enforced, and it is
the one the repo states nowhere.** `07-frontend/src/portal/routing/everyRouteHasADoor.test.ts`
exists and does exactly what R-13 asks — and its own docstring is careful about
the limit: *"It catches **no door anywhere** … It does **not** catch **a door
that is not where a person would look** … No check can find that."* All six of
this lane's screens pass it, and **`CWP-065` passes it with one inbound link
that the drawing does not draw** (**H-07**) — which is the docstring's own
sentence happening in practice. So the finding is not *add a check*; it is that
**a rule this product already enforces in code is written down in no rule
register**, so the next lane learns it only by tripping over the test.
Everything else in the list of twelve is a copy or layout proposal.
