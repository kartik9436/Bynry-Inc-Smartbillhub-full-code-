# J45 — Paperless consent taken, then withdrawn (a timestamp and the wording version they saw, never dated in the future, one control from withdrawal, a row that is never deleted — and an always-print column that is honest)

---
id: J45
tier: 2
rules: [BR-CWP-087, BR-CWP-026, BR-CWP-083, BR-CWP-086, BR-CWP-010]
stories: [US-CWP-014, US-CWP-028]
# Wiring: every story above cites `J45` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J45.spec.ts`. Release 1 (taking the
# consent on CWP-009) · release 2 (CWP-024/025). Release 3 in the flow document
# is the notifications channel it feeds.
# ⚠ CR-068 R5/R6: paperless is a RECORDED CONSENT, not a toggle; existing
# paperless customers are NOT asked again; the consent is taken on the
# new-connection form and applies from the next customer onward. A migration
# back-filling consent rows for existing customers INVENTS A CONSENT NOBODY GAVE.
# ⚠ CR-068 R4: print is the FLOOR on bills, receipts, notices and plan letters —
# the preferences screen must not offer an off switch that does nothing.
---

**Intent.** Two halves of one recorded fact. **Taken**: on the new-connection form the
applicant ticks *Send my bills and letters by email* and the product writes a
`portal_consent` **row** — kind, **the wording version they actually saw**, a timestamp
that **may never be in the future**, the screen it was taken on. **Withdrawn**: one control
on *How we contact you* sets `withdrawn_on`; **the row is never deleted**. Around it, two
honest columns: the **always-print** floor on bills, receipts, notices and plan letters —
rendered as `ALWAYS`, with **no control**, rather than an off switch that quietly does
nothing — and the eleven-language picker whose choice is the variant the next document is
rendered with.

**Upstream leaves (handoff in).** J32's applicant **Daniel Okafor** on `CWP-009` (release 1);
J36's session for **Maria Alvarez**, `1408 Elm St · A`, who is an **existing paperless
customer** — her consent recorded **21 Sep 2025** (⚠ deliberately in the past; the
blueprint shipped one nineteen days **after** its own *today*), wording
`paperless-v1-2025-09`. Notification rule catalogue with per-event channels — *Your bill ·
Payment received · Payment overdue · Instalment coming up · Usage looks high · Planned works
near you* — post `ALWAYS` on the four print-floor classes. Two `DeliveryReturnEvent` rows on
Maria's account and `bad_address = true` (J47). Locale `Español (México)` among eleven.
Tenant `oak-ridge`. Clock **2 Sep 2026**.

**This journey leaves (handoff out).** ONE new `portal_consent` row for Daniel's request
(`wording_version = paperless-v1-2026-09`, `agreed_on` = the submit moment, `taken_on_screen
= CWP-009`); Maria's 2025 row with **`withdrawn_on`** set and `taken_on_screen = CWP-025`
on the withdrawal, **still present**; a changed mobile with its audit row; **no** consent row
for any customer who never ticked. Notifications reads the consent to route bills by email
**as well as** print.

**Fixture.** Screens `CWP-009` (the tick) → `CWP-025` (*How we contact you*) → `CWP-024`
(*Your details*). New mobile `(512) 555-4218` → `(512) 555-4219`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (row · constraint · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | Daniel, `CWP-009` — ticks *Send my bills and letters by email* (helper *We print them as well. You can go back to paper at any time.*), *Send my application ✓* | ONE `portal_consent` row: `kind = paperless`, **`wording_version = paperless-v1-2026-09`**, `agreed_on` = now, `taken_on_screen = CWP-009`, `withdrawn_on` NULL. Scoped to tenant and the request's account | **A consent without a wording version is not a consent** — assert the column is NOT NULL and equals the version rendered. A double-click → one row. The `ConsequenceBox`'s *Records how you want your bills sent* is the only sentence about it | BR-CWP-087 |
| 2 | **negative · the absent consent** — a second applicant sends **unticked** | The application succeeds and **no consent row is written**. An absent consent is **not** a withdrawn one | Assert row count unchanged; no `withdrawn_on` anywhere | BR-CWP-087 · `US-CWP-014` TC-2 |
| 3 | **negative · never in the future** — a fixture attempts `agreed_on = now + 19 days` | **Refused by a database constraint** — not by the screen. The blueprint's own §26 lists this repair | `CHECK (agreed_on <= now())` or equivalent; assert the insert fails on PostgreSQL | BR-CWP-087 · `US-CWP-014` TC-4 |
| 4 | **negative · existing customers are not asked again** | Maria (paperless since 21 Sep 2025) sees **no** consent prompt on sign-in, on `CWP-022` or anywhere. **Assert no migration created a consent row for any customer who did not tick on `CWP-009` or `CWP-025`** — `SELECT count(*) FROM portal_consent WHERE taken_on_screen NOT IN ('CWP-009','CWP-025')` is **zero** | The consent applies **from the next customer onward**; a back-fill invents a consent nobody gave | `CR-068` `R6` · BR-CWP-087 |
| 5 | Maria — `CWP-025` *How we contact you* | `PreferenceGrid` WHAT WE SEND / POST / EMAIL / TEXT / IN THE PORTAL: *Your bill · Every month* **`ALWAYS`** On On On · *Payment received* **`ALWAYS`** On Off On · *Payment overdue* **`ALWAYS`** On On On · *Instalment coming up* **`ALWAYS`** On On On · *Usage looks high* `—` On Off On · *Planned works near you* `—` On On On. **PAPER**: *Paperless billing On* / *You agreed **21 Sep 2025*** / paragraph *Bills, receipts, notices and plan letters are always printed as well. Paperless changes where we send them, not whether they exist.* / `Button(outline)` *Go back to paper*. **LANGUAGE**: `Select` *Español (México)*, helper *Eleven languages available.* | **The always-print column is a rule, not a bug.** The `ALWAYS` cell **offers no control** on the four floor classes; `—` where post does not apply. The *in the portal* column is a **real switch** on every row, not a decorative one (`US-CWP-067` TC-2). The agreed date is shown **from the row** | `CR-068` `R4` · BR-CWP-087 |
| 6 | **negative · the floor** — `PUT details/preferences` with post **off** for *Your bill* | **Refused** — the endpoint must refuse to switch off print on bills, receipts, notices and plan letters **rather than accept a value it ignores**. Switching **email off** for *Payment received* is **accepted** — that one genuinely can be switched off | Turning the **portal** off for *Payment received*: the row stops appearing on `CWP-053` **and post still goes** — assert the outbound row still names post (J47) | `CR-068` `R4` · BR-CWP-083 · `US-CWP-028` TC-3/4 |
| 7 | *Go back to paper* (`POST details/paperless/withdraw`) | Maria's 2025 row gains **`withdrawn_on` = now**; `taken_on_screen` on the withdrawal records `CWP-025`; **the row is not deleted**. The **PAPER** panel now reads *Paperless billing Off* with the withdrawal date. ONE audit row naming **Maria Alvarez** | Withdrawal is **one control away**. The next bill's outbound rows carry **post only**; the previous bills' rows are untouched. Withdrawing twice → the second is a no-op, not a second row | BR-CWP-087 · hard rule 7 |
| 8 | `CWP-024` — changes the mobile to `(512) 555-4219`, *Save changes ✓* | The new value on reload **and an audit entry naming Maria Alvarez as the actor**. The screen says *Changes here reach every account on this login* — **one save, four accounts updated** (J37's set) | **negative:** posting a new **legal name** to `PATCH details` is **refused with the request route named** — assert `customer.last_name` unchanged. Name and account holder change **who owes the money**, so they go through a request a person checks. Two returned letters show **above** the address field (J47) and fixing the address clears the flag | BR-CWP-026 · BR-CWP-086 · `US-CWP-028` TC-1/2/8/10 |
| 9 | The language picker → *Français* | `customer.locale = fr-FR`; the **next** document is rendered with the template **including its language variant** — and where the class has no `fr-FR` variant the tenant-default variant renders (T7-06's fallback law), **never a blank** | Eleven catalogues; the pin includes the language (BR-NOT-006) | `US-CWP-028` TC-9 |
| 10 | **tenant isolation** | Saving details with a Pine Hill session touches **only Pine Hill's** customer row; the consent row carries Pine Hill's tenant and account; RLS `FORCE` on `portal_consent`; an Oak Ridge session cannot read or withdraw it | `app.tenant_id` from the path before the write | BR-CWP-010 · hard rule 1 |
| 11 | **INVARIANCE** | Every consent row carried a wording version and a timestamp not in the future; no row was ever deleted — taken and withdrawn are two timestamps on one row; nobody already paperless was asked again; print never switched off on the four floor classes and the screen never pretended it could; every write was audited under the actor's name; a public form (step 1) created a request and a consent and **changed no account** | The four print-floor classes went to post on **every** bill in the fixture, paperless or not | BR-CWP-087 · `CR-068` `R4` · BR-CWP-026 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The **portal** column's rows being **delivery** of anything | `OQ-1399` — the portal waits; post and email remain the delivery record (J47) |
| b | The email actually **sending** | Customer email sending activates in the email wave (W6, `BR-INT-007`). The outbound row's channels are asserted; delivery is not |
