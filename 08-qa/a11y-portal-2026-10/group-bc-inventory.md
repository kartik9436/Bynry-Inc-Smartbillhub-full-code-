# Customer portal accessibility — Groups B and C: inventory, baseline, and after

Lane **A11Y-BC**, 2026-10-23. Rulings built: decision log 2026-10-23 *"three product answers (F-18, F-17, F-11)"*, *"Groups B and C: the selectors switch on the arrow keys; B and C start together"*, and our own *"Groups B and C: how they are built"* (judgments 1–11).

This file was written **before any fix landed**, from the code at `345292ec7` (the branch tip when the lane started) and from a baseline scan of that same code in Chromium. The *After* section is added once the fixes are in.

## The findings and their defect rows

| Finding | WCAG | Defect | What the tester saw |
|---|---|---|---|
| F-02 | 4.1.3 | `DEF-CWP-10547` | After every submit the message is a plain new element; live regions stay empty, focus does not move (37 of 37 runs) |
| F-03 | 1.3.1 · 3.3.1 · 3.3.2 · 4.1.2 | `DEF-CWP-10548` | No input gets `aria-invalid` or `aria-describedby`; required is an asterisk only |
| F-11 | 3.3.1 · 3.3.3 | `DEF-CWP-10549` | My details accepts phone `abc` and ZIP `1`; clearing the phone is ignored ("Saved on 0 accounts") |
| F-18 | 3.3.1 · 3.3.3 | `DEF-CWP-10550` | Forgot password says "Check your email." for an invalid address; sign-in has one message for every failure, even empty |
| F-22 | 3.3.2 · 4.1.2 | `DEF-CWP-10551` | On Report, Track, Set up login and Ask for a plan the reason a button is disabled is a `title` tooltip only |
| F-04 | 2.4.3 | `DEF-CWP-10552` | Focus drops to the body after the Ask cards, the selectors and 34 of 37 submits |
| F-17 | 3.2.2 | `DEF-CWP-10553` | The language and account selectors change the page with no warning |

*Our reading of which finding id is which*: the decision log names B as F-02, F-03, F-11, F-18, F-22 and C as F-04, F-17, and the task text lists the findings in that order. The tester's report itself is not in the repository.

## Shared roots (measured, not assumed)

1. **F-03 — built, not wired.** `components/primitives.tsx` `TextInput` / `SelectInput` / `DialInput` have supported `invalid`, `describedBy` and `required` since `DEF-CWP-9215`. On the pre-change tree: **104 `FormField`s in 42 files, 72 drawn required, 22 sites pass `invalid`, 18 pass `describedBy`**, and `required` reaches `aria-required` only where a caller passes it a second time. `FormField`'s own error line was already an always-present polite region (`DEF-CWP-9215`).
2. **F-02 — the page-level message is conditionally mounted.** 41 message sites render `{refused ? <p …> : null}` (or a `role="alert"` mounted with its text). A region inserted together with its text is not reliably read; and nothing moves focus to it.
3. **F-04 — one `.focus()` in the whole portal** (`signin/UpdateEmail.tsx:49`). Every control that REPLACES itself (an *Ask →* card, a Send that becomes its result, a selector whose page re-renders) leaves focus on the body.
4. **F-22 — the kit's `CommitButton` puts its reason on `title=` and nowhere else.** `DEF-CWP-4866` wrapped it per screen (`HeldCommit`) and wrote *"the fix belongs in the kit"*; five screens then hand-built the same `disabled title=` pattern.
5. **F-11 — `_clean("")` means *do not touch*.** An emptied phone box became `None` and nothing was written, so 0 accounts changed. No format check ran on the contact path although `apps/portal/applications.py` has `phone_ok` and `US_ZIP_RE`.
6. **F-18 — sign-in sends whatever was typed.** Forgot-password already refuses a blank or malformed email on the screen (`DEF-CWP-10380`, 2026-10-22); sign-in did not, so an empty form got *"Those details do not match."*.

## Every site, before changing anything

Counted by `inv.py` (a regex count over the pre-change tree — approximate by nature; each row was then read by hand).

| File | fields | drawn required | pass `invalid` | pass `describedBy` | submit sites | page messages | title-only reasons | open/replace controls | `.focus()` |
|---|---|---|---|---|---|---|---|---|---|
| `agreements/AgreementAcceptance.tsx` | 2 | 2 | 3 | 1 | 2 | 0 | 0 | 0 | 0 |
| `agreements/AgreementPage.tsx` | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `arrears/HelpPaying.tsx` | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| `bill-link/BillLinkCard.tsx` | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `bill-link/BillLinkPage.tsx` | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `components/MailingAddress.tsx` | 5 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `components/PortalDateField.tsx` | 1 | 1 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |
| `components/heldCommit.tsx` | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `components/primitives.tsx` | 0 | 0 | 2 | 0 | 1 | 2 | 3 | 0 | 0 |
| `details/AddAccount.tsx` | 3 | 3 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `details/EmailCodeStep.tsx` | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| `details/MyDetails.tsx` | 5 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 0 |
| `details/Preferences.tsx` | 1 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 0 |
| `guest/ApplicationCustomFields.tsx` | 1 | 1 | 3 | 2 | 0 | 0 | 0 | 0 | 0 |
| `guest/ApplicationFeeCard.tsx` | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `guest/ApplicationPreferences.tsx` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `guest/ApplyForService.tsx` | 10 | 7 | 3 | 3 | 1 | 2 | 6 | 1 | 0 |
| `guest/CoApplicantCard.tsx` | 4 | 1 | 3 | 3 | 0 | 0 | 0 | 1 | 0 |
| `guest/HelpPage.tsx` | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `guest/QuickPay.tsx` | 2 | 2 | 0 | 0 | 2 | 1 | 0 | 0 | 0 |
| `guest/QuickPayCheck.tsx` | 3 | 3 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| `guest/QuickService.tsx` | 5 | 4 | 0 | 0 | 1 | 1 | 0 | 2 | 0 |
| `guest/ReportProblem.tsx` | 5 | 3 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `guest/StartService.tsx` | 4 | 3 | 1 | 2 | 1 | 1 | 2 | 0 | 0 |
| `guest/TrackAnything.tsx` | 2 | 2 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `methods/Autopay.tsx` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `methods/Methods.tsx` | 2 | 2 | 0 | 0 | 1 | 3 | 0 | 0 | 0 |
| `payments/PayNow.tsx` | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `payments/PayNowCheck.tsx` | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| `payments/PayNowDone.tsx` | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| `plans/AskForPlan.tsx` | 3 | 2 | 0 | 0 | 1 | 1 | 2 | 0 | 0 |
| `plans/PlanOffer.tsx` | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 |
| `requests/AskAQuestion.tsx` | 3 | 2 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| `requests/DisputeBill.tsx` | 3 | 2 | 0 | 0 | 2 | 1 | 0 | 2 | 0 |
| `requests/StopOrRestart.tsx` | 6 | 3 | 0 | 0 | 1 | 3 | 2 | 5 | 0 |
| `requests/TrackRequest.tsx` | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| `shell/PortalShell.tsx` | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `signin/Enrol.tsx` | 7 | 7 | 0 | 0 | 3 | 4 | 1 | 0 | 0 |
| `signin/ForgotPassword.tsx` | 3 | 3 | 2 | 2 | 4 | 7 | 1 | 0 | 0 |
| `signin/FrontDoor.tsx` | 2 | 2 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| `signin/UpdateEmail.tsx` | 6 | 6 | 0 | 0 | 5 | 3 | 0 | 0 | 1 |
| `usage/SendReading.tsx` | 4 | 2 | 3 | 4 | 2 | 1 | 0 | 0 | 0 |
| **total (42 files)** | **104** | **72** | **22** | **18** | **47** | **41** | **21** | **11** | **1** |

### Title-only instructions (F-22) — every `title=` read

The portal holds about 180 `title=` occurrences. **All but the rows below are a component PROP called `title`** (`PageHeader`, `Panel`, `ErrandCard`, `SectionTitle` …), which renders a heading, not a tooltip. The HTML `title` attribute that carries an instruction:

| Site | Control | Reason text | Visible elsewhere? |
|---|---|---|---|
| `components/primitives.tsx` `CommitButton` (all callers: Report, Track, Quick pay, Quick pay check, Ask a question, Dispute, Track a request, Send a reading, Methods, Add account, Update email …) | the commit | the caller's `reason` | **No** — only the per-screen `HeldCommit` wrapper drew it |
| `components/primitives.tsx` `HeldButton` | held control | `reason` | Yes, but not tied by `aria-describedby` |
| `signin/Enrol.tsx:380` (Set up your login) | Create my login | *Type it twice* | No |
| `signin/ForgotPassword.tsx:354` (choose a new password) | Save | *Type it twice* | No |
| `plans/AskForPlan.tsx:296` (Ask for a plan) | See the plan | `askHeld` | No |
| `requests/StopOrRestart.tsx:404` | Continue | `commitHeld` | No |
| `guest/StartService.tsx:341` | Check | `checkHeld` | No |
| `guest/ApplyForService.tsx:1177, 1472, 1869` | Continue / Send | `heldTitle(…)` | No |
| `plans/PlanOffer.tsx:355, 365, 375` | Accept / Different terms / Decline | `actionsHeld` | Yes (`data-plan-actions-held`), not tied |
| `components/primitives.tsx:1711, 1739` (usage bars) | a chart bar | the bar's figure | Chart text is Group D/E's (contrast/charts), not this lane's — **left, named here** |
| `accounts/MyAccounts.tsx:365, 386` · `accounts/YourAccount.tsx:423` | row icon links | *Open account …* / *Pay …* | They also carry an accessible name; a tooltip on an icon is B14 rule 3's row-action pattern — **left, it is not an instruction** |

### Asterisk-only required (F-03)

Every asterisk is drawn by `FormField required` (`<span aria-hidden="true"> *</span>`), with ONE hand-built exception: `guest/ApplicationCustomFields.tsx`, which draws its own label and already sets `aria-invalid` and its own error region. **72 drawn-required fields**, of which the pre-change scan found `aria-required` on only the few whose caller passed `required` twice.

### Bad-value inputs (F-11, F-18)

| Box | Before | Ruled |
|---|---|---|
| My details · Cell phone | `abc` saved | *"Enter a 10-digit phone number."* (screen and server) |
| My details · ZIP code | `1` saved | *"Enter a 5-digit ZIP."* (screen and server) |
| My details · Cell phone emptied | ignored, *"Saved on 0 accounts."* | removed, *"Phone removed."* (+ *"Text reminders stop without a phone."* when on) |
| Sign in · Email | sent as typed | *"Enter a full email address, like name@example.com."* before sending |
| Sign in · Password empty | sent | *"Enter your password."* before sending |
| Forgot password · Email | already refused on screen (`DEF-CWP-10380`) as *"Please enter a valid email."* | the ruled sentence |

### Open / replace / remove controls (F-04)

| Screen | Control | Replaces | Back / close |
|---|---|---|---|
| `CWP-010` Ask (`guest/QuickService.tsx`) | six *Ask →* cards | the card grid → the form | *Back to the list* |
| `CWP-010` Ask | *Send* | the form → *Asked* | — |
| Dispute a bill (`requests/DisputeBill.tsx`) | step 1 → step 2 | the step | `back-to-step-1` |
| Stop or restart (`requests/StopOrRestart.tsx`) | *what* → *when* → *check* → *sent* | the step | `back` ×2 |
| Apply for service (`guest/ApplyForService.tsx`) | four steps | the step | `back` ×2 |
| Co-applicant (`guest/CoApplicantCard.tsx`) | add / remove | the card | remove |
| Documents (`guest/ApplicationDocuments.tsx`) | remove a file | the row | — |
| Forgot password, Enrol, Update email, My details email code | each step | the step | — |
| Every route change (tab, link, brand) | the whole page | — | — |

### Tabs, sort, paging, filters, toggles, pickers (F-04, F-17)

| Control | Where | Kind |
|---|---|---|
| Tab bar | `shell/PortalShell.tsx` | route change |
| Sort headings, pager, filter chips | `components/listTable.tsx` (Bills, Payments, Documents, Readings, Requests) | in place |
| `SegmentedChoice` | Usage (months), Payments (owing only), Requests (open/all), Preferences | in place (radiogroup) |
| Bill month | `home/Home.tsx` `home-bill-month` | in place |
| Account selector | `shell/PortalShell.tsx` `AccountSwitcher` | re-renders the page |
| Language selector | `shell/GuestLanguage.tsx` | re-renders the page |

## Baseline (BEFORE), Chromium, private copy of the dev database

World: `sbh_a11y_bc_walk`, a `pg_dump` copy of the dev database (one utility, *Brazos Bend*, fake `@example.invalid` people), portal switched live on the copy only, one walk password set on the copy. Frontend served from a worktree pinned at `345292ec7`. Scan: `10-scripts/a11y/portal_bc_scan.mjs`, every form submitted EMPTY with the keyboard (focus the primary, press Enter), in English and Spanish, signed out and in; every Group C control pressed with the keyboard, then Tab once.


### BEFORE — what the scan measured on `345292ec7`

Two full runs (the second with longer waits; the first had read some pages before their form arrived). Rows read "primary disabled — not pressed" where the commit was held until the form was filled: that is F-22's own case, and the scan records the title-only reason count for those pages instead.

| What | Before |
|---|---|
| Forms whose submit could be pressed empty | 13 (en + es, signed out and in) |
| …focus left on the **body** afterwards | **8 of 13** |
| …anything at all in a live region | **3 of 13** (forgot-password only, through `FormField`'s own region) |
| Sign-in, both boxes empty | nothing heard, focus on the body, neither box marked, `aria-required` 0 of 2 |
| Sign-in, `maria@` | the same — nothing caught before sending |
| Pages with a disabled commit whose reason was a `title` only | 12 pages × 2 languages |
| Six Ask cards, Enter | **12 of 12** opens and **12 of 12** Backs left focus on the body (× 2 languages) |
| Bills tab, Enter | focus on the body, nothing announced |
| Language selector, ArrowDown | switched, focus kept in Chromium, **nothing announced**, label *"LANGUAGE"* |
| Account selector | not reachable in this world (the walk login holds one account) — covered by `groupC.dom.test.tsx` |
| My details, `abc` / `1` | **saved**: the first baseline run wrote phone `abc` and mailing ZIP `1` to the copy (audit rows 05:21:30 UTC) — F-11 reproduced exactly |
| My details, phone emptied | *nothing* heard, focus on the body; the server answered `accounts_updated: 0` |

## AFTER — the same scan on the fixed tree (final run, `STRICT=1`: **0 keyboard/announcement failures**)

| What | After |
|---|---|
| Forms pressed | 16 |
| …focus left on the **body** | **0 of 16** |
| …anything heard | 15 of 16 — the one that says nothing is not a submit: Stop or restart's *Continue* opens step 2 and focus moves to its `h1`, which is read. Payment methods' *Add a method* now lands on *"Confirm it is you"* / *"Confirma que eres tú"* (it stayed on the button in the first after-run, and was fixed) |
| Sign-in, both boxes empty | *"Check these fields. Email: Please enter your email. Password: Enter your password."* (assertive), both boxes `aria-invalid` + `aria-describedby` + `aria-required`, focus on the summary, nothing sent |
| Sign-in, `maria@` | *"Enter a full email address, like name@example.com."* — Spanish *"Escriba un correo completo, como nombre@example.com."* |
| Forgot password, `maria@` | the same ruled sentence, summary focused |
| Title-only disabled reasons | **0** pages (was 12 × 2) |
| Bills tab, Enter | focus on *"Your bills"* `h1`, heard once (*"Sus facturas"* in Spanish) |
| Sign-in success → Home | focus on `main` and the page title heard — **Home draws no `h1` at all**, which is lane A11Y-D's (headings) and is named for them below |
| Language selector, ArrowDown | switched at once, focus kept, *"Página en español"* heard, label *"Language (changes the page)"* / *"Idioma (cambia la página)"* |

The keyboard walk `10-scripts/a11y/portal_bc_walk_f11_ask.mjs` (exits 1 on any failure): **40 of 40 PASS**, English and Spanish —

```
PASS  en six Ask cards drawn — 6
PASS  en ask-re_read opens: focus on the form heading — h1 "A meter reading looks wrong"
PASS  en ask-re_read Back: focus returns to the card — button[ask-re_read] "Ask →"
… (all six cards, both directions, both languages)
PASS  en sign-in success: focus not on the body — main …
PASS  en abc / 1: both boxes invalid — phone "Enter a 10-digit phone number." · ZIP "Enter a 5-digit ZIP."
PASS  en abc / 1: focus on the summary
PASS  en phone emptied: heard — "Saved on 1 account. Phone removed. Text reminders stop without a phone."
PASS  en never 'Saved on 0 accounts'
PASS  es phone emptied: heard — "Guardado en 1 cuenta. Teléfono eliminado. Sin teléfono no hay recordatorios por SMS."
WALK PASS
```

⚠ **One consequence the walk found, stated rather than hidden:** after the old code had stored ZIP `1`, the first *phone emptied* save on the fixed code was refused with *"Enter a 5-digit ZIP."* — the screen now refuses a stored malformed ZIP until it is corrected. That is the ruling (*"refused on the field, never stored"*) applied to data the old code let in; the customer sees which box and why.

## What was NOT changed, and why

| Item | Why |
|---|---|
| Usage chart bars' `title` (`primitives.tsx` `UsageBars`) | Chart text is a different group (charts, week 10 of the contract) |
| Row icon links' `title` (`MyAccounts`, `YourAccount`) | Not an instruction: B14 rule 3's row-action tooltip, and each carries an accessible name |
| `details/EmailCodeStep.tsx` *Confirm* disabled with no reason at all | No `title` and no catalogue sentence exists for it; a new reason is new copy for a state the finding did not name — listed for the next pass |
| `home/Home.tsx` bill-month `<select>` has no label | 1.3.1 labelling, not a B/C finding; it now announces its change. Listed for the next pass |
| Signed-in Home has no `h1` | Headings are lane A11Y-D's; route focus falls back to `main` and the title until it has one |
| The server's `portal.reset.email_invalid` text | Kept at *"Please enter a valid email."*: the ruled sentence is 7 words and G33 caps a server refusal at 6; the screen shows the ruled sentence (decision log, judgment 11) |
| Native `required` attribute | `aria-required` only — the native one would put the browser's own bubble over our message |
| VoiceOver, NVDA, Firefox, Safari | Could not be run in this environment; everything above is Chromium (Playwright) and jsdom |
