# The gate suite, measured — a dated baseline (2026-09-25)

**Why this exists.** On 2026-09-24 the Product Owner was told *"55 gates are failing
repo-wide, none of them Finance's"* — and nobody could say whether that number was
getting better or worse, **because no before-count had ever been recorded.** This
file is that before-count. It is a MEASUREMENT, not a work item: none of the 56 is
fixed here.

## How to re-run it, exactly

```
python3 10-scripts/gates/run_gates.py      # tier 3, all 134 gates, the merge verdict
```

⚠ **Through `run_gates.py`, NEVER `python3 <gate>.py`.** A gate with no callable
`run` has been announced green while the suite reported `gate crashed`
(`DEF-GOV-3733`); `__main__` is not the path the suite uses. ⚠ **The runner prints
nothing until it finishes and a quiet log means WAIT, not restart** — it says so
itself. This run took ~50 minutes with four other lanes on the machine.

## The numbers, at `2d17762a5`, 2026-09-25

| | count |
|---|---|
| gates run (tier 3) | **134** |
| PASS | **73** |
| **FAIL** | **56** |
| SKIP | **5** |
| verdict | `MERGE BLOCKED` |

⚠ **THE PO WAS TOLD 55; THE NUMBER IS 56.** Not a correction of anyone's arithmetic
— there was no baseline to be wrong about. This is the first one.

⚠ **THE RUNNER REFUSED TO INVENT A TREND, CORRECTLY.** Its own output: *"NO PREVIOUS
RUN IS RECORDED … This is NOT '0 newly failing': it is 'there is no basis for that
number'."* From the next run on a machine it compares against
`10-scripts/gates/last-run.json`, which is **gitignored** — so **this file is the
only cross-machine record and the only thing a future lane can diff against.**

## ⚠ What this measurement CANNOT tell you — with numbers, not adjectives

| the limit | count |
|---|---|
| failing gates whose finding names a repo file, so a date could be attached | **28 of 56** |
| failing gates whose finding names NO file — ratchet counters, totals, cross-cutting sweeps — **UNDATED here** | **28 of 56** |

⚠ **THE DATE COLUMN IS `git log -1 -- <file>` — *last touched*, NOT *made it red*.**
They coincide often and not always. Sixteen of the 28 date to one commit,
`08a8d08df` (2026-09-16), which is a mass commit, so for those the column means
only *this file last moved then*. **An exact `git log -S` on the failing symbol was
run by hand only for the rows this lane fixed.** Re-date any other row before
quoting it to anybody.

⚠ **THE PARSER THAT BUILT THIS TABLE WAS WRONG ON ITS FIRST PASS, WHICH IS WHY THE
COUNT IS STATED TWICE.** It read **55** of 56 rows: `G129`'s name
(`premises/units copy caps`) contains spaces and a `(\S+)` field swallowed the row
silently. **Counting what was found against what should be there is the only thing
that caught it** — the parser was not lying, it was answering truthfully about
everything it could see. It now reconciles: **56 parsed, 56 reported.**

## The five SKIPs — and four had ONE cause

**A SKIP is green to a reader scanning a table.** These were not "not applicable";
they were **unable to run**:

* `G5 isolation SKIP no interpreter on this machine can import both pytest and Django, so the isolation suite cannot be run at all. Tried: /usr/local/bin/python3, python3, python3.14, python3.13, python3.12, python3.11, python3.10. (1247 backend test file(s) present.) ⚠ This is the ONLY honest skip for this gate — it used to skip whenever the RUNNER's own interpreter lacked pytest, which reported not`
* `G49 identifier-series-contract SKIP could not read the import module's declarations, so nothing was checked: ModuleNotFoundError: No module named 'django'. The probe runs `python -c` in 06-backend with DJANGO_SETTINGS_MODULE=config.settings.test and touches no database`
* `G68 plant-on-postgres SKIP DATABASE_URL is unset, so there is no PostgreSQL to prove anything on. This gate is DEF-2395's own prevention and it deliberately does NOT report PASS for a SQLite run: law 14 exists because SQLite has no aborted-transaction state, so a green run there is not the proof. Runnable with: DATABASE_URL=postgres://... DJANGO_SETTINGS_MODULE=config.settings.local`
* `G87 declared-dependencies SKIP not the project's interpreter (smartbillhub is not installed in /usr/local/bin/python3), so nothing here could be checked — re-run the suite with the interpreter that runs the tests`
* `G120 the-application-starts SKIP no interpreter on this machine can import Django, so a cold boot cannot be attempted. Tried: /usr/local/bin/python3, python3, python3.14, python3.13, python3.12, python3.11, python3.10.`
* `G121 plans-name-their-late-fee-code PASS no late-fee code path reads late_pct or late_min_amount from the tenant's Billing defaults (3/3 late-fee file(s) scanned) — the terms come from the charge code the plan names (BR-RAT-1011). Plan count: SKIP — no interpreter on this machine can import Django`
* `run_gates: 73 PASS, 56 FAIL, 5 SKIP — MERGE BLOCKED`

⚠ **`G5`, `G49`, `G87`, `G120` AND HALF OF `G121` SKIPPED FOR ONE CAUSE.** The
interpreter probe tries `[sys.executable, "python3", "python3.14"…"python3.10"]` and
**never `06-backend/.venv/bin/python`**, which is where this project installs its
dependencies. Measured 2026-09-25: bare `python3` and `python3.11` have no Django,
`python3.12` has no pytest, the venv has both (Django 5.2.17). Filed `DEF-GOV-6691`
and fixed by this lane. **What the fix immediately uncovered:**

* `G120` **now PASSES** — it had been skipping over a boot it could perform.
* `G5` now reports what it could not: **the only tenant-isolation proof this repo
  holds was taken 2026-09-07, is STALE against current migrations, and WAS RED WHEN
  TAKEN — 1 failed, 272 passed.** That is hard rule 1, and no gate has been able to
  say so for eighteen days. Re-take with `10-scripts/prove_isolation.py` (~20 min).
* `G4`'s `pytest -m golden` leg reports **1180 errors** from the same cause — the
  B4/B5 billing-math suite is not being run by the gate suite at all.

## Which of the 56 are Finance's

**20 of 56** name a file or subject under `ledger` / `payments` / `reports` /
`billing`. None is a Finance FEATURE defect: they are repo-wide sweeps that list a
Finance file among many. The claim *"none of them is pointing at Finance's work"* is
**upheld**, and is now a number rather than an impression.

## Checks that cannot do their job, found while measuring

| what | shape (hard-won law 7) | filed |
|---|---|---|
| Five gates cannot find the project's virtualenv, so the RLS isolation suite and the golden billing suite are never run | *incapable of passing* | `DEF-GOV-6691` — **fixed** |
| `G116` printed its scope numbers only in its PASS branch — the one state it has never been in — so a red reader could not tell 24 bad of 1,266 from 24 of 30 | *output cannot distinguish pass from fail to a reader* | `DEF-GOV-6690` — **fixed** |
| `G5` reports a STALE-and-RED isolation receipt as **SKIP**, which reads green in the table | *reporting nothing over a scope it excludes* | noted on `DEF-GOV-6691`; the verdict is the gate's own design and was not changed unilaterally |

**Gates that do this WELL — the pattern to copy:** `G128` prints *"⚠ 11 address
read(s) in apps/integrations/adapters/ were NOT checked"* beside its pass; `G129`
prints *"catalogue only — 1 literal(s) and 976 foreign key(s) unmeasured"*; `G5`'s
skip names every interpreter it tried. **A check that says what it did NOT look at
is worth more than one that says PASS.**

## The 56, in the runner's own order

`Finance?` is a keyword match on the finding, not a judgment. The date column
carries the limit described above.

| gate | first finding (trimmed) | first file it names | that file last moved | Finance? |
|---|---|---|---|---|
| `G1` packet | 06-backend/apps/assets/equipment_reads.py: Lifecycle trailer lacks a 'packet: US-XXX-###@<hex>' line; 06-backend/apps/assets/migrations/0007_cr028_valuation.py: Lifecycle trailer lacks a 'pa | `06-backend/apps/assets/equipment_reads.py` | 08a8d08df 2026-09-16 | no |
| `G2` code-trace | 06-backend/apps/runbooks/definitions/accounting_export.py: cites US-RBS-042 — no such story in 06-epics frontmatter | `06-backend/apps/runbooks/definitions/accounting_export.py` | 08a8d08df 2026-09-16 | no |
| `G3` checklist | 06-backend/apps/assets/equipment_reads.py: checklist missing letters B,D,E,H; 06-backend/apps/audit/migrations/0005_rls_deny_on_unset_tenant.py: checklist missing letters B,D,E,H; 06-backend | `06-backend/apps/assets/equipment_reads.py` | 08a8d08df 2026-09-16 | **yes** |
| `G4` golden | harness: golden-verify: 33 PASS, 0 FAIL / ruling-derived (part 3, NOT frozen): 6 PASS, 0 FAIL / CR-081 not-yet-re-signed (part 4): 9 PASS, 0 FAIL / GT-1..16 self-consistency: 12 PASS, 0 FAIL | — none named: **UNDATED** | — | no |
| `G6` forbidden | 06-backend/apps/billing/api.py:1491: ORM access in api.py — use selectors/services (B8 layering); 06-backend/apps/billing/api.py:1801: ORM access in api.py — use selectors/services (B8 layer | `06-backend/apps/billing/api.py` | 08a8d08df 2026-09-16 | **yes** |
| `G7` human-owned | 06-backend/apps/rating/migrations/0039_def_rat_5799_class_backfill_under_rls.py: holds real logic but has no row in the human-review ledger; 06-backend/apps/customers/migrations/0045_br_cus_ | `06-backend/apps/rating/migrations/0039_def_rat_5799_class_backfill_under_rls.py` | 4a30d3885 2026-09-19 | **yes** |
| `G8` stub-honesty | registry OQ-249: status does not begin with a state token (reads '**The 2026-08-16 design bundle (prototype r10, CR-002) ships') — a status field is a STATE, not a story; registry OQ-267: st | — none named: **UNDATED** | — | no |
| `G10` tc-tests | US-AST-005: no test named test_us_ast_005_tc* under 06-backend; US-CUS-007: no test named test_us_cus_007_tc* under 06-backend; US-CUS-008: no test named test_us_cus_008_tc* under 06-backend | — none named: **UNDATED** | — | no |
| `G11` tag-stamp | 06-backend/apps/assets/migrations/0007_cr028_valuation.py: status 'HUMAN-REVIEW-PENDING' not in ['GENERATED', 'RATIFIED', 'SUPERSEDED', 'VERIFIED-UNRATIFIED']; 06-backend/apps/assets/migrati | `06-backend/apps/assets/migrations/0007_cr028_valuation.py` | 08a8d08df 2026-09-16 | **yes** |
| `G12` journeys | STALE: 08-qa/01-e2e/01-journey-story-index.md, 08-qa/01-e2e/01-journey-story-index.json — re-run 10-scripts/07-e2e-wiring-index.py | `08-qa/01-e2e/01-journey-story-index.md` | 870b4c21f 2026-09-23 | no |
| `G13` unwired-props | FAIL unwired props — a feature is guarded by a prop nothing supplies: 07-frontend/src/features/customers/moveReadsCapture.tsx: renders behind `props.readAtLabel` but no caller passes it / 07 | `07-frontend/src/features/customers/moveReadsCapture.tsx` | 693c7a3fb 2026-09-24 | no |
| `G14` prototype-conf | 4 conformance failure(s): metering.premises.explainer.premises is missing from the English catalog (+3 more) | — none named: **UNDATED** | — | no |
| `G15` i18n-parity | 635 NEW value(s) pasted in English rather than translated (baseline holds 5906, g15_untranslated_baseline.txt): de :: assets.exportCapacityKw, de :: billing.print.tile.about, de :: customers | — none named: **UNDATED** | — | **yes** |
| `G17` duplicate-ids | 6 running number(s) claimed by more than one id, BEYOND the carried set: 6554 is claimed by 2 different ids (DEF-PAY-6554, DEF-SHL-6554) — the module segment is not part of the number, and a | `10-scripts/allocate.py` | 08a8d08df 2026-09-16 | no |
| `G18` i18n-callsites | 21 missing (18 unparked, renders raw to a user) · 789 dead (579 unparked, renders to nobody) · 234 PARKED in i18n_known_gaps.txt (real, unfixed, routed) — 18 key(s) used in code and defined  | `10-scripts/gates/g18_i18n_call_sites.py` | 08a8d08df 2026-09-16 | **yes** |
| `G19` env-hostnames | 1 problem(s): 11 catalogue value(s) name an environment: de.json:integrations.modal.emailExample names 'ihrversorger.example'; en.json:integrations.modal.emailExample names 'yourutility.exam | — none named: **UNDATED** | — | no |
| `G20` seam-impl | 1 seam problem(s): STALE PARK line 44: apps.rating.selectors.tax_authority_id_for_tax RESOLVES now — the park has done its job; delete the row so the gate guards it again | — none named: **UNDATED** | — | no |
| `G23` surface-debt | ledger: surface_debt.txt declares 2 unreachable stor(ies) and there are 1 — FEWER than declared (US-LED-003). The count is EXACT: raise it with a reason, or lower it because a surface landed | — none named: **UNDATED** | — | **yes** |
| `G26` required-rows | 06-backend/apps/identity/sample_data.py::_owner_as_actor refuses because a per-tenant row is missing, and required_rows.txt does not say how that row is ever created. Add a row naming the pr | `06-backend/apps/identity/sample_data.py` | 08a8d08df 2026-09-16 | **yes** |
| `G25` screen-coverage | 1 screen-coverage problem(s): S147 is in the screen inventory and NO story claims it (no `screens:` frontmatter names it) — hard-won law 8. Author its story, or register it in screen_story_c | — none named: **UNDATED** | — | no |
| `G27` i18n-keys | 4 finding(s), the first being: 07-frontend/src/features/payments/ForceCloseCounterModal.tsx asks for 1 key(s) no catalogue defines: payments. | `07-frontend/src/features/payments/ForceCloseCounterModal.tsx` | 870b4c21f 2026-09-23 | **yes** |
| `G28` internal-refs | 2 internal reference(s) on screen: 06-backend/apps/integrations/partner_api.py :: description :: rule or story id :: A key we (+13 Part 3 diagnostic finding(s)) | `06-backend/apps/integrations/partner_api.py` | 33c863619 2026-09-24 | no |
| `G29` screen-ids | 4 screen-id problem(s): routes_total ROSE: 152 now, 148 registered. A screen shipped with no id — give it one or record why it has none.; screens_total ROSE: 139 now, 137 registered. A scree | — none named: **UNDATED** | — | no |
| `G31` declared-classes | 1 type-scale orphan(s): a `text-<name>` no token file declares. `--text-*: initial` deleted Tailwind's own scale, so this compiles to NO RULE and renders as nothing — tsc, eslint and every t | — none named: **UNDATED** | — | **yes** |
| `G32` refusal-keys | 12 raised message_key(s) resolve to nothing, 0 baselined: billing.templates.layout_preview_refused (raised in 06-backend/apps/billing/layo | — none named: **UNDATED** | — | **yes** |
| `G33` refusal-copy | 9 new or changed refusal(s) over 6 words (573/1297 over 6 words, 573 baselined): integrations.field.site_id: a 10-word sentence (max 6) — Type the site ID they gave you, o — shorten by delet | — none named: **UNDATED** | — | no |
| `G129` premises/units copy caps | 2 new or changed premises/units string(s) over cap (114/743 over rule 33's caps, 112 baselined; catalogue only — 1 literal(s) and 976 foreign key(s) unmeasured): metering.premises.listSubtit | — none named: **UNDATED** | — | no |
| `G35` version-lockstep | VERSION 2.351.84 HAS NO CHANGELOG ENTRY — CHANGELOG.md's newest heading is 2.351.83. A user on 2.351.84 opening the changelog is told about a build they are not running (DEF-806, which is ex | — none named: **UNDATED** | — | no |
| `G37` row-actions | 12 rule-15 problem(s): components/Sparkline.tsx declares an inline <svg>. The B14 rule 15 vocabulary lives in components/icons.tsx and nowhere else — that is DEF-348, where the same pencil e | — none named: **UNDATED** | — | no |
| `G38` stated-absences | 52 stated absence(s); 8 cite a DEF or OQ, 44 cite nothing (baseline 47). DOWN from 47 — lower UNTRACKED_BASELINE to 44 in this file to hold the gain. A ratchet that never tightens is a numbe | — none named: **UNDATED** | — | no |
| `G40` unmounted-components | unmounted components ROSE by 26: 26 now, 0 baselined. A component nothing renders is dead UI — it compiles, its own tests pass, and the feature does not exist (hard-won law 2, DEF-520). Now: | — none named: **UNDATED** | — | no |
| `G41` tenant-guc-form | 2 problem(s): 06-backend/apps/customers/migrations/0070_p0_2_primary_holder.py: introduces the OLD tenant predicate (1x) and is not in the baseline. · 06-backend/apps/tenancy/migrations/0048 | `06-backend/apps/customers/migrations/0070_p0_2_primary_holder.py` | b813394a6 2026-09-24 | no |
| `G43` list-toolbar-contract | B14 rule 19: 0 searchable list(s) with no prompt (baseline 0); rule 18: 31 live `max-w-prose` (baseline 50); toolbar capacity: 0 dimension control(s) in a download slot (baseline 0); self-te | — none named: **UNDATED** | — | no |
| `G44` display-truth | clause (c) — 40 classified value(s) reach a text position untreated; the banked ratchet is 20. A NEW one was added: | — none named: **UNDATED** | — | no |
| `G45` declared-filters-rendered | BR-SHL-010: 6 screen(s) declaring `TableConfig.filters` with no `filterBarSlot` (baseline 0); self-test: 6/6 clauses bite. 6 more than the baseline of 0. A `TableConfig` that declares filter | — none named: **UNDATED** | — | **yes** |
| `G46` register-vocabularies | 2 vocabulary problem(s) in 10-defect-log.csv: category: 'stale-copy' on DEF-RAT-6145 (filed 2026-09-22) — from 2026-09-11 a new row carries one of the twelve: access-tenancy · built-not-wire | — none named: **UNDATED** | — | no |
| `G47` service-catalog-parity | BR-RAT-024: the platform seeds 11 service(s); (a) 3 incomplete enumeration(s) (baseline 0), (b) 0 unseeded code(s) (baseline 0); 8 file(s) partial by a named ruling; self-test: 11/11 clauses | — none named: **UNDATED** | — | no |
| `G48` import-money-posts | BR-LED-007: 8 money column(s) on the shipped import template, 15 ledger posting entrypoint(s), 2 posting caller(s) outside the ledger; 1 unposted (0 banked, 1 not posted by a ruling); self-t | — none named: **UNDATED** | — | **yes** |
| `G53` guard-list-coverage | 35 file(s) invoke the 🔒 human-review protocol in their own docstring (HUMAN-OWNED or HUMAN-REVIEW-PENDING) and no glob in human_owned.txt matches them: 34 with a review-ledger row already op | `06-backend/apps/billing/penalty.py` | 08a8d08df 2026-09-16 | **yes** |
| `G63` guard-claims | 1 guarded file(s) tell the reader they are UNGUARDED (DEF-2791). Each is matched by a glob in human_owned.txt today and its own docstring says no glob matches it — so the next lane files a c | `06-backend/apps/rating/pricing/percent_basis.py` | 00b3ae358 2026-09-22 | no |
| `G64` golden-engine-coverage | 1 live document(s) quote the harness count (33/33) and never name the engine one, so a reader takes 'GT-1..61 are the billing-math contract' beside it as the engine being checked against 61  | `04-docs/05-modules/07-billing/conformance/CR-100-BRC03-billing-step1.md` | 08a8d08df 2026-09-16 | **yes** |
| `G67` fix-leaves-a-trace | traceless fixes ROSE to 360 from a baseline of 123: a row marked closed names a file, and that file never mentions the id — so a lane grepping for it finds nothing and concludes the fix was  | `06-backend/apps/work/rules.py` | 08a8d08df 2026-09-16 | no |
| `G85` one-address-home | apps/notifications/suppression_models.py::SuppressedAddress declares ['address']. An address is stored on `premises` (BR-MET-1161, PO ruling 2026-09-04) and everything else walks to it — ass | — none named: **UNDATED** | — | no |
| `G86` house-style-controls | features/work/OrderDetailPage.tsx hand-rolls a button: border border-divider px-2 py-1 text-sm text-accent / portal/components/primitives.tsx hand-rolls a button: shrink-0 border border-neut | — none named: **UNDATED** | — | no |
| `G93` one-build-destination | features/customers/ApplicationBecomesABuild.dom.test.tsx:111 links to the retired build destination / features/customers/ApplicationBecomesABuild.dom.test.tsx:155 links to the retired build  | — none named: **UNDATED** | — | no |
| `G94` credential-three-exits | apps.py:57 logs from the credential path — this module has no logger on purpose; apps.py:88 logs from the credential path — this module has no logger on purpose; apps.py:97 logs from the cre | — none named: **UNDATED** | — | no |
| `G95` trace-tests-exist | 92 Trace citation(s) name a file that does not exist and is not in the baseline: 06-backend/apps/integrations/adapters/bank_lockbox_file.py -> 06-backend/tests/test_us_int_008_bank_adapter.p | `06-backend/apps/integrations/adapters/bank_lockbox_file.py` | 08a8d08df 2026-09-16 | **yes** |
| `G98` lint-clean | eslint is RED: `npm run lint` (`eslint src --ext .ts,.tsx --max-warnings 0`) exited 1 in 07-frontend. 38 file(s): src/features/assets/AssetLifecycle.test.tsx; src/features/billing/fixABillSt | `07-frontend/src/features/rating/RateScheduleWizard.tsx` | 1c6d052f8 2026-09-24 | **yes** |
| `G78` work-writes-nothing-foreign | 06-backend/apps/work/sample_field_work.py:746 imports apps.metering.connections outside seams/ (BR-WRK-002) | `06-backend/apps/work/sample_field_work.py` | 08a8d08df 2026-09-16 | no |
| `G103` holds-cannot-rot | portal.apply.held.companyName is a hold drawn in portal/guest/ApplyForService.tsx with no row in 07-frontend/src/portal/routing/holds.ts. Add one saying what would release it — a hold with n | `07-frontend/src/portal/routing/holds.ts` | 08a8d08df 2026-09-16 | no |
| `G79` no-send-route | 06-backend/apps/integrations/api.py mounts 'integrations/<str:key>/export' — the module sends nothing itself (BR-INT-008); the owning flow reads the connection and does the sending | `06-backend/apps/integrations/api.py` | 870b4c21f 2026-09-23 | no |
| `G106` cited-ids-exist | OQ-BIL-12376 is cited at 06-backend/apps/billing/fee_bill.py:363 and no register ever issued it / OQ-BIL-12377 is cited at 06-backend/apps/billing/fee_bill.py:665 and no register ever issued | `06-backend/apps/billing/fee_bill.py` | 090df1096 2026-09-24 | **yes** |
| `G107` one-responsive-direction | 07-frontend/src/portal/bills/BillDetail.tsx writes `md:hidden` — a MIN-width variant in a DESKTOP-FIRST theme. The portal was converted to zero of these by DEF-CWP-4004; authoring reads `max | `07-frontend/src/portal/bills/BillDetail.tsx` | 08a8d08df 2026-09-16 | **yes** |
| `G114` list-envelope | 07-frontend/src/api/endpoints.ts: `ImportRunListResult` declares `rows` beside `per`/`pages`/`last_page` — that is the SELECTOR's page dict, not the reply. The wire carries {count, next, pre | `07-frontend/src/api/endpoints.ts` | 7f6cbae0a 2026-09-24 | no |
| `G115` runbooks-import-census | 06-backend/apps/runbooks/definitions/leak_alert.py:846 imports apps.notifications outside seams/*_seam.py and ports/*_ports.py (BR-RBS-039) / ports/ declares 14 port(s); the reviewed interfa | `06-backend/apps/runbooks/definitions/leak_alert.py` | 08a8d08df 2026-09-16 | no |
| `G116` cited-tests-exist | 06-backend/apps/integrations/partner_csv.py cites 06-backend/tests/test_cr111_partner_csv.py, which does not exist / 06-backend/apps/integrations/sample_data.py cites 06-backend/tests/test_c | `06-backend/apps/integrations/partner_csv.py` | 1b0d9c745 2026-09-17 | **yes** |

## What a future lane should do with this

1. Re-run the command at the top.
2. Diff the PASS/FAIL/SKIP triple against **73 / 56 / 5**.
3. **A gate that moved from FAIL to SKIP is a REGRESSION, not progress** — that is
   exactly what `DEF-GOV-6691` was, for weeks, on hard rule 1.
4. Re-date any row before quoting it.

Trace: lane FIN-TEST, 2026-09-25 · tip `2d17762a5` · `DEF-GOV-6690` · `DEF-GOV-6691`
