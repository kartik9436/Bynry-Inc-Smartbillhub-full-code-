# 15 · Customer Web Portal — the execution plan (`CR-068`)

**What this is.** The build order for the customer portal, written 2026-09-03 from the
documentation that already exists — `CR-068` §12 (five phases, tasks `1.1`…`5.10`),
the 74 stories in `06-epics/`, the 98 endpoints, the 14 tables, the 18 journeys, the
screen layouts and the component inventory — and **verified against the code at HEAD
`b29edecd`** before a single task was written. Tasks are grouped into WAVES, waves into
PHASES. `CR-068` §12's task numbers are kept as the cross-reference; where a §12 task
had to be split, or a story had no task, the table says so.

**The Product Owner's rule for this plan, verbatim (decision log 2026-09-03):**

> *"we ahve to execute in agile way - each phase/wave should produce tangila eoutcome"*

and, ruled the same day on `CR-069`:

> *"at the end of each pahse we should abl to luanch some funtionlaity"*

**And the rule that arrived while this plan was being written, verbatim:**

> *"everything should be executed based on actual code, and rules that we place, also
> ensure you do web walkthorugh before you sign off the user story or build"*

**So, in this plan:**

* A **PHASE** is a launchable increment. It has a launch sentence — the thing a utility
  can announce — taken from `CR-068` §12 and kept. Five phases, unchanged.
* A **WAVE** is a sprint-sized lane (one or two people, one to two weeks) that ends in a
  **DEMONSTRATION** — something clicked in the running product, written out as a 5–8 step
  demo script against the fixture — and a **version bump**. No wave ends in *"the tables
  exist"* or *"the endpoints are mounted"*. A wave blocked to a boundary by an open
  question **still demonstrates the boundary** — the stub, the sentence on screen — and
  says so in its exit test.
* A **TASK** is one of the r11 parts — **2a backend · 2b frontend · 2c tests + data ·
  2d prove it** — or a **ground**, **gate** or **doc** task. **2b is numbered so that
  skipping it is visible** (`12-engineering-plan.md` Addendum r11); every wave here has
  a 2b task and a 2d task, and step 6 refuses a story missing either.
* Waves in the same phase that do not depend on each other **run in parallel**; each wave
  says which.

## How a lane uses this plan — and the definition of done

Take one wave. For every task in it, run **r11 steps 0–6** (`04-docs/02-decisions/
12-engineering-plan.md` Addendum r11), and nothing shorter:

| Step | What it means for a portal task |
|---|---|
| **0 · Check the packet is current** | Re-read `12-governance/01-open-questions.md` rows `OQ-1391`–`OQ-1399` and `OQ-249`, the decision log for `CR-068`, the defect register, and **the code paths this plan names for the task** — the *touches* column was verified at `b29edecd` and the repo moves under you. **If the documentation and the code disagree, the code wins and the task says so** (this plan's §0 is the list of places where they already disagreed). |
| **1 · Packet** | The story's eight sections (`06-epics/EP-CWP-##`), its `BR-CWP-` rules quoted verbatim from `02-business-rules.md`, its rows in `03-field-map.md` and `07-endpoints.md`, its layout entry in `08-screen-layouts.md` beside its wireframe `wireframes/CWP-###.png`, the components in `09-component-inventory.md`, its journeys in `04-flows.md`, and every `depends_on` story's handoff. |
| **2a · Backend** | Refuses rather than guesses. Every open question is `raise NotImplementedError("OQ-####")` with the id in the code. Four write points and nothing else (`BR-CWP-001`). |
| **2b · Frontend** | The screens, in Tailwind utilities, in `07-frontend/src/portal/` (on `route-b-migrated.txt`) or, for `CWP-069`–`075`, in `07-frontend/src/features/tenancy/`. Layout per `08-screen-layouts.md`. |
| **2c · Tests + data** | Test CODE for the cases the story's §3 already declares — `06-backend/tests/test_us_cwp_<nnn>_tc*.py` (G10's shape, `g10_tc_tests.py:38`) and the vitest beside the screen — plus the fixture rows in `apps/portal/sample_data.py`. Never cases authored after the code. |
| **2d · Prove it** | **A browser walkthrough of the running product, and it is the definition of done.** The wave adds `10-scripts/render-checks/cr068-<wave-letter>-<slug>.mjs` (Playwright, Chromium preinstalled; the convention is `cr058-owner-import-and-sale.mjs` — its header says how to run against a database nobody else is seeding). The script clicks the wave's demo script against the seeded fixture, asserts the on-screen sentences named in the exit test, asserts computed style (a utility that did not compile is a class name in the DOM and nothing else — `DEF-974`), asserts no uuid and no rule id in customer copy (B14 rules 31, 32), and saves screenshots. Every guard the wave adds is **broken first, in a worktree, and its failure quoted** (law 7). |
| **W · Write back as you go** | A stale rule → amend it dated, before building on it. A question the rules do not answer → mint it, stub with its id, before code that would guess. A defect → file it before fixing it. A judgment → decision log with its worked figure, before reporting it. |
| **3 · Self-verify** | `10-scripts/gates/run_gates.py` — including `G75`–`G78` once wave A lands — and the §5 checklist. |
| **4 · Close the record** | Decision-log row · `20-wave-tasks.tsv` states moved · review-ledger row for every 🔒 file, **in plain English with a figure** · CHANGELOG entry · the version. |
| **5 · Human review** | The PO, on anything touching money rules — and on the two re-signs this plan names (consumer upload; nothing else). |
| **6 · Merge** | Refuses a story whose 2b or 2d was skipped. |

**A story is signed off only when all three are true:** its tests are green · the wave's
walkthrough script has run green **on the actual build** · and the rendered layout of
each of its screens matches `08-screen-layouts.md` and the wireframe (hard-won law 6 —
*"diff the running app against the prototype; no gate looks at rendered output"*).
Not one of the three substitutes for another.

**The version scheme** (`12-governance/13-change-process.md` §7, amended 2026-08-26):
`<release>.<change>.<fix>`. Today the product is **`2.128.2`** (`07-frontend/package.json:4`
and `06-backend/pyproject.toml:193`, held in lockstep by `G35`). **The middle number
moves once per wave, at merge, in the order waves land — it is the integrator's act, and
the CHANGELOG entry lands in the same commit.** The *ships as* line on each wave below is
therefore a **nominal** figure — `2.129.0` for the first wave to merge, `+1` per wave —
and the real literal is written back into this file at merge. Whether a phase launch
moves the first number is the PO's to declare (a *named release*); this plan assumes it
does not.

**Fixture.** The stories are written against **Pine Hill Water & Power** (`pine-hill`,
brand `#EC3013`, Maria Alvarez, `ACC-10432-A`, `1408 Elm St · A`, `78702`, bill
`BL-2608-0141` owing `$142.18` due 14 Sep) with **Oak Ridge** (`oak-ridge`) as the second
tenant every isolation test needs. The code's one seeded demo tenant is **Brazos Bend**
(`seed_demo.py:33,89-90`, `brazosbend`), whose figures are workbook-verified and guarded
by `G4`/`G61`. **The plan's default, for wave A to record in the decision log:** the
portal fixture is seeded as its own tenant `pine-hill` (plus `oak-ridge`) by
`apps/portal/sample_data.py`, so the story figures land verbatim and **no Brazos Bend
figure moves**. Demo scripts below name Pine Hill.

**Coverage.** Every one of the 74 stories is placed in exactly one wave. The check is a
small Python script run over this file (§9 is its input); its output is pasted here
verbatim so it can be re-run:

```
stories expected 74 · in §9 table 74 · in wave sections 74
per wave: A 3 · B 5 · C 4 · D 4 · E 8 · F 5 · G 5 · H 3 · I 7 · J 3 · K 4 · L 4 · M 5 · N 2 · O 2 · P 3 · Q 4 · R 3 = 74
per phase: 1 16 · 2 21 · 3 14 · 4 13 · 5 10
RESULT: PASS — every one of the 74 stories is placed in exactly one wave, and §9 agrees with the wave sections
```

The check (re-run it with `python3 check.py 10-execution-plan.md` after any edit to §9 or a wave's **Stories:** line):

```python
"""Coverage check for 15-portal/10-execution-plan.md: every US-CWP story in exactly one wave."""
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
expected = {f"US-CWP-{n:03d}" for n in range(1, 75)}
# §9 table: three (story, phase, wave) triples per row
table = {}
for sid, ph, wv in re.findall(r"`(US-CWP-\d{3})` \| (\d) \| ([A-R]) \|", text):
    table.setdefault(sid, []).append((int(ph), wv))
# per-wave "Stories:" lines (text before any parenthesis), under "### Wave X"
waves = {}
current = None
for line in text.splitlines():
    m = re.match(r"### Wave ([A-R]) ", line)
    if m:
        current = m.group(1)
    if line.startswith("**Stories:**") and current:
        head = re.sub(r"\([^)]*\)", "", line)
        waves.setdefault(current, set()).update(re.findall(r"US-CWP-\d{3}", head))
problems = []
if set(table) != expected:
    problems.append(f"§9 table ids != 001–074: missing {sorted(expected-set(table))}, extra {sorted(set(table)-expected)}")
dups = [s for s, v in table.items() if len(v) != 1]
if dups: problems.append(f"§9 lists more than once: {dups}")
placed = {}
for w, ids in waves.items():
    for s in ids: placed.setdefault(s, []).append(w)
multi = {s: w for s, w in placed.items() if len(w) > 1}
if multi: problems.append(f"placed in more than one wave: {multi}")
missing = sorted(expected - set(placed))
if missing: problems.append(f"in no wave's Stories line: {missing}")
mismatch = sorted(s for s in expected if s in table and s in placed and table[s][0][1] != placed[s][0])
if mismatch: problems.append(f"§9 wave != wave section for: {mismatch}")
print(f"stories expected 74 · in §9 table {len(table)} · in wave sections {len(placed)}")
print("per wave: " + " · ".join(f"{w} {len(waves[w])}" for w in sorted(waves)) + f" = {sum(len(v) for v in waves.values())}")
print("per phase: " + " · ".join(f"{p} {sum(1 for v in table.values() if v[0][0]==p)}" for p in range(1,6)))
print("RESULT: " + ("PASS — every one of the 74 stories is placed in exactly one wave, and §9 agrees with the wave sections" if not problems else "FAIL — " + "; ".join(problems)))
sys.exit(1 if problems else 0)
```

---

## 0 · What the code says today — verified at HEAD `b29edecd`, 2026-09-03

**Read this before any task.** Each row is a place where the module's documents and the
code disagree, or where a document assumed something the code does not have. **The code
wins, and the task that touches the row says so.** Write-backs to the documents are owed
by the wave that builds the row (law W), not by this plan.

| # | The documents say | The code at `b29edecd` | Consequence for the plan |
|---|---|---|---|
| 1 | Nothing of the portal exists yet | **True.** No `06-backend/apps/portal/`, no `07-frontend/src/portal/`, no `portal` line in `07-frontend/src/styles/route-b-migrated.txt` (2,976 lines), gates end at `g74_tables_nobody_reads.py`, no `08-qa/01-e2e/journeys/J3*`/`J4*` files | Wave A is ground first |
| 2 | Stories' §5 read `tenant.brand_colour`, `tenant.accent_colour`, `tenant.trading_name`; `09-component-inventory.md` tokens read `tenant.brand_colour` | **Those columns do not exist.** `apps/tenancy/models.py` has `subdomain` (113), `legal_name` (120), `support_phone` (136), `logo_content_type`/`logo_bytes` (145–146). The brand hexes the Company tab saves are **`brand_primary_hex` / `brand_accent_hex`** (`07-frontend/src/features/tenancy/SettingsCompanyTab.tsx:71-72`; `apps/tenancy/brand.py:34,222`) | A5/A6 read the real names; the story §5 rows are stamped by wave A |
| 3 | `US-CWP-001`: entry `smartbillhub.bynry.com/{tenant}` — the bare tenant root | **`/:tenant` is the staff app's index and forwards to the dashboard** (`07-frontend/src/routing/screenIds.ts:240-243`; `App.tsx:215-241`). `CR-068` §11a checked only that `portal` collides with nothing | Guest surface lives at **`/{tenant}/portal`** (front page) and `/{tenant}/portal/…` — which is the PO's ruling `R11` read literally. Wave A records it in the decision log. Moving the staff redirect would be a change request |
| 4 | `03-field-map.md`: `meter_read` gains `source` enum `staff \| portal \| estimated` | **`MeterRead.source` already exists** — `ami \| manual \| import` (`apps/metering/models.py:1773`), beside `read_method` (1791, the tenant's `read_methods` list) and `status` over `READ_STATUSES` (1279–1312, lifecycle `BR-MET-053`) | The portal adds the value `portal` to the existing column; `review_state` is the only new column; `awaiting_review` is reconciled with `BR-MET-053`'s staged→committed lifecycle in wave J's packet |
| 5 | `03-field-map.md`: `outbound_message` gains `portal_delivered_at`, `portal_read_at` | `OutboundMessage.channel` is a text field (`apps/notifications/models.py:404`). A `read_at` exists only on the **staff mailbox** row (917), and the docstring at 828–840 says why: *"a recipient marking a message read must not touch the row that records what the utility sent"* — one message × one recipient | Portal read state is a **portal-owned per-recipient row**, not a column on the queue row. `CHANNELS_BY_KIND` (`catalogs.py:1915`) knows `pdf_print`, `email`, `sms`, `in_app` and **no `portal`** — `CP-17` adds it there, dated |
| 6 | `service_request.channel` is an enum gaining `customer_portal` | **Free text** (`apps/customers/models.py:1504`), one rule value `staff_collections` (1507); the detail header already renders the label *Customer portal* (1491). No migration | Wave B writes the first row carrying it |
| 7 | The eleven-state lifecycle already has the customer's four transitions | `create_request` (474), `update_request` (533), `submit` (1886), `add_note` (1766) exist in `apps/customers/service_request_service.py`; **there is no `withdraw`** (`refuse_request`, `manual_close`, `approve` are staff) | `withdraw` is new — wave I, `BR-CWP-079` |
| 8 | *"Nothing publishes a balance"* | **Nothing publishes it to a customer.** Staff-side reads exist: `apps/payments/outstandings.py:287 outstandings()`, `apps/payments/customer_position.py:93 customer_open_bill_position()`, `billing_seam.outstanding_positions` | The balance seam **composes** these (`BR-CWP-012`, no second copy) — wave E |
| 9 | `webhooks.py` *"one docstring line"* | **577 lines**, `tests/test_cr060_c21_webhooks.py` has 15 tests, review-ledger row exists | Wave P verifies before building; `CP-09` may be largely done |
| 10 | `payment_methods` is the customer's stored instrument | The **table name is taken** by the tender lookup — `apps/payments/models.py:55-80` says so; `AutopayCaptureIntent` at 992 (`autopay_capture_intents`), `autopay.py` 337 lines | Wave P resolves the name before its migration |
| 11 | Plans: `agreement_sent`, per-plan elections | `PaymentPlan` (`collections_models.py:138`), `PLAN_AGREEMENT_SENT` (98), `agreement_sent_on` (173), `suspend_late_fees`/`suspend_disconnect` (166–167), `plans.py:199-248` | New columns `customer_signed_on`, `offer_expires_on` — wave M |
| 12 | Protections, the ladder, notices, returned mail, write-offs, adjustments, credits, refunds, level pay, tax exemption, deposit rule all exist | `AccountProtection` (`customers/disconnects.py:1629`), `DisconnectCase` (1259), `DisconnectNotice` (1481), `TIER_UNMAPPED = "unmapped_rung"` (603), `LadderState` (2139) · `NoticeHistory` (`payments/collections_models.py:239`, skip reason 266), `AccountCollectionState` (286), `DeliveryReturnEvent` (321), `WriteOff` (447) · `Adjustment` (`billing/models.py:1241`) · `billing/credit_notes_api.py` · `payments/refunds.py` · `AccountBudgetStatus`/`AccountBudgetEvent` (`billing/models.py:1081,1161`), `budget_api.py` (303, 443, 515, 541) · `TaxExemptionCertificate` (`rating/models.py:1209`) · `PlanDepositRule` (1338) · `WorkOrder` (`metering/connections.py:684`, `work_orders`) | Phases 2–4 are reads through seams over these; **no portal table duplicates any of them** |
| 13 | Photos and documents go *"through the existing document store with its allow-list, size cap and malware scan"* | `StoredDocument` exists (`tenancy/document_models.py:403`, `document_store.py`, `document_storage.py`). **No malware scan exists outside `tenancy/logo.py`** *(and since 2026-09-23 none exists anywhere, by ruling: the scan is SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), `DEF-SHL-6347`)*, and `attach_document` (`service_request_service.py:983`) takes a `size` and validates no content. **And `CR-068` §2b records consumer upload as a signed deferral needing a re-sign via HUMAN-GUIDE §6** — while `US-CWP-007` TC-8, `US-CWP-042` TC-11 and `US-CWP-066` TC-7 each attach a photo | Every `PhotoPicker` renders **held with its reason** (`BR-CWP-056`'s shape) until the re-sign; the re-sign is task **B9**, put to the PO in plain English. `US-CWP-064` already says the upload box is not built |
| 14 | The interruption is genuinely new | **True** — `grep -i interruption apps/metering/` finds nothing; `service_outage_notice` is only wording (`catalogs.py:944-949`) | Wave B builds it in `metering` (B2 §2) |
| 15 | Holiday closures come from the calendar the utility keeps | `HolidayCalendar` (`tenancy/models.py:1292`: `holiday_date`, `label`) | `BR-CWP-096` reads it — wave D |
| 16 | The anonymous throttle at 60/min already exists | `PublicOnboardingThrottle(AnonRateThrottle)`, `rate = "60/min"` (`tenancy/api.py:84-88`), on four public routes (`public/subdomain-check`, `public/pricing-plans` at 1009–1010, …) | The guest edge **reuses** it — `BR-CWP-022` |
| 17 | Password policy and lockout are tenant settings | `SecurityPolicy.pw_min_length ∈ {8,10,12}` (`identity/models.py:249`), lockout 5-fail/15-min columns (175); staff `sessions` table (41) | `BR-CWP-037` reads the policy; `portal_session` **never joins** `identity` |
| 18 | Back-office endpoints live in `apps/tenancy/…` (`07-endpoints.md` §3) | `portal_settings` is **portal-owned** (`03-field-map.md` §1) and cross-module writes are forbidden (B2 §2) | `GET/PUT settings/portal` and `…/branding` live in `apps/portal/backoffice_api.py` (staff-authenticated); help, tips and centres stay in `tenancy` because `tenancy` owns those tables. `07-endpoints.md` §3 stamped by wave A |
| 19 | Settings → Configure gains a *Customer portal* segment | `CONFIGURE_SUB_TABS` = `reference-data`, `routes-cycles`, `number-series`, `templates` (`SettingsPage.tsx:37-40`); `G14` compares headings to r10 and is **already red** (256 unknown against a baseline of 199 — `g14_prototype_conformance.py:247-260`) | Wave A adds `customer-portal`; read G14's docstring first; **the baseline is not raised** |
| 20 | `02-business-rules.md`'s question table | Names the wrong story for eight of nine questions (e.g. `OQ-1391` → `US-CWP-052`; the register and the epics say `051`/`058`). **`01-open-questions.md` and the epics agree with each other** | Defect row owed (outside this plan's write scope); build from the epics |
| 21 | `US-CWP-011` frontmatter `wave: 1`; `US-CWP-044` `wave: 0` | `CR-068` §12 says `CP-16` is *"Not in this phase; not silently dropped either"*; `CWP-058` is a signed-in screen | `US-CWP-011` is placed in **Phase 3 wave K**; `US-CWP-044` in **Phase 4 wave O** (`CP-29` is §12 task 4.6). Frontmatter to be amended by those waves |
| 22 | The clerk moves an interruption to *crew on site* (`US-CWP-008` TC-1) | **No staff screen owns that write** — `CWP-069`–`075` are settings, not operations | Wave B adds a status control as a **section of the existing request detail** (`07-frontend/src/features/customers/ServiceRequestDetailPage.tsx`); no new `S`-id, because screen numbers are the PO's (`R13`) |
| 23 | OTP by SMS or email; reset by email | The outbound queue exists (`dispatch_outbound`); **email sending activates in W6, SMS (Twilio) is W8** (`12-engineering-plan.md` r3 wave table) | Codes are queued on the existing queue; the demo reads the code from the queue row until W6 activates; the SMS choice is **held with its reason** |

---

## 1 · The five phases at a glance

| Phase | Launch sentence (from `CR-068` §12, kept) | Product wave it stands on | Waves | Stories | Exit test — the demonstration |
|---|---|---|---|---|---|
| **1** | *"Our website can now tell you whether we serve your address, what it costs, where our office is and when it is open, answer your common questions, let you report a burst main or ask for a small service, and let you check on anything you have already asked us — without you signing in to anything."* | **W0** (shell, settings, tenancy), **W1** (premises, plans and fees), **W2** (service requests) — all built | **A · B · C · D** | 16 | A person outside the team opens `/pine-hill/portal` on a deployed build, reports a burst on Elm St, gets `RP-26-0412`, tracks it to *Crew on site*, checks `31 Palm Ct`, reads an answer, and finds the north counter closed on Thanksgiving — signing in to nothing |
| **2** | *"Sign in and see what you owe, every bill you have ever had and the PDF of each one, your meter readings and how this bill compares with last, your payment plan, your deposit, anything we are holding for you, and change how we contact you."* Paying is visible and held (`R3`) | **W2** (accounts, reads), **W3** (issued bills, pinned documents), **W4** (payments history, deposits), **W6** for the codes to arrive by email | **E · F · G · H** | 21 | Maria Alvarez, who has never signed in, enrols cold on three facts off her bill, sees `$142.18 · Due 14 Sep`, opens `BL-2608-0141` line by line, downloads the PDF that was posted, and every Pay control is disabled with its reason |
| **3** | *"Raise a request, send us your own meter reading, question a bill or a reading, and see every notice we have sent you and when."* ⚠ **`OQ-1399` is put to the PO before this phase starts** | **W2** (requests, read validation), **W4** (notices, move-out settlement), **W3** (outbound queue) | **I · J · K** | 14 | Maria asks to move out on 17 Sep and `SR-26-0056` reaches a clerk with channel *Customer portal*; sends `158940` and is warned *about nineteen times your usual*; sees *Final notice · 15 Sep · post · not sent, no forwarding address* |
| **4** | *"See exactly where you stand if you are behind, what happens next and what it will cost, ask for a payment plan, apply for the protections you may qualify for, and let your bookkeeper or a family member see your account without giving them your password."* | **W4** (plans, collections ladder, protections, budget billing) | **L · M · N · O** | 13 | A customer `$412.60` overdue reads *if it goes that far `$657.60`*, asks for a plan of five `$22.03` and one `$22.05`, accepts a plan the utility offered on her signature alone, and Kestrel Bookkeeping's payment is audited under Kestrel's name |
| **5** | *"Pay your bill online, with a card or your bank, save the method for next time, set up automatic payment, and pay without signing in if you have your bill to hand."* | **W7** (payment rails — arrives through `CR-069`'s substrate) and **W6** | **P · Q · R** | 10 | A real sandbox payment of `$142.18` lands on `BL-2608-0141`, the gateway's replayed settlement leaves one row on PostgreSQL, and a guest holding the paper bill pays it seeing `M. A••••••` and nothing else |

**Sixteen + twenty-one + fourteen + thirteen + ten = 74.** Eighteen waves, `A`–`R`.
---

## 2 · PHASE 1 — LAUNCH: a utility puts its public page live

**Launch sentence:** `CR-068` §12 Phase 1, kept verbatim in §1 above.
**Stands on:** W0 · W1 · W2 (all built). **Stories (16):** `US-CWP-001`, `002`, `007`,
`008`, `009`, `010`, `012`, `013`, `014`, `015`, `069`, `070`, `071`, `072`, `073`, `074`.
**Exit test:** the Phase 1 demonstration in §1, on a deployed build, by a person outside
the team — and `G75` green with its RED proof quoted.
**Order:** wave **A** first; **B, C and D run in parallel** the day A's ground tasks
(`A1`–`A4`) are pushed. Phase 1 launches when all four are merged.

### Wave A — *Switch it on* · the portal exists and a System Admin can turn it on

**Goal a person can see:** a System Admin finds the portal's address in Settings, turns
the portal on, and the public front page appears in the utility's own colours — with the
cards for anything switched off simply absent.
**Stories:** `US-CWP-001` · `US-CWP-069` · `US-CWP-070`
**Demo script** (fixture: Pine Hill Water & Power, brand `#EC3013`; second tenant Oak Ridge):
1. Sign in to the **staff** app as Pine Hill's System Admin; open Settings → Configure → **Customer portal**. The Overview reads the address `smartbillhub.bynry.com/pine-hill` with *copy* and a QR code — read from `tenant.subdomain`, no second column.
2. In a second tab open `/pine-hill/portal`. **The portal is off for a new tenant**: a holding page, no cards (defaults fail closed, law 3; `R8`).
3. Back in Settings, set *The portal is* to **live**; reload the second tab. **SIX** errand cards render — all of them, in the wireframe's order — plus the *Already have a login? Sign in* bar. **Four are usable and two are plainly disabled:** *Check my area* says *No status page here yet.* (`R9`) and *Help & answers* says *Nothing published here yet.* (`BR-CWP-093`). ⚠ **THIS STEP SAID *Four* UNTIL 2026-09-05**, when the PO ruled *"for completess have them on screen"* — the count on the glass changed and the two conditions behind it did not. The *Help* and *Visit us* nav words are still absent, which is the difference between a catalogue and a destination. No password field anywhere.
4. Turn **Quick pay** off; reload. The *Pay a bill* card is gone.
5. Show *Send your own reading* — already **off** for a new tenant (`R8`), the one switch that is.
6. Open the **Branding** segment: logo, trading name and the two brand hexes are **read-only** with a link to Company → Profile; type a strapline — the preview updates as you type; reload `/pine-hill/portal` and the strapline is under the utility's name.
7. Open `/oak-ridge/portal`: Oak Ridge's own strapline and colours, nothing of Pine Hill's (tenant resolved from the path before any content query — `BR-CWP-005`).
8. Run `run_gates.py`: `G75` and `G78` PASS; then, in a worktree, add a fifth write to `apps/portal/services.py` without a row in `write_points.py` and show `G75` **RED** with its sentence.
**Exit test (asserts rules):** `BR-CWP-093` — the DOM has **no** *Help & answers* card and no empty container when nothing is published · `R8`/law 3 — a fresh tenant has `is_live=false`, `self_read_enabled=false`, the other four `true` · `BR-CWP-005` — the Oak Ridge page carries no Pine Hill string · `BR-CWP-003` — `G75` red then green · B14 rule 31 — no uuid is the visible value of anything on `CWP-001`, `069`, `070`.
**Depends on:** nothing in this CR. **Blocked by:** nothing.
**Walkthrough script:** `10-scripts/render-checks/cr068-a-switch-it-on.mjs`

⚠ **AS BUILT — 2026-09-04, `2.133.0` (the nominal `2.129.0` below went to CR-069 wave A).** Where this table and the code disagreed, the code won and the register says so (`DEF-CWP-3640`): **A1** — both readers of `route-b-migrated.txt` were taught a DIRECTORY entry (`portal/`), because neither accepted `portal/**`; **A2** — `api.py`, `session.py`, `credentials.py`, `delegates.py` are NOT created empty (an empty `api.py` is endpoint code to G9 and a promise to law 1); they arrive with the waves that fill them; **A4** — the gates are **`G81`** (write points) and **`G82`** (CWP register): `G75`–`G77` were CR-069 wave A's, `G78` CR-070's and `G79`–`G80` CR-069 wave B's before this wave landed; **A5** — the guest edge carries, beyond the sixty-a-minute per-address throttle, a per-TENANT rate and an in-flight budget, by the PO's load ruling of 2026-09-03 (`NFR-38`–`NFR-41`, `apps/portal/guards.py`) — three point reads, measured by a test; **A6** — the chips follow the utility's own listing order; every `Start →` and `Sign in` shipped HELD with its reason (R3) ⚠ **AND THAT SENTENCE WAS TRUE FOR ONE DAY AND THEN ROTTED IN PLACE — `DEF-CWP-3925`.** R3 holds a control *until its screen lands*, and waves B, C, D, E and P landed `CWP-002`, `CWP-008`, `CWP-011`, `CWP-013` and `CWP-015` without anyone returning to the door: five of the six cards, the sign-in bar, and three of the frame's four nav words were still refusing over live screens on 2026-09-05, found by opening the product in a browser. **Only *What things cost* is held now**, and correctly — §9 allocates it no screen. The general lesson, recorded because it outlives this page: **a rule of the form *held until X* needs the test that fires when X arrives, written at the same time as the hold**; the counts a table cannot yet hold are ABSENT, not zero; **A7** — the fixture is two provisioned utilities and no Brazos Bend figure moved; **A9** — `errors.rate-limited` reached all eleven catalogues for the first time (`DEF-SHL-3643`). The walkthrough also prints the front page's measured round trip; the target is `OQ-CWP-1510`, OPEN.
**Journeys written:** none — every Phase 1 journey passes through `CWP-001` but none is complete here. **Ships as:** nominal `2.129.0`. **Size:** large — about 10 lane-days, two people (the ground tasks are the long pole and everything else in the CR waits on them).

| Task | Part | What it touches — verified at `b29edecd` | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **A1** | ground | `07-frontend/src/styles/route-b-migrated.txt` gains `portal/**` **in the module's first commit** (2,976 lines today, no `portal`); `routeBUtilities.test.ts` then owns the folder. B14 rule 21; `DEF-974` | `US-CWP-023` TC-7 (proved here early) · rule 21 | — | 1.3 | S |
| **A2** | ground | `06-backend/apps/portal/` per `CR-068` §11b — `apps.py`, `models.py`, `migrations/`, `api.py`, `guest_api.py`, `backoffice_api.py` (new — §0 row 18), `session.py`, `credentials.py`, `selectors.py`, `services.py`, `seams/`, `write_points.py`, `sample_data.py`, `tests.py`; `INSTALLED_APPS`; mounted in `06-backend/config/urls.py` beside lines 29–213 as three includes (guest, portal, back office). Guest and portal edges are **separate files and separate middleware** (`BR-CWP-011`) | `BR-CWP-011`, `BR-CWP-012` | — | 1.1 | S |
| **A3** | ground | Ids: a row in `12-governance/14-id-reservations.md` for `CWP-001`–`079`, `US-CWP-001`–`074`, `BR-CWP-001`–`096`, `EP-CWP-01`–`12` and a `DEF-` reservation block (**today only `J30`–`J47` are reserved, line 598**); module code `cwp` wherever tooling lists modules (`10-scripts/r2_status.py:69 MODULES`, `module_report.py`, `screen_report.py`); `10-scripts/02-trace_lint.py` green; pattern `\d{3,5}(?!\d)` everywhere (`DEF-2804`) | CLAUDE.md id grammar | — | 1.1 | S |
| **A4** | gate | ⚠ **THE NUMBERS ARE TAKEN AT PUSH TIME, NOT FROM THIS TABLE (`DEF-CWP-3634`).** This row named `g75` and `g78`, and both are now other people's — `g75_connection_table_no_secret.py` and `g78_work_writes_nothing_foreign.py`. `G74`–`G80` are all occupied as of 2026-09-04, so the next free is **`G81`**; re-check `10-scripts/gates/` at the moment you create the file, because three lanes took six numbers in the hours after this plan was written. The portal's **write-points gate** (`g<next>_portal_write_points.py`) — reads `apps/portal/write_points.py` **as data** and the portal surface's reachable writes; **not a grep for four table names** (`CR-068` §13). The portal's **screen-register gate** (`g<next+1>_cwp_screen_register.py`) — every route under `07-frontend/src/portal/routing/screenIds.ts` carries a `CWP` id from `CR-068` §9 and invents none; `g29` is **not** pointed at the portal. Both: `run()` + `__main__` + `selftest()` (the `DEF-1785` contract), registered in `run_gates.GATES` (`run_gates.py:121`) **in the same commit**, and each **proved RED first** in a worktree, failure quoted in the docstring | `BR-CWP-001`–`003` · `R12` · law 7 | A2 | 1.4 (+`G78`, new) | M |
| **A5** | 2a | `portal_settings` (portal-owned, `03-field-map.md` §1) — migration `0001_initial` and **`0002_rls_portal_settings.py`** (the `rls` in the name puts it under `human_owned.txt`'s glob `06-backend/**/migrations/*rls*` → 🔒, review-ledger row); defaults `is_live=false`, `self_read_enabled=false`, the other four `true` (`R8`, law 3). `GET/PUT settings/portal`, `GET/PUT settings/portal/branding` in `apps/portal/backoffice_api.py` under `SystemAdminOnly` (`core/permissions.py`). Branding **reads** `tenant.logo_bytes`/`logo_content_type` (`tenancy/models.py:145-146`) and `brand_primary_hex`/`brand_accent_hex` (`tenancy/brand.py`) — **stores nothing twice** (`BR-CWP-043`→`PR-43`). `GET /api/{tenant}/portal/public/front` in `guest_api.py` behind `PublicOnboardingThrottle` (`tenancy/api.py:84-88`) — reused, not copied (`BR-CWP-022`); returns branding, the switches, and the card list **already filtered** by switch and by published content. The tenant is resolved from the first path segment before anything is read (`BR-CWP-005`; `core/tenancy.py`) | `US-CWP-069`, `070`, `001` · `BR-CWP-005`, `007`, `022` | A2 | 1.14 · 1.5 (front half) | M |
| **A6** | 2b | **Staff app:** `SettingsPage.tsx:37-40` `CONFIGURE_SUB_TABS` gains `customer-portal` (label key in all **eleven** catalogues `07-frontend/src/i18n/locales/*.json`; read `g14_prototype_conformance.py:247-260` first — G14 is already red and its baseline **is not raised**); `CWP-069` Overview (T8 + `TwoCol`: address, QR, on/off, five switches each with one sentence, the four counts — *Readings are off, so nothing is counted* when off) and `CWP-070` Branding (T8: read-only shared four with *edit in Company*, portal-only fields, live preview) in `07-frontend/src/features/tenancy/`. **Portal app:** `07-frontend/src/portal/` — `GuestFrame`, `PageHead` (composes staff `PageHeader.tsx`), `ErrandCard`, `CardGrid3`, `InfoBar`, `Button` held presentation (staff `buttonKit.ts:127` disabled classes **plus** a visible ≤6-word reason — `BR-CWP-056`), tokens from `09-component-inventory.md` §0 with `--brand` from the tenant's hex; `CWP-001` at **`/:tenant/portal`** (a sibling of the staff shell in `App.tsx:215`, **not** `/:tenant` — §0 row 3); holding page when `is_live=false`; `screenIds.ts` for the portal mirroring `CR-068` §9. Layout per `08-screen-layouts.md` T1 | `US-CWP-001`, `069`, `070` · `BR-CWP-007`, `021`, `093` · B14 r21, r31, r32 | A1, A5 | 1.16 (`CWP-001`) · 1.17 (`069`, `070`) | L |
| **A7** | 2c | `06-backend/tests/test_us_cwp_001_tc*.py`, `test_us_cwp_069_tc*.py`, `test_us_cwp_070_tc*.py` — every §3 case including the `isolation`-marked ones (001 TC-5/6, 069 TC-8, 070 TC-7); vitest beside each screen; `apps/portal/sample_data.py` first cut — tenant `pine-hill` (brand `#EC3013`/`#E15B47`, office `8am–5pm · (512) 555-0148`, emergency `(512) 555-0100`, strapline) and `oak-ridge`, **without moving one Brazos Bend figure** (`G4`, `G61`); the seeding decision recorded (header, *Fixture*) | all three stories' §3/§4 | A5, A6 | 1.18 (part) | M |
| **A8** | 2d | `10-scripts/render-checks/cr068-a-switch-it-on.mjs` — steps 1–7 of the demo above, asserting the sentences in the exit test, computed style on `.grid`/`.border` utilities (they compiled — `DEF-974`), no `[0-9a-f]{8}-…` uuid and no `BR-`/`OQ-`/`DEF-` in any customer-facing text, no sideways scroll at 1440; screenshots to `/tmp/cr068-a/`. `G75` and `G78` RED proofs quoted in their docstrings and in the wave's close record. Layout of `CWP-001`, `069`, `070` diffed by eye against `08-screen-layouts.md` and the wireframes | law 6, law 7 | A6, A7 | 1.19 (part) | M |
| **A9** | doc | CHANGELOG entry and the version at merge (`G35` lockstep: `package.json`, `package-lock.json` ×2, `pyproject.toml`); `20-wave-tasks.tsv` rows `A1`–`A9` moved from `open`; decision-log rows for the two judgments (guest routes under `/portal`; back-office settings endpoints in `apps/portal`) and the fixture decision; review-ledger row for `0002_rls_portal_settings.py` **in plain English with a figure**; `07-endpoints.md` §3 and the stories' §5 brand column names stamped, dated | law 9, 10, W | A8 | 1.19 (part) | S |

### Wave B — *Report a problem and track it* · `J31`

**Goal a person can see:** a passer-by who is not a customer reports a burst main, gets a
reference, and can look it up later — and a clerk sees it on the worklist with channel
*Customer portal*, the first row in the product ever to carry that value.
**Stories:** `US-CWP-002` · `US-CWP-007` · `US-CWP-008` · `US-CWP-009` · `US-CWP-010`
**Demo script** (D. Okafor, `(512) 555-7730`, not a customer; `1408 Elm St`; `RP-26-0412`):
1. From `/pine-hill/portal`, *Report a problem →*. Pick **a leak or a burst**, type *Water coming up through the pavement outside number 1412…*, name and phone, send. The photo picker is **held** with its reason (§0 row 13).
2. **Report sent**: `RP-26-0412`, 9:52am, *near 1412 Elm St*, and the four-step *what happens now* with step 2 current. The closing line says a second report is welcome.
3. Pick **a smell of gas** on a fresh form: the page returns `(512) 555-0100` and **creates nothing** — no request row, no interruption row (asserted on the database).
4. Staff app: the requests list (`ServiceRequestsListPage.tsx`) shows the report with channel **Customer portal**; the detail's new *Interruption* section moves it to **crew on site** and sets the affected area *Elm St, 1400–1500*.
5. Guest: *Track anything*, `RP-26-0412` + `78702` → *A leak or a burst, near 1412 Elm St · Crew on site* — **no name, no balance, no other reference** (asserted on the response body).
6. Six wrong pairs on Track from one address → the sixth reads *locked for fifteen minutes*; a **correct** pair from the same address is still refused; the same pair from `/oak-ridge/portal` is not locked.
7. The 61st report inside one minute → refused in five or six words (B14 rule 33), in all eleven catalogues (`g32` baseline 0).
8. The affected set: `1408 Elm St · A/B/Common` and `1412 Elm St` are in it; `22 Palm Ct` is not.
**Exit test:** `BR-CWP-027` — reporter not a customer, address free text, `premises_id` null until a clerk resolves it · `BR-CWP-024`/`025` — the track response body names no customer field · `BR-CWP-023` — lock per tenant, per form, per address · `BR-CWP-026` — no account row changed by any guest write · `BR-CWP-076` — the row carries `customer_portal`.
**Depends on:** A. **Blocked by:** the consumer-upload re-sign (photo held — task B9). **Runs in parallel with:** C, D.
**Walkthrough script:** `cr068-b-report-and-track.mjs` · **Journeys written:** `08-qa/01-e2e/journeys/J31-report-a-burst-and-track-it.md`; `07-frontend/e2e/J31.spec.ts` activates when the wiring index says all five stories are built.
**Ships as:** nominal `2.130.0`. **Size:** large — about 9 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **B1** | 2a | `interruption` in **`apps/metering`** (B2 §2; `03-field-map.md` §2) — kind enum incl. `gas_smell`, status `looking_into_it → crew_on_site → resolved`, `location_text`, nullable `premises_id`, `affected_area` jsonb (street + number range), reporter fields, `expected_back_on`; migration + `*rls*` migration (🔒 → ledger row); **the affected-area rule** resolving a range to `Premises` rows (`metering/models.py:264`) within the tenant; status transition service refusing a second `resolved` | `US-CWP-008` · `BR-CWP-027`, `012` | A2 | 1.10 | M |
| **B2** | 2a | `POST /api/{tenant}/portal/public/reports` in `guest_api.py`: writes the interruption **and** a service request through `service_request_service.create_request` (474) + `submit` (1886) with `channel="customer_portal"` (free text, `customers/models.py:1504`); `gas_smell` returns the emergency phone and writes **nothing**; phone required; a second report on the same street accepted with *already reported*. `POST /api/{tenant}/portal/public/track`: reference + second fact across the `SR-`/`RP-`/`PAY-` series, returns status and dates only. The lockout: cache keyed tenant + form + address, five wrong → fifteen minutes (**not a table** — `US-CWP-002` §8) | `US-CWP-007`, `009`, `010`, `002` · `BR-CWP-022`–`028`, `076` | B1 | 1.8 · 1.9 · 1.15 | M |
| **B3** | 2a | The clerk's write: `PATCH` interruption status + affected area, mounted on the **staff** request API (`apps/customers/service_request_api.py`, `AdminOrClerk`), reaching metering through a seam — *new — no task in §12* (§0 row 22) | `US-CWP-008` TC-1 | B1 | new | S |
| **B4** | 2b | `CWP-006` Report a problem (T3 under `GuestFrame`: `RadioList` ×6 with hints, `FormField`, `PhotoPicker` **held**, `ConsequenceBox`, `Panel.Emergency`), `CWP-007` Report sent (`KVList`, `ChecklistTimeline` ×4), `CWP-012` Track anything — in `src/portal/`, per `08-screen-layouts.md`. Refusal sentences for the throttle and the lock in all eleven catalogues, five or six words | `US-CWP-007`, `009`, `010`, `002` · B14 r33 | A6, B2 | 1.16 (`006`, `007`, `012`) | M |
| **B5** | 2b | Staff: an *Interruption* section on `07-frontend/src/features/customers/ServiceRequestDetailPage.tsx` — status control, affected area, expected back-on — **no new `S`-id** (`R13`); the list's channel column shows *Customer portal* (label already rendered — `customers/models.py:1491`) | `US-CWP-008` | B3 | new | S |
| **B6** | 2c | `test_us_cwp_002_tc*`, `_007_`, `_008_`, `_009_`, `_010_` — all §3 cases; the affected-area cases (008 TC-2/3/5); the lock cases (002 TC-3–7) on the cache; **the 61st-request case**; fixture: the Elm St burst, the Cedar Row low pressure, `1408 Elm St` A/B/Common, `1412 Elm St`, `22 Palm Ct` | five stories' §3/§4 | B1–B5 | 1.18 (part) | M |
| **B7** | 2d | `cr068-b-report-and-track.mjs` — the eight steps, asserting *Crew on site*, the absence of any customer field in the track response (read via `page.request`), the lock sentence, the gas-smell phone number and zero rows; screenshots. RED proof: remove the second-fact check in a worktree and show 010 TC-3 fail | law 6, 7 | B4–B6 | 1.19 (part) | M |
| **B8** | doc | `J31` journey file (handoff: an `interruption` row, a request on the worklist with `customer_portal`, `RP-26-0412` on screen); CHANGELOG + version; `20-wave-tasks.tsv`; review-ledger rows for the `*rls*` migration; decision-log row for B3/B5's placement | law 9, W | B7 | 1.19 (part) | S |
| **B9** | doc | **The consumer-upload re-sign, put to the PO in plain English with a figure** (HUMAN-GUIDE §6; `CR-068` §2b): today a photo of a burst main, a meter dial or a queried bill cannot be attached by a customer because uploads were signed as staff-only; the ask is the same allow-list and size cap the counter uses, plus the scan the store does not yet have. Until ruled, every `PhotoPicker` is held with its reason. Legitimately reaches the PO — it collides with a signed rule (law 13) | `US-CWP-007` TC-8, `042` TC-11, `066` TC-7, `064` | — | new | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. **B1–B2** — `POST portal/public/reports` and `POST portal/public/track` are both served from `guest_api.py`, as the table says. **B4** — `CWP-006` is `/report` (`portal/guest/ReportProblem.tsx`) and `CWP-012` is `/track` (`portal/guest/TrackAnything.tsx`); `CWP-007` is the confirmation STATE of `/report` and has no address of its own, which is what `screenIds.ts` records and not a gap. **B6** — all five stories are exercised by tests. **B7** — `cr068-b-report-and-track.mjs` EXISTS; it is one of only five browser walkthroughs in the repo. **B9 IS STILL OPEN**: the consumer-upload re-sign is unruled, the portal accepts no upload at all (`BR-CWP-089`), and every `PhotoPicker` is still held.

### Wave C — *Start service before identity exists* · `J32`

**Goal a person can see:** somebody moving in types an address, learns what is available
and what it costs, applies without an account, and the paperless consent they gave is a
record with the words they saw — nothing is charged, no document is demanded up front.
**Stories:** `US-CWP-012` · `US-CWP-013` · `US-CWP-014` · `US-CWP-015`
**Demo script** (`31 Palm Ct`; connection fee `$185.00`, deposit `$150.00`):
1. `/pine-hill/portal` → *Start service →*. Type `31 Palm Ct`, *Check →*. Four rows: **Water · YES · $185.00 · $150.00**, **Sewer · YES · Included**, **Trash · YES · $0.00**, **Electric · NOT HERE** (greyed). The *IF YOU APPLY* box: `$185.00` before we start, `$150.00` on your first bill.
2. Type an address that matches no premises: *a person will look at it* — **never a refusal** (`BR-CWP-093`).
3. *Apply for service →* — **About you** (`CWP-047`): name, contacts, move-in date; a returning customer is recognised on the facts the counter uses, and the screen says so without disclosing anything. Close the tab.
4. Reopen the draft link: **saved from the first keystroke** — the fields are still filled, no reference yet.
5. **Check and send** (`CWP-009`): the `KVList`, *WE WILL NEED THESE FROM YOU* with two rows at **AFTER YOU APPLY**, the boxed *How we send your bills* consent with its helper, the four-bullet `ConsequenceBox`. Send.
6. A reference on screen; in the database one `service_request` (channel `customer_portal`) and **one `portal_consent` row** with `wording_version`, `agreed_on` not in the future, `taken_on_screen = CWP-009`. **No payment, no document, no account.**
7. *Ask for a quick service* (`CWP-010`): six cards read from the tenant's request categories — a re-read, a missed collection, a copy of a bill — *Ask →* lands a request and a reference.
8. Track the application by reference + phone on `CWP-012`: progress and dates only.
**Exit test:** `BR-CWP-026` — no account row changed · `BR-CWP-087`/`R5` — the consent row carries the wording version and cannot be dated in the future (constraint) · `BR-CWP-021` — availability names services, never the current occupier (asserted on the body) · hard rule 2 — every money figure displays two decimals from four stored.
**Depends on:** A. **Blocked by:** nothing (`US-CWP-050` fees is Phase 5; the fee table here is read-only). **Runs in parallel with:** B, D.
**Walkthrough:** `cr068-c-start-service.mjs` · **Journeys written:** `J32-availability-apply-consent.md` (J45's first half is this consent; J45 is written in wave F where it is withdrawn).
**SHIPPED 2026-09-04 AS `2.137.0`** (the nominal figure below was `2.131.0`; waves land in the order they merge, and B, D and two CR-069 waves landed first). **Size:** medium — about 7 lane-days.

⚠ **FOUR OF THIS WAVE'S OWN PACKET ROWS WERE WRONG ABOUT THE CODE, AND THE CODE WON** (§0's rule, applied to §0's own author). `DEF-CWP-3700` — the draft cannot be a `service_requests` row, because `BR-CUS-093` numbers one at creation. `DEF-CWP-3701` — `service_requests` has no `category` column and no lookup holds request kinds. `DEF-CWP-3702` — `portal_consent.account_id` cannot be NOT NULL when the only screen that takes the consent belongs to somebody with no account. `DEF-CWP-3703` — the connection fee is a charge code, not a tariff column, and effective dating is the plan's. `DEF-CWP-3704` — `GET /public/prices` has no wave-C screen and is deliberately not built. All five are filed with their repairs; the module documents are stamped.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **C1** | 2a | `GET /public/premises/availability` and `GET /public/prices` in `guest_api.py`, reading `Premises`/`Unit` and their services (`metering/models.py:264,455`) and the tariff's connection fees and `PlanDepositRule` (`rating/models.py:1338`) through seams — **computes nothing** (`CR-068` §2d); unknown address → *a person will look at it*; a move-in vs a new connection distinguished on whether the unit is occupied | `US-CWP-012` · `BR-CWP-021`, `026`, `093` | A2 | 1.6 · 1.7 | M |
| **C2** | 2a | `PUT /public/applications/{draft}` (upsert from the first keystroke, no reference until submit), `POST …/submit` (creates the request via `service_request_service` with `channel="customer_portal"`, allocates the reference, records the document checklist as *after you apply*, **writes `portal_consent`** — portal-owned table, `*rls*` migration 🔒), `POST /public/requests` (the quick asks, categories from the tenant's configuration — `US-CWP-060` TC-8's rule applied early). Returning-customer recognition uses the counter's blind-indexed identity fields **read-only** and discloses nothing (`BR-CWP-031`'s spirit) | `US-CWP-013`, `014`, `015` · `BR-CWP-026`, `028`, `087` | A2, B2 (throttle + reference series) | 1.8 (split: applications) | M |
| **C3** | 2b | `CWP-008` (T3 under `GuestFrame`: address, *Check →*, `MiniTable` with greyed Electric row, `ConsequenceBox` *IF YOU APPLY*), `CWP-047` About you (T2 under `GuestFrame`, URL strip *not signed in · step 2 of 4*), `CWP-009` Check and send (T2: `KVList`, document rows with `StatusChip` AFTER YOU APPLY, boxed consent checkbox + helper *We print them as well…*, `ConsequenceBox` ×4, *Send my application ✓*), `CWP-010` quick service (T1) | four stories · B14 r11 (consequence box), r32 | A6, C1, C2 | 1.16 (`008`, `009`, `010`, `047`) | M |
| **C4** | 2c | `test_us_cwp_012_tc*`…`_015_tc*`; consent constraint case (`agreed_on` never future); draft-survives-closed-tab case; fixture: `31 Palm Ct` with Water/Sewer/Trash and no Electric, `$185.00` / `$150.00`, the request categories | four stories' §3/§4 | C1–C3 | 1.18 (part) | M |
| **C5** | 2d | `cr068-c-start-service.mjs` — the eight steps; asserts the four availability rows and their figures, the *a person will look at it* sentence, the consent row's wording version via the API, and that the fee figures display two decimals | law 6 · hard rule 2 | C3, C4 | 1.19 (part) | S |
| **C6** | doc | `J32` journey file; CHANGELOG + version; TSV; review-ledger row for the consent RLS migration in plain English (*a consent without the version of the words is not a consent*) | law 9, W | C5 | 1.19 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. This wave already carried **SHIPPED 2026-09-04 as `2.137.0`** and the four-defect divergence block above; what it did not carry was a stamp in the form A, D, P, Q and R use, so a reader scanning for one found nothing. The code confirms it: `CWP-008` is `/start-service`, `CWP-047` and `CWP-009` are the two steps of `/start-service/:draft` (`portal/guest/ApplyForService.tsx`, 721 lines), `CWP-010` is `/ask`; `public/premises/availability`, `public/applications/{token}`, `…/submit`, `public/requests` and `public/quick-services` are all served; all four stories are tested; and `cr068-c-start-service.mjs` EXISTS.

### Wave D — *Help, tips and where you can walk in* · `J34` · `J46` · `J33` (public half)

**Goal a person can see:** a clerk writes an answer, publishes it, and a visitor reads it
the same minute — in English when their language has no translation; a depot stays off the
public page without being deleted; both counters close on Thanksgiving with nobody typing
a closure.
**Stories:** `US-CWP-071` (⚠ boundary — `OQ-1398`) · `US-CWP-072` · `US-CWP-073` · `US-CWP-074`
**Demo script** (eight answers, six published; three centres, the depot hidden; watering tip Jun–Sep):
1. Staff: Settings → Configure → Customer portal → **Help & answers** (`CWP-071`): eight rows — six PUBLISHED, one DRAFT, one NOT SHOWN — with *read this month*; drag row three to the top.
2. Open *Why is my bill higher than last month?* (`CWP-072`): set *Also show on: the bill screen*; the language table reads `English PUBLISHED · Español (México) PUBLISHED · Français NEEDS TRANSLATING · हिंदी PUBLISHED`. **Publish** — the screen warns there is no approval step.
3. Guest `/pine-hill/portal/help` (`CWP-011`): **six** answers in the back office's order; the draft and the not-shown are not there and **no count of hidden answers appears**. Switch the browser to French: the answer shows in **English** with a line saying so (`BR-CWP-094`).
4. Open the answer three times; press *No* on *did this help?* once. Staff `CWP-071`: the read count moves `1,204 → 1,207` and the vote is its own event.
5. Staff **Tips** (`CWP-073`): six tips, four showing today. The freeze tip is off **and** Dec–Feb.
6. Staff Reference data → **Service centres** (`CWP-074`): three rows, the depot *shown to customers* off. Edit the north counter (`CWP-075`): hours, four of five action rows **no**, *takes* cash and cheque only.
7. Guest **Where you can walk in** (`CWP-013`): **two** centres; the north counter reads *Closed today · Opens Thursday at 9:00am* from the clock (Tue & Thu hours on a Wednesday; the drawing's *Tuesday* was wrong — `DEF-CWP-3604`); `CWP-014` shows four of five rows **no** and the footer *Closed 26 November — Thanksgiving* read from `HolidayCalendar`.
8. Hide every centre: the *Visit us* link, the page and the routes are **absent** (`BR-CWP-093`). Unpublish every answer: the *Help* link is absent.
**Exit test:** `BR-CWP-094` — `status = published` is in the **query** (asserted by a draft that never leaves the API) · `BR-CWP-096` — hidden is a state (the row is still in the back-office list) and Thanksgiving comes from the calendar · `BR-CWP-095` — at most one tip per screen, an empty tip response is a normal response · `BR-CWP-093` — nothing empty ever appears · `OQ-1398` boundary — *needs translating* is a **visible state** and no translation workflow is promised on any screen.
⚠ **AS BUILT — 2026-09-04, `2.138.0`.** Where this table and the code disagreed, the code won and the register says so. **D1** — the six tables are `tenancy`'s and their migrations are `0037` + `0038_rls_…`; every child carries its OWN `tenant_id` (a policy on the parent does not constrain a query that starts at the child), and `allowed_actions`/`payment_methods_accepted` are JSON rather than `text[]` because the suite runs on SQLite (law 14). **D2** — ⚠ **the one guest WRITE is served by `apps/tenancy`, not by `apps/portal`**: `help_answer_feedback` is a tenancy table, B2 §2 forbids a cross-module write, and `G81` holds that line file by file — so `BR-CWP-001`'s four write points are untouched and `CP-34`'s *"the portal's smallest write"* is `DEF-CWP-3727`. **D3** — **B14 rule 36 was ratified while this wave was building** and the first draft of the three staff screens broke it (three hand-rolled tables, no pagination footer, no sortable header); they compose `DataTable`, `FilterBar`, `Panel`, `StatusPill` and `RowActions` now, and the two pieces the kit lacked — `Switch` and `ChipMultiSelect` — were **added to the kit**, which also fixed rule 36's own live breaches (d) and (e) on wave A's Overview and Branding (`DEF-CWP-3729`). **A language's own name is computed by `Intl`, not translated** — 110 catalogue lines that could only ever be identical are 110 lines `G15` would rightly call English pasted in. **D4** — 42 backend cases, 30 vitest, 11 on PostgreSQL; the RLS proof reads `relrowsecurity` AND `relforcerowsecurity` from `pg_class` rather than trusting an empty SELECT. **D5** — the walkthrough runs with the server clock pinned to **Wednesday 18 November 2026** (`PORTAL_CLOCK_OVERRIDE`, honoured only under `DEBUG`), because the two sentences `BR-CWP-096` is about can only be SEEN on a Wednesday in November; 70 assertions green. **AND THE FIXTURE WRITES NO HOLIDAY ROW** — provisioning already seeds the federal holidays, so a brand-new Pine Hill closes on Thanksgiving having done nothing at all, and the label that ships is the calendar's `Thanksgiving Day` rather than §4's abbreviated *Thanksgiving*. **The gate is `G88`**, not the `G75`/`G78` this plan named — those were taken (`DEF-CWP-3634`), and it was proved RED on the real code twice before it was trusted. `OQ-1398` is OPEN and untouched: the mechanism ships, the workflow is not promised, and a test asserts the absence of the promise.
**Depends on:** A (the Configure segment, the guest frame). **Blocked by:** `OQ-1398` (who maintains the answers) — **does not block the mechanism**; the boundary is the visible untranslated state. **Runs in parallel with:** B, C.
**Walkthrough:** `cr068-d-help-tips-centres.mjs` · **Journeys written:** `J34-where-you-can-walk-in.md`, `J46-answer-authored-published-read-voted.md`, `J33-read-an-answer-end-at-a-person.md` (J33's last screen `CWP-054` is Phase 3 wave I; the file says so).
**Ships as:** nominal `2.132.0`. **Size:** large — about 10 lane-days (six tables, seven staff screens, four guest screens).

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **D1** | 2a | In **`apps/tenancy`** (it owns published content — `03-field-map.md` §2): `help_answer` (statuses `draft \| published \| not_shown`, `position`, `also_show_on_screen`), `help_answer_variant` (one per locale of the **eleven**: `de en es-MX es fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR`, status `published \| needs_translating`), `help_answer_feedback` (`read \| helpful \| not_helpful` — **counted separately**), `tip` (`target_screen`, `month_from/to`, `is_on`, `position`), `service_centre`, `service_centre_hour`; `*rls*` migrations (🔒). Back-office endpoints in `apps/tenancy` (`07-endpoints.md` §3 minus the two portal-settings pairs) | `US-CWP-071`, `073`, `074` · `BR-CWP-093`–`096` | A2 | 1.11 · 1.12 · 1.13 | L |
| **D2** | 2a | Guest reads in `guest_api.py`: `GET /public/help` (**`status = published` in the query**, locale fallback to English), `GET /public/help/{slug}`, `POST /public/help/{slug}/feedback`, `GET /public/service-centres` (only `is_shown_to_customers`; **404 when none**), `GET /public/service-centres/{slug}` (today's status from the clock; closures from `HolidayCalendar`, `tenancy/models.py:1292`), `GET /public/tips?screen=` (at most one; empty is normal) | `US-CWP-072`, `073`, `074` | D1 | 1.11–1.13 (read half) | M |
| **D3** | 2b | Staff, in `features/tenancy/`: `CWP-071` (T8 + T5, drag handle `⋮⋮`, filters All · Published · Draft · Needs translating), `CWP-072` editor (T8 + T6 + `TwoCol`, language table, *also show on*, publish warning), `CWP-073` Tips (T8 + T5 then `TwoEqual`; a 30-word tip flagged against the fifteen-word guidance), `CWP-074` centres as a card in **Reference data** (`SettingsReferenceData.tsx`, breadcrumb *Reference data › Service centres*) and `CWP-075` editor (`ToggleChips` for payment methods; *Remove* in the **danger** tier warning a printed address may still circulate). Guest, in `src/portal/`: `CWP-011` (T3, topic chips, `Panel` *STILL STUCK?*), one answer with in-text controls, `CWP-013` `CentreCard`s, `CWP-014` (T6; *Call* as a **plain** outline — B14 rule 6, `08-screen-layouts.md` §*where the drawings and B14 disagree*). `TipBar` and `AttachedAnswerCard` components defined once (their signed-in slots land in wave H) | four stories · B14 r6, r15, r21, r33 | A6, D1, D2 | 1.17 (`071`–`075`) · 1.16 (`011`, `013`, `014`) | L |
| **D4** | 2c | `test_us_cwp_071_tc*`…`_074_tc*` — the query-level exclusion (071 TC-2), the hidden-count absence (TC-3), the English fallback (TC-6), the two-reasons freeze tip (073 TC-3), Thanksgiving from the calendar (074 TC-3), hide-every-centre (TC-5); fixture: eight answers (the bill-higher answer at `1,204` reads), six tips, three centres with hours, `26 Nov` in `HolidayCalendar` | four stories' §3/§4 | D1–D3 | 1.18 | M |
| **D5** | 2d | `cr068-d-help-tips-centres.mjs` — the eight steps with the clock pinned to a Wednesday and to 26 November; asserts *Closed today · Opens Thursday at 9:00am*, *Closed 26 November — Thanksgiving*, exactly one `TipBar`, the absent *Visit us*/*Help* links, the English fallback line; screenshots | law 6 | D3, D4 | 1.19 (part) | M |
| **D6** | doc | `J33`, `J34`, `J46` journey files; CHANGELOG + version; TSV; review-ledger rows for the tenancy `*rls*` migrations; the `OQ-1398` boundary stated in the wave's close record (*what ships, what is not promised*); `US-CWP-072` and `073` noted as **finished by wave H** for their signed-in surfaces | law 9, W | D5 | 1.19 (part) | S |
---

## 3 · PHASE 2 — LAUNCH: customers can sign in and see everything they have

**Launch sentence:** `CR-068` §12 Phase 2, kept verbatim in §1. **Paying is visible and
held** — every Pay control appears in its normal place, disabled, carrying its reason
(`R3`, `BR-CWP-056`); that is a deliberate launch state and the announcement says when
paying arrives.
**Stands on:** W2 · W3 · W4 (built) · **W6** for codes and reset links to *arrive* by
email — the queue exists today, sending activates in W6 (§0 row 23).
**Stories (21):** `US-CWP-016`–`021`, `023`–`028`, `031`–`034`, `036`, `040`, `041`,
`043`, `048`.
**Exit test:** the Phase 2 demonstration in §1.
**Order:** wave **E** first (credentials, session, balance, shell — everything signed-in
stands on it); **F, G and H run in parallel** after E.

### Wave E — *Getting in* · `J35` · the balance read and the shell

**Goal a person can see:** a customer who has never signed in enrols on three facts off
her paper bill, proves it is her with a code sent only to the phone already on file, sees
what the login can and cannot do — including `$142.18` — and lands inside the portal shell.
**Stories:** `US-CWP-021` (🔒) · `US-CWP-024` · `US-CWP-023` · `US-CWP-016` · `US-CWP-017` · `US-CWP-018` · `US-CWP-019` · `US-CWP-020`
**Demo script** (Maria Alvarez, `ACC-10432-A`, `78702`, `Alvarez`, mobile `••• ••• 4218`):
1. `/pine-hill/portal` → *Sign in*. The front door (`CWP-015`) states **three doors**: sign in · first time here · just want to pay (reaches quick pay with no password). Pine Hill's **staff** admin email and password are refused here with the ordinary failure — no session row (asserted).
2. *First time here* → **Find my account** (`CWP-016`): `ACC-10432-A` + `78702` + `Alvarez`. The response carries **no name, no balance, no address** (asserted on the body). A wrong surname is refused identically to an unknown number. Four wrong tries → *locked for fifteen minutes*.
3. **Prove it is you** (`CWP-017`): *It went to the phone we already hold: ••• ••• 4218. It lasts ten minutes.* The code is read from the outbound queue row (W6 not yet activated) and typed. An account with no phone and no email dead-ends into *ring the office*.
4. **Choose a password** (`CWP-018`): eight characters refused on a tenant whose `pw_min_length` is twelve (policy read, not hardcoded); the **consequence panel** names `ACC-10432-A`, `1408 Elm St · A`, Water/Sewer/Trash and **`$142.18`**, and that the login cannot close the account or change who it belongs to.
5. Lands on the **shell**: header *Pine Hill Water & Power* in `#EC3013`, switcher reading `1408 Elm St · A` **as a label** (one account), six tabs, bell, avatar `MA`. Home shows the balance tile `$142.18 · Due 14 Sep · in 12 days` (the rest of Home is wave F).
6. Sign out; **Forgotten password** (`CWP-019`) with a real address and then with an unknown one — *check your email* both times, **byte-identical**, and no email queued for the unknown one.
7. Sign in as the landlord: the switcher is a real `<select>` of **four flat entries** — the common-areas master is one of them, not a parent — and the tenants' own accounts are not in it.
8. On PostgreSQL: a query with no `app.tenant_id` set is refused by RLS `FORCE` (the isolation proof, quoted). A portal session calling a staff route is refused at the edge; `G76` green, and RED in a worktree when a portal credential is joined to `identity.user`.
**Exit test:** `BR-CWP-032` — between matched and proven, the body discloses nothing · `BR-CWP-033`/`034` — the code goes only to the stored contact (the outbound row's destination asserted) and dead-ends when none · `BR-CWP-038` — identical reset responses · `BR-CWP-004`/`011` — `G76` red-then-green, staff credential refused, staff route refused · `BR-CWP-008`/`009`/`013` — the set is flat and re-derived from the two sources on read · `BR-CWP-015`/`047` — four rows total `$872.82`, never merged, never cached · hard rule 1 — RLS proof on real PostgreSQL.
**Depends on:** A. **Blocked by:** nothing (`OQ-1397` blocks widening the set, not building it flat). **Runs in parallel with:** nothing in this phase — F, G, H wait for it.
**Walkthrough:** `cr068-e-getting-in.mjs` · **Journeys written:** `J35-enrol-cold.md` (+ `J35.spec.ts`).
**Ships as:** nominal `2.133.0`. **Size:** large — about 12 lane-days, two people.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **E1** | 2a 🔒 | `portal_credential`, `portal_session` (`03-field-map.md` §1) — Argon2id, `failed_attempts`/`locked_until` (5 → 15 min, `BR-CWP-036`; enrolment form 3 tries), `otp_channel`, `account_set` jsonb built from **exactly two sources** and **re-derived on read**; `0003_rls_portal_credentials.py` (🔒 — RLS + session scoping; review-ledger row). `session.py`: resolve tenant from the path → `set app.tenant_id` (`core/tenancy.py`) → force RLS → **then** read the credential. **Never joins `identity.user`** (`identity/models.py:41` `sessions` is the staff table). Password policy read from `SecurityPolicy.pw_min_length` (`identity/models.py:249`). `credentials.py`: one-time codes (ten minutes, resend invalidates, six wrong locks) queued on the existing outbound queue; SMS **held** (no provider until W8) | `US-CWP-021`, `018`, `019` · `BR-CWP-004`–`011`, `029`–`040` | A2 | 2.1 · 2.2 | L |
| **E2** | 2a | The seven auth endpoints in `api.py` (`07-endpoints.md` §2): `find-account` returns matched/not-matched **and nothing else** (`BR-CWP-032`), matches on account number + service postcode + last name/company **never DOB/SSN** (`BR-CWP-031`), refuses an already-enrolled account with a route to reset **without confirming a login exists**; `verify-code`; `set-password` (guarded on the endpoint, not the wizard — 019 TC-4); `forgot-password` (**same body, same timing**, staff store not consulted — `BR-CWP-038`); `reset-password` (seven-day link, single use); `sign-in` refusing staff credentials with the ordinary failure; `sign-out`, `sessions/revoke-all`, `GET session`, `GET accounts` | `US-CWP-016`, `017`, `018`, `019`, `020`, `021` | E1 | 2.1–2.3 | L |
| **E3** | 2a | **The balance read** — `GET accounts/{id}/balance`, `GET balance/summary` — in `seams/payments_seam.py` **composing** `outstandings()` (`payments/outstandings.py:287`), `customer_open_bill_position()` (`customer_position.py:93`) and `billing_seam.outstanding_positions`; sees **nothing above the issued bill** (`BR-CWP-041`); counts a corrected pair once; excludes void; part-paid is neither paid nor unpaid; **never cached** (`BR-CWP-047`); totalled across the set and never merged (`BR-CWP-015`). No arithmetic of its own (`CR-068` §2d) | `US-CWP-024` · `BR-CWP-015`, `041`, `047` | E1 | 2.4 | M |
| **E4** | gate | ⚠ **NEXT FREE AT PUSH TIME, NOT THE NUMBER PRINTED HERE (`DEF-CWP-3634`)** — `g76` and `g77` are `g76_operation_modes.py` and `g77_provider_key_branches.py` on the branch. The **staff-separation gate** — no FK, join or import path from `apps/portal` credentials/sessions into `apps/identity`; a portal session cannot authenticate a staff route and a guest request cannot reach the portal edge (`BR-CWP-011`); registered same commit; **RED first** by joining a credential to `identity.user` in a worktree. The **guest-leak gate** — a guest serialiser field set is a declared allow-list (amount, status, masked name, dates) and a track/lookup response carries no customer field; RED first by adding `email` to a guest serialiser | `BR-CWP-004`, `011`, `021`, `024` · law 7 | E2 | `G76`, `G77` (§13) | M |
| **E5** | 2b | `CWP-015` Front door (split `Card` 50/50), `CWP-016` (T2), `CWP-017` (T7, masked contact, resend, *wrong number? ring the office*), `CWP-018` (T4 50/50 with the `ConsequenceBox` naming the balance — **the first screen in the flow that may show one**), `CWP-019` (T7). **`PortalShell`** per `09-component-inventory.md` §1: header, `AccountSwitcher` (a `<select>` per rule 8, **a label when the set has one entry**), Messages bell, Help, `Avatar`, six tabs with `aria-current`; changing the switcher re-scopes **every** tab through the query, never the screen (`BR-CWP-010`). Home renders the lead `KpiTile` balance from E3 (the rest is F). Phone layouts `CWP-076`–`079` **deferred by PO instruction 2026-09-03** (`08-screen-layouts.md` header) — the shell's narrow width is not asserted | `US-CWP-016`–`020`, `023`, `024` · `BR-CWP-010`, `039` · B14 r8, r11 | A6, E2, E3 | 2.5 · 2.14 (`015`–`019`) | L |
| **E6** | 2c | `test_us_cwp_016_tc*`…`_021_tc*`, `_023_`, `_024_` — including 021 TC-7 marked `isolation` and **run under `DJANGO_SETTINGS_MODULE=config.settings.local` against real PostgreSQL** (law 14: the SQLite suite has no RLS); 020 TC-2 timing/byte identity; 024 TC-2 `$872.82`, TC-3 `$102.18`, TC-6 corrected pair once; fixture: Maria's credential-less customer, `ACC-10432-A`, `BL-2608-0141` `$142.18` due 14 Sep, the landlord's four accounts (`$142.18`, `$0.00`, `$318.04`, `$412.60`), a tenant with `pw_min_length=12`, an account with no contact, an identically-numbered Oak Ridge account | eight stories' §3/§4 · law 14 | E1–E5 | 2.15 (part) | L |
| **E7** | 2d | `cr068-e-getting-in.mjs` — the eight steps; the code read from the queue via the API; asserts the masked phone string, the consequence panel's `$142.18`, the label-not-control switcher, byte-identical reset bodies (compared as strings), `aria-current` on the active tab, computed style on the shell's `border-b-[3px]`; screenshots. `G76`/`G77` RED proofs quoted | law 6, 7 | E5, E6 | 2.16 (part) | M |
| **E8** | doc | `J35` file + spec; CHANGELOG + version; TSV; **review-ledger rows for `0003_rls_portal_credentials.py`, `session.py` and `credentials.py` in plain English with a figure** (*a defeated portal login costs one customer's data — Maria's — never the utility's whole book*); decision-log row: the SMS code channel is held until W8, email codes ride the queue until W6 | law 9, W · `g07` | E7 | 2.16 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. **E2** — all seven auth endpoints are in `api.py` (`enrol/find-account`, `enrol/verify-code`, `enrol/set-password`, `enrol/consequences`, `auth/sign-in`, `auth/forgot-password`, `auth/reset-password`), plus `auth/sign-out`, `sessions/revoke-all`, `GET session` and `GET accounts`. **E1** — `PortalCredential`, `PortalSession` and `PortalOneTimeCode` are in `portal/models.py` behind `0007_cr068_e_credential_session_code.py` and `0008_rls_portal_credentials.py`. **E5** — `CWP-015`, `CWP-016` (three drawings on one address), `CWP-019` and `CWP-022` are routed to real components and `shell/PortalShell.tsx` exists. **E7** — `cr068-e-getting-in.mjs` EXISTS. All eight stories are exercised by tests.

### Wave F — *Home, my accounts, my details* · `J37` · `J45`

**Goal a person can see:** the answer to *do I owe anything and by when* above everything
else; a landlord's four balances on one screen totalled and never merged; a customer fixes
her own mobile number and is told plainly why she cannot change her name here; paperless
is a consent with the date it was agreed and one control to withdraw it.
**Stories:** `US-CWP-025` · `US-CWP-026` ✅ **built 2026-09-04** · `US-CWP-027` · `US-CWP-028` · `US-CWP-031`
**Demo script:**
1. Sign in as Maria. **Home** (`CWP-022`): four tiles — `$142.18 · Due 14 Sep · in 12 days`, last bill, last payment, usage `4,820 gal` **with its unit**; the *needs your attention* panel offers *Pay $142.18* (**held** with its reason) and *Send a reading* only while the window 2–6 Sep is open; the tip slot is **absent** — the only home tip is off and Dec–Feb.
2. Sign in as the landlord. **All my accounts** (`CWP-023`): four rows, *Total owing **`$872.82`***, the common-areas row *Billed to you as owner*, the others *Tenant billed*; filter *Owing* drops `· B` at `$0.00`. The response names four account ids and **no fifth**.
3. Request a tenant's account id directly with the landlord's session → refused. Call the common-area reconciliation → it still refuses, ⚠ **but on FINANCE and not on `OQ-1397`, which closed on 2026-09-04**: the arithmetic is `finance_calc: proposed` and a lane implements signed law rather than inventing it. The message names *not finance-signed* and carries no `OQ-` id — a stub citing a closed question is stale the moment it is written.
4. **Add another account** (`CWP-020`): `ACC-10519-C` + `78702`; the code goes to **that account's** contact (the outbound row's destination asserted), the switcher lists five, bills stay separate.
5. **My details** (`CWP-024`): change the mobile, save, reload — and the audit row names **Maria Alvarez**. Post a new legal name to the endpoint → refused with the request route; `customer.last_name` unchanged. *Two letters came back from this address* sits **above** the address field; correcting the address clears it.
6. **How we contact you** (`CWP-025`): the grid — post reads **ALWAYS** on bills, receipts, notices and plan letters (no control); email off for *Payment received* is accepted; the *In the portal* column is present and **held** until wave K; the paperless consent shows its agreed date; **withdraw** → the row gains `withdrawn_on` and is **not deleted**.
7. **Your account** (`CWP-065`): *We are holding `$150.00`, taken on 4 March 2021*, interest `$3.20`, it comes back at closing with interest and is **not money off a bill**; services with what each is billed on; *Residential Standard since 1 January 2026, before that Residential Basic*; *exempt from state utility tax until 31 March 2027* and a reminder a month before. The body contains **no** `credit_tier`, `match_tier`, `match_basis`.
8. A householder's `CWP-023` shows one row and **no total line**; an account with no deposit shows **no** deposit panel.
**Exit test:** `BR-CWP-015` — `$872.82` as four rows and a total, no merged invoice · `BR-CWP-013`/`016` — the master confers nothing; `OQ-1397` raises with its id · `BR-CWP-026` — legal name refused, request route named · `BR-CWP-087`/`R4`/`R6` — post ALWAYS, consent withdrawn not deleted, existing paperless customers not asked · `BR-CWP-052` — the three held-back fields absent from the body · `BR-CWP-049`/`053` — deposit shown while held; exemption with its lapse date.
**Depends on:** E. **Blocked by:** nothing — `OQ-1397` was ruled **no** on 2026-09-04 (`BR-CWP-016` CONFIRMED), which is how `CWP-023` was already drawn. **Runs in parallel with:** G, H.
⚠ **`US-CWP-027` AND `US-CWP-028` CARRY A WRITE QUESTION THE OTHER THREE DO NOT, AND IT IS NOT `OQ-1397`'s.** `BR-CWP-001` names FOUR kinds of row the portal may create — a payment, a service request, a meter reading, a preference — and *adding another account to this login* creates a `customer_accounts` link, which is a row in the utility's book rather than one the portal owns (`BR-CWP-102`'s own test). Editing an email is the same shape one step smaller. **The three READ stories (`025`, `026`, `031`) are unaffected and are what wave F builds first**; the two write stories need that boundary settled before a lane reaches for a fifth write point, which `write_points.py` says in its own words is *a ruling and not an edit*.
**Walkthrough:** `cr068-f-home-accounts-details.mjs` · **Journeys written:** `J37-landlord-across-four-accounts.md`, `J45-paperless-consent-taken-then-withdrawn.md`.
**Ships as:** a version allocated AT SHIP TIME with `10-scripts/allocate.py version --bump change` — this read `nominal 2.134.0`, and a number written down weeks early is `DEF-GOV-3759` with a longer fuse. **Size:** large — about 9 lane-days; `US-CWP-026` landed 2026-09-04 in `2.144.0`.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **F1** | 2a | `POST accounts/add` (code to the **added** account's contact); `GET details`, `PATCH details` (email, mobile, postal address **only**; legal name and holder refused → request route — `BR-CWP-026`), `GET/PUT details/preferences` (refuses to switch off print on the four floor classes; portal column stored but **held**), `POST details/paperless/withdraw` (sets `withdrawn_on`, never deletes); `GET accounts/{id}/account-facts` reading the deposit (`Account` deposit fields — `customers/models.py:133` lists `deposit_interest_accrued`), services and their billing basis, plan history, `TaxExemptionCertificate` (`rating/models.py:1209`) — and **omitting** `credit_tier`, `match_tier`, `match_basis` (`BR-CWP-052`); returned mail from `DeliveryReturnEvent` (`payments/collections_models.py:321`) surfaced above the address; audit rows through `audit_log` with the portal actor (the `portal_actor_id`/`label` columns — `03-field-map.md` §3 row 11, `audit/models.py:51` has only `actor_user_id`). The common-area reconciliation raises `NotImplementedError("OQ-1397")` | `US-CWP-026`, `027`, `028`, `031` · `BR-CWP-009`, `026`, `033`, `049`, `052`, `053`, `086`, `087` | E1–E3 | 2.13 · 2.9 (deposit, exemption) · 2.12 (history) | L |
| **F2** | 2b | `CWP-022` Home (T3 with `KpiRow` first; lead `KpiTile`; attention panel **absent** when empty; three recent bills; twelve-month `ChartPanel` — load the `dataviz` skill; `TipBar` slot absent when no tip), `CWP-023` (T5: `DataTable` + `FilterBar` + `ListPager`, row actions as icons, *Pay* held; no total line for one row), `CWP-020` (T3 without tabs), `CWP-024` (T4), `CWP-025` (`PreferenceGrid` with the neutral **ALWAYS** chip, then T4), `CWP-065` (T3, four panels, the deposit panel absent when none) | five stories · B14 r11, r15, r17, r31 | E5, F1 | 2.14 (`020`, `022`–`025`, `065`) | L |
| **F3** | 2c | `test_us_cwp_025_tc*`…`_028_tc*`, `_031_tc*`; 026 TC-3 (four ids, no fifth) and TC-8 (the raise); 028 TC-10 (one save, four accounts updated); 031 TC-7 (the three absent fields asserted on the body); fixture: `ACC-10519-C`, the deposit taken 4 Mar 2021 with `$3.20` interest, the exemption to 31 Mar 2027, two returned letters, a paperless consent, the home tip off and Dec–Feb, the reading window 2–6 Sep | five stories' §3/§4 | F1, F2 | 2.15 (part) | M |
| **F4** | 2d | `cr068-f-home-accounts-details.mjs` — the eight steps; asserts `$872.82`, the absent tip container (`document.querySelector` null), the ALWAYS chip and no control beside it, the audit actor sentence, the `OQ-1397` refusal sentence; screenshots | law 6 | F2, F3 | 2.16 (part) | M |
| **F5** | doc | `J37`, `J45` files (+ specs when the index says so); CHANGELOG + version; TSV; the `OQ-1397` boundary stated in the close record; decision-log row on where the audit actor label lives | law 9, W | F4 | 2.16 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. All five stories are built and tested: `CWP-020`, `CWP-022`, `CWP-023`, `CWP-024`, `CWP-025` and `CWP-065` are each routed to a real component, and `portal/home`, `my-accounts`, `my-details`(+`/save`), `my-details/preferences`(+`/save`), `my-details/paperless/withdraw`, `accounts/add/find`, `accounts/add/verify` and `accounts/{id}/summary` are all served. `US-CWP-026` already carried ✅ **built 2026-09-04** in the story line above — the ONE place this wave admitted to being built, on one of its five stories, in a line a reader scanning for a stamp would not look at. ⚠ **F4 IS NOT DONE AND WAS RECORDED NOWHERE:** `cr068-f-home-accounts-details.mjs` does not exist. That is r11 step 2d — *prove it* — missing on a shipped wave, and it is filed rather than left here. ⚠ **CLOSED THE SAME DAY — the file exists as of `2.197.3`, 2026-09-06, and the stamp below is what it found.** This clause is left standing rather than edited away because it was TRUE when written and finding it was the reason the walkthrough got built.
⚠ **AS BUILT — 2026-09-06, `2.197.3`.** Where this table and the code disagreed,
the code won and the register says so.

**F1** — the endpoint is `GET accounts/{id}/**summary**`, not `account-facts` as
this table names it, and `AccountSummary` is the type. **It omits the billing
BASIS**: `services` is `{code, name, since}`, so the *"services and their billing
basis"* this row promises is served nowhere and `CWP-065` cannot draw the
drawing's third column. Filed `DEF-CWP-4136` and **left open with its size** —
the basis is rating knowledge and composing it in the portal would break
`CR-068` §2d.

**F4** — `cr068-f-home-accounts-details.mjs` **did not exist**; thirteen of this
plan's walkthroughs are named and were never written and this was one. It exists
now and it drives all six screens on a real PostgreSQL. ⚠ **IT DOES NOT ASSERT
`$872.82` AND MUST NOT.** The demo script above tells Maria Alvarez's story;
`seed_portal_demo` plants a GENERATED estate where the landlord holds **three**
accounts and every figure moves on a reseed, so a constant would fail on a
correct product. **The arithmetic is asserted as a RELATIONSHIP** — the total
equals the sum of the rows, to the cent — which is what `BR-CWP-015` actually
claims and holds on any fixture. It printed rows `$201.21 + $625.94 + $0.00`
against total `$827.15`.

**THE DEMO SCRIPT'S STEPS 3, 4 AND 6 WERE NOT EXERCISED, AND SAYING SO IS THE
POINT.** Step 3's common-area refusal and step 4's add-an-account code both need
a second account outside the login's set and a readable outbound queue; step 6's
*withdraw* needs a paperless consent, and the fixture's account **has never been
asked**, which is `BR-CWP-087` R6 working correctly and also means the consent
state and its withdraw control were never seen. Four panels on `CWP-065` —
deposit, tax, plan history, transferred-from — were likewise only ever seen
ABSENT. The walkthrough asserts those absences as a **correspondence with the
wire** (`deposit === null` ⇒ zero panels) rather than as constants, so it still
fails if a real deposit stops being drawn; but nobody should read this stamp as
saying those paths are proved.

**WHAT THE WALKTHROUGH FOUND THAT 649 PASSING PORTAL TESTS DID NOT** — eleven
defects, `DEF-CWP-4130`–`4140`, eight closed. The five worth carrying forward:

* **Five screens printed bare ISO dates to customers** (`DEF-CWP-4131`) while the
  kit already held **two** date helpers that do not, used by neither. ⚠ **Five of
  the six unit tests that touch these figures ASSERTED THE DEFECT** —
  `toContain("2026-07-27")`, `toContain("4820")` — so they passed on the broken
  screen and went red on the fix. Each is replaced rather than relaxed: the new
  assertion states the human form AND that the machine form is absent.
* **`CWP-023` had no row actions at all** (`DEF-CWP-4133`), and the wireframe's
  own caption insists on them by name.
* **A landlord read the same sentence three times** (`DEF-CWP-4132`) — the home
  payload concatenates each account's `problems[]` and `NamedGaps` drew one line
  each. Every unit test passes ONE account, so the duplication could not appear.
* **`CWP-065` had no heading of any kind** (`DEF-CWP-4135`). ⚠ And
  `pageHeadCensus.test.ts` **also listed `CWP-022` as a gap and it is not one** —
  `08-screen-layouts.md` opens home `PortalShell → KpiRow` with no `PageHead` and
  the wireframe draws none, so a lane following that list would have ADDED one
  and broken the drawing. Home moves to a `CORRECTLY_HEADLESS` list with the
  reason written down.
* **`Home.tsx` and the fixture both cited a rendered-output check that has never
  existed** (`DEF-CWP-4139`) — on the very screen the PO had rejected for its
  shape. Hard-won law 1: a comment claiming a guarantee is not the guarantee.

**THE FIXTURE ITSELF WAS BROKEN AND HAD ALWAYS BEEN** (`DEF-CWP-4130`):
`def-cwp-3965-fixture.py` scoped by RLS alone, and the setup its own header
prescribes connects as a superuser, so `FORCE RLS` is skipped and it reached
another tenant's account and crashed by name. `tenant_context()` sets the GUC; it
does not filter the queryset.

**LEFT OPEN, EACH WITH ITS REASON ON THE ROW:** `DEF-CWP-4136` (the *Billed on*
column, a backend story) and `DEF-CWP-4362` (`CWP-024` offers neither *Change
password* nor *Sign out everywhere*, and `sessions/revoke-all` shipped in wave E
with nothing pointing at it — both are new controls on a security path and each
needs a destination ruling before it is drawn or held).
⚠ **THE SECOND ID READ `DEF-CWP-4137` UNTIL 2026-09-07, AND THAT ROW IS A
DIFFERENT DEFECT THAT IS FIXED** — the `CWP-063` plan-ends copy, closed in
`873ee0a5`. A lane following the citation found a closed row and would have
concluded the two controls were built. The gap now has a row of its own
(`DEF-CWP-4362`), which is what an id is for. Its ordinary sibling — a customer
could not sign out AT ALL — was `DEF-CWP-4359`, fixed the same day, and
`BR-CWP-104` is the destination ruling that one needed.

**Wireframe comparison:** `13-wireframe-delta.md` gains a second pass covering
`CWP-020`, `CWP-023`, `CWP-024`, `CWP-025`, `CWP-065` and a re-read of
`CWP-022` — nine screens of seventy-seven becomes fifteen.


### Wave G — *Bills, documents and the money list* · `J36`

**Goal a person can see:** every bill with **owing** as a separate column from **amount**;
one bill line by line that adds up; the PDF exactly as it was posted; everything the
utility sent and by which route; every payment with a bounce shown as two rows — and every
Pay control visible, disabled, carrying its reason.
**Stories:** `US-CWP-032` · `US-CWP-033` · `US-CWP-034` · `US-CWP-036` · `US-CWP-048`
**Demo script** (`BL-2608-0141` `$142.18`; paid `BL-2607-0139` `$138.44`; corrected pair `BL-2606-0137 $154.90 → BL-2606-0147 $129.02`; cheque `#10174` bounced):
1. **Bills** (`CWP-027`): four rows. `BL-2608-0141` — amount `$142.18`, owing `$142.18`, **DUE IN 12 DAYS**; the part-paid row — amount `$142.18`, owing `$102.18`, **neither PAID nor DUE**; `BL-2606-0137` greyed, **CORRECTED**, *Replaced by BL-2606-0147*, and the replacement its own row. A draft bill in a live run is **absent**. Filter *Unpaid* keeps the part-paid row.
2. **One bill** (`CWP-028`): Water `$18.50 + $17.80 + $34.12`, Sewer `$35.67`, Trash `$22.00`, tax `$5.42`, fee `$8.67`; *first 2,000 gal at $8.90 / 1,000 gal*; every quantity cell carries its unit; charges before tax `$128.09` + tax `$14.09` = **`$142.18` exactly from the displayed figures**. The readings panel: `31 Jul 148,220 · 31 Aug 153,040 · Both taken by a reader. Neither was estimated.`
3. **The bill as it was printed** (`CWP-029`): download — **byte-identical** to the bill run's file (`invoices/{id}/document.pdf`, `billing/documents_api.py:454`); redesign the tenant's template, download again — unchanged.
4. **Documents and letters** (`CWP-031`): 41 documents, page 1 of 9, route *Post · Email* on a bill sent both ways, *Email* on a receipt; *download a year* is one archive of issued files. A skipped notice is **not** here (it has no document — that is `CWP-068`, Phase 3).
5. **Payments and receipts** (`CWP-041`): five payments; the bounce as **two rows** — `2 Jul · Cheque #10174 · Returned by the bank · −$129.02 · BOUNCED` directly above `2 Jul · Cheque #10174 · BL-2606-0147 · $129.02 · REVERSED`; a goodwill adjustment `−$25.88` with its reason; a write-off `$84.20` *written off* with **no reason code** in the body; the receipt is the existing document class.
6. Every **Pay** control — Home, Bills, the bill, Payments — renders in its place, **disabled, with its reason** (*Online payment arrives later this year* — five or six words, all eleven catalogues). `CWP-038` Pay now, `CWP-039` methods and `CWP-040` autopay render their layouts with every commit **held**; autopay's *next few* table shows the **real** `AutopayCaptureIntent` rows (`14 Sep 2026 · $142.18 · SCHEDULED`; `14 Oct · — · NOT BILLED YET`).
7. Force a click on a held control → no payment row, no audit row, no gateway call.
8. A new customer with no bills → an empty state that says what fills it; never a blank table.
**Exit test:** `BR-CWP-043` — owing and amount are two columns and part-paid is a third state · `BR-CWP-042` — the corrected pair both present, the original naming its replacement · `BR-CWP-044`/hard rule 3 — no bare quantity in any cell · `BR-CWP-045` — byte identity of the PDF after a template redesign · `BR-CWP-061` — the bounce is two rows · `BR-CWP-051` — no reason code in the write-off body · `BR-CWP-056`/`R3` — every Pay control disabled with its reason, and a forced click writes nothing · B14 rule 17 — the empty state.
**Depends on:** E. **Blocked by:** nothing (`OQ-1340` constrains wording on `CWP-041`: the list is **not** described as a permanent record of a corrected payment reference). **Runs in parallel with:** F, H.
**Walkthrough:** `cr068-g-bills-and-money-list.mjs` · **Journeys written:** `J36-the-eleven-month-cold-return.md` (+ spec).
**Ships as:** nominal `2.135.0`. **Size:** large — about 9 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **G1** | 2a | `GET accounts/{id}/bills`, `GET bills/{no}` (lines grouped by service, rounded lines that sum, the readings behind the bill), `GET bills/{no}/document` (**serves** the pinned render through `billing/documents_api.py` — never re-renders, `BR-CWP-045`), `GET accounts/{id}/documents` (outbound messages that kept a document, with channel), `GET accounts/{id}/payments`, `GET payments/{ref}/receipt` (`payments/receipts.py`), `GET accounts/{id}/adjustments` (`Adjustment`, `billing/models.py:1241`), write-offs (`WriteOff`, `collections_models.py:447`) **without `reason`**; `GET accounts/{id}/autopay` reading `AutopayCaptureIntent` (`payments/models.py:992`) read-only; the held reason for every Pay control served as a refusal code with its catalogue sentence. **No update or delete route for a payment exists on the portal edge** (048 TC-3) | `US-CWP-032`, `033`, `034`, `036`, `048` (+ the held half of `045`, `047`) · `BR-CWP-041`–`045`, `050`, `051`, `056`, `061` | E1–E3 | 2.6 · 2.8 (adjustments, write-off) | L |
| **G2** | 2b | `CWP-027` (T5, greyed corrected row, status chips DUE / PAID / CORRECTED / part-paid), `CWP-028` (T6 + `TwoCol`, `MiniTable` per service, `KVList` + `TotalRow`, `AttachedAnswerCard` slot — filled in wave H), `CWP-029` (T6, `DocumentPreview`), `CWP-031` (T5, filters, *Download a year*), `CWP-041` (T5, danger row for the bounce, receipt row action, CSV); **the held Pay surfaces**: `CWP-038` (T2, *Pay $142.18 ✓* held), `CWP-039` (T5, held), `CWP-040` (T4, *Turn autopay on* held per `08-screen-layouts.md` §disagreements; the *next few* `MiniTable` live). Every held control: staff disabled presentation **plus** a visible ≤6-word reason and `title` | five stories + the 2b-held half of `045`, `046`, `047` · `BR-CWP-056` · B14 r15, r17, r20, r33 | E5, G1 | 2.14 (`027`–`029`, `031`, `038`–`041`) | L |
| **G3** | 2c | `test_us_cwp_032_tc*`, `_033_`, `_034_`, `_036_`, `_048_` — 033 TC-2 asserts `$128.09 + $14.09 = $142.18` from **displayed** strings; 033 TC-6 the eleven-service bill with fire counting (`$60.00 + 2 × $12.00`); 034 TC-1/2 byte identity; 048 TC-2 row order; 048 TC-5 no reason code; the forced-click case (045 TC-2) writing nothing; fixture: the four bills, the corrected pair, the bounce, the adjustment, the write-off, 41 documents, the intents | five stories' §3/§4 | G1, G2 | 2.15 (part) | M |
| **G4** | 2d | `cr068-g-bills-and-money-list.mjs` — the eight steps; asserts the two-column distinction, *Replaced by BL-2606-0147*, every quantity cell matching `/\d[\d,]* (gal|cart|kWh|therm)/`, the disabled attribute **and** the reason text on every Pay control, the two bounce rows in order, the PDF bytes' hash; screenshots | law 6 · hard rule 3 | G2, G3 | 2.16 (part) | M |
| **G5** | doc | `J36` file + spec; CHANGELOG + version; TSV; `US-CWP-048`'s `OQ-1340` wording constraint recorded in the screen's docstring | law 9, W | G4 | 2.16 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. All five stories are built and tested: `CWP-027` (`bills/Bills.tsx`), `CWP-028` (`bills/BillDetail.tsx`, 535 lines), `CWP-029` (`PrintedBillPage`), `CWP-031` (`documents/Documents.tsx`) and `CWP-041` (`payments/Payments.tsx`) are each routed to a real component, and `portal/bills`, `bills/{number}`, `bills/{number}/document`, `bills/{number}/document.pdf`, `accounts/{id}/documents` and `portal/payments` are all served. ⚠ **G4 IS NOT DONE AND WAS RECORDED NOWHERE:** `cr068-g-bills-and-money-list.mjs` does not exist.

⚠ **G4 IS DONE NOW — 2026-09-06, `2.197.6`, and the walkthrough it names is on disk and GREEN.**
`10-scripts/render-checks/cr068-g-bills-and-money-list.mjs` runs the demo script's eight steps in a
real browser and finishes **0 failures with 2 named open gaps**. Where this table and the code
disagreed, the code won and the register says so.

**What it proves, with the figures it printed** (landlord `maria@example.test`, three accounts, a
freshly seeded clone): `BR-CWP-043`'s two columns are **provably different rather than two columns of
zeroes** — one bill charged **`$1,564.84`** and owes **`$625.94`**; that same bill **adds up from the
strings on the screen**, `$1,445.58` + `$119.26` = `$1,564.84`, which is `US-CWP-033` TC-2's own
acceptance done against rendered cells rather than a payload; `BR-CWP-061`'s bounce is **two rows in
the drawn order** — `BOUNCED · REVERSED · CLEARED`, the reversal at **`−$1,111.23`** directly above the
row it undoes, its cells in the danger tier and the row beneath it not; `BR-CWP-045`'s document is
**byte-identical across two fetches** (7,469 bytes, one sha256); every quantity cell carries its unit
(hard rule 3); and a customer with no payments gets a sentence rather than an empty table.

⚠ **THE FIXTURE WAS THE MISSING HALF, NOT THE SCRIPT — G3 IS STILL ONLY PARTLY DONE.** G3 names *"the
four bills, the corrected pair, the bounce, the adjustment, the write-off, 41 documents, the
intents"* and **none of it had been written**; `seed_portal_demo` plants an estate where **every
payment is cleared**, so every assertion about a bounce would have passed vacuously over a list that
could not contain one. `cr068-g-fixture.py` now bounces a payment through the real
`payments.reversal.reverse_payment` service. It does **not** manufacture the corrected pair, and that
is a refusal rather than an omission: corrections run through `single_correction.py`, which is
human-owned money math. **`BR-CWP-042` is therefore recorded as a KNOWN GAP (`DEF-CWP-4176`), not as a
pass** — through `lib/knownGaps.mjs`, so the day a fixture plants one the run goes RED and names the
row to delete.

⚠ **AND THE FIXTURE'S FIRST DRAFT DESTROYED THE THING THIS WAVE EXISTS TO SHOW, WHICH IS WORTH MORE
THAN THE FIXTURE.** It preferred to bounce a *cheque*, on the reasoning that a returned cheque is what
a person pictures. It took the card payment instead — the cheque rows on this estate carry no
`method` at all, so the tender name came back empty and the filter matched nothing — and that card
payment was **the part payment that made the bill part-paid**. Reversing it put the bill back to
owing its full amount, and `CWP-027` lost the only row where `owing` and `amount` differ. The
walkthrough then reported, correctly, *"every row owes all or nothing, so this fixture cannot prove
`BR-CWP-043`"*. **The rule now is that the bounce must SETTLE ITS BILL IN FULL**: a bounce and a part
payment are two different demonstrations and a fixture must not spend one to buy the other.

⚠ **AND THE WALK HAS TO CROSS THE ACCOUNTS, WHICH IS `DEF-WRK-4121`'s SHAPE ONE LEVEL UP.** `/bills`
and `/payments` are scoped to the account the SWITCHER names, and the landlord's three accounts do not
hold the same shapes — the part-paid bill is on one, the bounce on another, and **the account the
switcher opens on has neither**. A run that looked only at the default account reported two skips and
a failure over a database holding both. Not an empty list: the one slice of a real list where the
interesting state is absent.

**Five defects filed from the browser, three fixed here.** `DEF-CWP-4149` — the back link on three
bill screens drew **two arrows**, because `PageHeader` renders one and the catalogue value already
carried one, in all eleven languages. `DEF-CWP-4150` — **raw ISO dates on two customer screens**
(*"BL-2608-000096 · 2026-07-01 to 2026-07-31"*) in a file whose readings panel had always formatted
correctly; the regression test asserts the subtitle's SHAPE and was proved red first, and it only has
teeth because the harness publishes a tenant format. `DEF-CWP-4151` — `PrintedBill.tsx`'s docstring
**forbade the preview its own file renders**, twelve lines lower: hard-won law 1 in its most dangerous
direction, a stated rule against something present, which the next lane obeys by deleting it. Left
open with its reason stated: `DEF-CWP-4152` — `CWP-038`'s Pay control is disabled and says nothing,
on the one screen in this wave that takes money.

⚠ **AND ONE OF THE FIVE WAS WRONG — `DEF-CWP-4153` IS INVALID, AND IT IS THE MOST USEFUL THING THIS
LANE DID BADLY.** It filed *"rates draw **four** decimals — `$0.1100 / kWh` — against hard rule 2's
display-2"* and closed with *"what is NOT in doubt: the current output disagrees with both the signed
rule and the drawing."* **It was in doubt, and the product is right.** `OQ-620`, closed **2026-08-27**,
PO verbatim: *"What does a tariff rate show? Four (`$0.1420`). A rate is not money and not a quantity
- 4 decimal places"* — worked there as `8.290000` per kgal → **`$8.2900`, zeros KEPT**. Hard rule 2 was
explicitly NOT changed by that ruling: money still displays 2 and a quantity at most 2 trimmed. **A
RATE IS A THIRD KIND** because it is multiplied by a quantity before it becomes money, so its
precision compounds; all three live in `06-backend/core/money_fields.py` and the rate is built as
`formatRate` / `wording.rate_text`. The wireframe's `$8.90 / 1,000 gal` is the STALE side — `OQ-620`
cites r10's own residential bill drawing `$0.1420`, and **a PO ruling beats a drawing**.
⚠ **AMENDED 2026-10-02 — UP TO FOUR, ZEROS PAST THE SECOND DROPPED.** PO, verbatim: *"Show unit prices with up to 4 decimals and keep every total at 2."* (decision log *"THREE UI RULINGS FROM THE RATE-SCHEDULE SWEEP"* (1)). A unit price now reads `$0.0425`, `$0.10`, `$12.50` — `8.290000` reads **`$8.29`**, no longer `$8.2900`. The four-place ceiling and the reason for it stand; every amount stays at 2.

**What kept it harmless is worth separating from what went wrong.** The lane REFUSED to act on its own
finding, because rounding the column would print `$0.00 / kWh` beside a real charge for any sub-cent
rate — which is the exact hazard `OQ-620` exists to prevent, and exactly what a later lane acting on
the delta row would have done to a customer's bill. **The instinct was right and only the conclusion
was wrong.** The row is marked `invalid` in the register and `13-wireframe-delta.md`'s 28.4 is
corrected in place rather than deleted, so the wrong reading stays visible — the treatment
`DEF-CWP-3993` established for that file.

**The reusable part is one command.** Hard-won law 13 says grep `02-decision-log.md` and
`01-open-questions.md` for the subject before putting anything to the PO. **It applies just as much
before FILING as before ASKING** — this question had been asked and answered ten days earlier, and a
defect row is a claim about signed law just as a question is.

**The walkthrough now asserts the ruled behaviour POSITIVELY** — rates draw four decimals with their
zeros kept — so a regression to two is what goes red. Proved through the harness that runs it:
`formatRate` was temporarily changed to two places, the bundle rebuilt, and the run went RED on all
four per-unit rates (`$0.11 / kWh` where the ruling says `$0.1100`); restored, rebuilt, green. The
three percent rates on the same screen are correctly excluded — a percent is a different kind at two
decimals, hard rule 2 unchanged.

**The five screens are compared against their drawings in `13-wireframe-delta.md`**, which covered
nine screens and none of wave G's until now.

⚠ **ONE THING LOOKED BROKEN AND IS NOT, recorded so nobody chases it:** in headless chromium
`CWP-029`'s preview paints as a solid black rectangle. The served file is a valid PDF and the
`bg-[white]` utility it relies on IS emitted into the built stylesheet, so the evidence points at the
headless shell having no PDF viewer. **Not filed** — one look in a headed browser settles it.

### Wave H — *Usage, readings and equipment* · the signed-in help and tip slots

**Goal a person can see:** a year of usage with the axis in gallons and the services that
are not measured saying so; every reading with **how it was taken** and why an estimate was
corrected; the meter that is hers; and the answer to *why is my bill higher* sitting under
the bill itself.
**Stories:** `US-CWP-040` · `US-CWP-041` · `US-CWP-043` (+ the signed-in surfaces of `US-CWP-072` and `073`, placed in wave D)
**Demo script:**
1. **Usage** (`CWP-033`): `4,820 gal` this period, *18% above last August*, daily average `155 gal`, next reading due *2–6 Sep*; twelve bars with the **axis labelled in gallons**, `3,050 gal` lowest and `4,820 gal` highest marked. Switch to 24 months. The **watering tip** shows in September (Jun–Sep) in the `TipBar`; pin the clock to 1 October — gone, with no edit.
2. The sewer panel: *Billed on: Water used · Not separately metered* — **no chart and no zero series**; trash: *Billed on: Your 96 gal cart · Not measured*. A trash-only account shows no chart at all and still makes sense.
3. **Every reading** (`CWP-034`): four rows with method in words; the estimated row reads **ESTIMATED then corrected** and opens to *estimated 144,600, corrected to 144,130 when the meter was read on 3 July — you were not charged twice*; a rollover computes used-since through the maximum; every used-since carries `gal`.
4. **Meters and equipment** (`CWP-037`): water meter `88-40219`, refuse cart `C-11840` with an **empty** last-read cell (not zero), backflow `BF-2210` **TEST DUE NOV**; a sub-meter of another unit is absent; every identifier is a serial, never a row id.
5. **Help, signed in** (`CWP-059`): six answers plus *we already know which account you are asking about*; **one answer** (`CWP-060`) with *did this help?* and three routes to a person; open `BL-2608-0141` — the same answer sits **under the charges** (`CWP-061`), written once.
6. CSV export of usage: every row carries its unit as a column.
**Exit test:** `BR-CWP-073` — unmeasured services say so; no empty chart · `BR-CWP-071`/`072` — the method in words and the correction with its size · hard rule 3 — unit on every quantity, axis and CSV column · `BR-CWP-095` — one tip, gone on 1 October · `BR-CWP-094` — the attached answer appears under the bill and is absent when none is attached · B14 rule 31 — serials, never ids.
**Depends on:** E, D (the answer store), G (`CWP-028` for the attached answer). **Blocked by:** nothing. **Runs in parallel with:** F, G (H's `CWP-061` task waits for G2's `CWP-028`).
**Walkthrough:** `cr068-h-usage-readings.mjs` · **Journeys written:** none new (`J36` closes in G; `J39` is wave J).

⚠ **H4 IS NOT DONE AS OF 2026-09-04, AND THE BLOCKER IS THE SEED RATHER THAN THE SCRIPT.**
`US-CWP-040`, `041` and `043` shipped with their backend, their screens and their tests
(2.150.0); the browser walkthrough did not, and saying so is the point of this note
(hard-won law 6 — *"no gate looks at rendered output"*, and an absence is exactly what these
three screens are about). **What it needs first: `seed_portal_demo` writes no meter reads,
no `monthly_usage` months and none of the three assets** — Maria's twelve months
(`3,050`–`4,820 gal`), the estimated-then-corrected June row, the water meter `88-40219`,
the refuse cart `C-11840` and the backflow device `BF-2210` exist **only in
`tests/test_us_cwp_usage_helpers.py`**, so a browser pointed at the demo tenant today would
open `CWP-033` and honestly draw nothing. **Extending the seed is the first task of whoever
picks H4 up**, and it is worth more than the script: it is also what a person demonstrating
this wave needs.
⚠ **CLOSED 2026-09-06 at `2.197.7`. The note above was right about everything, including
which half was the work:** the seed took most of a lane-day and the script took the rest,
and the seed is what turned three honestly-empty screens into a demo. The stamp below says
what the browser found. This clause is left standing rather than edited away because it was
TRUE when written and it is the reason the walkthrough exists.
**Ships as:** nominal `2.136.0`. **Size:** medium — about 7 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **H1** | 2a | `GET accounts/{id}/usage` (`metering/monthly_usage*.py` through a seam; per-service basis — metered or not — from the service's `is_metered`), `GET accounts/{id}/readings`, `GET readings/{id}` (method from `MeterRead.read_method`/`source`/`status` at `metering/models.py:1773-1792`, estimation and true-up in words; the correction's size), `GET accounts/{id}/equipment` (`Asset.serial_no`, `assets/models.py:228`; only this unit's assets; cart with no last read); signed-in `GET help`, `GET help/{slug}`, `POST help/{slug}/feedback`, `GET tips?screen=` scoped to the session; the bill's attached answer by `also_show_on_screen` | `US-CWP-040`, `041`, `043`, `072`, `073` · `BR-CWP-071`–`073`, `094`, `095` | E1–E3, D1 | 2.12 (`CP-55`) · 2.14 (part) | M |
| **H2** | 2b | `CWP-033` (T3 variant: `KpiRow` ×3, `ChartPanel` with the unit on the axis — load the `dataviz` skill — per-service panels that **say** *not measured*, CSV, `TipBar`), `CWP-034` (T6 + T5, *Query* row action routing to Phase 3's dispute), `CWP-037` (T6 + `DataTable`), `CWP-062` (= `CWP-033` with the `TipBar` filled), `CWP-059` (T3), `CWP-060` (T6 + `TwoCol`, in-text controls that go where they say), `CWP-061` (`CWP-028` + the `AttachedAnswerCard`) | `US-CWP-040`, `041`, `043`, `072`, `073` · hard rule 3 · B14 r15, r31 | E5, G2, H1 | 2.14 (`033`, `034`, `037`, `059`–`062`) | L |
| **H3** | 2c | `test_us_cwp_040_tc*`, `_041_`, `_043_` and the signed-in cases of `_072_`/`_073_` (072 TC-2/6, 073 TC-2/3/4); 040 TC-9 unit column; 041 TC-8 rollover; fixture: twelve months of reads (`3,050`–`4,820 gal`), the estimated-then-corrected row (`144,600 → 144,130`, 3 July), the three assets, the trash-only account | five stories' §3/§4 | H1, H2 | 2.15 (part) | M |
| **H4** | 2d | `cr068-h-usage-readings.mjs` — the six steps with the clock pinned to 2 Sep and to 1 Oct; asserts the axis label text, the absence of any `<svg>`/canvas in the sewer and trash panels, the correction sentence, the empty last-read cell, the attached answer under the charges; screenshots | law 6 | H2, H3 | 2.16 (part) | M |
| **H5** | doc | CHANGELOG + version; TSV; `US-CWP-072`/`073` marked complete across D and H in the close record; the `dataviz` palette choice recorded once | law 9, W | H4 | 2.16 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. **H1–H3 ARE DONE:** `US-CWP-040`, `041` and `043` shipped with their backend, screens and tests — `CWP-033` (`usage/Usage.tsx`, 599 lines), `CWP-034` (`usage/Readings.tsx`) and `CWP-037` (`usage/Equipment.tsx`), served by `accounts/{id}/usage`, `…/readings` and `…/equipment`. **H4 was already recorded above as not done**, with the seed rather than the script as the blocker, and that note stands. ⚠ **BUT THE OTHER HALF OF THIS WAVE'S OWN TITLE IS NOT BUILT AND NOTHING SAID SO:** *the signed-in help and tip slots* — `CWP-059` (help while signed in), `CWP-061` (the answer attached under a bill) and `CWP-062` (the tip on the usage screen) — have no address in the product and are three of the ten rows in `07-frontend/src/portal/routing/unbuiltScreens.ts` (`DEF-CWP-3988`). So **step 5 of the demo script above cannot be performed today**: a signed-in customer reaching for help gets `CWP-011`, the GUEST screen, which is a working screen and not the drawn one.

⚠ **AS BUILT — H4 AND H5, 2026-09-06, `2.197.7`. The clause above said H4 was not done; it is done, and this is what the browser found.**
`10-scripts/render-checks/cr068-h-usage-readings.mjs` walks the six demo steps and finishes
**0 failures, 0 gaps that have closed, 8 known gaps still open** (exit 0), beside
`cr068-h-fixture.py`, which puts a login on the meter's own account.

**THE SEED WAS THE WORK, EXACTLY AS THE NOTE PREDICTED.** `seed_portal_demo` now plants
Maria's history on `1408 Elm St · A` through each owning module's own door — 24 readings
through metering's stage → validate → commit pipeline, the three assets through
`assets.create_asset`, June corrected through `supersede_read`. **Three things had to be
true that no document said:**
* **The twelve monthly figures are `US-CWP-040` §4's own twelve RE-ORDERED.** The two shipped
  test fixtures describe DIFFERENT histories for one meter — `twelve_months_of_water` puts
  30 June 2026 at dial `144,810`, `four_readings` puts it at `144,600`/`144,130` — and both
  are green because no test builds both on one account. A demo has one meter. The order used
  is a PERMUTATION, so the total `48,120 gal`, the low `3,050` and the high `4,820` are
  untouched by construction, and it is the only arrangement under which the four dials
  `US-CWP-041` asserts (May `140,370`, June `144,130`, July `148,220`, August `153,040`) all
  fall out.
* **June is posted as an ESTIMATE and corrected afterwards, in that order.** `portal_reads`
  surfaces a correction by looking through the SUPERSEDED rows for an estimated one; run the
  other way round the browser showed June as an ordinary walked reading with
  `estimated: false` and `correction: null` — the screen rendering perfectly and this
  story's whole point missing.
* **The fixture reaches 24 months, not 12, and the oldest month it can state is October
  2024.** The plan's *"18% above last August"* is not what the product computes:
  `monthly_usage_reads._metrics` measures the last twelve months against the twelve BEFORE
  them, a total against a total, so twelve months of seed makes that tile answer
  `no_prior_reads`. And `meter_reads` is range-partitioned with `meter_reads_2024_09` as its
  earliest partition, so nothing older can be planted at all (`DEF-CWP-4167`).

**WHAT THE BROWSER PRINTED** — the figures, read off the screen rather than off the wire:
axis `gal per month` · highest `2026-08: 4820 gal used`, MARKED and painted a darker tier ·
lowest `2026-01: 3050 gal used`, MARKED · 12 month tracks, 11 with a reading and September
absent because nobody has read it yet · **24 months → 23** · sewer *Billed on: The water you
use · Not separately metered* with **no `<svg>`, no canvas and no zero series inside the
panel** · trash *Billed on: Your Trash 96-gallon cart · Not measured* · every used-since
figure carrying `gal`, 23 of 23, the 24th being the baseline read that correctly draws `—` ·
the correction opening to **“We estimated 144,600 and corrected it to 144,130 when the meter
was read on 2026-07-03. You were not charged twice.”** · three serials, the cart's last-read
cell **empty and not a zero** while the meter's is filled · `TEST DUE NOV` · CSV header
`service,month,quantity,unit,estimated`, 11 of 11 rows carrying their unit.

**ELEVEN DEFECTS FILED, `DEF-CWP-4165`–`4175`, each before it was touched.** Three fixed
here: `4165` (774 of 775 `monthly_usage` rows were `is_sample=false`, so every month the
sample plant states is unremovable), `4166` (the fixture priced water in `kgal` against a
`gal` meter, so the newest reading committed `unit_mismatch` and the bill engine would refuse
the account), `4167` (a read batch answers `batch_status: posted` while posting nothing, so a
seeder that sums `posted_reads` plants a shorter history in silence — this one cost a month
before it was caught). Eight open, four of them `CWP-033` against its own wireframe.

⚠ **AND THE WIREFRAME COMPARISON IS WHERE FOUR OF THE EIGHT CAME FROM, WHICH IS B14 RULE 36
DOING ITS JOB WITH NO GATE BEHIND IT.** `4168` — the KPI and the chart legend draw `4820 gal`
while the panel below them draws `43,300 gal`: one screen, one kind of number, two formats.
`4169` — the drawing's third KPI tile, *NEXT READING DUE · 2–6 Sep*, is not built. `4170` —
the drawing's `DAILY AVERAGE 155 gal` is built as `MONTHLY AVERAGE 3936.36 gal`, a different
statistic under a different heading. `4175` — the axis label duplicates the panel title, the
service panels lead with sewer where the drawing leads with water, and the trash basis reads
*Your Trash 96-gallon cart* for the drawing's *Your 96 gal cart*. None of these could fail a
test: the screens' 2,561 lines of unit tests all pass over every one of them.

**The eight open gaps are recorded through `lib/knownGaps.mjs`, not skipped and not left
red.** The run finished RED five times on its first outing, every failure correct and every
one filed — and a walkthrough that exits 1 forever teaches its reader that red is its normal
colour. A gap here goes red in BOTH directions, and that was proved through the harness that
runs it: one gap was flipped to present and the run reported `GAP CLOSED`, named the row to
delete and exited 1. **Step 5 is three of the eight** (`CWP-059`, `CWP-061`, `CWP-062`), so
the clause above is now machine-watched rather than only written down.

---

## 4 · PHASE 3 — LAUNCH: customers can ask us for things, and see what we sent them

**Launch sentence:** `CR-068` §12 Phase 3, kept verbatim in §1.
⚠ **`OQ-1399` — is the portal a channel a notice can be delivered on? — is put to the PO
in plain English BEFORE this phase starts** (`CR-068` §12; `02-business-rules.md`
`BR-CWP-088`). The question is already minted and worded in the register; the plain-English
packet is task **K0**, and it is prepared during Phase 2 so it is not on this phase's
critical path. Until ruled, every wave here builds to the boundary: a portal row is a record
that a message **exists**, never proof it arrived (`BR-CWP-084`), and any path that would
treat it as delivery raises `NotImplementedError("OQ-1399")`.
**Stands on:** W2 (requests, read validation) · W4 (notices, move-out settlement) · W3 (the
outbound queue).
**Stories (14):** `US-CWP-011`, `037`, `038`, `039`, `042`, `060`–`068`.
**Order:** **I, J and K run in parallel** after Phase 2's wave E (J also needs H; K also
needs F and G).

### Wave I — *Requests, disputes and a question* · `J40` (request half) · `J33` (closes)

**Goal a person can see:** a customer asks to move out in her own words, is told before the
button that it cannot be undone and that stopping service is a different thing, can withdraw
until a clerk approves, and never sees an internal routing note; a query holds collection on
`$142.18` without touching the bill.
**Stories:** `US-CWP-060` · `US-CWP-061` (⚠ `OQ-1392`) · `US-CWP-062` · `US-CWP-063` · `US-CWP-064` · `US-CWP-065` · `US-CWP-066`
**Demo script** (`SR-26-0056`; standing charge `$18.50`/month; connection fee `$185.00`):
1. **What do you need** (`CWP-046`): six cards in the customer's words, read from the tenant's categories; open requests below with references.
2. **Moving out** (`CWP-048`): last day 17 Sep, where the final bill goes, deposit `$150.00` (matching `CWP-065`); the `ConsequenceBox` — *we read your meter on 17 September · a final bill settles your deposit · the account closes. You cannot undo this*; the panel: *stopping service leaves the account open — standing charges keep running*. **Send this request ✓** is the **danger** tier. Fewer than eight days' notice is refused naming the period.
3. Staff worklist: `SR-26-0056 · Move out · 17 Sep` with channel **Customer portal** — asserted as the first row in the fixture carrying `customer_portal`. Call the self-serve close → `NotImplementedError("OQ-1392")`: the request lands for a person.
4. **Stop or restart** (`CWP-052`): 1 Nov → 1 Apr — *the account stays open*, `5 × $18.50 = about $92.50` against `$185.00` plus a new deposit — **stopping is cheaper**; change to nineteen months — `$351.50` exceeds `$185.00` plus the `$150.00` deposit (`$335.00`) — **closing is cheaper**, and the screen says so (twelve months is `$222.00` and does NOT cross; this step said *twelve* until 2026-09-03 — `DEF-CWP-3608`).
5. **Track your request** (`CWP-051`): *You sent it · 2 Sep, 9:14am through the portal · We picked it up · 2:40pm · Sarah at the office · We need something from you · 3 Sep*; the clerk's internal note *route to Tuesday crew* is **absent from the body**; *Open for 1 day* computed. **Withdraw** works until approval; after approval it is refused with a plain sentence.
6. **Documents we need from you** (`CWP-049`): *Photo ID · to confirm who you are · RECEIVED 2 SEP*, *Proof of address · NEEDED*, *Landlord's consent · you are not the owner · NEEDED*; **no file input in the DOM**; the sentence says documents come to the office.
7. **Dispute a bill or a reading** (`CWP-055`): query `BL-2608-0141` over the 31 August reading; `CWP-027` shows *held while we look*; `CWP-034` shows the marker; `invoice.total` is still `$142.18` and **no row was updated**; no late fee accrues on `$142.18` while a second undisputed bill still accrues.
8. **Ask a question** (`CWP-054`) about `BL-2608-0141`: the request reaches a clerk **already naming that bill**; the *might answer it now* panel shows three published answers and is **absent** when none; office and emergency numbers distinct.
**Exit test:** `BR-CWP-075` — exactly four customer transitions; `approve`/`refuse` unreachable from the portal edge · `BR-CWP-076` — the first `customer_portal` row · `BR-CWP-078` — the internal note absent from the response body · `BR-CWP-079` — withdraw until approved · `BR-CWP-080`/`081` — the distinction copy present; both figures shown and the cheaper option named · `BR-CWP-082`/`OQ-1392` — the raise · `BR-CWP-042`/hard rule 4 — the disputed bill unchanged · B14 rule 6 — the danger tier on the move-out commit.
**Depends on:** E, G (`CWP-027`/`034` markers), D (published answers). **Blocked by:** `OQ-1392` (boundary, step 3); the upload re-sign (B9 — the checklist is real, the box is not). **Runs in parallel with:** J, K.
**Walkthrough:** `cr068-i-requests-and-disputes.mjs` · **Journeys written:** `J40-move-out-final-bill-refund.md` (spine; steps 3–4 activate in J and Phase 5) · `J33` completed.
**Ships as:** nominal `2.137.0`. **Size:** large — about 10 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **I1** | 2a | `GET request-categories` (tenant configuration, never a fixed list), `POST requests`, `POST requests/{ref}/submit`, `POST requests/{ref}/notes`, `GET requests`, `GET requests/{ref}` (transitions + notes flagged `AccountNote.customer_visible` — `customers/models.py:1234`, **switched on**; internal comments filtered), `GET requests/{ref}/fees` — over `service_request_service.create_request/update_request/submit/add_note` (474/533/1886/1766) with `channel="customer_portal"` and `portal_credential_id` (new FK, `03-field-map.md` §3 row 8). **`withdraw` is new** (§0 row 7): allowed until approval, touches no account. Move-out: the request only; self-serve close raises `NotImplementedError("OQ-1392")`. Stop/restart: the comparison **reads** the plan's standing charge and the tariff's connection fee — arithmetic over stored figures, no rate computed. Dispute: the existing marker on the read/bill with collection held on the disputed **amount**; only a System Admin clears it. Question: category + `invoice.number` on the request | `US-CWP-060`–`066` · `BR-CWP-075`–`082`, `042` | E1–E3 | 3.5 · 3.6 · 3.7 · 3.8 | L |
| **I2** | 2b | `CWP-046` (T1 inside `PortalShell`), `CWP-048` (T2; danger-tier commit; distinction `Panel`), `CWP-052` (T4; both figures), `CWP-051` (T6 + `TwoCol`; `ChecklistTimeline`; *Add a note*, *Withdraw*), `CWP-049` (T6; **a sentence, no file input** — `08-screen-layouts.md` §disagreements), `CWP-055` (T2, 2-cell stepper; *the bill itself does not change* panel), `CWP-054` (T3; suggestions panel absent when none) | seven stories · B14 r6, r11, r32 | E5, I1 | 3.9 (screens — §12 has no screen task for Phase 3; **new**) | L |
| **I3** | 2c | `test_us_cwp_060_tc*`…`_066_tc*`; 060 TC-3 (first `customer_portal` row); 061 TC-6 the raise; 062 TC-2/3 both arithmetic branches; 063 TC-2 body free of the internal note; 064 TC-3/4 no input, no upload route; 065 TC-2/3/4 immutability and the per-amount hold; fixture: `SR-26-0056` with its transitions and one internal note, the three-document checklist, the request categories, an account with two open bills | seven stories' §3/§4 | I1, I2 | new | M |
| **I4** | 2d | `cr068-i-requests-and-disputes.mjs` — the eight steps; asserts the danger-tier classes by computed style, the distinction sentence, both comparison figures, the absence of the internal note in the fetched body, no `input[type=file]`, `invoice.total` unchanged via the API, the `OQ-1392` refusal sentence; screenshots | law 6 | I2, I3 | new | M |
| **I5** | doc | `J40` file (spine), `J33` completed; CHANGELOG + version; TSV; the `OQ-1392` boundary in the close record; the `withdraw` transition recorded as an amendment to the customers module's rule table (dated) | law 9, W | I4 | 3.9 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. **FIVE OF THE SEVEN STORIES ARE BUILT AND TESTED:** `US-CWP-060` (`CWP-046`, `requests/Requests.tsx`), `062` (`CWP-052`, `requests/StopOrRestart.tsx`), `063` (`CWP-051`, `requests/TrackRequest.tsx`), `065` (`CWP-055`, `requests/DisputeBill.tsx`) and `066` (`CWP-054`, `requests/AskAQuestion.tsx`), served by `portal/requests`, `requests/{reference}` (+`/notes`, +`/withdraw`), `bills/{number}/dispute`, `portal/questions` and `accounts/{id}/stop-or-restart`(+`/ask`). ⚠ **TWO ARE NOT BUILT, BOTH DELIBERATELY AND BOTH BLOCKED:** `US-CWP-061` *moving out or moving on* (`CWP-048`, blocked on `OQ-1392`) and `US-CWP-064` *documents we need from you* (`CWP-049`, blocked on the upload re-sign). Neither screen has an address; both are rows in `unbuiltScreens.ts`. `CWP-048` is the one of the ten the SERVER holds — `ERRAND_HELD_UNTIL` names it per errand card — so the day it lands, `tests/test_cwp_holds_expire.py` fires. ⚠ **I4 IS NOT DONE AND WAS RECORDED NOWHERE:** `cr068-i-requests-and-disputes.mjs` does not exist.

⚠ **`OQ-1392` IS CLOSED AND EVERY *blocked on `OQ-1392`* IN THIS SECTION IS
STALE — CORRECTED 2026-09-06, `DEF-CWP-4200`.** The PO ruled on **2026-09-04**,
verbatim *"(a) ask only"*, and `BR-CWP-082` is **CONFIRMED** in the portal
module's rule table carrying that sentence. So: the **Stories** line's
*(⚠ `OQ-1392`)*, the demo script's **step 3** *"Call the self-serve close →
`NotImplementedError("OQ-1392")`"*, the **Blocked by** line, task **I1**'s
*"self-serve close raises `NotImplementedError("OQ-1392")`"* and the **Exit
test**'s *"`BR-CWP-082`/`OQ-1392` — the raise"* are all superseded. **There is
no stub to write and nothing to raise**: a customer may ask to close and may not
close, the boundary is a ruled ABSENCE rather than a question awaiting an
answer, and `CWP-048` is simply **UNBUILT** rather than blocked. The original
sentences are left in place rather than rewritten, per the supersession
convention — read this stamp, not them. (`CWP-049` **is** genuinely blocked: the
portal accepts no upload, that is a signed deferral, and its own wireframe
carries a `BLOCKED` stamp saying so.)

⚠ **I4 IS DONE — 2026-09-06, `2.197.12`, and the walkthrough it names is on disk
and GREEN.** `10-scripts/render-checks/cr068-i-requests-and-disputes.mjs` runs
the demo script in a real browser and finishes **0 failures with 4 named open
gaps**, having read **27 figures off the screen**. It ships with
`cr068-i-fixture.py`, and that fixture is not optional: on a plain
`seed_portal_demo` database **four of the five built screens draw an empty
branch** and the fifth draws a comparison it cannot make, so a run without it
reports this wave clean and proves nothing.

**What it proves, with the figures it printed** (`i-requests@example.test` on
`1408 Elm St · A`, a freshly seeded clone): `BR-CWP-081`'s verdict is
**computed and it FLIPS**, which is the one thing a single test case can never
show — five months `5 × $18.50 = $92.50` against `$185.00 + $150.00 = $335.00`
→ *stopping is cheaper*; twelve months `$222.00` → still stopping (the case
`DEF-CWP-3608` corrected, and it is in the run precisely because this plan said
*twelve* until 2026-09-03); nineteen months `$351.50` → *closing is cheaper*,
and the screen names it. `BR-CWP-078` holds over the whole rendered page **and**
the whole response body — the clerk's *"route to Tuesday crew, low priority"* is
in neither, while the note written FOR the customer IS, so the filter is not a
vacuous pass over an empty timeline. `BR-CWP-075` is proved by asking the edge:
`approve`, `refuse` and `close` all answer **404**. Hard rule 4 is proved by
asking the API on either side of a real query — `142.1800` before, `142.1800`
after — and a SECOND query on the same bill is refused **409** by name.
`US-CWP-064`'s deferral is proved by there being **no `input[type=file]` in the
DOM at all**.

**WHAT THE BROWSER FOUND THAT THE TESTS DID NOT — five defects, four of them
customer-facing.** `DEF-CWP-4204`: all five screens printed raw `YYYY-MM-DD` to
a customer whose tenant asks for `MM/DD/YYYY` — **fixed here**, and the
component test that asserted the broken string is now format-agnostic.
`DEF-CWP-4198`: a bill query writes a sentence composed for the CLERK's worklist
into the same column `CWP-046` prints as *the customer's own words*, carrying
**`142.1800 USD`** — four-decimal money on a customer screen — two ISO dates and
*"Their reason:"*. `DEF-CWP-4199`: **0 of 73 accounts on the demo tenant can
produce this wave's headline comparison**, because the seeded quote plan states
a base charge on the plan AND on the charge code and they disagree, and because
sixty-three other plans carry neither a connection fee nor a deposit.
`DEF-CWP-4201`/`4202`/`4203`: the wireframe pass below.

**LEFT OPEN, EACH WITH ITS REASON ON THE ROW:** `CWP-048` and `CWP-049` are
unbuilt (`DEF-CWP-3988`) and are known gaps in the walkthrough, so the day
either lands the run goes RED and names it; `OQ-CWP-1682` keeps the collection
hold off `CWP-055` and is a known gap for the same reason; and the *Attach a
photo* deferral on `CWP-054` is the fourth.

**Wireframe comparison:** `13-wireframe-delta.md` gains a **fourth pass**
covering all five built screens — nineteen screens of seventy-seven becomes
**twenty-four**.

### Wave J — *Your own reading, and the final bill* · `J39` · `J40` (bill half)

**Goal a person can see:** a customer standing at her meter sends a reading, is warned in
plain words when it looks nineteen times her usual, may send it anyway, and it appears on
**no bill** until a clerk clears it; a customer moving out sees the final bill settle her
deposit and **we owe you `$89.80`**.
**Stories:** `US-CWP-042` (`OQ-1393` **CLOSED 2026-09-04** — unbuilt, not blocked) · `US-CWP-037` · `US-CWP-068` (⚠ `OQ-249`, still OPEN)
**Demo script** (last read `153,040`; window 2–6 Sep):
1. Turn **Send your own reading** on for Pine Hill in Settings (it is off by default — `R8`). Before that, `CWP-035` is unreachable **and** `POST accounts/{id}/readings` refuses.
2. **Send your own reading** (`CWP-035`): meter `88-40219`, today, `153300` → accepted, lands **awaiting review**, and `CWP-034` shows *You sent it in · awaiting review* with an **empty** *on which bill* cell.
3. Type `158940`: the `DialInput` goes brand-red with *that is 5,900 gallons in two days — about **nineteen** times your usual* — and **it can still be sent**. A lower figure fires the low threshold with a sentence, not a silent rollover.
4. Run the next bill run on the fixture: the submitted read is on **no bill**. A later real read of `153,190` supersedes it; **no bill charges both** (asserted on the run's lines).
5. ⚠ **AMENDED 2026-09-06 (`DEF-CWP-4194`).** This step read *"Call the straight-to-bill path → `NotImplementedError(\"OQ-1393\")`"*. **There is no such stub to build**: `OQ-1393` was ruled on 2026-09-04 — option (b), a reading is ACCEPTED then validated then flagged, plus a **provenance flag on every customer reading** (*"you will also ahve to flag that this reading is reacievd from Cosnumer"*). What the ruling actually needs is a **fourth `meter_source`**: `READ_SOURCES` is `("ami","manual","import")`, B2 names the same three, and a customer's reading is not `manual`. The photo picker is still **held** (B9).
6. **Your final bill** (`CWP-032`) for the move-out on 17 Sep: service `$63.40`, deposit `−$150.00`, interest `−$3.20`, **we owe you `$89.80`** — a refund row exists and no credit note does; the deposit figures match `CWP-065`; the closing reading `154,310` with a *query this reading* route that is **gone after settlement**, and the screen says a correction is slower now.
7. **A visit is booked** (`CWP-067`): *A meter exchange is booked for Tuesday 15 September, morning* from the existing `WorkOrder`; when the crew closes it the **same** row shows done. Anything depending on the unresolved field-work shape raises `NotImplementedError("OQ-249")`; no visit → the screen and its link are absent.
**Exit test:** `BR-CWP-067` — the portal calls **the same** `metering/validation.py` service (`RULE_HIGH`, `RULE_ROLLOVER`, `RULE_OUT_OF_WINDOW` at 136–142) — asserted by the test importing no second validator · `BR-CWP-068`/`069` — on no bill until cleared; superseded never charged twice · `BR-CWP-070` — flagged is not refused · `BR-CWP-074` — the TWO flags: a validation flag only when the check objects, a provenance flag on **every** customer reading (`OQ-1393` closed 2026-09-04; no raise to assert) · `BR-CWP-048` — `−$89.80` is a refund, not a carried credit · `R8` — off means unreachable **and** refused.
**Depends on:** E, H (`CWP-034`), I (`US-CWP-061` for the move-out). **Blocked by:** `OQ-249` only (step 7); the upload re-sign. ⚠ This read *"`OQ-1393`, `OQ-249`"* until 2026-09-06 — `OQ-1393` has been closed since 2026-09-04 and blocks nothing (`DEF-CWP-4194`). **Runs in parallel with:** I (its final-bill step waits for I's move-out), K.
**Walkthrough:** `cr068-j-self-read-and-final-bill.mjs` · **Journeys written:** `J39-self-read-end-to-end.md`; `J40` bill half.
**Ships as:** nominal `2.138.0`. **Size:** medium — about 7 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **J1** | 2a | `POST accounts/{id}/readings` in `api.py` → `metering` seam → **`metering/validation.py`** (the one validator: high, low, rollover, window); `MeterRead.source` gains the value `portal` (**existing column**, `metering/models.py:1773`); new `review_state` (`awaiting_review \| cleared \| superseded`) and `submitted_by_credential_id` reconciled with `BR-MET-053`'s lifecycle in the packet (§0 row 4); a clerk's *clear* on the staff read-exceptions surface; the bill run **excludes** `awaiting_review`; supersession through the existing true-up. ⚠ Straight-through does NOT raise — `OQ-1393` is closed and a passing reading goes through; what it needs instead is the fourth `meter_source` for the provenance flag. The endpoint refuses when `self_read_enabled=false`. `GET bills/{no}` for a final bill reads `customers/move_out_settlement.py` (deposit, interest, refund vs credit). `GET accounts/{id}/visits` reads `WorkOrder` (`metering/connections.py:684`); the unresolved shape raises `NotImplementedError("OQ-249")` | `US-CWP-042`, `037`, `068` · `BR-CWP-048`, `067`–`070`, `074` | E1–E3, I1 | 3.4 · (037, 068: **new — no task in §12**; `CP-51` is 4.9 and moves here) | L |
| **J2** | 2b | `CWP-035` (T3; `DialInput` flagged state; `PhotoPicker` held; *what happens to it* `Panel`), `CWP-032` Your final bill (T4; the settle-up `KVList` + `TotalRow` *we owe you*; the query route that disappears), `CWP-067` (T3; absent when none). The phone reading screen `CWP-078` is **deferred** (PO) | three stories · B14 r10, r11 | E5, H2, J1 | new | M |
| **J3** | 2c | `test_us_cwp_042_tc*` (TC-3 next bill run excludes it; TC-8 superseded never charged twice; TC-10 the raise; TC-7 off means refused), `_037_tc*` (TC-2 `63.40 − 150.00 − 3.20 = −89.80`; TC-4 refund row, no credit note), `_068_tc*`; fixture: meter `88-40219` at `153,040`, the window 2–6 Sep, the move-out settlement, a booked meter exchange | three stories' §3/§4 | J1, J2 | new | M |
| **J4** | 2d | `cr068-j-self-read-and-final-bill.mjs` — the seven steps; asserts the nineteen-times sentence, the awaiting-review row with the empty bill cell, the `$89.80` sentence, the absent query route after settlement, the one remaining refusal sentence (`OQ-249`); screenshots | law 6 | J2, J3 | new | M |
| **J5** | doc | `J39` file; `J40` bill half; CHANGELOG + version; TSV; the two boundaries in the close record; the `review_state`/`BR-MET-053` reconciliation as a decision-log row with the worked read | law 9, W | J4 | 3.9 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. **ONE OF THE THREE STORIES IS BUILT:** `US-CWP-037` *your final bill* — `CWP-032` is `/final-bill` (`bills/FinalBill.tsx`), served by `accounts/{id}/final-bill`, and it is tested. ⚠ **THE WAVE'S HEADLINE STORY IS NOT BUILT:** `US-CWP-042` *send your own reading* (`CWP-035`) has no address; it is the ONE of the ten unbuilt screens held by a control that NAMES it — `portal.readings.sendReadingHeld` on `CWP-034`'s head action — so `G103` fails the merge the day it lands. ~~It is blocked on `OQ-1393`.~~ ⚠ **IT IS NOT — `OQ-1393` WAS CLOSED ON 2026-09-04 AND THIS SENTENCE WAS STALE FOR TWO DAYS (`DEF-CWP-4194`, amended 2026-09-06).** `CWP-035` is **unbuilt and unblocked**, which is a larger statement than *blocked*: nothing is waiting on the PO, and the work is a screen plus a fourth `meter_source`. `US-CWP-068` *a visit is booked at the property* (`CWP-067`) is likewise unbuilt and sits behind the field-work scope question `OQ-249`. **So this wave is a third built, and the title's first half is the part that is missing.** ~~`cr068-j-self-read-and-final-bill.mjs` does not exist.~~

⚠ **J4 IS DONE NOW — 2026-09-06, and the walkthrough it names is on disk and GREEN.**
`10-scripts/render-checks/cr068-j-self-read-and-final-bill.mjs` walks the demo script in
a real browser and finishes **0 failures with 11 named open gaps**. Where this table and
the code disagreed, the code won and the register says so.

**WHAT A CUSTOMER STILL CANNOT DO, WHICH IS THIS WAVE'S MAIN FINDING.** They cannot send
a reading. `/usage/submit` — the address the drawing's own bar carries — opens nothing;
there is no form, no `POST accounts/{id}/readings` (`apps/portal/api.py` says so in its
own comment), and nothing to flag, review or exclude from a bill run. The one control in
the product that names it is honest and cannot rot: `CWP-034`'s head action is held with
*"Sending readings is not ready yet"* — six words, inside B14 rule 33 — and `G103` fails
the merge the day `CWP-035` gains an address. **The absence is now four counted gap rows
rather than one sentence**, because the form, the nineteen-times warning, the
awaiting-review state and the provenance flag are four different pieces of work and
whoever builds the screen needs all four to come due.

**WHAT THE BUILT HALF PRINTED**, on a fixture with two leaving customers (`$150.00`
held since 4 March 2021, a tenant rate of 2%): **`$63.40` − `$150.00` − `$16.50` =
`−$103.10`, read as *We owe you*, raised as a REFUND and not a credit** — and the three
lines were added up **from the rendered cells**, which is `US-CWP-037`'s own acceptance
done on the screen rather than on a payload. The closing reading is `154,310` taken on
the move-out day, `1270 gal` used since — the unit on the cell, hard rule 3 — and *Read
by a meter reader*. ⚠ **The story's `−$89.80` is an illustration and not a ❄️ frozen
figure** (`US-CWP-037` carries `golden_tests: []`): the seeded tenant pays 0%, so the
answer moves with the rate and the walkthrough asserts the ARITHMETIC, never the literal.

⚠ **THE FIXTURE WAS THE MISSING HALF AGAIN.** `seed_portal_demo` plants **no final bill
on any account**, so `/final-bill` draws *"When your service ends, your last bill will be
here"* for every customer in the estate and a walkthrough without `cr068-j-fixture.py`
would have reported a clean walk of a screen it never saw (`DEF-WRK-4121`). **And ONE
move-out is not enough:** `Settlement.settled` is `path is not None or remainder == 0`
and a refund picks its path automatically, so *we owe you* and *you owe us* are mutually
exclusive screens. The fixture plants one of each.

**FIVE DEFECTS FILED FROM THE BROWSER, TWO FIXED HERE.**
`DEF-CWP-4190` — **`CWP-032` drew no heading at all on the only branch that has a
bill**; `{head}` was in the three empty-state returns and missing from the success
return, so the title appeared whenever there was nothing to read and vanished the moment
there was. Fixed, with a case asserting the `h1` **on the branch with data**, proved red
first. `DEF-CWP-4193` — four machine dates on the last screen a leaving customer sees;
fixed through `usePortalDate`. **Not fixed, deliberately:** `DEF-CWP-4191` — on the *you
owe us* half the panel lists `$289.10` − `$150.00` − `$16.50` and states **`$296.82`**,
because the deposit settles *"everything outstanding"* (the PO's own words closing
`OQ-158`) and **no line names the `$174.22` the account already owed**; the seam serves
`charges` for exactly this and the screen reads `service_charges`. The fix needs a new
customer-facing line in eleven catalogues, which is not a walkthrough lane's copy to
invent. `DEF-CWP-4192` — ***Query this reading* can never draw on a refund bill**, which
is the screen the drawing puts it on, and the component test proves otherwise by feeding
it `path: "refund"` with `query_reading_open: true` — a pair the server cannot produce.
`DEF-CWP-4194` — the six stale `OQ-1393` sentences this stamp is part of correcting.

**Wireframes compared:** `CWP-032`, `CWP-035` and `CWP-067`, all three, in
`13-wireframe-delta.md`. The two unbuilt ones are recorded **one-sided** — the drawing's
column filled in, the live column stated as absent — because what the picture asks for is
most of the specification whoever builds it will need.


### Wave K — *Messages, notices sent and not sent, and the two documents that do not exist yet* · `J47`

**Goal a person can see:** the bell reads `2`; a customer sees *Final notice · 15 Sep · post ·
not sent, no forwarding address* — the notice that never arrived is the one most visible;
and where a statement or a planned-work page would be, the screen says honestly what is
not there yet.
**Stories:** `US-CWP-067` (⚠ `OQ-1399`) · `US-CWP-039` (⚠ `OQ-1399`) · `US-CWP-038` (⚠ `OQ-1395`) · `US-CWP-011` (⚠ `OQ-249`, moved from Phase 1 — §0 row 21)
**Demo script:**
1. **Messages** (`CWP-053`): five rows, two unread; the shell's bell reads **2**; open *Your August bill is ready — $142.18* → the bell reads **1**; *mark all read* → zero, each row's read timestamp set on the **portal-owned per-recipient row** (§0 row 5).
2. `CWP-025`'s *In the portal* column is now a **real** switch; turn it off for *Payment received* → the row stops appearing here **and post still goes** (the outbound row still names post).
3. **Everything we sent you, and what came back** (`CWP-068`): three notices, one skipped — *Final notice · 15 Sep · post · not sent, no forwarding address* (`NoticeHistory` skip reason, `collections_models.py:266`); a message the product could not send shows `unavailable` with its reason. On `CWP-031` the skipped notice is **absent** — it has no document — and that split is the point.
4. A paperless customer who **never signs in**: post still went, and the notice's outcome names post. Any path recording a portal row as **delivery** → `NotImplementedError("OQ-1399")`.
5. **Statement**: pick 1 January to 30 June on `CWP-031` — the date-range read returns every bill, payment, credit and adjustment in order, the corrected pair as two rows; request the **document** → `NotImplementedError("OQ-1395")`, shown as one plain sentence (five or six words).
6. **Outages and planned work** (`CWP-058`): with two works seeded directly, *Water main replacement · Elm St, 1400–1500 · 4–5 Sep · Planned*; the same work appears in `CWP-053` for `1408 Elm St · A` and **not** for `22 Palm Ct`; with none, the page and its link are **absent**; the planned-work write path → `NotImplementedError("OQ-249")`.
7. `CHANNELS_BY_KIND` (`catalogs.py:1915`) gains `portal` for the classes ruled in, dated — and the catalogue entry that said this platform has no portal channel is amended, not deleted (`CR-068` §2c).
**Exit test:** `BR-CWP-084` — a portal row is a record that a message exists (asserted: no delivery status moves when a row is read) · `BR-CWP-085` — the skipped notice appears with its reason · `BR-CWP-083`/`R4` — post still went for the customer who never signed in · `BR-CWP-088`/`OQ-1399`, `OQ-1395`, `OQ-249` — each raise with its id · `BR-CWP-093` — absent pages when nothing is there · `BR-CWP-005` — the notifications docstring's split (message × recipient) honoured.
**Depends on:** E, F (`CWP-025`), G (`CWP-031`), B (`interruption`). **Blocked by:** `OQ-1399` (put to the PO first — K0), `OQ-1395`, `OQ-249` — all three demonstrated as boundaries. **Runs in parallel with:** I, J.
**Walkthrough:** `cr068-k-messages-and-notices.mjs` · **Journeys written:** `J47-notices-sent-and-not-sent.md`.
**Ships as:** nominal `2.139.0`. **Size:** large — about 8 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **K0** | doc | **`OQ-1399` put to the PO in plain English with a figure**, before Phase 3 starts (prepared during Phase 2): *a disconnection notice posted on 15 September to an address with no forwarding address was never delivered; if the portal counted as delivery, a customer who does not sign in would be cut off having been "told" — the three options and what each changes for audit and retention.* Recorded verbatim on return (law 9, 13) | `BR-CWP-088` | — | 3.1 (precondition) | S |
| **K1** | 2a | **The portal as a fourth channel** (`CP-17`): `CHANNELS_BY_KIND` gains `portal` for the ruled classes (`notifications/catalogs.py:1915`, dated amendment); a **portal-owned per-recipient message row** (message × credential: delivered-to-portal = queued and visible, `read_at`) — **not** columns on `outbound_message` (§0 row 5); `GET messages`, `POST messages/{id}/read`, unread count for the bell; the preference's portal switch becomes real (F1's held column). `GET accounts/{id}/notices` reading `NoticeHistory` (`collections_models.py:239`) **including skips** and `DeliveryReturnEvent` (321). Any path treating a portal row as delivery raises `NotImplementedError("OQ-1399")`. `GET accounts/{id}/statement` — the date-range read over bills, payments, credits, adjustments; the document raises `NotImplementedError("OQ-1395")`. Planned work: the read and the affected-premises join against `interruption` (B1); the `planned_outage` **table is not created** and the write path raises `NotImplementedError("OQ-249")` (`US-CWP-011` §5) | `US-CWP-067`, `039`, `038`, `011` · `BR-CWP-083`–`088`, `093` | E1–E3, B1, F1, G1 | 3.1 · 3.2 · 3.3 · 4.5 (moves here) · `CP-16` (moves here) | L |
| **K2** | 2b | `CWP-053` Messages (T5; unread rows marked; *mark all read*), the bell count in `PortalShell`, `CWP-068` (T3 with a `DataTable` main; outcome column), the statement range picker on `CWP-031` with the held document control and its sentence, `CWP-058` (T5; absent when none). `CWP-025`'s *In the portal* switch made live | four stories · B14 r15, r17, r33 | E5, F2, G2, K1 | new | M |
| **K3** | 2c | `test_us_cwp_067_tc*` (TC-3 post still goes; TC-4 the raise; TC-5 never-signs-in), `_039_tc*` (TC-1 skip sentence; TC-2 absent on documents; TC-8 empty → absent), `_038_tc*` (TC-2 the raise; TC-5 corrected pair as two rows), `_011_tc*` (TC-2 affected accounts only; TC-4 the raise); fixture: five messages two unread, three notices one skipped for *no forwarding address*, two planned works seeded directly | four stories' §3/§4 | K1, K2 | new | M |
| **K4** | 2d | `cr068-k-messages-and-notices.mjs` — the six screen steps; asserts the bell text `2 → 1 → 0`, the skip sentence, its absence on `CWP-031`, the three refusal sentences, the absent `CWP-058` link with no works; screenshots | law 6 | K2, K3 | new | M |
| **K5** | doc | `J47` file; CHANGELOG + version; TSV; the catalogue amendment dated; the three boundaries in the close record; `US-CWP-011`'s frontmatter `wave` amended with the reason (§0 row 21) | law 9, W | K4 | 3.9 (part) | S |

⚠ **NOT BUILT AS OF 2026-09-06 (`bc4b976e`), AND THIS ROW SAYS SO RATHER THAN SAYING NOTHING.** Re-decided from the code, not from this table. **Nothing in this wave exists:** there is no `/messages` route in `portalRoutes.tsx`, no messages or notice-log endpoint in `api.py`, and no model for either in `portal/models.py` (the six models are `PortalSettings`, `PortalApplicationDraft`, `PortalConsent`, `PortalCredential`, `PortalSession`, `PortalOneTimeCode`). **All four stories are blocked and none has a single implementing test:** `US-CWP-011` outages (`OQ-249` field-work scope), `US-CWP-038` a statement (`OQ-1395`), `US-CWP-039` every notice sent and deliberately not sent (`CWP-068`, `OQ-1399`) and `US-CWP-067` messages (`CWP-053`, `OQ-1399`). The three references to `US-CWP-067` in the tree are HOLD-EXPIRY references, not implementation: `CWP-053` is drawn but unbuilt, and `PortalShell.tsx`'s *Messages* word is self-releasing — `MESSAGES_SCREEN_ID` resolved against `PORTAL_SCREENS` on every render — so the header link appears the moment the screen lands and cannot rot. **This row is left unstamped on purpose: the absence is the statement.**

---

## 5 · PHASE 4 — LAUNCH: customers in difficulty can help themselves before it gets worse

**Launch sentence:** `CR-068` §12 Phase 4, kept verbatim in §1. **Deliberately ahead of
paying** — a customer who can see the ladder and ask for a plan is helped on a day they
cannot pay.
**Stands on:** W4 (plans, collections ladder, protections, budget billing — all built).
**Stories (13):** `US-CWP-029`, `030`, `035`, `044`, `051`–`059`.
**Order:** **L, M, N and O all run in parallel** after Phase 2's wave E (O also needs G).

### Wave L — *Overdue: the ladder, its cost, and the three protections* · `J43`

**Goal a person can see:** a customer `$412.60` overdue reads exactly what happens next and
what it would cost, beside a button that stops it; three protections with three different
lifetimes in three different sentences; and a hold that stops a disconnection but not the debt.
**Stories:** `US-CWP-057` · `US-CWP-058` (⚠ `OQ-1391`) · `US-CWP-059` · `US-CWP-056`
**Demo script** (`$412.60` overdue 19 days; certificate to 30 Nov; moratorium 1 Dec–1 Mar):
1. **What happens if this is not paid** (`CWP-057`): *`$412.60` is overdue by 19 days*; the timeline — due 14 Aug, reminder 21 Aug, late fee `$8.25` 24 Aug, first notice 1 Sep, final notice *around 15 Sep*, disconnection *no earlier than 25 Sep* — built from **this account's `DisconnectCase`**, not the cadence settings (two accounts at different tiers show different dates).
2. The cost panel: owed `$412.60` + reconnection `$95.00` + new deposit `$150.00` = ***if it goes that far `$657.60`***, beside *Ask for a plan* (reaches `CWP-042` carrying `$412.60`) and *Pay* (held).
3. An account at the **five-day** notice: the tier renders as an **absence** (`TIER_UNMAPPED`, `customers/disconnects.py:603`) — the ten-day date is **not** shown.
4. **Help paying** (`CWP-056`): three cards — a plan, a certificate route that says **in words** the hold expires, level pay — and the moratorium *between 1 December and 1 March nobody is disconnected in this state* as a **fact with no button**. Submit a certificate → it becomes a request a person judges; **no protection row is created** by the form; the route ends *bring it to the office*. The plan card → `NotImplementedError("OQ-1391")` on self-activation.
5. **What is protecting your supply** (`CWP-064`): *A doctor's certificate is holding your supply until 30 November* and *this is not permanent*; the plan hold with **no date** — *it lifts the day an instalment is missed*; the moratorium `1 December 2026 – 1 March 2027` from the **record** with no button; the warning *A hold stops a disconnection. It does not stop the debt.* A certificate with no end date is refused upstream and never rendered.
6. **Credits and refunds** (`CWP-045`): the refund at *Raised 18 Sep `$89.80` · Approved 19 Sep · Sent 21 Sep · Cleared usually within ten working days*; two credits of `$25.88` with the bill each was used on; spend a credit between two loads — the second load shows the new figure; the sentence *a credit comes off your next bill. A refund is money sent back.*
7. An account not overdue: `CWP-057` and its link are absent; no protection: `CWP-064` absent; no credits and no refunds: `CWP-045` absent.
**Exit test:** `BR-CWP-092` — an unmapped rung is an absence, never rounded · `BR-CWP-090` — three lifetimes, three sentences; no invented expiry on the plan hold · `BR-CWP-089` — no protection row from any portal form · `BR-CWP-091` — the debt sentence present · `BR-CWP-066`/`OQ-1391` — the raise · `BR-CWP-047` — the credit re-read, never cached · `BR-CWP-051` — write-off without reason code.
**Depends on:** E. **Blocked by:** `OQ-1391` (boundary, step 4); the upload re-sign (certificate). **Runs in parallel with:** M, N, O.
**Walkthrough:** `cr068-l-overdue-and-protections.mjs` · **Journeys written:** `J43-overdue-and-the-protections.md`.
**Ships as:** nominal `2.140.0`. **Size:** medium — about 7 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **L1** | 2a | `GET accounts/{id}/arrears` over `DisconnectCase` (`disconnects.py:1259`), `DisconnectNotice` (1481), `LadderState` (2139), the reconnection fee and deposit from the case — **`TIER_UNMAPPED` rendered as an absence** (603); `GET accounts/{id}/protections` over `AccountProtection` (1629) — three shapes, the moratorium from the record; the certificate route creates a **request**, never a protection (`BR-CWP-089`); `GET accounts/{id}/credits` (`billing/credit_notes_api.py` seam; **never cached**), `GET accounts/{id}/refunds` (`payments/refunds.py` lifecycle incl. voided). Plan self-activation raises `NotImplementedError("OQ-1391")` (shared with M1) | `US-CWP-056`–`059` · `BR-CWP-047`, `089`–`092` | E1–E3 | 4.3 · 4.4 · 2.8 (credits/refunds move here) | M |
| **L2** | 2b | `CWP-057` (T3; `ChecklistTimeline` ladder; cost `KVList` + `TotalRow`), `CWP-056` (`CardGrid3` then `InfoBar`; the moratorium card has **no button**), `CWP-064` (T3; three `ProtectionCard`s; absent when none), `CWP-045` (T4; two halves and the separating sentence). `CWP-079` phone overdue **deferred** (PO) | four stories · B14 r11, r33 | E5, L1 | new (§12 has no Phase 4 screen task) | M |
| **L3** | 2c | `test_us_cwp_056_tc*`…`_059_tc*`; 057 TC-2 `412.60 + 95.00 + 150.00 = 657.60`; 057 TC-3/4 absence and per-case dates; 058 TC-2/4 no button, no protection row; 059 TC-2/4; 056 TC-3 no cache; fixture: the overdue account with its case at tier 1 and a second at the five-day notice, the certificate to 30 Nov, a plan hold, the moratorium record, the refund and two credits | four stories' §3/§4 | L1, L2 | new | M |
| **L4** | 2d | `cr068-l-overdue-and-protections.mjs` — the seven steps; asserts `$657.60`, the absent ten-day date on the five-day account, no `button` inside the moratorium card, the three lifetime sentences, the credit figure changing between loads, the absent pages; screenshots | law 6 | L2, L3 | new | M |
| **L5** | doc | `J43` file; CHANGELOG + version; TSV; the `OQ-1391` boundary in the close record | law 9, W | L4 | 4.11 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. All four stories are built and tested: `US-CWP-056` (`CWP-045`, credits and refunds), `057` (`CWP-057`, the overdue ladder), `058` (`CWP-056`, help paying) and `059` (`CWP-064`, what is protecting your supply) — all four routed to real components in `portal/arrears/ArrearsPages.tsx` and `arrears/MoneyBack.tsx`, served by `accounts/{id}/arrears`, `…/help-paying` (+`/ask`), `…/protections` and `…/money-back`. ⚠ **L4 IS DONE AS OF 2026-09-06 (`2.197.5`), AND THE BROWSER FOUND WHAT THE STAMP ABOVE COULD NOT.** `cr068-l-overdue-and-protections.mjs` is written and **GREEN at 91 checks**, with `cr068-l-fixture.py` beside it — the wave's state is **not in the seeder and cannot be**: on a freshly seeded database every Pine Hill account owes `$0.00`, so all four of these screens draw their ABSENCE state and a walkthrough run against the seeder alone would pass every assertion it makes about rows **because there are no rows** (`DEF-WRK-4121`'s shape). **Figures the browser printed:** `$412.60` overdue by `19 days` · reconnection fee `$95.00` read from the tenant's own `CC-RECON` row · subtotal `$507.60`, added up in the browser from the parts on screen and compared with the printed row · refund `$89.80` in four dated steps · credits `-$25.88` each, and the count changed `2 → 3` between two loads, which is the only way `BR-CWP-047` can be proved in a browser. **Every exit-test rule held:** the unmapped rung is an absence with no neighbour's chip, the three lifetimes are three different sentences, the plan hold carries no invented date, the moratorium card contains no control, the certificate form created no protection row (counted before and after), and all three screens state their absence on an account in good standing.

⚠ **THE DEMO SCRIPT'S `$657.60` IS UNREACHABLE AND STEP 2 SHOULD BE READ WITH THAT IN MIND.** It adds a `$150.00` new deposit, and **no read in this product prices a reconnection deposit** (`OQ-CWP-1600`, OPEN). The panel states the requirement in words — *required, ask us the amount* — and the closing row is a SUBTOTAL. `$507.60` is `$412.60 + $95.00`, and inventing the missing figure would put a number nobody set in front of the most frightened reader this product has.

⚠ **AND STEP 4'S `NotImplementedError("OQ-1391")` IS STALE PROSE — THE QUESTION CLOSED ON 2026-09-04**, option (a), PO verbatim: *"Utility Clark will di it for Consumer; COnsumer cannot do it by themself; these are special cases"*. Self-activation is declined **permanently** rather than stubbed, `BR-CWP-066` is CONFIRMED, and the control correctly reads **Ask for a payment plan** — five words, `B14` rule 33. Amended here per CLAUDE.md's status-column rule: a closed question's body goes on describing the open world, and the body is what a lane actually reads.

⚠ **EIGHT DEFECTS FILED, ONE FIXED.** `DEF-CWP-4142` (**fixed**): `disconnects.case_payload` never serialised `next_step_due`, so `selectors._timeline`'s `notice_next` branch was unreachable and `CWP-057` could never draw the ***final notice*** rung — the ladder went from the notice already sent **straight to disconnection**, telling a household when the supply goes and not when the last warning arrives. `DEF-CWP-4143` (high, open): there is **no Pay control on `CWP-057` at all**, held or otherwise, while `/pay-now` (`CWP-038`) is live. Then `4144` two duplicated headings and a noun-phrase button · `4145` every `ProtectionCard` missing the action the drawing gives it, through an optional prop nothing passes · `4146` `CWP-045` one column where L2 and the drawing both say two · `4147` `account_balance` answering `open_bill_count: 0` for an account it says owes `$174.22` · `4148` the chromium fallback every render-check copies is a catch that cannot catch · `4154` a plan hold whose plan is not current labelled *Not started yet* beside a start date in the past. **The four screens' picture-by-picture comparison is `13-wireframe-delta.md`.**

### Wave M — *Plans and level pay* · `J41` · `J42`

**Goal a person can see:** a customer spreads `$132.20` over six months and sees five of
`$22.03` and one of `$22.05`; a plan the utility offered is accepted on **her** signature
alone and moves `agreement_sent → active`; an enrolled level-pay customer sees *you pay
`$125.00` · you are `$47.30` ahead · June settles up*.
**Stories:** `US-CWP-051` (⚠ `OQ-1391`) · `US-CWP-052` · `US-CWP-053` · `US-CWP-054` · `US-CWP-055`
**Demo script:**
1. **Ask for a payment plan** (`CWP-042`): `$172.20` overdue, six months, `$40.00` up front → the table: five instalments of **`$22.03`** and a final **`$22.05`**, total **`$132.20`**; the `ConsequenceBox` says *five payments then one* (the count matches the table). Thirteen months refused naming 2–12. `$120.00` over six → six of `$20.00`, no odd final. Press *Ask for this plan* → the ask lands for a person; self-activation → `NotImplementedError("OQ-1391")`.
2. **Your payment plan** (`CWP-043`): six rows *paid on time · paid on time · paid late · due in 9 days · to come · to come*; instalment 2 names **the payment that cleared it**; `$40.00 paid up front`; cadence *monthly* from the record; on a plan with `suspend_late_fees=false` the panel says **fees still apply**; the hold panel: *new bills still arrive and still have to be paid*; a **closed** plan is still reachable, marked closed.
3. **A plan the utility has offered you** (`CWP-063`): *Pine Hill has offered you a plan. Sarah at the office set this up on 2 September.* Six dated instalments. **Accept this plan ✓** → the row moves `agreement_sent → active` **with the customer's signature date**, and `CWP-043` opens at instalment 1 of 6 *to come*. Do nothing → it stays `agreement_sent`. After 16 September → *the office has to set it up again*. *Ask for different terms* raises a request. A delegate with See only cannot accept.
4. **Level pay** (`CWP-044`): twelve months totalling `$1,501.09`, average `$125.09`, **rounded to `$125.00` by the tenant's rounding setting**; the chart; the box names **the tenant's** settle-up month. Fewer months than eligibility → not offered, with the reason in words.
5. **Where your level pay stands** (`CWP-066`): *You pay `$125.00` · you are `$47.30` ahead · June settles up*; each re-levelling with what happened; *ahead*/*behind* in words; a not-enrolled customer is routed to `CWP-044`.
6. Plans switched off for the tenant → `CWP-042` unreachable **and** the endpoint refuses.
**Exit test:** `BR-CWP-062` — `(172.20 − 40.00) ÷ 6` → five at `$22.03` (`$110.15`) and `132.20 − 110.15 = $22.05`, summing exactly · `BR-CWP-063`/`064` — the hold sentence; *fees still apply* on the per-plan election · `BR-CWP-065` — activation on the customer's signature alone, `customer_signed_on` set; `offer_expires_on` refuses after 16 Sep · `BR-CWP-066`/`OQ-1391` — the raise · `BR-CWP-054` — the level from the tenant's rounding setting, not a portal rule · `R8` — plans off means unreachable **and** refused.
**Depends on:** E. **Blocked by:** `OQ-1391` (boundary, step 1). **Runs in parallel with:** L, N, O.
**Walkthrough:** `cr068-m-plans-and-level-pay.mjs` · **Journeys written:** `J41-a-plan-asked-for.md`, `J42-a-plan-offered.md`.
**Ships as:** nominal `2.141.0`. **Size:** large — about 8 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **M1** | 2a 🔒 | `POST accounts/{id}/plans/preview` over the **existing** instalment arithmetic in `payments/plans.py` (remainder on the final instalment — no arithmetic in the portal); `POST …/plans/request` lands a request for a person; self-activation raises `NotImplementedError("OQ-1391")`; `GET …/plans/current` (installments + the payment that cleared each; `suspend_late_fees` from `collections_models.py:166`; closed plans still served); `GET …/plans/offer`, `POST plans/{id}/accept`, `POST plans/{id}/decline` — **new columns `customer_signed_on`, `offer_expires_on`** on `PaymentPlan` (`03-field-map.md` §3 rows 5–6), transition `agreement_sent → active` on the customer's signature (`plans.py` is 🔒 — review-ledger row); *different terms* raises a request. `GET accounts/{id}/level-pay` and `POST …/level-pay/join` over `billing/budget_api.py` eligibility/enrol/account (303, 443, 515) — the level from the tenant's rounding setting; refuses when `plans_enabled=false` | `US-CWP-051`–`055` · `BR-CWP-062`–`066`, `054` | E1–E3 | 4.2 · 2.10 · 2.9 (level pay) | L |
| **M2** | 2b | `CWP-042` (T2; instalment `MiniTable` + total; `ConsequenceBox`), `CWP-043` (T3; the payment that cleared each row; *while the plan holds* `Panel`), `CWP-063` (T3; three controls in the order **Accept · Ask for different terms · Decline**), `CWP-044` (T4; `ChartPanel`), `CWP-066` (T3 with `KpiRow`; CSV) | five stories · B14 r4, r11 | E5, M1 | new | L |
| **M3** | 2c | `test_us_cwp_051_tc*`…`_055_tc*`; 051 TC-2 the arithmetic from the existing service; 051 TC-10 the raise; 052 TC-5 *fees still apply*; 053 TC-2/3/4 signature, no clerk activation, expiry; 054 TC-2 rounding by setting; fixture: `$172.20` arrears, a plan three-of-six paid with `suspend_late_fees=false`, an offer by *Sarah* expiring 16 Sep, twelve months totalling `$1,501.09`, an enrolment `$47.30` ahead | five stories' §3/§4 | M1, M2 | new | M |
| **M4** | 2d | `cr068-m-plans-and-level-pay.mjs` — the six steps; asserts the six instalment strings and the total, the *five payments* copy, *fees still apply*, the `agreement_sent → active` change via the API after the click, `$125.00`, the `OQ-1391` refusal sentence; screenshots | law 6 | M2, M3 | new | M |
| **M5** | doc | `J41`, `J42` files; CHANGELOG + version; TSV; review-ledger row for the `plans.py`/`PaymentPlan` change **in plain English with the worked plan** (five of `$22.03`, one of `$22.05`); the `OQ-1391` boundary | law 9, W · `g07` | M4 | 4.11 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. All five stories are built and tested: `US-CWP-051` (`CWP-042`, ask for a plan), `052` (`CWP-043`, your plan), `053` (`CWP-044`, level pay), `054` (`CWP-063`, a plan the utility has offered you) and `055` (`CWP-066`, where your level pay stands) — five real components under `portal/plans/`, served by `accounts/{id}/plans/current`, `…/plans/offer`, `…/plans/preview`, `…/plans/request`, `…/level-pay` and `…/level-pay/standing`. ⚠ **M4 IS DONE — 2026-09-06, AND IT IS THE FIRST TIME ANY OF THESE FIVE SCREENS
HAS BEEN OPENED IN A BROWSER.** `cr068-m-plans-and-level-pay.mjs` now exists and
PASSES, with `cr068-m-fixture.py` beside it. **It found five defects that 55
component tests, 23 backend tests, `tsc` and every gate had passed over**, and
one of them was a customer-facing promise on the screen where a plan is
accepted:

* **`DEF-CWP-4137` (high) — `CWP-063` told a customer *"Miss two payments and the
  plan ends, and the whole balance falls due."*** The PO ruled the opposite on
  2026-08-11 (*"nodrop we chase for payments until write off"*) and
  `record_missed_instalment` returns `active` on the tenth miss. `CWP-042`
  printed the true sentence all along, so this wave said two opposite things
  about one rule. **It escaped because the guard exists on the other two plan
  screens and `PlanOffer.dom.test.tsx` supplied the forbidden code in its own
  fixture.** Fixed; the assertion was proved red on the defect first, through
  vitest rather than by hand.
* **`DEF-CWP-4138` — all five screens printed raw ISO dates** (`2026-09-14`) to a
  tenant set to `MM/DD/YYYY`. `DEF-CWP-3994` shipped the `usePortalDate` hook
  for exactly this and wave M never adopted it. Fixed.
* **`DEF-CWP-4139` — four held controls cited `OQ-CWP-1565`, an id that was never
  issued** (no register row, no reservation), for two different questions. The
  real question is `OQ-CWP-1568`, which the SERVER cites correctly. `1563` and
  `1564` were wrong the same way, each by exactly three. Fixed, in the code and
  in `holds.ts`.
* **`DEF-CWP-4140` — the rounding note was unconditional**, so `$120.00` over six
  (six of `$20.00`, this wave's own second demo case) told the customer the last
  instalment carried a rounding. Fixed at the source: `carries_the_rounding` now
  means what its name says instead of *is the last row*.
* **`DEF-CWP-4141` (open) — thirteen months is refused with *"check the dates"***
  when the term is the field at fault and the server sends `min: 2, max: 12`.

⚠ **THE FIXTURE IS THE OTHER HALF OF THE STORY AND M3 OVERSTATED ITSELF.** None
of wave M's demo state is seeded: after `seed_portal_demo` there are **no
level-pay rows, no plan in `agreement_sent` and no portal credential at all**, so
`CWP-063` and `CWP-066` draw *nothing here* branches that render, assert cleanly
and prove nothing (`DEF-WRK-4121`). `cr068-m-fixture.py` builds the state, calls
`build_schedule` rather than typing six figures in, and **refuses to seed
anything** unless the engine still returns five of `$22.03` and a final `$22.05`
summing to `$132.20`.

⚠ **AND M1's TWO NEW COLUMNS WERE NEVER ADDED.** This table says
*"new columns `customer_signed_on`, `offer_expires_on` on `PaymentPlan`"*;
`payment_plans` has neither, and the transition `agreement_sent → active` on the
customer's signature is not built. That is CORRECT as things stand —
`OQ-CWP-1568` (may a signed-in customer accept a plan?) is OPEN and all three
controls are held — but the row read as though the columns existed. **What
shipped is the READ; the write is still a question.**

⚠ **WHAT THE BROWSER STILL HAS NOT PROVED**, both named as skips in the run
rather than passed over: `CWP-044`'s eligible-but-not-enrolled branch (the one
the wireframe draws) and `CWP-066`'s twelve-month chart, because the fixture
account has two months of billing history. **Eight wireframe gaps are open and
registered** through `lib/knownGaps.mjs`, so the run counts them and goes red the
day one closes — see `13-wireframe-delta.md`'s third pass for all five screens.

### Wave N — *People with access* · `J44`

**Goal a person can see:** Maria gives her bookkeeper access without giving them her
password; the invitation says what they can and cannot do in both directions; and when
Kestrel pays a bill the audit entry names **Kestrel Bookkeeping**, not Maria.
**Stories:** `US-CWP-029` (⚠ `OQ-1396`) · `US-CWP-030` (⚠ `OQ-1396`)
**Demo script:**
1. **People with access** (`CWP-026`): Maria shown as `HOLDER` with no expiry; invite `accounts@kestrel.example` to *Common areas* with See and Download, ending 30 Jun 2027 → the row reads *Common areas · See · Download · 30 Jun 2027 · Invited*.
2. The invitation token (unguessable, single-use) opens **Accept an invitation** (`CWP-021`) for someone not signed in: the account, *See bills · Pay · Download receipts*, and **explicitly** *Close the account · Change the owner · Move out* as things they could **not** do, *Access ends 31 Dec 2026*.
3. Accept having no login → routes into enrolment (wave E), then the account appears in **Kestrel's** set and nobody else's.
4. Kestrel performs a permitted action (a download; a payment once Phase 5 lands) → the audit entry names **Kestrel Bookkeeping** (`portal_delegate.audit_actor_id`, the `portal_actor_label`), not Maria.
5. Kestrel tries to close the account → refused; the permission set **cannot contain** `close_account`. A non-holder tries to invite → refused. An expired delegate is refused on the very next request.
6. Remove Kestrel → the row moves to `ended` and **stays on the record**. Call the retention/revocation policy → `NotImplementedError("OQ-1396")`.
**Exit test:** `BR-CWP-009` — the set is built from customer links **and** delegate grants only · `BR-CWP-017` — four fixed roles · `PR-14`/hard rule 7 — the named actor on every delegate action · `OQ-1396` — the column and set built, the policy raises · `BR-CWP-039` — the consequence stated in both directions before *Accept*.
**Depends on:** E. **Blocked by:** `OQ-1396` (boundary, step 6). **Runs in parallel with:** L, M, O.
**Walkthrough:** `cr068-n-people-with-access.mjs` · **Journeys written:** `J44-a-delegate-invited-and-named.md`.
**Ships as:** nominal `2.142.0`. **Size:** medium — about 5 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **N1** | 2a 🔒 | `portal_delegate` (`03-field-map.md` §1; `permissions ⊂ {see, download, pay, save_method}`, **never** `close_account`/`change_owner`/`move_out`; `expires_on` column built, **policy stubbed** `NotImplementedError("OQ-1396")`; `status` incl. `ended` kept), `*rls*` migration (🔒); `GET details/access`, `POST details/access/invite` (holder only), `DELETE details/access/{id}`, `GET invitations/{token}`, `POST invitations/{token}/accept` (outside the account set — the invitee may not be signed in); the session's account set gains the delegate source (E1's second source); **`audit_log.portal_actor_id` + `portal_actor_label`** written on every delegate action (`audit/models.py:51` has only `actor_user_id` today; row 11 of `03-field-map.md` §3) | `US-CWP-029`, `030` · `BR-CWP-009`, `017`, `039` · hard rule 7 | E1, E2 | 4.1 | L |
| **N2** | 2b | `CWP-026` (T5; `DataTable`, row actions as icons *Edit · Remove*; the invite form with permission set and end date), `CWP-021` (T7; both directions stated; *Accept* / *Decline*) | two stories · B14 r15 | E5, N1 | new | M |
| **N3** | 2c | `test_us_cwp_029_tc*` (TC-2 audit actor; TC-3 permission set; TC-6 expiry on the next request; TC-9 the raise), `_030_tc*` (TC-8 token entropy and single use); fixture: Kestrel Bookkeeping's invitation | two stories' §3/§4 | N1, N2 | new | S |
| **N4** | 2d | `cr068-n-people-with-access.mjs` — the six steps; asserts the invitation's *could not do* list, the audit row's actor label via the API, the `ended` row still present, the `OQ-1396` refusal sentence; screenshots | law 6 | N2, N3 | new | S |
| **N5** | doc | `J44` file; CHANGELOG + version; TSV; review-ledger row for the delegate RLS migration and the audit actor columns **in plain English with the figure** (*after Kestrel pays a bill the entry names Kestrel, not Maria*); the `OQ-1396` boundary | law 9, W · `g07` | N4 | 4.11 (part) | S |

⚠ **NOT BUILT AS OF 2026-09-06 (`bc4b976e`), AND THIS ROW SAYS SO RATHER THAN SAYING NOTHING.** Re-decided from the code, not from this table. **Nothing in this wave exists:** neither of its two screens has an address — `CWP-026` *people with access* and `CWP-021` *accept an invitation* are both rows in `07-frontend/src/portal/routing/unbuiltScreens.ts` with pointer kind **`none`**, meaning nothing in the product points at either, so no gate can fire when they land. There is no delegate or invitation model in `portal/models.py`, no migration for one, and no endpoint in `api.py`; the only occurrence of the word *delegate* in the portal backend is a sentence in a docstring describing what one WOULD be able to read. `apps/portal/` contains no `delegates.py` — wave A's stamp already ruled that such a file arrives with the wave that fills it, and that wave has not run. Both stories are blocked on `OQ-1396` and neither has an implementing test. **This row is left unstamped on purpose: the absence is the statement.**

### Wave O — *Why this bill is different, and the alert that has no trigger* · `J38`

**Goal a person can see:** *Why August cost `$3.74` more* — four lines that sum **exactly**
to the difference between `$138.44` and `$142.18`; and the high-usage screen rendered from a
seeded alert with copy honest that nothing fires it yet.
**Stories:** `US-CWP-035` · `US-CWP-044` (⚠ no trigger — a scope decision, placed here from `wave: 0`)
**Demo script:**
1. Open `BL-2608-0141` → *Why is this bill different?* (`CWP-030`): *Why August cost `$3.74` more*; the four lines `+$8.83`, `$0.00`, `+$4.29`, `−$9.38`; **the sum is `+$3.74`** and `$142.18 − $138.44 = $3.74`. Against last August: `4,090 gal → 4,820 gal`, rate unchanged.
2. Perturb one component in a worktree → the test fails (no tolerance). A bill that went **down** reads *cost less* with the signs reversed and still sums. The **first** bill on an account offers no comparison at all.
3. A month where a rate version changed: the rate component is its own line from the version that applied.
4. **Your usage looks high** (`CWP-036`), from a seeded alert: *Since 25 August you have used about twice your normal daily amount*, the fourteen-day chart with the change marked, the causes, two routes (send a reading; ask for a visit). The copy names **billing time** on a monthly-read account and does not promise daily detection.
5. Fire the read-validation threshold (`RULE_HIGH`) on the fixture → **no** alert is produced; the test asserts nothing fires this screen. With no alert on the account, the screen and its message row are absent.
**Exit test:** `BR-CWP-046` — the lines sum exactly to the stated difference; a perturbation fails the test · `PR-28` — the comparison never disagrees with the bill · `BR-CWP-093` — first bill: no comparison against zero; no alert: absent · `US-CWP-044` TC-2/4 — nothing fires it; the validation threshold does not produce it.
**Depends on:** E, G (`CWP-028`), H (usage). **Blocked by:** nothing — but the **decomposition rule is a finance judgment** (`US-CWP-035` §8): which components exist and how two that move at once are attributed. Raised with the figure above through the review ledger (task O5); the build uses the blueprint's four-line decomposition until answered. **Runs in parallel with:** L, M, N.
**Walkthrough:** `cr068-o-why-different.mjs` · **Journeys written:** `J38-the-bill-that-went-up.md` (its dispute step is wave I).
**Ships as:** `2.143.0` (shipped 2026-09-04). **Size:** medium — about 6 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **O1** | 2a 🔒 | `GET bills/{no}/explain` in `seams/billing_seam.py` — arithmetic **over stored reads, days in period, the rate version that applied and any discount that ended**, four components summing exactly to `invoice.total − previous.total`; no comparison on a first bill; refuses if the sum does not tie (it is a **read that must never disagree with the bill** — `BR-CWP-046`; flag 🔒 rating-adjacent, review-ledger row). The high-usage alert: the message class exists in the catalogue and **nothing fires it** — a read of a seeded alert row, wording naming billing time; no trigger is built (a scope decision, recorded) | `US-CWP-035`, `044` · `BR-CWP-046`, `093` | E1–E3, G1, H1 | 2.7 · 4.6 | M |
| **O2** | 2b | `CWP-030` (T6 + `TwoEqual`; signed money — positive in brand red, zero and negative ink — `KVList`), `CWP-036` (T4; fourteen-day `ChartPanel`; the honest sentence) | two stories · B14 r32 | E5, G2, O1 | new | M |
| **O3** | 2c | `test_us_cwp_035_tc*` (TC-2 exact sum; TC-3 perturbation fails; TC-5 first bill; TC-9 rate version), `_044_tc*` (TC-2 nothing fires; TC-4 the threshold does not produce it); fixture: `BL-2607-0139 $138.44 → BL-2608-0141 $142.18` with the four components, last August `4,090 gal`, a seeded alert dated 25 Aug | two stories' §3/§4 | O1, O2 | new | M |
| **O4** | 2d | `cr068-o-why-different.mjs` — the five steps; asserts the four line strings and the heading's `$3.74`, the *cost less* variant, the absent comparison on a first bill, the billing-time sentence; screenshots | law 6 | O2, O3 | new | S |
| **O5** | doc | `J38` file; CHANGELOG + version; TSV; **review-ledger row putting the decomposition rule to finance in plain English with the figure** (`+$8.83 · $0.00 · +$4.29 · −$9.38 = +$3.74`); the `US-CWP-044` scope decision recorded and its frontmatter `wave` amended | law 9, W · HUMAN-GUIDE §6 | O4 | 4.11 (part) | S |

⚠ **AS BUILT — VERIFIED FROM THE CODE 2026-09-06 at `bc4b976e`, NOT FROM THIS TABLE.** This wave carried no stamp until now. **An unstamped row means UNKNOWN, not unbuilt** (`DEF-WRK-3933`: unstamped execution-plan rows sent two lanes onto work that had shipped days earlier), so the thirteen unstamped waves were re-decided from the router, the screen register, the endpoints and the tests — never from this table's own prose, which was the thing under suspicion. Where the two disagreed, the code won. **ONE OF THE TWO STORIES IS BUILT:** `US-CWP-035` *why is this bill different* — `CWP-030` is `/bills/:number/comparison` (`bills/BillComparison.tsx`, 390 lines), served by `bills/{number}/comparison`, and it is tested. ⚠ **THE SECOND IS NOT BUILT AND CANNOT BE, YET:** `US-CWP-044` *your usage looks high* (`CWP-036`) has no address, no endpoint and no test, and the story register marks it **no trigger exists** — the alert has nothing to fire it, which is why this is a deliberate absence rather than late work. `cr068-o-why-different.mjs` does not exist.

⚠ **AS BUILT — THE BROWSER PASS, 2026-09-06, `2.197.14`. The stamp above ends
*"`cr068-o-why-different.mjs` does not exist"*; it exists, and this is what it
found.**
`10-scripts/render-checks/cr068-o-why-different.mjs` walks the five demo steps and
finishes **0 failures, 0 gaps that have closed, 7 known gaps still open** (exit 0),
beside `cr068-o-fixture.py`.

**THE FIXTURE WAS THE WORK, AND FOR A REASON THE PLAN DID NOT ANTICIPATE.** Wave O's
own step 2 asks for a bill that went DOWN, and **there is no such bill on the
tenant**: counted over the whole of `seed_portal_demo`, 50 accounts are billed,
49 of them twice, and **all 49 comparisons went UP** (`+$3.38` to `+$56.65`).
Neither is there one that stayed level. So a walkthrough driven against the seed
could assert *cost more*, find it, pass, and never catch a screen printing a
constant — hard-won law 7's *"a check that cannot fail"*, and the exact trap wave
I's briefing warns about. The fixture chains **five bills on one account** so the
same screen is driven four times and must give four different answers.

**WHAT THE BROWSER PRINTED** — read off the screen, not off the wire:
`BL-O-2608-0141` *"This bill cost $3.74 more than last month."* · `$142.18` against
`$138.44` · four lines `+$8.83 / unchanged / −$9.38 / +$4.29` **summing to exactly
`+$3.74`** · `BL-O-2609-0143` *"cost $3.74 less"* with all four reversed, summing to
`−$3.74` · `BL-O-2610-0145` *"cost the same"*, `$0.00`, **and two components that
moved and cancelled** (`+$5.00` water, `−$5.00` tax) · `BL-O-2606-0100` *"This is
your first bill, so there is nothing to compare it with yet."* with no difference
figure anywhere · **0 raw machine dates** on any branch.

⚠ **THE LEVEL BILL IS THE ONE THAT PROVES ANYTHING.** A screen deriving its four
lines FROM the headline difference — the obvious wrong implementation — passes the
rise and the fall and draws nothing at all here. `BR-CWP-046` is checked as
arithmetic on the PRINTED strings, both sides read off the DOM, because *the
numbers on the page add up to the headline on the page* is the only version of
that rule a customer can act on.

⚠ **AND THE WHOLE RIGHT-HAND COLUMN OF THE DRAWING HAD NEVER DRAWN FOR ANYBODY
(`DEF-CWP-4206`).** `bill_comparison_for` declared `months: int = 12` and passed it
to `usage_same_month_last_year`, whose own docstring warns IN CAPITALS that August
2025 and August 2026 are **thirteen** months apart and which defaults itself to 24.
No caller overrode it, so the shipped default was the broken one and
`against_last_year` was `[]` on **every bill on every account**. It was invisible in
both directions: `LastYearPanel` returns `null` on an empty list, which is CORRECT
under `BR-CWP-093`, so the panel rendered as nothing rather than as an error; and
the one test naming `against_last_year` asserts `== []` on a first bill whose
account has no usage seeded, so it is legitimately empty there and pinned nothing.
**Measured on a live clone, same account and same bill: 1 row at 24 months, 0 at
12.** Fixed here.

**SEVEN DEFECTS, EACH FILED BEFORE IT WAS TOUCHED. TWO FIXED, FIVE OPEN.**
Fixed: `DEF-CWP-4206` (above) and `DEF-CWP-4207` — the screen's Trace header, the
screen's own docstring and the endpoint's docstring **all still described the
four-line breakdown as unsigned and undrawn**, five days after the PO closed
`OQ-CWP-1563`/`OQ-CWP-1569` with *"(a) list every reason with its share"* and the
panel started drawing. That is the status-versus-body lesson (`DEF-WRK-4030`) in
CODE rather than in a register: `DEF-CWP-3968` edited the boolean and the comment
beside the branch and left the prose, which is what a lane actually reads.
Open, and all five came from the wireframe pass: `DEF-CWP-4209` (both bars of the
year chart read `Aug`, so this August and last August are indistinguishable) ·
`DEF-CWP-4210` (a component that ROSE is painted ink where task O2 and the drawing
both say brand red — measured, `rgb(45, 43, 43)` against the headline's
`rgb(236, 48, 19)`) · `DEF-CWP-4211` (the H1 is the generic question where the
drawing makes the ANSWER the heading) · `DEF-CWP-4212` (nothing on the screen or in
the payload says whether the RATE moved) · `DEF-CWP-4213` (the drawing's *Send a
reading* and *Query this bill* are absent, **and both destinations shipped in waves
J and I**). `DEF-CWP-4168` is carried as a gap rather than refiled — its own surface
is *"every consumer of `quantity_text`"*, and this panel reading `4171 gal` instead
of `4,171 gal` is that defect seen from a second screen.

⚠ **`US-CWP-044` IS STILL NOT BUILT AND THAT IS THE RECORDED ANSWER, NOT AN
OMISSION.** The walkthrough opened the drawing's own URL (`/alerts/high-usage`) and
two others; **none serves `CWP-036`**, and the account's `attention` list carries one
row, `{"kind": "pay"}`, and no usage alert of any kind (`US-CWP-044` TC-2/TC-4). Its
wireframe is stamped **BLOCKED** and carries its own panel saying the alert has no
trigger, which is why it is one of the four screens `unbuiltScreens.ts` deliberately
excludes from its ten — **that absence is correct and is not a gap in the register.**
The reason it cannot simply be finished: firing it needs a daily or weekly comparison
against the account's own history, and these utilities read monthly, so on this
product it could only ever fire at billing time — which is not the warning the
drawing describes.

**Wireframe comparison appended to `13-wireframe-delta.md` as the fifth pass** —
`CWP-030` (sixteen rows) and `CWP-036` (one-sided). That file now carries **40
distinct screens**, counted from its `##` headings rather than carried forward,
because its own header records that its running total has drifted every time it was
maintained by hand. **`CWP-030` and `CWP-036` were the last two portal screens with
no row in it.**
---

## 6 · PHASE 5 — LAUNCH: customers can pay

**Launch sentence:** `CR-068` §12 Phase 5, kept verbatim in §1. Ruled 2026-09-02 as a
later stage (`R2`); every Pay control has been visible and disabled since Phase 2, so this
phase **turns on a control people have already seen**.
**Stands on:** **W7 payment rails**, which arrive through `CR-069`'s integration substrate
(gateway adapter, tokenisation, the signed webhook). **This phase cannot start until that
work has landed** — the plan names the dependency and does not schedule around it. Also W6
(receipts by email).
**Stories (10):** `US-CWP-003`–`006`, `022`, `045`–`047`, `049`, `050`.
⚠ **Before any migration here:** resolve the `payment_methods` name collision
(`apps/payments/models.py:55-80`) — a migration that discovers it at `makemigrations`
time has already picked, badly. **And `OQ-1394`** (who pays the card fee) is regulated in
some states: until ruled **no fee line is drawn** and the computation raises.
**Order:** **P** first; **Q and R run in parallel** after P.

### Wave P — *Rails and the webhook* · `CP-08` · `CP-09`

**Goal a person can see:** a card is tokenised in the sandbox and listed as *Visa ••••8812 ·
expires 11/27* with never a full number anywhere; the gateway's replayed settlement leaves
**one** payment on PostgreSQL; adding or removing a method needs a fresh code.
**Stories:** `US-CWP-006` · `US-CWP-046` (⚠ `OQ-1394`) · `US-CWP-022`
**Demo script:**
1. **Verify first** (`CR-068` §0c): open `apps/payments/webhooks.py` (577 lines) and `tests/test_cr060_c21_webhooks.py` (15 tests); run them; record what `CP-09` already does — signature verification, the composed idempotency key, the two guards — and what remains (the gateway half; `CR-069` R-8 q4 on how the body is signed, answered only *"there will be some code"* — confirmed before trusting `payments.webhook_key`).
2. **Your payment methods** (`CWP-039`): add a card through the sandbox with a **fresh code** (step-up, `CWP-017`'s mechanism) → *Visa ••••8812 · card · expires 11/27 · ACTIVE*; the stored row holds a token, a brand and four digits — **no column holds more than four digits of a card** (asserted).
3. Add a method **without** a code → refused at the endpoint; reuse the sign-in code from ten minutes earlier → refused (step-up needs its own).
4. Send settlement `STL-2609-0031` for `$142.18` against `BL-2608-0141` with key `pay_26_08841`; send **the identical body again** → still **one** payment row; `CWP-041` shows one row. Send the two **concurrently** → one row, by the unique constraint.
5. **On PostgreSQL** (`DJANGO_SETTINGS_MODULE=config.settings.local`): a batch where row 2 of 3 violates a constraint → rows 1 and 3 commit, row 2 is reported — the savepoint proof (law 14).
6. A reversal `STL-2609-0032` carrying the same `pay_26_08841` with the reversal flag → **two** rows, the payment and the reversal above it — not mistaken for a duplicate.
7. An account marked **cash-only**: autopay disabled with *we cannot take card or bank payments on this account* **on it**; two bounces: the reason names the bounces. Any card-fee computation → `NotImplementedError("OQ-1394")`; no fee line drawn.
**Exit test:** `BR-CWP-057` — token, brand, last four and nothing else · `BR-CWP-040` — step-up with its own code · `BR-CWP-059`/hard rule 6 — one row after the replay, proved concurrently and on PostgreSQL · `BR-CWP-061` — the reversal is its own row · `BR-CWP-056` — every refused control carries its reason · `OQ-1394` — the raise, no fee line.
**Depends on:** E (step-up code mechanism), G (`CWP-039`/`041` layouts), **`CR-069`'s rails**. **Blocked by:** `OQ-1394` (boundary, step 7); the webhook signing answer.
**Walkthrough:** `cr068-p-rails-and-webhook.mjs` · **Journeys written:** none new (`J30` is R).
**Ships as:** a version allocated AT SHIP TIME with `10-scripts/allocate.py version --bump change` — this read `nominal 2.144.0` until 2026-09-04, when 2.144.0 was taken by the ruling batch. `DEF-GOV-3759` was two waves claiming one number; a number written down weeks early is the same bug with a longer fuse. **Size:** large — about 10 lane-days (two people; the 🔒 set is the whole wave).

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **P1** | ground | **Resolve the `payment_methods` name collision** — the tender lookup keeps or yields the name; recorded in the decision log with the two options and the one chosen **before** any migration (`apps/payments/models.py:55-80`) | `CR-068` §11b | — | 5.1 (first clause) | S |
| **P2** | 2a 🔒 | **Verify `CP-09`**: `webhooks.py` + its 15 tests; what remains built on the gateway half only. `payment_method` (stored instrument) in **`apps/payments`** — `gateway_token`, `brand`, `last_four`, `kind`, `status`, `used_for`; `*rls*` migration (🔒); `GET/POST/DELETE payment-methods` with **step-up** (a fresh one-time code — `BR-CWP-040`); `payment.portal_credential_id` (`03-field-map.md` §3 row 7). Webhook replay proved **concurrently** (unique constraint) and **on PostgreSQL with a savepoint** (law 14 — the comment says why). Card-fee computation raises `NotImplementedError("OQ-1394")`. Refusal reasons for cash-only and bounce-count accounts served as codes with catalogue sentences | `US-CWP-006`, `046`, `022` · `BR-CWP-040`, `056`, `057`, `059`, `061` · hard rules 4, 6, 7 | P1, E1, `CR-069` rails | 5.1 · 5.2 · 5.7 · 5.8 | L |
| **P3** | 2b | `CWP-039` goes **live** (from G2's held layout): add/remove with the step-up code screen (`CWP-017` reused), the *we never hold your full card number* note; refused controls with their reasons; `CWP-040`'s *Turn autopay on* stays held until Q | `US-CWP-046`, `022` · B14 r15, r33 | G2, P2 | 5.7 · 5.8 | M |
| **P4** | 2c | `test_us_cwp_006_tc*` (TC-2 replay; TC-3 concurrent; **TC-5 on PostgreSQL**; TC-7 reversal), `_046_tc*` (TC-2 no column > 4 digits; TC-9 the raise), `_022_tc*` (TC-3 the session's code is refused); fixture: the sandbox card `Visa ••••8812 11/27`, bank `Chase ••••4021 VERIFIED`, `STL-2609-0031/0032`, a cash-only account, a two-bounce account | three stories' §3/§4 · law 14 | P2, P3 | 5.10 (part) | M |
| **P5** | 2d | `cr068-p-rails-and-webhook.mjs` — steps 2–4 and 7 in the browser, 5–6 through the API against the local-settings PostgreSQL; asserts the masked method string, the refused-without-code sentence, one row after replay, the cash-only reason text, no fee line in the DOM; screenshots. RED proof: remove the unique constraint in a worktree and show TC-3 fail | law 6, 7, 14 | P3, P4 | 5.10 (part) | M |
| **P6** | doc | CHANGELOG + version; TSV; review-ledger rows for `payment_method`'s RLS migration and the webhook/gateway changes **in plain English with a figure** (*the same `$142.18` settlement arriving twice leaves one payment*); the collision decision; the `OQ-1394` boundary | law 9, W · `g07` | P5 | 5.10 (part) | S |

⚠ **AS BUILT — 2026-09-05, `2.165.0`.** All three phase-5 waves shipped in ONE
version rather than the nominal `2.145.0` and `2.146.0` below: they landed in
one afternoon across four parallel lanes, and three versions for one release
would have told a reader looking at a screen three different things. Where this
table and the code disagreed, the code won and the register says so.

**P1 — the collision was resolved the other way round from the way the table
reads.** `B2` §2 spells the customer's stored instrument `payment_methods`, and
that name was already taken by the tender lookup (`apps/tenancy/models.py:985`
— cash, cheque, card, bank transfer) which `Payment.method` points at on every
payment row in the product. **The lookup keeps the name; the new table is
`stored_payment_instruments`.** Renaming the lookup was the tidier reading of
the spec and it moves a foreign key on a money table across every existing
`payments` row to win a word. `B2` §2 is stamped with the divergence rather than
followed. ⚠ And the name is not `customer_payment_methods`, which would have
left two tables a reader has to hold apart by their prefix.

**P2 — the RLS policy is IN `payments/0024_cr068_p2_stored_payment_instrument.py`,
not a separate `*rls*` migration.** One table, created and secured in one step,
so there is no window in the migration order where the table exists unprotected.

**P2 — `OQ-1394`'s boundary is GONE, and the table above is superseded on it.**
The plan says *any card-fee computation → `NotImplementedError("OQ-1394")`*.
That question **CLOSED on 2026-09-04, the day before this wave ran** — not (a)
and not (b) but BOTH, behind a per-tenant switch (PO: *"we have to give both the
options … create a flag somewhere to on and off it"*). So there is no raise.
Beta ships ABSORBED and `guest_api._no_surcharge_is_lawful_here()` REFUSES a
tenant who has surcharging on, because the PO's answer obliges a fee that is
computed, disclosed before the commit and checked against the customer's state,
and none of the three is possible without a real processor. ⚠ `DEF-GOV-3929` was
filed the same day for putting that question back to the PO after it was ruled.

**P2 — a SEVENTH portal write point, and `G81` was green over it before the row
existed.** `stored_instrument` is neither `payment` (money moving; a customer
saves a card without paying anything) nor a companion of it (`CWP-039` is a door
somebody walks through on its own). G81 refuses ORM writes inside `apps/portal/`
and imports of another module's `…services`; the owning module is called
`instruments`, so neither rule bit. The lane said so in its own docstring rather
than banking the green.

**P2 — payment providers turned out to be INTEGRATIONS, and there are five of
them.** Not in this table at all: PO ruling 2026-09-05, *"We have invoiceCloud,
Worldpay, US payments, Global Payments, spruse"*. Each is a provider manifest,
`coming_soon` until its adapter is written; beta runs against `payments_sandbox`.

⚠ **P5 — DONE 2026-09-06. `cr068-p-rails-and-webhook.mjs` EXISTS AND RUNS
GREEN at 33 assertions, 10 of them about the webhook, with 1 known gap named.**
This paragraph read *"NOT BUILT … and neither does `cr068-q-…` or `cr068-r-…`"*
until now; all three exist today.

⚠ **AND *GREEN AT 33* IS NOT REPRODUCIBLE — IT DEPENDS ON THE CLOCK
(`DEF-CWP-4208`, found 2026-09-06 by re-running this walkthrough while
rescuing this lane's own close-the-record work).** Re-run at the branch tip it
prints **33 assertions, 10 of them about the webhook**, and the whole
idempotency table above comes out line for line — `accepted 1→2`,
`duplicate 2→2`, the same money under a new id `accepted 2→3`, a forged
signature and an unconfigured provider both refused, two concurrent deliveries
`3→4`, and the savepoint holding on PostgreSQL. **Nothing in the product
misbehaves.** What fails is one assertion: `BR-CWP-057`'s check for a run of
five or more digits is taken over the DOM *and* over the stringified served
body, and the served body carries each saved method's `ref` — **a UUIDv7 whose
leading hex is a TIMESTAMP.** Both instruments minted in one millisecond window
began `01a07512-`, so the pattern found `07512` twice in a body holding no card
digits at all. The DOM arm passed, correctly, because `ref` is never drawn.
**So the stamp above records what this lane's run truly printed, and a later
run is red for reasons that have nothing to do with the product.** It is the
SECOND occurrence of one pattern: `DEF-CWP-4033` was `not.toContain("123")`
over a body carrying a `crypto.randomUUID()`, on this same rule and this same
guest payment path, and its prevention already says it — **assert on the thing
the rule is about, not over the whole envelope.** That fix was applied to the
file that failed rather than to the pattern, which is why the walkthrough
written the next day repeated it.

**THE IDEMPOTENCY ANSWER, WITH THE NUMBERS, because hard rule 6 is this wave's
headline promise and a claim without a count is not a proof.** Five deliveries
at the mounted endpoint against a live PostgreSQL, each printed with the payment
row count either side:

| what was sent | answered | payment rows |
|---|---|---|
| one signed settlement, a new event id | `accepted` | 1 → 2 |
| the SAME event id, byte-identical | `duplicate` | 2 → 2 |
| the SAME money, a DIFFERENT event id | `accepted` | 2 → 3 |
| a forged signature | `refused` `signature_did_not_verify` | 3 → 3 |
| a provider with no configured secret | `refused` `no_signing_secret_configured` | 3 → 3 |
| two identical deliveries CONCURRENTLY | `accepted` + `duplicate` | 3 → 4 |

**The third line is the control and the wave is not proved without it.** *"I
sent it twice and no second row appeared"* is equally true of an endpoint that
is inert, throttled, unmounted or refusing everything, so line three re-sends
the same money under a new id and REQUIRES a second row. Line six is the race
guard 1's pre-insert SELECT cannot close and only `uq_payment_webhook_events_
event` can — asserted separately because `DEF-058` is what happens when one
guard silently stands in for another. Proved independently of wave Q rather than
by citing it.

**Demo-script step 5 — THE SAVEPOINT — is proved on PostgreSQL** (law 14): a
delivery whose PAYMENT was refused by a rule still committed its delivery row
(`created: true`) and wrote no payment. The suite runs on SQLite, which has no
aborted-transaction state, so the version without the nested
`transaction.atomic()` passes every test on every machine.

⚠ **DEMO-SCRIPT STEP 6 IS SUPERSEDED AND THE TABLE ABOVE IS WRONG ON IT.** Step
6 asks for a reversal to produce *"two rows, the payment and the reversal above
it — not mistaken for a duplicate"*. **It is not mistaken for a duplicate; it is
mistaken for a PAYMENT, which is worse.** A correctly-signed `charge.reversed`
for `25.00` was ACCEPTED and wrote a positive `25.00` payment row: `event_type`
is stored on the delivery row and branched on nowhere, and `CHARGE_SETTLED` is
compared against nothing on the inbound path. `DEF-PAY-4189`, and the
walkthrough carries it as a known gap that goes RED the day the branch lands.

⚠ **AND THE WHOLE STEP CANNOT RUN ON A STOCK SERVER AT ALL — `DEF-PAY-4188`.**
`signing_secret` reads `settings.PAYMENT_WEBHOOK_SECRETS`, and the word WEBHOOK
appears nowhere in `config/settings/` or in `.env.example`; there is no
`env.dict`/`env.json` reader in the settings package. So **every delivery on
every deployment is refused `no_signing_secret_configured`** and the guard this
wave exists for has never run outside a unit test. The empty default is CORRECT
and signed (decision log 2026-09-03, hard-won law 3); what is missing is the way
to type it. The walkthrough takes `SMOKE_WEBHOOK_SECRET` and SKIPS LOUDLY with
the count of assertions that did not run, and its header shows the scratchpad
settings shim to run them with — **no repo file is edited to make a proof pass.**

**P5 also found `DEF-CWP-4197` on `CWP-039`:** the ADDED column printed
`2026-09-06` where the drawing reads *4 Mar 2026*. Fixed with the published
`usePortalDate()`. See `13-wireframe-delta.md` rows 39.7–39.9, and row 39.2 is
CONFIRMED RESOLVED by photograph rather than inferred from a commit.

**P6 — done here**: `2.165.0` across all four version literals, with a changelog
entry written for a person.

### Wave Q — *Pay now, autopay, refunds and fees* · the signed-in half of `CP-08`

**Goal a person can see:** Maria pays `$142.18`, sees **which bill it lands on before she
commits**, and `CWP-041` reads *Cleared* the same minute; autopay executes the intent that
was written when the bill issued; a refund goes back *to the card ending 8812*; an
applicant pays `$335.00` and the deposit still waits for the first bill.
**Stories:** `US-CWP-045` · `US-CWP-047` · `US-CWP-049` · `US-CWP-050`
**Demo script:**
1. **Pay now** (`CWP-038`): *the whole balance* `$142.18` → the *where it will go* panel names `BL-2608-0141`; the `ConsequenceBox` — *takes `$142.18` from Chase `••••4021` · clears the August bill in full · emails you a receipt*; **Pay `$142.18` ✓** → one payment row allocated to that bill, one audit entry naming **Maria Alvarez**, one receipt; `CWP-041` shows *Cleared*.
2. *Another amount* `$40.00` against two open bills → the panel shows **oldest first, by the tenant's rule** before the commit; afterwards the older bill reads owing `$102.18`.
3. Make the sandbox gateway **time out**: the screen says so and **no payment row is written**; retry → the **same** idempotency key generated before the first request left; the debit is never taken twice.
4. **Autopay** (`CWP-040`): *Turn autopay on* goes live — always the due date, a ceiling optional; the *next few* table `14 Sep 2026 · $142.18 · SCHEDULED`, `14 Oct · — · NOT BILLED YET`; correct the bill after the intent was written → the intent **still carries the amount the customer was told**; a ceiling of `$200.00` against `$240.00` → the utility rings, and the screen says so; two bounces → autopay stops and says why.
5. **Refunds** (`CWP-045`): money that came in by card → *Sent · 21 Sep · to the card ending 8812*; by cheque → `#10241` and the address; an expired card → falls back to a cheque **and the timeline says so**; a voided refund stays on the timeline.
6. **Fees to pay** (`CWP-050`) for an approved application: `$185.00` + `$150.00` = **`$335.00`** to pay now; the security deposit `$150.00` *on your first bill*; account set-up `$25.00` **waived, struck through, still listed**; pay `$335.00` → the request leaves *fees due* and the deposit still shows as due on the first bill. A partial amount is refused.
7. A delegate with Pay permission pays → the audit entry names **the delegate**.
**Exit test:** `BR-CWP-058` — where it lands, shown before the commit; the row cannot be edited afterwards · hard rule 4/7 — one immutable row, one audit entry with a named actor · `US-CWP-045` TC-6/7 — timeout writes nothing; retry reuses the key · `BR-CWP-060` — refund to the original method, the fallback stated · `US-CWP-050` TC-2 — `$335.00` now, `$150.00` on the first bill, `$25.00` in neither · `US-CWP-047` TC-4 — the intent keeps the amount the customer was told.
**Depends on:** P. **Blocked by:** nothing once P lands. **Runs in parallel with:** R.
**Walkthrough:** `cr068-q-pay-now-autopay-refunds.mjs` · **Journeys written:** `J40` activates (its refund step); `J32`'s fee step completes.
**Ships as:** nominal `2.145.0`. **Size:** large — about 9 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **Q1** | 2a 🔒 | `POST accounts/{id}/payments` — **write point one**: the allocation preview (the tenant's rule through `payments/allocation.py`, 🔒), the idempotency key minted before the gateway call, **no row on an unknown outcome**, one payment + receipt (`payments/receipts.py:387`) + audit with the portal actor; `PUT accounts/{id}/autopay` — enrolment over `payments/autopay.py` and the existing `AutopayCaptureIntent`, execution through the rails, ceiling → ring, two bounces → stop; refunds to the original method through `payments/refunds.py` with the expired-card fallback **stated**; `POST requests/{ref}/fees/pay` for `$335.00` in full, the deposit left for the first bill, the waiver kept | `US-CWP-045`, `047`, `049`, `050` · `BR-CWP-056`, `058`–`060` · hard rules 4, 6, 7 | P2 | 5.3 · 5.5 · 5.6 | L |
| **Q2** | 2b | `CWP-038` goes live (T2; *where it will go* `MiniTable`; `ConsequenceBox`; step three a confirmation the customer can screenshot), `CWP-040` live (T4), `CWP-045` refund timeline (`ChecklistTimeline`), `CWP-050` (T6 + `TwoCol`; struck-through waived row). Every Pay control across the shell flips from held to live **in one place** | four stories · B14 r4, r11 | G2, P3, Q1 | 5.3 (screens) | L |
| **Q3** | 2c | `test_us_cwp_045_tc*` (TC-4/5 oldest first; TC-6 timeout writes nothing; TC-7 same key; TC-10 delegate actor), `_047_tc*` (TC-4 intent keeps the told amount; TC-9 ceiling), `_049_tc*` (TC-3 fallback stated), `_050_tc*` (TC-2 arithmetic; TC-4 deposit not taken); fixture: two open bills, the sandbox timeout switch, an expired card, the approved application with four fees | four stories' §3/§4 | Q1, Q2 | 5.10 (part) | M |
| **Q4** | 2d | `cr068-q-pay-now-autopay-refunds.mjs` — the seven steps; asserts the *where it will go* bill number before the click, *Cleared* after, zero rows after the timeout (via the API), the intent's unchanged amount, *to the card ending 8812*, `$335.00`, the struck-through `$25.00`; screenshots | law 6 | Q2, Q3 | 5.10 (part) | M |
| **Q5** | doc | `J40` activation; CHANGELOG + version; TSV; review-ledger rows for the write point and the allocation seam **in plain English with the figure** (*`$40.00` lands on the older bill and that bill then owes `$102.18`*) | law 9, W · `g07` | Q4 | 5.10 (part) | S |

⚠ **AS BUILT — 2026-09-05, `2.165.0`.** Where this table and the code disagreed,
the code won and the register says so. **Two of the six demo-script steps did not
go live, and both are the honest outcome rather than a shortfall.**

**Q1/Q2 — *Turn autopay on* is STILL HELD, and step 4 above overstates what
shipped.** The screen is live and reads a customer's position — the amount, the
ceiling, the bounce count, why it is refused — but the switch is disabled on
`no_automatic_charge`. A charging path exists (`payments/gateway.py` landed the
same day); **what does not exist is anything that DRAFTS a payment without a
person pressing a button.** Nothing consumes `AutopayCaptureIntent`, which is
`BR-PAY-015`'s whole shape. ⚠ The reason was `no_rails` for one afternoon and
that wording went FALSE the moment the gateway landed — caught by the
hold-expiry test hard-won law 2 asks for, which went red and named the control.

**Q1/Q2 — *Pay `$335.00`* on `CWP-050` is STILL HELD**, on `no_fee_payment_path`,
and step 6 above overstates it the same way. The figures are right and the
arithmetic is right; what is missing is a path. A fee is a `service_request_fees`
QUOTE that never posts to the ledger, `collect_fee` is a counter action gated to
Admin or Billing Clerk, and `write_points.py`'s `payment` row still carries
`function=None` for it — the product's own statement that the portal writes no
payment here.

**Q1 — `to_pay_now` is the OUTSTANDING figure, not the quoted one.** On this
wave's fixture the two agree at `$335.00`; they diverge the moment a clerk takes
`$100` at the counter and the honest answer is then `$235.00`. TC-4's *"the
request moves out of fees due"* therefore falls out of `BR-CUS-090`'s existing
arithmetic instead of a second sum on this screen. **The deposit is in neither
total** — `$150.00` is not a fee line and settling the fees leaves it exactly
where it was.

**Q1 — a card refund goes back BY CHEQUE, and the screen says why.** Step 5
above reads *to the card ending 8812*; what ships is *the money came in on the
card ending 8812; we have sent cheque 10241 instead*, because we cannot return
money to a card yet. A dead card outranks absent rails (the reason that survives
W7 is the one the customer is given), and a refund with no source payment reads
`several_sources` rather than `unknown` — since `OQ-195` a null `payment_id`
means the credit came from more than one payment, so its absence is a FACT.
⚠ The four digits are named only where the customer holds EXACTLY ONE card:
instruments belong to the customer, a landlord holds three, and naming the
oldest would put specific digits on a refund we cannot prove the money came
from.

**Q1 — autopay is refused for the whole ACCOUNT SET when any one account is
cash-only**, conservatively and with the reason named, because a card enrolled
at the set level could otherwise be charged for an account the utility excluded.
A per-account election is this screen's own future work. Where the block list
cannot be read at all it refuses CLOSED (law 3).

**Q3 — `US-CWP-046` TC-9 AMENDED, and TC-8 / `US-CWP-022` TC-5 / TC-7
DEFERRED.** TC-9 was written to prove the `OQ-1394` raise and that question was
already closed, so it asserts the absent fee line and the refusal instead. The
three delegate cases are deferred by `OQ-1396` (PO 2026-09-04: *"we are not
giveing this acces as of now"*) and **assert the ABSENCE rather than skipping** —
a `@skip` proves nothing in either direction, while an asserted absence goes red
the day somebody builds delegate access without reopening the question.

⚠ **Q4 — BUILT AND RUN, 2026-09-06, `2.197.7`.** This note read *"NOT BUILT.
See wave R"* until the walkthrough was written; the sentence is replaced by what
it PRINTED. `10-scripts/render-checks/cr068-q-pay-now-autopay-refunds.mjs`,
**GREEN at 77 assertions with 2 known gaps named**, plus
`cr068-q-fixture.py` — which is the half that matters.

**The fixture, because a run without it proves almost nothing.**
`seed_portal_demo` leaves the tenant with **no saved instruments and no payments
provider**, so every Pay control is held, `CWP-045` says nothing is coming back
and `CWP-050` says nothing to pay. That run is GREEN and exercises the one state
where these screens have no work to do — `DEF-WRK-4121`'s exact shape. So step 0
asserts the state on the WIRE before a screen opens and STOPS the run when it is
absent. ⚠ **And the walkthrough consumes its own fixture: it PAYS**, settling
both open bills, so a second run halts at step 0 saying the account owes `$0.00`.
The seeded estate holds very few accounts with two open bills; snapshot the
database after the fixture and clone per run.

**The figures it printed, on `AC-2026-00004`:** the *where it will go* panel
named `BL-2607-000004` — the oldest open bill — **before anything was pressed**;
`$40.00` landed on that bill alone and the screen stated it would owe `$419.31`
afterwards, which is the figure `allocate_payment` returned rather than a
subtraction done in the browser; `Pay $957.07 ✓` wrote **one** payment row
(`PY-260906-0084`), one receipt and one audit entry, and `CWP-041` read *Cleared*
the same minute; the sandbox switched to `timeout` wrote **no row at all**
(2 → 2) and the retry presented the key the first attempt minted; `$185.00` +
`$150.00` = **`$335.00`** to pay now with `$25.00` struck through
(`text-decoration-line: line-through`, read from the browser) and in neither
total; the refund read *the money came in on the card ending 8812, cheque 10241
sent instead*.

⚠ **HARD RULE 6, PUT UNDER LOAD RATHER THAN ASSERTED — AND THE CONTROL IS THE
POINT.** Four deliveries: one signed settlement `accepted` (2 → 3 rows); the
SAME event id `duplicate` (3 → 3); **the same money under a DIFFERENT event id
`accepted` (3 → 4)**; a forged signature `refused` (4 → 4). The third is why the
second means anything — an endpoint that is inert or refusing everything also
writes no second row. **I could not make a webhook apply twice.**
⚠ **Getting there found that on every server in this repository the webhook
refuses every delivery**: `signing_secret` reads
`settings.PAYMENT_WEBHOOK_SECRETS` and **nothing in `config/settings/` sets it**
— it exists only inside `override_settings` in pytest. Absent means refuse,
which is law 3 and is right; the consequence is that this guard had never run
outside a unit test. The step takes `SMOKE_WEBHOOK_SECRET` and skips LOUDLY,
naming how many assertions did not run, without it.

**Six defects the run found, all filed before any was fixed** —
`DEF-CWP-4131` (a machine instant, `2026-08-28T02:08:26.806734+00:00`, on a
customer's screen) · `DEF-CWP-4132` (*A refund on its way* over a CANCELLED
refund, which the DOM test asserted and passed) · `DEF-CWP-4133` (a 667px
control where a 175px one belongs — `DEF-CWP-3973`'s fault, unfixed one screen
over) · `DEF-PAY-4134` (five files call the payment reference *the PMT- number*;
the seeded default series is `PY-`) · `DEF-CWP-4135` (`def-cwp-3965-fixture.py`
reads every tenant's accounts) · `DEF-CWP-4136` (a chromium fallback that can
never fire). The first three are FIXED here; `DEF-CWP-4142` and `DEF-CWP-4149`
came out of the same pass on the holds register and its gate.

**Two signed cases this wave cannot reach on any running tenant**, recorded as
KNOWN GAPS so they print on every pass and go RED the day either closes:
`DEF-PAY-4177` (nothing writes an `AutopayCaptureIntent`, because
`apps/billing/issue.py` never calls `record_intent_at_issue` — so `US-CWP-047`
TC-4 is unprovable in a browser) and `DEF-CWP-4176` (the seeded plan prices no
residential deposit, so `US-CWP-050` TC-4's `$150.00 on your first bill` has
never been drawn).

**The wireframe comparison is in `13-wireframe-delta.md`** — `CWP-050` opened for
the first time by anybody, and rows `40.2` and `38.11` corrected inline.

**Q5 — `J40` was NOT activated by this wave.** The journey file exists
(`J40-move-out-final-bill-refund.md`) and the index counts 53 activated
journeys, unchanged. CHANGELOG and version are done at `2.165.0`.

### Wave R — *Quick pay for a guest* · `J30`

**Goal a person can see:** somebody holding a paper bill and no account pays it in three
steps, sees `M. A••••••` and nothing else about who lives there, gets `PAY-26-08841` and a
receipt, and is **offered** a login rather than made to create one.
**Stories:** `US-CWP-003` · `US-CWP-004` (⚠ `OQ-1394`) · `US-CWP-005`
**Demo script** (`BL-2608-0141` + `78702`; receipt to `d.okafor@example.com` — a neighbour, deliberately not the customer):
1. `/pine-hill/portal` → *Pay a bill →* (`CWP-002`): `BL-2608-0141` + `78702` → step 2 opens with `$142.18` owing. The wrong postcode and a non-existent bill number are refused **byte-identically**.
2. **Check and pay** (`CWP-003`): *Billed to **`M. A••••••`*** — the response body carries **no other field** of the customer record; a one-letter surname masks fixed-width. Card fields, the optional email, the `ConsequenceBox`. **Pay `$142.18` ✓** → one payment row allocated by the tenant's rule, one audit entry naming the **guest channel**, one receipt, **no account created**.
3. **Paid** (`CWP-004`): `PAY-26-08841`, 9:47am, against `BL-2608-0141`, *Card ending 8812*; *↓ Receipt* works **without** an email; *Email it to me* prompts for one. The enrolment offer routes to `CWP-017` and **does not skip the code**; decline it and reload — the receipt is still reachable by reference and **no credential row exists**.
4. A **paid** bill `BL-2607-0139` opens showing `$0.00` owing and **no Pay control** (not a refusal); a **corrected** bill `BL-2606-0137` reads *replaced by BL-2606-0147* and directs payment there; a voided bill reads *cancelled*.
5. Six wrong pairs from one address → *locked for fifteen minutes* — **independently** of the track lock (`US-CWP-002` re-verified on quick pay).
6. `PAY-26-08841` + `78702` on *Track anything* → status and date, **not the amount**.
7. The card-fee line: **absent**; the computation raises `NotImplementedError("OQ-1394")`.
8. Stamp `CR-059` rows 68, 70, 71, 72, 73 `SUPERSEDED BY CR-068` **in this wave's commit** — not before, because until quick pay is live `CR-059`'s statement is still true (`CR-068` §2a).
**Exit test:** `BR-CWP-018`–`021` — amount and status, a masked name, never a person; the body asserted · `BR-CWP-023` — the lock, per form · `BR-CWP-028` — a reference to keep, offered by email, lookup-able · `BR-CWP-029`/`PR-21` — the login offered last and never created silently · `BR-CWP-042` — the corrected bill directs payment at its replacement · `G77` green on the guest serialisers.
**Depends on:** P, B (the lock mechanism), E (`CWP-017` for the offer). **Blocked by:** `OQ-1394` (boundary, step 7). **Runs in parallel with:** Q.
**Walkthrough:** `cr068-r-quick-pay.mjs` · **Journeys written:** `J30-guest-pays-a-bill.md` (+ spec).
**Ships as:** nominal `2.146.0`. **Size:** medium — about 6 lane-days.

| Task | Part | What it touches — verified | Stories · rules | depends_on | §12 | Size |
|---|---|---|---|---|---|---|
| **R1** | 2a 🔒 | `POST /public/bills/lookup` (bill number + **service** postcode → amount owing, status, **server-side masked name** `M. A••••••` fixed-width; byte-identical refusals; paid → `$0.00` and no Pay; corrected → the replacement; the B2 lock from B2's cache), `POST /public/bills/{ref}/pay` — **the guest write point**: the tenant's allocation, the guest channel in the audit, the receipt document, `payment.receipt_email`, **no account and no credential**; `GET`/email of the receipt by reference; fee computation raises `NotImplementedError("OQ-1394")`. `G77`'s allow-list covers the new guest fields | `US-CWP-003`, `004`, `005` · `BR-CWP-018`–`021`, `023`, `028`, `029`, `058` | P2, B2 | 5.4 · 5.3 (guest half) | M |
| **R2** | 2b | `CWP-002` (T2; *Continue →* live), `CWP-003` (T2; `KVList` with the masked *Billed to*; `TotalRow` `$142.18`; the `Panel` *WHY SO LITTLE IS SHOWN*), `CWP-004` (T2 two cards; the enrolment offer card with the brand left rule; *Set up a login →* live, routing to `CWP-017`) | three stories · B14 r11 | A6, E5, R1 | 5.4 (screens) | M |
| **R3** | 2c | `test_us_cwp_003_tc*` (TC-2/3 byte identity; TC-4 paid; TC-7 corrected), `_004_tc*` (TC-1 body has no other field; TC-4 fixed-width mask; TC-6 no account created; TC-7 timeout writes nothing), `_005_tc*` (TC-3 no credential row; TC-4 no code skipped), and `_002_tc*` TC-3/4 re-run on quick pay; fixture: `d.okafor@example.com`, the one-letter surname *M. O* | three stories' §3/§4 | R1, R2 | 5.10 (part) | M |
| **R4** | 2d | `cr068-r-quick-pay.mjs` — the seven screen steps; asserts `M. A••••••` and the body's field set via `page.request`, `$142.18` twice, `PAY-26-08841`, the receipt download without an email, the absent Pay on a paid bill, the lock sentence, no fee line; screenshots | law 6 | R2, R3 | 5.10 (part) | M |
| **R5** | doc | `J30` file + spec; **`CR-059` rows 68, 70, 71, 72, 73 stamped `SUPERSEDED BY CR-068`**; CHANGELOG + version; TSV; review-ledger row for the guest write point in plain English (*a stranger holding the bill can pay `$142.18` and learn nothing but `M. A••••••`*); the `OQ-1394` boundary; **`CR-068` closes** when this and Q have landed (§15: not before phase 5) | law 9, W · `g07` · `CR-068` §2a, §15 | R4 | 5.9 · 5.10 | S |

⚠ **AS BUILT — 2026-09-05, `2.165.0`.** Where this table and the code disagreed,
the code won and the register says so.

**R1 — the guest edge shipped as described**, and the parts worth confirming
because they are the ones a mistake would be expensive in: the response body
carries a server-side masked name and no other field of the customer record; a
wrong postcode and a non-existent bill number are refused byte-identically; a
paid bill answers `$0.00` with no Pay control rather than a refusal; a corrected
bill directs payment at its replacement; no account and no credential row is
created.

**R1 — `OQ-1394`'s raise is GONE here too.** Step 7 above says *the computation
raises `NotImplementedError("OQ-1394")`*. The question closed on 2026-09-04, so
what ships is `_no_surcharge_is_lawful_here()` — a guard, not a calculation. No
fee line is drawn; a tenant with surcharging switched on is refused BY NAME. The
distinction is the ruling: the surcharged path obliges a computed fee, disclosed
before the commit, checked against the customer's state, and beta has no
processor that could do any of it.

**R5 — the journey file is `J30-guest-quick-pay.md`, not `J30-guest-pays-a-bill.md`.**

⚠ **R4 — DONE 2026-09-06. `cr068-r-quick-pay.mjs` EXISTS AND RUNS GREEN at 70
assertions with 1 known gap named.** `CWP-002`, `CWP-003` and `CWP-004` have
been opened, and compared against their drawings (`13-wireframe-delta.md`,
fourth pass).

**THE MONEY, PRINTED.** A guest holding a paper bill and no account paid
`BL-2608-000057` for `$303.30` and got `PY-260906-0107`. Hard rule 2 is visible
on the wire at the one place a guest sees both halves of it: the served body
carries `303.3000` — FOUR decimals — beside `$303.30` — TWO — with `USD` as a
`CHAR(3)` code. The *what this will do* box named the figure and the bill BEFORE
the button (B14 rule 11) and the receipt afterwards named the same figure.

**`BR-CWP-019` IS ASSERTED AS A CLOSED KEY SET**, not by spot-checking: the body
carries exactly `number · amount · status · due_on · masked_name · replaced_by`
and seven named leaks are then checked one by one, because a key set is easy to
widen by accident. The mask is fixed-width — `D. D••••••`, six dots whatever the
surname's length. **The two refusals are compared AS STRINGS:** a real bill with
the wrong postcode and a bill that does not exist come back byte-identically,
same `409`, and neither repeats the bill number back.

**Demo-script step 5 — the lock — is asserted as EXACTLY five, not "at most
five".** `lockedAt > 0` would pass over a form that locked on the first try,
which is a broken form rather than a strict one. Five wrong pairs were allowed,
the sixth refused, and a CORRECT pair inside the window was refused too, which
is what makes it a lockout and not a delay.

**No account and no credential appears behind the payment**, asserted by trying
to USE one: a silently minted credential would let that address sign in. It
answers `401`.

⚠ **DEMO-SCRIPT STEP 3 IS NOT TRUE TODAY AND THE TABLE IS SUPERSEDED ON IT.**
Step 3 says *"↓ Receipt works **without** an email; *Email it to me* prompts for
one"*. **Both controls are HELD** — drawn, disabled, each carrying its reason
and each stamped `data-held-for` (`US-CWP-005-receipt-document` and
`-receipt-email`), which is `BR-CWP-056` satisfied and the expiry test hard-won
law 2 asks for. The guest receipt DOCUMENT does not exist yet.

⚠ **AND STEP 4's THIRD CASE CANNOT OCCUR IN THIS BUILD — `DEF-CWP-4196`.** *"a
voided bill reads cancelled"*: `bill_lookup` has that branch and **no endpoint
voids a bill** (`US-BIL-027` has none; `corrections_api.py` records it in its own
exceptions block). The branch has unit coverage, which is why nobody looked —
the test proves the mapping and the question is the reachability. A fixture
cannot lawfully make one either: setting `status=void` on an issued invoice is
an UPDATE on an issued invoice, which hard rule 4 forbids. Carried as a known
gap that goes RED the day a cancelled bill can be found.

⚠ **`DEF-CWP-4197` — THE RECEIPT NAMED THE WRONG DAY, and it is the worst thing
either wave found.** `CWP-004`'s *Paid* row printed
`2026-09-06T03:59:13.769308+00:00`: an ISO instant, with microseconds, in **UTC**,
on the document a person keeps. It now draws `09/05/2026 23:09`, because the
tenant is `America/Chicago` — **a different day.** `CWP-003`'s due date had the
same fault. Both screens sat inside `PortalRegionalProvider` from birth
(`GuestFrame` is one of its two callers by design) and the tenant really was
publishing `MM/DD/YYYY`; they simply never imported `usePortalDate()`. Fixed
with the published formatter, never a second one.

⚠ **STEP 8 — the `CR-059` supersession stamps — is R5's and is unaffected by
this task.**

⚠ **AMENDED AGAIN 2026-09-06 — ALL THREE WALKTHROUGHS NOW EXIST AND THE
PARAGRAPH BELOW IS TRUE OF NONE OF THEM.** `cr068-q-pay-now-autopay-refunds.mjs`
runs GREEN at 77 assertions with 2 known gaps; `cr068-p-rails-and-webhook.mjs`
at 33 with 1; `cr068-r-quick-pay.mjs` at 70 with 1. **`CWP-002`, `CWP-003`,
`CWP-004`, `CWP-038`, `CWP-039`, `CWP-040`, `CWP-045` and `CWP-050` have all now
been opened in a browser**, and the four screens of waves P and R were compared
against their drawings — `13-wireframe-delta.md`, fourth pass. The paragraph
below is kept rather than deleted because **its reasoning is the part that
matters and it is unchanged**: every one of those screens had unit and DOM tests
and every one of them passed, and what nobody had done was open them.

**WHAT OPENING THEM COST, COUNTED: five defects across the three waves' own
surface that no test, no gate and no `tsc` could see.** Wave Q found six. Waves
P and R found `DEF-PAY-4188` (the webhook cannot be switched on by any
deployment), `DEF-PAY-4189` (a non-settlement event is recorded as a payment),
`DEF-CWP-4196` (the `cancelled` branch has no reachable input in this build) and
`DEF-CWP-4197` (a raw UTC instant on the guest receipt, naming the WRONG DAY —
`2026-09-06T03:59:13.769308+00:00` where the customer's own clock read
`09/05/2026 23:09`). Three of the four are on the money path.

⚠ **P5 · Q4 · R4 — THE BROWSER WALKTHROUGHS WERE NOT WRITTEN, FOR ANY OF THE
THREE WAVES.** *(Superseded 2026-09-06 by the two amendments above — all three
now exist. Kept because the reasoning is why they were written.)* `cr068-p-rails-and-webhook.mjs`, `cr068-q-pay-now-autopay-refunds.mjs`
and `cr068-r-quick-pay.mjs` do not exist. `10-scripts/cwp_portal_walkthrough.mjs`
reaches `CWP-001`, `002`, `008`, `011`, `014`, `015`, `060` and `066` — so
`CWP-002`, quick pay's front door, IS clicked, and **`CWP-003`, `CWP-004`,
`CWP-038`, `CWP-039`, `CWP-040`, `CWP-045` and `CWP-050` are not opened in a
browser by anything.**

**This is r11 step 2d — *prove it* — not done, and it is recorded here rather
than left to be inferred, because it is exactly the gap hard-won law 6 exists
for:** *no gate looks at rendered output*, and nine defects on the first live
deployment were found this way and by nothing else. Every one of those seven
screens has unit and DOM tests and every one of them passes; what nobody has
done is open them.

⚠ **AND THIS PHASE HAS ALREADY PAID FOR THAT TWICE IN TWO DAYS.**
`DEF-CWP-3927` and `DEF-CWP-3928` were both `31 Palm Ct`'s prices failing to
seed, and `DEF-CWP-3925` was six portal doors still refusing over screens that
had shipped days earlier — **found by opening the product in a browser, and by
nothing else.** A walkthrough that reaches a screen is the only check this repo
has that would catch the same class again on the seven screens above.

**R5 — `CR-068` §15 says the CR closes when Q and R have landed.** They have
landed; **it is not closed here**, because the walkthroughs above are part of
what landing means and because `DEF-PAY-3942`, `DEF-CWP-3943` and
`DEF-CWP-3941` are open against this phase's surface.

---

## 7 · The critical path, and what runs in parallel on day one

**To the first launch (Phase 1):** `A → {B ‖ C ‖ D}`. Wave A is the long pole
(~10 lane-days); the three behind it are independent of each other and each is 7–10
lane-days. **With three lanes, Phase 1 launches in roughly 20 working days; with one lane,
roughly 36.** Nothing in Phase 1 waits on a ruling: `OQ-1398` blocks who *maintains*
answers, not the mechanism, and the consumer-upload re-sign (B9) leaves the photo pickers
held rather than blocking a wave.

**To release 2:** `A → E → {F ‖ G ‖ H}`. E is 12 lane-days and everything signed-in stands
on it — the credential store, the session's account set, the balance seam and the shell.
F, G, H are 7–9 each and independent. **Release 2 is reachable about 20 working days after
Phase 1 launches, with three lanes.**

**To release 5:** the shortest chain of waves is **`A → E → G → P → Q`** (and `R` beside Q).
`G` is on it because the Pay surfaces it renders held are what P and Q turn live. `P` cannot
start until **`CR-069`'s payment rails** (W7) have landed and `OQ-1394` has been ruled or
its boundary accepted — so Phase 5's start date is set outside this CR. Phases 3 and 4 are
**not** on the release-5 chain: they run in parallel with each other after Phase 2 and are
launched in either order; the plan keeps §12's numbering (3 before 4) because Phase 3's one
precondition, `OQ-1399`, should be put to the PO early rather than late.

**What can start tomorrow, in parallel, on day one:**
1. **Wave A**, all of it (one or two people).
2. **K0** — the `OQ-1399` plain-English packet, drafted from the register's worked example
   and put to the PO; it needs no code.
3. **B9** — the consumer-upload re-sign packet (HUMAN-GUIDE §6), likewise.
4. **B1** and **D1** (the `interruption` table; the six content tables) can begin their
   packets and migrations as soon as A2's app skeleton is **pushed** (push after every
   step — law 12) — they do not need A's screens.

**Everything else waits on A.** That is deliberate: `route-b-migrated.txt`, the app
skeleton, the id registrations and `G75` are the four ground tasks `CR-068` §12 first put
in a *phase 0* the PO refused; they are the first four tasks of wave A instead, and wave A
still ends with a switch a System Admin flips and a page a stranger can open.

**Stands-on summary against the product waves:**

| Phase | Needs built | Needs *activated* | Needs ruled first |
|---|---|---|---|
| 1 | W0, W1, W2 | — | — (B9 re-sign leaves pickers held) |
| 2 | W2, W3, W4 | **W6** email, for codes and reset links to arrive (queued until then) | — |
| 3 | W2, W3, W4 | W6 | **`OQ-1399`** put to the PO; `OQ-1392/1393/1395/249` stubbed |
| 4 | W4 | — | `OQ-1391/1396` stubbed; decomposition rule raised with finance |
| 5 | **W7** (via `CR-069`), W6 | W7 | `OQ-1394`; `payment_methods` name; webhook signing answer |

---

## 8 · What is blocked, and what still demonstrates

**The rule (PO, 2026-09-03):** a wave blocked to a boundary by an open question still
demonstrates the boundary — the stub, the sentence on screen — and says so. **Nothing here
is skipped because a question is open; nothing here guesses an answer.** Every stub carries
its id in the code (`raise NotImplementedError("OQ-####")`), and the boundary demo shows the
refusal sentence a customer or clerk would actually read.

| Blocked by | Stories | Wave | What is built to the boundary | What the demo shows |
|---|---|---|---|---|
| **`OQ-1399`** — is the portal a notice delivery channel? *(put to the PO before Phase 3)* | `US-CWP-067`, `039` | K | The channel, the message list, the read state, the notices list including skips | The bell counts and the skipped notice render; any path treating a portal row as delivery raises |
| **`OQ-1391`** — self-serve plans? | `US-CWP-051`, `058` | M, L | Preview with the exact arithmetic; *ask for this plan* lands for a person | The instalment table; the ask on a clerk's worklist; self-activation raises |
| **`OQ-1392`** — self-serve close? | `US-CWP-061` | I | The move-out **request** with its danger-tier commit and distinction panel | `SR-26-0056` on the worklist; the close raises |
| ~~**`OQ-1393`** — straight onto a bill or review?~~ **CLOSED 2026-09-04, option (b)** | `US-CWP-042` | J | Everything — it blocks nothing. A reading is ACCEPTED, then validated, then flagged | ⚠ **Nothing is deferred any more.** What the ruling ADDED is a **provenance flag on every customer reading**, which needs a FOURTH `meter_source` beside `ami`/`manual`/`import` (`DEF-CWP-4194`) |
| **`OQ-1394`** — who pays the card fee? | `US-CWP-046`, `004` | P, R | Stored methods, quick pay — **no fee line drawn** | The pay screens without a fee line; the computation raises |
| **`OQ-1395`** — what is a statement? | `US-CWP-038` | K | The date-range read over bills, payments, credits, adjustments | The list in order; the document raises |
| **`OQ-1396`** — delegate term and revocation? | `US-CWP-029`, `030` | N | The record, the permission set, the expiry **column** | Kestrel named in the audit; the policy raises |
| **`OQ-1397`** — does a landlord see a tenant's bill? | `US-CWP-026` | F | The **flat** set — the only safe model until ruled | Four rows, `$872.82`, no fifth id; the reconciliation raises |
| **`OQ-1398`** — who keeps answers current, in how many languages? | `US-CWP-071` | D | The store, three statuses, eleven variants, *needs translating* visible | Publishing takes effect; French reads English with a line saying so; no workflow promised |
| **`OQ-249`** — field-work scope (older than this module) | `US-CWP-011`, `068` | K, J | Planned work read from `interruption`; the visit read from the existing `WorkOrder`; **no `planned_outage` table** | Seeded rows render; absent pages when none; both write paths raise |
| **Payment rails (W7, via `CR-069`)** | `US-CWP-004`, `005`, `006`, `022`, `045`, `046`, `047`, `049`, `050` | P, Q, R | Every screen ships **earlier, held**: the Pay control in its place, disabled, with its reason (`R3`); autopay's *next few* table live from the real intents | Wave G's step 6–7: the disabled control with its sentence; a forced click writes nothing |
| **Consumer upload — a signed deferral needing a re-sign** (`CR-068` §2b; task B9) | `US-CWP-007` TC-8, `042` TC-11, `066` TC-7, `064` | B, J, I | Every `PhotoPicker` held with its reason; the document checklist real; **no file input** | *Documents come to the office*; the held picker's sentence |
| **No trigger exists** (a scope decision, not a question) | `US-CWP-044` | O | The screen from a seeded alert; copy naming billing time | The test asserting **nothing fires it** |
| **W6 email / W8 SMS not activated** | `US-CWP-018`, `020` | E | Codes and links on the existing queue; SMS held | The code read from the queue row; the SMS option's held sentence |
| **Finance judgment** — the explainer's decomposition rule | `US-CWP-035` | O | The blueprint's four-line decomposition, summing exactly | The four lines and `$3.74`; the rule raised with that figure through the ledger |
| **`OQ-1340`** — is a corrected reference's audit row exempt from pruning? | `US-CWP-048` (wording) | G | The payments list | The list is **not** described as a permanent record of the old value |

---

## 9 · Story → wave — look up any `US-CWP-###`

| Story | Phase | Wave | Story | Phase | Wave | Story | Phase | Wave |
|---|---|---|---|---|---|---|---|---|
| `US-CWP-001` | 1 | A | `US-CWP-026` | 2 | F | `US-CWP-051` | 4 | M |
| `US-CWP-002` | 1 | B | `US-CWP-027` | 2 | F | `US-CWP-052` | 4 | M |
| `US-CWP-003` | 5 | R | `US-CWP-028` | 2 | F | `US-CWP-053` | 4 | M |
| `US-CWP-004` | 5 | R | `US-CWP-029` | 4 | N | `US-CWP-054` | 4 | M |
| `US-CWP-005` | 5 | R | `US-CWP-030` | 4 | N | `US-CWP-055` | 4 | M |
| `US-CWP-006` | 5 | P | `US-CWP-031` | 2 | F | `US-CWP-056` | 4 | L |
| `US-CWP-007` | 1 | B | `US-CWP-032` | 2 | G | `US-CWP-057` | 4 | L |
| `US-CWP-008` | 1 | B | `US-CWP-033` | 2 | G | `US-CWP-058` | 4 | L |
| `US-CWP-009` | 1 | B | `US-CWP-034` | 2 | G | `US-CWP-059` | 4 | L |
| `US-CWP-010` | 1 | B | `US-CWP-035` | 4 | O | `US-CWP-060` | 3 | I |
| `US-CWP-011` | 3 | K | `US-CWP-036` | 2 | G | `US-CWP-061` | 3 | I |
| `US-CWP-012` | 1 | C | `US-CWP-037` | 3 | J | `US-CWP-062` | 3 | I |
| `US-CWP-013` | 1 | C | `US-CWP-038` | 3 | K | `US-CWP-063` | 3 | I |
| `US-CWP-014` | 1 | C | `US-CWP-039` | 3 | K | `US-CWP-064` | 3 | I |
| `US-CWP-015` | 1 | C | `US-CWP-040` | 2 | H | `US-CWP-065` | 3 | I |
| `US-CWP-016` | 2 | E | `US-CWP-041` | 2 | H | `US-CWP-066` | 3 | I |
| `US-CWP-017` | 2 | E | `US-CWP-042` | 3 | J | `US-CWP-067` | 3 | K |
| `US-CWP-018` | 2 | E | `US-CWP-043` | 2 | H | `US-CWP-068` | 3 | J |
| `US-CWP-019` | 2 | E | `US-CWP-044` | 4 | O | `US-CWP-069` | 1 | A |
| `US-CWP-020` | 2 | E | `US-CWP-045` | 5 | Q | `US-CWP-070` | 1 | A |
| `US-CWP-021` | 2 | E | `US-CWP-046` | 5 | P | `US-CWP-071` | 1 | D |
| `US-CWP-022` | 5 | P | `US-CWP-047` | 5 | Q | `US-CWP-072` | 1 | D |
| `US-CWP-023` | 2 | E | `US-CWP-048` | 2 | G | `US-CWP-073` | 1 | D |
| `US-CWP-024` | 2 | E | `US-CWP-049` | 5 | Q | `US-CWP-074` | 1 | D |
| `US-CWP-025` | 2 | F | `US-CWP-050` | 5 | Q | | | |

**Wave sizes:** A 3 · B 5 · C 4 · D 4 · E 8 · F 5 · G 5 · H 3 · I 7 · J 3 · K 4 · L 4 ·
M 5 · N 2 · O 2 · P 3 · Q 4 · R 3 = **74**.

## 10 · Journey → wave

`04-flows.md` describes all eighteen; **none of the files in `08-qa/01-e2e/journeys/` is
written yet** (its own header and `14-id-reservations.md:598` say so). Each wave writes the
journey file for the journey whose spine it demonstrates; the `07-frontend/e2e/J##.spec.ts`
activates when the wiring index (`10-scripts/07-e2e-wiring-index.py`) says every story in
the journey is built — `G12` reads the index, never prose.

| J | Journey | File written in | Spec activates after |
|---|---|---|---|
| `J30` | Guest quick pay | R | R |
| `J31` | Report a burst main, track it | B | B |
| `J32` | Availability → apply → consent | C | Q (its fee step is `US-CWP-050`) |
| `J33` | Read an answer, end at a person | D | I (`CWP-054`) |
| `J34` | Where you can walk in | D | D |
| `J35` | Enrol cold | E | E |
| `J36` | The eleven-month cold return | G | G |
| `J37` | Landlord across four accounts | F | F |
| `J38` | Bill went up → query | O | O (dispute in I) |
| `J39` | Self-read end to end | J | J |
| `J40` | Move-out → final bill → refund | I (spine) | Q (`US-CWP-049`) |
| `J41` | A plan asked for | M | M |
| `J42` | A plan offered | M | M |
| `J43` | Overdue and the protections | L | L |
| `J44` | A delegate invited and named | N | N |
| `J45` | Paperless consent taken, withdrawn | F | F |
| `J46` | Answer authored → read → voted | D | D |
| `J47` | Notices sent and not sent | K | K |

## 11 · What this plan adds to `CR-068` §12, and what it moves — for the wave lanes to write back

`CR-068` §12 was written before the 74 stories existed. Completing it against the stories
produced these differences; each is owed a write-back by the wave that meets it, dated
(law W), and none changes a signed rule.

1. **Two gates §13 names but §12 never schedules** — `G76` portal/staff separation and
   `G77` guest-leaks-nothing — are tasks **E4**; `G78` the CWP register is **A4**.
2. **§12 has no screen task at all for Phases 3, 4 or 5** and one for Phase 2 (`2.14`)
   covering fifty-four screens. Every wave here has its own 2b task, per r11.
3. **§12 has no journey task**; every wave writes the journey files it demonstrates (§10).
4. **§12 has no walkthrough task**; every wave's 2d names its `render-checks` script.
5. **Stories with no §12 task:** `US-CWP-037` (final bill), `US-CWP-068` (visit booked —
   §12's `4.9` is the spec, not the story; moved to Phase 3 wave J where `WorkOrder` is
   read), `US-CWP-002` (the throttle — the blueprint never specified it), `US-CWP-033`
   (one bill line by line), `US-CWP-044` (the alert).
6. **§12 tasks split across waves:** `1.5` (guest edge — A5 front half, B2/C1/C2/D2 the
   rest); `1.8` (unauthenticated requests — B2 reports, C2 applications and quick asks);
   `1.16`/`1.17` (screens — A6, B4, C3, D3); `2.8`/`2.9` (credits/refunds move to L1;
   deposit and exemption stay in F1; level pay to M1); `2.12` (history F1; `CP-55` H1);
   `4.5` (statement — moved to K1, Phase 3, because it is a documents-tab read);
   `4.9` (visit — moved to J1).
7. **Tasks §12 never had:** B3/B5 (the clerk's interruption status control), B9 (the
   consumer-upload re-sign packet), K0 (the `OQ-1399` packet), P1 (the name collision as its
   own task), the fixture decision (A7/A9), the held-Pay half of `045`/`046`/`047` rendered
   in G2 so `R3` is true from Phase 2.
8. **Stories moved between phases:** `US-CWP-011` release 1 → Phase 3 wave K (§0 row 21);
   `US-CWP-044` wave 0 → Phase 4 wave O.
9. **Documents that disagree with the code**, listed in §0 — the brand column names, the
   guest root, `MeterRead.source`, the read-state split, the endpoints' owner, the upload
   scan — each stamped by the wave that builds the row.
10. **`02-business-rules.md`'s question table** names the wrong story for eight of nine
    questions; the register and the epics agree. A defect row is owed (this plan's write
    scope did not include the register).

## 12 · STOPPING SERVICE HAS THREE STEPS AND ITS DRAWING HAS FOUR — the missing one, on the plan (added 2026-09-11, `CR-085` step 2 lane 3)

⚠ **THIS SECTION EXISTS BECAUSE THE WHOLE RECORD OF IT WAS A CODE COMMENT** —
`DEF-CWP-4874`. `StopOrRestart.tsx`'s docstring said, correctly and in detail, that
wireframe **s22** — *where the final bill goes* — is absent and why. Nothing else in
the repo said it: no question, no plan row, no rule. A deferral written as a code
comment is tracked by nothing, which is `DEF-CWP-4203`'s own escape reason and
hard-won law 1 in its plainest form.

**What is missing, in one sentence.** A customer who is moving out tells us the day to
turn the supply off and nothing about where to reach them afterwards, so their final
bill is posted to the house they have just left.

**Why the build is right to refuse it today.** `POST accounts/{id}/stop-or-restart/ask`
accepts **four** things — a stop date, a restart date, a reason and a contact — and
**none** of the three that step needs: a forwarding address, the deposit figure, a
refund destination. `GET stop-or-restart` serves no deposit either. Boxes that posted
nowhere would collect the one thing a leaving customer most needs us to have and drop
it on the floor (hard-won law 2).

**The question, not the answer: `OQ-CWP-1767`, OPEN.** Three costed options are in the
row, and the cheapest is worth naming here because it needs no new concept: a
forwarding address already has a lawful home in `customers.addresses` `kind='mailing'`
— CLAUDE.md hard rule 8's first exception, *where the BILL goes, which for a landlord
is another building*. **The refund destination is the heavy half**, because it is a
bank account and touches `payments`.

**The other end of the same gap.** `CWP-032`'s drawn **WHERE WE SENT IT** block —
*"220 Lakeview Dr… the forwarding address you gave when you stopped service"*, with
*That is wrong — change it* — cannot exist while this step does not. Whoever takes
`OQ-CWP-1767` takes both screens.

**And the four dates are DECIDED rather than open.** s23 ends with a timeline —
*meter read Sep 30 · final bill around Oct 5 · due around Oct 20 · deposit back by
Nov 4*. Nothing on the wire carries any of the four, and the blueprint's **R-23** —
*no sentence states a fact it does not derive* — forbids printing them. **They stay
absent**, recorded in the decision log of 2026-09-11, and a lane that "fixes" this by
computing four dates in the browser is inventing a promise on the screen that closes a
household's water.
