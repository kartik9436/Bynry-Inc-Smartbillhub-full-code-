# J58 — Allowed, then stopped ⚠ conditional `OQ-INT-1482` (Maria allows *SunPath Installers* twelve months of usage; two months later Priya stops it; the installer's very next request is refused — not their next nightly collection)

---
id: J58
tier: 2
rules: [BR-INT-036, BR-INT-035, BR-INT-053, BR-INT-044]
stories: [US-INT-046]
# Wiring: `US-INT-046` cites `J58` in its `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J58.spec.ts`. Wave P: task P2 proves the
# BOUNDARY now (`cr069-p-consent-boundary.mjs`); task P3 — the feature and this
# journey's steps 3–9 — runs only "when OQ-INT-1482 is ruled (a)"
# (`cr069-p-allowed-then-stopped.mjs`). Phase 5, conditional.
# ⚠ CONDITIONAL ON OQ-INT-1482 — IS LETTING A CUSTOMER AUTHORISE A THIRD PARTY
# TO COLLECT THEIR USAGE IN SCOPE AT ALL? A market decision (yes with the partner
# surface · later · no). NOTHING IS BUILT UNTIL IT IS RULED: every writer of
# `integration_consent` raises `NotImplementedError("OQ-INT-1482")`, S145 and
# S146 have no route and no `screenIds.ts` row, and the consents route answers
# exactly as an unknown route does. The table exists from wave A so that, if
# ruled in, this is "rung 5 rather than rung 1" already paid for. Frames 56.1
# and 57.1 are SHAPE ONLY — "the only two in the pack that are" — and their
# wording is not settled. The grantee's READS also need OQ-INT-1481.
# ⚠ Maria Alvarez here is BRAZOS BEND's customer on ACC-1048 (US-INT-046 test
# data) — a different tenant from the portal journeys' Pine Hill fixture.
---

**Intent.** *"Nothing in this product has ever held a permission that its owner can revoke,
and a revocation that takes effect on the next scheduled run rather than the next request is
the classic way it is built wrong."* A consent **belongs to the customer**: scoped (which
accounts, how much history), it **expires**, it can be **withdrawn**, rows are **kept after
revocation** — *who could see my data last year* is a question a customer is entitled to ask
— and it is **checked on every request**, so a revocation one second ago refuses the very
next call. The staff view exists because the customer will **ring up rather than log in**. It
is a consent feature wearing a standard's name (Green Button's) and **the standard is not
claimed**.

**Upstream leaves (handoff in).** `integration_consent` **exists and holds no rows**
(migration `0001`, RLS `FORCE`). Brazos Bend customer **Maria Alvarez**, account **`ACC-1048`**,
with a portal session (the portal, `CR-068`). A registered partner **SunPath Installers** with
an issued key (J54's shape) and an allowlist. Actor **Priya Menon** (Billing Clerk) on S145.
Clock **3 Sep 2026** → **3 Nov 2026**. Lone Star Ridge.

**This journey leaves (handoff out) — boundary now.** Zero `integration_consent` rows; a
test asserting every write path raises; no S145/S146 route. **When ruled (a):** ONE consent
row `granted_by = Maria (the customer)`, `grantee = SunPath Installers`, `scope = {usage,
months: 12}`, `granted_at = 2026-09-03`, `expires_at = 2027-09-03`, then `revoked_at =
2026-11-03`, `revoked_by = Priya` — **never deleted**; `inbound_read` runs for the installer's
reads while the consent stood; a refused read at `2026-11-03 09:00:01`.

**Fixture.** Frames `56.1` (S146, the customer decides — *Bright Solar wants to see your water
use … You decide what they get, and for how long. Which account · How much history · Until
when · Allow · No thanks*), `57.1` (S145, staff view — *WHO THIS CUSTOMER HAS ALLOWED · Bright
Solar · Water use, 12 months · 12 Mar 2027 · Stop it · Green Audit Co · Water use, 3 months ·
Stopped 14 Aug · ended*). The grantee's request at `2026-11-03 09:00:01`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (rows · routes · refusal · isolation) | Rule |
|---|---|---|---|---|
| 1 | **boundary · today** — Alex opens Settings → Integrations; Priya opens an account; a request hits `/…/settings/integrations/consents` and `GET /portal/consents` | **No consent card, no consent tab, no route** — the consents routes answer **exactly as an unknown route does**. `screenIds.ts` has **no row** for S145 or S146 | `integration_consent` holds **zero rows**; a test asserts **every write path** raises `NotImplementedError("OQ-INT-1482")` — quoted green in the walkthrough | `OQ-INT-1482` · `US-INT-046` TC-6 |
| 2 | **boundary · the standard is not claimed** | Nothing anywhere says *Green Button* is supported, compatible or certified; the conformance report (`GET /integrations/conformance`, regenerated from the registry) lists **no** claim for it | The words we may use about any standard are `OQ-INT-1483`; MultiSpeak and Green Button are not claimed regardless | BR-INT-053 |
| 3 | **when ruled (a)** — Maria, S146 (frame `56.1`): *SunPath Installers wants to see your water use.* Which account **12 Silver Creek Rd** | All of mine · How much history **12 months** · Until when **1 year** · *Allow* | ONE `integration_consent` row: **`granted_by` = the customer, not a member of staff**; `scope = {usage, months: 12}`; `expires_at = +12 months`. The blue note: *They will see how much water you used and when. **They will not see your bills, your payments or your contact details.** You can stop this at any time.* | *Allow* is a portal write — the portal's fourth kind (a preference) — and the wording on the frame is **not settled** | BR-INT-036 · `US-INT-046` TC-1 |
| 4 | The installer's first read (SERVE runner, J54's surface, within scope) | **Succeeds** and is **recorded** as an `inbound_read` run — the grantee's reads are recorded like any partner's; Maria's S146 lists *SunPath Installers · Water use, 12 months · until 3 Sep 2027* | The consent is checked **before** the page is served | BR-INT-035 · BR-INT-036 |
| 5 | **negative · scope** — the installer requests **bills**; a request one second **after** `expires_at` | Both **refused** — outside the granted scope; expired. No run for the expired request | Scope is what **and how much history**; time is a hard edge | `US-INT-046` TC-4/5 |
| 6 | **3 Nov 2026, 09:00** — Maria rings; Priya, S145 (frame `57.1`), presses **Stop it** (danger tier) | `revoked_at = 2026-11-03T09:00:00`, `revoked_by = Priya`; the row **stays** — *ended*. Note on the screen: *Stopping takes effect on **the next request they make**, not on their next scheduled collection.* | A clerk needs this because the customer will ring rather than log in. The row is **never deleted** | BR-INT-036 · B14 rule 6 |
| 7 | **the exit test** — the installer's request at **09:00:01** | **Refused** — the very next request, one second later, **not the next nightly collection**; the run record says why | Checked on **every** request by the SERVE runner; a revocation cached until the next run is the classic wrong build | BR-INT-036 · `US-INT-046` TC-2 |
| 8 | Maria asks *who could see my data last year* — S146 | Lists the **ended** consent with its dates (granted 3 Sep 2026 · stopped 3 Nov 2026 by the office) — the row was never deleted | `revoked_at`, never a delete — the one question the history exists for | BR-INT-036 · `US-INT-046` TC-3 |
| 9 | **tenant isolation** | A grantee key valid for a Brazos Bend customer used against **Lone Star Ridge** → **unknown, in the declared way**; the consent rows are under Brazos Bend; RLS `FORCE` | The allowlist refusal reveals nothing | hard rule 1 · BR-INT-044 |
| 10 | **INVARIANCE** | Until ruled: **nothing mounted, nothing written, the raise asserted.** When ruled: the consent was the customer's grant, scoped and dated; every read under it was recorded; the stop took effect on the next request; the history survived the stop; no standard was claimed | The portal's write here is a **preference** — one of its four permitted kinds — and it changed nothing on the account | `OQ-INT-1482` · BR-INT-036 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | Steps 3–9 at all | **`OQ-INT-1482`** — is this in scope? A market decision. The boundary (steps 1–2) is what runs today |
| b | The grantee's **reads** | `OQ-INT-1481` — who may authorise a partner to read (J54) |
| c | The wording on S145/S146 | *Shape only · wording not settled* — the two frames say so themselves |
