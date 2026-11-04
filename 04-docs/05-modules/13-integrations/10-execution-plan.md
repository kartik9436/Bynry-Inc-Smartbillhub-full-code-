# 13 · Integrations — execution plan for `CR-069` (phases → waves → tasks)

**Written 2026-09-03 against HEAD `b29edecd` (product `2.128.2`) from the documentation that already exists:
`12-governance/change-requests/CR-069-integration-substrate.md` (§8 the 36 cards, §12 the five phases, §13 the
three gates, §16 rollback), this module's `01`–`09` files, `04-docs/02-decisions/12-engineering-plan.md`
Addendum r11, `12-governance/19-execution-sequence.md`, `12-governance/20-wave-tasks.tsv` and
`12-governance/01-open-questions.md` rows `OQ-INT-1470`–`1488`.** Paths are relative to the repository root.
Task ids (`A1`, `B3` …) are this plan's own; the design's `T-x.yy` ids appear in a cross-reference column only
where `CR-069` names them, and none is invented here.

## 0a · THE BOUNDARY OF 2026-09-06 — WHAT THIS PLAN STILL COVERS

⚠ **READ THIS BEFORE ANY WAVE BELOW. Roughly half of the pending work in this plan is no
longer integrations' to build**, and the waves that moved are still printed here, in place,
with their letters intact.

**PO ruling 2026-09-06, verbatim:**

> "We want integration scope about building a conn crore , managing keys/secret, managing
> lifecycle of connect - while business logic , scheduling , processing we will take it in
> run book."

⚠ ***"conn crore"* is read as *connection***; the words are recorded as said. This
**sharpens** the ruling of 2026-09-05 (`BR-INT-054`) and reverses nothing — that one said
what integrations does not do, this one says what it does, and adds **scheduling** to the
Runbooks side. **The full statement, the supersedes chain and the wave-by-wave verdicts are
`CR-069` §20**; this section is the plan's own copy of the consequences.

**Integrations keeps exactly three things: (1) building a connection · (2) holding keys and
secrets · (3) the lifecycle of a connection.** Business logic, scheduling and processing are
Runbooks'.

### The nineteen waves, after the line

| Verdict | Waves | |
|---|---|---|
| **Stays whole with integrations** | `A` · `B` · `E` · `H` · `R` | doors, credentials, a connection's own health |
| **Moves whole to Runbooks** | `G` · `L` · `Q` | scheduling; the reconcile of late readings; the GIS night |
| **Splits** | `C` · `D` · `F` · `I` · `J` · `K` · `M` · `N` · `O` · `S` | each keeps its door and gives up its decisions |
| **Cancelled, untouched** | `P` | `OQ-INT-1482` ruled (c) on 2026-09-04; the letter is not reused |

**The rule that decides every split, and it is one sentence:** *recognising something we
have already taken is connection-level and stays; deciding what it means is Runbooks'.*
That is the 2026-09-05 worked case — *"records that a batch arrived on that connection —
and stops"* — applied to `I`'s `input_hash`, `J`'s period+target key and `N`'s dedupe.

⚠ **A MOVED WAVE IS NOT DELETED AND ITS LETTER IS NEVER REUSED**, exactly as `M3` was
handled when it left wave `M` in the Work plan. Its heading, goal and task table stay
where they are under a banner saying where the work went, **so a citation of `G1` or `L3`
still lands on the thing it named.** The task total below is unchanged at **122** for the
same reason.

### What this does to the size

| | People-weeks | |
|---|---|---|
| Built already (`A`–`E`) | **15** | of which `C` 1.5 and `D` 1.5 are the disputed ones — `OQ-INT-1727` |
| **Still pending** (`F`–`S`, `P` cancelled) | **≈ 40** | 39.5 low / 43.5 high, at this plan's own sizes |
| — integrations retains | **≈ 20** | `H` + `R` whole, plus its share of the ten splits |
| — Runbooks inherits | **≈ 21** | `G` + `L` + `Q` whole (10), plus its share of the splits |

⚠ **THE FIGURE SOMETIMES QUOTED AS *"about ten weeks"* IS §4's *"About nine and a half
weeks along the spine"* AND IS A DIFFERENT MEASUREMENT** — the **calendar** length of the
critical path `A → B → C → E → N` with two people on it, which deliberately excludes
everything running in parallel beside it. Ten calendar weeks and forty people-weeks are
both true of this plan and they answer different questions; quoting the first as the
backlog understates the work about fourfold.

⚠ **The whole-wave figures are this plan's own. The share of each SPLIT wave is a judgment
and is marked as one wherever it appears.**

### The best worked example is a partner that points both ways (2026-09-06)

**PO, verbatim:** *"In integration - for invoicecloud we have both. Cases together they hold
ours and we hold theirs. They will call our invoice and account APIs and we will call their
payment APIs for payment records . I hope we are handing both things together and for one
integration there can be multiple endpoints/ spit to integrate or connect"*

**InvoiceCloud is one relationship with two credentials pointing opposite ways** — they hold
a key we issued, we hold a credential of theirs. Put it through the three things:
**integrations owns both credentials and both connections** (issuing the one they hold,
storing the one we hold, and the lifecycle and health of each); **Runbooks owns what flows
across them** — which invoice, which account, which payment record, and when. It is a
cleaner illustration than the bank file, because the two halves point in opposite directions
and cannot be mistaken for one another.

⚠ **AND OUR MODEL CANNOT EXPRESS IT — `DEF-INT-4118`.** `registry.py:293` is `auth: Auth`,
**singular**, and this module's shipped `0001` migration enforces
`EXCLUDE … (connection_id) WHERE (is_active)`, so **the database refuses a second active
credential on a connection**. It lands on **built wave `E`**, and it is **repair work added
to integrations' remaining total, not taken out of it.** Every pending wave was re-checked
against it (`CR-069` §20.8) and **no verdict above moved** — which is itself evidence the
line is drawn in the right place, because **not one of `G`, `L` or `Q` knows what a
credential is.**

### Three things the ruling did not settle — ⚠ **TWO OF THEM WERE RULED ON 2026-09-06**

| | |
|---|---|
| **`OQ-INT-1727`** | Waves `C` and `D` shipped work now on the Runbooks side — the per-item run results, and the value mappings with screen **S143** live at `2.131.0`. About **three people-weeks** already spent. Move it, keep it as a named exception, or have Runbooks read it in place? |
| **`OQ-INT-1728`** ✔ **RULED 2026-09-06 — option (a)** | Does *record updates go to Runbooks* cover a write a **person** makes synchronously on a screen (wave `M`'s Create), or only unattended runs? **ANSWERED: only unattended runs — the synchronous write stays with the module that owns the screen, so nothing of wave `M` moves.** ⚠ **And the PO added a second requirement in the same sentence:** the same job must ALSO exist as a batch, **scheduled** and **run once on demand** — three ways to do one job, and the last two are not the same thing. See wave `M` below and the decision log, 2026-09-06. |
| **`OQ-INT-1729`** ✔ **RULED 2026-09-06 — option (a)** | Wave `F` is **running now** and the unbuilt half of `F2` is a record update. Stop it, or let it land here and move later? **ANSWERED: it stops at the door.** The feedback door is integrations' and is finished here; the record-marking and the suppression list wait for Runbooks. |

**Nothing in this section commissions work.** PO, 2026-09-05: *"right now notng to be done
… we will handle CR 69 and Runbook together once CR70 is completed."* A lane picking up a
wave below **still builds it as written** until that sequencing is reached — what this
section changes is who OWNS it and how the remaining backlog is sized, not what a lane
does tomorrow.

---

## 0 · What this is, and the three rules it obeys

**A PHASE is a launchable increment with a launch sentence.** `CR-069` §12 has five and they are kept verbatim;
the GL track — *"not a phase — it is a different project wearing the same word"* — is a sixth, parallel,
blocked track with its own waves. **A WAVE is a sprint-sized lane** (one or two people, one to two weeks) that
**ends in a demonstration** — a five-to-eight-step script clicked in the running product on the seeded fixture
— **and a version bump**. No wave ends in "the tables exist". A wave blocked to a boundary by an open question
still demonstrates the boundary: the stub, the sentence on the screen, the test that asserts the raise.
**A TASK is one r11 part** — `2a` backend · `2b` frontend · `2c` tests + data · `2d` prove it — or a `ground`,
`gate`, `doc`, `review` or `version` act, each with what it touches verified against the code at HEAD.

**The Product Owner's rules, verbatim (decision log 2026-09-03):**

> *"we ahve to execute in agile way - each phase/wave should produce tangila eoutcome"*
> *"at the end of each pahse we should abl to luanch some funtionlaity"*
> *"everything should be executed based on actual code, and rules that we place, also ensure you do web
> walkthorugh before you sign off the user story or build"*

**Definition of done for every task and every wave in this plan — three parts, all required:**

1. **Actual code.** Every task's *touches* column below was verified against the code at HEAD before it was
   written — the file, the model, the route, the component, with its path and line where useful. Where a document
   and the code disagreed, the code won and the task says so (§1 lists every such finding). A lane re-verifies at
   step 0 before it starts, because the tree moves.
2. **The rules.** Every task names the `BR-INT-`, B14 or CLAUDE.md rule it satisfies, and every wave's exit test
   asserts a rule — the three-exits secret proof, the `409` before posting, the eleven catalogues without the
   sentence — never an impression.
3. **The web walkthrough.** Every wave's `2d` task is a browser walkthrough of the running product in the repo's
   existing convention — `10-scripts/render-checks/cr069-<wave-letter>-<slug>.mjs` (Playwright on the
   preinstalled Chromium; the shape is `cr058-owner-import-and-sale.mjs`: `SMOKE_BASE`, a database nobody else
   seeds, computed style read in a real engine, screenshots saved). It clicks the wave's demo script on S8 / S141 /
   S142 / S143 against the seeded fixture and asserts the on-screen sentences. **A story is signed off only when
   its tests are green — on PostgreSQL where law 14 applies — that walkthrough has run green on the actual
   build, and the screens match this module's `08-screen-layouts.md`** (landed 2026-09-03 beside this plan, with
   `09-component-inventory.md` and the `wireframes/` frames; the layouts entry is what the walkthrough asserts
   against, and where a frame and a rule disagree the layouts file already says which wins).

**How a lane uses this plan.** Take one wave. Run `./10-scripts/check_head_current.sh` first (law 12). Do r11
**step 0** — re-read `01-open-questions.md`, `02-decision-log.md`, `10-defect-log.csv` and
`11-change-requests.md` for anything ruled since 2026-09-03, and grep before putting anything to the PO (law 13).
Assemble the **packet** (the wave's stories in `06-epics/`, the rules they cite verbatim from
`02-business-rules.md`, the field-map rows, the journeys in `04-flows.md` Part 2, the layouts entry). Build the
tasks in the order their `depends_on` allows, **writing back as you go** — a stale rule amended before building on
it, a question minted before code would guess, a defect filed before it is fixed. Work in a `git worktree`, commit
by pathspec, push after every task (law 11). Close the record — decision-log row, review-ledger row for every 🔒
file stating what was shown to the PO in plain English with a figure, `20-wave-tasks.tsv` rows moved to
`verify` then `done`, CHANGELOG and version — **before** review. Then the walkthrough is run green on the built
product, and only then is the story signed off.

**Version.** Scheme `<release>.<change>.<fix>` (`13-change-process.md` step 7); the product is `2.128.2` at HEAD
in both `07-frontend/package.json:4` and `06-backend/pyproject.toml:193`, held in lockstep by G35. **Each wave
lands as its own `<change>` bump with a CHANGELOG entry, and each phase's closing wave carries the phase's entry**
(`CR-069` §15). Absolute numbers are NOT pre-assigned here: sibling lanes bump the same literal concurrently —
`CHANGELOG.md` carries an *[Unreleased] 2026-09-03* entry (`DEF-3422`) waiting for exactly that reason — so each
wave takes **the next free `<change>` at push time**, re-derived from the tip (law 11: an allocated number is a
blob). The first wave to move the version attaches the waiting entry.

**Coverage.** Every one of the 34 substrate stories `US-INT-013`–`046` is placed in exactly one wave. Of the twelve
Part-1 stories, **eight are placed** — `001`, `002`, `004` (phase 1), `003` (phase 2), `005` (phase 3), `008`,
`010`, `009` (phase 4) — and **four stay deferred**: `006` and `007` are the W5/W6 email-activation stories (the
ESP's sending-domain checklist and the dispatcher's channel binding — the substrate makes them cheaper without
making them this CR's), `011` and `012` are the W7/W8 unlocks whose *Coming soon* card copy phase 1 renders from
the manifest disposition while their connects stay refused. A story placed in one wave may have named acceptance
tests landing in a neighbour (`US-INT-033`'s file-out cases land in wave J); the closing table says where.
§7 prints the check that was run over this file.


### The visual reference — the pack, then r10 (PO 2026-09-03)

**PO, verbatim: *"for Cr68, 69 and 70 - you will have to ensure you refer to screenshot we build and not just r10"*.**
Every wave's walkthrough below is judged against **`wireframes/frame-NN-N.png` in this module** — 41 frames from
the pack the PO uploaded — read through `08-screen-layouts.md`, which says which frames draw each screen, and
`09-component-inventory.md`, which names the pieces. **r10 stays the default for everything the pack does not
draw** (the shell, the table conventions, the button tiers). **Where the two disagree on one of these screens, the
pack wins and the divergence is stamped in `08-screen-layouts.md`** — hard-won law 6 read the other way round,
because r10 is the older drawing. A task is not done until its screen has been compared to its frame.

## 1 · The code at HEAD — what every task rests on, verified 2026-09-03

| Claim in the documentation | Measured at HEAD `b29edecd` | Consequence for the plan |
|---|---|---|
| The module is six files and eleven lines, all docstrings | **TRUE.** `06-backend/apps/integrations/` — `api.py` 1 · `models.py` 3 · `registry.py` 3 · `services.py` 2 · `tests.py` 2 · `__init__.py` 0; `migrations/` holds only `__init__.py`; **no `apps.py`**, though `"apps.integrations"` is in `INSTALLED_APPS` (`config/settings/base.py:99`) | Wave A creates `apps.py` for `AppConfig.ready()`; migration `0001` is the first |
| S8 has an Integrations tab | **A placeholder, not a grid.** `07-frontend/src/features/tenancy/SettingsPage.tsx:139-143` mounts the tab with `arrivesWithKey: "settings.arrivesWith.integrations"`; the sentence is `en.json:8845` and is in all eleven catalogues (`de · en · es-MX · es · fr-FR · hi · id-ID · it-IT · ja-JP · ko-KR · pt-BR`). **No `/integrations` API route is mounted anywhere** (`grep -rn "/integrations" 06-backend` finds only docstrings) | `US-INT-001`'s grid is unbuilt; wave A builds it and deletes the sentence in the same commit (`C1`) |
| `features/integrations/` is the frontend root | **Exists as a 106-byte README only**, and is **not** in `07-frontend/src/styles/route-b-migrated.txt` (2,976 lines, no match) | Wave A's first frontend commit adds it (B14 rule 21, `DEF-974`) |
| The six kernels exist | **TRUE.** `core/jobs.py` 763 (`set_job_handler` · `set_job_queue` · `job_queue` · `enqueue` · `dispatch_is_ready`) · `config/celery_routes.py` 115 (`route_job` reads `core.jobs.job_queue(kind)`) · `core/crypto.py` 583 (AES-256-GCM `sbh1:<kid>:…`, `EncryptedTextField`, `blind_index`, keyring from `SBH_FIELD_ENCRYPTION_KEYS`; **HUMAN-REVIEW-PENDING**, ledger row `09-human-review-ledger.md:395`, four judgments unsigned) · `core/idempotency.py` 252 (three billing keys) · `core/errors.py` 464 (`ApiError` family, `deny_as_not_found`, envelope with `trace_id`) · `core/partitioning.py` (yearly machinery) | Inherited, not written. The crypto sign-off is wave E's first task |
| Named queue pattern | `apps/billing/run_jobs.py:688-699` registers handlers and `set_job_queue(kind, BILLING_QUEUE)`; `docker-compose.yml` has `celery` (line 198, `-Q celery`), `celery-billing` (335, `-Q billing`), `celery-beat` (501, one replica); **no `celery-integrations`**. `10-scripts/gates/g59_billing_queue_split.py` checks the billing pair; gates register in `10-scripts/gates/run_gates.py` (`GATES`, line ~902 for G59) | Wave B adds routing and the worker in one commit and clones G59's clauses |
| No `beat_schedule` | **TRUE.** Nothing in `06-backend/config/`; `settings/base.py:238` and `:467` are comments saying so; `config/celery.py` (11 lines) reads `CELERY_*` from settings | Wave G's `CELERY_BEAT_SCHEDULE` is the product's first |
| `payments/webhooks.py` is a stub | **FALSE.** 577 lines (`CR-060` C21, 2026-09-03): `ingest` · `verify_signature` · `signing_secret` · `_existing_delivery` · `_replayed` · `_record` → `record_payment` with `SOURCE_WEBHOOK`; two independent guards `uq_payment_webhook_events_event` (`PaymentWebhookEvent`, `payments/0020`) and `uq_payments_webhook_key`; savepoint proved on PG | `T-9.04` is largely done; wave N's door **reuses** these guards and mints no second inbound path |
| `payments.channel` exists | **FALSE.** `payments/models.py:1120` is a comment; no `channel`, no `external_ref` column | Wave N1 is payments' own migration, run first and in parallel |
| The file guards need building | **Largely built in payments.** `payment_import.py:344` hashes the file (`lockbox.file_sha256`) **before** `parse_remittance_file` (line ~370) and refuses a duplicate naming the batch and its `committed_at` (`br_ref=BR-PAY-028`); rows commit inside a nested `transaction.atomic()` at lines 801-809 with the law-14 comment in place. `ledger/exports.py:317` `content_hash` and `:328` `overlapping_batch` carry period+target (`ExportBatch` UNIQUE on tenant · period · target, `ledger/models.py:850`) | Waves I and J **wrap** these as connections with run rows; they do not rebuild them. The run row's `input_hash` and the refusal *naming the first by date* are the new parts |
| The accounting target column mixes a place with a format | **TRUE.** `ledger/models.py:832` `target = models.TextField()  # EXPORT_TARGETS` — two places, two shapes (`I-16`) | Wave J files the defect first, then `destination × codec` on the connection |
| `smtp_secret_ref` names an environment variable | **TRUE.** `notifications/sender_config.py:50` (*"holds the NAME of a secret"*), column `notifications/models.py:746`, served by `settings_api.py:382`, migration `notifications/0015` | Wave E's fold (`C35`) is a data migration reading it once |
| Delivery counts read *not reported* | **TRUE.** `notifications/delivery_counts.py:328` serves `not_reported`; `provider_seam.py` is the ONE seam and says email does not send this release | `BR-INT-027` already enforced; wave F keeps it so for mailbox connections |
| No machine authentication | **TRUE.** `settings/base.py:187` `DEFAULT_AUTHENTICATION_CLASSES` = `apps.identity.auth.IdentitySessionAuthentication` (`identity/auth.py:108`) only | Wave R mints identity's companion story before building against it (`I-9`) |
| Two live third-party calls have no connection record | **TRUE.** `apps/metering/geocode.py` (Census, `CR-028` D6, run by `geocode_premises`) and `features/assets/AssetMapTab.tsx:51` `ESRI_TILE_URL` | Defects, not changes (`CR-069` §0.3); filed in wave M before the manifests carry them |
| Premises carry the GIS columns | **TRUE.** `metering/models.py`: `postal_code` 276 · `inside_city_limits` 308 · `external_ref` 390 · `lat`/`lng` 404-405 · `custom_data` 413; `services.update_premises` at 860, `supersede_read` at 7344 | Waves L, M, Q write only through those services |
| The chart carries two vendor columns | **TRUE.** `ledger/models.py:348-349` `qbo_ref`, `xero_ref` | Wave D adds the table BESIDE them (`OQ-INT-1480`) |
| A named-format registry exists in billing | **TRUE.** `apps/billing/print_formats.py` (`CR-053` task 14), one format, read by `print_api.py` | Wave D lifts it into `codecs.py` and points billing at the one registry |
| The reversal reasons are four and signed | **TRUE.** `payments/models.py:217` `REVERSAL_REASONS`; `tenancy/models.py:927` `PaymentMethod` is the tenant-extensible tender lookup | Wave D's mapping rows point at these; `R02` stays `OQ-INT-1487` |
| CI proves things on PostgreSQL | **Only the migrations.** `.github/workflows/ci-backend.yml` boots `postgres:16` and runs `manage.py migrate` against it; `pytest -q` (line 97) runs the SQLite suite. ⚠ **CORRECTED 2026-09-03 (wave A lane): there is NO `06-backend/tests/pg/` folder.** The PostgreSQL-only tests are seven files `06-backend/tests/test_*_pg.py` (incl. `test_def_2444_law14_savepoint_pg.py`), each carrying `tests.isolation_helpers.requires_postgres` so it SKIPS on SQLite — and **no workflow runs them under PostgreSQL settings** | Wave A adds a CI step running `pytest tests/test_*_pg.py` under `config.settings.local` + `DATABASE_URL` (law 14) so every later PG proof runs in CI; the new file is `tests/test_us_int_014_pg.py`, beside the others |
| Journeys `J48`–`J59` exist | **Described, not written** — `04-flows.md` Part 2 reserves them; `08-qa/01-e2e/journeys/` has `J14`, `J17`, `J19` (each gains a leg) | Each demonstrating wave writes its journey file |
| The badges for `S141`–`S146` | **Not allocated.** `10-scripts/gates/g29_allocated_badges.txt` (119 lines) has no INT row; `07-frontend/src/routing/screenIds.ts` keeps every Settings tab at `S8` | A separate allocation, named as task B7 |
| The 🔒 files are guarded | **No integrations glob** in `10-scripts/gates/human_owned.txt` | Wave A adds the globs so G7 sees `inbound.py`, `runners/reconcile.py`, `seams/metering.py`, `seams/payments.py`, `migrations/*rls*` |
| Fixture tenants and actors | `seed_demo` provisions **Brazos Bend Utilities**; Silver Creek Water and Lone Star Ridge WSC are named in `tenancy/brand.py`, `services.py` docstrings and the stories, not seeded; Alex Reed and Priya Menon are story actors, not seed rows | Each wave's `2c` seeds what its demo needs; isolation tests provision the second tenant |

## 2 · The phases — six increments, each with a launch sentence

| Phase | LAUNCH (`CR-069` §12, kept) | Product wave (r3 W0–W8) | Exit test — a demonstration, and the rule it asserts | Stories | Waves | Rollback (§16) |
|---|---|---|---|---|---|---|
| **1** | **The Settings screen lists every integration we will ever offer, and honestly says none is set up** — and a connect attempt on a coming-soon provider is refused by the API, not just by a greyed-out button | W4 (connections surface) | Wave B's walkthrough: seventeen cards from the registry all *Not set up*; `POST /integrations/payments_card/connect` refused in ≤ 6 words with the database byte-identical (`BR-INT-037`, `BR-INT-001`, `BR-INT-003`) | 013 · 014 · 015 · 016 · 017 · 018 · 019 · 020 · 021 · 037 · 039 + Part 1 `001` · `002` · `004` | A · B · C · D | Clean — no partner holds anything of ours |
| **2** | **A utility connects its own mail server and sends real email through it** | W5 (comms connections); customer SENDING stays the W6 flip (`BR-INT-007`) | Wave E's walkthrough: a wrong password reads *the mail server rejected the password*, and the credential is **provably absent from the database, the logs and the audit trail** — three assertions (`BR-INT-003`, `BR-INT-019`) | 022 · 023 · 024 · 025 · 026 + `003` | E · F | Clean |
| **3** | **A utility connects Google or Microsoft, and the token renews itself** | W5 / W6 | Wave H's walkthrough: an expiring token raises a **dated** warning eleven days ahead, and re-authorising **keeps the connection's entire run history** (`BR-INT-042`) | 027 · 029 · 030 + `005` | G · H | Clean |
| **4** | **Files out and files in — the accounting export, then bank and lockbox import** | W4 (bank/lockbox) · W5 (accounting export) | Wave I's walkthrough: the same bank file uploaded twice records the second as a **refused duplicate naming the first** — **on real PostgreSQL** (`BR-INT-020` C, `BR-INT-023`, law 14) | 028 · 031 · 032 · 033 · 034 🔒 · 035 🔒 · 036 ⚠ · 038 · 042 ⚠ + `008` · `009` · `010` | I · J · K · L · M | **Disable the connection and keep the runs, never drop the tables** — a file has left the building and an import has created payments |
| **5** | **A payment taken at a kiosk appears on the customer's account by itself** | W7 (payment rails) | Wave N's walkthrough on a real captured payload: a replayed notification is **applied exactly once**, answered **409 before anything is posted**, and a return carrying the same id **is not mistaken for a duplicate** (`BR-INT-020` D, `BR-INT-030`, `BR-INT-045`, `BR-PAY-003`) | 044 · 045 🔒 ⚠ · 046 ⚠ · 043 🔒 ⚠ | N · O · P · Q | **Cannot be rolled back in the direction that matters** — a charge that reached a bank is not undone by a migration |
| **GL** | *Not a phase — a different project wearing the same word.* A finance system reads our payments and bills on its own schedule, and every read is a row a manager can see | W5 (finance) — parallel, **blocked `OQ-INT-1481`** | Wave S's walkthrough against the test partner: three `inbound_read` runs at 02:41, a read from outside the allowlist refused revealing nothing, the enable path raising until ruled (`BR-INT-035`, `BR-INT-044`) | 040 ⚠ · 041 ⚠ | R · S | Clean until enabled; after that, disable and keep the access log |

⚠ marks a story built to the boundary and stubbed `NotImplementedError("OQ-INT-####")`. 🔒 marks a sensitive path
(a `HUMAN-REVIEW-PENDING` file and a review-ledger row in plain English with a figure — `US-INT-034`, `035`,
`040`, `043`, `045`; and `core/crypto.py`'s sign-off before wave E stores a real credential).

## 3 · The waves

Wave letters are unique across this CR. **Size:** S ≤ 1 day · M 2–3 days · L 4–5 days, per person. **Demo
scripts** are clicked by the walkthrough named in the wave's `2d` task; fixture tenant **Brazos Bend Utilities**
(`seed_demo`) unless said, with **Silver Creek Water** and **Lone Star Ridge WSC** as the second tenant; actors
**Alex Reed** (System Admin) and **Priya Menon** (Billing Clerk), as the stories use them.

---

### Wave A — the grid that tells the truth · phase 1

✅ **STAYS WITH INTEGRATIONS — 2026-09-06 (`CR-069` §20.4).** A catalogue of what can be
connected and the tables a connection lives in: **building a connection**, item (1).
Nothing here is transformed. **BUILT.**

**Goal a clerk can see:** Alex opens Settings → Integrations and, where a dashed box with a sentence stood, sees
seventeen cards drawn from the registry, every one reading *Not set up*, the payment-kiosk card listing three
things it does.
**Stories:** US-INT-014 · US-INT-013 · US-INT-018 · US-INT-001
**Depends on:** nothing — this is day one. **Blocked by:** nothing.
**Version:** the next free `<change>` (indicative `2.129.0`); attaches CHANGELOG's waiting *[Unreleased]* entry.
**Size:** two people, two weeks.

| Task | r11 | What it touches — verified at HEAD | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **A1** | ground / doc | **`C34` — B2 FIRST.** `04-docs/02-decisions/02-database-design-brief.md` gains `### Module: integrations` under §2 (the five tables' DDL from this module's `03-field-map.md` §5 — the brief's §2 has `tenancy … audit` and no integrations section), a §3 RLS row per table, a §5 partition row for `integration_run` (yearly), and **Addendum r22** (r21 is the last at HEAD). `03-field-map.md` discrepancy `I-2` → CLOSED **in the same commit**. This commit must precede A3's in `git log` (`US-INT-014` TC-7) | 014 · CLAUDE.md hard rule 1 · `BR-INT-039` | — | `C34` | S |
| **A2** | ground | `07-frontend/src/features/integrations/` (README only at HEAD) is listed in `07-frontend/src/styles/route-b-migrated.txt` **in the first frontend commit** (B14 rule 21). ⚠ **AMENDED 2026-09-03 by the wave A lane (`DEF-INT-3560`): the four `human_owned.txt` globs — `06-backend/apps/integrations/inbound.py`, `runners/reconcile.py`, `seams/metering.py`, `seams/payments.py` — are ASKED FOR in the review-ledger row, not added by the lane.** G53 and the guard list's own header say adding a file to that list is a process event and the Product Owner's call, never a lane's; this row said *gains globs* and contradicted a ratified gate. (`**/migrations/*rls*` already matches the RLS migration.) `.github/workflows/ci-backend.yml` gains a step running the PostgreSQL-only tests — **`pytest tests/test_*_pg.py -q`, because there is NO `tests/pg/` folder at HEAD (§1's row below was wrong; corrected 2026-09-03): the seven PostgreSQL-only files live beside the others as `tests/test_*_pg.py` with a `requires_postgres` skip** — against the `postgres:16` service it already boots (`DJANGO_SETTINGS_MODULE=config.settings.local`, `DATABASE_URL=…sbh_ci`, `JOBS_EAGER=false`) — no workflow names `tests/pg` at HEAD; prove it RED by breaking a savepoint (law 7) | 014 · B14-21 · G7 · law 14 | — | — | S |
| **A3** | 2a | `apps/integrations/models.py`: `IntegrationConnection` (no secret material — `config` jsonb non-secret), `IntegrationCredential` (`payload_enc = core.crypto.EncryptedTextField`, `blind_index`, `masked_hint`, `expires_at`), `IntegrationRun` (five counts, seven outcomes, `provider_error`, `input_hash`, `artifact_link`, `trace_id`), `IntegrationTargetReference` (UNIQUE on the external side), `IntegrationConsent` (in the brief; nothing writes it). `migrations/0001_initial.py` — `UNIQUE (tenant_id, provider_key, environment)`, `UNIQUE (connection_id, version)`, `EXCLUDE (connection_id WITH =) WHERE (is_active)` as raw SQL, `PARTITION BY RANGE (started_at)` yearly via `core/partitioning.py`, an append-only trigger on finished runs. `migrations/0002_rls_force.py` — RLS `FORCE` on all five (matches `human_owned.txt`'s `*rls*` glob: `HUMAN-OWNED` + `HUMAN-REVIEW-PENDING` + a ledger row). `selectors.py` reads · `services.py` writes (skeleton; B1 boundary) | 014 · hard rule 1 · `BR-INT-025` · `026` · `032` · `036` · `039` | A1 | `T-1.01`–`T-1.20` group | L |
| **A4** | 2a | `apps/integrations/registry.py` becomes THE registry: `Manifest · Operation · Field · Conformance` as frozen dataclasses; `apps/integrations/manifests/` — **seventeen files** in `US-INT-013` §4's order (`email_microsoft · email_google · email_smtp · email_bulk · bank_lockbox_file · accounting_file · print_vendor · payments_kiosk · payments_card · meters_neptune360 · meters_mdm · gis_city · map_tiles_public · geocoder_census · gl_partner · sms_twilio · sso`); **new `apps/integrations/apps.py`** registering them at `AppConfig.ready()` (the app is in `INSTALLED_APPS` at `base.py:99` with no config class). **Refuses at load, never at run time:** an operation missing `idempotency.mode` or `completion` · `respond_after` before `authenticate` · a codec name not registered (D1's registry — until D1 lands, the codec vocabulary is a constant here) · `certified` with no `certificate_id` · an unknown field kind · zero operations. The registry reads nothing and calls nothing | 013 · `BR-INT-028` · `037` · `043` · `053` · `030` · `033` · `001` | — (parallel with A3) | `T-1.01`–`T-1.20` group · `C1` `C2` `C3` `C6` `C7` | L |
| **A5** | 2a | `apps/integrations/api.py` + a URLconf mounted in `config/urls.py` (nothing at HEAD): `GET /integrations` — every manifest joined to **this tenant's** connection state; `operations[]` per connection `{name, direction, initiative, state, last_run_at, last_outcome}`; state words *Working · Not working · Not tested yet · Not set up · Turned off*, plus the **computed** display state *Reading from us* (`08-screen-layouts.md` S8 — the status enum keeps five values). This is `US-INT-004`'s consumer read-model, a service function in `selectors.py`; consumers never touch the tables | 013 · 018 · 001 · 004 · `BR-INT-002` · `004` · `028` | A3 · A4 | `C1` | M |
| **A6** | 2b | `features/integrations/IntegrationsTab.tsx` mounted from `SettingsPage.tsx:139-143` **replacing** `arrivesWithKey`; template **I1** from `08-screen-layouts.md` (PageHead · `CategoryFilter` **generated from the registry's categories** · `CardGrid` · `ProviderCard` with the direction kicker · `StateWord` — one of the four components `09-component-inventory.md` says the staff kit lacks); operation rows under a multi-operation card with **no aggregate word**; the action button arrives in B4 — **no button wired to nothing in this wave (law 2)**. **Delete `settings.arrivesWith.integrations` from all eleven catalogues in this commit** (`C1`); add the `integrations.*` keys to all eleven (g15). `screenIds.ts` unchanged (S8 already routed) | 001 · 018 · 013 · `BR-INT-001` · `028` · `037` · B14 rules 21 · 31 · 32 · g13 · g15 | A5 · A2 | `C1` | L |
| **A7** | 2c | Tests named for their TCs: `US-INT-013` TC-1..7 (TC-5 is the grep gate) · `US-INT-014` TC-3, 5, 6, 7 on SQLite and **`tests/pg/test_us_int_014_pg.py`** TC-1 (EXCLUDE), TC-2 (no tenant → zero rows on five tables), TC-4 (append-only trigger) · `US-INT-018` TC-1..6 (through seeded run rows written by `services.py`) · `US-INT-001`'s TCs. Second tenant Lone Star Ridge WSC provisioned by the test fixture for TC-7 | 013 · 014 · 018 · 001 | A3–A6 | — | M |
| **A8** | gate | Three gates proven RED first, registered in `run_gates.py`'s `GATES` in the same commit (G42 contract: `run()` + `__main__` + `selftest()`); next free numbers are **G75 onward** (⚠ corrected 2026-09-03: `g74` is the highest file at HEAD, not `g61` — thirteen gates landed between the plan's HEAD and the build; take them at push): **(i)** no `EncryptedTextField` and no column matching `secret|token|password|payload` on `IntegrationConnection` — RED by adding `api_key_enc` (`US-INT-014` TC-3; `CR-069` §13 gate 2's schema half); **(ii)** every declared operation names `idempotency.mode` AND `completion` — RED by stripping one from `manifests/email_smtp.py` (§13 gate 3); **(iii)** `provider_key ==` appears nowhere outside `adapters/` and `manifests/` — RED by `if provider_key == "email_smtp"` in `services.py` (§13 gate 1, `US-INT-013` TC-5) | 013 · 014 · `BR-INT-037` · law 7 | A3 · A4 | §13 | M |
| **A9** | 2d | **`10-scripts/render-checks/cr069-a-grid-not-set-up.mjs`** — the demo script below, asserting: seventeen `ProviderCard`s · every `StateWord` reads *Not set up* · the kiosk card has three operation rows · no string matches `BR-[A-Z]+-\d+` or a UUID · the `arrivesWith` sentence is absent · the utilities compiled (computed style) · no sideways scroll at 1440 · screenshots. Plus the terminal proof quoted in the PR: a manifest missing its completion mode refuses to start naming `payments_kiosk · Payments` | 013 · 018 · 001 · B14 31 · 32 · law 6 | A6 · A7 · A8 | — | S |
| **A10** | doc / version | CHANGELOG entry (attach the waiting *[Unreleased]* entry if still unversioned) · `package.json` + `pyproject.toml` bumped together (G35) · decision-log row for the wave's judgments (the seventeen keys; no button in A; the computed *Reading from us*) · `20-wave-tasks.tsv` rows A1–A10 → `verify` → `done` · review-ledger row for `0002_rls_force` | — | A9 | — | S |

**Demo script A (Alex Reed):** 1 sign in to Brazos Bend → 2 Settings → 3 the Integrations tab — the dashed box and
its sentence are gone → 4 count seventeen cards under the category chips, each *Not set up* → 5 the Payment kiosk
card: *Account lookup · Payments · Returns*, each *Not set up*, and no headline word above them → 6 sign in as
J. Okafor of Lone Star Ridge — the same seventeen, nothing of Brazos Bend → 7 in the terminal: start the app with a
manifest missing `completion` — it refuses, naming the provider and the operation.
**Exit test (asserts a rule):** all seventeen cards come from the registry and none from React (`BR-INT-037`); the
eleven catalogues no longer contain `settings.arrivesWith.integrations` (`C1`); with no `app.tenant_id` set, all
five tables return zero rows on PostgreSQL (hard rule 1).

**Wave A — AS BUILT (2026-09-03, the CR-069 wave A build lane; product `2.129.0`/`2.130.0`). Stamped
2026-09-05 by the wave F lane, five waves late — see the note under wave F for why that is now the
thing this section exists to prevent.** Verified from the code at `eea15784`, not from the task table:

* **`A3` — five tables, two migrations.** `apps/integrations/models.py` (376 lines) holds
  `IntegrationConnection` · `IntegrationCredential` · `IntegrationRun` · `IntegrationTargetReference` ·
  `IntegrationConsent`, created by `migrations/0001_initial.py` (572 lines: the partitioned parent, the
  append-only trigger, the `EXCLUDE`/unique-index pair for one active credential) with
  `0002_rls_force.py` (100 lines) immediately after.
* **`A4` — the registry is real and it holds EIGHTEEN manifests, not seventeen.** `registry.py` is 576
  lines; `manifests/` carries the seventeen `US-INT-013` §4 names **plus `payments_sandbox.py`**, added
  later by the `CR-068` phase-5 lane (the test payment provider, PO ruling 2026-09-05). A lane counting
  seventeen against this directory will find eighteen and the extra one is legitimate.
* **`A5`/`A6` — the read and the grid.** `api.py` (249 lines) and `selectors.py` (377);
  `features/integrations/IntegrationsTab.tsx` (20,609 bytes) with its own test file.
* **`A8` — the three gates are `G75` · `G76` · `G77`**, all three registered in `run_gates.py`
  (`g75_connection_table_no_secret` · `g76_operation_modes` · `g77_provider_key_branches`).

---

### Wave B — the modal, the gate, the queue · phase 1 (the phase-1 LAUNCH)

✅ **STAYS WITH INTEGRATIONS — 2026-09-06 (`CR-069` §20.4).** Items (1) and (3).
⚠ **The queue built here is NOT the scheduler** — a queue is how a connection's work runs;
deciding *when* it runs is scheduling and left with wave `G`. **Runbooks runs on this
queue and does not get a second one** (*"one scheduler, not two"*). **BUILT.**

**Goal:** every card opens the same modal; connecting the kiosk asks for a key and nothing about bearer tokens;
a connect on a coming-soon card is refused by the server; a test request is a job on its own queue with its own
worker.
**Stories:** US-INT-019 · US-INT-002 · US-INT-015 · US-INT-016 · US-INT-017 · US-INT-004
**Depends on:** A. **Blocked by:** nothing. ⚠ `OQ-INT-1479` was RULED on 2026-09-04 — *"(b) clerk may test, never change"* — which NARROWS the signed rule that Settings is System Admin only, for exactly one action: a clerk may press *Test it now* and may not see, set or replace a credential. The modal still ships Admin-only until that permission exists; adding it is now a build rather than a question.
**Version:** next free `<change>` (indicative `2.130.0`). **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **B1** | 2a | `apps/integrations/adapters/base.py` — the protocol, four methods and only four: `validate(config) → FieldErrors` · `test(conn) → TestResult` (one sentence a clerk can read) · `execute(conn, work) → RunResult` (per-item outcomes, never a boolean) · `describe(conn) → str` (masked); `adapters/__init__.py` key → class registry; **`conformance.py`** — the kit every adapter runs unchanged, driven off the manifest (`US-INT-015` TC-6, 37 cases), with fixture adapters *returns-True* (TC-3), *slow 90 s — sleeps, never raises* (for F), *no-count 200* (for C). The plaintext credential exists at exactly one point — in memory, inside `test()` or `execute()` | 015 · `BR-INT-004` · `019` · `038` · `003` | A4 | `C6` | L |
| **B2** | 2a | `apps/integrations/apps.py`: job kinds `integration.run · integration.test · integration.sweep_due · integration.sweep_expiry · integration.inbound_process` via `core.jobs.set_job_handler` + `set_job_queue(kind, "integrations")` (the `run_jobs.py:688-699` pattern; `config/celery_routes.py` already routes by kind). **The job row is written before the broker message and before the 202.** **`docker-compose.yml` gains `celery-integrations`** (`-Q integrations`, `entrypoint: []`, `CMD-SHELL` healthcheck, a CPU limit — G59's clauses) **in the same commit**; the default worker stays `-Q celery`. `runners/` — the four quadrants as files (`deliver.py` · `fetch.py` · `serve.py` · the inbound door in `inbound.py`) with the runtime wiring to `core.jobs` retry; the runner with no connector behind it (serve) is built here on purpose. ⚠ **AMENDED 2026-09-03 by the wave B lane: the door is `apps/integrations/inbound.py` at the module root — the path A2's review-ledger row asks the PO to put on the guard list — not `runners/inbound.py`; `runners/__init__.py` maps the `in · them` quadrant to it** | 016 · `BR-INT-041` · `022` · TD-17 · `DEF-320` | A3 | `T-1.01`–`T-1.20` group | L |
| **B3** | 2a | `api.py` writes — `US-INT-002`'s four ratified endpoints `POST /integrations/{key}/connect` · `POST …/test` (202 + poll url) · `PATCH /integrations/{key}` · `DELETE /integrations/{key}`, plus `POST …/credential` and `POST …/run`. **Coming-soon refusal** `INT_COMING_SOON` (≤ 6 words, names the wave in words, `message_key` in all eleven catalogues — g32 baseline 0) on every write route; `INT_UNKNOWN_KEY` → 404 identical to any absent resource; a malformed connect on a LIVE key runs `adapter.validate()` before any write and stores **nothing** — not the connection, not a partial credential. Audit rows `integration.connected · test_run · updated · disconnected · connect_refused` with masked refs (`US-INT-004`); the subprocessor feed derived from live connections | 002 · 017 · 004 · `BR-INT-001` · `002` · `003` · `014` · `037` · B14 rule 33 | A5 · B1 | `C2` | L |
| **B4** | 2b | S141 — `features/integrations/ConnectModal.tsx`, template **I2**: *Connect · <name>* · *How to sign in* (`Segmented`, from the manifest) · *Environment* · **the `FieldSlot`** rendered from `manifest.fields` with the closed kind vocabulary `text · email · host · port · secret · select · redirect · mapping_editor · issued_secret` and **no fallback branch** (`FieldSlot` is the first of the four components the staff kit lacks) · *How often* · footer *Save and test · Cancel · Testing sends one real message to an address you type.*; the `redirect` body is a button and a return trip with **Cancel only** (*the round trip is the save*); the Manage view (describe line, connected by, state, expiry sentence slot, last runs slot, **Test it now · Replace password · Disconnect** danger tier). The action button lands on A's cards (state → button map from `09-component-inventory.md`, one map); coming-soon cards get the dashed `aria-disabled` Connect and the server refuses too. Admin-only (`OQ-INT-1479` boundary) | 019 · 002 · `BR-INT-043` · `026` · `019` · B14 rules 5 · 6 · 21 · 31 · 32 · 33 | B3 · A6 | `C2` · `T27` (epic cite, 70-register) | L |
| **B5** | 2c | Tests: `US-INT-019` TC-1..8 (TC-7 asserts every `features/integrations/**` file is on the migrated list and Disconnect renders `data-variant="danger"`) · `US-INT-017` TC-1..6 (TC-1 row counts unchanged and no log line carries the key) · `US-INT-015` TC-1..7 against the recorded SMTP fixture (host `smtp.brazosbend.example`, good `Ew3!kQ9-lockbox`, bad `hunter2 ` with the trailing space) · `US-INT-016` TC-1..6 with `JOBS_EAGER=false --reuse-db` · `US-INT-002` and `US-INT-004` TCs | 019 · 017 · 015 · 016 · 002 · 004 | B1–B4 | — | M |
| **B6** | gate | Two gates RED first, registered the same commit: **the queue pair** — clone G59's clauses for `integrations` (routing ⇄ `celery-integrations` consumer; default worker not draining it; entrypoint cleared; healthcheck form) — RED by deleting the compose service (`US-INT-016` TC-2); **no `POST /integrations/{key}/send`** anywhere in a URLconf (`BR-INT-008`; the overview promises this gate) — RED by adding the route. ⚠ **`BR-INT-008` AMENDED 2026-10-02** (PO: *"B · Keep it and change the rule, because it only passes the job on."*): wave J's `POST /integrations/{key}/export` hands the job to the runner with no figure and no file, and `G79` names it as its one ruled exception. ⚠ **AMENDED 2026-09-03 by the wave B lane: the numbers are `G79` (no send route) and `G80` (the queue pair) — `G78` was taken by the CR-070 wave A lane in the same hour, and the queue gate's RED proof is the worker's `-Q integrations` REMOVED, not the service renamed: a consumer under another name still consumes, and the gate was right to stay green on a rename** | 016 · `BR-INT-041` · `008` · law 7 | B2 · B3 | — | S |
| **B7** | doc | **Six badges for `S141`–`S146` allocated into `10-scripts/gates/g29_allocated_badges.txt`** — a separate allocation in that file's own row shape (`ID   path  — reason`), performed by this wave's lane as the first screen mounts and **not decided in this plan**; `screenIds.ts` rows follow as each screen routes (S141 here; S142 in C; S143 in D; S144 in R; S145 in P). ⚠ **AMENDED 2026-09-03: wave D mounted S143 first and allocated all six as `INT-01`–`INT-06` in that file; wave B inherits `INT-01` for the modal and adds no row — S141 is a modal over S8 and has no route of its own** | 019 · G29 · `CR-069` §9 | B4 | — | S |
| **B8** | 2d | **`cr069-b-modal-and-refusal.mjs`**: *Connect · Custom SMTP* shows five fields and the footer sentence · *Connect · Microsoft 365* shows one field and a *Sign in with Microsoft* button, and **no password input exists in the DOM** · the Payment card card reads *Coming soon · W7* with a dashed Connect · `POST /integrations/payments_card/connect` with `sk_live_51H…` → the refusal in ≤ 6 words, `integration_connection` and `integration_credential` row counts unchanged (read back through the test database) · `docker compose config` lists `celery-integrations` · screenshots | 019 · 017 · 016 · `BR-INT-001` · `003` · B14 rule 33 | B4–B7 | — | S |
| **B9** | doc / version | CHANGELOG · version lockstep · decision-log row · TSV rows · **phase 1 LAUNCH declared** (the grid + the refusal) | — | B8 | — | S |

**Demo script B (Alex Reed):** 1 Integrations → *Connect* on Custom SMTP → 2 five fields, environment, cadence,
*Save and test*, and the sentence under it → 3 Cancel; *Connect* on Microsoft 365 → one field and a sign-in
button, no password field → 4 Cancel; *Connect* on Payment kiosk → a Key field and the allowed addresses, nothing
about bearer tokens → 5 the Payment card card: *Coming soon · W7*, its Connect dashed → 6 from the API, connect to
`payments_card` with a real-looking key → refused in six words or fewer; the database is unchanged → 7 press *Test
it now* on a connection → *202*, a poll link, and the job row exists before the message → 8 `docker compose
config` shows the `celery-integrations` worker on `-Q integrations`.
**Exit test (asserts a rule):** `BR-INT-001` — refused at the API, not only the button; `BR-INT-003` — zero secret
persistence, proved by row counts and a log grep; `BR-INT-041` — routing and consumer land together, and the gate
goes red when either is missing. **This is `CR-069` §12's phase-1 exit test.**

**Wave B — AS BUILT (2026-09-03, the CR-069 wave B build lane; product `2.131.0`/`2.132.0`). Stamped
2026-09-05 by the wave F lane.** Verified from the code at `eea15784`:

* **`B1` — the protocol and the kit.** `adapters/base.py` (369 lines, four methods and only four) and
  `conformance.py` (450). **The `slow` fixture wave F depends on EXISTS and really sleeps** —
  `conformance.py:439` is a bare `time.sleep(self.SLOW_SECONDS)`, which is the one property
  `US-INT-022` TC-2 turns on.
* **`B2` — the queue.** `apps/integrations/jobs.py` (223 lines) registers `integration.test` and
  `integration.run` and routes all five kinds to the `integrations` queue; `docker-compose.yml:501`
  carries the `celery-integrations` worker. `runners/deliver.py` · `fetch.py` · `serve.py` exist;
  the inbound door is `inbound.py` at the module root, as the wave B lane's own amendment says.
* **`B3`/`B4` — the writes and the modal.** `api.py`'s six routes; `ConnectModal.tsx` (31,733 bytes)
  with a DOM test beside it.
* **`B6` — the two gates are `G79` (no send route) and `G80` (the queue pair)**, both registered.
* **`B7` — the six badges are allocated** as `INT-01`…`INT-06` in `g29_allocated_badges.txt`.

---

### Wave C — the run record, and the word for not knowing · phase 1

÷ **SPLITS — 2026-09-06 (`CR-069` §20.4), AND PART OF IT IS BUILT ON THE RUNBOOKS SIDE.**
`BR-INT-054`(3) keeps the connection's own run row here: *this connection authenticated,
pulled a file, took three seconds* is **lifecycle**, item (3). But this wave also shipped
**per-item results** — the `items` column, `runs.py`, the `RunCard`, and summaries like
*86 of 93 · 7 bad addresses*. A record of what happened to row 412 **inside** the file is a
record of **processing**, which the ruling gives to Runbooks. ⚠ **This is BUILT (1.5
people-weeks) and what happens to it is `OQ-INT-1727` — the PO's to answer, not a lane's.**

**Goal:** a support agent reads *86 of 93 · 7 bad addresses* on the connection's detail and finds a run from eight
characters read down the phone; a provider that will not say how many it accepted is *Unconfirmed*, never green.
**Stories:** US-INT-020 · US-INT-021
**Depends on:** A · B (the runtime writes the rows). **Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** one person, one and a half weeks. **Runs in parallel with D.**

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **C1** | 2a | `services.py` run lifecycle — `start_run / finish_run` writing `integration_run`: five counts; **outcome set here, never by an adapter** — `succeeded` only when `attempted = succeeded + failed + skipped` AND the far end confirmed a count, `partial` when some failed and the counts reconcile, **`unconfirmed`** otherwise; `summary` in plain language with no rule id; `provider_error` **scrubbed by the adapter** (email addresses, account numbers, postal addresses) and stored in its own column; `trace_id` eight characters from `core/errors.py`'s trace; `artifact_link` via `core.jobs.succeed(job_id, result_link)`. Red-first: the always-`succeeded` stub fails the no-count fixture (`US-INT-021` TC-2, recorded) | 020 · 021 · `BR-INT-018` · `039` · `040` · `020` · hard rule 4's shape | B1 · B2 | `C10`'s vocabulary · `C26` reserved | M |
| **C2** | 2a | `GET /integrations/{key}/runs` (existing pagination kernel; filters operation · outcome · trigger; **`provider_error` never in the list payload**) · `GET …/runs/{run_id}` (per-item results, artifact, `provider_error` to the owning tenant only); cross-tenant ids → 404 identical to absent | 020 · `BR-INT-039` · hard rule 1 | C1 | — | M |
| **C3** | 2b | S142 — `features/integrations/ConnectionDetailPage.tsx` at `/:tenant/settings/integrations/:key`, template **I3**: `DetailHead` (describe line · state word · meta) → `WarningBox` / `BudgetLine` slots (H, G) → `OperationsTable` → `RunsTable` *RECENT ACTIVITY* — the last twenty, grouped by operation, B14 rule-20 table, counts written as a clerk reads them (*93 of 93* · *86 of 93 · 7 bad addresses* · *Unconfirmed · 93 sent, provider did not say*), row action icon opens the run (template **I4** `RunCard` with **`CountTile` that renders a dash** where a number would be a claim — the second missing component); `changed` shown only for reconcile operations; trace id labelled *Support reference*; `screenIds.ts` row for S142 | 020 · 021 · B14 rules 15 · 20 · 31 · 32 | C2 | `C10` · `C13`'s fifth count | L |
| **C4** | 2c | `US-INT-020` TC-1..7 (TC-3 PG trigger; TC-6 the leak-path fixture *"…for account 4471-0021 at 1408 Pecan St, Lone Star Ridge"* scrubbed, absent from list/audit/notification) · `US-INT-021` TC-1..6. **Seed** Brazos Bend `email_smtp` runs — 1 Sep `93/93 succeeded` · 1 Aug `93/86/7 partial` with the seven addresses · 1 Jul `93/0 unconfirmed` · a manual `failed` run *the mail server rejected the password* with trace `a7f3c9e1` — the walkthrough needs them | 020 · 021 | C1–C3 | — | M |
| **C5** | 2d | **`cr069-c-run-record.mjs`**: S142 for the Billing mailbox → twenty rows newest first → the 1 Aug row reads *86 of 93 · 7 bad addresses* → open it: seven addresses each with the mailbox's own sentence → the 1 Jul row reads *Unconfirmed · 93 sent, provider did not say* and is not green → search *a7f3c9e1* finds the failed test → no `BR-` string, no UUID on screen · screenshots | 020 · 021 · `BR-INT-018` · B14 31 · 32 | C3 · C4 | — | S |
| **C6** | doc / version | CHANGELOG · lockstep · decision-log row (the scrubbing rule, PROPOSED in the story) · TSV | — | C5 | — | S |

**Demo script C (support, then Alex):** 1 support is read *a7f3c9e1* over the phone → 2 one search on S142 finds
the run, its connection and the provider's own sentence → 3 open the Billing mailbox → 4 the 1 Aug row: *86 of 93 ·
7 bad addresses* → 5 open it — the seven, named → 6 the 1 Jul row: *Unconfirmed · 93 sent, provider did not say*
→ 7 the S8 panel shows attention for it, not green.
**Exit test:** `BR-INT-018` — the no-count fixture produces `unconfirmed`, and the recorded red run shows a stub
that always writes `succeeded` failing that test; `BR-INT-039` — a finished run cannot be updated on PostgreSQL.

**Wave C — AS BUILT (2026-09-04, the CR-069 wave C build lane; product `2.135.0`). Stamped
2026-09-05 by the wave F lane.** Verified from the code at `eea15784`:

* **`C1` — the run lifecycle is in `services.py`, not in a file of its own.** `start_run` at
  `services.py:277` and `finish_run` at `:339`, with the outcome word computed at `:331` —
  `OUTCOME_UNCONFIRMED` is chosen there and never by an adapter, which is the rule the wave
  turns on. `runs.py` (333 lines) and `scrubbing.py` (135) are its neighbours; `migrations/0003_run_items.py`
  added the `items` column.
* **`C2`/`C3` — the reads and the screen.** `runs_api.py` (107 lines);
  `features/integrations/ConnectionDetailPage.tsx` (37,803 bytes) at `/:tenant/settings/integrations/:key`,
  with `screenIds.ts` carrying `S142`/`INT-02`.
* **`C4` — the seeded runs are a management command**, `management/commands/seed_integration_runs.py`,
  with `sample_runs.py` (207 lines) behind it.

---

### Wave D — their words, and format as a parameter · phase 1

÷ **SPLITS — 2026-09-06 (`CR-069` §20.4), AND THE HEAVIER HALF IS BUILT ON THE RUNBOOKS
SIDE.** Deciding that the kiosk's `ACHCHECK` means our *Bank transfer* is **the ETL lookup**
the 2026-09-05 ruling named. `mappings.py` (537 lines), `mappings_api.py` (100),
`ValueMappingPage.tsx` (18,760 bytes) and **screen S143** shipped at `2.131.0`, and both
`J1` and `S1` read those rows. **The codecs half stays** — a codec is how bytes are shaped
on the wire, which is landing what arrives — **except its `projections`** (`gl_payment_v1`,
`bill_message_v1`), which build a business record out of our data and are ETL. ⚠ **BUILT
(1.5 people-weeks), screen live: `OQ-INT-1727`.**

**Goal:** Priya maps the kiosk's fourteen tender words to the utility's own five on one screen, two of theirs
sharing one of ours; the same payment leaves as JSON to one partner and XML to another from one definition.
**Stories:** US-INT-037 · US-INT-039
**Depends on:** A (the table; the manifests' codec names). **Runs in parallel with B and C**, taking B4's field-kind
vocabulary as a contract. **Blocked by:** nothing — the ledger half is bounded by `OQ-INT-1480` and the table ships
beside the two columns.
**Version:** next free `<change>`. **Size:** one person, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **D1** | 2a | `apps/integrations/codecs.py` — the registry lifted from `apps/billing/print_formats.py` (`CR-053` task 14; one format at HEAD): projections (`gl_payment_v1`, `bill_message_v1`), codecs `json · xml · csv · iif · bai2 · camt053 · mime · qbo · xero · ofx · qfx`, packaging `none · zip · pgp`; an unregistered name refused **at load with the list**; **a codec with no fixture under `fixtures/<codec>/` is not a supported format**; `print_formats.py` reads from `apps.integrations.codecs` (one registry — `US-INT-039` TC-6 grep). A4's load-time codec check now reads this registry | 039 · `BR-INT-033` · `038` | A4 | `C8` · `T63` (epic cite, 70-register) | M |
| **D2** | 2a | `integration_target_reference` in `services.py` / `selectors.py`; `GET` / `PUT /integrations/{key}/mappings`; a manifest ships its known vocabulary (the kiosk's fourteen; Nacha `R01`…); an inbound unknown becomes a red row with *last seen*; `local_value` validated against **our** lookups (`tenancy.PaymentMethod`, `tenancy/models.py:927`; `REVERSAL_REASONS`, `payments/models.py:217`); `ledger_accounts.qbo_ref / .xero_ref` (`ledger/models.py:348-349`) **read, never widened** — the table ships BESIDE them until `OQ-INT-1480` | 037 · `BR-INT-031` · `032` · B14 rule 31 | A3 | `T-B1` (the ruling) | M |
| **D3** | 2b | S143 — `features/integrations/ValueMappingPage.tsx`, template **I5**, the *Their words* tab only (B9 matrix: search their word · our value; filters connection · type · unmapped only; unmapped first; **red** when unmapped; edit icon, rule 15; `MappingRow` *Change / Map it*); the second tab is **not rendered** until wave Q (a stated absence closed by default, B14 rule 32); the **format picker on S141 only where more than one codec is registered** (extends B4); `screenIds.ts` row for S143 | 037 · 039 · `BR-INT-033` · B14 rules 15 · 31 · 32 | D2 · B4 | `C4` · `C8` | M |
| **D4** | 2c | `US-INT-037` TC-1..6 (TC-2 and TC-3 on PG) · `US-INT-039` TC-1..6 (TC-4: `camt053` registered without a fixture fails the kit). Fixtures: the fourteen kiosk words; Brazos Bend methods *Cash · Cheque · Card · Bank transfer · Money order*; Aclarian rows `1200 → 001.100.11200`, `4100 → 001.100.44100`; `gl_payment_v1` JSON + XML for `PAY-2609-0311 · $142.18` | 037 · 039 | D1–D3 | — | M |
| **D5** | 2d | **`cr069-d-their-words.mjs`**: Priya opens S143 for the Payment kiosk → fourteen red rows, unmapped first → maps `ACHCHECK` and `ACHSAVINGS` both to *Bank transfer* → both green → `PUT` `ACHCHECK → Cash` refused → S141 for the Accounting file shows a format picker with four; Custom SMTP shows none · screenshots | 037 · 039 · `BR-INT-032` · `033` | D3 · D4 | — | S |
| **D6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the projection names chosen) | — | D5 | — | S |

**Demo script D (Priya Menon):** 1 Settings → Integrations → Payment kiosk → *Mappings* → 2 fourteen rows in red,
unmapped first → 3 *Map it* on `ACHCHECK` → *Bank transfer* → 4 the same for `ACHSAVINGS` → both green, one of
ours shared by two of theirs → 5 try to map `ACHCHECK` a second way — refused → 6 open *Connect · Accounting file*
— a format picker with four choices → 7 open *Connect · Custom SMTP* — no picker at all.
**Exit test:** `BR-INT-032` — the UNIQUE on the external side refuses on PostgreSQL; `BR-INT-033` — one projection
emits two codecs whose parsed field sets are identical, and an unregistered name is refused by name with the list.
**Phase 1 closes when A–D are done: fourteen stories.**

**Wave D — AS BUILT (2026-09-03, the CR-069 wave D build lane; product `2.131.0`). Stamped
2026-09-05 by the wave F lane.** Verified from the code at `eea15784`:

* **`D1` — `codecs.py` is 820 lines** and is the one registry; `D2` — `mappings.py` (537) and
  `mappings_api.py` (100).
* **`D3` — `ValueMappingPage.tsx` (18,760 bytes)** at the mappings route, `screenIds.ts` carrying
  `S143`/`INT-03`.

---

### Wave E — connect day: the first adapter · phase 2 (the phase-2 LAUNCH)

✅ **STAYS WITH INTEGRATIONS — 2026-09-06 (`CR-069` §20.4).** The purest wave in the change
request: **holding keys and secrets** (item 2) and the lifecycle of a connection (item 3).
The boundary ruling does not touch it. **BUILT — 8 of 9 tasks; one review owed.**
⚠ **BUT `DEF-INT-4118` LANDS HERE.** The PO named a partner (**InvoiceCloud**) who holds a
key we issued *and* whose key we hold — **two credentials, one relationship** — and this
wave's model cannot express it: `registry.py:293` `auth: Auth` is singular, and this
module's shipped `0001` migration enforces `EXCLUDE … (connection_id) WHERE (is_active)`,
so **the database refuses a second active credential**. `BR-INT-025` is `PROPOSED`, so
correcting it is ours and needs no re-sign — but it costs a migration. **Repair work on a
built wave: ADDED to integrations' remaining total, not taken out of it.**

**Goal:** Alex types the mail password into the product, presses *Save and test*, one real message arrives, the
card turns *Working* — and the password is in no table, no log and no audit row. A wrong key on a Friday is undone
in one row.
**Stories:** US-INT-025 · US-INT-024 · US-INT-026 · US-INT-003
**Depends on:** B (modal, endpoints, adapter protocol) · C (run rows). **Blocked by:** E1 — no real credential is
stored before `core/crypto.py`'s sign-off is recorded (fixture credentials are fine until then).
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **E1** | review | **BEFORE a real credential is stored:** `core/crypto.py`'s four self-made judgments — where the key comes from (`SBH_FIELD_ENCRYPTION_KEYS=<kid>:<base64url 32 bytes>`), what happens when it is absent (refuse to start), how rotation works (additive by `kid`, new key first), randomised-not-deterministic — put to the PO **in plain English with a worked figure**, and the ledger row at `09-human-review-ledger.md:395` moved to signed with the words shown. Not a question; a review | 024 · CLAUDE.md 🔒 · HUMAN-GUIDE §6 | — | — | S (calendar-bound) |
| **E2** | 2a | **The deletion path first** (`US-INT-025`): `DELETE /integrations/{key}` destroys **every** credential version (rows deleted — a secret's retention differs from a record's), sets `status = off`, **keeps every run row**, audits with masked hints `••••3F9A, ••••A17C destroyed`; queued notification rows rest `queued` with the config-missing marker through `seams/notifications.py` (no shared-sender fallback); reconnect needs fresh credentials; the IS-6 consequence copy per card class (`US-INT-003`) | 025 · 003 · `BR-INT-016` · `042` · `014` · B14 rule 6 | B3 | — | M |
| **E3** | 2a | Versioning (`US-INT-024`): `POST /integrations/{key}/credential` writes v(n+1), deactivates n (`rotated_at`), re-runs `test()`; `POST …/credential/rollback` re-activates the previous version in one row — refused *Nothing to roll back to* / *Previous credential has expired* (≤ 6 words each); audit `integration.credential_rotated` carries `••••3F9A → ••••A17C` and nothing else; the connection row does not change — it holds no secret to change | 024 · `BR-INT-025` · `003` · `014` | A3 · E1 | — | M |
| **E4** | 2a | **`adapters/email_smtp.py`** — the real adapter: `validate` (host · port · from), `test` sends **one real message** to the typed address (`smtplib` — legal only in `adapters/` and `core/`, `US-INT-015` TC-7) and returns the server's verdict in one sentence (*the mail server rejected the password*), `execute` per-item results, `describe` *billing@brazosbend.example · Custom SMTP*. **The fold (`C35`, `US-INT-026`):** a data migration converts every `notifications.NotificationSettings.smtp_secret_ref` holder (`notifications/models.py:746`) into an `email_smtp` connection (`config`: host · port · send_from) plus credential v1 read **once, at migration time, in the deployment that holds it**; absent → `not_set_up` with *Mail password needs entering* — no guessed value, no empty credential row; `smtp_secret_ref` NULLed and its reader in `sender_config.py:50` retired (TC-4: only the migration and a `# retired` comment remain); `seams/notifications.py` resolves the credential **inside the seam at use time** for the dispatcher (`provider_seam.py` stays the one seam, `BR-NOT-005`) | 026 · 015 · `BR-INT-005` · `007` · `008` · `019` · `038` · `042` | E1 · E3 · B1 | `C35` | L |
| **E5** | 2b | The Manage view live on S141/S142: *Replace password* → *Roll back*; the credential history under Replace password (frame `54.2`); **Disconnect** → template **I7** `ConfirmDialog` (destructive: question · red *what happens straight away* · blue *what is kept* · type the name) → toast → card *Turned off*; the S8 Notifications sender card (`features/notifications/SettingsNotificationsTab.tsx`, on the migrated list) becomes a **read** of the `email_*` connection | 024 · 025 · 003 · 026 · B14 rules 6 · 32 | E2–E4 · B4 | `C35` | M |
| **E6** | 2c | `US-INT-024` TC-1..7 — **TC-6 the three exits**: a database dump, the captured logs and `audit_log` grepped for both plaintexts (`Ew3!kQ9-lockbox`, `wrong-key-friday`) → zero hits in all three; TC-3 on PG · `US-INT-025` TC-1..6 (TC-4 the dump; **TC-6 the ordering gate: the disconnect test lands in the same PR as, or before, the first adapter that stores a credential**) · `US-INT-026` TC-1..6 (present and absent secret at migration; two tenants) · `US-INT-003`'s TCs · `US-INT-015` TC-1, 2, 4 against the real adapter's recorded fixture. `JOBS_EAGER=false --reuse-db` | 024 · 025 · 026 · 003 · 015 | E2–E5 | — | L |
| **E7** | gate | **§13 gate 2 as a permanent check** — the three-exits assertion runs inside the conformance kit for every adapter, and a gate scans `apps/integrations` for log calls and audit-payload builders that reference credential fields — RED by logging the password inside the fixture adapter. Registered the same commit | 024 · `BR-INT-003` · law 7 | E4 | §13 | S |
| **E8** | 2d | **`cr069-e-smtp-connect-day.mjs`** (`J48` + `J49`): the demo script below, then the three-exits proof printed and asserted (dump · logs · audit — zero hits). **Journey files `J48` and `J49` written** in `08-qa/01-e2e/journeys/` (frontmatter id · tier · rules · stories; Intent; Fixture; the step table with handoff contracts) | 024 · 025 · 026 · 003 · `BR-INT-003` · `019` · `025` · `016` | E5–E7 | — | S |
| **E9** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · **phase 2 LAUNCH declared** | — | E8 | — | S |

**Demo script E (Alex Reed, then 5 pm Friday):** 1 *Connect* on Custom SMTP → host, port, username, password,
*Send bills from* → 2 *Save and test* → one real message reaches `alex@brazosbend.example`; the card turns
*Working*, its line reads *billing@brazosbend.example · Custom SMTP* → 3 *Replace password* with `hunter2 ` →
*the mail server rejected the password*; the card turns *Not working* → 4 *Roll back* → *Working* again without
re-authorising; S142 shows two versions, v1 active → 5 *Disconnect* → type the name → confirm → the card reads
*Turned off*, the runs still listed → 6 in the terminal: the database dump, the captured log and the audit table
searched for both passwords — zero hits in all three.
**Exit test (asserts a rule):** `BR-INT-003` and `BR-INT-019` — **`CR-069` §12's phase-2 exit test**: the wrong
password produces the mail server's own sentence on screen, and the credential is provably absent from the
database, the logs and the audit trail. `BR-INT-025`: the database, not the application, refuses a second active
version (PostgreSQL).

**Wave E — AS BUILT (2026-09-04/05, the CR-069 wave E build lane; product `2.142.0`, corrected at
`2.144.0`), WITH `E1` STILL OWED AND SAID SO.** Stamped 2026-09-05 by the wave F lane. Verified from
the code at `eea15784`:

* **`E2`–`E4` — the adapter and the fold.** `adapters/email_smtp.py` (376 lines);
  `services.disconnect` at `:972`, `rotate_credential` at `:1076`, `rollback_credential` at `:1166`;
  the `C35` fold is `migrations/0004_c35_fold_sender_secret_ref.py` (171 lines).
* **`E7` — the three-exits gate is `G94`**, and the wave's own walkthrough found `DEF-INT-3762`
  (a card still reading *Working* on a test taken against the password that had just been replaced),
  fixed at `17c57b5e`.
* ⚠ **`E1` IS NOT DONE AND MUST NOT BE READ AS DONE.** `20-wave-tasks.tsv` carries it as
  `review-owed`, and `09-human-review-ledger.md` holds three integrations rows —
  `core/crypto.py`, `adapters/email_smtp.py` and `migrations/0004_…` — every one of them
  `HUMAN-REVIEW-PENDING` with *"NOT YET PUT TO THE PO"* written into the row. The wording to
  show is drafted in each row; nobody has shown it. Phase 2 has stored real credentials with
  that signature outstanding, which is lawful under the standing ruling of 2026-08-09
  (*"AI will do it; we will review it later as human"*) and is not the same thing as reviewed.

---

### Wave F — one tenant's outage stays one tenant's · phase 2

÷ **SPLITS — 2026-09-06 (`CR-069` §20.4) — AND THIS IS THE LIVE LANE.** `F1` (timeout,
concurrency cap, breaker, backoff, *Not working*) is **item (3)** end to end and is
**BUILT**. `F2` is two halves that fall on opposite sides: the **feedback door**
(`inbound.py` — authenticate → dedupe → reply → persist raw) is landing what arrives and
**stays**; **marking notification rows `delivered` / `bounced` and feeding the suppression
list is a record update** and is **Runbooks'**.

⚠ **RULED 2026-09-06 (`OQ-INT-1729`) — OPTION (a): THE LANE STOPS AT THE DOOR, AND THE
RECORD-MARKING WAITS FOR RUNBOOKS.** The choice is the Product Owner's; the words of the
option are ours, from the register.

**What is integrations' and is FINISHED HERE:** `F1`, **BUILT** · `F2`(a) the send half,
**BUILT** and now behind the guard · **`F2`(b) the feedback door** — `inbound.py`,
`POST /integrations/webhooks/{key}`, *authenticate → dedupe → reply at the declared
position → persist raw*. The door is **landing what arrives**, it **stays**, and it is
**not started** — build it here.

**What is NOT built now and waits for Runbooks:** marking notification queue rows
`delivered` / `bounced` with the provider's own sentence, and feeding the suppression list
`J17` expects.

⚠ **NOTHING IS WASTED BY STOPPING, AND THAT IS WHY THE ANSWER WAS CHEAP: THAT HALF WAS
NEVER STARTED.** Change process step 4 treats in-flight work against a changed rule as a
collision — here the collision was with a **plan**, not with code. No line is deleted, no
test is discarded, and no shipped behaviour changes.

⚠ **`F3`, `F5` AND `F6` ARE UNSTARTED — EACH WAS CHECKED AGAINST THE LINE RATHER THAN
ASSUMED, AND THE NEXT LANE SHOULD DO THE SAME BEFORE TAKING ONE:**

* **`F3` — stays, and part of it is already done.** The `S8` card, the `S142` breaker note
  and the skipped-window row are a connection's own health. The delivery dashboard's
  ***not reported*** is read off the **manifest** — whether the provider declares a
  feedback operation at all — so it is connection-level and stays too. ⚠ **What cannot be
  built yet is the delivered/bounced COUNTS behind it**, because nothing will mark a row
  until Runbooks exists — and `BR-INT-027` already makes that screen correct without them:
  the absence is words, forever, and never `0`. **The rule written for honesty is what lets
  this wave stop cleanly.**
* **`F5` — buildable WHOLE.** Every step of `cr069-f-dead-mail-server.mjs` is the breaker,
  the skip row, the send count and the *not reported* string. None of it needs a marked row.
* **`F6` — and this is the one worth a human's eye.** `F6` closes **phase 2** on six
  stories, and **`US-INT-023` can no longer be completed here**: its feedback half is now
  Runbooks'. **This lane's judgment, recorded rather than put back to the PO (law 13):
  phase 2 closes with `US-INT-023` delivered TO THE BOUNDARY and the remainder named in the
  story**, rather than phase 2 being held open for work that has deliberately moved to a
  project with no home in this repository yet. It is a planning consequence of the ruling,
  not a fact only the PO holds — but it is flagged here and in the decision log, because a
  phase closing on a story that is half-elsewhere is what reads as drift six weeks later.

**Goal:** Brazos Bend's mail server hangs for ninety seconds a call, Silver Creek's 240 bills still go out on
time, and Brazos Bend's card says why in words. Bounces keep reading *not reported* until a provider tells us.
**Stories:** US-INT-022 · US-INT-023
**Depends on:** B (queue) · C (runs). **Runs in parallel with E.** **Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** one person, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **F1** | 2a | `apps/integrations/runtime.py`: a hard timeout on every call (manifest default `timeout_s = 30`, per operation) · a per-connection concurrency cap (default 2) · a breaker (open after 3 consecutive timeouts, half-open with one probe after 300 s) · exponential backoff **with jitter** through `core.jobs` retry · `Retry-After` honoured · a token bucket per connection in front of a `429`. Open breaker → `status = not_working`, `last_test_text` *the mail server is not answering*; the next due run **skipped and recorded** (a run row, `attempted 0`, the reason in words). The breaker is per connection, not per provider key | 022 · `BR-INT-022` · `041` · `024` | B2 · C1 | — | L |
| **F2** | 2a | `US-INT-023` — **(a) the send half:** `seams/notifications.py` maps per-item `execute()` results to queue-row `sent / rejected` **through notifications' service function** (consumers never write; `provider_seam.py` stays the one seam); **(b) the feedback door:** `inbound.py` — `POST /integrations/webhooks/{key}` with the guard pipeline *authenticate → dedupe → reply at the declared position → persist raw → process async* (`integration.inbound_process`); an `email_feedback` operation on `email_bulk` (`respond_after = persist`, event-id key) marks rows `delivered / bounced` with the provider's own sentence and feeds the suppression list `J17` expects; **mailbox connections have no feedback operation and bounces stay *not reported* — in words, forever, never `0`** (`delivery_counts.py:328` already serves the string). The customer-sending flip itself is W6 (`BR-INT-007`) and not this CR's | 023 · `BR-INT-027` · `020` · `021` · `008` | C1 · B2 | `C28` | L |
| **F3** | 2b | S8 card and S142 breaker note *Not working · the mail server is not answering* (frame `52.3`); the skip row in the runs table; the delivery dashboard (`US-NOT-013`, existing) reads send counts as numbers and bounces as *not reported* for a mailbox; the S8 Notifications provider-status panel treats `unconfirmed` and an open breaker as attention | 022 · 023 · `BR-INT-015` · `027` | F1 · F2 · C3 | — | M |
| **F4** | 2c | `US-INT-022` TC-1..6 — TC-1 an integration test on the `integrations` queue: fixture *slow* **sleeps 90 s then succeeds** (TC-2 asserts it sleeps, never raises), cap 2, pool 8, Silver Creek's 240-bill run completes in normal time; TC-3 breaker; TC-4 `429 Retry-After: 120`; TC-5 jitter; TC-6 per-connection · `US-INT-023` TC-1..6 (TC-3 duplicate event id applied once; TC-4 bad signature never parsed; TC-5 cross-tenant row ignored; TC-6 the gate asserting no code path writes `0` for a mailbox) | 022 · 023 | F1–F3 | — | L |
| **F5** | 2d | **`cr069-f-dead-mail-server.mjs`** (`J53` + `J17`'s leg): seed Silver Creek Water's 240-bill run; switch Brazos Bend's SMTP fixture to *slow*; run both; Silver Creek's run finishes on time; Brazos Bend's card reads *Not working · the mail server is not answering*; S142 shows the skip row; the dashboard shows a send count and the string *not reported* for bounces · screenshots. **Journey `J53` written; `J17` gains its leg** | 022 · 023 · `BR-INT-022` · `027` | F3 · F4 | — | S |
| **F6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · **phase 2 closes** (six stories) | — | F5 | — | S |

**Demo script F (two tenants):** 1 Silver Creek has 240 bills queued; Brazos Bend's mail server is made to hang →
2 the nightly sweep runs → 3 Silver Creek's bills are issued on time → 4 Brazos Bend's card: *Not working · the
mail server is not answering* → 5 S142: the skipped window, recorded → 6 the delivery dashboard: sends as a number,
bounces as *not reported* → 7 the probe succeeds and the card returns to *Working*.
**Exit test:** `BR-INT-041` — with a cap of 2 on a pool of 8, six workers stay free and another tenant's run
completes; `BR-INT-027` — no code path writes `0` for a connection with no feedback operation.

**Wave F — `F1` AS BUILT and `F2` PART BUILT (2026-09-05, the CR-069 wave F build lane; product
`2.177.0`). `F3`, `F5` and `F6` are NOT done and the second half of `F2` is not started — this stamp
says which, by name, because a wave that stamps itself green is the drift the stamp exists to stop.**

**What this lane found before building, and both findings are the reason task zero exists:**

* **The record was five waves behind the code.** Waves A–E had all shipped with no AS BUILT stamp
  (they have one now, above), and `F1` had landed on 2026-09-04 in commit `6f689ecc` while its row in
  `20-wave-tasks.tsv` still read `open`. This is the shape that dispatched two lanes onto finished
  work the same morning (`16-work/10-execution-plan.md`, wave B's stamp).
* ⚠ **AND `F1`'s GUARD REACHED NOTHING (`DEF-INT-4015`).** `apps/integrations/runtime.py` — 427 lines,
  297 lines of green tests — had **zero importers**. All four places that dial a provider
  (`runners/deliver.py`, `runners/fetch.py`, `jobs.py`'s test path, `seams/notifications.py`) called
  the adapter directly, with no timeout, no cap and no breaker. **The ninety-second hang this wave
  exists to contain was exactly as uncontained after that commit as before it.** Nothing here asks
  whether a Python module has a caller: `G13` is the built-is-not-wired gate and it reads React props,
  and the tests could not see it either because **every one of them called `guarded_call` itself** — a
  test that constructs the thing it is testing says nothing about whether the product constructs it.

**`F1` — DONE, and wiring it turned up three more things, each of which would have survived the fix.**

* **An eighth outcome word, `skipped`.** `outcome_for` returns `succeeded` whenever `failed = 0` and
  the counts reconcile, so a window the breaker refused to dial came out **`succeeded`** and `S142`
  would have read *93 of 93* over a batch that never left the building. `BR-INT-024` already required
  the word (*a skipped window is recorded as skipped*) and `US-INT-022` §5 asked for an
  *"`outcome = skipped`-shaped row"*, hedged because the vocabulary was seven. Migration
  `integrations/0005` is choices-only; `sqlmigrate` prints `(no-op)`.
* **`DEF-INT-4019` — the cap was holding the workers it exists to free, so this wave's own exit test
  was not satisfiable as built.** `guarded_call` waited the full CALL TIMEOUT for a slot, so with a cap
  of 2 on a pool of 8 two workers went into the call and **six blocked at the door for thirty seconds
  each**: the connection held all eight and the other tenant queued behind it anyway. Every existing
  case passed because they all counted *callers inside the provider* (2, correct) and none counted
  *workers held* (8). `queue_wait_s` is its own bound now, 2 s, clamped below half the call timeout so
  a Settings override cannot restore it.
* **`DEF-INT-4016` — the durable breaker was written on a monotonic clock.** `open_until` is written by
  one worker and read by another; a monotonic reading counts from an arbitrary origin, so it means
  nothing on a second host and can sit far in the future after a restart, holding a healthy connection
  shut. It survived because every test injects its clock as a bare float.

**`F4` — the isolation proof, DONE for `US-INT-022`; `US-INT-023`'s cases are not.**
`tests/test_us_int_022_isolation.py` is TC-1, TC-2, TC-3 and TC-6 (TC-4 and TC-5 were already in
`test_us_int_022_runtime.py`). It asks a different question from that file rather than a louder version
of it: eight workers, Brazos Bend blocked on a gate the test holds shut, and **Silver Creek's batch
asserted to finish WHILE the sick provider is still hanging** — an ordering, not a duration, so it is
not a wall-clock flake. Both guards were proved RED first: restoring the queue wait to the call timeout
makes Silver Creek's future raise `TimeoutError`, and removing the eighth word makes the skipped run
assert `'succeeded' == 'skipped'`.

**`G108` — the gate that would have caught `DEF-INT-4015`**, registered in `run_gates.py` the same
commit. Two clauses: no adapter `.execute`/`.test` outside a guarded `call=`, and `guarded_call` must
have a caller outside `runtime.py` and `tests/`. Proved RED both ways **through `run_gates.py`'s own
registry dispatch and not `python3 <gate>.py`** (`DEF-GOV-3733`). ⚠ Its first draft matched by LINE
SPAN and was defeated by its own RED proof — a dial sharing a line with `call=` read as guarded — so it
matches by AST ancestry, and the sabotage that beat it is kept in `selftest()` permanently.

**`F2` — HALF. The send half was already built and is now guarded; the feedback door is NOT started.**

* ✔ **(a) the send half** — `seams/notifications.py:dispatch_outbound_batch` (wave E) maps per-item
  `execute()` results to the dispatcher's `sent`/`failed` verdict, consumers write nothing, and
  `provider_seam.py` is still the one seam. This lane put it behind the guard and made a skipped or
  timed-out batch answer `retryable` with the rows resting `queued`.
* ✔ **`BR-INT-027`, the wave's second exit test** — `tests/test_us_int_023_not_reported.py`. The rule's
  structural half holds (nothing writes `delivered` or `bounced` as a number, now asserted across every
  event row and channel slot rather than trusted). ⚠ **Its second half had broken and nothing could
  see it:** the sentence served beside the absence said *there is no email provider connected*, which
  stopped being true the day wave E shipped the SMTP adapter — a utility could connect its mailbox,
  send a real message, and read that no email provider was connected. **The figure was right the whole
  time**, which is why nothing else in the product could tell. The reason now follows what is actually
  connected, read off the MANIFEST (`reports_feedback` — does the provider declare an `in · them`
  operation) rather than off our own progress, and a mailbox says so **for ever**, never softening into
  a zero.
* ✘ **(b) the feedback door is NOT built** — no `POST /integrations/webhooks/{key}`, no
  `integration.inbound_process` body, no `email_feedback` marking of `delivered`/`bounced`, no
  suppression-list feed for `J17`. `apps/integrations/inbound.py` is still wave B's stub raising
  `NotImplementedError("US-INT-044")`. ⚠ **AMENDED 2026-09-06 — HALF OF THIS BULLET IS NOW DEFERRED BY A
  RULING.** When it was written, none of it was. `OQ-INT-1729` was then ruled option (a):
  **the door — `POST /integrations/webhooks/{key}`, `integration.inbound_process`, the
  five-position pipeline — is integrations' and is still simply not reached, so build it
  here**; but the **`email_feedback` marking of `delivered`/`bounced` and the
  suppression-list feed are DEFERRED to Runbooks and are not built now.** Deferred is not
  blocked. It is a multi-day task that shares its file and its five-position pipeline with
  wave `N`. A lane taking it should read `BR-INT-030` (the reply position) and the note in `§1` that
  wave N **reuses** `payments/webhooks.py`'s two guards and mints no second inbound path.

**`F3` — PART DONE, and building it found the wave's fourth defect.** ⚠ **`DEF-INT-4025`: the one
sentence that tells a clerk WHY a connection stopped working reached the browser and was drawn
NOWHERE.** `last_test_text` has been on the read model since wave B (`selectors.py:249`), is declared
in the TypeScript type (`integrationsEndpoints.ts:106`), and is written by three separate backend paths
— a test, a credential rotation, and now an open breaker — and **no component read it**. That is
hard-won law 2 pointing the other way: `G13` asks whether a component prop has a caller, and nothing
asks whether a SERVED FIELD has a reader, so `tsc` and every existing case passed over a status with no
reason attached to it. Without it the wave's demo step 4 — *Not working · the mail server is not
answering* — had nowhere to appear.

* ✔ **The sentence is on both screens now.** `S142` draws it under the state word whenever there is one
  (it is the detail page); the `S8` card draws it **only when the connection is not working**, which is
  B14 rule 32's budget rather than shyness — eighteen cards each carrying a sentence is the *"too much
  content for a clerk to read"* the rule was ratified over. Both files were already on
  `route-b-migrated.txt` and both lines reuse a utility the same file already uses, so nothing new had
  to compile (`DEF-INT-3641`'s trap); `routeBUtilities.test.ts` is 10/10 and the local `tsc` 5.5.4
  reports nothing. Seven cases across the two test files, each proved RED by deleting the line.
* ✘ **Not done in `F3`:** the S8 Notifications provider-status panel treating an open breaker as
  attention, and the skip row's new outcome word has **no translation** — `integrations.state.skipped`
  and a runs-table label for it are missing from all eleven catalogues, so a skipped run will render
  its raw key. That is the next lane's first job and it is small.

**`F5` (the browser walkthrough `cr069-f-dead-mail-server.mjs` and journey `J53`) and `F6` (the wave's
own close-out) are NOT done.** `F5` is the one that matters: **nothing in this repository reads rendered
output** (hard-won law 6), so the seven cases above prove the markup and not the screen. The wave is not
signed off until somebody clicks it.

**THE ISOLATION IS PROVED ON REAL POSTGRESQL, AND GETTING THERE FOUND A BRANCH-BLOCKER.**
`tests/test_us_int_022_isolation_pg.py` asserts what SQLite cannot express: the breaker's durable state
is a tenant row, so one utility's *this provider has stopped answering* is invisible to another under the
**non-superuser** probe role; a skipped window is a real row read back through a raw cursor; and turning
that row into a success is refused by the append-only trigger — the one statement that would erase the
evidence that a utility's bills did not go out.

⚠ **IT WAS RUN BY HAND AND HAD TO BE, BECAUSE A GREEN ISOLATION GATE IS NOT EVIDENCE.**
`DEF-GOV-4024` (2026-09-05) records that the repository's tenant-isolation gate runs its suite without
pointing it at PostgreSQL, so it inherits SQLite and **46 of 238 proofs run, 192 skip, and the exit code
is 0.** A wave about one tenant's outage not reaching another may not lean on that.

⚠ **AND THE FIRST RUN COULD NOT BUILD A DATABASE AT ALL (`DEF-WRK-4027`, critical).**
`apps/work/migrations/0009_rls_force_dispatch.py`'s append-only trigger does not compile —
*too many parameters specified for RAISE* — so **every PostgreSQL migration on this branch stopped at
that file**, and had done since it landed. The cause is a convention that is right in one place and
wrong in another: `integrations/0001_initial.py` documents doubling every `%`, because
`schema_editor.execute(sql)` defaults to `params=()` and psycopg then substitutes, so `%%` arrives as
one `%`. `work/0009` runs through `RunSQL`, which passes `params=None`, so nothing substitutes and `%%`
reached PostgreSQL verbatim — a literal percent with no placeholder behind it, and two arguments with
nowhere to go. It is fixed in this lane's commit with the reason written at the site, because until it
is fixed no lane can prove anything on a real database.

---

### Wave G — the first beat schedule this product has ever had · phase 3

⚠ **MOVES WHOLE TO RUNBOOKS — 2026-09-06 (`BR-INT-054` as amended, `CR-069` §20.4).** The PO
put **scheduling** on the Runbooks side: *"business logic , scheduling , processing we will
take it in run book"*. Everything below — the beat schedule, the due sweep, tenant-midnight
and DST, the three-hundred-utility spread, the skip row, the catch-up policy — is
scheduling. Runbooks already asks for exactly this: *"one scheduler, not two"*.
**INTEGRATIONS RETAINS ONE CLAUSE: `G2`'s request-budget COUNTER** — a 10,000-a-week
allowance is a fact about that provider (item 1); what a scheduler does with the count is
Runbooks'. ⚠ **THE QUEUE AND WORKER ARE NOT THE SCHEDULER** and stay in integrations
(wave `B`); Runbooks runs on them. **This wave, its letter and its task ids are kept in
place and NOT reused.** **2 people-weeks leave integrations.**

**Goal:** *nightly* means the utility's own midnight on both sides of the clock change; three hundred utilities do
not fire together; a run still going is skipped and the skip is written down; and the screen says *9,980 of 10,000
requests used this week* before readings stop on a Thursday.
**Stories:** US-INT-029 · US-INT-030
**Depends on:** B (queue) · C (run rows). **Can start the day phase 1 closes, in parallel with E and F.**
**Version:** next free `<change>`. **Size:** one person, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **G1** | 2a | **`CELERY_BEAT_SCHEDULE` in `config/settings/base.py` — the product's first** (none at HEAD): `integration.sweep_due` every minute · `integration.sweep_expiry` nightly (its body is H2; a no-op-safe handler lands here). `apps/integrations/scheduler.py` — the due sweep of Figure 13: `enabled AND next_run_at ≤ now AND not running` → deterministic per-connection offset (hash of the id modulo the window — stable across sweeps) → enqueue scope-keyed → next due computed **in the tenant's timezone, DST-safe** (`zoneinfo`); a run still `running` → **skip and write a skip row**; `catch_up_policy` per operation `latest_only | never` (money ⇒ `never` → *needs a person to start it*); `manual` has no due time and is never swept; cadence vocabulary `nightly · hourly · manual` — a cron string is refused; a connection with an open breaker is skipped and recorded; a `sandbox` connection is never handed real work | 029 · `BR-INT-024` · `026` · `022` | B2 · C1 | `C29` · `T-1.15` (the CR names it as `C29`'s dependency) | L |
| **G2** | 2a | The request budget (`US-INT-030`): manifest `budget = {allowance, period, resets}` **or an explicit `budget = none`** (a gate refuses an omitted one); the runtime counts each run's spend atomically with the run row in `config.budget_spent` / `period_started_at` (non-secret); the sweep **declines a run it cannot finish** — at 9,980 of 10,000 with 40 due it does not start — and records *declined — 40 requests needed, 20 left this week*; the counter resets at the provider's time | 030 · `BR-INT-034` · `024` | G1 | — | M |
| **G3** | 2b | S142 `BudgetLine` *9,980 of 10,000 requests used this week · resets Monday* (frame `53.1`) and the card's figure above 90 %; skip and declined rows in the runs table; `next_run_at` shown in the tenant's words | 029 · 030 · B14 rule 32 | G1 · G2 · C3 | — | M |
| **G4** | 2c | `US-INT-029` TC-1..7 — DST on `2026-11-01` and `2027-03-14` for America/Chicago; 300 connections across six zones spread identically on two sweeps; skip row; six missed windows → one file fetch, **zero** for the money-moving operation; `manual` never swept; cron refused · `US-INT-030` TC-1..6 with `meters_neptune360` at `10,000 / week / resets Monday 00:00 America/New_York`, spent `9,980`, 40 due | 029 · 030 | G1–G3 | — | L |
| **G5** | 2d | **`cr069-g-thursday-budget.mjs`** (`J56`): the connection at 9,980 of 10,000, a collection needing 40 falls due → the sweep runs → the declined row *40 requests needed, 20 left this week* → S142 reads *9,980 of 10,000 requests used this week · resets Monday* → the card carries the figure · screenshots; the DST proof quoted from the test run. **Journey `J56` written** | 029 · 030 · `BR-INT-034` · `024` | G3 · G4 | — | S |
| **G6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the offset formula; the two beat entries) | — | G5 | — | S |

**Demo script G (the due sweep, then Alex):** 1 a head-end connection shows *9,980 of 10,000 requests used this
week* → 2 Thursday's collection, needing 40, falls due → 3 the sweep declines it and writes why → 4 S142: the
declined row with both figures and *resets Monday* → 5 the card shows the same figure under its state word → 6 in
the test output: Chicago's nightly run fires once at midnight on the night the clocks go back, and once on the
night they go forward → 7 a run still going when the next is due leaves a skip row, not a second run.
**Exit test:** `BR-INT-034` — the sweep declines what it cannot finish and shows the spend; `BR-INT-024` — one run
per night across a DST change, and no automatic catch-up for anything that moves money.

---

### Wave H — token lapse averted · phase 3 (the phase-3 LAUNCH)

✅ **STAYS WITH INTEGRATIONS — 2026-09-06 (`CR-069` §20.4).** A credential expiring, a dated
warning, re-authorising, credential v(n+1) on the same connection: **items (2) and (3)**,
with nothing else in it. ⚠ Once `G` moves, this wave's sweep body is *triggered* by
Runbooks' scheduler — that is integrations work running on a shared clock, **not** a split
of ownership.

**Goal:** Silver Creek is told eleven days ahead, in words with the date, that Microsoft needs re-authorising;
Alex re-authorises and every earlier run is still there.
**Stories:** US-INT-005 · US-INT-027
**Depends on:** E (credential versions, the real adapter shape) · G (the nightly sweep entry). **Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** one or two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **H1** | 2a | `adapters/email_microsoft.py` and `adapters/email_google.py`: the `redirect` field kind → the authorisation URL; the return trip `GET /integrations/{key}/oauth/return` writes credential v(n+1) with `expires_at` **on the same connection row**; token refresh through the provider; `test()` one real message; *Send bills from* is the signed-in identity (`US-INT-005` §1 — the tenant's OWN address); recorded fixtures, no network in tests | 005 · `BR-INT-005` · `007` · `003` · `043` · `025` | E3 · E4 · B1 | `C11`'s mode for OAuth | L |
| **H2** | 2a | `integration.sweep_expiry`'s body: active credentials with `expires_at` inside the manifest's warning window (default 14 days) → the dated sentence ***Needs re-authorising by 12 September. After that, bills stop going out.*** on S142 and the S7 attention strip, and **one** email to the System Admins queued through notifications (never a direct send) — once per day, never twice for the same day; lapsed → `not_working` *Microsoft needs re-authorising*, the send run skipped and recorded, bills rest `queued`; `expires_at = NULL` (an SMTP password) is never warned | 027 · `BR-INT-042` · `015` · `008` | G1 · E3 | `C29`'s second entry | M |
| **H3** | 2b | S141 the OAuth body (frame `49.2`: one field, *Sign in with Microsoft*, *We never see or store your password*, Cancel only); S142 `WarningBox` and the S7 strip with the dated sentence (frame `54.1`); a *Re-authorise* button that is the return trip | 005 · 027 · B14 rule 32 | H1 · H2 · B4 · C3 | — | M |
| **H4** | 2c | `US-INT-027` TC-1..6 (Silver Creek `email_microsoft`, `expires_at = 2026-09-12` on `2026-09-01`; the day-10 warning not repeated; TC-3 history unbroken across v2; TC-4 lapse) · `US-INT-005`'s TCs against the recorded OAuth fixtures | 027 · 005 | H1–H3 | — | M |
| **H5** | 2d | **`cr069-h-token-lapse.mjs`** (`J50`): Silver Creek's credential eleven days out → run the sweep → S7 and S142 read the dated sentence → one queued email → re-authorise through the fixture return trip → credential v2 on the same connection, the warning cleared, **every earlier run still listed on S142** · screenshots. **Journey `J50` written** | 027 · 005 · `BR-INT-042` | H3 · H4 | — | S |
| **H6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · **phase 3 LAUNCH declared and phase 3 closes** (four stories) | — | H5 | — | S |

**Demo script H (the sweep, then Alex Reed at Silver Creek):** 1 the credential is eleven days from lapsing → 2 the
nightly sweep runs → 3 the dashboard strip: *Needs re-authorising by 12 September. After that, bills stop going
out.* → 4 the same sentence on the connection's detail → 5 one email queued to the admins → 6 *Re-authorise* →
Microsoft's sign-in (the fixture) and back → 7 the warning is gone, the credential is version 2, and the twenty
runs from before are still on the screen.
**Exit test (asserts a rule):** `BR-INT-042` — **`CR-069` §12's phase-3 exit test**: a dated warning before the
lapse, and re-authorising keeps the connection's entire run history.

**Wave H — AS BUILT (2026-09-06, the CR-069 wave H build lane; product `2.201.0`), WITH THE ADMIN
EMAIL NOT DONE AND SAID SO.** The exit test is met and was met **by clicking**, not only by
assertion: `10-scripts/render-checks/cr069-h-token-lapse.mjs` finishes `0 failures · 1 known gap`.

* **`H1` — the round trip is manifest DATA, not adapter code.** `adapters/base.py`'s protocol is
  exactly four methods and the conformance kit refuses a fifth, so there is nowhere on an `Adapter`
  to hang *where Microsoft's sign-in lives*. It became `registry.OAuthEndpoints` on
  `Manifest.auth`, which is what `BR-INT-043` asked for anyway — *"no code branched to make that
  true"*. `oauth.py` (400 lines) serves every provider that declares endpoints; Microsoft and
  Google differ by that object and by nothing else. `adapters/oauth_mailbox.py` holds everything
  the two mailboxes share and each provider file is about thirty lines — a send URL and a message
  shape — which is `P1` demonstrated rather than asserted.
* **`H2` — `expiry.py` is a CALLABLE and its docstring says so twice.** Under `BR-INT-054` as
  amended 2026-09-06, deciding *when* to look is scheduling and is Runbooks'. It holds no cron,
  reads no clock and computes no `next_run_at`; a test walks its AST and fails on any of those
  names appearing in executable code. `jobs.run_sweep_expiry_job` is the invocation, and when
  wave G's scheduler moves it will enqueue that same kind unchanged.
* **The once-a-day marker is on the CREDENTIAL, not the connection** (`migrations/0006`), and that
  one choice is why re-authorising needs no reset: v(n+1) arrives with `expiry_warned_on` NULL and
  its own later date, so the warning stops because the row it was about is no longer active. On the
  connection it would have owed a second write a lane could forget.
* **`H3` — `components/WarningBox.tsx`** fills template I3's slot, which this screen's own trailer
  had carried as a stated absence since wave C. It is in the KIT (B14 rule 36) and on
  `route-b-migrated.txt` in the same commit that created it. S142 and the S7 attention strip read
  the SAME server-settled `expiry` block, so the two cannot drift on which side of a boundary a
  date falls.
* **The date is the tenant's, everywhere.** Frame `54.1` writes *"by 12 September"*; the screens
  render `formatDate` in the tenant's regional format, so a US utility reads **09/17/2026** and a
  German one **17.09.2026**. A month name in the component would have been a second formatting
  path against `BR-SHL-023` and English in all eleven catalogues. Stamped as a deviation below.
* **`H4` — 26 backend cases** (`test_us_int_027_expiry.py`, `test_us_int_005_oauth.py`) and 97
  frontend. Four sweep guards were shown RED on their own fault first and restored.
* **`H5` — the walkthrough passes**, and it REFUSES a wrong starting state rather than reporting
  nine reds about it: it re-authorises, so it cannot run twice on one clone, and runs are
  append-only (`BR-INT-039`) so the fixture cannot start over.
* ⚠ **THE BROWSER FOUND THREE THINGS NOTHING ELSE COULD, WHICH IS THE ARGUMENT FOR 2d IN ONE
  LINE.** `DEF-INT-4236` — the WarningBox drew with **no coloured border**, because
  `border-amber-600` (the class `09-component-inventory.md` writes against it) is a Tailwind
  DEFAULT-palette name this product does not have; the class IS in the DOM, so every assertion
  passed. `DEF-INT-4237` — ***Replace password* on a mailbox you SIGN IN TO** opened a form the
  server refuses, under a heading calling a consent a password; wave E's tests all pass because
  they use `email_smtp`, which does have one. `DEF-INT-4238` — a red this lane did not cause,
  dated to `89ce3237` with `git log -S` rather than dismissed.
* ⚠ **`H2`'s ADMIN EMAIL IS NOT BUILT AND MUST NOT BE READ AS BUILT.** `BR-INT-042` asks for the
  warning *"on the dashboard and by email"*; the dashboard half ships, the email half does not.
  Notifications publishes no expiry notice, and the nearest existing callable
  (`queue_staff_alert`) is a bulk-summary shape that refuses a `failed_count` below 1 and renders
  as *N of M failed* — borrowing it would have put *"Sign-in about to lapse: 1 of 1 failed"* in
  the bell and **looked done**. `sweep_expiry` therefore reports `notified: 0` with the reason in
  words rather than a silent zero, the seam name `queue_expiry_notice` is declared on both sides
  so `G20` can see it, and `DEF-INT-4214` carries it. The walkthrough records it as a known gap
  that goes RED IN BOTH DIRECTIONS.
* **Deviations from the frames, stamped rather than silent:** *(a)* the date is regional rather
  than the frame's *"12 September"* — see above. *(b)* Frame `54.1` draws a **Remind me** button
  beside *Re-authorise now*; it is **not built**, because nothing in this wave stores a snooze and
  a button that forgot its own promise is worse than none. *(c)* The panel's heading reads
  *SIGN-IN ON THIS CONNECTION* rather than frame `54.2`'s *KEYS ON THIS CONNECTION* on a redirect
  provider, chosen from manifest data so no screen branches on a provider key.
* **Phase 3 is NOT declared closed by this wave.** `H6` names *"phase 3 LAUNCH declared and phase
  3 closes (four stories)"*, and this lane built two of them — `US-INT-005` and `US-INT-027`. The
  other two are not this wave's and are not stamped here.


---

### Wave I — the same bank file twice · phase 4 (the phase-4 LAUNCH)

÷ **SPLITS — 2026-09-06 (`CR-069` §20.4) — AND THIS WAVE *IS* THE WORKED CASE.** From the
boundary ruling: *"A bank file lands. Integrations connects to the bank, authenticates,
pulls the file, and records that a batch arrived on that connection — **and stops**.
Runbooks reads the batch, decides which payment matches which account, writes the payments,
and keeps the run record and the audit of what it decided."*
**KEEPS:** the bank connection, the manifest, SFTP-or-upload, `test()`, and **`input_hash`
computed before the parse with the duplicate refused naming the first by date** — because
*records that a batch arrived* is on the integrations side.
**MOVES:** `stage_import` / `commit_batch`, the per-row savepoint, **which payment matches
which account**, the counts `899 / 1 / 0`, the receipt naming row 412.
⚠ Most of the moving half **already exists in `apps/payments`** (`payment_import.py`); the
ruling decides who WRAPS it, not who wrote it.

**Goal:** Priya uploads Tuesday's lockbox file through a named bank connection; on Wednesday she uploads it again
by mistake and reads *refused duplicate — the same file as Tuesday 06:10*; one bad row in nine hundred stops one
row — on PostgreSQL.
**Stories:** US-INT-008 · US-INT-010 · US-INT-032 · US-INT-033
**Depends on:** D (codecs) · C (runs) · B (queue, modal). **Runs in parallel with J, K and M.** **Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **I1** | 2a | The bank connection on the substrate: `bank_lockbox_file` manifest (source upload or SFTP; codecs from D1; the CSV `mapping_editor` as a **second step**) · `adapters/bank_lockbox_file.py` — `test()` lists one directory for SFTP; an upload source has no safe instance and the manifest declares it (card *cannot be tested until first use*) · `runners/fetch.py`'s file-in path: **`input_hash` computed BEFORE parse** and written on the run row (payments' `stage_import` at `payment_import.py:344` already hashes first — the runner adds the run row, and a second arrival is **refused naming the FIRST by date**: *refused duplicate — the same file as Tuesday 06:10*, `input_hash` equal on both rows) → the bytes handed to `apps.payments.payment_import.stage_import / commit_batch` through `seams/payments.py` — **the one inbound write path; the per-row SAVEPOINT already lives at `payment_import.py:801-809` with its law-14 comment** — the run's counts (`899 / 1 / 0`) and a receipt artifact naming row 412 with the SQLSTATE sentence read two or three hops down `__cause__`; the batch records its producing connection (`payment_import_batches` profile ref → connection id; history never restated — `US-INT-010`) | 008 · 010 · 032 · 033 · `BR-INT-020` C · `023` · `009` · `010` · `BR-PAY-028` · `036` · law 14 | D1 · C1 · B2 | `C13`'s hash · `T23` `T24` `T25` (epic cites, 70-register) | L |
| **I2** | 2b | S38 (`features/payments/BankImportWizard.tsx`) picks a **named bank connection**; S35 shows the producing connection on the batch; S141's bank variant (frame `50.2`: bank label · file format · source; the column mapping as a second step); S142 run rows with the receipt link; the IS-1 deactivate-first lifecycle on the connection (`US-INT-010`) | 008 · 010 · 033 · `BR-INT-043` · IS-1 | I1 · B4 · C3 | `C8` | M |
| **I3** | 2c | **`tests/pg/test_us_int_033_duplicate_file_pg.py`** TC-1 · **`tests/pg/test_us_int_032_savepoints_pg.py`** TC-1, **TC-2 red-first** (`try/except IntegrityError: continue` → `InFailedSqlTransaction` at row 413, zero committed — recorded), TC-4, TC-6 · `US-INT-033` TC-4, 6 · `US-INT-032` TC-3 (the SQLite-honesty docstring), TC-5 · `US-INT-008` and `010`'s TCs. Fixtures: `J14`'s 40-row CSV; the 900-row poison file (row 412 → account `4471-0021`, absent); the one-row fix; Lone Star Ridge's hash-collision file | 032 · 033 · 008 · 010 | I1 · I2 | — | L |
| **I4** | 2d | **`cr069-i-same-file-twice.mjs`** (`J51` + `J52`, on PostgreSQL): the demo script below · screenshots. **Journeys `J51` and `J52` written; `J14` gains its profile leg** | 032 · 033 · `BR-INT-020` · `023` | I2 · I3 | — | S |
| **I5** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · **phase 4 LAUNCH declared** | — | I4 | — | S |

**Demo script I (Priya Menon):** 1 S38 → choose *Chase lockbox* — a connection, not a bare upload → 2 upload
Tuesday's file → 38 of 40 in, two named (`J14`'s numbers) → 3 upload the same file on Wednesday → *refused
duplicate — the same file as Tuesday 06:10*; no payment applied twice → 4 upload the 900-row file → the run reads
*899 / 1 / 0* → 5 open the receipt: *row 412: account 4471-0021 is not on file* → 6 upload the one-row fix → one
more payment; the original receipt unchanged → 7 S35: the batch names the connection that produced it.
**Exit test (asserts a rule):** `BR-INT-020` C and `BR-INT-023` — **`CR-069` §12's phase-4 exit test, on real
PostgreSQL**: the byte-identical file is refused naming the first by date, the hash was computed before parsing
(asserted by ordering), and the recorded red run shows the savepoint-less handler losing every row.

**Wave I — THE INTEGRATIONS HALF AS BUILT (2026-09-06, the CR-069 wave I build lane; product
`2.200.0`). ⚠ THE OTHER HALF IS RUNBOOKS' AND IS DELIBERATELY NOT BUILT — read the split
before reading the stamp.**

**WHAT WAS BUILT, and it is exactly the five things `CR-069` §20.4 names:** the bank
connection · the manifest · SFTP-or-upload · `test()` · **`input_hash` computed BEFORE the
parse, with the duplicate refused on it**.

* **`apps/integrations/arrivals.py` (new).** `record_arrival()` in three steps, and the
  ORDER is the guarantee: hash the bytes → open the run row already carrying the digest →
  ask whether we have had them before. It imports no codec and no parser, so it *cannot*
  read a field out of a file. Step 2 before step 3 on purpose: a duplicate that arrives is
  still an arrival, and a utility asking *did Wednesday's upload reach you at all* is owed
  a row that says yes.
* **`services.start_run(input_hash=…)`.** The digest is written when the run OPENS. It
  could only ever have been written at CLOSE before, and a hash written at close is a hash
  of a file we had already read.
* ⚠ **`finish_run`'s `KEEP` sentinel, and this is the bug the wave would otherwise have
  shipped.** The argument was `input_hash: str | None = None`, assigned unconditionally.
  All five runners omit it, so closing an arrival's run row set the column back to NULL and
  **the next arrival of the same file would have found nothing to match** — a duplicate
  refusal incapable of firing, with every test green. Hard-won law 7's *what would make
  this check pass wrongly*.
* **`adapters/bank_lockbox_file.py`** — the module's THIRD adapter, bound in
  `adapters/__init__.py`. Until that one line the card was live, the manifest was
  registered and every connect was refused *Cannot be connected yet.* (law 2).
* **`POST /integrations/{key}/arrival`** — 201 for a new file, **409** for a repeat, with
  the sentence naming the first arrival by day and time. 409 and not 200: a duplicate is a
  refusal a clerk must see.
* **Six message keys plus `integrations.runs.outcome.skipped` in all eleven catalogues.**

**WHAT WAS NOT BUILT, BY RULING RATHER THAN BY DEFERRAL (`BR-INT-054` as amended
2026-09-06):** `stage_import` / `commit_batch`, the per-row savepoint, **which payment
matches which account**, the counts `899 / 1 / 0`, and the receipt naming row 412. That is
Runbooks' half. `arrivals.close_arrival()` is the door the processing half will close the
run row through; it has **no caller in this module and that is correct**. Until Runbooks
exists an accepted arrival's run row stays open, which is honest: the file arrived, and
nothing has yet said what became of it.

⚠ **THE PLAN'S OWN `I1` CELL CROSSES THE LINE ITS WAVE HEADING DRAWS, AND WAS NOT
FOLLOWED.** `I1` reads *"→ the bytes handed to `apps.payments.payment_import.stage_import /
commit_batch` through `seams/payments.py` … the run's counts (`899 / 1 / 0`) and a receipt
artifact naming row 412"* — every clause of which the same wave's heading and `CR-069`
§20.4 assign to **Runbooks**. `I1` predates the 2026-09-06 sharpening and was never
rewritten. A test walks `arrivals.py`'s AST and fails if it ever imports `apps.payments`,
so this cannot be re-crossed quietly.

**Proved, not merely tested:**

* **The phase-4 exit test PASSES on real PostgreSQL** —
  `tests/test_us_int_033_duplicate_file_pg.py`, against a `proof-db.sh clone int_i`.
* **The ordering is proved STRUCTURALLY.** TC-1 hands `record_arrival` bytes that are not
  valid text in any encoding (a lone `0x80`); anything that decoded or parsed would raise.
  The row coming back with a digest on it is evidence about ORDER, not arithmetic.
* **The control case is present and is not optional.** *Nothing was written* also describes
  a broken endpoint, so a file ONE BYTE different is sent and proved **accepted**.
* **The guard was proved RED, and the first sabotage was not enough** — breaking only the
  assignment left all thirteen cases green, because `update_fields` is the deciding half.
  Breaking both fails two cases including TC-4 itself.

**Two live screen defects found by building this and fixed here**, both pre-existing since
wave `F1` and both made common by wave I (every refused duplicate closes `skipped`):
`skipped` was missing from the frontend's `RunOutcome` union while the server had been
sending it — so the value arrived, every branch fell through to its default, and S142
rendered **`0 of 0`**, a formatted lie for a run nothing was attempted on. It reads *Not
attempted* now. The catalogue key was missing too, so the raw enum word `skipped` reached
a clerk in all eleven languages (B14 rule 32).

⚠ **`I2`'s S38 AND S35 ARE NOT DONE AND MUST NOT BE READ AS DONE.** The bank import wizard
picking a named connection, and the batch showing its producing connection, are screens
over the PROCESSING half; they wait on Runbooks. What wave I shipped on screen is the card
(S8) and the connection detail (S142). ⚠ **AND `test()` CANNOT DIAL A REAL FOLDER ON THIS
DEPLOYMENT** — no SFTP client is installed, so `FOLDER_CLIENT` is unbound and `test()`
answers `ok=false` *No folder client is installed.* rather than a pass it has not earned.
Recorded as a known gap in `cr069-i-same-file-twice.mjs`, which goes red in BOTH
directions: install a client and leave the gap, and the walkthrough fails for being stale.

---

### Wave J — a remembered destination · phase 4 · ✅ **AS BUILT 2026-09-06 (`2.203.0`)**

÷ **SPLITS — 2026-09-06 (`CR-069` §20.4). ⚠ NOT the clean integrations wave it looks like.**
**KEEPS:** the `accounting_file` connection (`destination × codec`), `test()`, the
`camt053` codec, and **period + target giving the same file or a refusal naming 5 August**
— outbound duplicate-recognition, the same argument as wave `I`.
**MOVES:** **readiness** (*3 accounts still need an export code* is a business judgment
about the chart of accounts) and the **Nacha return-code mapping** (`R01 → nsf`,
`R02 → other`), which is wave `D`'s ETL table one module along.
⚠ **AND THIS WAVE IS NOT BLOCKED, WHATEVER §5 BELOW STILL SAYS** — `OQ-INT-1487` and
`OQ-INT-1483` both **CLOSED 2026-09-04**.

**Goal:** month-end goes to a saved export target; a period regenerated is the same file or a refusal that says
when it was first exported; a format nobody registered is refused by name with the list of what exists.
**Stories:** US-INT-009 · US-INT-038
**Depends on:** D (codecs, mapping rows) · C (runs). **Runs in parallel with I.** **Blocked by:** `OQ-INT-1487`
bounded the `R02` mapping only and was RULED on 2026-09-04 to option (b) — `R02` records as `other` with the raw code kept, the four signed reasons are not widened, and the writer refuses to map it BY RULING (`mappings.py`, done); `OQ-INT-1483` bounded the badge copy only and was RULED the same day to `self-declared` alone — never *certified*, never *compatible with*.
**Version:** next free `<change>`. **Size:** one person, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **J1** | 2a | **File the `I-16` defect first** (`ledger/models.py:832` `target` mixes a place with a format). `accounting_file` manifest — **no credential** for a download target; the connection carries `destination ∈ {download, drop}` × `codec ∈ {qbo, xero, csv, iif}` and maps to the existing `EXPORT_TARGETS` string on the batch until the ledger retires it · `adapters/accounting_file.py` `test()` writes a zero-row export — *Wrote an empty QuickBooks file* · file-out key **period + target** through `ledger/exports.py`'s `overlapping_batch` / `content_hash` (`:317`, `:328`) — regenerate identical or refuse *July was already exported on 5 Aug*; readiness *N unmapped* from `ledger_accounts` export codes / D2's rows (`BR-LED-014`) — no file offered above zero; **an outbound unregistered codec refused by name with the list** (`US-INT-038`) · Nacha return-code rows (`R01 → nsf`; **`R02` → `other`, raw code kept on the payload, the chooser raises `NotImplementedError("OQ-INT-1487")`**; the four signed reasons not widened) · `camt053` codec on the bank connection with a **recorded, redacted real-bank fixture**; MultiSpeak and Green Button not claimed (`OQ-INT-1483` bounds the wording) — this completes `US-INT-033`'s file-out acceptance (TC-2, 3, 5) | 009 · 038 · 033 · `BR-INT-020` B · `031` · `033` · `053` · `010` · `BR-LED-004` · `014` | D1 · D2 · C1 | `C36` · `T-1.16` (the CR names it as `C36`'s dependency) · `C32` | L |
| **J2** | 2b | S43 picks the saved target — *QuickBooks · IIF · monthly · download* (frame `80.1`); S42's connections panel reads the read-model; *3 accounts still need an export code*, no file; S141's accounting variant with the format picker; S143 shows `R02` red | 009 · 038 · `BR-INT-031` · `033` | J1 · D3 · B4 | `C8` | M |
| **J3** | 2c | `US-INT-033` TC-2, 3, 5 · `US-INT-038` TC-1..7 (TC-5 the `R02` boundary asserted; TC-6 a codec with no fixture fails the kit) · `US-INT-009`'s TCs and `010`'s accounting half. Fixtures: `J19`'s July export; three unmapped accounts; Nacha `R01 R02 R03`; the camt.053 file | 009 · 038 · 033 | J1 · J2 | — | M |
| **J4** | 2d | **`cr069-j-export-target.mjs`** (`J19`'s leg): Alex → S43 → export July to the saved target → the file → regenerate → byte-identical (hash equal) or *July was already exported on 5 Aug* → request `xlsx` through the API → *xlsx is not a registered format — QuickBooks, Xero, CSV, IIF* → with three accounts unmapped, S43 reads *3 accounts still need an export code* and offers no file → S143: `R02` in red, `R01` mapped · screenshots. **`J19` gains its leg** | 009 · 038 · 033 · `BR-INT-020` · `031` · `033` | J2 · J3 | — | S |
| **J5** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · the `I-16` defect row closed with its evidence | — | J4 | — | S |

**Demo script J (Alex Reed):** 1 Finance → export → the destination is remembered → 2 export July → a file → 3
export July again → the same bytes, or the sentence naming 5 August → 4 ask for `xlsx` → refused, and the four
registered names are in the refusal → 5 un-map three accounts → *3 accounts still need an export code*, and no file
is offered → 6 open the kiosk's mappings → `R01` reads *not enough money*, `R02` is red and waits.
**Exit test:** `BR-INT-020` B — period + target gives the same file or refuses, never a different file silently;
`BR-INT-031` — inbound degrades, outbound refuses by name; `OQ-INT-1487` — nothing chooses a reason for `R02`.

---

#### ✅ AS BUILT — 2026-09-06, `2.203.0`

**What a utility can do now that it could not before.** The accounting export target is a
CONNECTION. Alex saves *Month-end journal · QuickBooks · downloaded here*, presses **Test it
now**, and reads **Wrote an empty QuickBooks file.** — a real IIF file carrying QuickBooks'
own `!TRNS` declarations and no entries in it. Ask for July twice and the second is refused,
in words, naming the date the first went: **July was already exported on 5 Aug**. Ask for
`xlsx` and it is refused BY NAME with the four that exist: **xlsx is not a registered format
— QuickBooks, Xero, CSV, IIF**. And S43, which had no memory at all, now reads **Going to
Month-end journal · QuickBooks · downloaded here** and opens its picker on the saved format.

| Task | What landed |
|---|---|
| **J1** | `DEF-INT-4243` filed FIRST (`I-16`) · `manifests/accounting_file.py` — `destination ∈ {download, drop}` × `file_format ∈ {qbo, xero, csv, iif}` · `adapters/accounting_file.py`, the SIXTH adapter and the first outbound file one · `departures.py`, the mirror of wave I's `arrivals.py` · `services.request_export` + `POST /integrations/{key}/export` · the `iif` encoder with a recorded own-emitter fixture · the `camt053` decoder · seven message keys in eleven catalogues |
| **J2** | S43 names the saved destination and defaults its picker to the saved format (`savedExportTarget`, `finance.export.savedTarget`) · `selectors.settings_for` serves a connection's non-secret settings, filtered by the manifest's own `Field.kind` · S141's accounting variant is generated from the manifest and needs no screen change |
| **J3** | `tests/test_us_int_038_export_target.py` — 26 cases · the `financeSurface` block — 5 cases · two `test_us_int_039` records MOVED deliberately |
| **J4** | `10-scripts/render-checks/cr069-j-export-target.mjs` — ten steps in a real browser against a real PostgreSQL, with four declared gaps that go red in BOTH directions |
| **J5** | this stamp · CHANGELOG · version · decision-log row · review-ledger row · `DEF-INT-4243` and `DEF-INT-4245` |

**What was NOT built, and why — the split, honoured (`CR-069` §20.4, `BR-INT-054`):**

* **Readiness** — *3 accounts still need an export code* is a business judgment about the
  chart of accounts and MOVED. `departures.export_readiness()` answers `{}` and says so.
  ⚠ S43's OWN *blockedRefs* line is the **LEDGER's** `missing_refs` and is untouched: the
  ruling moved integrations' copy of that judgment, not the ledger's.
* **What goes IN the file.** `departures.journal_rows()` answers `[]`. Both are **deliberate
  absences, not stubs** — nothing is unruled — and a test goes red the day either fills, so
  the boundary cannot close in silence.
* **The Nacha return-code mapping** — wave `D`'s ETL table one module along. `mappings.py`
  already refuses `R02` BY RULING (`OQ-INT-1487` (b), closed 2026-09-04); nothing was added.

**Two defects found by building it:**

* **`DEF-INT-4243`** (the `I-16` defect, filed before the first line was written) —
  `ledger/models.py:832`'s `target` answers two questions with one four-value list. Fixed ON
  THE CONNECTION; the ledger column and its signed key `uq_export_batches_period_target` are
  untouched, so `DEF-INT-4243` stays **open** for the ledger's own wave.
* **`DEF-INT-4245`** — `uq_integration_connection_key_env` allows ONE connection per provider
  per environment, so *the QuickBooks target and the CSV copy for the auditor* that
  `US-LED-016` TC-2 describes **cannot both be SAVED**. The handover is unaffected and a test
  proves it. Widening that constraint touches every provider on a shared table.

**Three honest gaps, each recorded so it goes red in BOTH directions:**

* **`camt053` decodes and is STILL not a *supported* format.** `BR-INT-033` makes the
  FIXTURE decide, and no redacted statement from a real bank has been recorded. That is an
  ARTEFACT a going-live utility hands us, not a decision anybody can rule. The decoder is
  proved against a structural fixture held under `tests/`, deliberately OUTSIDE
  `fixtures/camt053/`, so a file written to exercise a parser can never make the kit say
  *supported*. ⚠ **This is a THIRD state the codec registry had no word for** — *name only*,
  *code with no recorded file*, *supported* — and it is now written down in three places.
* **`xero` stays name-only, and its `arrives` label now names a MODULE rather than a wave.**
  Xero's manual-journal column layout is a PROJECTION, and `CR-069` §20.4 puts projections in
  Runbooks. `test()` on a Xero connection answers *No writer for that format yet.* rather
  than a pass it has not earned. `qbo` is wave `I`'s and answers the same way.
* **A `drop` destination cannot dial a real folder on this deployment** — no SFTP client is
  installed, so `FOLDER_WRITER` is unbound and `test()` answers `ok=false` *No folder client
  is installed.* The path is complete and is proved with a bound writer.

**Proved, not merely tested.** Every guard was broken FIRST and its failure quoted, in the
harness that runs it (`pytest`, `vitest`), then restored: step 3 removed from
`record_departure` → *assert True is False* on `.accepted` · step 1 removed → *Failed: DID
NOT RAISE UnregisteredFormat*, twice · a typed sample dropped into `fixtures/camt053/` →
*a typed sample must never live in fixtures/* and `is_supported` flipped True ·
`journal_rows` made to return a row → *assert [{'account': '4100'}] == []* · the format
passed through unvalidated → *expected 'xlsx' to be undefined* · a failed test hiding the
destination → *expected undefined to be 'Month-end journal · QuickBooks · down…'*.

⚠ **AND `npx tsc` IS THE TRAP `CLAUDE.md` LAW 7 NAMES, MET IN PERSON.** This worktree had no
local TypeScript, so `npx --no-install tsc` fetched a newer compiler, aborted on a `baseUrl`
deprecation and reported **no type errors at all**. `npm ci` then
`./node_modules/.bin/tsc` (5.5.4) found six real ones — among them a `ConnectionState` that
has no `"connected"` value, which would have hidden the saved destination on every screen.

**AND PROVED BY CLICKING, WHICH IS WHERE THE TWO WORST THINGS IN THIS WAVE WERE FOUND.**
`cr069-j-export-target.mjs`, against a real PostgreSQL clone: **0 failures, 4 declared
gaps.** S43 reads *Going to Month-end journal · QuickBooks · downloaded here* with the
picker opened on **QuickBooks Desktop file**; S142 reads *Wrote an empty QuickBooks file.*
and *No password is stored for this connection.*; the second July answers **409** naming the
first, `xlsx` answers **422** listing the four, and a different window and a different format
both still answer **201**.

**Two defects that only the browser could find:**

* **`DEF-INT-4254` — a refusal that CRASHED instead of refusing, since wave B.** Three sites
  in `services.py` raised `errors.VAL_INVALID`, **an attribute that has never existed**, so
  `POST /integrations/{key}/connect` answered **HTTP 500 `AttributeError`** for any caller
  outside the modal's two-value control. Python resolves a module attribute at CALL time, no
  screen can reach the branch and no test had sent a value outside the vocabulary — so it sat
  there from 3 September. Fixed to `VAL_UNKNOWN_LOOKUP` and given its first reader.
* **`DEF-INT-4255` — *Running*, forever.** An ACCEPTED arrival or departure deliberately
  leaves its run row open, because only the processing half can close it and that half is
  Runbooks'. Every test asserts that and is right. **Nobody asked what the SCREEN then
  says**, and the answer is *Running* — true for a second and false ever after. Not fixed
  here: the fix is a WORD, and choosing it spans waves `I`, `J` and `C`'s run vocabulary.

⚠ **AND THE WALKTHROUGH ITSELF HAD TO LEARN WAVE `I`'s LESSON TWICE.** A durable connection
means a script demanding `201` from `connect` passes exactly once and then fails on its own
success; `409 already_connected` is a pass, and the assertion says why. The window YEAR is
derived from the clock for the same reason. And the grid check read `body.innerText()`
straight after `networkidle` — which fires before a react-query fetch lands — so it failed
over a card that was present a beat later. All three are law 7's *looking at the wrong
thing*, met three times in one script.

---

### Wave K — the walk: token exchange, the fetch plan, and the file they build · phase 4

÷ **SPLITS, MOSTLY INTEGRATIONS — 2026-09-06 (`CR-069` §20.4).**
**KEEPS:** **token exchange in memory, re-minted mid-walk, one credential row after two
hours** — item (2), and the sharpest illustration of it in the change request; the fetch
plan and paging (how you talk to *this* provider); submit–poll–collect; the safety
parameters and `mutates_partner_state`, which govern the request we send over the
connection. **MOVES:** the **readings projection** — turning what was collected into our
measurement frame is ETL. ⚠ **`meters_neptune360` is ALREADY BIDIRECTIONAL** (operations in
and out) **on one credential**, which is exactly why nobody hit `DEF-INT-4118`'s limit. If
credentials become plural per connection, this wave's exit test *"one credential row before
and after"* must say **per credential**, or it will read as a claim about the connection and
quietly become wrong.

**Goal:** a two-hour collection completes across a ten-minute token and the credential table still shows one
version; a vendor that builds the file while we wait shows *asked them 4 times · checking again in 30 seconds*;
a request missing `actual_consumption` does not leave, and a fetch that closes their routes happens once.
**Stories:** US-INT-028 · US-INT-031 · US-INT-035 🔒
**Depends on:** E (credentials) · G (scheduling) · C (runs) · D (codecs). **Runs in parallel with I and J.**
**Blocked by:** nothing. ⚠ `OQ-INT-1484` was RULED on 2026-09-04 — *"not yet; We will not bring hourly internal data in this product"* — so interval collection is out of scope for every tenant, not merely gated on a storage re-run. It bounded a different operation than this walk and now bounds it permanently: about **26 million rows a year** per utility, and half a billion at the top of the range, not taken on.
**Version:** `2.204.0`. **Size:** two people, two weeks.

✅ **BUILT 2026-09-06 — `2.204.0`.** `K1`, `K2` and `K3` shipped; `K4`'s
review-ledger row is written and the file is `HUMAN-REVIEW-PENDING`; `K6` is this
stamp.

⚠ **`K5` IS WRITTEN AND HAS NOT BEEN RUN IN A BROWSER, AND SAYING SO IS THE
POINT (hard-won law 1).** `10-scripts/render-checks/cr069-k-building-the-file.mjs`
is committed, is nine steps of demo script K, and includes the CONTROL that
separates *the refusal works* from *the endpoint is broken* — the same
collection with all four parameters set DOES run. What stopped it was the
environment rather than the code: the shared seeded template database
(`proof-db.sh`) was **four migrations behind**, one of them this wave's own
`integrations/0007`, and `build --force` took over half an hour on a machine
carrying four other lanes' test runs, and the browser run it finally reached had
not reported by the time this wave signed off. **A walkthrough that
was never driven must not be reported as one that was**, so the claim is
withdrawn here rather than left standing. What IS proved: **33 backend cases**,
**6 screen cases** over the real components, a clean `vite build`, and **six
sabotages each shown RED on the case that should notice** (the decision log of
2026-09-06 quotes every failure). **What only a browser can still tell us** is
whether the three sentences render as sentences — the collecting band, *window
61 of 105*, and the four parameters — and that is the next lane's first job,
with the command in the script's own header. **33 backend cases and 6 screen cases pass**, and every guard was proved
RED first (the six sabotages and their failures are in the decision log of
2026-09-06). What a utility can do that it could not: **connect the water meter
cloud and collect from it** — the card was live and connect was refused
*Cannot be connected yet.* until the seventh adapter was bound.

⚠ **THE VERSION ON THIS WAVE READ `2.203.0` FOR ONE COMMIT AND IS `2.204.0`.**
A sibling took `2.203.0` for the accounting-export release while this wave was
being built, and `allocate.py` — which asks the REMOTE rather than the local
checkout — said so on the next call. That is law 11's version collision
(`DEF-GOV-3756`): every lane's arithmetic is right, and what is wrong is which
world the maximum came from. Recorded rather than silently corrected, because a
version that moves after a stamp is exactly the thing a later reader would
otherwise treat as a typo.

⚠ **ONE STORY CASE MOVED RATHER THAN SHIPPED, AND IT IS NOT A DEFERRAL.**
`US-INT-035` TC-5 — *a response amount with no declared unit in the PROJECTION
is refused by name* — is a projection case, and `CR-069` §20.4 moves the
readings projection to Runbooks in as many words. The REQUEST half of hard rule
3 is met here as the manifest's `unit_of_measure` safety parameter; the RESPONSE
half travels with the projection. `apps/integrations/seams/runbooks.py` is the
door, it returns nothing, and two tests assert it — one on the seam and one on
metering's own tables, so a projection that crept back would show as ROWS rather
than as a changed return value.

⚠ **AND `collect_interval_data` STAYS DECLARED AND IS NEVER BUILT.**
`OQ-INT-1484` closed on 2026-09-04 for **every** tenant (*"we will not bring
hourly internal data in this product"*; ≈ 26 million rows a year per utility,
half a billion at the top). It is one of the sixteen operations the vendor's own
catalogue offers, so the manifest keeps it and no runner walks it — it is absent
from `OPERATION_PATHS` by name with the ruling quoted beside the absence.

⚠ **A DEFECT WAS FOUND BY THIS WAVE'S OWN NEW GUARD AND FILED BEFORE IT WAS
FIXED: `DEF-INT-4244`.** `print_vendor` had declared `completion =
submit_poll_collect` since `2.131.0` with no poll schedule and no
`result_delivery`, so a print hand-over would have submitted and waited for ever.
The registry now refuses that at LOAD, and the refusal went red on a real
manifest the first time all eighteen were validated together.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **K1** | 2a | `manifests/meters_neptune360.py` (sixteen operations, one credential, `auth.mode = token_exchange`; fetch plan `window = 7 days`, `page_size = {readings: 5000, meters: 150, routes: 100}`; `safety_parameters` — four, `actual_consumption` among them; `billing_export` with `completion = submit_poll_collect`, `poll = {every: 30 s, max: 40}`, `result_delivery = link | handle`, `mutates_partner_state = true` on `CloseOnExport`) · `adapters/meters_neptune360.py` against recorded fixtures · `runtime.py` token exchange **in memory only — never a credential row**, re-minted mid-walk · `runners/fetch.py` walks windows × pages with `core.jobs` checkpoints (a failure at window 61 resumes at 61) · submit–poll–collect through the job framework (`record_progress` → *asked them 4 times · checking again in 30 seconds*); the poll budget exhausted → `unconfirmed` *they never finished the file* · a request leaving a safety parameter unset **does not start** — *not started — actual_consumption was not set* · `mutates_partner_state` → an idempotency key and a receipt written **before** the call; a retry refused *already closed on 1 Sep* · a numeric without its declared unit refused by name (the measurement-frame object of `BR-INT-049` lands here for the readings projection). 🔒 `HUMAN-REVIEW-PENDING` on the files | 028 · 031 · 035 · `BR-INT-047` · `046` · `050` · `018` · `020` · `025` · `049` · hard rule 3 | E3 · G1 · C1 · D1 | `T-7` group (16) · `C10` `C11` `C12` `C18` `C19` `C20` | L |
| **K2** | 2b | S142: *They are building the file. We will collect it when it is ready · asked them 4 times · checking again in 30 seconds* (frame `53.2`), *window 61 of 105* progress, the two refusal sentences; S141's Neptune variant (the key pair from the manifest); frame `83.1` *what we ask them for* — the four parameters shown explicitly | 028 · 031 · 035 · B14 rule 32 | K1 · C3 · B4 | `C10` | M |
| **K3** | 2c | `US-INT-028` TC-1..6 (≥ 11 re-mints, one credential row; resume at 61; logs carry neither the pair nor a token) · `US-INT-031` TC-1..6 (fixtures *v1 link*, *v2 handle*, *never ready*; TC-5 load refusal) · `US-INT-035` TC-1..6. Recorded Neptune-shaped fixtures, no network | 028 · 031 · 035 | K1 · K2 | — | L |
| **K4** | review | Review-ledger row for `US-INT-035` in plain English with the figure: *an export carrying CloseOnExport closes their routes once and a retry is refused; one supplier has four request parameters that fail open, two of them on the money path* | 035 · CLAUDE.md 🔒 | K1 | — | S |
| **K5** | 2d | **`cr069-k-building-the-file.mjs`**: Alex → the Neptune connection → run the billing export → S142 shows the collecting sentence with the count rising → close the tab, reopen → `succeeded` with the artifact link → run the readings collection with the template missing `actual_consumption` → *not started — actual_consumption was not set* → retry the `CloseOnExport` export → *already closed on 1 Sep* → S142 shows one credential version after the two-hour walk fixture · screenshots | 028 · 031 · 035 · `BR-INT-046` · `047` · `050` | K2 · K3 | — | S |
| **K6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row | — | K5 | — | S |

**Demo script K (Alex Reed):** 1 run the billing export → 2 *They are building the file. We will collect it when
it is ready · asked them 4 times · checking again in 30 seconds* → 3 leave the page and come back → 4 the run is
`succeeded` and the file is linked → 5 start the readings collection with a parameter missing → *not started —
actual_consumption was not set*; nothing left → 6 run the route-closing export twice → the second reads *already
closed on 1 Sep* → 7 after the two-hour fixture walk, the credential history shows one version.
**Exit test:** `BR-INT-046` — a run is not finished until the file is collected, and an exhausted poll is
`unconfirmed`; `BR-INT-047` — one credential row before and after; `BR-INT-050` — no vendor default on a money
path, and one close, not two.

---

### Wave L — readings that arrive late · phase 4

⚠ **MOVES WHOLE TO RUNBOOKS — 2026-09-06 (`CR-069` §20.4).** Reconcile by natural key,
insert four readings, supersede two, **never touch a reading already billed and raise a
correction naming the bill**, list the register differences — that is **record updates and
business logic** from the first line to the last, and record updates were named for
Runbooks in the original ruling of 2026-09-05. Nothing in this wave is a connection.
⚠ **The 🔒 `HUMAN-REVIEW-PENDING` obligation on `runners/reconcile.py` travels with it.**
**Letter and task ids kept, not reused. 4 people-weeks leave integrations.**

**Goal:** Tuesday collects the same three days as Monday after the supplier filled four gaps and revised two
values: the run reads *1,240 read · 6 revised*, 1,238 rows do not move, and a reading already billed is never
touched — the difference becomes a correction. A missed night on a one-day flag raises. The register sync shows
what it would change and changes nothing.
**Stories:** US-INT-034 🔒 · US-INT-036 ⚠
**Depends on:** K (the walk) · G (scheduling) · D (mapping rows). ⚠ **UNBLOCKED 2026-09-04 — `OQ-INT-1485` ruled option (a): WE ARE MASTER of the meter-to-account link and the head-end's version is shown as a DIFFERENCE, never applied.** Not (c) either — the head-end may not even FILL an empty link, because a link we do not hold is a link a person has not made. `seams/assets.py` now has a rule to implement instead of a boundary to raise at. **Was blocked by:** `OQ-INT-1485` — every write of
`US-INT-036`; the boundary is demonstrated.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **L1** | 2a | **`runners/reconcile.py`** 🔒 — `idempotency.mode = reconcile` by the natural key `meter · register · read_at`; the fifth count `changed`; four new readings inserted and two superseded **through metering's service** (`seams/metering.py` → `apps/metering/services.py` `supersede_read` at 7344 and the correction path — verified callables, not an adapter write); **a reading already billed does not move** — a correction is raised naming the bill (hard rule 4); a manifest declaring `reconcile` with no natural key is refused at load; `must_not_skip` — a missed night on the one-day register change-out flag **raises** *missed 2 Sep — the change-out flag for that day cannot be refetched*. **`US-INT-036` to the boundary:** the register sync collects the supplier's meter records into staging on the run artifact, lists the differences (*size 5/8" for MTR-2210, we hold none*), and **`seams/assets.py` raises `NotImplementedError("OQ-INT-1485")` at the write**; a size without its unit is refused by name; an unmapped route records as `other` and goes red on S143. 🔒 `HUMAN-REVIEW-PENDING` | 034 · 036 · `BR-INT-029` · `050` · `031` · `032` · `049` · hard rule 4 | K1 · G1 · D2 | `C13` · `C21` · `T-B6` (the ruling) | L |
| **L2** | 2b | S142 *1,240 read · 6 revised* (frame `83.2`); the raised row and the S8 panel's attention; the register sync's difference list with *waiting for a decision* wording; S143's red route row | 034 · 036 · B14 rule 32 | L1 · C3 · D3 | — | M |
| **L3** | 2c | **`tests/pg/test_us_int_034_reconcile_pg.py`** TC-1 (1,238 `updated_at` unchanged), **TC-2 red-first** (a refuse-only guard reports *1,240 duplicates refused*, loses six and goes green — recorded), TC-3 (the billed reading untouched, a correction naming `BL-2609-0044`), TC-4, TC-5, TC-6 · `US-INT-036` TC-1 (the raise asserted), **TC-2 written now and skipped until `OQ-INT-1485` closes**, TC-3..5. *The backfill* fixture — Monday 2026-08-31, 1,240 readings for 28–30 Aug; Tuesday's response with four added and two revised (`MTR-2210 · 4,517 → 4,571 gal`, `MTR-0987 · 12.3 → 12.8 kWh`), `MTR-2210` billed on `BL-2609-0044`; the one-day change-out flag | 034 · 036 | L1 · L2 | — | L |
| **L4** | review | Review-ledger row for `US-INT-034`: *1,240 read · 6 revised · 1,238 untouched, and a reading already billed does not move — the difference is a correction* | 034 · CLAUDE.md 🔒 | L1 | — | S |
| **L5** | 2d | **`cr069-l-backfill-tuesday.mjs`** (`J55` on PostgreSQL + `J57`'s boundary): run Monday's collection → S142 *1,240 read* → run Tuesday's → *1,240 read · 6 revised* → open the run → the billed reading's line says a correction was raised naming `BL-2609-0044` → run the register sync → S142 lists *size 5/8" for MTR-2210, we hold none* and *waiting for a decision*; `assets` unchanged (read back through its API) · screenshots. **Journeys `J55` and `J57` written** | 034 · 036 · `BR-INT-029` · hard rule 4 | L2 · L3 | — | S |
| **L6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row | — | L5 | — | S |

**Demo script L (the nightly collection, then Priya):** 1 Monday's collection: *1,240 read* → 2 Tuesday's, same
three days: *1,240 read · 6 revised* → 3 open it — four new, two revised, 1,238 untouched → 4 the revised reading
that was already billed: not moved; a correction raised, naming the bill → 5 the change-out operation misses a
night → a raised row, not a quiet catch-up → 6 the register sync runs → *size 5/8" for MTR-2210, we hold none* →
7 the meter's record in Assets is unchanged, and the screen says a decision is waited on.
**Exit test:** `BR-INT-029` and hard rule 4 on PostgreSQL — six rows move, 1,238 do not, none of the billed ones
is touched, and the recorded red run shows a refuse-only guard losing six readings while green; `OQ-INT-1485` —
the write raises, and the demonstration ends one step early, as `J57` says it must.

---

### Wave M — the address search and the map · phase 4 · ✅ **AS BUILT 2026-09-06 (`2.205.0`)**

✅ **BUILT — `2.205.0`, 2026-09-06.** The `gis_city` adapter (323 lines), the generated page-security
policy (282 lines) and the browser walkthrough (357 lines) are on the branch across five commits.
⚠ **THIS STAMP WAS MISSING FOR HOURS AND THE WAVE READ AS *not started* BECAUSE OF IT** — twice, to
the Product Owner, in a status answer assembled by searching this file for the words *AS BUILT*.
The wave recorded its completion in its own prose and in the story register, in different words.
**A wave's doneness must be answerable by a machine reading ONE place** (`DEF-INT-4264`); until it
is, a status report is a grep against inconsistent prose and will keep being wrong in the safe-
looking direction — reporting built work as not started, which costs a re-dispatch rather than a
revert, but is wrong either way.

÷ **SPLITS, MOSTLY INTEGRATIONS — 2026-09-06 (`CR-069` §20.4).**
**KEEPS:** the `gis_city` connection, the `executor` declaration
(`server | browser | browser_credentialed`), the generated page-security policy, connection
records for the two live calls that have none, the breaker, the search endpoint.
**MOVES:** ⚠ **NOTHING — CORRECTED 2026-09-06.** The write was listed here as moving:
a picked candidate becoming a premises. **`OQ-INT-1728` was ruled option (a) and it does
not move.**

⚠ **RULED 2026-09-06 (`OQ-INT-1728`) — A PERSON'S SYNCHRONOUS WRITE ON A SCREEN STAYS WITH
THE MODULE THAT OWNS THE SCREEN.** PO verbatim: *"(a). Every other Runbooks example is a
batch nobody is watching. Routing a form submit through a runbook to write one row while
somebody waits is a different animal, and slower for no benefit. Keeps ~3 of wave M's 4
weeks here. - we provide both option schedule it as a batch job or you run it one time as a
batch job"* So **Priya pressing Create is integrations' work, this wave keeps its write,
and about three of its four people-weeks stay here** — the figure the PO ruled on.

⚠ **AND THE CLAUSE AFTER THE DASH IS AN ADDITION, NOT A RESTATEMENT — IT IS THE PART A LANE
WILL MISS.** The same work must **also** be available as a batch, **in two forms**:
**scheduled**, and **run once, on demand**. That is **three ways to do one job, and all
three get built**:

| | The way | Whose |
|---|---|---|
| **1** | Priya's synchronous write on the screen, while she waits | **integrations** — this wave, ruled by (a) |
| **2** | the same work **scheduled** as a batch job | **Runbooks** — scheduling is Runbooks' under `BR-INT-054` |
| **3** | the same work run **once**, as a batch, started by a person | **split: the trigger is the screen's, the running is Runbooks'** |

**Do NOT collapse 2 and 3 — the PO named both.** Row 3 splits because **a person pressing
*Run it now* is TRIGGERING, not SCHEDULING**: scheduling decides *when*, and a button
decides nothing about when. It is the same distinction `BR-INT-054` already draws for wave
`H`'s sweep body running on Runbooks' clock, with a person in the place of the clock.
⚠ **Neither batch form is sized in this wave's four people-weeks, neither is sized anywhere
else, and this ruling commissions nothing** — sequencing is unchanged.

**Goal:** Priya types an address and sees the City's candidates in under a second, picks one, and the premises is
written from what the City holds — nothing queued, nothing written until she picks; the map is drawn by the
browser with no tenant secret and a generated page-security policy; when the City is slow the screen says so.
**Stories:** US-INT-042 ⚠ (one branch)
**Depends on:** B (adapters, modal) · F (the breaker) · A (manifests). **Runs in parallel with I, J and K.**
**Blocked by:** nothing. ⚠ `OQ-INT-1471` was RULED on 2026-09-04 — *"(b) type it, marked unchecked"* — so the unreachable branch is a BUILD: the premises is created, marked **unchecked**, and re-checked on the next night's run. The mark must be VISIBLE wherever the premises is read, because the danger this question named was that the bad case looks identical to the good one.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **M1** | 2a | **File the two `I-15` defects first** — `apps/metering/geocode.py` (Census, `CR-028` D6) and `features/assets/AssetMapTab.tsx:51` `ESRI_TILE_URL` are live third-party calls with no connection record. `executor` per operation `server | browser | browser_credentialed`; `gis_city` manifest (address search **inline**, `latency_budget_ms = 1000`, `result_disposition = offer`; map tiles `executor = browser`; the nightly reconciliation declared, its runner is wave Q) · `map_tiles_public` and `geocoder_census` gain connection records and health (the geocoder keeps *fill empties only*, D6) · **a Content-Security-Policy generated from the registered browser operations** — none exists at HEAD in `07-frontend/server.mjs` or the settings; the lane decides where it is served and records why · the inline runner: no job row, one `inline` run row per search session (*14 lookups · 1 pick*); the breaker (F1) opens on a slow City; `GET /integrations/gis_city/address-search?q=` · the write: a chosen candidate → premises through `metering.services` with the parcel **re-checked live at the moment of the write**; **the unreachable branch is a BUILD** — `OQ-INT-1471` was ruled option (b) on 2026-09-04, so Create writes the premises with no parcel key and marks it `gis_unchecked` (metering `0054`), and the mark is served wherever a premises is read (⚠ **THIS CELL SAID THE BUTTON RAISES `NotImplementedError("OQ-INT-1471")` UNTIL 2026-09-06**, two days after the ruling and in contradiction of this wave's own *Blocked by* line above — amended 2026-09-06 by the CR-069 wave M build lane) | 042 · `BR-INT-048` · `022` · `003` · `CR-028` D6 | B1 · F1 · A4 | `C14` `C15` `C16` · `T-8` group (the search half) | L |
| **M2** | 2b | `features/metering/AddPremisesWizard.tsx` step 1 *Find the address* (frames `66.1` / `66.2`): candidates under a second as `MatchRow`s (*strong match · close match* — **no score shown as a number**), *Use this* fills the fields, Create re-checks; the slow-City sentence *the city's address service is not answering*, no spinner; the boundary sentence *Waiting for a decision on adding addresses while the city is offline*; the S8 card reads *the call is made by the browser*; *Test it now* shows two results — the server's reach and this page's reach; the `AssetMapTab` tile layer reads its host from the connection | 042 · B14 rules 21 · 32 | M1 · B4 | `C14` `C15` `C16` | L |
| **M3** | 2c | `US-INT-042` TC-1..7 (fixture latencies 300 ms and 4,000 ms; candidate *1408 Pecan St · parcel 88214 · 30.2672, −97.7431 EPSG:4326*; the CSP lists exactly the registered tile host per tenant; TC-4 the boundary) | 042 | M1 · M2 | — | M |
| **M4** | 2d | **`cr069-m-address-search.mjs`**: Priya → Add premises → type *1408 Pec* → candidates within a second (timed) → *Use this* → Create → the premises carries `external_ref 88214` → switch the fixture to slow → the field reads *the city's address service is not answering* → type the address by hand → Create → *Waiting for a decision on adding addresses while the city is offline* → the response's CSP header names exactly the tile host · screenshots | 042 · `BR-INT-048` · `022` | M2 · M3 | — | S |
| **M5** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (where the CSP is served) · the two `I-15` defect rows closed with evidence · **phase 4 closes when I–M are done** (twelve stories, two to the boundary) | — | M4 | — | S |

**Demo script M (Priya Menon):** 1 Add premises → 2 type *1408 Pec* → four matches from the City within a second,
*strong* and *close* in words → 3 *Use this* on *1408 Pecan St · parcel 88214* → 4 Create → the parcel is checked
against the City again at that moment; the premises exists with the parcel on it → 5 the City slows to four
seconds → the field says *the city's address service is not answering*, no spinner → 6 type it in by hand and
press Create → *Waiting for a decision on adding addresses while the city is offline* → 7 the map on the premises
screen draws from the browser, and the page's security header names only the tile host.
**Exit test:** `BR-INT-048` — candidates under the budget with nothing queued and nothing written before a pick;
a browser operation carries no tenant secret and the policy is generated; `OQ-INT-1471` — **the unreachable branch
BUILDS**: the premises exists, carries no parcel key, and is marked *unchecked* where every screen can see it.
⚠ **THE LAST CLAUSE READ *"raises rather than choosing"* UNTIL 2026-09-06** (amended 2026-09-06 by the CR-069 wave M build lane) — the exact opposite of the
ruling the *Blocked by* line above has carried since 2026-09-04.

---

### Wave N — the kiosk payment, twice · phase 5 (the phase-5 LAUNCH)

✅ **BUILT AS THE DOOR — 2026-09-06, `2.206.0`. `N2` (the integrations half), `N4`, `N5` and this
stamp are done; `N1`, `N3`, `N6` and the rest of `N7` are NOT, and each has a reason below rather
than a deferral.** What a kiosk sending the same payment twice now gets: `200` and one
`payment_webhook_events` row keyed `K-88231|payment` the first time; `409` and **nothing written**
the second; a return carrying the same `K-88231` answers `200` because its key is `K-88231|return`.
**Payments recorded: ZERO** — `record_payment` with channel `KIOSK` is Runbooks' under `BR-INT-058`.

| Task | State | Why |
|---|---|---|
| **N1** | **NOT BUILT** | `payments.channel` / `external_ref`. The migration is payments' own and on neither book, but its ONLY writer is `record_payment` with channel `KIOSK`, which §20.4 moved. A column with no writer and no reader is hard-won law 2 in a migration; it lands with the lane that fills it. |
| **N2** | **BUILT (the integrations half)** | `inbound.py` · `inbound_api.py` · the landing seam · two new manifest fields (`Auth.header`, `Idempotency.key_field`). **`adapters/payments_kiosk.py` was NOT written**: `Manifest.we_never_dial` landed the same day for `DEF-INT-4215`, so a connector every operation of which is `initiative = them` needs no adapter, and one would have had four methods with no caller. The `record_payment` / reversal / `DRIVEUP → OTHER` / risk-flag clauses of this row are Runbooks'. |
| **N3** | **NOT BUILT — and this wave has NO SCREEN** | Every item N3 lists DISPLAYS a fact only the apply half writes: the payment detail's *Kiosk · K-88231*, the report split by channel, S143's red `DRIVEUP` row. Said explicitly rather than left silent (r11 step 2b). What a person DOES see needed nothing built — each landing writes an `IntegrationRun` row and **S142 (`ConnectionDetailPage`) already draws those**, grouped by the operation's own label. |
| **N4** | **BUILT** | `tests/test_us_int_044_inbound_door.py` — TC-1..TC-7, TC-9, TC-10, the boundary and the fail-closed cases; **23 green on PostgreSQL 16.13**, 30 green + 2 skipped on SQLite. The redacted capture is in `apps/integrations/fixtures/payments_kiosk/`. **TC-8 and TC-11 are not here** — both moved with `record_payment`, and §4's five accounts belong to that same half. |
| **N5** | **BUILT** | The review-ledger row for `inbound.py`, in plain English with five numbered figures, **and it re-asks wave A's unanswered `human_owned.txt` glob** (G53 — a lane may not add itself). |
| **N6** | **NOT BUILT** | `J59` and `cr069-n-kiosk-twice.mjs` walk *the payment appears on the account*, which is the half that is not built. A walkthrough of a door with no screen would assert an HTTP status a test already asserts. |
| **N7** | **PART** | CHANGELOG · version `2.206.0` · four decision-log rows · `BR-INT-058` stamped BUILT · endpoints row 25 stamped · this table. **Phase 5 is NOT declared LAUNCHED** — its exit test names *"applied exactly once"*, and nothing is applied yet. |


÷ **SPLITS — 2026-09-06 (`CR-069` §20.4) — AND THE LINE FALLS WHERE THE MANIFEST ALREADY
DRAWS ONE.**
**KEEPS:** **authenticate** (the `X-Kiosk-Key` and the source allowlist, *before the body is
read*), **dedupe** on the composite key, **reply** `200` / `409`, **persist raw**.
**MOVES:** `record_payment` with channel `KIOSK`, the reversal row for a return,
`DRIVEUP → OTHER`, and showing the risk flag to a clerk.
⚠ **The split lands exactly at `respond_after = dedupe`** — a boundary the manifest file
format already has. The PO's line and the format's line turn out to be **the same line**,
which is the strongest evidence available that this is a real seam rather than an imposed
one. `N1` is payments' own migration and is on neither book.

**Goal:** a kiosk posts `K-88231 · $42.10 · CASH` for `ACC-1048` and it appears on the account with no clerk
keying it, channel *Kiosk*; the kiosk replays it and gets `409` before anything is posted; a return carrying the
same id reverses the payment and is not mistaken for a duplicate.
**Stories:** US-INT-044
**Depends on:** B (door skeleton) · C (runs) · D (tender mappings) · E (the kiosk key in the credential table) ·
N1 (payments' columns). **N1 can start on day one.** ⚠ A ruling reading *"(a) accept and flag"* arrived against
`OQ-INT-1485` on 2026-09-04, and the PO confirmed the same day that it belongs to **`OQ-INT-1486`**: a risky-flagged
payment is **accepted and the flag is SHOWN ON THE PAYMENT FOR A CLERK** — not held, not notified. ⚠ **`N2` KEEPS THE
FLAG ON THE RAW ENVELOPE AND THAT IS NOW HALF THE JOB:** what the ruling adds is the clerk-visible half, and *no hold,
no notification* does not build it. Allocation is NOT held, deliberately — a held allocation is money the customer has
paid that their balance does not show, and they cannot see why. **Blocked by:** nothing — `OQ-INT-1486` (a risky-flagged
payment) bounds the flag's handling only, and the raw flag is kept.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **N1** | 2a (payments') | **`payments.channel` and `payments.external_ref` do not exist** (`payments/models.py:1120` is a comment) — payments' own migration adds `channel ∈ {KIOSK, COUNTER, PORTAL, OTHER}` (default `COUNTER`) and `external_ref`; `record_payment` (`payments/services.py:821`) accepts both; the reversal path accepts a mapped reason; the payments report separates takings by channel (`US-INT-044` TC-11). Payments' lane, payments' migration | 044 · `C31` / `BR-INT-053` · `BR-PAY-036` · hard rule 4 | — | `C31` · `T-6.05` (the CR names it as `C31`'s dependency) | M |
| **N2** | 2a | `manifests/payments_kiosk.py` (three operations: *Account lookup* `respond_after = authenticate`; *Payments* and *Returns* `respond_after = dedupe`, status map `{ok: 200, duplicate: 409}`) · `adapters/payments_kiosk.py` · **`inbound.py`** 🔒 for the kiosk: **authenticate** — the `X-Kiosk-Key` credential header and the source allowlist `198.51.100.0/24, 203.0.113.7` **before the body is read** (this provider carries no signature) → **dedupe** on the composite key `kiosk · K-88231 · payment | return` **through `payments/webhooks.py`'s two guards** (`PaymentWebhookEvent`, `payments/0020`; `uq_payments_webhook_key`) — no second inbound path → **reply** at `respond_after = dedupe` with the declared map — **the adapter contains neither number** → **persist raw** → **process async** (`integration.inbound_process`) → `record_payment` with channel `KIOSK` and the kiosk's reference; a return → a reversal row (a new row, hard rule 4) with the reason from D2's rows; *Account lookup* answers the balance in the declared shape and an unknown account `200 · status: not_found`, **not** 404; an unmapped channel (`DRIVEUP`) → `OTHER` and a red S143 row, the payment not stopped; **the risk flag (`OQ-INT-1486`): kept on the persisted raw envelope, the run's summary says a flag arrived and a decision is awaited — no hold, no notification, none of the three options taken**. Savepoint per item on PG (TC-9). 🔒 `HUMAN-REVIEW-PENDING` | 044 · `BR-INT-020` D · `021` · `030` · `044` · `045` · `053` · `BR-PAY-003` · `036` · hard rule 6 · law 14 | B2 · C1 · D2 · E3 · N1 | `C3` `C5` `C6` `C31` · `T-6` group · `T-9.04` (verified largely done) · `T-B7` (the ruling) | L |
| **N3** | 2b | The payment's detail shows channel *Kiosk* and reference `K-88231`; S142's three groups worded as the story says — *They send us payments* · *They ask us about an account* · *They send us a return* — never a quadrant name (frame `81.1` *the same payment, twice*); S143's red `DRIVEUP`; the payments report by channel | 044 · B14 rule 32 | N1 · N2 · C3 · D3 | `C1` | M |
| **N4** | 2c | `US-INT-044` TC-1..11 (TC-9 on PG). **The five accounts, seeded before the conversation, not during it:** `ACC-1048 · $142.18` · `ACC-2207 · −$18.50` · `ACC-9999` (unknown) · `ACC-3310` (payments disallowed) · `ACC-5002` (commercial); the kiosk credential (`••••K1OS`); the payment and return payloads; **a real captured payload, redacted, in `fixtures/payments_kiosk/`** | 044 | N1–N3 | — | L |
| **N5** | review | Review-ledger row for `inbound.py` and the kiosk key handling: *$42.10 applied once; the replay answered 409 before anything is posted; a return with the same id reverses instead of being refused* | 044 · CLAUDE.md 🔒 (webhook keys) | N2 | — | S |
| **N6** | 2d | **`cr069-n-kiosk-twice.mjs`** (`J59`): the demo script below, driven by the captured payload · screenshots. **Journey `J59` written** | 044 · `BR-INT-020` · `030` · `045` · `BR-PAY-003` | N3 · N4 | — | S |
| **N7** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · **phase 5 LAUNCH declared** | — | N6 | — | S |

**Demo script N (a kiosk, then Priya):** 1 the kiosk posts `K-88231 · $42.10 · CASH` for `ACC-1048` → `200` → 2
the payment is on the account with no clerk keying it — channel *Kiosk*, reference `K-88231`, cleared and allocated
→ 3 the kiosk replays the same notification → `409`, before anything is posted; still one payment → 4 a return
arrives carrying `K-88231` → not a duplicate; a reversal row; the payment reversed → 5 S142: three inbound runs
under three plain headings → 6 the kiosk posts a payment naming `DRIVEUP` → recorded as *Other*, a red row on S143,
the money not stopped → 7 the payments report: counter takings and kiosk takings on separate lines.
**Exit test (asserts a rule):** `BR-INT-020` D, `BR-INT-030`, `BR-INT-045` and `BR-PAY-003` — **`CR-069` §12's
phase-5 exit test**: a replayed notification is recognised and applied exactly once, answered with the conflict
status the provider expects, and a reversal carrying the same identifier as the payment it reverses is not
mistaken for a duplicate — demonstrated by replaying a real captured payload.

---

### Wave O — we do not know · phase 5 · contingent on `OQ-INT-1476` (ROUTED to the processor) and `OQ-INT-1478`

÷ **SPLITS, MOSTLY RUNBOOKS — 2026-09-06 (`CR-069` §20.4) — AND IT STAYS BLOCKED.**
**KEEPS:** **the idempotency key generated and stored before the request leaves**, the same
key on every retry, `executor = browser_credentialed`.
**MOVES:** what `indeterminate` MEANS, the refused blind Retry, the `charge_status`
companion, recording the payment once — deciding what a result means and what to write is
business logic.
⚠ **THE SPLIT DOES NOT UNBLOCK IT.** `OQ-INT-1476` is **ROUTED to the card processor and
unread**; `OQ-INT-1478` is **OPEN — answered in part**. Neither is ours to answer: they are
facts the processor holds (law 13's third case). **`O` is the ONLY wave in this plan still
genuinely blocked.**

**Goal (boundary):** a charge that times out reads *we do not know* — not failed and never `$0.00` — with a button
to go and ask the processor; a blind retry is refused; the key is stored before the request leaves. The live
charge call itself raises until the processor's documentation is read.
**Stories:** US-INT-045 🔒 ⚠
**Depends on:** N (the door, the kiosk pattern) · C (runs). **Blocked by:** `OQ-INT-1476` (does the processor
accept our idempotency key — *unread*) and `OQ-INT-1478` (signature or shared code); `OQ-INT-1473`, `1474`, `1475`,
`1477` bound `T-9.05`, `T-9.06`, `T-9.08` and the chargeback half — of those, `1473`, `1474` and **`1475`** are now
RULED and `1477` is ROUTED to the processor. ⚠ **`1475`'s ruling has a shape no option offered and `T-9.08` must
build THAT one:** the charge is `min(what the customer authorised, what is owed)`, because the recorded intention
is an authorisation CEILING. A bill corrected DOWN to **$138.42** is taken at $138.42; a bill corrected UP to
**$155.00** still takes only the approved **$142.18** and leaves **$12.82** owing for its own ask.
**`T-9` does not start before `OQ-INT-1476` is
read; the boundary below is buildable now.**
**Version:** next free `<change>`. **Size:** one person, one and a half weeks for the boundary.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **O1** | 2a | The seventh outcome **`indeterminate`** wired in `services.py` (the enum value exists from A3): a charge timing out → `indeterminate`, summary *we do not know*, no `$0.00` anywhere · **our idempotency key generated and stored in payments' idempotency record BEFORE the request leaves** (ordering asserted on the fixture); the same key on every retry · a blind *Retry* refused *ask the processor first* · a companion `charge_status` operation against fixtures — *captured* → the payment recorded once and a **new** run row `succeeded`; *not found* → a new row `failed` and retry allowed with the same key · **the live charge call raises `NotImplementedError("OQ-INT-1476")`** · `executor = browser_credentialed` on the card-page operation (PO: *"they are on Spruce page"*) · `payments_card` stays `COMING_SOON(W7)`; a sandbox connection only. 🔒 `HUMAN-REVIEW-PENDING` | 045 · `BR-INT-052` · `018` · `020` · `048` | N2 · C1 | `C26` `C27` · `T-9` group (10) · `T-9.04` | L |
| **O2** | 2b | S142 and the payment's detail: *we do not know* with **Ask the processor** and the refused Retry (frame `82.2` *a charge with no answer*; the `CountTile` dash); the S8 panel's attention | 045 · B14 rules 32 · 33 | O1 · C3 | `C26` | M |
| **O3** | 2c | `US-INT-045` TC-1..7 (TC-5 key ordering; TC-6 the boundary asserted). Fixtures *timeout* · *captured* · *not found*; the generated key `chg_brazos_9f2e…` | 045 | O1 · O2 | — | M |
| **O4** | review | Review-ledger row for `US-INT-045`: *a $142.18 charge that times out is recorded as unknown; with the key one retry is one charge; without it a blind retry could take $284.36* | 045 · CLAUDE.md 🔒 | O1 | — | S |
| **O5** | 2d | **`cr069-o-we-do-not-know.mjs`**: the sandbox card connection → a $142.18 charge with the timeout fixture → S142 *we do not know* → *Retry* → *ask the processor first* → *Ask the processor* (fixture *captured*) → one payment, a new run row `succeeded` → start a live charge → the boundary sentence · screenshots | 045 · `BR-INT-052` | O2 · O3 | — | S |
| **O6** | blocked | **After `OQ-INT-1476` is read:** the live charge call — with the companion query kept if the answer is no · `T-9.05` the fee line (`OQ-INT-1473` back to the PO with the $147.50 / $137.50 + $10.00 figure; `OQ-INT-1477` the chargeback half) · `T-9.06` card refunds (`OQ-INT-1474`) · `T-9.08` autopay intentions (`OQ-INT-1475`, $142.18 as told vs $138.42) · the webhook code (`OQ-INT-1478`) — each its own task when ruled; not sized here | 045 | O1 · the rulings | `T-9.05` `T-9.06` `T-9.08` · `T-9` | — |
| **O7** | doc / version | CHANGELOG · lockstep · TSV · decision-log row | — | O5 | — | S |

**Demo script O (Alex Reed, on the sandbox):** 1 charge $142.18 → the fixture never answers → 2 S142 reads *we do
not know*, and the amount tile shows a dash, not zero → 3 press *Retry* → *ask the processor first* → 4 press *Ask
the processor* → *captured* → 5 one payment on the account, the run now `succeeded` by a new row → 6 the key row
existed before the first request left → 7 start a live charge → the screen says the processor's documentation has
not been read.
**Exit test:** `BR-INT-052` — a timed-out charge is never rounded to succeeded or failed, a blind retry is refused,
and the key precedes the call; `OQ-INT-1476` — the live call raises.

---

### Wave P — allowed, then stopped · ⚠ **CANCELLED 2026-09-04 — `OQ-INT-1482` ruled (c), no**

⚠ **UNTOUCHED BY THE BOUNDARY RULING OF 2026-09-06.** The wave is cancelled and **its letter
is not reused**. What remains is `P1` and only `P1` — the test proving every write path to
`integration_consent` refuses — and that guard is on an integrations table, so it stays
here. **Nothing in `CR-069` §20 changes anything about `P`.**

**Goal:** ⚠ **THIS WAVE DOES NOT SHIP.** `OQ-INT-1482` asked whether customer-authorised third-party access is in
scope at all and the Product Owner answered **no** on 2026-09-04 — *"c) no"* — not *later* and not *conditionally*.
So `US-INT-046`, `S145`, `S146` and `J58` come out, the two consent endpoints are not mounted, and
`integration_consent` stays in the brief holding no rows.
**What remains of the wave is `P1` and only `P1`:** the test proving every write path to `integration_consent`
refuses. It is kept BECAUSE the feature is cancelled rather than deferred — a table nothing writes needs something
that fails when somebody starts writing it. ⚠ **A DELIBERATE ABSENCE, NOT A STUB:** a lane finding the empty table
leaves it alone. **P3 is deleted, not parked.**
**Stories:** ~~US-INT-046~~ — out of scope
**Depends on:** A (the table).
**Version:** next free `<change>` (the boundary proof is a `<fix>`-sized change to tests only; it rides another
wave's bump if one is open). **Size:** half a day for the boundary.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **P1** | 2c | The boundary only: a test asserting every write path to `integration_consent` raises `NotImplementedError("OQ-INT-1482")`; S145 and S146 have no route and no `screenIds.ts` row; the table exists from A3 and holds no rows | 046 · `BR-INT-036` (OPEN) | A3 | `C9` · `T-B4` (the ruling) | S |
| **P2** | 2d | **`cr069-p-consent-boundary.mjs`**: Settings → Integrations shows no consent card or tab; `/…/settings/integrations/consents` answers exactly as an unknown route does; the test's output quoted | 046 | P1 | — | S |
| **P3** | blocked | **When `OQ-INT-1482` is ruled (a):** the consent service (grantee · scope · `expires_at` · `revoked_at` set, never deleted; `granted_by` is the customer); the SERVE runner checks the consent **on every request**; S145 (template **I9**, *Stop sharing* danger tier) and S146 in the portal (template **I8**; takes the next `CWP` id there); `J58` written; the walkthrough becomes `cr069-p-allowed-then-stopped.mjs` (Maria Alvarez allows *SunPath Installers* twelve months; Priya stops it; the installer's very next request is refused) | 046 · `BR-INT-036` · `035` · `053` · B14 rule 6 | P1 · S1 · the ruling | `C9` | — |

**Demo script P (boundary):** 1 Settings → Integrations — no consent card, no consent tab → 2 the consents route
answers as any unknown route does → 3 the test that asserts the raise, quoted green.
**Exit test:** `BR-INT-036` is OPEN and nothing writes its table — asserted, not assumed.

---

### Wave Q — the night report · phase 5 · ⚠ **UNBLOCKED 2026-09-04 — `OQ-INT-1470`–`1472` all ruled**

⚠ **MOVES WHOLE TO RUNBOOKS — 2026-09-06 (`CR-069` §20.4).** Sorting 69,000 parcels into
seven classes, per-field authority `auto | queue | never`, the money-path refusal and the
decision queue a clerk works through are **business logic and record updates** entirely.
Integrations keeps only the `gis_city` connection, which is wave `M`'s. ⚠ **Two things
travel with it:** the 🔒 `HUMAN-REVIEW-PENDING` obligation, and the **design job**
`OQ-INT-1470`'s ruling handed us — *which* of the new GIS identifiers on `premises` and
`units` is the match key — which becomes Runbooks' to choose and record.
**Letter and task ids kept, not reused. 4 people-weeks leave integrations.**

**Goal (boundary):** the City's nightly file of 69,000 parcels is classified against our 2,914 premises into seven
classes and **reported** — *2,914 matched · 66,086 not ours · 41 would change by themselves · 3 queued · 0
created* — and every write raises until the PO rules which key wins. A change to `inside_city_limits` is refused
naming the column.
**Stories:** US-INT-043 🔒 ⚠
**Depends on:** M (the GIS connection) · L (reconcile mode) · G (nightly) · D (S143). **Blocked by:** nothing —
all three were ruled on 2026-09-04 and `T-8` may start. ⚠ **`OQ-INT-1470` (which key): NONE of the three options.**
The key comes from **new GIS parameters on `premises` AND on `units`** — *"we will have to create GIS parameters on
Premises and Unit and use one of the ID from that for matcing"* — which is exactly where `BR-MET-1161` already keeps
a location, so a map and an envelope cannot disagree. `premises.external_ref` is NOT the key and is not widened.
**WHICH of those identifiers is the match key is OURS to choose and record in the decision log**, and designing that
parameter set is now wave `M`/`Q`'s first task rather than a question. ⚠ **`OQ-INT-1471` (unreachable): create it,
marked unchecked, re-checked overnight.** ⚠ **`OQ-INT-1472` (auto-create): never** — *"City may have more services to
offer and thats why they may have more parcel IDs"*; the ~66,500 *not ours* go on a list a clerk reads, and the night
creates none of them.
**Version:** next free `<change>`. **Size:** two people, two weeks for the boundary.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **Q1** | 2a | `runners/reconcile.py` 🔒 — the GIS night: classify every parcel into **seven classes** (new-to-us · gone-from-city · field changed *auto* · field changed *queue* · money-path field *never* · **two of ours on one parcel key** · one of ours on two keys), each with a disposition; **per-field authority `auto | queue | never`** from the manifest, overridable in `config`, **visible on screen**; **membership separate from content** — *not ours* is its own count and the night **creates none**; **the money-path columns in ONE list in `seams/metering.py`** — `inside_city_limits`, `city`, `state` — the refusal names the column; **a measurement frame** on `lat`/`lng` (EPSG:4326 with bounds — the projected-system and the South-Pole cases refused by name) and on the match score (0–100; `0.8` refused); class six caught and queued **before** any write; `gone-from-city` is a class, never a delete; **the night reports, and every write path raises `NotImplementedError("OQ-INT-1470")`**; `premises.custom_data.gis_confirmed_on` through metering's service, stubbed. 🔒 `HUMAN-REVIEW-PENDING` | 043 · `BR-INT-051` · `049` · `024` · `029` · `CR-028` D6 | M1 · L1 · G1 · D2 | `C17` `C22` `C23` `C24` `C25` · `T-8` group (16) · `T-B1`-style rulings `R-1` `R-2` `R-3` | L |
| **Q2** | 2b | S143's second tab *Waiting for a decision* (template **I5** → **I10** `DecisionCard`: address · meta · blue *what changed* · **red money consequence** · KV rows; B9 matrix: premises · parcel search; class · night · field filters; oldest first; accept · keep ours · open icons; bulk same-class; CSV of the night) — **Accept on a money-path row is stubbed** (frames `75.2` / `84.2` pre-decide it); S142's report figures with *not ours* as its own number (frames `75.1` / `84.1`); S141 the per-field grants shown | 043 · B14 rules 15 · 31 · 32 | Q1 · D3 · C3 | `C22` `C24` | L |
| **Q3** | 2c | `US-INT-043` TC-1..10 (TC-8 the boundary; TC-4, 6, 7 the 🔒 refusals). A fixture generator for the 69,000-parcel night; the 428 / 9 / 419 re-import case; `1408 Pecan St 78702 → 78721`; the district change on `2210 Elm St`; the `inside_city_limits` flip on `900 Riverside Dr`; duplicate key `88214`; the projected and South-Pole coordinates; score `0.8` | 043 | Q1 · Q2 | — | L |
| **Q4** | review | Review-ledger row for `US-INT-043`: *a night takes 69,000 parcels, updates the ones we have, creates none, and reports 66,500 not ours; a night where 2,914 matches become 300 is visible; and no feed ever writes `inside_city_limits`, `city` or `state`* | 043 · CLAUDE.md 🔒 | Q1 | — | S |
| **Q5** | 2d | **`cr069-q-night-report.mjs`**: run the fixture night → S142 *2,914 matched · 66,086 not ours · 41 would change by themselves · 3 queued · 0 created* → S143's second tab lists the three queued with *we hold · the city says* → the `inside_city_limits` row reads *decides tax and no feed may change it* → the premises unchanged (read back) → the boundary sentence on every write · screenshots | 043 · `BR-INT-051` · `049` | Q2 · Q3 | — | S |
| **Q6** | blocked | **After the three rulings:** the `auto` writes through metering's service; the key per `OQ-INT-1470`; the `new-to-us` disposition per `OQ-INT-1472`; the accept / keep-ours commits; `gis_confirmed_on`; the unreachable branch per `OQ-INT-1471` (shared with M) | 043 · 042 | Q1 · the rulings | `T-8` | — |
| **Q7** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · **phase 5 closes when N–Q are done** (four stories, three to the boundary) | — | Q5 | — | S |

**Demo script Q (the night, then Alex):** 1 the City's file arrives — 69,000 parcels → 2 the report: *2,914
matched · 66,086 not ours · 41 would change by themselves · 3 queued · 0 created* → 3 S143's *Waiting for a
decision*: the three, each with what we hold and what the City says → 4 one row wants to flip *inside city
limits* — refused, the column named, and *decides tax* in the reason → 5 two of our premises share a parcel key —
caught and queued, no database error at two in the morning → 6 a coordinate 700 km from the South Pole — refused
by name → 7 nothing in Premises has changed, and every accept says a decision is waited on.
**Exit test:** `BR-INT-051` and `BR-INT-049` — the report is the five counts with *not ours* as its own figure,
the tax columns are never written and the refusal names them, and out-of-frame numbers are refused; `OQ-INT-1470`
— every write raises.

---

### Wave R — a key we issue · GL track · ✅ **AS BUILT 2026-09-06 (`2.200.0`)**

✅ **STAYS WITH INTEGRATIONS — 2026-09-06 (`CR-069` §20.4).** `they_hold_ours`: we mint the
key, show it once, and revoking refuses the partner's very next call. **Item (2) in its
purest form.** ⚠ **For a two-way partner this wave is HALF the job** — `R` builds the key
we ISSUE, `E` holds the key we KEEP, and **InvoiceCloud needs both on one relationship**
(`DEF-INT-4118`). `R` is not wrong; it is incomplete, and the incompleteness is the defect
rather than the wave. **Not blocked** — `OQ-INT-1481` ruled (a) on 2026-09-04.

**Goal — MET.** Alex issues a key for the finance partner and sees it once; afterwards only the four-character
hint; the partner authenticates for Brazos Bend alone; revoking refuses their very next call. ⚠ The old last
sentence — *"Enabling the connection to serve says a decision is waited on"* — was already flagged wrong in this
section and is now simply gone: `OQ-INT-1481` closed on 2026-09-04 and **wave S built the door the same day this
wave built the key**, so the connection serves.
**Stories:** US-INT-040 ⚠
**Depends on:** E (credential table, blind index) · B (the `issued_secret` field kind, the modal). **Runs in
parallel with phases 2–5.** **Blocked by:** nothing. ⚠ `OQ-INT-1481` was RULED on 2026-09-04 to option (a): **the
System Admin** authorises a partner to read, recorded as an **audited grant on the connection** plus a
subprocessor-register row **pointing inward** — the shape the register did not have. **Not (c):** a signed
data-processing agreement is not a precondition, and gating on one would refuse a lawful connection. So *"Enabling
the connection to serve says a decision is waited on"* in the goal above is now WRONG and the enable path is a
build: `runners/serve.py` refuses naming this wave rather than a question.
**Version:** next free `<change>`. **Size:** one or two people, two weeks (plus identity's story).

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **R1** | ground | **Mint identity's companion story (`I-9`)** in `04-docs/05-modules/02-identity/`: `MachineCredentialAuthentication` beside `IdentitySessionAuthentication` (`identity/auth.py:108`; `settings/base.py:187` lists only the session class) — scoped to `tenant_id`, resolving a presented key through `core.crypto.blind_index_candidates`. Identity's to build; integrations declares the field kind and the connection. A `US-IDN-` id is allocated at push from that module's register, not here | 040 · `BR-INT-053` · B1 boundary | — | `C30` | S |
| **R2** | 2a | The `issued_secret` field kind end to end: `POST /integrations/{key}/key` issues or replaces (returned **once**, copyable, never re-displayed), `DELETE …/key` revokes — **the very next call refused**, not the next collection; stored as an encrypted credential with a blind index, `masked_hint`, `config.last_used_at`; `gl_partner` manifest (`initiative = them`, `auth.mode = they_hold_ours`; *What they may read* chips; the allowlist); a key presented against another tenant's route answers as an unknown caller; ⚠ **this row said "enabling the connection raises `NotImplementedError(\"OQ-INT-1481\")` with *Waiting for a decision on who may allow this*" and that is WRONG** — the question closed 2026-09-04 and wave S built the enable path, so nothing here refuses by naming it and a test greps all three files to keep it that way | 040 · `BR-INT-053` · `043` · `003` | E3 · R1 (identity's class) · B4 | `C30` · `T-B2` (the ruling) | L |
| **R3** | 2b | S144 (template **I6** as `08-screen-layouts.md` draws it; B9 matrix: partner · state; issued desc; hint `••••7Q2F` · scope · issued by/on · last used · state; replace icon · revoke danger); S141's `IssuedKeyPanel` (frame `50.1`: the key in mono + Copy, then the hint only); `screenIds.ts` row for S144 | 040 · B14 rules 6 · 15 · 31 | R2 | `C30` | M |
| **R4** | 2c | `US-INT-040` TC-1..7 (TC-6 the boundary; TC-7 the three exits for the issued key) | 040 | R2 · R3 | — | M |
| **R5** | review | Review-ledger row for `US-INT-040`: *a key is shown once and never again, only replaced; revoking it refuses the partner's very next call* | 040 · CLAUDE.md 🔒 | R2 | — | S |
| **R6** | 2d | **`cr069-r-issued-key.mjs`**: Alex → *Connect · Third-party GL* → *Issue key* → shown once with Copy → reopen → `••••7Q2F` only → S144 lists *issued by Alex Reed, 3 Sep, never used* → the partner fixture authenticates for Brazos Bend only → *Revoke* → its next call refused → *Enable* → *Waiting for a decision on who may allow this* · screenshots | 040 · `BR-INT-053` | R3 · R4 | — | S |
| **R7** | doc / version | CHANGELOG · lockstep · TSV · decision-log row | — | R6 | — | S |

**AS BUILT — 2026-09-06, `2.200.0`.** R1 ✅ (identity's companion story recorded as seam `I-9`; the DRF class stays identity's and **was not needed** — wave S's three partner routes opt out of the default authenticator and call `serve.resolve_caller()` directly, so no `US-IDN-` id was taken from that module's register) · R2 ✅ (`machine_auth.py`; `POST`/`DELETE /integrations/{key}/key`; the key stored as a blind index and NOTHING else) · R3 ✅ (`MachineKeysPage.tsx`, S144 at `INT-04`, with `IssuedKeyPanel` and the door on the connection card) · R4 ✅ (`tests/test_us_int_040_issued_key.py`, TC-1..7 — four of them through wave S's real partner route) · R5 ✅ · R6 ✅ (`10-scripts/render-checks/cr069-r-issued-key.mjs`) · R7 ✅.

⚠ **THE ONE THING THIS WAVE DID NOT BUILD, AND IT IS NOT A GAP:** `machine_auth` does **not** authenticate. The wave's first draft did — a full resolver with passing tests — and it was DELETED before it was pushed, because wave S's `serve.resolve_caller()` landed first, is live behind three real routes, and is better (no early returns, one `raise`, a timing floor that equalises the three refusals, the allowlist folded in). Two resolvers would be two answers to *may this machine read* drifting apart in silence. The two halves are joined by ONE string — `serve.ISSUED_KEY_BLIND_INDEX_CONTEXT`, imported by the mint, never retyped — and a test asserts the identity, because two spellings would refuse every valid key while looking exactly like a wrong key. Decision log 2026-09-06.

⚠ **TWO DEFECTS FOUND ON THE WAY IN, BOTH FILED:** `DEF-INT-4215` — **a `they_hold_ours` connector could not be connected at all**; `POST /integrations/gl_partner/connect` answered *Cannot be connected yet.* because `connect_with_fields` demands an adapter, and a partner who reads FROM us is the one relationship we never dial. Both such connectors were affected, and wave S had built a door for a connection the modal could not create. Fixed as data (`Manifest.we_never_dial`). `DEF-INT-4216` — wave S's `partner_api.py` and `serve.py` both argue from `test_us_int_041_partner_surface.py`, which is not in the repository; wave R wrote the three-refusal comparison its own report needed.

**Demo script R (Alex Reed):** 1 *Connect · Third-party GL* → 2 *Issue key* → the key, once, with Copy → 3 close
and reopen — `••••7Q2F` and nothing more → 4 S144: *issued by Alex Reed, 3 Sep, never used* → 5 the partner's test
call succeeds, for Brazos Bend only; *last used* moves → 6 *Revoke* → the partner's next call, one second later,
is refused → 7 *Enable the connection* → *Waiting for a decision on who may allow this*.
**Exit test:** `BR-INT-053` — shown once, scoped to one tenant, revocation effective on the next request;
`OQ-INT-1481` — the enable path raises.

---

### Wave S — the partner's morning · GL track · ⚠ **UNBLOCKED 2026-09-04 — `OQ-INT-1481` ruled (a)**

✅ **THE INTEGRATIONS HALF IS BUILT — `2.200.0`, 2026-09-06.** `S1`, `S2`, `S3`, `S4` and
`S5` are done; `S6` is this stamp. **What was built, in the CR's own words: machine
authentication, the allowlist refusal that reveals nothing, the rate limit, every page a run
with the key's hint as *who*, and the subprocessor register row pointing inward.**
**What was NOT built, and is Runbooks' rather than pending: what is in the payload** —
`tenderType` through `D2`'s mapping rows, the `projectType` constant, `accountString` from
the ledger codes. `runners/serve.partner_fields()` is the named seam, it returns `{}`, and
`test_tc5…` asserts a served record carries our four fields and none of those three — so the
day Runbooks fills it the suite goes red and names the row rather than the boundary closing
quietly. That is a **deliberate absence, not a stub** (`OQ-1396`'s distinction): nothing is
blocked and no question is open on it.

⚠ **`S5` IS DONE AND NOT BLOCKED — the table below still says `blocked` and it is wrong.**
`OQ-INT-1481` CLOSED 2026-09-04 option (a), so the enable path is a build: `POST
/integrations/{key}/grant` writes the audited grant to the connection and to `audit_log`,
gated on `SettingsReadAnyWriteSystemAdmin` — the ruling expressed as a permission class
rather than as an `if` somebody can delete — and the register row is DERIVED from that grant,
so the two cannot disagree. **Not (c):** no data-processing-agreement reference is required.

⚠ **THE DECLARED ADDRESS `GET /api/v1/payments` CANNOT BE BUILT, AND THE SURFACE IS
`/api/{utility}/v1/payments`.** Two signed rules meet: `BR-TEN-003` says the tenant is read
from the PATH and *"never"* from a header, a parameter or a body; CLAUDE.md hard rule 1 has
RLS on `FORCE`. `integration_credential` is a tenant table, so with no utility in the path no
context is set and the key lookup returns **zero rows for every key, a valid one included** —
the endpoint would be *incapable of passing* (law 7's third shape), and the only way to make
it pass would be to read the tenant from a header, which `BR-TEN-003` forbids by name. Put
the utility in the path and `TC-5` and `TC-7` stop being checks somebody has to remember and
become properties of the database. Decision log, 2026-09-06.

⚠ **AND WRITING THE TWO-TENANT CASES FOUND A REAL DEFECT IN THIS WAVE'S OWN CODE, IN FOUR
PLACES.** The door, the register and both read seams were scoped by RLS alone — correct on
PostgreSQL, and **nothing at all on the vendor the suite runs on**: `config/settings/test.py`
hardcodes SQLite, which has no RLS. Lone Star Ridge asked for its seven payments and got
**eleven** — its own seven and Brazos Bend's four. Written the other way round, a partner
reading another utility's money would have passed the entire suite. The tenant is now stated
twice, by the database and by an explicit `tenant_id=current_tenant_id()` filter, and each of
the four files carries the paragraph saying why. **⚠ It is worse than a test-vendor gap: this
machine's PostgreSQL role is a superuser, so `core.W001` reports RLS is not enforced there
either** — the belt-and-braces filter is the only scoping a walkthrough here actually has.

⚠ **`S2` USES THE KIT'S `ConsequenceBox`, NOT THE NEW `AmberBox` THE TABLE ASKS FOR.** The
kit does not lack that component: `components/ConsequenceBox.tsx` renders an amber
`role="note"` with an outlined tag, a bold lead and one sentence — frame 46.2's box element
for element — under the `check` tone. A second component for one visual decision is what
`G86` clause (c) is about. B14 rule 36 settles it: the shared kit is HOW you comply.
**And frame 46.2's two buttons (*Allowed addresses*, *Revoke the key*) are NOT drawn** — both
are S144's, which wave R is building, and a control pointing at a screen this wave did not
land is hard-won law 2's mirror. B14 rule 32: a stated absence is closed by default.

**Where wave R was not there yet:** nothing of R had landed when this was built, so the door
VERIFIES a credential rather than minting one — `services.record_credential` (wave E, built)
is the same call R's issue endpoint uses, and the blind index is computed from
`serve.ISSUED_KEY_BLIND_INDEX_CONTEXT`. **R must IMPORT that constant, never retype it:** two
different context strings refuse every valid key while the door still looks like it works.

⚠ **THE BROWSER FOUND SIX THINGS NO TEST, NO GATE AND NO TYPE CHECK COULD (hard-won law 6),
AND FIVE OF THEM WERE IN THIS WAVE'S OWN WORK.** `cr069-s-partner-morning.mjs` finishes
**GREEN — exit 0, 0 failures, 3 known gaps named** — and it got there through these:

1. **`GET /integrations/subprocessors` answered `405`.** Two segments, so `api.py`'s
   `integrations/<str:key>` matched first and read *subprocessors* as a provider key — while
   a comment this lane had written in `config/urls.py` asserted the collision could not
   happen. It is `integrations/register/subprocessors` now, and a test resolves all six
   routes through the real URLconf, because every other case here calls the view function
   directly and none of them could see it.
2. **The unusual read fell off the screen — failure 13 arriving through the fix for failure
   13.** The access log took the newest 100 rows; the walkthrough's own hundred requests
   pushed the 48,000-row collection past the cap. A partner wanting its big collection
   unnoticed need only make a hundred small ones. The list is the newest hundred **∪ every
   unusual read** now, and the payload carries `unusual_reads` as a COUNT.
3. **The screen called *Who has been reading* did not say WHO.** The hint reached it only
   inside `detail`, which nothing rendered. It is its own field now — validated as a mask
   before it leaves — drawn under the window text so frame 46.2 keeps three columns.
4. **The section was 5,800 pixels tall**, drawing every row the server sent. It shows twenty
   and states the remainder (*and 80 more reads*) — **newest twenty ∪ every unusual one**,
   because a plain slice re-introduces (2) one layer up.
5. **A single-day window printed *Payments, 2–2 Sep*,** and **a refusal we made ourselves was
   recorded `unconfirmed`** — which means *they would not say*, and there is no "they". It is
   `skipped`, the word `outcome_for` already reserves for *we did not ask*.
6. And in the walkthrough itself: `executablePath()` returns a chromium path that does not
   exist here, so the `try/catch` fallback **all sixteen sibling scripts share** can never
   fire (law 7's second shape). It is checked with `existsSync` in this one; the other
   fifteen still carry the unreachable version.

**Proved on the wire, not only in `pytest`:** five ways of being turned away, one refusal —
`404`, **42 bytes**, `application/json`, **~100ms each against a 40ms floor**. The **101st**
request in a minute is the first refused, `429`, `Retry-After: 60`. Three pages of the seeded
morning: **500 · 500 · 236 of 1,236**. The key's plaintext appears in **zero** run rows, zero
audit rows and zero server-log lines.

⚠ **THE TWO-TENANT PROPERTY IS THE SUITE'S, NOT THE WALKTHROUGH'S, AND THE SCRIPT PRINTS
THAT.** `seed_demo` provisions Brazos Bend and nothing else, so a second utility's key cannot
be presented on a proof clone at all; `test_tc4b`, `test_tc7` and `test_tc8d` build both.
A check that cannot cover its subject must say what it skipped beside what it checked.

÷ **SPLITS — 2026-09-06 (`CR-069` §20.4).**
**KEEPS:** machine authentication, the allowlist refusal that reveals nothing, the rate
limit, **every page is a run with the key's hint as *who***, and the subprocessor register
row pointing inward — that is the access log of a connection, item (3), and it is exactly
what a manager reads.
**MOVES:** **what is in the payload** — `tenderType` through the mapping rows,
`projectType`, `accountString` from the ledger codes. Building a business record for someone
else is outbound ETL.
⚠ **SCOPE OBSERVATION (`DEF-INT-4118`): `runners/serve.py`, built here for a finance partner
reading payments and bills, is the SAME DOOR InvoiceCloud needs** to call our invoice and
account APIs. The inbound half of a bidirectional partner is this wave's shape, not a new
one. **Not blocked** — `OQ-INT-1481` closed, `OQ-INT-1480` HELD (out of scope permanently).


÷ **SPLITS — 2026-09-06 (`CR-069` §20.4).**
**KEEPS:** machine authentication, the allowlist refusal that reveals nothing, the rate
limit, **every page is a run with the key's hint as *who***, and the subprocessor register
row pointing inward — that is the access log of a connection, item (3), and it is exactly
what a manager reads.
**MOVES:** **what is in the payload** — `tenderType` through the mapping rows,
`projectType`, `accountString` from the ledger codes. Building a business record for someone
else is outbound ETL.
⚠ **SCOPE OBSERVATION (`DEF-INT-4118`): `runners/serve.py`, built here for a finance partner
reading payments and bills, is the SAME DOOR InvoiceCloud needs** to call our invoice and
account APIs. The inbound half of a bidirectional partner is this wave's shape, not a new
one. **Not blocked** — `OQ-INT-1481` closed, `OQ-INT-1480` HELD (out of scope permanently).

**Goal (boundary):** a finance system collects yesterday's payments over three pages at 02:41 and a manager reads
three rows under *Who has been reading*; a read from an address not on the list is refused and learns nothing;
the 101st request in a minute waits. Served only to the test partner until the PO rules who may allow it.
**Stories:** US-INT-041 ⚠ — **S1 · S2 · S3 · S4 · S5 DONE at `2.199.0`; `S6` is the stamp above.**
**Depends on:** R (machine auth) · D (mapping rows, codecs) · C (runs). **Blocked by:** nothing —
`OQ-INT-1481` was ruled on 2026-09-04 (System Admin, audited grant), so *"Served only to the test partner until the
PO rules who may allow it"* in the goal above no longer applies. ⚠ **`OQ-INT-1480` was HELD the same day** —
*"we will use our GL code only"* — so `accountString` beyond the flat code is **out of scope permanently**, not
pending: a partner needing `001.100.51200` is not served, and that is the ruling.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **S1** | 2a | `runners/serve.py` (the SERVE quadrant, built with nothing behind it in B2, filled here): `GET /api/v1/payments` · `GET /api/v1/billing` · `GET /api/v1/openapi.json`, machine-authenticated (R2), filtered by type · tender · date range, **paginated in the partner's declared envelope** `partner_paged = {total_records, page, page_size, total_pages}` (never the DRF shape); each record `id · paymentDate · amount` (4-decimal money, displayed 2) · `tenderType` **through D2's mapping rows** · `projectType` the constant *Utility Billing* · `accountString` from the rows, else `ledger_accounts.code` (the segmentation is `OQ-INT-1480`); **every page is a run** — `direction = inbound_read`, `trigger = partner`, `attempted = records handed over`, the key hint as *who*; the allowlist refusal **reveals nothing** (identical body for a real and an unknown account); a per-partner rate limit (100/min → `429` + `Retry-After`, recorded); an unknown account answered in the declared way; the subprocessor register gains the relationship **pointing inward, derived from the live connection** (`C33`). The debits and credits handed over already balance (hard rule 5 — reads only). Served to the test partner; a real partner needs R2's enable, which raises | 041 · `BR-INT-035` · `044` · `032` · `033` · hard rule 5 | R2 · D2 · C1 · D1 | `C5` `C33` · `T-5` group (Aclarian, 6) · `T-B2` | L |
| **S2** | 2b | S142 *Who has been reading* — the `AccessLog` table with the unusual-row emphasis and an `AmberBox` beneath (the fourth component the staff kit lacks; frames `46.2` / `80.2`; CR-045's toolbar); the register view's inward row *Aclarian — reads payments and bills — authorised by … on …* | 041 · B14 rules 15 · 20 · 31 | S1 · C3 | `C33` | M |
| **S3** | 2c | `US-INT-041` TC-1..9 (TC-9 the boundary). *The partner's morning*: 2026-09-02's 1,236 payments over three pages of 500; *the unusual read*: 2024-09-01 → 2026-09-01, 48,000 records, 105 runs at 02:41; the allowlist; 100/min | 041 | S1 · S2 | — | M |
| **S4** | 2d | **`cr069-s-partner-morning.mjs`** (`J54` against the test partner): the fixture collects three pages at 02:41 → S142 shows `02:41 · Aclarian · payments · 500 records · page 1 of 3 · ••••7Q2F` (⚠ read *412* — 1,236 ÷ 3 — until 2026-09-03; the envelope is 500 · 500 · 236 — `DEF-INT-3614`) and two more → a read from `203.0.113.99` refused with a body identical to an unknown account's → the 101st request in a minute → `429` → the register shows the inward row → *Enable* → the boundary sentence · screenshots. **Journey `J54` written** | 041 · `BR-INT-035` · `044` | S2 · S3 | — | S |
| **S5** | blocked | **After `OQ-INT-1481`:** the enable path and the audited authorisation as ruled — an admin grant plus a register row (a), the owner role only (b), or a DPA reference first (c) | 041 · 040 | S1 · R2 · the ruling | `T-B2` | — |
| **S6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · **the GL track closes when R and S are done** (two stories, both to the boundary) | — | S4 | — | S |

**Demo script S (a finance system, then Alex):** 1 the partner collects yesterday's payments — three pages at
02:41 → 2 S142's *Who has been reading*: three rows, each with when, who, what, how many, and the key's hint →
3 the counts match what we hold → 4 a read from an address not on the list — refused, and the refusal reads the
same for a real account and a made-up one → 5 the 101st request in a minute — *429*, *Retry-After* → 6 the
subprocessor register: *Aclarian — reads payments and bills*, pointing inward, derived and not typed → 7 *Enable*
→ *Waiting for a decision on who may allow this*.
**Exit test:** `BR-INT-035` — every partner read is a row a manager can read; `BR-INT-044` — the refusal reveals
nothing; `OQ-INT-1481` — no real partner is served.

## 4 · Critical path, and what runs in parallel on day one

**To the phase-1 launch (the grid, and the refusal by the API):** `A1 → A3 → A5 → A6 → A9` for the grid, with
`A4 → B1 → B3 → B4 → B8` for the modal and the refusal. **A then B, in series: about four weeks with two people.**
The phase-1 launch sentence is true at **B8**; the phase closes when **C** and **D** land, and those two run in
parallel (about a week and a half more).

**To the phase-5 launch (a kiosk payment on the account by itself):** `A → B → C → E → N`. E needs B's modal and
endpoints and C's run rows; N needs E's credential table (the kiosk key is a stored credential), D's tender
mappings and N1's payments columns. **About nine and a half weeks along the spine**, with D and N1 off the spine.
Waves O, P and Q follow N and are blocked to their boundaries; the GL track (R, S) hangs off E and runs beside
phases 3–5.

**Everything else is off the spine and can be parallel:** G (scheduling) starts the day phase 1 closes, beside E
and F; H needs E and G; I, J, K and M all start once phase 1 closes and E has landed (I and J need no credential
and can start after D); L needs K.

**Day one, three lanes can start at once:**

1. **Lane 1 — A1 → A3 → A5** (the brief, the five tables on PostgreSQL, the read API).
2. **Lane 2 — A4 and A8** (the registry with seventeen manifests; the three gates proven RED), then **A2**
   (the migrated list, the `human_owned` globs, the `tests/pg` CI step).
3. **Lane 3 — D1 and N1** (the codec registry lifted from `print_formats.py`; payments' `channel` and
   `external_ref` migration) — neither depends on the tables.

**The three things that gate a later wave and can be done early:** `E1` (the `core/crypto.py` sign-off — a
conversation with the PO in plain English with a figure, before any real credential is stored); `R1` (identity's
companion story); and the reading of the card processor's documentation (`OQ-INT-1476`, the one question
`CR-069` says to read first — it decides the shape of the whole charge operation and nothing in `T-9` starts
before it).

**Where this sits against `12-governance/19-execution-sequence.md` — proposed, not decided here** (that file says
*"if the order changes, say who changed it and why, in the log"*): the go-live path's step **9 · Deliver it** is
what phases 2 and 3 serve (a utility's own mail server, then Google or Microsoft), step **10 · Take payment** is
phase 4's bank import and phase 5's kiosk door, and step **11 · Books tie out** is wave J's remembered export
target. **Phase 1 is a prerequisite with no step of its own** — it makes the Settings tab honest and gives every
later connector its rails — so the proposal is: phase 1 immediately, as the substrate under steps 9–11; phases 2–3
beside the email-activation work (W6) they unblock; phase 4 before the next utility's first month-end; phase 5
when the kiosk network's onboarding date is set. The GL track waits on its ruling and costs nothing in the queue
until then. This is an argument for the log, not a change to the sequence file.

## 5 · Blocked — and what each still demonstrates

⚠ **THIS TABLE IS STALE AND IS CORRECTED HERE RATHER THAN REWRITTEN, 2026-09-06.** It was
written on 2026-09-03. **Reading each question's STATUS COLUMN rather than its body — which
is the check, because a closed question's body usually still describes the open world —
sixteen of the nineteen `OQ-INT-` questions are now CLOSED**, most of them on 2026-09-04,
and each affected wave's own heading below already says so while this summary did not.

**What is actually still blocked: wave `O`, and nothing else.**

| Wave | The table below says | The register's status column says |
|---|---|---|
| **`O`** | blocked on `OQ-INT-1476` · `1478` | ⚠ **STILL BLOCKED.** `1476` **ROUTED** to the card processor and unread; `1478` **OPEN — answered in part**. Neither is ours to answer — both are facts the processor holds. |
| `J` | blocked on `OQ-INT-1487` · `1483` | **NOT BLOCKED** — both **CLOSED 2026-09-04** ((b) `R02` records as `other` with the raw code kept; (a) *self-declared* only). |
| `L` | blocked on `OQ-INT-1485` | **NOT BLOCKED** — **CLOSED**, option (a): we are master of the meter-to-account link. |
| `M` | blocked on `OQ-INT-1471` | **NOT BLOCKED** — **CLOSED**, *"(b) type it, marked unchecked"*. |
| `Q` | blocked on `OQ-INT-1470` · `1471` · `1472` | **NOT BLOCKED** — all three **CLOSED 2026-09-04**. |
| `R` | blocked on `OQ-INT-1481` | **NOT BLOCKED** — **CLOSED**, option (a). |
| `S` | blocked on `OQ-INT-1481` · `1480` | **NOT BLOCKED** — `1481` **CLOSED**; `1480` **CLOSED — held** (out of scope permanently). |
| `B` · `E` · `D` | bounded by `OQ-INT-1479` · `1488` · `1480` | all three **CLOSED**. |
| `P` | `OQ-INT-1482` | **CLOSED — out of scope**; the wave is cancelled. |

⚠ **THE LESSON IS HARD-WON LAW 12's, ONE VOCABULARY ALONG: a summary table and the thing it
summarises are two places, and only one of them was kept up to date.** Every wave heading
below was corrected as its question closed; this list was not, because closing a question and
updating the summary of closed questions are two acts and only the first feels like the work.
**Read the status column, never the body — and never this table without checking it.**

⚠ **Of the three questions minted on 2026-09-06 — `OQ-INT-1727`, `1728`, `1729` — TWO WERE
RULED THE SAME DAY AND ONLY `OQ-INT-1727` IS STILL OPEN.** None is in the table below, which
predates them. **`OQ-INT-1728` (wave `M`) — option (a):** a person's synchronous write on a
screen stays with the module that owns the screen, so nothing of `M` moves; and the same job
must ALSO exist as a batch, scheduled and run-once. **`OQ-INT-1729` (wave `F`) — option
(a):** the lane stops at the door; the record-marking waits for Runbooks. **`OQ-INT-1727`
(waves `C`/`D`, about three people-weeks already shipped, screen S143 live) is OPEN and is
not a lane's to answer.** See §0a, the waves themselves, `CR-069` §20.5 and the decision
log, 2026-09-06.

**The 2026-09-03 table is kept below as the record of what was true then — with ONE dated correction, and the reason it was made rather than left standing:**

⚠ **A HISTORICAL TABLE IS STILL READ AS INSTRUCTIONS, AND THIS ONE WAS, TWICE.** The line above says the table is a record; the ROWS say `US-INT-038` waits on `OQ-INT-1487`. A reader who lands on a row does not first walk back twenty-five lines to find out that the whole table is historical — and on 2026-09-06 a lane counting occurrences of the word *blocked* in this file reported wave `J` to the Product Owner as BLOCKED on exactly this row, while the correction table above it said **NOT BLOCKED** and the wave was being built. That is `CLAUDE.md`'s own rule one register along: **the status decides, and a body that contradicts it is stale until proved otherwise.**

**So the wave `J` row is struck through IN PLACE, with its rulings written into it.** The rest of the table is untouched — every other row's question was closed too, and each is already corrected in the table above and in the wave's own heading. This one is corrected here as well because it is the one that misled somebody.



The story index says **eleven blocked (nine wholly, two on one branch)**. Read against the frontmatter, **seven
stories carry `status: blocked`** and **four are `ready` with one half stubbed and named**; the eleven are these,
and every one ends its wave with a demonstration of the boundary — the stub, the sentence on the screen, the test
that asserts the raise.

| Story | Wave | Waits on | What is demonstrated anyway |
|---|---|---|---|
| `US-INT-036` the register sync | L | `OQ-INT-1485` (which system is master of the meter-to-account link) | the differences on S142 — *size 5/8" for MTR-2210, we hold none* — and `assets` unchanged; `J57` ends one step early |
| `US-INT-040` a key we issue | R | `OQ-INT-1481` (who may authorise a partner) | issue · shown once · revoke refuses the next call; *Enable* → *Waiting for a decision on who may allow this* |
| `US-INT-041` the partner surface | S | `OQ-INT-1481`; `OQ-INT-1480` bounds `accountString` | three `inbound_read` runs at 02:41 against the test partner; the allowlist refusal; the inward register row |
| `US-INT-042` the address search | M | **nothing** — `OQ-INT-1471` CLOSED 2026-09-04 (b) | candidates under a second, a pick that writes, the breaker's sentence; Create while offline → **the premises, marked unchecked** |
| `US-INT-043` the GIS night | Q | `OQ-INT-1470` · `1471` · `1472` | the report with seven classes and *not ours* as its own count; the tax-column refusal naming the column; every write raises |
| `US-INT-045` indeterminate | O | `OQ-INT-1476` (unread) · `OQ-INT-1478`; `1473` `1474` `1475` `1477` bound `T-9.05/06/08` | *we do not know*, *Ask the processor*, the refused Retry, the key stored before the call — on fixtures; the live charge raises |
| `US-INT-046` consent | P | `OQ-INT-1482` (in scope at all?) | nothing mounted; the test that asserts every writer raises; the table already in the brief |
| `US-INT-019` the modal (ready) | B | `OQ-INT-1479` bounds the Test button's permission | the modal ships Admin-only; a clerk sees no Test button |
| `US-INT-026` the fold (ready) | E | `OQ-INT-1488` bounds the bulk-connector threshold copy | the fold ships; the card says nothing about a threshold until ruled |
| `US-INT-037` their words (ready) | D | `OQ-INT-1480` bounds retiring `qbo_ref` / `xero_ref` | the table beside the two columns; no third column ever |
| ~~`US-INT-038` unknown values (ready)~~ ⚠ **NOT WAITING ON ANYTHING — CORRECTED 2026-09-06 IN THE COMMIT THAT BUILT WAVE `J`** | J | ~~`OQ-INT-1487` bounds `R02`; `OQ-INT-1483` bounds the standards wording~~ — **BOTH CLOSED 2026-09-04** | **`OQ-INT-1487` → option (b):** `R02` records as `other`, the raw code is kept on the payload, and the four signed reversal reasons are **not widened to five**. The writer still refuses to map `R02`, and the refusal now names that CLOSURE rather than a `NotImplementedError` awaiting an answer. **`OQ-INT-1483` → option (a):** *self-declared* only — never *certified*, never *compatible with*. MultiSpeak and Green Button are still not claimed. |

**Not ours to reverse, and not reversed here:** `OQ-INT-1473` — the derived-fee ruling of 2026-08-12 whose premise
moved when the PO said the processor sends a nightly settlement file — goes back to the PO with its figure
($5,120.40 taken · $4,972.90 credited · a $147.50 gap that $137.50 + $10.00 also produces).

## 6 · Closing table — every story, its wave, its phase

| Story | Wave | Phase | Story | Wave | Phase |
|---|---|---|---|---|---|
| US-INT-013 registry | A | 1 | US-INT-030 request budget | G | 3 |
| US-INT-014 five tables | A | 1 | US-INT-031 submit–poll–collect | K | 4 |
| US-INT-015 adapter protocol | B | 1 | US-INT-032 savepoints (PG) | I | 4 |
| US-INT-016 queue + worker | B | 1 | US-INT-033 files in / out (file-out TCs land in J) | I | 4 |
| US-INT-017 server-side gating | B | 1 | US-INT-034 reconcile mode 🔒 | L | 4 |
| US-INT-018 operations are the unit | A | 1 | US-INT-035 safety parameters 🔒 | K | 4 |
| US-INT-019 the modal S141 | B | 1 | US-INT-036 register sync ⚠ | L | 4 |
| US-INT-020 run record S142 | C | 1 | US-INT-037 their words S143 | D | 1 |
| US-INT-021 unconfirmed | C | 1 | US-INT-038 unknown values · Nacha · camt.053 | J | 4 |
| US-INT-022 cap · timeout · breaker | F | 2 | US-INT-039 codecs | D | 1 |
| US-INT-023 email feedback | F | 2 | US-INT-040 machine credentials ⚠ | R | GL |
| US-INT-024 credential versions | E | 2 | US-INT-041 partner surface ⚠ | S | GL |
| US-INT-025 offboarding | E | 2 | US-INT-042 executor · address search ⚠ | M | 4 |
| US-INT-026 the fold | E | 2 | US-INT-043 GIS night 🔒 ⚠ | Q | 5 |
| US-INT-027 expiry sweep | H | 3 | US-INT-044 the kiosk door | N | 5 |
| US-INT-028 token exchange · fetch plan | K | 4 | US-INT-045 indeterminate 🔒 ⚠ | O | 5 |
| US-INT-029 the beat schedule | G | 3 | US-INT-046 consent ⚠ | P | 5 |

**Part 1 placed:** US-INT-001 → A · US-INT-002 → B · US-INT-004 → B · US-INT-003 → E · US-INT-005 → H ·
US-INT-008 → I · US-INT-010 → I · US-INT-009 → J. **Part 1 deferred (four):** US-INT-006 (W5), US-INT-007 (W5/W6),
US-INT-011 (W7), US-INT-012 (W8).

**Counts:** 6 tracks (5 phases + GL) · 19 waves · 122 tasks (4 of them blocked until a ruling — `O6`, `P3`, `Q6`,
`S5`; every other task in a blocked wave builds and demonstrates the boundary) · 34 substrate stories placed once
each · 8 Part-1 stories placed, 4 deferred · 19 walkthrough scripts · 12 journeys written (`J48`–`J59`; `J58`
waits on `OQ-INT-1482`) and 3 legs (`J14`, `J17`, `J19`).

## 7 · The coverage check, as run over this file

Run 2026-09-03 with a twenty-line script that reads this file's `### Wave` headings, their `**Stories:**` lines and
their task rows (the script is in the lane's scratchpad; anyone can re-derive it from the two regexes named here:
`^### Wave ([A-Z]) —` and `^\| \*\*([A-S])(\d+)\*\* \|`):

```
waves: 19 (ABCDEFGHIJKLMNOPQRS)
tasks: 122  per wave: A=10 B=9 C=6 D=6 E=9 F=6 G=6 H=6 I=5 J=5 K=6 L=6 M=5 N=7 O=7 P=3 Q=7 R=7 S=6
tasks blocked until a ruling: 4 (O6, P3, Q6, S5)
substrate stories US-INT-013..046 placed exactly once: YES (34/34)
Part-1 placed: 001->A, 002->B, 003->E, 004->B, 005->H, 008->I, 009->J, 010->I
Part-1 deferred (not placed): 006, 007, 011, 012
every wave names its 2d walkthrough script: YES
TSV rows written: 122 -> cr069/wave-tasks.tsv
RESULT: PASS
```

---

## 8 · AFTER THE BOUNDARY — what integrations still owns, and what Runbooks picks up (2026-09-06)

**This section is the plan's own bottom line.** §0a states the ruling; this states what is
left of the plan under it. **Nothing here commissions work** — `CR-069` and Runbooks are
taken together after CR-070 completes.

### 8.1 · The remaining backlog, split

| | People-weeks | Made of |
|---|---|---|
| **Built already** (`A`–`E`) | **15** | `A` 4 · `B` 4 · `C` 1.5 · `D` 1.5 · `E` 4 |
| **Still pending** (`F`–`S`, `P` cancelled) | **≈ 40** | 39.5 low / 43.5 high — the spread is `H` and `R`, which this plan sizes as *"one or two people"* |
| **— integrations retains** | **≈ 20** | `H` and `R` whole (≈ 6), plus its share of the ten splits (≈ 14): the doors, the credentials, the duplicate-recognition halves, the access log |
| **— Runbooks inherits** | **≈ 21** | `G`, `L`, `Q` whole (**10**), plus its share of the splits (≈ 11) |
| **— plus, on top** | not sized | `DEF-INT-4118`, repair to **built** wave `E`; the fixing lane chooses the shape first |

⚠ **The whole-wave figures are this plan's own sizes. The share of each SPLIT wave is a
judgment, and is marked as one every time it appears.**

⚠ **THE ~40 IS NOT THE FIGURE USUALLY QUOTED, AND THE DIFFERENCE MATTERS.** §4 says *"About
nine and a half weeks along the spine"* — the **calendar** length of the critical path
`A → B → C → E → N` with two people, which deliberately excludes everything running in
parallel beside it. **Ten calendar weeks and forty people-weeks are both true of this plan
and answer different questions.** Quoting the first as the size of the backlog understates
the work roughly fourfold.

**The planning fact, said plainly: `CR-069` stops being one project of about forty
people-weeks and becomes two of about twenty.** Runbooks does not end up carrying *most* of
it — it carries **as much as integrations does**, and it carries that with **no module
folder, no stories, no epics and no home in this repository.**

### 8.2 · What Runbooks inherits — a LIST, not a plan, and its home is undecided

⚠ **Runbooks has no module folder here and this document does not invent one.** This is what
the Runbooks work picks up when it starts, and nothing more:

1. **The scheduler, whole** — the beat schedule, the due sweep, tenant-midnight and DST, the three-hundred-utility spread, the skip row, the catch-up policy (wave `G`).
2. **The reconcile of late readings** — natural key, supersede, the billed-reading refusal and its correction, plus its 🔒 review obligation (wave `L`).
3. **The GIS night** — seven classes, per-field authority, the decision queue, its 🔒 review obligation, and the match-key design job `OQ-INT-1470` handed us (wave `Q`).
4. **The value mappings** — their words to ours, and the Nacha return codes with them (waves `D`, `J`) — **subject to `OQ-INT-1727`, because this is built and live.**
5. **The matching and writing of imported payments** — which payment belongs to which account (waves `I`, `N`).
6. **The record of what was decided** — per-item run results and the audit of a transformation (wave `C`) — **also `OQ-INT-1727`.**
7. **The readings projection, and the outbound business payload** (waves `K`, `S`).
8. **The record updates that follow a landing** — notification rows marked delivered or bounced and the suppression list (wave `F`). ⚠ **CORRECTED 2026-09-06: the premises written from a picked address is NO LONGER ON THIS LIST.** `OQ-INT-1728` was ruled option (a) — a person's synchronous write on a screen stays with the module that owns the screen — so wave `M`'s Create **stays with integrations**. What Runbooks inherits from `M` instead is the **batch forms of that same job**: the **scheduled** run, and the **running** half of the run-once button whose trigger stays on the screen. `OQ-INT-1729` was ruled option (a), which leaves the `F` half exactly as written and confirms it is **not built now**.

### 8.3 · The three questions, and one of them has a clock on it

| | Why it cannot be answered by a lane |
|---|---|
| **`OQ-INT-1727`** | Waves `C` and `D` shipped work now on the Runbooks side — **≈ 3 people-weeks and one live clerk-facing screen (S143)**. A ruling colliding with shipped work is the PO's; the supersession must be **stated, never assumed** (law 13). |
| **`OQ-INT-1728`** ✔ **RULED 2026-09-06** | **ANSWERED — option (a): only unattended runs.** A person's synchronous write on a screen stays with the module that owns the screen, so wave `M`'s Create stays here. ⚠ **The PO added that the same job must ALSO exist as a batch, scheduled and run-once**; the scheduled form and the running half of the run-once form are Runbooks'. |
| **`OQ-INT-1729`** ✔ **RULED 2026-09-06** | **ANSWERED — option (a): the lane stops at the door.** The feedback door stays with integrations and is finished there; the record-marking and the suppression list wait for Runbooks. ⚠ **The collision was with a plan, not with code** — that half had never been started, which is why the answer cost nothing. |

### 8.4 · What a lane picking up a wave does TOMORROW

**It builds the wave as written below.** The sequencing is unchanged — PO, 2026-09-05:
*"right now notng to be done … we will handle CR 69 and Runbook together once CR70 is
completed."* What §0a and this section change is **who owns each piece and how the backlog
is sized**, not what anybody does next. **The one thing a lane must NOT do is answer
`OQ-INT-1727` by choosing** — it is stubbed to its boundary, as the prime directive
requires. ⚠ **`OQ-INT-1728` and `OQ-INT-1729` were RULED on 2026-09-06 and are no longer
stubs**: wave `M`'s write is a build and stays here, and wave `F` builds its door and stops
there. Read the waves themselves, not this paragraph, for what each one now includes.

## 9 · THE FOUR DIRECTIONS AND SEPARATE COMPUTE — 2026-09-06

**PO working session, 2026-09-06. The model whole is
[`11-the-runbooks-boundary.md`](11-the-runbooks-boundary.md); the rules are `BR-INT-055`–`065`;
the batch and its states are [`04-flows.md`](04-flows.md) Part 3; the wave-by-wave direction is
`CR-069` §20.9.2, which is its SOURCE — §9.1 below reproduces only the assignment.**

⏸ **THIS COMMISSIONS NOTHING.** `BR-INT-054` still says *"NOTHING IS TO BE BUILT AGAINST THIS
RULE YET"* and the 2026-09-06 model did not change that sequencing. **It is here because it
changes how waves are SIZED, and a size has to be known before it is spent.**

### 9.1 · Which direction each wave is

A wave's direction decides its **shape** — and a lane that knows only its §20.4 verdict does not
yet know whether it is building a batch, a door or a read.

| Direction | Waves | The shape |
|---|---|---|
| ***We pull*** | `H` `I` `K` `L` `M` `Q` (+ `O`'s follow-up leg) | **The batch** — schedule or one-off · chunk size · walk records · nine states · two failure buckets |
| ***We push*** | `J` `O` (+ `F`'s send half) | **The batch, mirrored** — same states, same failure handling, records travelling the other way |
| ***They push*** | `N`, `F2`'s feedback door | **The door** — authenticate → dedupe → reply fast → persist raw, **and it stops there** |
| ***They pull*** | `R` `S` | **A read** — their key, where they may call from, how often, on/off, who read what and when. ⚠ **NO BATCH, NO SCHEDULE** |
| **Substrate — all four** | `A` `B` `C` `E` (`D` inbound-facing; `G` serves only the two we start) | The registry, the tables, the queue, the run row, the keys |
| **Cancelled** | `P` | `OQ-INT-1482` ruled (c); the letter is **not** reused |

⚠ **THE THIRD TRIGGER, because it is the one a lane will miss: when THEY start it there is no
schedule.** The trigger is **their call** (`BR-INT-057`). *They push* and *they pull* have **no
cadence, no due time, no next run and no catch-up policy** — **nobody builds a scheduler for a
doorbell** — and **every word of `BR-INT-024` applies to `H` `I` `J` `K` `L` `M` `O` `Q` and to
no other wave.**

⚠ **AND `F` AND `O` EACH CARRY TWO DIRECTIONS.** `BR-INT-028` puts direction on the **operation**,
so **classify an operation, never a provider** — the email provider is *we push* for the messages
we hand it and *they push* for the bounce it reports back.

⚠ **`L` AND `Q` ARE *we pull* WAVES MARKED `→ Runbooks` WHOLE, AND THAT IS CORRECT** — their
integrations half is another wave's connection (`L` depends on `K`; `Q` uses `M`'s `gis_city`).
**It would be wrong for a *we pull* wave that owned its own connection**, so do not read them as
a precedent for one.

### 9.2 · Separate compute per utility — `BR-INT-061`

**The PO's words: this will be heavy for each utility, and they must be able to set up separate
compute.** Six requirements:

1. **Work is queued PER UTILITY**, not on one global queue — **one utility's heavy night must not
   be everyone's.**
2. **The runner is its own deployable**, separate from the web application.
3. **A setting says which pool a utility's runbooks use.** **The default is a SHARED pool.**
4. **Moving a utility to its own compute is a SETTING CHANGE** — no migration, no code change, no
   downtime.
5. ⚠ **EVERY POOL STILL ENFORCES TENANT ISOLATION.** `app.tenant_id` is set and RLS `FORCE` is on
   in a dedicated pool exactly as in the shared one. **Separate compute is CAPACITY. A pool
   boundary is NOT a security boundary and must never be described as one** (hard rule 1).
6. **A utility on its own compute fails alone** — its runner dying stops no one else's batches.

**This EXTENDS `BR-INT-041`, which this plan already builds in wave `B`.** `BR-INT-041` separates
work **by kind** — integrations on its own named queue with its own consuming worker, off the
billing workers. Requirements 1–4 add a **per-tenant** axis on top of that: under `BR-INT-041`
alone, three hundred utilities share one integrations queue, and requirement 1 says that is not
enough. ⚠ **The pool stays with INTEGRATIONS** — `BR-INT-054`: *"the QUEUE and the WORKER are not
the scheduler and stay here … Runbooks runs on them."* **Runbooks decides *when* and *what*; the
pool is *where it runs*, and that is item (c).**

### 9.3 · What it does to sizing — the reason this is in the plan and not only in the model

⚠ **REQUIREMENT 2 CANNOT BE ADDED AT THE END.** A runner that starts as a thread inside the web
application and is later pulled out is **a re-architecture, not a setting**. Three consequences
for how waves are sized:

1. **Wave `B` is the last cheap moment for the deployable boundary.** `B` is where the queue and
   its consuming worker land (`BR-INT-041`, `DEF-320`). Whatever `B` builds is what every later
   wave's work runs on, so **a `B` that assumes one process is a `B` that has to be re-opened.**
   `B`'s current size does **not** carry requirement 2 and **is not re-sized here** — this is the
   note that the cost exists and is currently unallocated.
2. **Requirements 1, 3 and 4 are a settings-and-routing change, and they are cheap in the right
   order and expensive in the wrong one.** A queue name derived from the tenant, plus a per-tenant
   pool setting with a shared default, is small **while there is one place that enqueues**. It
   grows with every additional enqueue site a later wave adds.
3. **Requirement 5 is a test obligation, not a build one, and it grows with the pools.** The
   isolation proof (`10-scripts/prove_isolation.py`, `rls_role_record.py`) currently answers *does
   a tenant's data leak inside one process*. With a second pool the same question has to be asked
   **of the dedicated pool as well** — ⚠ and hard-won law 7 applies with force here: **a check
   that runs against only the shared pool and reports zero is reporting zero over a scope it
   silently excludes**, which is indistinguishable from a clean result. **It must print which
   pools it checked.**

⚠ **NOT SIZED HERE, AND SAID RATHER THAN IMPLIED.** No wave in §3 is re-sized by this section and
no new wave is added. **`BR-INT-054` commissions nothing**, so putting a number on separate
compute today would be sizing work nobody may start. **What §9.3 records is that the number is
NOT ZERO and NOT YET TAKEN** — so that whoever commissions Runbooks sizes it deliberately instead
of discovering it inside wave `B`.

### 9.4 · What a lane picking up a wave does with this — added to §8.4

1. **Read your wave's DIRECTION in §9.1 before its task table**, and build the shape it names:
   a **batch** (`04-flows.md` §3.2–§3.3), a **door** (§3.4) or a **read** (§3.5).
2. ***They push* or *they pull*: do not build a schedule, a cadence or a next-run field.** There
   is nothing to put in one.
3. ***They push*: stop at the door.** Authenticate, dedupe, reply, persist raw. **The `apply` half
   is Runbooks'** — because the vendor is waiting on our reply and will re-send if we are slow, so
   answering the door must never wait on processing.
4. ***They pull*: if your wave composes a payload, that projection is Runbooks'** — which is the
   entire difference between `R` (whole) and `S` (split).
5. **Do not build against `BR-INT-061`.** It is recorded so it is not lost and so wave `B` knows
   the cost exists; **it is not commissioned.**
