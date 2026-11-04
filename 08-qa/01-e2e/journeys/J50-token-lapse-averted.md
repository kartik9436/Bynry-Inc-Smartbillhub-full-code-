# J50 — Token lapse averted (*Needs re-authorising by 12 September. After that, bills stop going out.* — eleven days ahead, in words, and a re-authorisation that keeps the whole run history)

---
id: J50
tier: 2
rules: [BR-INT-042, BR-INT-015, BR-INT-008, BR-INT-005, BR-INT-007, BR-INT-024, BR-INT-025, BR-INT-043, BR-INT-003]
stories: [US-INT-019, US-INT-027, US-INT-029]
# Wiring: every story above cites `J50` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J50.spec.ts`. Wave H task H5 writes it
# (`cr069-h-token-lapse.mjs`). Phase 3 LAUNCH — "a utility connects Google or
# Microsoft, and the token renews itself"; phase 3's exit test is step 6.
# ⚠ `expires_at` earns its column here: it is the difference between "email
# stopped working last Tuesday and nobody knew" and a message on the dashboard
# eleven days beforehand.
---

**Intent.** Credentials have a **lifecycle, not a moment**. The nightly expiry sweep — the
second entry in **the first beat schedule this product has ever had** — finds Silver
Creek's Microsoft 365 credential eleven days from lapsing and writes **a dated sentence in
words** in three places: the connection detail, the dashboard's attention strip, and one
email to the System Admins **through the notifications queue** (never a direct send). Alex
re-authorises through the OAuth return trip, and **the connection keeps its entire run
history** — credential v2 lands on the **same** connection row.

**Upstream leaves (handoff in).** Silver Creek Water's `email_microsoft` connection,
`production`, `working`, connected by Alex Reed 12 Aug, **twenty** run rows on S142 (bill
emails, 93 of 93 and the like); credential **v1** with **`expires_at = 2026-09-12`**. The
beat schedule (`config/settings/base.py` `CELERY_BEAT_SCHEDULE`) with `integration.sweep_due`
every minute and `integration.sweep_expiry` nightly; manifest warning window **14 days**.
Brazos Bend's `email_smtp` credential with `expires_at` **NULL**. A second tenant (Lone Star
Ridge) with its own expiring credential. Recorded OAuth fixtures — no network. Clock **1 Sep
2026**, then nightly.

**This journey leaves (handoff out).** ONE sweep run row per night (`trigger = scheduled ·
operation = expiry_sweep`); ONE queued notification row per warning day to Silver Creek's
admins; after re-authorisation, credential **v2** on the same connection (v1 inactive,
retained), `expires_at` ninety days on, the warning **cleared**, **all twenty earlier runs
still listed**. On the lapse twin: `status = not_working`, one skipped-and-recorded send run,
bills resting `queued`.

**Fixture.** Frames `54.1` (*Re-authorise this connection by 12 September. After that date,
bills stop going out. — Microsoft asks for this every ninety days. It takes about a minute
and nothing else changes — the history stays.*), `25.2` (the amber `WarningBox` on S142),
`49.2` (S141's OAuth body — one field, *Sign in with Microsoft*, *We never see or store your
password*, Cancel only). S7 dashboard attention strip.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (sentence · queue · rows · history · isolation) | Rule |
|---|---|---|---|---|
| 1 | **1 Sep, the nightly `integration.sweep_expiry`** | Finds the credential with `expires_at` inside 14 days (11 days out). Writes ***Needs re-authorising by 12 September. After that, bills stop going out.*** on **S142** (`WarningBox`, frame `25.2`) and on the **S7 attention strip**, and queues **one** email to the System Admins **through the notifications queue** | **The date is in words, never a timestamp.** The email is a queue row — integrations sends nothing itself (`BR-INT-008`); the dispatcher is the only sender. ONE sweep run row `trigger = scheduled` | BR-INT-042 · BR-INT-008 · BR-INT-015 |
| 2 | **2 Sep, the sweep again** | **One more** warning (day 10) — **not two**; the day-11 warning is not repeated | Once per day, never twice for the same day. The S8 provider-status panel shows attention, not green | `US-INT-027` TC-2 · BR-INT-015 |
| 3 | **negative · the credential with no expiry** | Brazos Bend's SMTP credential (`expires_at` NULL) is **never warned** — the sweep ignores it | An SMTP password does not lapse; a warning on it would be noise that trains people to ignore the real one | `US-INT-027` TC-5 |
| 4 | Alex (Silver Creek) opens S142 → *Re-authorise now* → S141's OAuth body (frame `49.2`) | **One** field (*Send bills from*, the signed-in identity — the tenant's **own** address) and a **Sign in with Microsoft** button; **no credential field exists in the DOM**; footer is **Cancel** only — *there is no Save here; the round trip is the save* | `POST /integrations/email_microsoft/oauth/start` returns the provider's authorisation URL bound to a **one-time state**; an unknown or expired state on return is refused | BR-INT-043 · BR-INT-005 |
| 5 | The return trip (`GET /integrations/oauth/callback`, the recorded fixture) | Credential **v2** written **on the same connection row**, `expires_at` ≈ 30 Nov 2026 (ninety days); v1 deactivated and retained; `test()` sends one real message; the warning **clears** on S142 and S7 | Token refresh through the provider; the token is **never** written to the credential table beyond the version the exchange produces (J55's `token_exchange` mode is the general rule) | BR-INT-025 · BR-INT-042 |
| 6 | **phase 3's exit test** — S142 after re-authorisation | **Every one of the twenty earlier runs is still listed.** The connection id is unchanged; only the credential version moved | A re-authorisation that created a new connection would have orphaned the history — that is the failure this step exists to catch | BR-INT-042 · `US-INT-027` TC-3 |
| 7 | **negative · the lapse** — a twin nobody re-authorises; 13 Sep | Card **Not working · Microsoft needs re-authorising**; the next send run is **skipped and recorded** (a run row, `attempted 0`, the reason in words); bills **rest `queued`** — there is no shared-sender fallback | The queue architecture stands; nothing is lost. Customer SENDING is the W6 flip regardless (`BR-INT-007`) | BR-INT-042 · BR-INT-024 · BR-INT-016 |
| 8 | **the scheduler underneath** (`US-INT-029`) | The nightly cadence is evaluated **in the tenant's timezone** — Silver Creek `America/Denver`, Brazos Bend `America/Chicago`; on **2026-11-01** (DST ends) and **2027-03-14** (DST starts) each fires **once at its own midnight** — not twice, not zero. 300 connections' start times are **spread by a deterministic per-connection offset, identical across two sweeps** | A run still `running` when the next window is due → **no second run**; a row `outcome = skipped` *skipped — the previous run is still going*. `manual` has **no due time and is never swept**. `PATCH … cadence = "*/5 * * * *"` is refused — the vocabulary is `nightly · hourly · manual`. A `sandbox` connection is never handed real work | BR-INT-024 · BR-INT-026 |
| 9 | **tenant isolation** | Lone Star Ridge's expiring credential produces a warning to **Lone Star Ridge's** admins only; Silver Creek's admins receive **one** email about **their** credential. Two tenants' nightly runs fire at **their own** midnights; the scope key carries the tenant | RLS `FORCE`; per-tenant queue rows | hard rule 1 · `US-INT-027` TC-6 |
| 10 | **INVARIANCE** | The sentence was dated and in words in all three places; the email went by queue; the history survived; the credential versioned rather than overwritten; the SMTP credential was never warned; nothing on any screen was a UUID | Every lifecycle event wrote `audit_log` with masked hints | BR-INT-042 · BR-INT-014 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The re-authorisation against **live** Microsoft | Recorded fixtures, no network in tests; the provider-sandbox contract test is a separate scheduled run, never CI |
| b | Customer bills actually **sent** through the renewed token | W6 — email sending activates with notifications (`BR-INT-007`) |
