# CR-145-BRC08 — Six session and lockout rules become per-utility settings, within fixed limits

**Raised:** 2026-09-28, by the Product Owner.
**Branch:** `claude/confirm-understanding-3ktufc` (`BRC08`). Block `CR-145`–`CR-149`, recorded in
`12-governance/14-id-reservations.md` before the branch started. `allocate.py cr --verify 145` at
push time.
**Version:** `2.389.0` — allocated once for the whole change request. ⚠ **ONE LANE OWNS IT**
(`SESS-DOCS`); the backend and frontend lanes were told not to bump, because two lanes bumping is
`DEF-GOV-3756`'s collision and `G35` holds four literals in lockstep.
**Classification:** **CHANGE.** The product does exactly what was agreed — `BR-IDN-025` and
`BR-IDN-026` were signed on 2026-08-08 and built to — and the owner of those rules has now asked
for something different. That is the PO's own test (*"CR is change in product, defect is product
does not do what is expected"*) answered on the *yes* side. ⚠ **ONE PART OF IT IS NEVERTHELESS A
DEFECT AND IS CALLED ONE BELOW:** *"Keep me signed in"* has never worked.
**Screen-shaped:** yes — Settings → Security (S8) gains five controls and loses two choices, and
the sign-in screen's tick box becomes conditional. **Drawing:** `05-prototype/r10-2026-08-16/`
`SMARTBillHub.dc.html`, the Security tab — there is **no blueprint PDF for identity**; checked with
`git -c core.quotePath=false ls-tree -r --name-only <ref> | grep -i 'pdf$'` across the refs, with
the `core.quotePath` flag that `DEF-GOV-6236` exists for. **Screen owner:** the frontend lane.

---

## 0 · What arrived, in the requester's words

> *"Im okay with these limit"*

Said in acceptance of this table, which is what the signature covers and therefore all it covers:

| Setting | Before | Admin may choose | Default |
|---|---|---|---|
| Sign-out after inactivity | 30 / 60 / 240 / 480 min | **15 / 30 / 45 / 60** | **60** |
| Hard limit after sign-in | 12 h, fixed | **4–12 hours** | **12** |
| Offer *"Keep me signed in"* | always | **on / off** | **on** |
| Its length | 30 days, fixed | **1–30 days** | **30** |
| Wrong passwords before lockout | 5, fixed | **3–10** | **5** |
| Lockout length | 15 min, fixed | **5–60 minutes** | **15** |

**A second ruling the same day, PO verbatim *"Yes"*:** the customer portal keeps following the
staff setting and gets **no setting of its own** — *"one setting is less for an admin to get
wrong."*

⚠ **AND A THIRD THING WAS OFFERED AND DECLINED, WHICH IS RECORDED BECAUSE A DECLINED DEFAULT IS
NOT ONE AWAITING IMPLEMENTATION:** stricter defaults for newly provisioned utilities — a 7-day
*"Keep me signed in"* and a 30-minute inactivity timeout. **Do not introduce them.**

Both rulings are in `12-governance/02-decision-log.md` under *2026-09-28 · SIX SESSION AND LOCKOUT
RULES BECOME PER-UTILITY SETTINGS*, with the worked figures put to the PO.

---

## 1 · Classification — and why the *"Keep me signed in"* half is filed differently

**The five settings are a CHANGE.** Nothing was wrong; the agreement moved.

⚠ **THE COOKIE IS A DEFECT AND IS NOT DRESSED UP AS A FEATURE.** Verified in the code before this
was written: all three `set_cookie` calls — `identity/api.py:183`, `tenancy/api.py:215`,
`portal/api.py:379` — pass **no expiry at all**, so the sign-in cookie is a session cookie and
dies when the browser closes. *"Keep me signed in"* therefore does the one thing it exists to
prevent, and has since it shipped. The server-side 30-day refresh was doing its job; the cookie
carrying it was not.

**This matters for the register and not only for tidiness.** Filing a miss of ours as a "change"
converts our error into the customer's new requirement, silently — §1 of this process says so, and
this is the case it describes. The wiring is done under this CR because it is the same code path,
but it is **a fix, and the CHANGELOG says fix**.

---

## 2 · What is being reversed — quoted, with the supersedes chain

| Signed statement, in its own words | What happens to it |
|---|---|
| `BR-IDN-025`: *"lockout 5 failed → 15-min lock"* | **CONFIRMED-AS-AMENDED** 2026-09-28. Both numbers become per-tenant settings (3–10, 5–60 min) at today's values. Supersedes CONFIRMED (PO Q&A R4, 2026-08-08). |
| `BR-IDN-025`: min 8 · upper+lower+number · symbol optional · no forced expiry · last-5 history · temp password 7 days | ⚠ **UNCHANGED AND STAYS FIXED.** Named here because it sits in the same rule, the same code block and the same screen. A lane widening this ruling to the password half has widened a ruling nobody made. |
| `BR-IDN-026`: *"idle timeout default 60 min (tenant-configurable 30 min–8 h), absolute 12 h; 'Keep me signed in' = 30-day trusted-device refresh, off by default"* | **CONFIRMED-AS-AMENDED** 2026-09-28. All four numbers become settings; ⚠ **the idle range NARROWS rather than widens** — 240 and 480 are withdrawn. ⚠ **"off by default" is STRUCK**: what defaults ON is whether the box is OFFERED. Supersedes CONFIRMED (PO Q&A R4, 2026-08-08). |
| `apps/portal/session.py:105`, `ABSOLUTE_LIFETIME_HOURS = 12` | Reversed as a constant; reads the tenant's hard limit. |
| `EP-IDN-04` §5's closing note: *"Lockout thresholds (5 → 15 min), last-5 history, temp-password validity (7 d) and the absolute session lifetime (12 h) are platform-fixed v1 values … not tab controls."* | **Three of the four become tab controls.** Amended in place, **not deleted** — it is the only statement anywhere that the last-5 history and the 7-day temp password are NOT settings. |

**No ❄️ FROZEN B4/B5 figure is touched.** Nothing here is money math; no finance re-sign is
required, and none is being taken as read.

---

## 3 · Impact — the eleven surfaces

| Surface | What it comes to |
|---|---|
| **User stories** | `US-IDN-001`, `US-IDN-003`, `US-IDN-010`. None becomes obsolete. `US-IDN-010` grows five controls. |
| **Business rules** | `BR-IDN-025`, `BR-IDN-026` amended (done, commit `9cdc7251c`). `BR-IDN-006` and `BR-IDN-019` cite them and are re-read rather than re-stamped — neither states a figure. |
| **Build steps / waves** | No reordering. B-tasks (backend) before F-tasks (frontend): the select cannot offer 15 until the endpoint accepts it. |
| **Documents** | `EP-IDN-01`, `EP-IDN-04`, `09-infra/01-deployment-architecture.md` §10.3, `docker-compose.yml`'s beat note, `06-backend/.env.example`, `CHANGELOG.md`. |
| **Code** | `identity` (services, api, models, migration), `portal` (session), `tenancy` (cookie), frontend Settings → Security and the sign-in screen. ⚠ **None of it is 🔒** — no RLS policy, no rating math, no ledger posting, no money rounding. The migration is ordinary. |
| **Test cases** | `US-IDN-001` TC-8 · `US-IDN-003` TC-3, TC-7, TC-8 · `US-IDN-010` TC-2, TC-3. **All amended, none deleted** (D4). Eight further cases are named as owed. |
| **E2E journeys** | None asserts a session timeout. `10-scripts/session_expiry_walk.mjs` ends a session by deleting the cookie or expiring the row, so it is **indifferent to the interval** and keeps passing — correctly. |
| **Seed data** | New tenants get today's values, so the demo utility is unchanged. ⚠ **The declined stricter defaults must not be seeded.** |
| **Open questions** | **Answers** `OQ-025` and `OQ-026` further than their original closures (both already CLOSED → `BR-IDN-025`/`026`; their bodies now describe a world with fixed numbers and are amended with the rules). **Re-opens nothing.** ⚠ Checked in both directions by reading, not by grep, per this step's own instruction. |
| **The demo fixture** | A person driving the product sees a Security tab with six settings at the values the old screen printed as fixed. Coherent. |
| **THE DRAWING** | `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`, Security tab. ⚠ **r10 draws four timeout choices including 4 h and 8 h, and the product will draw four INCLUDING 15 MINUTES AND EXCLUDING BOTH.** The drawing loses to a later PO ruling, which is the one case B14 rule 41 sends to the PO — and it has already been there: this table IS the ruling. No escalation is owed. |

### ⚠ The one visible change, and it is the only one

**Utilities on 240 or 480 minutes are migrated to 60**, so their staff are signed out **up to
seven hours earlier** than before. Everything else in this change is invisible on day one, because
every default equals today's behaviour.

**How many utilities that is: the sum of the two counts the upgrade prints while it runs.** It is
deliberately not estimated here. The migration writes one `audit_log` row per utility it moves and
prints its total, so the number is a fact somebody can look up rather than a figure this document
invented.

⚠ **MEASURED ON THE DEMO DATABASE 2026-09-29 (`T10`'s lane) AND IT CAME OUT BACKWARDS, WHICH
CONFIRMS THE REASON RATHER THAN CONTRADICTING IT.** The two data migrations were unapplied, `480`
minutes was planted on the one seeded utility, and they were re-applied:

    identity/0007  →  CR-145: 1 utility(ies) moved …  (naming the utility, 480 -> 60)
    identity/0008  →  CR-145 (per tenant): 0 …
                      SUM = 1

**On a real deployment those two numbers are the other way round** — the migrating account is not
a superuser, row security answers *no rows* to its cross-utility read, `0007` prints `0` and
`0008` carries the answer (`DEF-IDN-7504`). **This container's database account IS a superuser**,
the one account for which that restriction cannot exist. **THE SUM IS STABLE UNDER BOTH; WHICH
LINE CARRIES IT IS NOT** — so no document, and no sentence said to the PO, may quote one line
alone. The `audit_log` row was checked on the same run: `settings.security_updated`, before
`{"session_timeout_minutes": 480}`, after `{"session_timeout_minutes": 60}`.

---

## 4 · What is already built and is now wrong

### Code already shipped on the old rule

| Where | What it says today | Why it is now wrong |
|---|---|---|
| `07-frontend/src/features/identity/SettingsSecurityTab.tsx:59` | `export const SESSION_TIMEOUT_OPTIONS: readonly number[] = [30, 60, 240, 480];` — **the list is typed out by hand in the front end**, a second copy of the backend tuple | Offers two withdrawn choices and cannot offer 15. ⚠ **Two hand-maintained copies of one list is the `SignupWizard.tsx` failure in another module**: the backend can accept 15 and the screen will never show it, with `tsc` and every test green. |
| `06-backend/apps/identity/services.py:76` | `SESSION_TIMEOUT_OPTIONS = (30, 60, 240, 480)` | The server-side allow list, used at `services.py:830`. **This is the one that decides**, and a select is not a validation. |
| `06-backend/apps/identity/services.py:66–76` | `LOCKOUT_MAX_FAILED = 5`, `LOCKOUT_MINUTES = 15`, `ABSOLUTE_SESSION_HOURS = 12`, `TRUSTED_DEVICE_REFRESH_DAYS = 30` under the banner *"Platform-fixed v1 values"* | Four of the six settings, still constants. The banner itself becomes false. |
| `06-backend/apps/portal/session.py:105` | `ABSOLUTE_LIFETIME_HOURS = 12` | Must read the tenant's hard limit (ruling 2 — the portal gets no setting of its own). |
| `identity/api.py:183` · `tenancy/api.py:215` · `portal/api.py:379` | three `set_cookie` calls that pass **no expiry** | The live defect above. |
| **The sign-in screen's printed sentence** — `07-frontend/src/features/identity/SignInPage.tsx:57–58`, `SIGN_IN_LOCKOUT_ATTEMPTS = 5` and `SIGN_IN_LOCKOUT_MINUTES = 15`, rendered at line 306 | *"After 5 failed attempts sign-in pauses for 15 minutes"* | ⚠ **A THIRD HAND-TYPED COPY OF THE LOCKOUT RULE, AND IT WAS NOT IN THIS CR'S ORIGINAL SCOPE** — found by the frontend lane while wiring `F3` and filed as `DEF-IDN-7500` rather than fixed inside a tab commit. A utility that chooses 3 tries and a 60-minute lock gets a screen telling its staff something else. ⚠ **It is NOT trivially fixable and that is why it is a defect rather than a task:** the sign-in screen has **no session**, so it cannot read a policy the way the Security tab does, and publishing a utility's lockout threshold to an unauthenticated page is a disclosure question rather than a wiring one. |
| **The Security card's printed sentences** — `07-frontend/src/i18n/locales/en.json:19117`, key `settings.security.fixedValues`, and its ten sibling catalogues | *"Fixed for every utility: 5 failed sign-ins lock the account for 15 minutes, the last 5 passwords can't be reused, a temporary password lasts 7 days, and every session ends after 12 hours."* | ⚠ **THREE OF THOSE FIVE FACTS STOP BEING TRUE** — the 5, the 15 and the 12 become settings. **The password history and the 7-day temporary password stay fixed and are NOT in this change**, so the sentence is rewritten and not removed: it is the only place a clerk is told those two are fixed. ⚠ **It says _"Fixed for every utility"_, which is the clause that becomes actively misleading** — an admin reading it will not go looking for a control that is now on the same screen. **The frontend lane owns the sentence**; this CR's job is that no document repeats the stale version. ⚠ **AND IT IS NOT THE ONLY ONE — SEE THE ROW BELOW:** the same rule is printed a third time on the sign-in screen, which nobody had counted. |

### Data already written

**Every existing utility's `security_policies` row.** Five of the six columns do not exist yet and
are added with defaults equal to today's behaviour, so no row changes meaning. ⚠ **The exception is
`session_timeout_minutes`**, where 240 and 480 become unreachable values that rows still hold —
which is why the migration must **rewrite** them rather than merely stop offering them. A row left
on 480 against an allow list that refuses 480 is a utility that cannot save its Security tab at all
until it happens to change that field.

### Lanes building right now

**Three, all on this branch, and none is stopped.** Backend (B-tasks), frontend (F-tasks) and this
one (D/E/T). They are split **by file**, and the screen has **one owner** — the frontend lane — per
§6 of this process. **In-flight work LANDS; nothing is redirected.**

### ⚠ Which checks are now wrong — named by file, before any code is written

**These do not fail helpfully. Each will either fail for a reason that reads as unrelated, or go
on passing over a product that has moved — and a check left asserting a superseded truth actively
defends the old behaviour.**

| Check | What it asserts | What must happen |
|---|---|---|
| `07-frontend/src/features/identity/SettingsSecurityTab.test.tsx:79` | `expect(SESSION_TIMEOUT_OPTIONS).toEqual([30, 60, 240, 480])` | **Amend to `[15, 30, 45, 60]`.** It will fail loudly and correctly. |
| `07-frontend/src/features/identity/SettingsSecurityTab.test.tsx:151–157` | the four printed sentences, including *"every session ends after 12 hours"* and *"5 failed sign-ins lock the account for 15 minutes"* | **Amend.** ⚠ Its own name — *"the platform-fixed values are STATED, so their absence is not read as an omission"* — is the part that goes stale hardest: three of them are no longer platform-fixed. |
| `06-backend/tests/test_us_idn_003_sessions.py` TC-7 (`test_..._absolute_twelve_hour_cap_even_when_active`) | 12 hours, **and it sets `session_timeout_minutes=480`** to keep the idle window out of the way | ⚠ **THIS ONE BREAKS SILENTLY AND IS THE WORST OF THEM.** 480 becomes a refused value; the fixture writes the model directly so it will not 400 — it will simply create a policy the product can no longer produce, and go on passing. **Re-point it at 60 and assert the tenant's hard limit.** |
| `06-backend/tests/test_us_idn_003_sessions.py` TC-3, TC-4 (30 min) and TC-8 (30-day refresh) | today's values | **Still correct** — 30 survives the narrowing and 30 days is the default. Amended for their REASON, not their figure. |
| `06-backend/tests/test_us_idn_010_security_policy.py` | the seed defaults and `session_timeout_minutes: 60` / `30` saves | Still correct; must grow the five new fields in its default payload or it will assert an incomplete row. |
| `06-backend/tests/test_cr011_security_policy_seed.py:100` | `served["session_timeout_minutes"] == 60` for a new tenant | **Still correct and must stay 60** — this is the check that catches the declined stricter defaults being introduced by mistake. |
| `07-frontend/src/features/identity/SignInPage.test.tsx:150` | loops `SIGN_IN_LOCKOUT_ATTEMPTS - 1` times, i.e. asserts the **5** | ⚠ **It will go on passing and prove nothing**, because it imports the constant it is testing — a check that moves with the thing it checks. It stays green whatever the constant becomes and can never notice that the screen disagrees with the utility. Tracked under `DEF-IDN-7500`, not amended here. |
| `10-scripts/gates/g132_beat_entries_are_installed.py` | counts the beat entries **from the code** | Goes RED when the nightly cleanup lands without being registered — which is the point; it is not amended, it is the thing that proves E2. |

---

## 5 · Sized and confirmed — in plain English, with the figure

**What changes:** six numbers a utility could not previously touch become six controls on one
screen it already has. Five are new columns on `security_policies`, a table that exists.

**What it costs:** one migration, one endpoint's validation, one screen's controls, the sign-in
screen's tick box becoming conditional, and the cookie finally being given a lifetime.

**What breaks:** for almost every utility, nothing — every default is what the product does today.
**For a utility sitting on a four- or eight-hour timeout, a real behaviour change: their staff are
signed out up to seven hours earlier.** That was put to the PO in those words and accepted.

**How we will know it looks right:** the Security tab compared row by row against r10's Security
section — every label, in order — walked at 1280 and 1440 by the frontend lane, with the five new
controls in the Access group and the rewritten fixed-values sentence read aloud against the three
facts that survive.

---

## 6 · Execute — through r11, unchanged

Three lanes on `claude/confirm-understanding-3ktufc`, each in its own `git worktree` from a pinned
tip, each owning its own files:

| Lane | Tasks | Owns |
|---|---|---|
| **backend** | `B1`–`B13` | `apps/identity`, `apps/portal/session.py`, `apps/tenancy/api.py`, the migration, the nightly cleanup task |
| **frontend** | `F1`–`F6` | Settings → Security, the sign-in screen, the eleven locale catalogues — **the screen owner** |
| **SESS-DOCS** | `D1`–`D6`, `E2`, `E4`, `T11` | this file, the stories, the version, `09-infra`, `.env.example`, `docker-compose.yml`, `tests/test_t11_*` |

**Task status**

| # | Task | Owner | Status |
|---|---|---|---|
| D1 | The rulings in the decision log | SESS-DOCS | **DONE** `9cdc7251c` |
| D2 | `BR-IDN-025` / `BR-IDN-026` amended | SESS-DOCS | **DONE** `9cdc7251c` |
| D3 | This file + the index row | SESS-DOCS | **DONE** |
| D4 | The three stories' test cases, amended not deleted | SESS-DOCS | **DONE** — 32 and 10 TC rows, unchanged counts. Re-checked against the code 2026-09-28: the cases the stories called *owed* (4-hour hard limit, 1-day window, offer off, range refusals) are written and green in `test_cr145_session_settings.py`, and the stories now cite them — `273094bda` |
| D5 | Version `2.389.0` — four literals + CHANGELOG | SESS-DOCS | **DONE** `a7ee34a6c` |
| D6 | `09-infra` + `.env.example` — cleanup schedule and release note | SESS-DOCS | **DONE** `cf1210381` (salvage) + `273094bda`. Runbook §r5 carries the pre-migration notice with a per-tenant query, the two printed counts and the release note; `.env.example`'s 2.389.0 block **declares no variable** — every line is a comment, so no deployed host adds anything by hand for this release |
| E2 | The nightly cleanup on beat, in compose and on ECS | SESS-DOCS | **DONE** `273094bda`. `identity.session_cleanup` 03:20 daily, installed from `IdentityConfig.ready()` → `session_cleanup.install()`; `G132` PASS lists it. ⚠ **`G132` counts EIGHT, not the seven this file expected** — `reports.schedule_sweep` landed 2026-09-27 uncounted (`DEF-INF-7541`, fixed in compose, architecture §10.3 and the runbook). **ECS needs nothing per schedule**: the one beat service (desired 1) picks the entry up from the image |
| E4 | The release note, verified before publishing | SESS-DOCS | **DONE** `273094bda`. All four claims checked in the code (names `sbh_session`/`sbh_portal` unchanged; value unchanged, only an explicit `max_age` added to the three `set_cookie` calls; `identity/0006`–`0008` touch `security_policies` and `audit_log` only; the sweep deletes expired OR signed-out rows only). Published **with** its qualification in `CHANGELOG.md`, the runbook §r5.3 and `.env.example` |
| T11 | End to end: 15 minutes set, signed out at 15 | SESS-DOCS | **GREEN** 2026-09-28 on the default suite — `test_t11_cr145_inactivity_fifteen_minutes.py`, 3 cases, run with the rest of the CR-145 files (100 passed, 12 skipped — the PostgreSQL-only cases) |
| F2 | The two password dropdowns read the server's limits | CR145-CLOSE | **DONE** `89652e2ea`, version `2.393.6`. The SERVER half had already landed at `02827cd52` — `SETTING_LIMITS` carries `pw_min_length` and `pw_expiry_days` and the read publishes them — so this is the SCREEN half: `PW_MIN_LENGTH_OPTIONS` and `PW_EXPIRY_OPTIONS` are **deleted** from `SettingsSecurityTab.tsx` and both selects render from `policy.limits`. **The tab now holds no hand-typed option list at all.** Proved RED first through `vitest`: a second fixture offering `[14, 16]` and `[null, 365]` failed on `expected … to contain 'value="14"'` while the literals were still there — a case asserting only 8/90/180 would pass with them restored and is therefore no test of this change |
| T10 | All six settings walked in a browser | CR145-CLOSE | **DONE** 2026-09-29 — `10-scripts/cr145_t10_six_settings_walkthrough.mjs`, **22 checks, all green**, every setting walked at TWO values so the assertion is that behaviour moved and not that a field saved. Two settings are proved on the REAL wall clock (a 15-minute inactivity timeout and a 5-minute lock) and two cannot be waited for at all (a 12-hour session, a 30-day remembered browser), so their contrast is taken by moving the session row's clock backwards in the database — named `SUBSTITUTED:` in the transcript at every point it is used. See §8 |

---

## 7 · Version

**`2.389.0`**, one allocation for the whole change request, landed at `a7ee34a6c` in the four
literals `G35` holds in lockstep (`package.json`, `package-lock.json` ×2, `pyproject.toml`) with
its `CHANGELOG.md` entry in the same commit — because rule 4 of step 7 refuses a bump without one,
and `2.52.0` was cut with no entry the very next version after that rule was written.

⚠ **AND A SECOND NUMBER, `2.393.6`, CARRIES THE CLOSING WORK — WHICH IS NOT A CONTRADICTION OF
THE LINE ABOVE.** `2.389.0` is the version the CHANGE shipped in and it is what the release note,
the runbook and the three lanes' commits all name. `CR-145` then sat unclosed for a day while
four hundred other commits landed, so the last two tasks (`F2`, `T10`) were cut from the tip at
`2.393.6` — the fix bump free on every branch at the moment they were pushed
(`allocate.py version --bump fix`, re-verified at push). **A change request's version is the one
its behaviour shipped in; a later fix inside it carries its own, and pretending otherwise would
put a number on the release note that no build ever had.**

⚠ **`package-lock.json`'s two fields were edited IN PLACE and `npm install` was NOT run**, which
would have moved dependency resolutions under two live lanes and turned a four-line change into an
unreviewable diff.

---

## 8 · Close — and the rollback, stated before shipping

### ✅ CLOSED 2026-09-29, version `2.393.6` — the bar is met

Per the closure bar (PO ruling 2026-08-18): *"CR is not closed until we have confirm user is able
to perform tasks using screen/browser/UI"*. **Somebody has now opened the Security tab, chosen 15
minutes, left the tab alone for sixteen minutes and been signed out** — on a real clock, in
Chromium, against the built bundle served through `server.mjs`. All six settings were walked at
two values each; the transcript and the screenshots are below.

⚠ **THIS SECTION READ *"⛔ This CR is NOT closed"* UNTIL 2026-09-29.** It is replaced rather than
appended to, because a closure notice under a refusal heading is how a closed record goes on
telling the next reader it is open.

---

## THE FIVE THINGS THE PRODUCT OWNER ASKED FOR WHEN THIS LANDS

*Written to be read aloud. No codes, no ids — everything below is checkable by a person with a
browser and this page.*

### 1 · What changed

Six things about signing in used to be the same for every utility, and nobody could change them.
They are now on one screen — **Settings, then Security** — and an administrator sets each of them
for their own utility, inside limits you agreed:

* **How long we wait before signing an idle person out** — 15, 30, 45 or 60 minutes. Starts at 60.
* **How long a session may last at most, however busy the person is** — 4 to 12 hours. Starts at 12.
* **Whether the sign-in screen offers *"Keep me signed in"* at all** — on or off. Starts on.
* **If it is offered, how long it remembers the browser** — 1 to 30 days. Starts at 30.
* **How many wrong passwords lock an account** — 3 to 10. Starts at 5.
* **How long that lock lasts** — 5 to 60 minutes. Starts at 15.

**Every starting value is what the product already did**, so on the day this ships nothing changes
for a utility that never opens that screen. **One exception, and it is a real one:** the two
longest inactivity choices — four hours and eight hours — are gone. A utility sitting on either is
moved to sixty minutes, and their staff will be signed out up to seven hours earlier than they are
used to.

**One thing was broken and is now fixed.** *"Keep me signed in"* never worked. The box was there,
you ticked it, and closing the browser signed you out anyway — the one thing the box exists to
prevent. It now keeps you signed in for as long as your utility says.

**Two things on that screen did NOT change and are not settings:** passwords must still be at
least eight characters, the last five passwords still cannot be reused, and a temporary password
still lasts seven days. The screen says so in one line.

### 2 · The version it shipped in

**`2.393.6`.** The number is on screen in the product, bottom of the page.

### 3 · How many utilities moved from four or eight hours to one hour

**On the demo database used for this walk: one.** ⚠ **That is a demo figure and it is not the
answer** — this container holds a single made-up utility, so the only honest thing it tells you is
that the move works and prints its count.

**The production number comes from the upgrade itself, when the release runs.** The upgrade does
this move in two steps, and **each step prints its own count. Add the two together — that sum is
the answer.** On a real deployment the first line reads `0` and the second carries the number,
because the account that runs an upgrade is deliberately not allowed to see across utilities and
the second step goes utility by utility. On this demo machine it came out the other way round —
the first line read `1` and the second `0` — for the same reason in reverse, since a test machine's
database account has no such restriction. **Either way, add the two lines. The sum is stable; which
line carries it is not.**

Every utility that moves also leaves a record of what its value used to be, so the answer is
checkable afterwards and not only at the moment of the upgrade.

### 4 · How to check each setting yourself, in a browser

Sign in as an administrator and open **Settings → Security**. Each one is a pair: set it one way,
see the behaviour; set it the other way, see the behaviour change. **Setting it one way only tells
you the field saved, which is not the same thing.**

1. **Sign-out after inactivity.** Set it to 15 minutes and save. Leave the tab completely alone for
   sixteen minutes. Come back, open any screen: *"Session expired — sign in again to continue."*
   Put it back to an hour and the same sixteen minutes changes nothing.
2. **The hard limit after sign-in.** Set it to 4 hours and save, **then sign out and in again** —
   the limit is fixed when a session starts, so it applies to the next sign-in, not the current
   one. Past four hours you are asked to sign in again however busy you have been. At 12 hours you
   are not.
3. **Whether *"Keep me signed in"* is offered.** Untick *Offer on sign-in* and save. Open the
   sign-in screen in a new window: the tick box is gone. Tick it again and the box is back.
4. **How long it remembers a browser.** Set it to 1 day and save. Sign out, sign in with the box
   ticked, and close the browser — you come back signed in, until a day has passed. At 30 days the
   same tick box lasts a month.
5. **How many wrong passwords lock an account.** Set it to 3 and save. On the sign-in screen, type
   the wrong password three times. The third one locks the account, and the RIGHT password is
   refused too. Set it back to 5 and the same three wrong tries do nothing at all.
6. **How long the lock lasts.** Set it to 5 minutes, lock an account as above, and wait five
   minutes. The right password then works. At 60 minutes, after the same five minutes, it does not.

### 5 · What could not be finished, honestly

* **Two of the six cannot be watched end to end in one sitting: a twelve-hour session and a
  thirty-day remembered browser.** Nobody can sit through either. Those two were proved by moving
  the session's clock backwards in the database instead of waiting — which is arithmetically the
  same thing and changes no code and no setting — and every place the walk does it says so out
  loud. The two shortest windows, a fifteen-minute timeout and a five-minute lock, were waited out
  on a real clock with no shortcut.
* **The sign-in screen still prints *"After 5 failed attempts sign-in pauses for 15 minutes"* as
  though it were true for everyone.** A utility that chooses three tries and a sixty-minute lock
  gets a screen telling its staff something else. It is written down and deliberately not fixed
  here: the sign-in screen has nobody signed in, so it cannot read that utility's settings the way
  the Security screen can, and whether we should tell an unidentified visitor a utility's lockout
  rule at all is a question of its own.
* **Five older sentences on the Security screen are longer than our own screen-writing rule
  allows** — they were there before this change and are written down rather than rewritten inside
  it. The sentences this change itself wrote are inside the rule.
* **The customer portal has no setting of its own and follows the staff one**, which is what you
  ruled. Nothing extra was built for it; it was checked in the code rather than walked.

---

## THE WALK ITSELF — `T10`, 2026-09-29, 22 CHECKS, ALL GREEN

Chromium against the built bundle (`vite build --mode compose`, `DEF-INF-7702`/`DEF-INF-7802`)
served through `server.mjs` on its own port, over its own migrated and seeded database
(`sbh_cr145t10`) so no sibling lane's data could move under it. Screenshots in `/tmp/cr145-t10`.
Re-runnable:

    BASE=http://127.0.0.1:8572 DBURL=postgres://…/sbh_cr145t10 \
      node 10-scripts/cr145_t10_six_settings_walkthrough.mjs

⚠ **THE FIRST RUN REPORTED THREE FAILURES AND ALL THREE WERE THE CHECK, NOT THE PRODUCT — AND
THAT RUN IS KEPT RATHER THAN DELETED.** It asserted that a signed-out browser lands on `/signin`.
The product **keeps the address the clerk asked for** — which is what lets them come back to it
after signing in — and renders a *Session expired · Sign in again to continue.* card over it. So
the URL is identical on a sign-out and on a success and the check could not tell them apart **in
either direction**: the three *"still signed in"* halves were passing for the wrong reason at the
same moment. It was found by reading a failure and opening the screenshot instead of believing
the assertion (hard-won law 7, *looking at the wrong thing*). The six checks now read the rendered
screen, and the positive half asserts the tab's own control is present — because `!signedOut` is
not the same statement as *signed in* when an error card is a third possibility.

```
tenant 01a0ea76-b654-7f9f-9d21-132cc87359eb   user 01a0ea76-bb10-78b5-821e-49dcf7991278

── 0 · Settings → Security, as a person opens it ──
PASS  inactivity offers 15/30/45/60 and neither withdrawn value — 15,30,45,60
PASS  the two password lists render from the server's limits (F2) — 8,10,12 · ,90,180
PASS  B14 rule 31 — no database id is visible — none
PASS  B14 rule 33 — every field label is 3 words or fewer
PASS  B14 rule 33 — every range help is 6 words or fewer per sentence
    labels: Minimum length · Expire passwords · Session timeout · Hard limit · Allowed IP ranges (optional) · Days · Wrong passwords · Lockout length
    helps:  Between 4 and 12 hours. · Comma-separated IPv4 CIDR blocks. Leave empty for no restriction. · Between 1 and 30 days. · Between 3 and 10 tries. · Between 5 and 60 minutes.
    rule 33, other copy on this screen: 5 of 8 sentences run past six words
      OVER CAP: Applies to every password set from now on.
      OVER CAP: How long a session lasts and where staff may sign in from.
      OVER CAP: Every configuration and money action is recorded with actor, timestamp and before/after.
      OVER CAP: New rules apply to the next password change, not to passwords already set.
      OVER CAP: The save is refused if your own address is not inside the ranges you enter.

── 1 · Wrong passwords before lockout ──
    the utility allows 5 wrong passwords
PASS  at 5 allowed, three wrong passwords do NOT lock the account — http://127.0.0.1:8572/brazosbend/dashboard
    the utility now allows 3 wrong passwords, and locks for 5 minutes
PASS  at 3 allowed, the SAME three wrong passwords lock the account — locked_until=2026-09-29 00:53:27.653863+00

── 2 · Sign-out after inactivity: 15 minutes, on the wall clock ──
    session 01a0eaa2-3c9d-753c-8228-cb4caa84cc89 is now idle; the tab is closed so nothing polls

── 3 · Lockout length: five minutes, on the wall clock ──
PASS  one minute into a five-minute lock the account is still locked (76s)
PASS  after the five minutes the same password is accepted (335s waited, nothing else changed) — http://127.0.0.1:8572/brazosbend/dashboard

    and the contrast, with the clock moved instead of waited
    SUBSTITUTED: the lock's clock moved back 6 minutes — the same wait as above, not a setting
PASS  at 60 minutes the same six-minute wait leaves the account locked
    lockout put back to 5 tries / 15 minutes

── 4 · Whether the tick box is offered ──
PASS  offered ON — the sign-in screen shows the box
PASS  offered OFF — the box is gone from the sign-in screen

── 5 · How long the box remembers a browser ──
PASS  at 1 day, the browser is told to keep the sign-in for about a day — 1.000 days
PASS  at 30 days, the same tick box is told to keep it for thirty — 30.000 days
    SUBSTITUTED: both remembered sessions aged two days — the wait itself is not walkable
PASS  at 30 days a two-day-old remembered browser is still let straight back in — http://127.0.0.1:8572/brazosbend/settings/security
PASS  at 1 day the same two-day-old remembered browser is sent back to sign in — http://127.0.0.1:8572/brazosbend/settings/security

── 6 · The hard limit after sign-in ──
PASS  signing in under a 4-hour limit stamps the session to end in 4 hours — 4h
    SUBSTITUTED: the session's clock moved back 5 hours — a 12-hour wait is not walkable
PASS  five hours into a four-hour limit the clerk is signed out, though they were active a moment ago — http://127.0.0.1:8572/brazosbend/settings/security
PASS  signing in under a 12-hour limit stamps the session to end in 12 hours — 12h
PASS  the SAME five hours under a twelve-hour limit changes nothing — still signed in — http://127.0.0.1:8572/brazosbend/settings/security

── 7 · The inactivity timeout, 396s in ──
PASS  after 16 untouched minutes on a 15-minute timeout the clerk is signed out — http://127.0.0.1:8572/brazosbend/settings/security
    SUBSTITUTED: that session left untouched for 20 minutes by moving its clock, not by waiting again
PASS  twenty untouched minutes on a 60-minute timeout signs nobody out — http://127.0.0.1:8572/brazosbend/settings/security

    the utility is back at 60 minutes / 12 hours / offered / 30 days / 5 tries / 15 minutes

screenshots: /tmp/cr145-t10

ALL CHECKS PASSED
```

---


**Three items in §6 wait on a sibling lane, and they are named rather than guessed at:**

⚠ **UPDATED 2026-09-28 (SESS-DOCS, `273094bda`): D6, E2 and E4 are DONE — see §6.** The three
bullets below are what they waited on, kept as the record of why; each was read from the backend
lane's pushed code before anything was published. The migration count is **the sum of two printed
lines** — `identity/0007` (`CR-145: …`, which reads 0 on a real deployment because it reads before
setting tenant context) and `identity/0008` (`CR-145 (per tenant): …`, `DEF-IDN-7504`) — and exists
only once somebody runs `migrate` on the real database; `09-infra/02-aws-runbook.md` §r5.2 says
where to read it.

* **D6 and E2** need the cleanup task's registered name from the backend lane's `B10`. ⚠ **It is
  read from what that lane pushes, never invented** — and note that in this repository **a beat
  entry is not added in compose at all**: schedules install from an app's `ready()`, and
  `docker-compose.yml`'s header list and `09-infra/01-deployment-architecture.md` §10.3 are the two
  places that *describe* them. Both said **SIX** and were moved to seven — and `G132` counts **eight** (`DEF-INF-7541`); they now say eight. **`G132` counts them from
  the code, which is the only version of that list that cannot rot.**
* **E4** — the release note *"Sessions opened before the deploy keep their old cookie until they
  expire; nobody is forced to sign out"* — is a promise to every signed-in user and **is not
  published until it has been read in the backend lane's commit rather than inferred from the
  ruling.** See the note below.
* **The migration count in §3** comes from `B1`'s printed output.

### ⚠ The release note has a qualification, and it is not a quibble

The sentence is about the **cookie**, and on the cookie it is expected to hold: a deploy rewrites
nobody's browser cookie, and the change only adds a `max_age` to cookies set **from that point on**.

⚠ **BUT A UTILITY MIGRATED FROM 480 TO 60 WILL SIGN PEOPLE OUT SOONER, AND THAT IS NOT WHAT A
READER HEARS IN *"nobody is forced to sign out"*.** Their cookie is untouched and their session is
not revoked — so the sentence is literally true — and a clerk who steps away for ninety minutes is
nevertheless signed out where yesterday they were not. **Both halves are published or neither**,
because a promise that is true in the way the reader did not mean is worse than no promise.

### The rollback

| If this was wrong | What undoing it costs |
|---|---|
| The five new columns | **Reversible.** Nothing reads them but this feature; drop the columns or stop reading them and every default is today's behaviour. |
| The cookie lifetime | **Reversible.** Remove the `max_age` and the cookie is a session cookie again — which is to say, the bug comes back. |
| ⚠ **The 240/480 migration** | **NOT REVERSIBLE FROM THE ROW.** The old value is overwritten; nothing in `security_policies` remembers it was 480. **The only record is the `audit_log` row the migration writes, and `audit_log` is pruned on a retention schedule** (hard rule 4, `OQ-1340` CLOSED 2026-09-23 — no row type is exempt). So after the retention window there is no way to restore a utility's original choice except by asking them. ⚠ **AND 480 IS NO LONGER A LAWFUL VALUE**, so restoring it means reversing the ruling, not editing a row. **This is a decision, not an experiment**, and it is stated here before shipping because that is what step 8 is for. |
| The withdrawn choices | Reversing them is another CR — the range is the thing the PO signed. |
