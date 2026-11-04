# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 P4 — stages 1–3 of the recorded ETL runner.
#           SUPERSEDES US-MET-004 §5's "no persistence in v1" two-step preview;
#           design B15 §7A)
#           Screens: WFL-01.premises.1–3 (Extract · Transform · Validate), PRM-04
# Rules:    BR-MET-085 (a premises import loads premises and NOTHING else —
#           ⛔ NARROWED 2026-09-01 by BR-MET-1030: an owner with a NAME and
#           ONE IDENTIFIER now gets a master account and a Customer #; no
#           unit is ever auto-created, which is the clause that rule is
#           actually about) · BR-MET-1030 (the owner's identity columns and
#           the conditional owner account) ·
#           BR-MET-088 (the transform stage offers the REAL target columns) ·
#           BR-MET-090 (a rule is a declared row; a run stores the rules as
#           they were) · BR-MET-091 (a rule we cannot evaluate is declared
#           unavailable, never omitted) · BR-MET-003 (services ⊆ tenant-enabled)
#           · BR-MET-034 (premises types are a lookup) · BR-MET-038 (10 MB ·
#           10,000-row cap) · BR-MET-048 (every change writes who/when) ·
#           BR-MET-035 (roles, server-enforced) · BR-RAT-101 (inside_city_limits
#           is THREE-STATE and `None` is not a default) · CLAUDE.md hard rule 1
#           · BR-CUS-051 (import mechanics = the standard: staged → per-row
#           errors → skip-errors ON → "N created · N failed" summary) ·
#           BR-CUS-017 / BR-CUS-022 (the two writer refusals stage 4 now
#           catches per row instead of losing the file to) · BR-AST-033 /
#           BR-AST-049 / BR-AST-011 / BR-AST-003 (the assets writer's own
#           refusals, now caught per row) · BR-MET-100 (a unit may load with
#           no plan — the blank cell on the successes file)
# Change:   CR-047 — a SAVEPOINT per record in `_load_accounts_rows`, a reason
#           and a fix sentence on every refused row, and the two result CSVs
#           (`results_csv`). DEF-2519, critical
#           CR-047 WIDENING (2026-08-29) — the SAME per-record savepoint on the
#           other five targets: business refusals on the three assets targets
#           (task 20) and DATABASE refusals on the generic premises/units path
#           (task 21, where the savepoint is MANDATORY — a failed statement
#           poisons a PostgreSQL transaction), a per-target column map for the
#           successes CSV (task 22), and `metering.import.not_loaded_no_download`
#           so the download refusal stops borrowing the rollback door's words.
# Tests:    06-backend/tests/test_cr023_import_stages.py ·
#           06-backend/tests/test_cr047_per_record_load.py (CR-047) ·
#           06-backend/tests/test_cr047_widening.py (CR-047 widening)
# Impacts:  apps/metering/import_rules.py (stage 3's rule set) ·
#           apps/metering/api.py (endpoints 1–4 of B15 §12) · PRM-04 · the
#           stateless POST /premises/imports pair this REPLACES but does not
#           yet delete (design B15 §7A — AddPremisesWizard still calls it)
# ───────────────────────────────────────────────────────
"""Stages 1–3 of the CR-023 import runner — **EXTRACT · TRANSFORM · VALIDATE**.

r10 prints the promise under its own title and this module is what makes it
true: **"Five stages · nothing is written until you commit at stage four."**

⚠ **THE SAFETY PROPERTY OF THE WHOLE DESIGN IS THIS FILE'S TO KEEP.** Stages
1–3 write `import_runs`, `import_run_rows` and `import_rule_results` and
**NOTHING ELSE** — no `premises`, no `units`, no `service_points`, not one row,
not even a lookup created on the way past. B15 §16's TC-1 asserts it by
counting all three tables before and after a full extract → transform →
validate cycle, and that test was proved RED first by making `transform` write
a premises. Every other guarantee in this design rests on this one, which is
why the load half (stage 4) is a separate phase in a separate commit: the two
halves cannot be reviewed together without the reviewer having to take the
no-write claim on trust.

WHAT EACH STAGE ANSWERS
-----------------------
**1 · EXTRACT** — *"Where is the data coming from?"* Rows, bytes, the
**server-computed** SHA-256, the detected encoding and delimiter, and a
suggested mapping. Every row that entered the file is stored, including the
ones that will fail, because `ReadImportRow`'s ratified claim holds here too:
*every row that enters the file comes out of the report*.

**2 · TRANSFORM** — *"Map their shape onto ours."* The `MAPS TO` picker is
populated from **the columns the target table actually has** (BR-MET-088) plus
this tenant's own custom-field definitions — never a hand-written list of
labels, because a label list drifts from the schema and then an operator maps a
column onto a name with nothing behind it, the row validates, the load reports
success and the value is discarded. That is DEF-388's shape applied to a
migration instead of to one record.

**3 · VALIDATE** — *"Test it before you trust it."* Runs the declared rule set
(`import_rules.py`), stores the rules **as they were** on the run, and attaches
one human sentence to every row that failed.

⚠ **`target=units` IS REFUSED AT STAGE 1, BY NAME.** B15 §17 puts the units
target at P8, and its stage-3 rule set needs an answer this design does not
have: a units row whose premise is on file and whose PLAN is not is *"reject,
or load unplanned and flag"* and nobody has ruled (B15 §4B.3, §8 Q11). Half a
units path — one that extracts and transforms and then cannot judge — would
look finished on screen and would be the more dangerous of the two options
(*"the unit then looks complete on screen and silently under-bills"*). The
refusal names `premises` as the only target this build accepts.

⚠ **`source_kind` OTHER THAN `file` IS REFUSED THE SAME WAY.** Stage 1 draws
four source cards and B15 §4.1 rules three of them *"out of scope for CR-023
unless the PO says otherwise"*. The vocabulary carries all four so a later run
needs no migration; this build accepts one.

WHAT THIS DOES NOT DO, STATED SO NOBODY ASSUMES OTHERWISE
--------------------------------------------------------
* No **address standardisation**. r10's stage-2 transform column offers
  *"Standardise to USPS"* and that is an outside paid integration —
  `04-docs/02-decisions/07-integrations.md` names none. The transform is not
  offered, and the columns endpoint says why rather than leaving a gap.
* No **ZIP+4 split**, for a structural reason rather than a commercial one:
  `premises` has ONE `postal_code` column, so a split has nowhere to put the
  +4. Offering it would accept a value and drop half of it.
* No **write of any kind**, including the `default_to` and `skip_on_load`
  ACTIONS a rule may carry. Stage 3 records what WOULD happen; stage 4 does it.
* r10's sample value for `SVC_AVAIL` is `E,W` — the DISPLAY letters. Services
  are matched here on their code or their name (`electric`, `Electric`), so a
  file using single letters is told which token was not recognised rather than
  having a vocabulary guessed for it.
* Custom-field VALUES are carried as text. Per-type checking against the
  `custom_field` definition (US-TEN-015 owns those rules) is not built here.
"""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import logging
import math
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

# ⛔ **`IntegrityError` AND `DataError` ARE IMPORTED FOR STAGE 4'S ROW LOOP
# (CR-047 widening task 21).** In PostgreSQL a failed statement poisons the
# WHOLE transaction — the connection answers
# `current transaction is aborted, commands ignored until end of
# transaction block` to every subsequent query — so `except IntegrityError:
# continue` on its own is not merely untidy, it CANNOT WORK: the next row's
# very first read would fail. The savepoint is what makes the catch legal,
# and that is why the shape in `_load_locked` is what it is.
from django.db import DataError, IntegrityError, transaction
from django.utils import timezone

from apps.metering import (
    bulk_write,
    import_identity,
    import_progress,
    import_rules,
    models,
    seams,
)
from core import audit as core_audit
from core import errors
from core import jobs as core_jobs
from core import numbering as core_numbering
from core import pagination
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: CR-047 — the ONE place this module speaks to the server log. It is used for
#: a refusal key that reached `_write_refusal_sentences` with no operator
#: sentence written for it: the ROW still gets a reason, and this line is how
#: the gap is found before an operator has to report it.
logger = logging.getLogger("smartbillhub.metering.import")

# ══════════════════════════════════════════════════════════════════════════
# CR-026 · WHERE A STAGE RUNS — the request, or a worker
#
# PO 2026-08-22, verbatim: *"In Premises and Unit import - the sizes of CSV file
# scan be 50,000 or 100,000 units or premises at a time; how you will hnadle
# such volume in upload"*.
#
# MEASURED ON THIS TREE, 50,000 REAL ROWS, LIVE POSTGRES (CR-026 step 3b):
# extract **6.8s** · transform **77.9s** · validate **50.8s** · dry-run **1.9s**
# · load **101.5s**. Three of those blow any web-request timeout, so those three
# — and ONLY those three — can be handed to a BE-07 job (TD-17: Celery on Redis,
# already in the stack; the record, not the broker, is the truth a client polls).
#
# ⚠ **AND THE SMALL FILE MUST NOT NOTICE.** A 3-row import that answered 202 and
# made a screen poll would be a product made worse; the 79 tests that walk
# 3-row files are the contract that says so. So the bar is a ROW COUNT, checked
# before the stage starts, and below it NOTHING changes — same call, same 200,
# same synchronous answer.
# ══════════════════════════════════════════════════════════════════════════

#: The DEFAULT bar, in rows. At 5,000 the slowest stage measures 5,000 x 2.03
#: ms/row = **10.2s**, inside a 30s gateway timeout with 3x margin; the 5,001st
#: row sends the stage to a worker. A row count rather than a clock because the
#: decision has to be made BEFORE the work starts, and rows are the only thing
#: known then.
#:
#: ⛔ **THIS IS THE DEFAULT AND NO LONGER THE WHOLE ANSWER — `DEF-2487`
#: (critical), and it cost a live customer demo.** The 2.03 ms/row above was
#: measured on the PREMISES target, where a row is one INSERT. It was then
#: applied to every target, and an ACCOUNTS row is not a premises row: it opens
#: an account, inherits the unit's services, plan and meters (CR-047 /
#: BR-CUS-672/673), writes an opening balance, posts to the ledger and snapshots
#: the whole account-detail payload for its audit row. **Measured on live
#: Postgres: 45 queries and 121–127 ms per account** — sixty times the figure
#: this bar was set from. 1,048 accounts therefore took **about two minutes
#: inside one web request** (121.9s and 130.6s in two measured runs), and
#: `06-backend/docker-entrypoint.sh` runs gunicorn with
#: `--timeout 60`, so the worker was SIGKILLed at sixty seconds with the
#: transaction still open. Django never formed a response, so there was no
#: envelope, no code and no `trace_id` — the browser showed *"Something went
#: wrong. Nothing was saved — try again."* over a reference it had minted
#: itself. The sentence was TRUE: the transaction rolled back and not one of the
#: 1,048 accounts landed.
#: **So the bar is now PER TARGET (`ASYNC_ROW_BAR_BY_TARGET`, below the target
#: constants because it is keyed on them), and it is measured against the wall
#: the request actually has to clear rather than against a gateway figure.**
ASYNC_ROW_BAR = 5_000

#: What a web worker gives a request before it is killed, in seconds —
#: `gunicorn --timeout "${GUNICORN_TIMEOUT:-60}"`, 06-backend/docker-entrypoint.sh.
#: Recorded HERE, beside the bars, because a bar chosen without it is a guess:
#: this is the number every per-target bar has to divide into with margin, and
#: `tests/test_def2487_accounts_async_bar.py` fails if any of them stops doing so.
WEB_WORKER_TIMEOUT_SECONDS = 60

#: The three BE-07 job kinds — one per deferrable stage, because `run_pending`
#: looks a body up by KIND and a single "import stage" kind would have to carry
#: the stage in its payload and dispatch on it, which is a registry in a second
#: place (apps/tenancy/tasks.py's own docstring makes that argument).
TRANSFORM_JOB = "metering.import.transform"
VALIDATE_JOB = "metering.import.validate"
LOAD_JOB = "metering.import.load"
STAGE_JOBS = {"transform": TRANSFORM_JOB, "validate": VALIDATE_JOB, "load": LOAD_JOB}


# ── caps (BR-MET-038, the rule that already governs premises bulk creation) ──
CSV_ROW_CAP = 100_000  # BR-MET-038 as amended by CR-026 (PO 2026-08-22:
#   "the sizes of CSV file scan be 50,000 or 100,000 units or premises at a
#   time" — the 10,000 cap was a CONFIRMED figure and is SUPERSEDED by the
#   requester's own number; the cap stays a cap because an unbounded upload is
#   a denial-of-service door, and 100,000 is the largest figure the PO named)

#: Bytes a row is allowed to be, for the purpose of the byte cap alone. NOT a
#: per-row limit — no row is ever measured against it — it is the multiplier
#: that turns the row cap into a byte cap.
#:
#: ⚠ **MEASURED, 2026-09-18: THE WIDEST SHIPPED TEMPLATE ROW IS `premises` AT
#: 353 BYTES** (31 columns), then units 208, accounts 199, assets_meters 133,
#: assets_submeters 132, assets_devices 126, parts 53 — taken from
#: `sample_csv(target)` under a real tenant. 512 is that widest figure with
#: about half again on top, because **the template is the NARROWEST realistic
#: file and not the widest**: our sample values are short where a customer's own
#: export carries a full street address, a management company's name and a
#: legacy key.
CSV_BYTES_PER_ROW_ALLOWANCE = 512

#: ⛔ **DERIVED FROM THE ROW CAP, NEVER WRITTEN BESIDE IT — AND THAT IS THE
#: WHOLE OF `DEF-MET-5756`.** This was `10 * 1024 * 1024` with the comment
#: *"US-MET-004 §5: ≤10 MB UTF-8"*, written when a file was three thousand rows.
#: `CR-026` then raised the ROW cap to 100,000 and left this one alone, so the
#: two caps disagreed by a factor of three and **the smaller one won every
#: time**: measured at 80,000 rows, FIVE of the seven targets are refused before
#: a single row is staged — premises 26.9 MB, units 15.9, accounts 15.2,
#: assets_meters 10.2, assets_submeters 10.1, all against 10.
#:
#: The operator never saw a row count. They were told *"the file is too large"*
#: with a megabyte figure, while every sentence the product writes about size —
#: and the number the PO said out loud — counts ROWS. **Two caps for one idea is
#: how a refusal comes to name the wrong limit**, so there is now one number and
#: one derivation, and `tests/test_import_scale_80k.py` fails if the byte cap
#: can ever refuse a file the row cap accepts.
#:
#: 100,000 x 512 B = 51,200,000 B (48.8 MB). It stays a cap for CR-026's own
#: reason — an unbounded upload is a denial-of-service door — and it is now the
#: OUTER of the two, so the limit an operator meets is the one we tell them.
#: ⚠ **AND THE ROW CAP IS NOW WHAT PROTECTS THE WORKER'S MEMORY**, because the
#: parse holds the whole file and a stage holds its whole staged table: measured
#: at 80,000 premises rows the process peaks near a gigabyte. See the decision
#: log of 2026-09-18 for the per-stage figures before raising either number.
CSV_BYTE_CAP = CSV_ROW_CAP * CSV_BYTES_PER_ROW_ALLOWANCE

#: The EP-TEN-08 series CR-005 added for exactly this and nothing has ever
#: allocated from (`core.numbering.IMPORT_RUN`, r10 SET-08 "Import run #",
#: default `RUN-{0000}`). A missing series row is REPORTED, never faked —
#: CR-005 found `JE-` had no row on any tenant and every manual journal entry
#: shipped unnumbered because nothing said so out loud.
IMPORT_RUN_SERIES = core_numbering.IMPORT_RUN

#: The explicit "map this to nothing" choice. BR-MET-088 requires it by name:
#: r10 shows `LEGACY_KEY` mapped to it and reported as `Ignored`, and *"ignored
#: on purpose" must be distinguishable from "nobody mapped it"*.
IGNORE = "__ignore__"

#: Reserved key inside `import_run_rows.mapped`, holding the parse problems
#: stage 2 found and CARRIED rather than coerced away. Stage 3 reads it; stage
#: 4 must strip it before building a record from `mapped`.
PARSE_PROBLEMS = "__parse_problems__"

#: ⛔ **CR-047 task 13 — WHAT A ROW ACTUALLY WROTE, kept on the row.**
#: The same reserved-key convention as `PARSE_PROBLEMS` above and stripped by
#: `_NOT_A_COLUMN` for the same reason, so it can never reach a model. The
#: successes download is a RECEIPT and takes `receipt()`'s law — *"every figure
#: is what the run RECORDED at the moment it loaded; nothing on this path
#: counts rows again"* — and this is where that record lives. Absent on a row
#: loaded before CR-047, which the reader treats as *"the run did not say"*
#: rather than as a zero.
LOAD_RESULT = "__loaded__"

TARGET_PREMISES = "premises"
#: ⚠ **THE SECOND TARGET, AND IT IS A PARAMETER RATHER THAN A SECOND RUNNER
#: (`BR-MET-096`, PO 2026-08-21).** Verbatim: *"same process for premises and
#: Unit - only at tranform stage we differntate field for premises and Units"*.
#: Everything below that used to name `PREMISES_` directly is now looked up BY
#: TARGET, so adding a third target is a dict entry and never a code path. A
#: `if target == units:` branch in extract, transform or validate would be the
#: two implementations that ruling forbids.
TARGET_UNITS = "units"
#: ⚠ **THE THREE ASSETS TARGETS (CR-028 AST-W3 — BR-MET-096 exercised as
#: written: dict entries, never a branch in extract, transform or validate).**
#: Their columns are EXPLICIT declarations rather than model-derived, because
#: the field map B16 §4.7b signs includes destinations that are not `assets`
#: columns at all — `unit_ref` lands as an ASSIGNMENT (BR-AST-045), `service`
#: as a service point, `parent_asset_no` as the BR-AST-003 parent FK — and
#: every declared entry names a real destination (BR-MET-088's intent; the
#: test suite asserts each column-named entry exists on the Asset model).
#: The LOAD delegates every row write to `apps.assets.services` through the
#: seam (B2 r4: assets services are the sole writer of assets rows).
TARGET_ASSETS_METERS = "assets_meters"
TARGET_ASSETS_SUBMETERS = "assets_submeters"
TARGET_ASSETS_DEVICES = "assets_devices"
ASSETS_TARGETS = (TARGET_ASSETS_METERS, TARGET_ASSETS_SUBMETERS, TARGET_ASSETS_DEVICES)
#: The targets whose rejected rows carry EVERY error, joined, rather than the
#: first one (plan U4, PO 2026-09-30 — `DEF-AST-8100`). The asset sheets only:
#: the ruling was about them, and widening it changes the sentence every other
#: target's operators already read.
ALL_PROBLEMS_TARGETS = frozenset(ASSETS_TARGETS)
#: ⚠ **THE SIXTH TARGET (CR-030 W1), AND IT IS THE ONE THE MODULE DOCSTRING
#: PROMISED.** `kinds.ts` has said since CR-023 that *"r10 opens this runner for
#: premises, units, ACCOUNTS, reads, lockbox, bank statements, cost inputs,
#: meters, sub-meters, devices and parts"* and that *"the kinds are DATA so the
#: tenth one costs an object"*. This is that claim being cashed.
#:
#: It is also **S68 being satisfied for the first time**: A1 has specified the
#: account import as *upload → stage → VALUE-MAP → review → commit* since
#: 2026-08-08 and the product shipped a three-step modal with no mapping step
#: (DEF-611), so a utility whose CSV did not already use our header names could
#: not import accounts at all.
#:
#: ⚠ **ACCOUNTS ARE NOT WRITTEN FROM THIS MODULE.** `accounts` is customers'
#: table and a cross-module write is forbidden (B1/B2 §2), so the loader goes
#: through a documented seam exactly as the assets targets do — G20 enforces
#: that every documented seam has an implementer.
TARGET_ACCOUNTS = "accounts"
#: ⚠ **THE SEVENTH TARGET (`CR-077`), AND IT IS THE ACCOUNTS CASE AGAIN RATHER
#: THAN A NEW ARCHITECTURE.** The PO asked on 2026-09-07 for import starters for
#: *"Premises, Units, Meters, Sub meter,s Assets, Parts, Accounts, Reading"*.
#: Parts was handed back as *"an architecture question — whose importer, through
#: which seam"*, and the answer, decided and recorded in
#: `12-governance/02-decision-log.md` of that day, is that two facts already
#: settle it: `BR-MET-096` makes a new target a PARAMETER and never a second
#: runner, and this runner ALREADY writes a table another module owns —
#: `accounts` is customers', written by customers' own `import_writer` through
#: the seam registry.
#:
#: ⚠ **`parts` IS `work`'s TABLE AND NOTHING OUTSIDE `apps/work` TOUCHES IT.**
#: `BR-WRK-002` forbids a foreign write and `G78` fails one from Work's first
#: commit, so the LOAD calls `work.import_writer` through
#: `seams.create_part_from_import` — which makes the boundary STRUCTURAL rather
#: than a thing to be careful about: there is no ORM statement in this module to
#: review.
TARGET_PARTS = "parts"
#: ⚠ **THE EIGHTH TARGET (`06 Payments Page Blueprint.pdf` phase 1, `P1.1`),
#: AND IT IS THE PARTS CASE A THIRD TIME RATHER THAN A NEW ARCHITECTURE.**
#: `payments` is the payments module's table, a cross-module write is forbidden
#: (B1/B2 §2), so the LOAD calls `payments.import_writer` through the seam
#: exactly as `accounts` calls customers' and `parts` calls work's. There is no
#: ORM statement in this module that names a payments table.
#:
#: ⚠ **AND IT NEEDED NO MIGRATION, WHICH WAS CHECKED AND NOT ASSUMED
#: (`P1.3`).** The blueprint marks it a hazard — *"if `import_runs.target`
#: carries a CHECK, an eighth value is a migration"*. Read off a live
#: PostgreSQL 16 database on 2026-09-22: `import_runs.target` is `text NOT
#: NULL` with **zero** CHECK constraints and no enum type, and an INSERT
#: carrying `target = 'utter_nonsense_zzz'` was accepted and rolled back. The
#: only thing that constrains this column is the Python guard at
#: `if target not in TARGETS` — the list two lines below.
#:
#: ⚠ **IT IS INSERT-ONLY, AND THAT IS HARD RULE 4 AND NOT A SIMPLIFICATION.**
#: No UPDATE on a payment, so *Insert & update* would overwrite money on file.
#: **`_refuse_payments_write_mode` is what refuses it**, by name, from the one
#: helper both entry points already call — run it and read it. And there is
#: **no rollback** — see `rollback`, which refuses this target by name, and
#: `_load_payments_rows`, which creates no rollback point to spend.
#:
#: ⚠ **THIS PARAGRAPH NAMED A TABLE THAT DOES NOT EXIST UNTIL `DEF-PAY-6202`**
#: — it said *"`WRITE_MODES_BY_TARGET` offers this target ONE mode"*, and there
#: is no such table anywhere in this module: `WRITE_MODES` is a flat tuple of
#: two modes with no target in it, and the narrowing is a FUNCTION. The
#: behaviour was right and tested the whole time; what was false was the
#: mechanism a reader was sent to look for, which is CLAUDE.md hard-won law 1
#: (a comment claiming a guarantee is not the guarantee) and its own repeated
#: cure: **where a rule restates what a tool does, name the tool.**
TARGET_PAYMENTS = "payments"
TARGETS = (
    TARGET_PREMISES,
    TARGET_UNITS,
    *ASSETS_TARGETS,
    TARGET_ACCOUNTS,
    TARGET_PARTS,
    TARGET_PAYMENTS,
)
SOURCE_FILE = "file"

# ══════════════════════════════════════════════════════════════════════════
# DEF-2487 · THE ASYNC BAR IS PER TARGET, BECAUSE A ROW IS NOT A ROW
# ══════════════════════════════════════════════════════════════════════════
#
# ⛔ **PO ruling 2026-08-30, verbatim: *"can we run anything above 100 recors
# directly using worker batch job"*.** 100 is the requester's own number and it
# is what the accounts bar is set to. The measurement below is not what CHOSE
# the number — it is what confirms the number is safe, which is the direction
# this work was given.
#
# MEASURED ON LIVE POSTGRES, `10-scripts/def2487_accounts_bar_benchmark.py`
# (one transaction per size, rolled back, so it can be re-run at will):
#
#     rows      load      ms/row    headroom vs the 60s web-worker timeout
#      100      12.7s       127       4.7x
#      500      60.5s       121       1.0x   ← already AT the wall
#    1,048     130.6s       125       0.5x   ← DEF-2487: the worker is killed
#
# **Read the 500-row line before touching this table.** At the bar the PO named,
# the load finishes in under thirteen seconds with better than four times'
# margin; at five hundred it lands on sixty seconds exactly, so a slightly
# busier database turns a working import into the same silent 500. The cost per
# row is flat (121–127 ms across a tenfold range), which means the only thing
# the bar controls is how many of them run inside a request — and there is no
# useful bar between 100 and 500, which is why the requester's number is also
# the right one.
#
# ⚠ **THE OTHER TARGETS KEEP 5,000 AND THAT IS A MEASURED POSITION, NOT AN
# OMISSION.** CR-026 timed 50,000 premises rows at 2.03 ms/row for the slowest
# stage, so 5,000 rows is about ten seconds — six times inside the wall. Units,
# the three assets targets and reads all write one record per row through the
# same shape of path. If any of them grows an account-shaped per-row cost, it
# needs a row in this table and a figure beside it; the guard in
# `tests/test_def2487_accounts_async_bar.py` is what makes that a decision
# somebody has to make rather than one that happens by accident.
#: Per-(target, stage) async bars, in rows. A pair with no row here uses
#: `ASYNC_ROW_BAR`. Above its bar the stage is handed to a BE-07 worker and the
#: request answers 202; at or below it, nothing changes.
#:
#: ⚠ **THE KEY CARRIES THE STAGE, AND THAT IS NOT OVER-ENGINEERING — IT WAS
#: MEASURED.** The accounts cost is entirely in the LOAD: on the same 1,048-row
#: file, transform took 0.2s and validate 0.2s (0.2 ms/row, the same shape of
#: work every other target does) while the load took 121.9s. A bar of 100 on all
#: three stages would push a 101-row file's one-fifth-of-a-second validate into
#: a worker and make the operator poll for it — and, on a deployment whose
#: worker is not running, would hang stages 2 and 3 as well as stage 4. The
#: refusal below (`_refuse_no_worker`) keeps that honest either way, but the
#: right bar is still the one the measurement supports.
ASYNC_ROW_BAR_BY_TARGET: dict[tuple[str, str], int] = {
    # 94 ms/row measured — DEF-2487, and the figure the PO named out loud.
    (TARGET_ACCOUNTS, "load"): 100,
    # 2.03 ms/row — CR-026's own measurement (101.5s at 50,000 rows), which is
    # still the only UNCONTENDED timing this repo has for it. 500 rows is
    # therefore about a second, twenty times inside the wall.
    #
    # ⚠ **WHY 500 AND NOT CR-026's 5,000, WHICH ITS OWN ARITHMETIC ALLOWS**
    # (5,000 x 2.03 ms = 10.2s, inside the third of the timeout this repo
    # requires): a re-measurement on 2026-09-18 (`DEF-MET-5756`) found this load
    # issuing **4.45 queries per row** — 8,897 of them for 2,000 rows — so its
    # wall time is dominated by round trips and moves with the database rather
    # than with the code. The re-measurement's own SECONDS are not quoted here
    # and must not be: it ran on a box with seven other suites on the same
    # PostgreSQL, and a contended figure is not a per-row cost. 500 keeps better
    # than four times' margin even if the real cost has grown fourfold since
    # CR-026, and it is still above the 431-row file B15 §16 and the CR-023
    # suites use, so the common case answers synchronously.
    #
    # ⚠ **IT NEEDS AN UNCONTENDED RE-MEASUREMENT AND HAS NOT HAD ONE.** Run
    # `10-scripts/cr026_import_benchmark.py --rows 80000 --pass sync` on a quiet
    # box and put the figure here; until then this bar is deliberately the
    # conservative one.
    (TARGET_PREMISES, "load"): 500,
    # ⛔ **89.0 ms/row MEASURED (`DEF-PAY-6204`, `P1.1`), AND THIS ROW CHANGES
    # NO BEHAVIOUR — 200 is what the stage default below already resolved to.**
    # It is here so the next lane reads a FIGURE instead of inferring one, and
    # so the margin guard can see this target at all; until it was written, the
    # eighth target had a bar and nothing in the repo knew what it cost.
    #
    # MEASURED 2026-09-22 on a PostgreSQL 16 clone migrated to the tip, with
    # `app.tenant_id` set and every row confirmed WRITTEN (a load that rejects
    # is fast and means nothing) — `10-scripts/pay_p1_1_load_bar_benchmark.py`:
    #
    #     rows      load      ms/row    created
    #       50      4.51s       90.2      50
    #      100      8.87s       88.7     100
    #      200     17.81s       89.0     200
    #      400     36.61s       91.5     400
    #
    # **Flat across an eightfold range, so it is a per-row cost and not a fixed
    # overhead** — and it is ACCOUNTS-SHAPED (94 ms/row) rather than
    # premises-shaped (2.03), which is what a row walking the match ladder,
    # creating a payment through payments' own writer and writing an audit row
    # was always going to be.
    #
    # ⚠ **SO THE STAGE DEFAULT'S OWN REASONING IS CONFIRMED, NOT REFUTED.** It
    # says 200 is the worst measured load's bar and fails closed at 18.8s for an
    # accounts-shaped target; payments came out at 18.3s at the bar, inside the
    # 20.0s a third of the request allows. **The bar is therefore NOT moved.**
    #
    # ⚠ **BUT 1.1x IS THE TIGHTEST MARGIN IN THIS TABLE** — accounts has 2.1x
    # and premises better than 4x — and this figure was taken on a box running
    # other lanes' suites against the same PostgreSQL. The premises entry above
    # already states the rule that applies here: **a contended figure is not a
    # per-row cost.** Re-run the benchmark on a quiet box before anyone leans on
    # the margin; if the true cost is above 100 ms/row the bar belongs at 100,
    # beside accounts.
    (TARGET_PAYMENTS, "load"): 200,
    # ⛔ **METERS: ~20 ms/row MEASURED, INSERT AND UPDATE (`DEF-AST-8103`, PO GO
    # 2026-09-30), SO THE BAR MOVES 200 → 500.** PostgreSQL 16, a migrated and
    # `seed_demo`'d database, every row confirmed WRITTEN,
    # `10-scripts/def_ast_8103_upload_cost.py` (statements counted with an
    # execute wrapper, never `CaptureQueriesContext`, which keeps only 9,000):
    #
    #     rows | insert s | stmt/row | update s | stmt/row      (branch base)
    #      100 |     2.16 |     21.4 |     2.36 |     19.3
    #      500 |    11.78 |     21.1 |    12.04 |     19.1
    #     1000 |    24.74 |     21.0 |    23.67 |     19.0
    #     rows | insert s | stmt/row | update s | stmt/row      (this change)
    #      100 |     1.90 |     21.4 |     1.75 |      9.3
    #      500 |     9.57 |     21.1 |     9.03 |      9.1
    #     1000 |    20.09 |     21.0 |    18.66 |      9.0
    #
    # 500 rows is ~9.6 s — inside the THIRD of the 60 s wall this table holds
    # every bar to (20 s), with 2x margin. **Meters only**: the sub-meters and
    # devices loads were not timed (a device seats on a service point, which
    # is more work), so they keep the stage default of 200 until somebody
    # measures them — the fail-closed posture the default states.
    # ⚠ **AND THE BAR DOES NOTHING ON A DEPLOYMENT RUNNING `JOBS_EAGER=true`**:
    # a "deferred" stage then runs inside the request anyway
    # (`09-infra/02-aws-runbook.md`). Uploads above a bar need `JOBS_EAGER=false`
    # and a running worker.
    (TARGET_ASSETS_METERS, "load"): 500,
}

#: The bar for a stage with no per-target row above, keyed by STAGE ALONE.
#:
#: ⚠ **THIS EXISTS BECAUSE ONE BAR WAS BEING SPENT ON THREE STAGES THAT DIFFER
#: BY TWO ORDERS OF MAGNITUDE, WHICH IS DEF-2487's MECHANISM ONE LEVEL UP.**
#: Every load this repo has measured costs far more per row than its own
#: transform or validate — premises 2.03 against 0.60 and 0.79 (CR-026, and the
#: two cheap figures re-measured at 80,000 rows on 2026-09-18), accounts 94
#: against 0.19 and 0.19 (DEF-2487) — so the cost belongs to the STAGE far more
#: than to the target, and one number for all three will always be wrong for one
#: of them. Transform and validate keep 5,000; a load nobody has measured
#: takes 200.
#:
#: ⚠ **AND THE SIX UNMEASURED LOADS ARE THE WHOLE POINT.** `DEF-2487` fixed the
#: accounts load bar and its guard asserts THAT ONE PAIR. The default of 5,000
#: — justified on premises at 2.03 ms/row — went on being inherited by units,
#: the three assets targets and parts, none of which anybody has timed. Accounts
#: is what happens when that inheritance is wrong: 94 ms/row, and 5,000 rows
#: would be **470 seconds inside a request gunicorn kills at 60**. Nothing said
#: the other five are cheap; nothing had looked.
#:
#: ⚠ **200 IS THE WORST MEASURED LOAD's BAR, NOT THE BEST — IT FAILS CLOSED
#: (hard-won law 3).** 200 x 94 ms/row is 18.8s, inside the third of the
#: timeout `tests/test_def2487_accounts_async_bar.py` allows. An unmeasured
#: target that turns out to be accounts-shaped is therefore safe on the day it
#: is written rather than on the day somebody remembers to measure it; a target
#: that turns out to be cheap loses nothing but a poll, and earns a row in
#: `ASYNC_ROW_BAR_BY_TARGET` the moment anyone times it.
ASYNC_ROW_BAR_BY_STAGE: dict[str, int] = {"load": 200}


def async_row_bar(target: str | None, stage: str) -> int:
    """The row bar for this target's stage — its own, its stage's, or the default.

    ⚠ **ALWAYS ASK THIS RATHER THAN READING `ASYNC_ROW_BAR`.** Reading the
    module constant directly is how a target silently inherits a bar measured on
    a different target, which is DEF-2487 exactly — and since `DEF-MET-5756` the
    constant is no longer even the usual answer for a load, so a caller reading
    it gets 5,000 where every load in the product uses 500 or less.
    """
    key = (str(target or ""), stage)
    if key in ASYNC_ROW_BAR_BY_TARGET:
        return ASYNC_ROW_BAR_BY_TARGET[key]
    return ASYNC_ROW_BAR_BY_STAGE.get(stage, ASYNC_ROW_BAR)

#: Never a mapping target, on any run. `tenant` comes from the session and is
#: never taken from a file (CLAUDE.md hard rule 1 — B15 §4.3A calls it *"not a
#: validation at all"*); `is_sample` is BR-TEN-013's, written only by this
#: module's own sample path; the timestamps are the database's.
#:
#: ⛔ **`created_at` LEFT THIS SET ON 2026-10-17 (`DEF-MET-10164`).** PO,
#: verbatim: *"Import (premises and units) may carry an optional Created column
#: — the date the property was first set up in the old system. Blank → the
#: import day."* It is OFFERED on exactly the two declared targets that name it
#: (`PREMISES_COLUMNS` / `UNITS_COLUMNS`) and nowhere else: the accounts and
#: assets targets declare their own column sets and do not list it. The stamp
#: is still the database's on every row that does not carry one.
NEVER_IMPORTABLE = frozenset({"id", "tenant", "is_sample", "updated_at", "deleted_at"})

#: `DEF-MET-10164` — the one timestamp a premises or units file may carry.
CREATED_FIELD = "created_at"


# ═══════════════════════════════════════════════════════════════════════════
# THE FIELD MAP — DECLARED, AND CHECKED AGAINST THE MODEL (BR-MET-088)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **`DEF-MET-5802`, PO 2026-09-19 — THIS SET USED TO BE DERIVED FROM
# `Premises._meta` AND IS NOW DECLARED BELOW.** The note that stood here read
# *"a column added to `premises` tomorrow is offerable tomorrow"*, and that was
# the DEFECT rather than the feature: derivation cannot judge whether a column
# is a **utility's to supply**. So every field the address-matching process
# writes for itself was published to every customer's import template the day
# it landed, with a label generated from the field name — which is how **"Gis
# parcel id was"** and **"Gis verified at"** became user-facing column
# headings. Nobody chose them; they arrived.
#
# ⚠ **CURATED, NOT FILTERED, AND THE DIFFERENCE IS THE WHOLE RULING.** The
# first proposal was to keep deriving and exclude the machine-written fields.
# The PO's own question is what refused it: a filter removes the GIS noise and
# can NEVER surface a column that is MISSING, because no filter finds something
# that was never there. Declaring the list is what makes an absence visible —
# and an absence is what `DEF-MET-5803` turned out to be.
#
# ⚠ **SO THE DECLARATION OWES BACK THE PROTECTION DERIVATION GAVE FOR FREE.**
# The derived version's own docstring put it exactly right and it is worth
# keeping the words: *"the picker cannot offer a target with no column behind
# it and cannot omit one that exists"*. A DECLARED list keeps the first half by
# construction and **loses the second** — it can silently omit a real column,
# which is precisely what derivation was protecting against. Three things pay
# that debt back: the declared tuple below, the NOT-OFFERED table beside it
# **with its reason per column**, and
# `tests/test_def_met_5802_declared_columns.py`, which asserts that
# **declared + not-offered + NEVER_IMPORTABLE accounts for EVERY concrete field
# on the model**. Add a field to `premises` and that test goes RED naming it
# until somebody DECIDES which of the two tables it belongs in. It is the same
# debt the three assets targets already pay by declaring
# (`EXPLICIT_COLUMNS_BY_TARGET`), and it is the same answer.
#
# ⚠ **THE ORDER IS THE FILE'S ORDER.** `sample_csv` writes these as its header
# row in this sequence, so this tuple is what a utility reads left to right.

#: The premises columns a UTILITY supplies, in file order (`DEF-MET-5802`).
#: ⚠ `custom_data` is listed at its own position and expands to one entry per
#: DEFINED tenant field — see `target_columns`. It IS a column of the model, so
#: leaving it out of this tuple would silently drop B15 §4.2A #14's *"by name"*
#: tenant fields, which is this declaration's own failure mode.
PREMISES_COLUMNS: tuple[str, ...] = (
    "premise_no",
    "name",
    "address_line",
    "city",
    "state",
    "postal_code",
    "inside_city_limits",
    "premises_type",
    "services_available",
    "area",
    "owner",
    "external_ref",
    "lat",
    "lng",
    "status",
    "gis_parcel_id",
    # `DEF-MET-10164` — optional; blank is the import day.
    "created_at",
    "custom_data",
)

#: The unit columns a UTILITY supplies, in file order (`DEF-MET-5802`).
UNITS_COLUMNS: tuple[str, ...] = (
    "premises",
    "unit_no",
    "label",
    "external_ref",
    "unit_type",
    "floor_label",
    "square_feet",
    "lat",
    "lng",
    "gis_point_id",
    "rate_plan",
    "plan_effective_from",
    "plan_locked",
    "vacant_standby_auto",
    "is_common_area",
    # `DEF-MET-10164` — the UNIT's own date; optional; blank is the import day.
    "created_at",
    "custom_data",
)

# ⛔ **THE REAL GIS KEYS STAY, AND THE DIVIDING LINE IS *WHO WRITES IT*.**
# `gis_parcel_id` (premises) and `gis_point_id` (units) are what a **CITY GIVES
# A UTILITY**: the parcel and point identifiers a utility already holds in the
# file it is migrating. Every other member of that block is written BY the
# address-matching process — who checked it, when, whether it verified, and
# what the key used to be. **A utility typing *"Gis verified at"* into a
# spreadsheet is asserting something only the system is entitled to
# determine**, and the template invited them to.

#: Premises columns the model HAS and the template deliberately does NOT offer,
#: each with the reason it is not a utility's to supply.
#: ⚠ **NOT A DUMPING GROUND.** Every entry is a DECISION, and the completeness
#: test refuses a model field that appears in neither this table nor
#: `PREMISES_COLUMNS`.
PREMISES_COLUMNS_NOT_OFFERED: dict[str, str] = {
    "owner_manager": (
        "The legacy free-text owner box. `Owner name` is the column that names "
        "an owner and the only one `owner_account_verdict` reads; offering both "
        "put two name-shaped columns on one template where only one of them "
        "created anybody. `_resolve_owner_ref` still writes this FIELD from the "
        "`Owner name` cell as BR-MET-151 provenance, so nothing stops being "
        "recorded — it stops being ASKED FOR twice (`DEF-MET-5803`)."
    ),
    "gis_unchecked": (
        "Written by the address-matching process — its own working flag, not a "
        "fact a utility holds."
    ),
    "gis_checked_by": "Written by the address-matching process — it records WHO ran it.",
    "gis_checked_at": "Written by the address-matching process — it records WHEN it ran.",
    "gis_parcel_id_was": (
        "Written by the address-matching process — the PREVIOUS parcel key, kept "
        "so a change can be seen. The current key, `gis_parcel_id`, IS offered."
    ),
    "gis_key_changed_at": "Written by the address-matching process — when the key last moved.",
    "gis_status": "Written by the address-matching process — its own verdict on the row.",
    "gis_verified": (
        "Written by the address-matching process — a utility asserting it would "
        "be asserting our own check on our behalf."
    ),
    "gis_verified_at": "Written by the address-matching process — when that verdict was reached.",
}

#: Unit columns the model HAS and the template deliberately does NOT offer.
UNITS_COLUMNS_NOT_OFFERED: dict[str, str] = {
    "gis_point_id_was": (
        "Written by the address-matching process — the PREVIOUS point key. The "
        "current key, `gis_point_id`, IS offered."
    ),
    "gis_key_changed_at": "Written by the address-matching process — when the key last moved.",
    "gis_status": "Written by the address-matching process — its own verdict on the row.",
    "gis_verified": (
        "Written by the address-matching process — a utility asserting it would "
        "be asserting our own check on our behalf."
    ),
    "gis_verified_at": "Written by the address-matching process — when that verdict was reached.",
}

#: target → its declared column order. A dict rather than a branch, for
#: `BR-MET-096`'s reason: one runner serves every target, and a branch on the
#: target name is how the seventh one starts diverging.
DECLARED_COLUMNS_BY_TARGET: dict[str, tuple[str, ...]] = {
    TARGET_PREMISES: PREMISES_COLUMNS,
    TARGET_UNITS: UNITS_COLUMNS,
}

#: target → the model columns it deliberately withholds, with the reason each.
NOT_OFFERED_COLUMNS_BY_TARGET: dict[str, dict[str, str]] = {
    TARGET_PREMISES: PREMISES_COLUMNS_NOT_OFFERED,
    TARGET_UNITS: UNITS_COLUMNS_NOT_OFFERED,
}

#: kind → how the value is parsed and which transforms are offered.
KIND_TEXT = "text"
KIND_BOOLEAN3 = "boolean3"  # ⚠ THREE-STATE — see `_parse_boolean3`
KIND_LOOKUP = "lookup"  # resolved against a Reference-data list
KIND_AREA = "area"  # resolved against tenancy.areas — checked, never created
KIND_LIST = "list"  # comma-separated, ⊆ tenant-enabled
KIND_ENUM = "enum"
KIND_CUSTOM = "custom"
#: ⚠ **A REFERENCE TO A ROW THAT MUST ALREADY EXIST**, carried as the
#: customer's own text and resolved at LOAD time — the same posture `KIND_AREA`
#: takes and for the same reason: resolving an id during stage 2 would make a
#: rehearsal depend on data that can change before the commit. Stage 3 is what
#: checks the row is there, and the two kinds differ ONLY in what happens when
#: it is not (`BR-MET-100` — a missing premise rejects, a missing plan does not).
KIND_PREMISE_REF = "premise_ref"
KIND_PLAN_REF = "plan_ref"
KIND_INTEGER = "integer"
KIND_DATE = "date"
#: `tenant_settings.date_format` (BR-TEN-020, the S8 Regional screen) → the
#: pattern that reads it. ⚠ **THE KEYS ARE `apps.tenancy.services.DATE_FORMATS`
#: VERBATIM AND MUST STAY THAT WAY** — a key this table spells differently is
#: not a wrong date, it is a SILENTLY UNREAD setting, and the tenant would go on
#: seeing their format on screen while the importer refused every row in it.
#: A test pins the two sets equal rather than trusting this comment (law 1).
#:
#: `%m`/`%d` read `1` and `01` alike, which is what a real US export carries.
#:
#: ⚠ **`DD-MMM-YY` READS ENGLISH MONTH NAMES AND ONLY ENGLISH ONES (DEF-753).**
#: `%b` is the C-locale abbreviation, so `25-Aug-26` parses and `25-Okt-26`,
#: `25-Mär-26` and `25-mars-26` are all REFUSED — measured, not assumed. The
#: SCREEN's month name comes from `Intl` in the tenant's own language and is a
#: different direction entirely; one sentence in `apps/tenancy/services.py` used
#: to cover both, which is why nobody checked the import half for eleven
#: locales. Refusing is the SAFE half — nothing is mis-dated — and the harm is
#: that a German utility got every row rejected with no reason it could act on.
#: So the REFUSAL says so (`_date_problem`) and the S8 picker says so, and this
#: parser does NOT start guessing: a month table per language would be eleven
#: guesses about a file OUR APP DID NOT WRITE, and BR-MET-117 (1) forbids
#: exactly that kind of "try until one works".
DATE_FORMAT_PATTERNS: dict[str, str] = {
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD.MM.YYYY": "%d.%m.%Y",
    "DD-MM-YYYY": "%d-%m-%Y",
    "YYYY/MM/DD": "%Y/%m/%d",
    "DD-MMM-YY": "%d-%b-%y",
}
#: The twelve abbreviations `%d-%b-%y` accepts, in the C locale — NAMED so the
#: refusal can list them instead of leaving an operator to guess which spelling
#: of October this parser wants (DEF-753). Derived from `strptime` itself in
#: `tests/test_def753_month_names_are_english.py` rather than trusted here.
ENGLISH_MONTH_ABBREVIATIONS: tuple[str, ...] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

#: The formats whose cells carry a month NAME. `_date_problem` says out loud
#: that the name has to be English; every other format is digits and separators
#: and needs no such sentence.
MONTH_NAME_FORMATS: frozenset[str] = frozenset({"DD-MMM-YY"})

KIND_BOOLEAN = "boolean"
#: ── the assets targets' kinds (CR-028 AST-W3) ──────────────────────────────
#: A decimal quantity — money (4dp stored) or a capacity (6dp). Parsed with
#: `Decimal` (HR-2: never float), carried as its STRING so `mapped` stays
#: JSON-safe; the assets service re-parses at write time.
KIND_DECIMAL = "decimal"
#: The customer's own UNIT reference (BR-AST-045) — carried as text, judged at
#: stage 3 against the unit index, resolved at load by THE SAME index. Blank
#: is ACCEPTED (→ inventory), which is the whole of the PO's ruling.
KIND_UNIT_REF = "unit_ref"
#: ── DEF-1088 · BR-MET-402 — the OWNER, carried as the customer's own text ──
#: The same posture `KIND_AREA` and `KIND_PREMISE_REF` take, and for the same
#: reason: resolving a party id during stage 2 would make a rehearsal depend on
#: data that can change before the commit. Stage 3 judges it; the LOAD resolves
#: it. What differs is the three-way answer underneath (`resolve_owner_name`):
#: an EXACT name reuses the party that exists, a NEAR name is REJECTED for a
#: person to settle (PO decision 3 — *"offer the match, clerk decides"*, so the
#: import may not pick), and an unknown name creates the party only when the
#: file also carries a CATEGORY, because BR-MET-151 clause 3 forbids reading a
#: category off a name.
KIND_OWNER_REF = "owner_ref"
#: A parent METER's number (BR-AST-003) — same carried-text posture.
KIND_ASSET_REF = "asset_ref"

# ── CR-058 W3 · BR-MET-1030 — THE OWNER'S IDENTITY, ON THE PREMISES FILE ───
#: Person or company, and it is NOT decoration: it decides WHICH identifier
#: counts (`BR-CUS-1022`). A Social Security number does not satisfy a company
#: and a Tax ID does not satisfy a person, so an identifier presented under an
#: unstated kind cannot be judged at all and is refused by name rather than
#: filed where the other kind's matcher will never look.
#:
#: ⚠ **A SEPARATE KIND FROM `KIND_ENUM`, DELIBERATELY.** `KIND_ENUM` is
#: hardwired to `PREMISES_STATUSES` in `_map_row` — the product has exactly one
#: enumerated premises column and the branch says so. Widening that branch to
#: take its options from the column would be a better shape and a bigger change
#: on a path six targets share; a second kind with its own two-line branch
#: cannot break the status column at all.
KIND_OWNER_KIND = "owner_kind"

#: The two values, in `customers.identity_match`'s own spelling. Stated here
#: rather than imported so the metering module does not take a hard dependency
#: on customers' constants for a dropdown; the WRITE goes through the seam,
#: where customers judges the value with its own vocabulary.
OWNER_KINDS: tuple[str, ...] = ("person", "company")

#: Which identifier column belongs to which kind — `BR-CUS-1022`, mirrored here
#: so stage 3 can flag a borrowed identifier on the operator's own file instead
#: of the writer refusing it one stage later on row 9,881.
#: ⚠ **THIS MIRRORS `identity_match.CREATE_IDENTIFIER_FIELDS` AND IS NOT A
#: SECOND OPINION BESIDE IT.** It decides what the IMPORT SCREEN says; the
#: creation minimum is customers' and is applied by customers.
OWNER_IDENTIFIER_COLUMNS_BY_KIND: dict[str, tuple[str, ...]] = {
    "person": ("owner_ssn", "owner_driving_licence", "owner_phone"),
    "company": ("owner_tax_id",),
}

#: Every identity column the premises file can carry, in the order the PO named
#: them: *"DL, SSN, Phone or Tax ID"*.
OWNER_IDENTIFIER_COLUMNS: tuple[str, ...] = (
    "owner_driving_licence",
    "owner_ssn",
    "owner_phone",
    "owner_tax_id",
)

#: The import column → the key `customers` knows the same fact by. One table,
#: so the spreadsheet's vocabulary and the module boundary's cannot drift.
OWNER_IDENTIFIER_FIELD: dict[str, str] = {
    "owner_ssn": "ssn",
    "owner_driving_licence": "driving_licence",
    "owner_phone": "phone",
    "owner_tax_id": "tax_id",
}

#: The four values `premises.status` holds — `draft | pending | active |
#: inactive`. r10's own premises list draws a **Pending** row and its page
#: sub-line reads *"12 pending activation"*, so a migration that cannot land
#: rows as pending must land 428 LIVE premises in one commit (B15 §4.2A #13).
PREMISES_STATUSES = ("draft", "pending", "active", "inactive")

#: field name → label / kind / required. Anything not named here is KIND_TEXT
#: with a label derived from the column name. ⚠ THIS TABLE NEVER DECIDES WHICH
#: COLUMNS ARE OFFERED — the model does (BR-MET-088). It decides only how an
#: offered column is presented and parsed.
def _as_column_kwargs(spec: dict[str, Any]) -> dict[str, Any]:
    """One spec, two call conventions — the adapter, and it exists because the
    two are genuinely different and neither is wrong.

    `PREMISES_FIELD_OVERRIDES` / `UNITS_FIELD_OVERRIDES` are DICTS merged into
    a derived column, so they spell the served key directly: `help`, `label`.
    `_account_column` / `_asset_column` are FUNCTIONS, so they spell the
    PARAMETER: `help_text`, and `label` is positional.

    Renaming one to match the other would touch every declared column on four
    targets to save six lines here. This translates instead, and it drops
    `label` because every caller supplies its own — a duplicate would be a
    `TypeError` at import time rather than a wrong screen, which is the failure
    mode to prefer but still one to avoid.
    """
    kwargs = {k: v for k, v in spec.items() if k not in ("label", "kind")}
    if "help" in kwargs:
        kwargs["help_text"] = kwargs.pop("help")
    return kwargs


def _issued_number_column(noun: str, setting: str) -> dict[str, Any]:
    """⛔ **CR-046 — THE IDENTIFIER COLUMN, ONE SHAPE FOR ALL FOUR UPLOADS.**

    This is `_asset_number_column`'s contract (BR-AST-049, 2026-08-27) stated
    once for the targets whose columns are DERIVED from a model rather than
    declared — premises, units — and reused verbatim by the accounts target.
    The PO widened the meter ruling to all four on 2026-08-27 (CR-046, fifth
    message: *"you ahve understood the happy path for Meters - can you use
    similar logic and update the upload logic for all 4 entities"*).

    Three things it does, and each is a decision the meters lane already made
    and this one must not re-litigate:

    1. **The header says `(existing only)`.** The column used to mean *"the
       number to give this record"*. It now means *"an EXISTING number, if this
       row updates a record already in SMARTBillHub — blank for a new one"*,
       and **blank is the normal case and the only case in Insert mode.**
    2. **The sample cell is an explicit `""`.** `sample=None` falls through to
       the kind-generic worked value and would ship `Sample premise ID` or
       `P-9001` in the downloadable template — an invented number, on the one
       column the PO objected to being asked to invent. That is `DEF-962`, and
       an explicitly declared empty sample is the fix.
    3. **The column is NOT deleted**, because it has a second job the ruling
       must not take with it: it is the MATCH KEY that tells *Insert & update*
       which record a row is about.

    ⚠ **THE SETTING IS NAMED BY ITS CLICK PATH, NOT BY A RULE ID** — standing
    PO instruction: things reach a person in plain English, never as an ID to
    go and look up.
    """
    lower = noun.lower()
    # ⚠ *"a account"* reached a screen once. The article is computed rather
    # than hard-coded because these four sentences are built from a noun the
    # caller supplies, and the next noun added here would break it again.
    article = "an" if lower[:1] in "aeiou" else "a"
    return {
        "sample": "",
        "blank_means": "a new number is issued from your numbering settings",
        "help": (
            f"LEAVE THIS BLANK for {article} new {lower} — SMART360 Next issues "
            f"the number from Settings → Numbering → {setting}, so it can never "
            "collide with one already in use or arrive in a shape your "
            f"settings would not produce. Fill it in ONLY to update {article} "
            f"{lower} already on file, quoting the number this system shows on "
            "its own screen. Your old system's number goes in External "
            "reference."
        ),
    }


def _legacy_ref_column(noun: str) -> dict[str, Any]:
    """⛔ **CR-046 C5 — WHERE THE UTILITY'S OWN NUMBER GOES NOW THAT THE
    IDENTIFIER COLUMN NO LONGER TAKES IT** (`_assets_external_ref_column`'s
    contract, BR-AST-049, applied to premises · units · accounts).

    A utility migrating from an old system holds its own reference for every
    record — the id its previous software printed on every work order. Under
    the ruling that reference had nowhere to go on three of the four targets
    and would have been **lost at import**.

    ⚠ **AND IT IS A LAWFUL MATCH KEY**, because CR-046 C5 makes it
    `UNIQUE (tenant, lower(external_ref))` on all four
    (`uq_premises_tenant_external_ref_ci` · `uq_units_tenant_external_ref_ci` ·
    `uq_accounts_tenant_external_ref_ci`) — which is what matters on the FIRST
    migration, where the operator's corrected re-run holds no SMARTBillHub
    number to quote. `_key_of` falls back to it on every target.
    """
    lower = noun.lower()
    return {
        "label": "External reference",
        "kind": KIND_TEXT,
        "sample": "",
        "blank_means": "nothing to reconcile against your old system",
        "help": (
            f"YOUR OWN number for this {lower} — the id your previous system "
            "used. It is kept so you can reconcile the two lists after the "
            "migration, and so a corrected re-run of this same file updates "
            "the rows it created instead of duplicating them. It is unique "
            "within this utility, and it is not the number SMART360 Next issues."
        ),
    }


def _created_column(noun: str) -> dict[str, Any]:
    """`DEF-MET-10164` — the optional **Created** column, one shape for both
    targets (PO 2026-10-17, point 4: *"the date the property was first set up
    in the old system. Blank → the import day. Future or unreadable → that row
    refused with a short reason."*).

    ⚠ **`KIND_DATE`, SO IT READS THE TENANT'S OWN FORMAT AND ISO — AND NOTHING
    ELSE** (`_parse_date`, BR-MET-117 (1)). `_parse_created` adds one more
    reading: the timestamp our own export writes in this column, so a
    downloaded list round-trips.

    ⚠ **THE SAMPLE CELL IS BLANK** — `DEF-962`'s ruling: we hold no truthful
    old-system date to put there, and blank is what most rows will carry.
    """
    return {
        "label": "Created",
        "kind": KIND_DATE,
        "sample": "",
        "blank_means": "the import day",
        "help": (
            f"The date this {noun} was first set up in your old system. Leave it "
            "blank to use the import day. A future date is refused. On a file "
            f"that carries only the {noun} number and this column, Insert & "
            "update corrects the Created date of records already on file."
        ),
    }


#: `DEF-MET-10164` — what a Created column may be headed in a utility's file.
CREATED_ALIASES: tuple[str, ...] = (
    "created",
    "created_at",
    "created on",
    "created date",
    "date created",
    "setup date",
    "set up date",
)


PREMISES_FIELD_OVERRIDES: dict[str, dict[str, Any]] = {
    "created_at": _created_column("property"),
    # ⛔ **CR-046 C2 — `premise_no` CHANGED MEANING ON 2026-08-27.** It used to
    # be *"the number to give this premises"*, sampled `P-9001`, and a blank
    # fell through to the series. It is now an EXISTING number or nothing; see
    # `_issued_number_column` for the three decisions behind that.
    "premise_no": {"label": "Premise ID (existing only)", **_issued_number_column("Premises", "Premises")},
    "address_line": {"label": "Address line 1", "required": True},
    "postal_code": {"label": "Postal code"},
    "inside_city_limits": {"label": "Inside city limits", "kind": KIND_BOOLEAN3},
    "premises_type": {"label": "Premise type", "kind": KIND_LOOKUP},
    "services_available": {"label": "Services available", "kind": KIND_LIST},
    "area": {"label": "Area / sub-area", "kind": KIND_AREA},
    # ⚠ **THE LABEL IS ALWAYS ONE OF A COLUMN'S ALIASES BY CONSTRUCTION
    # (DEF-1077)**, so a label may only ever be changed to a string this
    # column's alias tuple already contains. `owner name` is one of `owner`'s
    # four aliases, which is what makes the rename below safe: the sample
    # writes the label as its header row and the file has to keep mapping
    # itself.
    #
    # ⛔ **RENAMED `Owner` → `Owner name` BY `DEF-MET-5803`, 2026-09-19.** The
    # PO read this template and reported that it cannot NAME an owner. It
    # could — THIS is the column `owner_account_verdict` reads, and a row with
    # no value here creates nobody at all — but the template offered TWO
    # name-shaped columns, `Owner` and `Owner name (legacy)`, and only one of
    # them created anybody. A utility filling in the more explicit-sounding of
    # the two got an address and no owner. `DEF-MET-5802` retires the legacy
    # box from this template and this label says plainly what the survivor is
    # for.
# ⛔ **`DEF-962`'s RULING, APPLIED TO THE FOUR COLUMNS IT DID NOT REACH.**
# The PO objected to a shipped sample proposing a value they would have to
# invent, and the fix was `sample=""` on the reference columns. `lat`, `lng` and
# the two GIS KEYS were never enumerated, so they fell through to the generic
# fallback and the downloadable file read **`Sample lat`**, **`Sample lng`**,
# **`Sample gis parcel id`** and **`Sample gis point id`**. A latitude column
# whose worked cell is the words *"Sample lat"* is not an example, it is a
# parse failure with a friendly name — and a parcel key is the CITY'S, so we
# have nothing truthful to put there. All four ship BLANK.
#
# ⚠ **Found by reading the generated file for `DEF-MET-5802`** rather than by
# any check: nothing in this repo compares a sample cell with the column it
# sits under.
    "lat": {"label": "Lat", "sample": ""},
    "lng": {"label": "Lng", "sample": ""},
    "owner": {
        "label": "Owner name",
        "kind": KIND_OWNER_REF,
        "help": (
            "The owner's name, as it should appear on their bill. With one "
            "identifier beside it this creates the owner's master account."
        ),
    },
    # ⚠ **`owner_manager` IS NO LONGER OFFERED** — see
    # `PREMISES_COLUMNS_NOT_OFFERED`. The entry stays because this table only
    # ever PRESENTS an offered column, so it costs nothing and keeps the label
    # should the column ever be offered again.
    "owner_manager": {"label": "Owner name (legacy)"},
    # ⚠ **THE CITY'S KEY, SO IT GETS A HUMAN LABEL.** `DEF-MET-5802` keeps this
    # column and retires `gis_parcel_id_was` beside it; a kept column with a
    # machine-generated heading (*"Gis parcel id"*) is the same complaint one
    # size smaller.
    "gis_parcel_id": {
        "label": "GIS parcel ID",
        "help": "The parcel identifier your city or county assigns this property.",
        "sample": "",
    },
    "external_ref": _legacy_ref_column("Premises"),
    "status": {"label": "Status", "kind": KIND_ENUM},
}

#: Header aliases for stage 1's auto-detect. This is a CONVENIENCE, not the
#: offered set: detection may guess, the picker may not invent. r10's own ten
#: headers are all here, including `LEGACY_KEY` → `external_ref`, which r10
#: itself throws away — B15 §4.2A #12: discarding the customer's own key means
#: you can never reconcile against their system, a re-import duplicates every
#: row it already created, and *"what happened to property 88214"* has no
#: answer. ⚠ `UNIT_CNT` HAS NO ALIAS AND MUST NOT GAIN ONE: `premises` has no
#: expected-units column, and BR-MET-088 forbids offering a target with nothing
#: behind it (OQ-330).
PREMISES_ALIASES: dict[str, tuple[str, ...]] = {
    # `DEF-MET-10164` — `premise id` (with a space) added: the dates-only
    # correction file the ruling's deploy note describes is "number + date",
    # and a header typed `Premise ID` matched NOTHING, so the file read as a
    # Created column alone and was refused as missing its address. Found by
    # the walk (W8), not by a test.
    "premise_no": (
        "premise_id",
        "premise id",
        "premise no",
        "premise_no",
        "premise",
        "property id",
    ),
    "name": ("name", "premises name", "property name", "building"),
    "address_line": ("addr1", "address", "address1", "address_line", "street", "street address"),
    "city": ("city", "town"),
    "state": ("state", "province"),
    "postal_code": ("zip", "zipcode", "zip code", "postal_code", "postcode"),
    "inside_city_limits": (
        "inside_city_limits",
        "inside city limits",
        "inside_city",
        "city limits",
        "in_city",
        "jurisdiction",
    ),
    "premises_type": ("prop_type", "property type", "premises_type", "type"),
    "services_available": ("svc_avail", "services", "services available", "services_available"),
    "area": ("area", "district", "sub_area", "sub-area", "area / sub-area"),
    # ── DEF-1247 / DEF-1088 — `Owner` NOW REACHES THE TYPED OWNER ──────────
    # ⚠ **THIS IS A CHANGE OF MEANING FOR A HEADER UTILITIES ALREADY SHIP, AND
    # IT IS DELIBERATE.** `owner` used to be the FIRST alias of the free-text
    # column, so when CR-039 wave C added the typed `Premises.owner` FK — and
    # the offered set is derived from the MODEL (BR-MET-088), so the sample
    # started shipping both headers — the alias loop claimed `owner` for the
    # free text and the `owner_manager` header was never claimed at all. Two
    # tests were RED on it (`test_def616__every_shipped_sample_maps_itself`,
    # `test_cr025_sample_csv`).
    #
    # **Under the PO ruling of 2026-08-27 the owner IS the master account**, so
    # an operator's `Owner` column is the OWNER and must reach the party record,
    # not the box beside it. Leaving it pointed at free text would keep exactly
    # the defect the ruling exists to close (DEF-650).
    #
    # ⚠⚠ **NOTHING IS LOST FROM A FILE THAT ALREADY HAS AN `Owner` COLUMN**, and
    # that is what makes the re-pointing safe rather than silent: the load
    # writes the operator's string to `owner_manager` AS WELL, as BR-MET-151
    # provenance (`_resolve_owner_ref`). So the same upload that used to fill
    # only the free-text box now fills the free-text box *and* resolves a typed
    # party — a strict addition, on the same column, from the same header.
    "owner": ("owner", "owner name", "owner party", "landlord"),
    # ⚠ BOTH SPACINGS OF `owner/manager`. A header typed by a person is as
    # likely to read `Owner / Manager` as `OWNER/MANAGER`, and an alias table
    # that knows only one of them sends the other to no column at all — which is
    # this defect's own failure mode, one row lower down.
    "owner_manager": (
        "owner/manager",
        "owner / manager",
        "owner_manager",
        "manager",
        "owner name (legacy)",
    ),
    "external_ref": ("legacy_key", "external_ref", "external reference", "gis ref", "legacy id"),
    "status": ("status",),
    # ── CR-058 W3 · BR-MET-1030 — the owner's identity, auto-detected ──────
    # ⚠ **NO ALIAS IS A SINGLE COMMON WORD.** `ssn` and `phone` are safe because
    # a premises file has no other use for them, but a bare `id` or `licence`
    # would claim a column that means something else on somebody's spreadsheet —
    # and a wrongly-claimed identity column files a government identifier
    # against the wrong party. A header this table does not know is offered
    # unmapped, which is the honest outcome (`DEF-616`'s own lesson).
    "owner_kind": ("owner_kind", "owner kind", "owner type", "person or company"),
    "owner_ssn": ("owner_ssn", "owner ssn", "ssn", "social security", "social security number"),
    "owner_driving_licence": (
        "owner_driving_licence",
        "owner driving licence",
        "owner driving license",
        "driving licence",
        "driving license",
        "drivers license",
        "dl",
    ),
    "owner_phone": ("owner_phone", "owner phone", "owner telephone", "owner contact number"),
    "owner_tax_id": ("owner_tax_id", "owner tax id", "tax id", "tax_id", "ein", "vat number"),
    "owner_account_type": (
        "owner_account_type",
        "owner account type",
        "owner_acct_type",
        "account type",
    ),
    # ⚠ **`DEF-MET-5803` — NO BARE `email`.** The note at the head of this
    # block applies with full force: a premises file's bare `email` column is
    # as likely to be the site contact, the property manager or the tenant as
    # the owner, and a wrongly-claimed contact column mails somebody else's
    # bill. Every alias here says OWNER.
    "owner_email": ("owner_email", "owner email", "owner e-mail", "owner email address"),
    # ⚠ **NO BARE `category`.** A premises file's `category` column is as
    # likely to be the PROPERTY's classification as the owner's, and claiming it
    # wrongly would file every address under a party type nobody chose. The
    # head of this block gives the general reason; this is the column it bites
    # hardest on, because the value is written into a party record.
    "owner_category": (
        "owner_category",
        "owner category",
        "owner type category",
        "owner classification",
    ),
    # ⛔ **DEF-616 — THE SHIPPED SAMPLE STOPPED MAPPING ITSELF.** `premises.lat`
    # / `.lng` arrived with CR-028 AST-W5 (migration 0018, §10-D6). The offered
    # set is derived FROM THE MODEL (BR-MET-088) and `sample_csv` is derived
    # from the offered set, so both columns appeared in the downloadable sample
    # the same day — and this table, which is hand-maintained, did not move. So
    # the one file a first-time operator is told to start from arrived with two
    # headers stage 1 could not recognise: `set(detected) == set(header)` failed
    # with *"Extra items in the right set: 'lat', 'lng'"*, and an operator would
    # have had to map two columns by hand on the product's OWN sample.
    # ⚠ NO GEO SYNONYM BEYOND THE OBVIOUS ONES: `x`/`y` are a projection's axes,
    # not a lat/lng pair, and guessing which is which is how a premises lands in
    # the wrong hemisphere. A header this table does not know is simply offered
    # unmapped, which is the honest outcome.
    "lat": ("lat", "latitude"),
    "lng": ("lng", "lon", "long", "longitude"),
    "created_at": CREATED_ALIASES,  # `DEF-MET-10164`
}

#: ── THE UNITS TARGET (`BR-MET-096`) ────────────────────────────────────────
#: field name → label / kind / required, for `metering.Unit`. Same contract as
#: the premises table above: it decides how an offered column is PRESENTED and
#: PARSED, never which columns are offered — the model decides that
#: (BR-MET-088).
UNITS_FIELD_OVERRIDES: dict[str, dict[str, Any]] = {
    "created_at": _created_column("unit"),
    "premises": {"label": "Parent premise", "kind": KIND_PREMISE_REF, "required": True},
    # ⚠ **THE CITY'S KEY, SO IT GETS A HUMAN LABEL** — `DEF-MET-5802`'s
    # premises half, one noun along: this column is kept and
    # `gis_point_id_was` retired beside it, so it should not go on wearing a
    # heading generated from its field name.
    "gis_point_id": {
        "label": "GIS point ID",
        "help": "The point identifier your city or county assigns this unit.",
        "sample": "",
    },
    # ⛔ **CR-046 C3 — same change of meaning, one noun along.** ⚠ AND READ
    # THE MODEL'S OWN `Meta.constraints` BEFORE TOUCHING THIS: a unit's
    # IDENTITY is `(premises, label)`, which is NOT NULL and unique, while
    # `unit_no` is unique only WHEN PRESENT. So this column is the strongest
    # statement an operator can make, never the only one available — which is
    # exactly why `_key_of` tries it first and falls back to the composite.
    "unit_no": {"label": "Unit number (existing only)", **_issued_number_column("Unit", "Unit")},
    #: CR-046 C5 — the column did not exist on `units` at all until migration
    #: 0042 (BR-MET-404). The offered SET is derived from the model, so adding
    #: the field is what offers the column; this entry only presents it.
    "external_ref": _legacy_ref_column("Unit"),
    "label": {"label": "Unit label", "required": True},
    "unit_type": {"label": "Unit type", "kind": KIND_LOOKUP},
    "floor_label": {"label": "Floor"},
    # `DEF-962`'s ruling again — see the note beside the premises pair.
    "lat": {"label": "Lat", "sample": ""},
    "lng": {"label": "Lng", "sample": ""},
    "square_feet": {"label": "Floor area (sq ft)", "kind": KIND_INTEGER},
    # ⚠ **`DEF-771` — THE COLUMN SAYS WHICH IT TAKES, ON THE SCREEN THAT ASKS
    # FOR IT.** It is labelled *Plan* and its aliases are `plan`, `plan_code`,
    # `rate_plan`, `rate plan`, `tariff`, `plan code` — three of those are the
    # words for a plan's NAME, and the matcher behind it held CODES only. A
    # utility's 9,881-row file said `city customer plan` in every cell, mapped
    # clean, showed `Matched`, and loaded 9,881 units with no plan. The matcher
    # takes both now; this sentence is the half that stops an operator having
    # to find that out from a receipt.
    "rate_plan": {
        "label": "Plan",
        "kind": KIND_PLAN_REF,
        "help": (
            "The plan's ID/CODE **or** its LABEL/NAME — either one, and upper "
            "or lower case makes no difference. You never have to look up an "
            "ID to write an import file. Only a PUBLISHED plan can be "
            "assigned: a draft or an archived plan is named back to you rather "
            "than used. A cell naming no plan — or naming one we do not "
            "recognise — leaves the unit UNPLANNED and flagged, which is "
            "allowed: the address is structure, the plan is pricing you can "
            "add later."
        ),
    },
    "plan_effective_from": {"label": "Plan effective from", "kind": KIND_DATE},
    "plan_locked": {"label": "Plan locked", "kind": KIND_BOOLEAN},
    "vacant_standby_auto": {"label": "Vacant standby", "kind": KIND_BOOLEAN},
    # ⚠ **A BOOLEAN COLUMN THAT WAS OFFERED AS FREE TEXT (CR-036).** The
    # offered SET is derived from the model (BR-MET-088) and this table decides
    # only how an offered column is PRESENTED AND PARSED — so a column missing
    # from it is offered as `KIND_TEXT`, and `is_common_area` is a
    # `BooleanField`. A file that mapped it (the PO's units export did, and the
    # stage-2 screen marked it `Matched`) sent the string `yes` into
    # `Unit(is_common_area="yes")`, which raises `ValidationError: "yes" value
    # must be either True or False` — and because stage 4 is ONE transaction,
    # that is not one bad row, it is the whole 9,881-row load failing with a
    # message about a value nobody typed. BR-MET-101 is the rule behind the
    # column ("3 + common"); it takes yes/no like the other two.
    "is_common_area": {"label": "Common area", "kind": KIND_BOOLEAN},
}

#: Header aliases for r10's own units sheet (`WFL-01.units.2`), and the FOUR of
#: its ten columns this product deliberately does not offer. Each absence has a
#: reason and none of them is an oversight:
#:
#:   * `METER_E` / `METER_W` → **PO ruling 2026-08-21**: *"we will not add meter
#:     or asset here when we are uploading units. When we upload assets at that
#:     time Units will be in system"*. A units import that linked meters would
#:     be doing the assets import's job one wave early, and BR-MET-093 says the
#:     bulk path creates no meter. **Do not add an alias for either.**
#:   * `OCCUPANT` → there is no occupant column on `units`, and there is no
#:     `unit_occupancies` table in this build.
#:   * `STATUS` (occupancy) → `units` has **no occupancy column by design** —
#:     unit status is COMPUTED for display (models.py: *"a settable column would
#:     violate the rule"*), so a mapping target would be a column that cannot be
#:     written. BR-MET-088 forbids offering it.
#:   * `ROUTE` → a read route attaches to a meter, not to a unit, so there is
#:     nothing on `Unit` to map it onto.
#:
#: r10 draws all four and we honour none: that is the stated-absence discipline
#: applied to a dropdown, exactly as `UNIT_CNT` is for premises.
UNITS_ALIASES: dict[str, tuple[str, ...]] = {
    "premises": (
        "premise_id",
        "premise",
        "premise_no",
        "premises",
        "property id",
        "parent premise",
    ),
    # `DEF-MET-10164` — `unit no` / `unit id`, for the dates-only file (see
    # the premises twin above).
    "unit_no": ("unit_no", "unit number", "unit_number", "unit no", "unit id"),
    "label": ("unit_ref", "unit", "unit label", "label", "apt", "apartment"),
    "unit_type": ("unit_type", "unit type", "type"),
    "floor_label": ("floor", "floor_label", "level"),
    "square_feet": ("sqft", "sq ft", "square_feet", "square feet", "area_sqft"),
    "rate_plan": ("plan", "plan_code", "rate_plan", "rate plan", "tariff", "plan code"),
    "plan_effective_from": ("plan_from", "plan_effective_from", "plan start", "effective_from"),
    # ⛔ **DEF-616, SECOND INSTANCE — FOUND BY ITS OWN GUARD, NOT BY THE ROW.**
    # The defect was filed about `premises.lat`/`.lng`; the guard written for it
    # walks EVERY target's shipped sample, and the `units` sample turned out to
    # ship three more headers this table had never learned:
    # *"the shipped `units` sample ships 11 column(s) and stage 1 cannot
    # recognise ['plan_locked', 'vacant_standby_auto', 'is_common_area']"*.
    # Identical mechanism — the offered set is derived from the MODEL
    # (BR-MET-088), this table is hand-kept, and three boolean columns arrived
    # over time without it. Each is its own alias plus the words an operator's
    # own export would plausibly use for it; nothing here is a guess about
    # MEANING, only about spelling.
    "plan_locked": ("plan_locked", "plan lock", "locked", "plan locked"),
    "vacant_standby_auto": (
        "vacant_standby_auto",
        "vacant standby",
        "standby",
        "auto standby",
    ),
    "is_common_area": ("is_common_area", "common area", "common_area", "common"),
    "created_at": CREATED_ALIASES,  # `DEF-MET-10164`
}

#: Transforms r10 names, and whether this product can honour them. A transform
#: it cannot is NOT OFFERED and carries its reason — the stated-absence
#: discipline (G38/DEF-421), applied to a dropdown. (Declared ABOVE the assets
#: column sets because their entries read it at import time.)
TRANSFORMS_BY_KIND: dict[str, tuple[str, ...]] = {
    KIND_TEXT: ("trim_whitespace", "title_case", "uppercase"),
    KIND_BOOLEAN3: ("three_state",),
    KIND_LOOKUP: ("code_table_lookup",),
    KIND_AREA: ("code_table_lookup",),
    # DEF-1088 — an owner NAME is the customer's own text, so the same three
    # tidying transforms a text column offers. It gets NO `code_table_lookup`:
    # the owner is matched by NAME against a party table, not mapped through a
    # code table, and offering one would suggest a mapping screen that does not
    # exist.
    KIND_OWNER_REF: ("trim_whitespace", "title_case"),
    KIND_LIST: ("split_on_comma",),
    KIND_ENUM: ("trim_whitespace",),
    # CR-058 W3 — trim only. `title_case` on `person`/`company` would ship
    # `Person`, which the seam then lowercases anyway; offering a transform
    # that changes nothing is a control that lies about what it does.
    KIND_OWNER_KIND: ("trim_whitespace",),
    KIND_CUSTOM: ("trim_whitespace", "title_case", "uppercase"),
}


# ═══════════════════════════════════════════════════════════════════════════
# CR-058 W3 · BR-MET-1030 — THE OWNER'S IDENTITY COLUMNS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **PO RULING 2026-09-01, VERBATIM:** *"If owner name is given and one
# identify given - DL, SSN, Phone or Tax ID - then you create master account and
# Customer ID - otherwise dont create anything"*.
#
# ⚠ **THE COLUMNS DID NOT EXIST, AND THAT IS WHY THIS BLOCK IS HERE RATHER THAN
# IN `PREMISES_FIELD_OVERRIDES` ABOVE.** The premises target is DERIVED from the
# model (`BR-MET-088`: the picker cannot offer a column with nothing behind it),
# and NONE of these is a column of `premises`. They are facts about a PARTY,
# carried on the premises row for the length of one run and written to
# `customers` through the seam — so they are declared as VIRTUAL columns,
# appended to the derived set by `target_columns`, and every one of them is in
# `_NOT_A_COLUMN` so it can never reach `Premises(**record)`.
#
# ⚠ **ADDING A COLUMN TO A PUBLISHED TEMPLATE IS SOMETHING THE UTILITY SEES.**
# The sample CSV is derived from the offered set, so the file a first-time
# operator downloads gains six headers the day this lands, and a mapping
# template saved before today still maps itself — every one of these is
# OPTIONAL, and a file that carries none of them behaves exactly as it did
# yesterday. That is the compatibility guarantee and it is the reason none of
# them is `required=True`.
#
# ⚠ **`owner_account_type` IS NOT IDENTITY AND IS NOT OPTIONAL-BY-ACCIDENT.**
# `create_master_account` refuses a missing account type BY NAME, because the
# consumer category is what the bill is priced and reported by. Guessing
# `residential` for a builder's site is a money decision taken by a shrug, so a
# row naming an owner and an identifier and NO account type creates nothing and
# is flagged — the same posture as the name-only row, for a different missing
# fact. `PRM.OWNER_ACCOUNT_TYPE_MISSING` says so on the operator's own file.


#: "this column declares no sample of its own" — distinct from declaring `""`.
#: ⚠ **THE THREE STATES ARE NOT TWO, AND COLLAPSING THEM COST A SHIPPED
#: SAMPLE.** `sample_csv`'s `cell()` tests `if "sample" in entry` BEFORE its
#: kind-aware branches, so a column that declares `""` never reaches them —
#: which is exactly what `DEF-962` wants for `owner_ssn`. The two LOOKUP
#: columns need the opposite: no declaration at all, so the tenant's own
#: `seed_codes` answer is used. With one default for both, `Owner account type`
#: and `Owner category` shipped EMPTY while the index behind them was full.
_SAMPLE_FROM_KIND: Any = object()


def _premises_owner_column(
    target: str,
    label: str,
    kind: str = KIND_TEXT,
    *,
    help_text: str,
    blank_means: str = "no owner account is created from this row",
    sample: Any = _SAMPLE_FROM_KIND,
) -> dict[str, Any]:
    """One virtual owner-identity column.

    ⛔ **THE BLANK DEFAULT IS `DEF-962`'s RULING AND IT IS NARROWED HERE, BY
    WHAT `DEF-962` WAS ACTUALLY ABOUT.** This docstring read *"EVERY ONE SHIPS
    `sample=""` — a worked cell here would be an invented Social Security
    number in a file a utility hands to its staff"*. **The reason is right and
    the blanket was wrong**, and the cost was measured: the shipped sample said
    `person` in the owner-kind cell and left the other eight empty, so the one
    file a utility is handed to copy **modelled the exact failure the PO
    reported** — owner details supplied, no master account generated. An
    operator reads a sample to learn what goes in each column; one committing
    cell beside eight empty ones teaches that the rest are decorative, and is
    worse than all-blank because the section looks demonstrated.

    **So the row is now self-consistent and EARNS an account**, and every cell
    in it is either the product's own vocabulary, the tenant's own lookup, or
    unmistakably fictional:

      * the KIND, whose two values are ours rather than somebody's data;
      * the PHONE, as the one identifier a person can be created from that is
        **not a government identifier** — in the `555-01xx` range reserved for
        fiction. `owner_ssn` and `owner_driving_licence` stay BLANK, which is
        `DEF-962`'s reason honoured rather than overridden: those two are the
        invented-government-identifier case in as many words;
      * the ACCOUNT TYPE and CATEGORY, read from **this tenant's own lookups**
        (`sample_csv`'s `seed_codes`), because a sample naming a code the
        tenant does not hold would ship the resolve-to-nothing bug as an
        instruction;
      * the EMAIL, at `example.test`, a domain reserved by RFC 2606 and so
        incapable of being anybody's.

    ⚠ **THE NAME IS NOT HERE** — it is a column of the model, and its cell is
    built in `sample_csv`'s `KIND_OWNER_REF` branch from the tenant's own first
    owner when there is one.
    """
    return {
        "target": target,
        "label": label,
        "kind": kind,
        "required": False,
        "transforms": list(TRANSFORMS_BY_KIND.get(kind, ())),
        **_owner_sample(kind, sample),
        "help": help_text,
        # The picker draws this beside the column, so an operator who leaves it
        # empty is told what they are choosing rather than finding out on the
        # receipt.
        #
        # ⚠ **PER COLUMN SINCE `DEF-MET-5803`, AND IT HAD TO BECOME ONE.** Every
        # column in this block used to say *"no owner account is created from
        # this row"*, which is true of the IDENTITY columns and FALSE of
        # `owner_email`: a blank email still creates the account, it just
        # leaves nobody to send anything to. A sentence that is wrong on one
        # column is worse than no sentence, because the operator acts on it.
        "blank_means": blank_means,
    }


def _owner_sample(kind: str, sample: Any) -> dict[str, Any]:
    """The `sample` key for one owner column, or NO KEY AT ALL.

    ⚠ **THE DEFAULT IS STILL BLANK AND THE BLANKET IS GONE.** `owner_ssn` and
    `owner_driving_licence` declare `""` — `DEF-962`'s reason honoured exactly,
    because a worked cell there is an invented government identifier in a file
    a utility hands to its staff. The owner KIND keeps `person`, whose two
    values are the product's own vocabulary. The phone and the email declare
    cells that invent nothing (a reserved `555` number, a reserved
    `example.test` domain).

    ⛔ **AND A LOOKUP COLUMN DECLARES NOTHING, WHICH IS THE THIRD STATE.**
    `sample_csv`'s `cell()` reads `if "sample" in entry` before its kind-aware
    branches, so declaring `""` here would SHADOW the tenant's own `seed_codes`
    answer — and did: `Owner account type` and `Owner category` shipped empty
    while the indexes behind them held eight codes and five. Omitting the key
    is what lets the tenant's own lookup supply the cell.
    """
    if sample is not _SAMPLE_FROM_KIND:
        return {"sample": str(sample)}
    if kind == KIND_LOOKUP:
        return {}
    return {"sample": "person" if kind == KIND_OWNER_KIND else ""}


PREMISES_OWNER_COLUMNS: tuple[dict[str, Any], ...] = (
    _premises_owner_column(
        "owner_kind",
        "Owner is a person or a company",
        KIND_OWNER_KIND,
        help_text=(
            "A person is identified by a Social Security number, a driving "
            "licence or a phone; a company by its Tax ID. Leave it empty and "
            "the address still loads — nobody is created for it."
        ),
    ),
    _premises_owner_column(
        "owner_ssn",
        "Owner Social Security number",
        help_text="For a person. Stored encrypted; only the last four ever appear on screen.",
    ),
    _premises_owner_column(
        "owner_driving_licence",
        "Owner driving licence",
        help_text="For a person. Stored encrypted; only the last four ever appear on screen.",
    ),
    _premises_owner_column(
        "owner_phone",
        "Owner phone",
        help_text="For a person. Enough on its own to create a customer number.",
        # ⚠ **THE ONE IDENTIFIER THIS SAMPLE CAN WORK WITHOUT INVENTING A
        # GOVERNMENT NUMBER.** `555-01xx` is the range reserved for fiction, so
        # it cannot be anybody's; and this column is enough on its own to
        # create a person, which is what makes the shipped row EARN an account
        # rather than demonstrate the reported failure.
        sample="555-0142",
    ),
    _premises_owner_column(
        "owner_tax_id",
        "Owner Tax ID",
        help_text="For a company, and the only identifier a company is created from.",
    ),
    _premises_owner_column(
        "owner_account_type",
        "Owner account type",
        KIND_LOOKUP,
        help_text=(
            "What the owner's account is priced and reported as — the same "
            "list the Accounts upload uses. Without it no owner account is "
            "created, because nothing may guess what a customer is charged as."
        ),
    ),
    # ⛔ **THE OWNER CATEGORY — PO RULING 2026-09-19, VERBATIM: *"Yes add owner
    # category column in csv template"*.**
    #
    # ⚠ **THIS IS NOT A REVERSAL OF `BR-MET-151` CLAUSE 3 — IT IS THE THING
    # CLAUSE 3 LEAVES ROOM FOR.** Clause 3 forbids READING a category off a
    # name: *Whitfield Rentals LLC* is not proof of a landlord. It has never
    # forbidden the operator from STATING one. The import was refused a guess
    # and then never given the chance to be told, so on a first migration — when
    # nobody is on file — every row created a master account with no owner party
    # attached and the name in the legacy box only.
    #
    # ⚠ **A BLANK CELL BEHAVES EXACTLY AS IT DID BEFORE THIS COLUMN EXISTED.**
    # No default, no guess: the address loads, the owner account is still
    # created, and the party is left for a person to type on `PRM-04`. That is
    # today's behaviour, and it must stay reachable — a utility that does not
    # know its categories yet has to be able to load its addresses.
    # `PRM.OWNER_CATEGORY_MISSING` says so at rehearsal, on their own file.
    #
    # ⚠ **THE FIVE ARE THE TENANT'S AND ARE NOT NAMED HERE.**
    # `owner_occupier`, `landlord`, `property_manager`, `hoa` and `builder` are
    # SEEDED into an editable Settings lookup, so a tenant may rename, retire or
    # add. `premises_owners._resolve_category` reads that table and refuses an
    # unknown or retired code BY NAME. Hardcoding the five here would be a
    # second opinion about a list somebody else owns, and it would go stale the
    # first time a utility edited it.
    _premises_owner_column(
        "owner_category",
        "Owner category",
        KIND_LOOKUP,
        help_text=(
            "What kind of owner this is — the list on Settings, such as "
            "Landlord or Property manager. With it, the owner record is "
            "created and linked to this address; without it the address still "
            "loads and someone types the owner later."
        ),
        blank_means="the address loads and the owner record is left for someone to type",
    ),
    # ⛔ **`DEF-MET-5803` — CONTACT, AND DELIBERATELY NOT IDENTITY.** It is LAST
    # in this block so the six identity columns stay together and this one
    # reads as the different thing it is.
    #
    # ⚠ **IT MUST NEVER JOIN `OWNER_IDENTIFIER_COLUMNS`.** The PO's ruling of
    # 2026-09-01 names the evidence that creates a party — *"DL, SSN, Phone or
    # Tax ID"* — and an email is not on that list. Adding it there would let a
    # name-and-email row mint a Customer #, which reverses a signed ruling with
    # a one-line edit; `test_def_met_5802_declared_columns.py` asserts a
    # name-plus-email row is still `awaiting_identity`.
    _premises_owner_column(
        "owner_email",
        "Owner email",
        help_text=(
            "Where this owner's bill and portal invitation go. It is not an "
            "identifier — an owner is still created from a driving licence, a "
            "Social Security number, a phone or a Tax ID."
        ),
        blank_means="the owner account is still created, with no way to contact it",
        # `example.test` is reserved by RFC 2606 and can never be a real
        # mailbox — the same posture as the `555` number above.
        sample="sample.owner@example.test",
    ),
)

#: target → the virtual columns appended to its DERIVED set. Premises only
#: today; a dict rather than an `if` because `BR-MET-096` is explicit that one
#: runner serves every target and a branch on the target name is how the
#: seventh one starts diverging.
VIRTUAL_COLUMNS_BY_TARGET: dict[str, tuple[dict[str, Any], ...]] = {
    TARGET_PREMISES: PREMISES_OWNER_COLUMNS,
}

#: Just the names, for the strip and for the counters.
PREMISES_OWNER_COLUMN_NAMES: tuple[str, ...] = tuple(
    entry["target"] for entry in PREMISES_OWNER_COLUMNS
)



# ═══════════════════════════════════════════════════════════════════════════
# THE ASSETS TARGETS (CR-028 AST-W3 — B16 §4.7b's field maps, verbatim)
# ═══════════════════════════════════════════════════════════════════════════
#
# EXPLICIT declarations, not `_meta`-derived — see the note on ASSETS_TARGETS.
# Each entry carries its stage-1 SAMPLE cell (CR-025: header + one worked row);
# tenant-specific references (units, premises, parents) sample EMPTY, never
# guessed — a blank unit is itself the worked BR-AST-045 case.


def _asset_column(
    target: str,
    label: str,
    kind: str = KIND_TEXT,
    *,
    required: bool = False,
    sample: str | None = None,
    blank_means: str | None = None,
    help_text: str | None = None,
) -> dict[str, Any]:
    """⚠ **`sample=None` IS NOT `sample=""` AND THE DIFFERENCE IS `DEF-962`.**

    This helper used to default `sample` to `""` and write the key
    UNCONDITIONALLY. `sample_csv`'s `cell()` reads that key FIRST, so every
    declared column short-circuited the kind-aware worked-value logic below it
    — and the three columns whose whole purpose is to attach a device to a
    place (`unit_ref` on all three targets, `parent_asset_no` on sub-meters,
    `premises` on devices) shipped EMPTY in the downloadable template, because
    none of them declares a sample of its own.

    The PO read the file and reported the column as missing: *"you dont have
    Unit field in CSV file that is downloaded; when you upload assets you iwll
    need Units field mapping"*. It was there, named `unit_ref`, with nothing
    in it — and BR-AST-045 makes a blank unit LAWFUL, so a file built from
    that template rehearses clean and loads every meter into inventory.

    So the key is now written only when a sample was actually DECLARED. A
    column that declares `sample=""` on purpose (the accounts target's
    `closed_at`, `tax_exempt_ref`) still ships blank; a column that declares
    nothing falls through to the kind, which is where the tenant's own worked
    values are read.
    """
    entry: dict[str, Any] = {
        "target": target,
        "label": label,
        "kind": kind,
        "required": required,
        "transforms": list(TRANSFORMS_BY_KIND.get(kind, ())),
    }
    if sample is not None:
        entry["sample"] = sample
    if blank_means is not None:
        entry["blank_means"] = blank_means
    if help_text is not None:
        # ⛔ **`DEF-1077` — WHAT THIS COLUMN TAKES, IN THE OPERATOR'S WORDS.**
        # The served key is `help`, the same one `UNITS_FIELD_OVERRIDES`
        # already uses for the `Plan` column (DEF-771) and the same one stage 2
        # already renders — so this is a column DECLARING what the screen
        # already knows how to say, not a new surface.
        entry["help"] = help_text
    return entry


def _asset_number_column(noun: str) -> dict[str, Any]:
    """⛔ **THE `asset_no` COLUMN CHANGED MEANING ON 2026-08-27, AND THE HEADER
    CHANGED WITH IT** (PO verbatim: *"here we should not allow usse to fill in
    Asset ID - we have number system set in the settings, we shoudl call that
    function and get unique number and assign it"* — decision log, *A METER
    NUMBER IS ALLOCATED FROM THE TENANT'S SERIES, NEVER TAKEN FROM AN UPLOADED
    FILE*, plus its same-day ADDENDUM).

    It used to be *"the number to give this meter"*, sampled `M-9001`, and a
    blank fell through to the series. It is now *"an EXISTING number, if this
    row updates a meter already in SMARTBillHub — blank for a new one"*, and
    **blank is the normal case and the only case in Insert mode.**

    ⚠ **THE COLUMN IS NOT DELETED, AND THE ADDENDUM IS WHY.** It has a second
    job the ruling must not take with it: it is the MATCH KEY for
    *Insert & update* (`_eval_unit_service_free` compares a seat's current
    holder to the row's own number, so a correction re-run reads as an update
    of the holder rather than a second meter on the seat). `serial_no` cannot
    take that job — BR-AST-033 makes a duplicate serial warn-but-allow, so it
    is not unique — while `asset_no` is `UNIQUE (tenant, asset_no)`.

    ⚠ **THE SAMPLE CELL IS `""`, DELIBERATELY AND NOT BY OMISSION (`DEF-962`).**
    `sample=None` would fall through to the kind-generic worked value and ship
    `Sample Meter number` in the downloadable template — an invented number, on
    the very column the PO objected to being asked to invent. An explicitly
    declared empty sample ships the cell BLANK, which is what a new meter's row
    should look like.
    """
    return _asset_column(
        "asset_no",
        f"{noun} number (existing only)",
        sample="",
        blank_means="a new number is issued from your numbering settings",
        help_text=(
            f"LEAVE THIS BLANK for a new {noun.lower()} — SMART360 Next issues "
            f"the number from Settings › Numbering › {noun}, so it can never "
            "collide with one already in use or arrive in a shape your "
            f"settings would not produce. Fill it in ONLY to update a "
            f"{noun.lower()} already on file, quoting the number this system "
            "shows on its own screen. Your old system's number goes in "
            "External reference, and the manufacturer's number goes in "
            "Serial number."
        ),
    )


def _assets_external_ref_column(noun: str) -> dict[str, Any]:
    """**`BR-AST-049` — WHERE THE UTILITY'S OWN NUMBER GOES NOW THAT `asset_no`
    NO LONGER TAKES IT** (decision log 2026-08-27, "THE ONE CONSEQUENCE,
    DECIDED HERE RATHER THAN ASKED").

    A utility migrating from an old system holds its own meter reference — not
    the manufacturer's serial, the number its previous software printed on
    every work order. Under the ruling that reference had nowhere to go and
    would have been **lost at import**. `customers` already solved exactly this
    (`external_ref`, BR-CUS-054), so this is that column on the same name.

    ⚠ It is NOT overloaded onto `serial_no`: a utility's own number and a
    manufacturer's serial are different facts, and a column that holds either
    means neither.

    ⚠ **AND IT IS A LAWFUL MATCH KEY**, because it is `UNIQUE (tenant,
    external_ref)` case-insensitively (`uq_assets_tenant_external_ref_ci`) —
    which matters on the FIRST migration, where the operator's corrected re-run
    holds no SMARTBillHub number to quote. `_key_of` falls back to it.
    """
    return _asset_column(
        "external_ref",
        "External reference",
        sample="",
        blank_means="nothing to reconcile against your old system",
        help_text=(
            f"YOUR OWN number for this {noun.lower()} — the id your previous "
            "system used. It is kept so you can reconcile the two lists after "
            "the migration, and so a corrected re-run of this same file "
            "updates the rows it created instead of duplicating them. It is "
            "unique within this utility, and it is neither the manufacturer's "
            "serial number nor the number SMART360 Next issues."
        ),
    )


# ⛔⛔ **THE THREE ASSET SHEETS, IN THE PO-CONFIRMED ORDER (2026-09-30).**
#
# PO verbatim on the regrouped tables: *"Meters: 19 columns in 6 groups +
# Sub-meters: 21 columns in 6 groups + Behind the meter (devices): 19 columns
# in 6 groups - these are all correct + all these tasks are good"*, and on the
# downloads the same day: every DOWNLOADED file follows this order — the
# template, the sample, the failures file and the result file. The tables are
# `04-docs/05-modules/05-assets/12-asset-upload-fix-plan.md`; the code below is
# them, row for row, and `tests/test_ast_upload_fix_u12.py` pins the order so a
# column added out of place fails.
#
# ⚠ **EACH COLUMN CARRIES ITS GROUP, ITS MODE AND WHETHER IT MOVES A BILL.**
#   * `group`   — Identity · Location · Service and billing · Meter/Device
#                 details · Dates · Purchase, the same six on every sheet.
#   * `mode`    — `match` (finds the existing asset; blank = create) ·
#                 `insert_only` (set on create, never by a re-upload — moving an
#                 asset is the Reassign screen) · `insert_update` (set on create
#                 and OVERRIDDEN by a re-upload, PO: *"we need to override it in
#                 case of upload"*).
#   * `billing` — 💲: changing it changes the next bill. A re-upload that
#                 changes one is audited old → new, applies forward only
#                 (BR-AST-012 — stored reads and issued invoices never restate),
#                 and is listed per asset in the result file.
#
# ⚠ **ONE REQUIRED COLUMN ON METERS, TWO ON SUB-METERS AND DEVICES** (PO:
# *"only have 1 or 2 or 3 as required rest will be options"*): meters Service ·
# sub-meters Parent / master meter, Service · devices Device type, Service —
# each the minimum a row cannot be placed or billed without.
GROUP_IDENTITY = "identity"
GROUP_LOCATION = "location"
GROUP_SERVICE_BILLING = "service_billing"
GROUP_DETAILS = "details"
GROUP_DATES = "dates"
GROUP_PURCHASE = "purchase"
#: The six groups, in the order every asset sheet prints them.
ASSET_COLUMN_GROUPS: tuple[str, ...] = (
    GROUP_IDENTITY,
    GROUP_LOCATION,
    GROUP_SERVICE_BILLING,
    GROUP_DETAILS,
    GROUP_DATES,
    GROUP_PURCHASE,
)
MODE_MATCH = "match"
MODE_INSERT_ONLY = "insert_only"
MODE_INSERT_UPDATE = "insert_update"
# The allocation-rule vocabulary and the 4–10 register-digit bound live ONCE,
# in `import_rules` (`allocation_rule_code`, `REGISTER_DIGITS_RANGE`), because
# stage 3 judges with them and the load writes with them (DEF-544).


def _placed(
    entry: dict[str, Any], group: str, mode: str = MODE_INSERT_UPDATE, *, billing: bool = False
) -> dict[str, Any]:
    """One column, stamped with its plan-table group, mode and 💲 flag."""
    return {**entry, "group": group, "mode": mode, "billing": billing}


def _uom_column(label: str = "Unit of measure") -> dict[str, Any]:
    """The asset's own unit (hard rule 3: a quantity always carries one).

    ⚠ **A LOOKUP AGAINST THE TENANT'S UoM LIST, JUDGED AGAINST THE ROW'S OWN
    SERVICE** (`AST.UOM_FOR_SERVICE`): `kWh` on a water meter is a unit this
    utility has and the wrong one for this row. Blank takes the service's
    default unit (`tenancy.services.SERVICE_DEFAULT_UOMS` — PO 2026-09-30).
    """
    return _asset_column(
        "unit",
        label,
        KIND_LOOKUP,
        blank_means="the service's default unit",
        help_text=(
            "The unit this asset is measured or sized in — kWh, kgal, cart, "
            "kW, Mbps, ton. Leave it blank and the service's own unit is used."
        ),
    )


def _register_digits_column() -> dict[str, Any]:
    return _asset_column(
        "register_digits",
        "Register digits",
        KIND_INTEGER,
        sample="9",
        blank_means="9 digits",
        help_text="How many digits the register shows — 4 to 10. Blank means 9.",
    )


def _size_column(label: str, help_text: str) -> dict[str, Any]:
    """⛔ BR-MET-530 — the size, CHOSEN from the tenant's list, never typed
    (`BR-TEN-171` ratifies forty codes and a typo would add a forty-first).
    ⚠ **NO `sample=`** — the worked cell is derived in `sample_csv` from THIS
    tenant's list for the SAME service the sample row names (`DEF-963`).
    ⚠ **AND FROM 2026-09-30 THE SIZE MUST BELONG TO THE ROW'S OWN SERVICE**
    (`AST.SIZE_FOR_SERVICE`, plan U4): a 2" fire line on a trash cart is a size
    the utility has and the wrong one for this row."""
    return _asset_column(
        "size_class",
        label,
        KIND_LOOKUP,
        blank_means="no size recorded — a per-size rate ladder cannot price this asset",
        help_text=help_text,
    )


_METER_SIZE_HELP = (
    "The size of the SERVICE CONNECTION this meter sits on — "
    'a 5/8" water tap, a 1φ 100A electric service — chosen from '
    "the sizes on your Reference data list for this meter's service. It is "
    "what a per-size rate ladder prices off, so a wrong one changes the bill. "
    "Leave it blank if you do not know it yet: the meter still "
    "loads, and a schedule that prices by size will say so by name "
    "rather than quietly charging the every-size rate."
)
_DEVICE_SIZE_HELP = (
    "The device's size — a cart size, a fire-line size, a panel size — chosen "
    "from the sizes on your Reference data list for this device's service. "
    "A per-size price is charged off it. Leave it blank if you do not know it "
    "yet: the device still loads, and a per-size price says by name that no "
    "size is recorded."
)
_UNIT_REF_HELP = (
    "The unit's NUMBER (U-00101), or the premises and the unit "
    "together (P-00101 · A), or just the unit label when only "
    "one unit in this utility carries it. Leave it blank and the "
    "meter loads into inventory — on file, but unable to take "
    "a reading or be billed until someone assigns it."
)


def _assets_meter_columns(
    noun: str, type_sample: str, *, submeter: bool = False
) -> list[dict[str, Any]]:
    """The meters (19) and sub-meters (21) sheets, in the plan's order.

    ⚠ **`submeter` IS THE SUB-METER BOUNDARY, EXPRESSED STRUCTURALLY** (PO
    ruling 2026-08-28, kept for sub-meters on 2026-09-30): a sub-meter carries
    NO connection size — it sits behind a service connection rather than on
    one — and gains its master, its allocation and its loss tolerance. The
    offered set IS the template, the field map and the auto-mapper's whitelist
    at once (`_auto_map` skips any alias whose field is not offered), so one
    flag keeps all three honest.

    Kept from before, each for its recorded reason: `serial_no` is on the sheet
    because the 2026-08-27 ruling rests on it (the manufacturer's serial is
    what ties a row to the device on the wall); `service` has NO literal sample
    (`DEF-963` — it comes from the tenant's own enablement); the number column
    ships blank (`DEF-962`, the 2026-08-27 ruling).
    """
    billing = GROUP_SERVICE_BILLING
    columns: list[dict[str, Any]] = [
        _placed(_asset_number_column(noun), GROUP_IDENTITY, MODE_MATCH),
        _placed(_assets_external_ref_column(noun), GROUP_IDENTITY),
        _placed(_asset_column("serial_no", "Serial number"), GROUP_IDENTITY),
        _placed(
            _asset_column(
                "unit_ref",
                "Unit",
                KIND_UNIT_REF,
                blank_means="loads into inventory (BR-AST-045)",
                help_text=_UNIT_REF_HELP,
            ),
            GROUP_LOCATION,
            MODE_INSERT_ONLY,
        ),
    ]
    if submeter:
        # BR-AST-003: a sub-meter REQUIRES its master — unmapped is a stage-2
        # refusal, exactly as an unmapped address is for premises. Insert only:
        # an update never re-hangs a sub-meter (BR-AST-050 (d)).
        columns.append(
            _placed(
                _asset_column(
                    "parent_asset_no", "Parent / master meter", KIND_ASSET_REF, required=True
                ),
                GROUP_LOCATION,
                MODE_INSERT_ONLY,
            )
        )
    columns.append(
        _placed(
            _asset_column("service", "Service", KIND_LOOKUP, required=True),
            billing,
            billing=True,
        )
    )
    if not submeter:
        columns.append(
            _placed(_size_column("Connection size", _METER_SIZE_HELP), billing, billing=True)
        )
    columns.append(_placed(_uom_column(), billing, billing=True))
    columns.append(
        _placed(_asset_column("multiplier", "Multiplier", sample="1"), billing, billing=True)
    )
    if submeter:
        columns.extend(
            [
                _placed(
                    _asset_column(
                        "allocation_share_pct",
                        "Allocation share %",
                        KIND_DECIMAL,
                        blank_means="metered, not allocated",
                    ),
                    billing,
                    billing=True,
                ),
                _placed(
                    _asset_column(
                        "allocation_rule",
                        "Allocation rule",
                        sample="",
                        blank_means="metered, not allocated",
                        help_text=(
                            "How this sub-meter's usage is shared: rubs (share of "
                            "the building's total), sqft (by floor area), equal "
                            "(split equally) or absorb (owner absorbs)."
                        ),
                    ),
                    billing,
                    billing=True,
                ),
                _placed(
                    _asset_column(
                        "loss_tolerance_pct",
                        "Loss tolerance %",
                        KIND_DECIMAL,
                        blank_means="no tolerance set",
                        help_text="How far the master and its sub-meters may differ — 0 to 100.",
                    ),
                    billing,
                ),
            ]
        )
    else:
        columns.append(
            _placed(
                _asset_column(
                    "net_metering",
                    "Net metering",
                    KIND_BOOLEAN,
                    sample="no",
                    blank_means="not net metered",
                    help_text="yes when this meter also records energy sent back to the grid.",
                ),
                billing,
                billing=True,
            )
        )
    columns.extend(
        [
            _placed(
                _asset_column("meter_type", "Meter type", KIND_LOOKUP, sample=type_sample),
                GROUP_DETAILS,
            ),
            _placed(
                _asset_column("read_method", "Read method", KIND_LOOKUP, sample="ami"),
                GROUP_DETAILS,
            ),
            _placed(_register_digits_column(), GROUP_DETAILS),
            _placed(
                _asset_column("manufacturer", "Manufacturer", sample="Sample Meter Co"),
                GROUP_DETAILS,
            ),
            _placed(_asset_column("model", "Model", sample="MX-100"), GROUP_DETAILS),
            _placed(
                _asset_column("install_date", "Install date", KIND_DATE, sample="2026-01-01"),
                GROUP_DATES,
            ),
            _placed(
                _asset_column(
                    "certification_due", "Certification due", KIND_DATE, sample="2027-01-01"
                ),
                GROUP_DATES,
            ),
            _placed(
                _asset_column("warranty_end", "Warranty end", KIND_DATE, sample="2031-01-01"),
                GROUP_DATES,
            ),
            _placed(
                _asset_column("supplier", "Supplier", sample="Sample Meter Co"), GROUP_PURCHASE
            ),
            _placed(
                _asset_column(
                    "purchase_cost", "Purchase cost", KIND_DECIMAL, sample="164.0000"
                ),
                GROUP_PURCHASE,
            ),
        ]
    )
    return columns


#: ⚠ **THE `number_sample` PARAMETER IS GONE (2026-08-27)** and `with_size` is
#: now `submeter` (2026-09-30) — the size is the one billing column the two
#: meter sheets do not share, and the sub-meter extras ride the same flag.
ASSETS_METERS_COLUMNS: tuple[dict[str, Any], ...] = tuple(_assets_meter_columns("Meter", "ami"))

ASSETS_SUBMETERS_COLUMNS: tuple[dict[str, Any], ...] = tuple(
    _assets_meter_columns("Sub-meter", "sub_meter", submeter=True)
)

#: ⛔ **THE DEVICES SHEET GAINS SERVICE, SIZE, UNIT OF MEASURE AND PARENT METER
#: (PO ruling 2026-09-30).** Behind-the-meter devices — carts, fire lines,
#: panels, batteries, modems — are COUNTED or SUMMED on the bill through their
#: SERVICE POINT (`assets.selectors.billable_asset_count`), and until this
#: ruling the sheet could not name a service at all: every uploaded cart loaded
#: with no service point and was never counted (`DEF-AST-8097`). The 2026-08-28
#: *"Sub-meters and devices are OUT"* is SUPERSEDED for devices only.
#: `DEF-AST-8364` — the devices sample's worked row, as (device type, the ONE
#: service it is billed under), in preference order: a backflow preventer on a
#: water connection, a cart on trash, a fire service line on fire (plan U2's
#: three named devices; `apps/assets/services.py` SEED_ASSET_TYPES codes).
SAMPLE_DEVICE_PAIRS: tuple[tuple[str, str], ...] = (
    ("backflow", "water"),
    ("container_cart", "trash"),
    ("fire_line", "fire"),
)

ASSETS_DEVICES_COLUMNS: tuple[dict[str, Any], ...] = (
    _placed(_asset_number_column("Device"), GROUP_IDENTITY, MODE_MATCH),
    _placed(
        _asset_column("type", "Device type", KIND_LOOKUP, required=True, sample="backflow"),
        GROUP_IDENTITY,
        MODE_INSERT_ONLY,
    ),
    _placed(_assets_external_ref_column("Device"), GROUP_IDENTITY),
    _placed(_asset_column("serial_no", "Serial number"), GROUP_IDENTITY),
    _placed(
        _asset_column(
            "premises",
            "Premises",
            KIND_PREMISE_REF,
            blank_means="loads into inventory when the unit is blank too",
        ),
        GROUP_LOCATION,
        MODE_INSERT_ONLY,
    ),
    _placed(
        _asset_column(
            "unit_ref",
            "Unit",
            KIND_UNIT_REF,
            blank_means="the premises' own unit seats it",
            help_text=(
                "The unit's NUMBER (U-00101), or the premises and the unit "
                "together (P-00101 · A), or just the unit label when only one "
                "unit in this utility carries it. Name a premises instead and its "
                "one unit seats the device; leave both blank and it loads into "
                "inventory — on file, but unable to be billed until "
                "someone assigns it."
            ),
        ),
        GROUP_LOCATION,
        MODE_INSERT_ONLY,
    ),
    _placed(
        _asset_column(
            "parent_asset_no",
            "Parent / linked meter",
            KIND_ASSET_REF,
            # ⚠ DECLARED BLANK: optional on a device, and a worked master of
            # another service would fail `AST.PARENT_SAME_SERVICE` on the
            # product's own sample.
            sample="",
            blank_means="not linked to a meter",
            help_text=(
                "The meter this device sits behind, if any — its number, its "
                "serial or your own reference for it. It must measure the same "
                "service as the device."
            ),
        ),
        GROUP_LOCATION,
        MODE_INSERT_ONLY,
    ),
    _placed(
        _asset_column(
            "service",
            "Service",
            KIND_LOOKUP,
            required=True,
            help_text=(
                "The service this device is billed under — trash for a cart, "
                "fire for a fire line. The device's unit must have that service."
            ),
        ),
        GROUP_SERVICE_BILLING,
        billing=True,
    ),
    _placed(_size_column("Size", _DEVICE_SIZE_HELP), GROUP_SERVICE_BILLING, billing=True),
    _placed(
        _uom_column("Unit of measure / capacity unit"), GROUP_SERVICE_BILLING, billing=True
    ),
    _placed(
        _asset_column("export_capacity_kw", "Export capacity (kW)", KIND_DECIMAL),
        GROUP_SERVICE_BILLING,
        billing=True,
    ),
    _placed(
        _asset_column("manufacturer", "Manufacturer", sample="Sample Device Co"), GROUP_DETAILS
    ),
    _placed(_asset_column("model", "Model", sample="DX-10"), GROUP_DETAILS),
    _placed(
        _asset_column("install_date", "Install date", KIND_DATE, sample="2026-01-01"),
        GROUP_DATES,
    ),
    _placed(
        _asset_column(
            "test_interval_months", "Test frequency (months)", KIND_INTEGER, sample="12"
        ),
        GROUP_DATES,
    ),
    _placed(
        _asset_column("certification_due", "Next test due", KIND_DATE, sample="2027-01-01"),
        GROUP_DATES,
    ),
    _placed(
        _asset_column("warranty_end", "Warranty end", KIND_DATE, sample="2029-01-01"),
        GROUP_DATES,
    ),
    _placed(_asset_column("supplier", "Supplier", sample="Sample Device Co"), GROUP_PURCHASE),
    _placed(
        _asset_column("purchase_cost", "Purchase cost", KIND_DECIMAL, sample="247.0000"),
        GROUP_PURCHASE,
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
# THE PARTS TARGET (CR-077 — `Work-025`'s six columns, and only those)
# ═══════════════════════════════════════════════════════════════════════════
#
# EXPLICIT rather than derived, and for a stronger reason than the assets and
# accounts targets have: `parts` is not a model this module may import at all
# (B2 §2 / G6). The set below is `Work-025`'s own register — part number, name,
# category, unit, unit cost — plus `active`, and nothing else. `Part` carries
# `is_system` too and it is deliberately absent: a system part is one the
# PRODUCT ships, and a file that could set the flag would let a utility's own
# spreadsheet claim rows the tenant may not edit.


def _part_column(
    target: str,
    label: str,
    kind: str = KIND_TEXT,
    *,
    required: bool = False,
    sample: str | None = None,
    help_text: str | None = None,
) -> dict[str, Any]:
    """Same contract as `_asset_column` and `_account_column`, and the same
    `DEF-962` rule: the `sample` key exists only when one was DECLARED, so a
    column added here later cannot ship a blank cell in the template by
    omission."""
    entry: dict[str, Any] = {
        "target": target,
        "label": label,
        "kind": kind,
        "required": required,
        "transforms": list(TRANSFORMS_BY_KIND.get(kind, ())),
    }
    if sample is not None:
        entry["sample"] = sample
    if help_text is not None:
        entry["help"] = help_text
    return entry


PARTS_COLUMNS: tuple[dict[str, Any], ...] = (
    # ⚠ **THE PART NUMBER IS THE UTILITY'S OWN AND IT COMES OFF THE FILE**, which
    # is the opposite of the assets targets since the PO's 2026-08-27 ruling.
    # There is no `part` number series — `Work-025` has never issued one — so
    # there is nothing to allocate from and nothing to renumber. It is also the
    # match key, and `work.services._clean_part` already enforces its
    # case-insensitive uniqueness through `uq_parts_tenant_part_no_ci`.
    #
    # ⚠ **SO IT DECLARES HELP, AS `account_no` DOES (`DEF-MET-9264`).** The
    # stage-2 screen draws any column's `help`, and without one an operator
    # who has just been told *leave the number blank* on four other targets
    # has nothing saying this one is the opposite. `test_cr046_e4` asserts it.
    _part_column(
        "part_no",
        "Part #",
        required=True,
        sample="PT-1042",
        help_text="Your own part number. A row without one is rejected.",
    ),
    _part_column("name", "Name", required=True, sample="3/4 in. brass coupling"),
    # A LOOKUP against the tenant's own `part_categories`, resolved by NAME and
    # then by CODE — the same two ways the Add-part screen resolves it, asked of
    # work rather than restated here. A blank is lawful: `_clean_part` writes
    # `category = None` and the register shows the part as uncategorised.
    _part_column(
        "category",
        "Category",
        KIND_LOOKUP,
        sample="Fittings",
        help_text=(
            "One of the categories on your parts register — its name or its "
            "code. Leave it empty and the part loads with no category."
        ),
    ),
    _part_column("unit_of_measure", "Unit", required=True, sample="each"),
    # ⚠ **MONEY, SO FOUR DECIMALS ARE STORED AND TWO ARE SHOWN** (CLAUDE.md hard
    # rule 2). The sample cell carries the stored precision, exactly as the
    # assets targets' `purchase_cost` does, because the file is what a utility
    # types into and the column is `NUMERIC(18,4)`.
    _part_column("unit_cost", "Unit cost", KIND_DECIMAL, sample="12.5000"),
)

# ═══════════════════════════════════════════════════════════════════════════
# THE PAYMENTS TARGET (`P1.1` — a lockbox or store file, six columns)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE COLUMN SET IS THE OWNING MODULE'S WRITER'S SIGNATURE, NOT THE
# TABLE'S** — the general lesson the parts target learned the hard way, applied
# here BEFORE running a file rather than after. `payments` has thirty-odd
# columns; the ones reachable through `payments.import_writer.
# create_payment_from_import` are these six, and a template offering a seventh
# would rehearse clean and reject every row at the write.
#
# ⚠ **AND THE SIX ARE THE LOCKBOX PARSER'S OWN, DELIBERATELY.** `apps/payments/
# lockbox.py::REMITTANCE_COLUMN_ALIASES` has been reading real remittance files
# since CR-059 and its vocabulary is what banks and stores actually emit. The
# aliases below are that table, so a file the retiring pipeline accepted is a
# file this target accepts — a migration that silently narrowed what a utility
# could upload would be the worst possible way to retire a pipeline.
#
# ⚠ **`payer_name` IS OFFERED AND IT CAN NEVER, BY ITSELF, POST MONEY**
# (`P1.12`). It is on the template because it is the only thing a person can
# work a stuck row from, and it is the one column whose successful match is
# still a REVIEW. See `payments.import_writer.match_account`.
#
# WHAT IS DELIBERATELY ABSENT, AND EACH ABSENCE IS A RULE:
#   * **no allocation instruction.** A bill reference is PROVENANCE. Turning a
#     bank's reference field into a staff allocation instruction would override
#     every tenant's `BR-PAY-010` order four hundred times a morning on the
#     strength of what a lockbox operator typed.
#   * **no `status`, no `posted_at` separate from `cleared_at`.** The arrival
#     date is ONE fact (`BR-PAY-033`) and a file that could set the two apart
#     would let a spreadsheet decide lateness.
#   * **no account BALANCE and no `origin`.** Both are ours to write.


def _payment_column(
    target: str,
    label: str,
    kind: str = KIND_TEXT,
    *,
    required: bool = False,
    sample: str | None = None,
    help_text: str | None = None,
) -> dict[str, Any]:
    """Same contract as `_part_column`, and the same `DEF-962` rule: `sample`
    exists only when one was DECLARED, so a column added here later cannot ship
    a blank cell in the template by omission."""
    entry: dict[str, Any] = {
        "target": target,
        "label": label,
        "kind": kind,
        "required": required,
        "transforms": list(TRANSFORMS_BY_KIND.get(kind, ())),
    }
    if sample is not None:
        entry["sample"] = sample
    if help_text is not None:
        entry["help"] = help_text
    return entry


PAYMENTS_COLUMNS: tuple[dict[str, Any], ...] = (
    _payment_column(
        "account_ref",
        "Account #",
        sample="AC-2026-00042",
        help_text=(
            "The account this money is for — your account number, or the "
            "reference you loaded from your old system."
        ),
    ),
    # ⚠ **MONEY, SO FOUR DECIMALS ARE STORED AND TWO ARE SHOWN** (CLAUDE.md
    # hard rule 2). The sample cell carries the stored precision because the
    # file is what a utility types into.
    _payment_column("amount", "Amount", KIND_DECIMAL, required=True, sample="247.3000"),
    _payment_column(
        "paid_on",
        "Date paid",
        KIND_DATE,
        sample="2026-08-20",
        help_text=(
            "The day the money arrived, not the day you are importing it. "
            "Late fees are judged on this date. Leave it empty and today is used."
        ),
    ),
    _payment_column(
        "reference",
        "Reference",
        sample="CHK-88213",
        help_text="The cheque or confirmation number. It goes on the receipt.",
    ),
    _payment_column(
        "payer_name",
        "Payer",
        sample="J RIVERA",
        help_text=(
            "Only used when the row names no account. A name is not an "
            "identifier, so a row matched on it waits for a person."
        ),
    ),
    _payment_column(
        "memo",
        "Memo",
        sample="August lockbox",
        help_text="A note kept on the payment. It is not shown to the customer.",
    ),
    # PO 2026-10-30 Q6, verbatim: *"can you add network name as part of csv
    # file / excel file do not add it on screen"*. The store payment network
    # that took the money (`Hy-Vee`, `CheckFreePay`). A row naming one banks in
    # that network's own daily deposit batch and reads *Store · Hy-Vee*; a
    # blank cell, or a file without the column, is a lockbox row as before.
    _payment_column(
        "network",
        "Network",
        sample="Hy-Vee",
        help_text=(
            "The store payment network that took the money. "
            "Leave it empty for a lockbox file."
        ),
    ),
)

# ⛔ **`active` IS NOT A COLUMN, AND IT WAS ONE FOR AN HOUR (CR-077, measured
# 2026-09-07).** The template offered *In use* and every row of the first proof
# file came back `rejected_at_write` with *"carries a column the parts register
# does not take"*: `work.services._clean_part`'s allow list is exactly
# `part_no · name · category · unit_of_measure · unit_cost`, an unknown field is
# REFUSED rather than ignored (`US-WRK-010` TC-5), and `create_part` writes
# `active=True` itself. A file cannot carry what work's own door will not take.
#
# ⚠ **THE LESSON IS THE GENERAL ONE FOR A NEW TARGET, NOT A NOTE ABOUT ONE
# COLUMN: THE COLUMN SET IS THE OWNING MODULE'S WRITER'S SIGNATURE, NOT THE
# TABLE'S.** `parts` has an `active` column and `is_system` too; neither is
# reachable through the door this import goes through, and a template offering
# either would rehearse clean and reject every row at the write. Stage 3 cannot
# catch it — no rule in the catalogue asks *"will the writer take this field"* —
# so it is caught by reading the writer, or by running a file.
#
# A part that arrives switched off is not a case the register has: a new part is
# in use, and one taken out of use is taken out on `Work-025`. `is_system` is
# absent for a stronger reason — it means a row the PRODUCT ships, and a file
# that could set it would let a utility's own spreadsheet claim rows the tenant
# may not edit.

#: Explicit column sets, by target. A target listed here derives NOTHING from
#: a model's `_meta`; a target absent here keeps the derived path.
# ═══════════════════════════════════════════════════════════════════════════
# THE ACCOUNTS TARGET (CR-030 W1 — B18 §5.9.3, and EP-CUS-07's five stories)
# ═══════════════════════════════════════════════════════════════════════════
#
# EXPLICIT, like the assets targets and unlike premises/units: the offered set is
# a SIGNED map (B18 §5.9.3 + US-CUS-019/021/023), not everything `Account` has a
# field for. Deriving it from `_meta` would offer `balance`, `credit_tier`,
# `kind` and `nsf_count` — four columns that must never come off a CSV, each for
# a different reason (see NOT_OFFERED below).


# ── CR-058 W7 · BR-CUS-1041 — THE CUSTOMER'S IDENTITY, ON THE ACCOUNTS FILE ──
#
# ⛔ **PO RULING 2026-09-01, VERBATIM:** *"Without identifier we cannot create
# Customer ID or master account ot regular account"*, put back as a migration
# blocker on this import and answered *give it identity columns too*. A row
# carrying a name and ONE identifier loads its account and its customer is
# matched-or-created; a row carrying a name alone loads **nothing** and is
# counted on the receipt.
#
# ⚠ **THE PHONE IDENTIFIER IS THE TEMPLATE'S EXISTING `phone` COLUMN AND THERE
# IS NO `customer_phone` BESIDE IT.** The premises file gained `owner_phone`
# because it had no phone column at all; this file has carried the customer's
# phone since `BR-CUS-046` and it is the number that becomes the account's
# contact. Two columns for one fact is a file where a utility fills one, the
# matcher reads the other, and the bill contact and the identity evidence
# disagree with nothing objecting. Decision log 2026-09-01, judgment 1.
#
# ⚠ **THIS MIRRORS `identity_match.CREATE_IDENTIFIER_FIELDS` AND IS NOT A
# SECOND OPINION BESIDE IT** — the same posture `OWNER_IDENTIFIER_COLUMNS_BY_KIND`
# takes for premises. It decides what the IMPORT SCREEN says; the creation
# minimum is customers' and is applied by customers, inside the account door.
ACCOUNT_IDENTIFIER_COLUMNS_BY_KIND: dict[str, tuple[str, ...]] = {
    "person": ("customer_ssn", "customer_driving_licence", "phone"),
    "company": ("customer_tax_id",),
}

#: Every identity column an accounts row can carry, in the order the PO named
#: them: *"DL, SSN, Phone or Tax ID"*.
ACCOUNT_IDENTIFIER_COLUMNS: tuple[str, ...] = (
    "customer_driving_licence",
    "customer_ssn",
    "phone",
    "customer_tax_id",
)

#: The import column → the key `customers` knows the same fact by. One table,
#: so the spreadsheet's vocabulary and the module boundary's cannot drift.
ACCOUNT_IDENTIFIER_FIELD: dict[str, str] = {
    "customer_ssn": "ssn",
    "customer_driving_licence": "driving_licence",
    "phone": "phone",
    "customer_tax_id": "tax_id",
}

#: ⛔ **`BR-MET-1032` — WHICH STAGED CELLS ARE ENCRYPTED, BY TARGET, IN ONE
#: TABLE.** Both import doors stage through `import_run_rows`, so one entry per
#: target is what makes *"one decision fixes both"* true in code rather than in
#: a comment. The VALUE is `customers`' own field name, because that is the
#: vocabulary `import_identity` looks the crypto contexts up by.
#:
#: ⚠ **`phone` IS PRESENT AND IS NEVER VAULTED**, and the two facts do not
#: contradict each other: this table says which cells CARRY identity, and
#: `import_identity.PROTECTED_FIELDS` says which are protected. A phone is shown
#: in full on every surface in the product (`customers.selectors` serves it
#: whole), so vaulting it would add a ciphertext beside a plaintext cell rather
#: than remove a secret. Stated here because a reader of this table alone would
#: reasonably assume all four are encrypted.
IDENTITY_FIELD_BY_TARGET: dict[str, dict[str, str]] = {
    TARGET_PREMISES: OWNER_IDENTIFIER_FIELD,
    TARGET_ACCOUNTS: ACCOUNT_IDENTIFIER_FIELD,
}


def identity_columns(target: str) -> dict[str, str]:
    """`{target column: customers' field name}` for one target — `BR-MET-1032`.

    Empty for the four targets that carry no identity at all (units and the
    three assets targets), which makes every call below a no-op for them
    without a `if target ==` branch anywhere (`BR-MET-096`)."""
    return IDENTITY_FIELD_BY_TARGET.get(target, {})


def identity_source_columns(target: str, mapping: dict[str, Any]) -> dict[str, str]:
    """`{the operator's own header: field}`, read off a column map.

    Takes either shape the runner holds a map in: stage 1's suggestion
    (`{header: target}`) and stage 2's confirmed resolution
    (`{header: {"target": …}}`). One reader for both, because the alternative is
    two and they drift — and a drift here means a header stops being recognised
    as an identifier and its nine digits stay in the row.
    """
    fields = identity_columns(target)
    out: dict[str, str] = {}
    for source, spec in (mapping or {}).items():
        name = str((spec or {}).get("target") or "") if isinstance(spec, dict) else str(spec or "")
        if name in fields:
            out[str(source)] = fields[name]
    return out


def revealed_mapped(mapped: dict[str, Any] | None, target: str) -> dict[str, Any]:
    """`mapped` with every identity cell back in the operator's own words.

    ⚠ **THIS IS THE MATCHER'S VIEW AND IT IS THE WHOLE POINT OF THE FEATURE.**
    A blind index cannot be built from four digits, so a change that redacted on
    the way IN would have broken the matching this product collects the number
    for, while looking like it hardened something. Every reader that needs the
    real value goes through here."""
    return import_identity.reveal_cells(mapped or {}, identity_columns(target))


#: The identity columns this target ADDS. Named once so the aliases, the
#: verdict and any future strip cannot disagree about which they are.
#: ⚠ `phone` is deliberately NOT here: it is an existing account column that
#: also carries identity, not a new one.
ACCOUNT_IDENTITY_COLUMN_NAMES: tuple[str, ...] = (
    "customer_kind",
    "customer_ssn",
    "customer_driving_licence",
    "customer_tax_id",
)


def _account_column(
    target: str,
    label: str,
    kind: str = KIND_TEXT,
    *,
    required: bool = False,
    sample: str | None = None,
    blank_means: str | None = None,
    help_text: str | None = None,
) -> dict[str, Any]:
    """Same contract as `_asset_column` above, and the same `DEF-962` rule:
    the `sample` key exists only when one was DECLARED. Every accounts column
    declares one today, so this target's file is byte-identical either way —
    it is written this way so the next column added here cannot ship a blank
    cell by omission."""
    entry: dict[str, Any] = {
        "target": target,
        "label": label,
        "kind": kind,
        "required": required,
        "transforms": list(TRANSFORMS_BY_KIND.get(kind, ())),
    }
    if sample is not None:
        entry["sample"] = sample
    if blank_means is not None:
        entry["blank_means"] = blank_means
    if help_text is not None:
        # CR-046 C4 — the same `help` key `_asset_column` writes and the same
        # one stage 2 already renders (DEF-1077). A column DECLARING what it
        # takes, not a new surface.
        entry["help"] = help_text
    return entry


ACCOUNTS_COLUMNS: tuple[dict[str, Any], ...] = (
    # ⚠ THE UNIT IS REQUIRED, AND IT IS THE PO'S OWN LINE (2026-08-23):
    # *"the only thing is acocunts will be mapped to Units at the time of
    # import"*. `KIND_UNIT_REF` already exists and is already used by the assets
    # targets — the mapping asked for is that kind REUSED, not a new mechanism.
    # Resolved at LOAD time against the tenant's units: checked, never created
    # (BR-CUS-047 — a row naming a missing unit is an error, never an
    # auto-create, because the migration order is Premises → Units+Plans →
    # Assets → Accounts → opening reads).
    # ⛔ **NO `sample=` — `DEF-2160`, and it is `DEF-962` on the target `DEF-962`
    # did not reach.** This declared the literal `U-00001`, which short-circuits
    # `cell()`'s `KIND_UNIT_REF` branch, so the accounts template shipped an
    # invented unit number on the ONE target where the column is `required=True`
    # — a worked row that cannot load on any tenant whose first unit is not
    # literally `U-00001`, which is every tenant. The cell is now
    # `_sample_reference_cells()["unit_ref"]`: this tenant's own first unit, or
    # blank when it has none, which is the honest statement that the build order
    # is Premises → Units → Accounts (J20 step 1).
    _account_column("unit_ref", "Unit", KIND_UNIT_REF, required=True),
    # ⛔⛔ **ACCOUNTS ARE THE ONE UPLOAD OF SIX THAT DOES *NOT* CALL SETTINGS ›
    # NUMBERING, AND THIS COLUMN IS REQUIRED (PO ruling 2026-08-27, REVERSING
    # this lane's own first build of CR-046 C4).**
    #
    # PO verbatim: *"we use utility provdied account number here - we dont
    # create our own number - since it will create lot of change management for
    # utility ; if row dont have account number reject it - please update the
    # logic; here we dont call settings -> account number logic"*.
    #
    # ⚠ **IT IS AN EXCEPTION, NOT AN INCONSISTENCY, AND THE PRINCIPLE UNDER
    # BOTH RULINGS IS THE SAME ONE: THE SIDE THAT OWNS THE IDENTIFIER ISSUES
    # IT.** A meter number is OURS and the customer has never seen it, so
    # issuing it removes collisions at no cost. An account number is THEIRS —
    # it is on every bill they kept, in their bank's payee list, on the
    # standing order. Renumbering is not a data change; it is a letter to every
    # customer, a reprint of every form, and a year of people quoting a number
    # the staff can no longer find. `BR-TEN-035` is the same instinct.
    #
    # ⚠ **DO NOT ADD A BLANK-MEANS-ALLOCATE PATH HERE.** There is nothing safe
    # to invent: a number we made up is one the customer has never seen and the
    # utility's own old records cannot match. A blank is an ERROR, not a gap.
    # It also closes `OQ-165`'s measured defect — on `bbu-accounts-cutover.csv`
    # the 96 blank-number rows **quietly created 96 new accounts on units that
    # already had one** while the 1,144 explicit ones errored as duplicates.
    #
    # ⚠ **AND THE OLD SAMPLE WAS A LIE ABOUT THIS TENANT'S OWN SETTINGS** —
    # `A-10432` against an `AC-{YYYY}-{00000}` series is a shape that series
    # cannot produce at any counter value. It is a WORKED value again now, but
    # it is a worked value for the OPERATOR'S OWN numbering, which is what this
    # column has always actually held.
    _account_column(
        "account_no",
        "Account # (your own)",
        required=True,
        sample="A-10432",
        help_text=(
            "YOUR account number for this customer — the one already on their "
            "bills, their bank's payee list and your own old system. "
            "SMART360 Next keeps it exactly as you send it and never issues one "
            "of its own here, because renumbering an account means writing to "
            "every customer. A row with this cell empty is rejected. It is also "
            "how a corrected re-run of this file finds the rows it created, so "
            "it must not change between runs."
        ),
    ),
    _account_column("customer_name", "Customer name", required=True, sample="Miller, Sarah"),
    # CR-030 W0 landed the column this maps onto. `customer_ref` below is the
    # LEGACY id and is what makes a re-import LINK instead of duplicating
    # (BR-CUS-054); the two are different facts and a utility needs both.
    # ⛔ **THIS COLUMN WAS OFFERED, AUTO-MAPPED, REPORTED `Matched` AT STAGE 2
    # AND THEN DROPPED ON THE FLOOR — `DEF-2593`, and it is `DEF-1660` one
    # column along on the same target and in the same function.** Its
    # `blank_means` promised *"allocated from the tenant's series"*, which reads
    # as *a value you supply is used*, and nothing read it: a utility migrating
    # in with its own customer numbers lost every one and could not reconcile
    # against their old system. `link_customer` is handed it now — a number on
    # file LINKS to that customer, a free one CREATES with that number, a blank
    # allocates as before (`BR-CUS-1042`).
    # ⚠ **IT IS A KEY AND NOT AN IDENTIFIER.** Quoting a number satisfies
    # `BR-CUS-1041` no more than `customer_ref` does — both name a ROW, neither
    # evidences a PERSON.
    _account_column(
        "customer_no",
        "Customer #",
        blank_means="allocated from the tenant's `customer` series (CR-030 W0)",
        sample="C-00001",
        help_text=(
            "YOUR customer number, if you already have one — the number that "
            "groups this customer's accounts. A number already on file links "
            "this account to that customer; a new one is kept exactly as you "
            "send it. Leave it empty and one is issued from your own series."
        ),
    ),
    _account_column("customer_ref", "Customer reference (legacy)", sample="CUST-118"),
    _account_column(
        "account_type", "Account type", KIND_LOOKUP, required=True, sample="residential"
    ),
    _account_column("account_subtype", "Account sub-type", KIND_LOOKUP, sample=""),
    _account_column("status", "Status", KIND_LOOKUP, sample="active"),
    # PO 2026-10-17 (`DEF-CUS-10180`): the ORIGINAL Opened date from the old
    # system, so a migrated account's age on the Accounts list is its real one
    # (2012 → 14 yrs 7 mos) rather than the day of the import. Optional; a
    # future date is refused by `ACC.OPENED_NOT_FUTURE`, an unreadable one by
    # `ACC.VALUES_PARSE`. Rule 33: instructions ≤ 6 words a sentence.
    _account_column(
        "opened_at",
        "Opened on",
        KIND_DATE,
        sample="2026-01-01",
        blank_means="no Opened date (required only when activating)",
        help_text="Optional. The day it first opened. Age counts from this day. "
        "Future dates are refused.",
    ),
    _account_column("closed_at", "Closed on", KIND_DATE, sample=""),
    # ── BR-CUS-048's FOUR AGED BUCKETS. ❄️ GT-16, finance-signed 2026-08-08.
    # NOT one figure: a lump sum lands every migrated account at `Current` on
    # day one, so collections cannot act and late fees are wrong for a quarter.
    # The PO asked for this on 2026-08-24 and it was already signed law.
    _account_column(
        "ob_current", "Opening balance · current", KIND_DECIMAL, blank_means="0.00", sample="84.20"
    ),
    _account_column(
        "ob_31_60", "Opening balance · 31–60 days", KIND_DECIMAL, blank_means="0.00", sample="62.10"
    ),
    _account_column(
        "ob_61_90", "Opening balance · 61–90 days", KIND_DECIMAL, blank_means="0.00", sample="0.00"
    ),
    _account_column(
        "ob_90_plus",
        "Opening balance · 90+ days",
        KIND_DECIMAL,
        blank_means="0.00",
        sample="121.00",
    ),
    # US-CUS-023 — the ORIGINAL receipt date, because interest accrues from it
    # (BR-CUS-050/057). Importing the deposit without its date starts the clock
    # at cutover and quietly under-pays every migrated customer.
    _account_column("deposit_on_file", "Deposit on file", KIND_DECIMAL, sample="150.00"),
    _account_column("deposit_received_on", "Deposit received on", KIND_DATE, sample="2024-02-12"),
    _account_column("currency", "Currency", blank_means="the tenant's currency", sample="USD"),
    _account_column("autopay", "Autopay", KIND_BOOLEAN, sample="false"),
    _account_column("tax_exempt", "Tax exempt", KIND_BOOLEAN, sample="false"),
    _account_column("tax_exempt_ref", "Tax exemption reference", sample=""),
    _account_column("tax_exempt_expires", "Exemption expires", KIND_DATE, sample=""),
    _account_column("bad_address", "Bad address", KIND_BOOLEAN, sample="false"),
    _account_column("preferred_language", "Preferred language", KIND_LOOKUP, sample=""),
    _account_column("email", "Email", sample="sarah.miller@example.com"),
    # ⚠ **THIS COLUMN CARRIES TWO FACTS SINCE `BR-CUS-1041`, AND THAT IS
    # DELIBERATE (decision log 2026-09-01, judgment 1).** It is the account's
    # contact phone AND, for a customer stated as a person, an identifier good
    # enough to create a Customer # — the PO named a phone in the creation
    # minimum. A second `customer_phone` column beside it would be one fact in
    # two cells: a utility fills one, the matcher reads the other.
    _account_column(
        "phone",
        "Phone",
        sample="+1 (512) 555-0184",
        help_text=(
            "The customer's phone. For a person this also identifies them, so "
            "a row with a name and a phone is enough to create their customer "
            "number. A company is identified by its Tax ID instead."
        ),
    ),
    _account_column("mailing_line1", "Mailing address line 1", sample=""),
    _account_column("mailing_city", "Mailing city", sample=""),
    _account_column("mailing_state", "Mailing state", sample=""),
    _account_column("mailing_postal_code", "Mailing postal code", sample=""),
    # ⛔ **NEVER DISCARD THE CUSTOMER'S OWN KEY — AND THIS COLUMN DID EXACTLY
    # THAT FOR THREE MONTHS (`DEF-1660`, CR-046 C4/C5).** The comment here read
    # *"throw it away and a re-import duplicates every row it created and 'what
    # happened to account 88214' has no answer"* — and the column was offered,
    # auto-mapped, reported `Matched` at stage 2, and then dropped on the floor
    # by `_account_payload_from`, whose own comment explained that `external_ref`
    # is a CUSTOMER field. It is: `customers.external_ref` is the PERSON's
    # legacy id (BR-CUS-054). It is not the ACCOUNT's, and a landlord with
    # fourteen units has fourteen legacy account numbers and one customer row.
    # `accounts.external_ref` (BR-CUS-172, migration customers/0033) is where
    # this value now lands, and it is UNIQUE per tenant, so it is the match key
    # a corrected re-run needs.
    # ⚠ `sample=""` for the same reason as every other reference cell: a made-up
    # legacy id in the template is one an operator might leave in place, and it
    # would then claim to be a record from a system we have never seen.
    _account_column(
        "external_ref",
        "External reference",
        **_as_column_kwargs(_legacy_ref_column("Account")),
    ),
    # ══════════════════════════════════════════════════════════════════════
    # CR-058 W7 · BR-CUS-1041 — WHO THIS CUSTOMER IS
    # ══════════════════════════════════════════════════════════════════════
    #
    # ⚠ **EVERY ONE IS OPTIONAL IN THE FILE, AND THAT IS THE COMPATIBILITY
    # GUARANTEE.** A spreadsheet saved yesterday still maps and still loads;
    # what changed is what a ROW is allowed to CREATE. None of them is
    # `required=True` and none ever will be — a required column is refused at
    # stage 2 for the whole file, which would turn a rule about rows into a
    # rule about uploads.
    #
    # ⚠ **EVERY IDENTIFIER SHIPS `sample=""` — `DEF-962`'s ruling.** A worked
    # cell here would be an invented Social Security number in a file a utility
    # hands to its staff. The kind is the one column whose worked value invents
    # nothing, because its two values are the product's own vocabulary.
    _account_column(
        "customer_kind",
        "Customer is a person or a company",
        KIND_OWNER_KIND,
        sample="person",
        blank_means="no account and no customer is created from this row",
        help_text=(
            "A person is identified by a Social Security number, a driving "
            "licence or a phone; a company by its Tax ID. Without it we cannot "
            "tell which identifier counts, so the row loads nothing."
        ),
    ),
    _account_column(
        "customer_ssn",
        "Customer Social Security number",
        sample="",
        blank_means="fine, if the row carries a driving licence or a phone",
        help_text=(
            "For a person. Stored encrypted; only the last four ever appear on screen."
        ),
    ),
    _account_column(
        "customer_driving_licence",
        "Customer driving licence",
        sample="",
        blank_means="fine, if the row carries a Social Security number or a phone",
        help_text=(
            "For a person. Stored encrypted; only the last four ever appear on screen."
        ),
    ),
    _account_column(
        "customer_tax_id",
        "Customer Tax ID",
        sample="",
        blank_means="a company row with this empty loads nothing",
        help_text="For a company, and the only identifier a company is created from.",
    ),
)

#: The four bucket columns, in ageing order — named once so the loader's
#: cutover check and `customers.import_writer` cannot disagree about which
#: columns carry money.
#: Just the column names, for the parse branch's BR-CUS-061 credit reading — a
#: negative cell in one of THESE is an opening credit and is carried; a negative
#: anywhere else is a typo and is refused. Derived from the pairs below so the
#: two cannot drift. (It read *"for the parse branch's OQ-065 refusal"* until
#: DEF-620: OQ-065 closed on 2026-08-08 and the refusal should never have been
#: written.)
ACCOUNTS_BUCKET_TARGETS: frozenset[str]

ACCOUNTS_BUCKET_FIELDS: tuple[tuple[str, str], ...] = (
    ("ob_current", "current"),
    ("ob_31_60", "d31_60"),
    ("ob_61_90", "d61_90"),
    ("ob_90_plus", "d90_plus"),
)
ACCOUNTS_BUCKET_TARGETS = frozenset(field for field, _bucket in ACCOUNTS_BUCKET_FIELDS)

#: Columns this target deliberately does NOT offer, each with the reason it is
#: absent — the stated-absence discipline (G38/DEF-421) applied to a dropdown,
#: exactly as `UNIT_CNT` is for premises. A mapping target the model cannot
#: honour is worse than a missing one: it silently accepts data and drops it.
ACCOUNTS_NOT_OFFERED: tuple[tuple[str, str], ...] = (
    (
        "balance",
        "a CACHE — the ledger is the source of truth (B2). The opening balance "
        "comes in as the four aged buckets above and posts through "
        "`opening_balances.post_opening_batch`; `accounts.balance` is their exact sum.",
    ),
    ("credit_tier", "COMPUTED (BR-CUS-058) — there is no input path, by design."),
    (
        "kind",
        "a REFUSED input on every account path (`services.REFUSED_FIELDS`); the only "
        "door to `master` is `POST /accounts/master` (BR-CUS-068).",
    ),
    (
        "nsf_count",
        "set by payment behaviour, never declared — and `cash_only_no_autopay` with it "
        "(BR-PAY-013).",
    ),
    (
        "plan",
        "BR-CUS-029 — the account plan snapshot has NO table; an account derives its "
        "plan from its unit.",
    ),
    (
        "meter_no",
        "the assets import's job. PO ruling 2026-08-21: *\"we will not add meter or asset "
        "here when we are uploading units. When we upload assets at that time Units will "
        'be in system"* — the same logic one step along.',
    ),
)

#: CR-077 — the header words a utility's parts spreadsheet actually uses.
PARTS_ALIASES: dict[str, tuple[str, ...]] = {
    "part_no": ("part", "part_no", "part #", "part number", "sku", "item", "item_no", "item #"),
    "name": ("name", "description", "part_name", "part name", "item description"),
    "category": ("category", "part_category", "group", "class", "type"),
    "unit_of_measure": ("unit", "uom", "unit_of_measure", "unit of measure", "units", "each"),
    "unit_cost": ("cost", "unit_cost", "unit cost", "price", "unit price", "std cost"),
}

#: ⚠ **THESE ARE `apps/payments/lockbox.py::REMITTANCE_COLUMN_ALIASES`, COPIED
#: DELIBERATELY RATHER THAN IMPORTED.** Importing them would be a cross-module
#: import from metering into payments (B1/B2 §2), which is the boundary this
#: whole target exists to respect. They are the vocabulary real bank and store
#: files emit, proved by the pipeline that has been reading them since CR-059 —
#: so a file the retiring pipeline accepted is a file this target accepts. Each
#: field's own name is included, so the CR-025 sample maps itself at stage 2.
PAYMENTS_ALIASES: dict[str, tuple[str, ...]] = {
    "account_ref": (
        "account_ref",
        "account ref",
        "account",
        "account no",
        "account number",
        "account #",
        "acct",
        "acct no",
        "customer account",
        "customer number",
    ),
    "amount": ("amount", "amount paid", "paid", "payment", "value", "remittance"),
    "paid_on": (
        "paid_on",
        "paid on",
        "date",
        "payment date",
        "received",
        "received date",
        "check date",
        "cheque date",
        "deposit date",
    ),
    "reference": (
        "reference",
        "ref",
        "check no",
        "check number",
        "check #",
        "cheque no",
        "cheque number",
        "confirmation",
        "document",
    ),
    "payer_name": (
        "payer_name",
        "payer name",
        "payer",
        "name",
        "customer",
        "customer name",
        "remitter",
    ),
    "memo": ("memo", "note", "notes", "narrative", "description"),
    # Q6 (PO 2026-10-30) — the store network's name, as partner files head it.
    "network": (
        "network",
        "payment network",
        "store network",
        "store",
        "network name",
        "agent network",
        "retail network",
    ),
}

ACCOUNTS_ALIASES: dict[str, tuple[str, ...]] = {
    "unit_ref": ("unit", "unit_id", "unit_no", "unit_ref", "unit number", "apt", "premise_unit"),
    "account_no": ("account", "account_no", "account #", "acct", "acct_no", "account number"),
    "customer_name": ("name", "customer", "customer_name", "customer name", "account name"),
    "customer_no": ("customer_no", "customer #", "customer number"),
    "customer_ref": ("customer_ref", "customer reference", "legacy_customer", "cust_id"),
    "account_type": ("type", "account_type", "account type", "class", "customer_class"),
    "account_subtype": ("subtype", "account_subtype", "sub type", "sub-type"),
    "status": ("status", "account_status"),
    "opened_at": ("opened", "opened_at", "open date", "start_date", "since"),
    "closed_at": ("closed", "closed_at", "close date", "end_date"),
    "ob_current": ("ob_current", "opening_current", "current", "balance_current", "aging_current"),
    "ob_31_60": ("ob_31_60", "opening_31_60", "31-60", "31_60", "aging_31_60", "days_31_60"),
    "ob_61_90": ("ob_61_90", "opening_61_90", "61-90", "61_90", "aging_61_90", "days_61_90"),
    "ob_90_plus": ("ob_90_plus", "opening_90_plus", "90+", "90_plus", "aging_90_plus", "over_90"),
    "deposit_on_file": ("deposit", "deposit_on_file", "deposit amount", "security_deposit"),
    "deposit_received_on": ("deposit_date", "deposit_received_on", "deposit received"),
    "currency": ("currency", "ccy"),
    "autopay": ("autopay", "auto_pay", "ach"),
    "tax_exempt": ("tax_exempt", "exempt"),
    "tax_exempt_ref": ("tax_exempt_ref", "exemption_ref", "exemption certificate"),
    "tax_exempt_expires": ("tax_exempt_expires", "exemption_expires"),
    "bad_address": ("bad_address", "undeliverable", "returned_mail"),
    "preferred_language": ("language", "preferred_language", "locale"),
    "email": ("email", "e-mail", "email_address"),
    "phone": ("phone", "telephone", "mobile", "phone_number"),
    "mailing_line1": ("mailing_address", "mailing_line1", "mail_addr1", "billing_address"),
    "mailing_city": ("mailing_city", "mail_city"),
    "mailing_state": ("mailing_state", "mail_state"),
    "mailing_postal_code": ("mailing_zip", "mailing_postal_code", "mail_zip"),
    "external_ref": ("legacy_key", "external_ref", "external reference", "legacy id"),
    # CR-058 W7 · BR-CUS-1041. ⚠ `phone` above is the person's identifier too
    # and gets no second entry here — one fact, one column.
    "customer_kind": (
        "customer_kind",
        "customer kind",
        "customer type",
        "person or company",
    ),
    "customer_ssn": ("customer_ssn", "customer ssn", "ssn", "social security", "social security number"),
    "customer_driving_licence": (
        "customer_driving_licence",
        "customer driving licence",
        "driving licence",
        "driving license",
        "drivers license",
        "dl",
    ),
    "customer_tax_id": ("customer_tax_id", "customer tax id", "tax id", "tax_id", "ein", "vat number"),
}

EXPLICIT_COLUMNS_BY_TARGET: dict[str, tuple[dict[str, Any], ...]] = {
    TARGET_ACCOUNTS: ACCOUNTS_COLUMNS,
    TARGET_PARTS: PARTS_COLUMNS,
    TARGET_ASSETS_METERS: ASSETS_METERS_COLUMNS,
    TARGET_ASSETS_SUBMETERS: ASSETS_SUBMETERS_COLUMNS,
    TARGET_ASSETS_DEVICES: ASSETS_DEVICES_COLUMNS,
    TARGET_PAYMENTS: PAYMENTS_COLUMNS,
}


def asset_column_order(target: str) -> tuple[str, ...]:
    """The sheet's field names in the plan's order — the ONE order every
    downloaded asset file follows (PO confirmation 2026-09-30: the template,
    the sample, the failures file and the result file)."""
    if target not in ASSETS_TARGETS:
        return ()
    return tuple(column["target"] for column in EXPLICIT_COLUMNS_BY_TARGET[target])


def asset_billing_fields(target: str) -> tuple[str, ...]:
    """The 💲 columns of one asset sheet — what a re-upload may override and
    what the result file must list old → new, per asset (PO 2026-09-30)."""
    return tuple(
        column["target"]
        for column in EXPLICIT_COLUMNS_BY_TARGET.get(target, ())
        if column.get("billing")
    )


#: Header aliases for the assets targets' auto-detect — the B16 §4.7b source
#: headers (the committed CR-028 fixtures use exactly these) plus each field's
#: own name, so the sample file maps itself at stage 2 (the CR-025 property).
#: `LEGACY` deliberately has NO alias: it is the field map's explicit
#: "— ignore —" case, and BR-MET-088 forbids offering a target with nothing
#: behind it.
_UOM_ALIASES: tuple[str, ...] = (
    "uom",
    "unit of measure",
    "unit_of_measure",
    "units of measure",
    "measure unit",
    "capacity unit",
    "capacity_unit",
)
_ASSETS_METER_ALIASES: dict[str, tuple[str, ...]] = {
    # ⛔ **`meter_no` / `meter #` / `meter number` NOW MEAN `external_ref`, AND
    # THAT RE-POINTING IS THE PRACTICAL HALF OF THE 2026-08-27 RULING.**
    #
    # They were `asset_no`'s aliases. Under the ruling `asset_no` is *"an
    # EXISTING SMARTBillHub number"*, and a first-migration file's `METER_NO`
    # column is the opposite of that: it is the OLD system's number, every cell
    # of which is a number this product has never issued. Leaving the alias
    # where it was would auto-map 1,847 legacy numbers onto the one column that
    # now refuses them (`AST.NUMBER_NOT_ON_FILE`), and the operator would meet
    # 1,847 identical errors on a file the product's own auto-mapper built.
    # Pointed at `external_ref` the same header lands where the ruling says the
    # utility's own reference belongs, and nothing is lost.
    #
    # ⚠ **`asset_no` KEEPS ONLY ITS OWN FIELD NAME AND ITS LABEL** (the label
    # match is `_auto_map`'s second pass, so the shipped sample still maps
    # itself — the CR-025 property `test_def616__every_shipped_sample_maps_
    # itself` asserts). That IS *"the auto-mapper stops offering it"*: no
    # header a utility would plausibly ship claims it any more, and an
    # operator updating existing meters maps it by hand, deliberately, which
    # is the only case it is now for.
    "asset_no": ("asset_no",),
    "external_ref": (
        "meter_no",
        "meter no",
        "meter #",
        "meter number",
        "legacy_key",
        "external_ref",
        "external reference",
        "legacy id",
        "old meter number",
    ),
    "serial_no": ("serial", "serial_no", "serial no", "serial #", "serial number", "device id"),
    "meter_type": ("meter_type", "meter type"),
    "service": ("service",),
    "read_method": ("read_method", "read method"),
    "multiplier": ("multiplier", "mult"),
    # BR-MET-530 — the headers a migration file plausibly ships for a
    # connection size. `meter_size` is here because that is what a legacy
    # system almost certainly calls it, and BR-TEN-170 renamed the LIST to the
    # utility SERVICE size class without renaming what is printed on ten years
    # of other people's exports.
    #
    # ⚠ **SUB-METERS INHERIT THIS TABLE (`ASSETS_SUBMETERS_ALIASES` spreads it)
    # AND STILL DO NOT GET THE COLUMN.** `_auto_map` skips any alias whose field
    # is not in the OFFERED set, and `_assets_meter_columns(with_size=False)`
    # leaves it out there — so the boundary is held by the column set, in one
    # place, rather than by two tables that have to agree.
    "size_class": (
        "size_class",
        "size class",
        "size",
        "connection size",
        "connection_size",
        "meter_size",
        "meter size",
    ),
    # ⛔ **PLAN U3 (2026-09-30) — THE HEADERS A MIGRATION FILE SHIPS FOR THE
    # NEW COLUMNS.** ⚠ `unit` IS NOT ONE OF THEM: the bare word has meant the
    # UNIT a meter sits in (`unit_ref`) since BR-AST-045, and re-pointing it
    # would silently seat 1,847 meters in "kWh". The field is `unit` because
    # that is the `Asset` column; its headers all say MEASURE.
    "unit": _UOM_ALIASES,
    "net_metering": (
        "net_metering",
        "net metering",
        "net metered",
        "net_metered",
        "net meter",
        "bidirectional",
    ),
    "register_digits": ("register_digits", "register digits", "digits", "dials", "num_dials"),
    "unit_ref": ("unit_ref", "unit", "unit ref", "unit reference"),
    "manufacturer": ("mfr", "manufacturer"),
    "model": ("model",),
    "install_date": ("install_dt", "install date", "install_date", "installed"),
    "certification_due": ("cert_due", "cert due", "certification due", "certification_due"),
    "warranty_end": ("warranty_end", "warranty end", "warranty"),
    "supplier": ("supplier",),
    "purchase_cost": ("cost", "purchase cost", "purchase_cost"),
}
ASSETS_SUBMETERS_ALIASES: dict[str, tuple[str, ...]] = {
    **_ASSETS_METER_ALIASES,
    # Same re-pointing as the meters target above, one noun along.
    "asset_no": ("asset_no",),
    "external_ref": (
        *_ASSETS_METER_ALIASES["external_ref"],
        "sub_meter_no",
        "sub-meter number",
    ),
    "parent_asset_no": ("parent_mtr", "parent", "parent meter", "master", "parent_asset_no"),
    "allocation_share_pct": ("alloc_pct", "allocation", "allocation share", "allocation_share_pct"),
    # Plan U3 (2026-09-30).
    "allocation_rule": (
        "allocation_rule",
        "allocation rule",
        "allocation method",
        "alloc_rule",
        "alloc_method",
    ),
    "loss_tolerance_pct": (
        "loss_tolerance_pct",
        "loss tolerance",
        "loss tolerance %",
        "loss_tol",
        "loss tol",
    ),
}
ASSETS_DEVICES_ALIASES: dict[str, tuple[str, ...]] = {
    # Same re-pointing again. `device_no` on a migration file is the old
    # system's device id, not one of ours.
    "asset_no": ("asset_no",),
    "external_ref": (
        "device_no",
        "device no",
        "device #",
        "device number",
        "meter_no",
        "legacy_key",
        "external_ref",
        "external reference",
        "legacy id",
    ),
    "serial_no": ("serial", "serial_no", "serial no", "serial #", "serial number", "device id"),
    "type": ("device_type", "device type", "type"),
    "premises": ("premise_id", "premise", "premises", "property id"),
    "unit_ref": ("unit_ref", "unit", "unit ref"),
    # ⛔ Plan U3 (PO ruling 2026-09-30) — the four columns the devices sheet
    # gained. `size_class` takes the meters' headers plus the three a device
    # file actually ships (cart, fire line, panel).
    "parent_asset_no": (
        "parent_mtr",
        "parent",
        "parent meter",
        "linked meter",
        "linked_meter",
        "parent_asset_no",
    ),
    "service": ("service", "utility service"),
    "size_class": (
        *_ASSETS_METER_ALIASES["size_class"],
        "cart size",
        "fire line size",
        "fire-line size",
        "panel size",
        "device size",
    ),
    "unit": _UOM_ALIASES,
    "manufacturer": ("mfr", "manufacturer"),
    "model": ("model",),
    "install_date": ("install_dt", "install date", "install_date", "installed"),
    "test_interval_months": ("test_freq", "test frequency", "test_interval_months"),
    "certification_due": ("next_test", "next test", "certification_due"),
    "export_capacity_kw": ("export_kw", "export capacity", "export_capacity_kw"),
    "warranty_end": ("warranty_end", "warranty end", "warranty"),
    "supplier": ("supplier",),
    "purchase_cost": ("cost", "purchase cost", "purchase_cost"),
}

# ── BR-AST-048 · the seeded default mapping templates ───────────────────────
#: target → (code, ruled name). One system default per ASSETS target, seeded
#: into tenancy's `import_mappings` list at provisioning (tenancy resolves
#: `default_import_mapping_entries` below through its seam).
# ⚠ THE FOURTH ENTRY EXISTS BECAUSE A RULE NOW NAMES IT — BR-CUS-075, PO ruling
# 2026-08-24. CR-030 W1 added an accounts default, `test_the_three_defaults_seed_
# for_a_fresh_tenant` went red on `3 != 4`, and it was REMOVED: BR-AST-048 is
# written for the three ASSETS targets, these rows appear on the SET-04 list a
# tenant reads, and a new row on a shipped Settings screen needs a rule behind
# it. That removal was right on the evidence available and is worth leaving on
# the record, because the PO then supplied the missing half — pointing at
# Settings → Reference data → Finance → Import mappings showing `0`:
#
#     "you might hav to add account import mapping tempalte to this settings"
#     "we did that for other improt also"
#
# ⚠ APPENDED LAST, NOT SORTED IN. This dict's ORDER IS THE ORDER THE SET-04 LIST
# PRINTS, so a new entry goes at the end; inserting it alphabetically would move
# three rows on a screen a tenant already knows. Same lesson as
# `core.numbering.SERIES_CATALOG` in CR-030 W0.
#
# ⚠ **AND `premises` AND `units` NOW HAVE ONE TOO — PO RULING 2026-09-07, AND
# THE SENTENCE THAT STOOD HERE IS SUPERSEDED.** It read: *"`premises` and
# `units` still have NO default and this ruling does not give them one — they
# were not raised, and a signature covers only what was shown."* That was the
# correct reading of BR-CUS-075 and it stayed correct for exactly as long as
# nobody raised them. The PO then raised them, by name and first in the list:
#
#     "it is required for - Premises, Units, Meters, Sub meter,s Assets, Parts,
#      Accounts, Reading - including all readings - Flat, Demand based,
#      Seasonal, Peak , off peak, etc"
#
# **These two are the ones a utility loads FIRST** — the README's own build
# order is Premises → Units → Assets → Accounts — so the two imports every
# migration begins with were the two with no starter, while the four that come
# after them all had one. (`Parts` and the reads are the same ruling and are
# NOT in this dict: `Parts` has no import target at all and the reads are a
# separate mechanism with their own `template_csv`. Both are named in the
# decision log of 2026-09-07 and neither is quietly dropped.)
#
# ⚠ APPENDED LAST, NOT SORTED IN — the same rule the accounts entry landed
# under. This dict's ORDER IS THE ORDER THE SET-04 LIST PRINTS, so putting
# premises first (which is where the build order would put it) would move four
# rows on a screen a tenant already knows.
DEFAULT_MAPPING_TEMPLATES: dict[str, tuple[str, str]] = {
    TARGET_ASSETS_METERS: ("assets_meters_default", "Meters default"),
    TARGET_ASSETS_SUBMETERS: ("assets_submeters_default", "Sub-meters default"),
    TARGET_ASSETS_DEVICES: ("assets_devices_default", "Devices default"),
    TARGET_ACCOUNTS: ("accounts_default", "Accounts default"),
    TARGET_PARTS: ("parts_default", "Parts default"),
    TARGET_PREMISES: ("premises_default", "Premises default"),
    TARGET_UNITS: ("units_default", "Units default"),
    # ⚠ APPENDED LAST, NOT SORTED IN — the same rule the accounts and parts
    # entries landed under. This dict's ORDER IS THE ORDER THE SET-04 LIST
    # PRINTS, so inserting this one anywhere else moves rows on a screen a
    # tenant already knows.
    TARGET_PAYMENTS: ("payments_default", "Payments default"),
}


def default_import_mapping_entries() -> list[dict[str, Any]]:
    """BR-AST-048 + BR-CUS-075 + the PO ruling of 2026-09-07: the SIX defaults,
    GENERATED from the SAME column sets that generate the CR-025 sample CSV —
    one source, so the sample's header row and the default template can never
    drift (DEF-521's shape, prevented by construction). The mapping is the
    target's own columns 1:1 under the sample's header names.

    ⚠ **THE COLUMNS COME FROM `sample_columns` NOW, NOT FROM
    `EXPLICIT_COLUMNS_BY_TARGET` — AND THAT IS WHAT LETS PREMISES AND UNITS HAVE
    A STARTER AT ALL.** Four of the six targets DECLARE their columns and two
    DERIVE them from the model's own `_meta` (`target_columns`, BR-MET-088), so
    reading the declared dict directly worked for exactly the four that were in
    this dict and would have raised `KeyError('premises')` for the two that were
    not. `sample_columns` is the list `sample_csv` itself writes, for every
    target and by either route, which is the "one source" this docstring
    promises — reading anything else would have been a second copy of it.

    For the four existing defaults this is byte-identical: `sample_columns`
    returns the declared entries unchanged, minus `— ignore —` (a mapping
    choice, never a column) and minus the tenant's custom fields (a sample
    cannot know a tenant's own field keys), neither of which was ever in a
    generated default.

    ⛔ **THE SOURCE KEY IS THE COLUMN'S LABEL SINCE 2026-08-28 (`DEF-1077`),
    BECAUSE THE SAMPLE'S HEADER ROW IS.** A mapping template is matched by its
    SOURCE HEADER SET (`_match_mapping_template`), so the moment `sample_csv`
    started writing labels, a default still keyed on field names stopped
    recognising the very file it was generated from — the sample would arrive,
    map itself by alias, and show no recognised template. That is the exact
    drift this docstring says cannot happen, so the key moves with the header
    rather than being left behind it.

    ⚠ **THE TARGET SIDE IS UNTOUCHED AND MUST STAY THAT WAY**: the DESTINATION
    is a field name, always — it is what `_apply_mapping` writes to. Only the
    source key, which is a string in somebody's spreadsheet, follows the label.
    """
    entries: list[dict[str, Any]] = []
    for target, (code, name) in DEFAULT_MAPPING_TEMPLATES.items():
        columns = sample_columns(target)
        entries.append(
            {
                "code": code,
                "name": name,
                "target": target,
                "mapping": {str(entry["label"]): {"target": entry["target"]} for entry in columns},
            }
        )
    return entries


#: ⚠ **THE ONE PLACE A TARGET IS RESOLVED TO ITS TABLES.** Adding a target is
#: dict entries and a model — never a branch (`BR-MET-096`). CR-028 adds three.
FIELD_OVERRIDES_BY_TARGET: dict[str, dict[str, dict[str, Any]]] = {
    TARGET_PREMISES: PREMISES_FIELD_OVERRIDES,
    TARGET_UNITS: UNITS_FIELD_OVERRIDES,
}
ALIASES_BY_TARGET: dict[str, dict[str, tuple[str, ...]]] = {
    TARGET_ACCOUNTS: ACCOUNTS_ALIASES,
    TARGET_PARTS: PARTS_ALIASES,
    TARGET_PREMISES: PREMISES_ALIASES,
    TARGET_UNITS: UNITS_ALIASES,
    TARGET_ASSETS_METERS: _ASSETS_METER_ALIASES,
    TARGET_ASSETS_SUBMETERS: ASSETS_SUBMETERS_ALIASES,
    TARGET_ASSETS_DEVICES: ASSETS_DEVICES_ALIASES,
    TARGET_PAYMENTS: PAYMENTS_ALIASES,
}

UNAVAILABLE_TRANSFORMS: tuple[dict[str, str], ...] = (
    {
        "code": "standardise_usps",
        "label": "Standardise to USPS",
        "reason": (
            "This product has no address service, so no address can be "
            "corrected against the postal file."
        ),
    },
    {
        "code": "zip4_split",
        "label": "ZIP+4 split",
        "reason": (
            "A premises records one postal code, so there is nowhere to keep "
            "the +4 half and it would be dropped without saying so."
        ),
    },
)

#: r10's three row-handling checkboxes, verbatim.
ROW_HANDLING_KEYS = ("drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required")

#: Which mapped field r10's *"skip rows with empty required fields"* checkbox
#: reads per target, with the sentence the skipped row shows. Premises keeps
#: its exact original wording (the shipped tests pin it).
SKIP_REQUIRED_BY_TARGET: dict[str, tuple[str, str]] = {
    TARGET_ACCOUNTS: ("unit_ref", "This row names no unit."),
    TARGET_PARTS: ("part_no", "This row has no part number."),
    TARGET_PREMISES: ("address_line", "This row has no street address."),
    TARGET_UNITS: ("label", "This row has no unit label."),
    TARGET_ASSETS_METERS: ("service", "This row names no service."),
    TARGET_ASSETS_SUBMETERS: ("service", "This row names no service."),
    TARGET_ASSETS_DEVICES: ("type", "This row names no device type."),
    # ⚠ **THE AMOUNT AND NOT THE ACCOUNT.** A row with no amount is not a
    # payment at all; a row with no account is a payment that needs a person,
    # which is a different outcome and `PAY.PAYER_NAMED` owns it. Skipping on
    # the account would throw away money the file really carries.
    TARGET_PAYMENTS: ("amount", "This row has no amount."),
}

#: Which mapped field *"keep the latest row when a key appears twice"* keys on,
#: with the label its drop sentence prints. ⚠ Units deliberately keeps its
#: shipped no-op (`premise_no` is never on a mapped units row): a bare unit
#: LABEL repeats legitimately across premises in one file, so deduping on it
#: would silently drop real rows — the in-file uniqueness rule judges the
#: composite instead.
DEDUPE_KEY_BY_TARGET: dict[str, tuple[str, str]] = {
    TARGET_ACCOUNTS: ("account_no", "Account #"),
    # The part number is the utility's own and it is the match key, so it is
    # also the one thing a duplicated row in a migration file repeats.
    TARGET_PARTS: ("part_no", "Part #"),
    TARGET_PREMISES: ("premise_no", "Premise ID"),
    TARGET_UNITS: ("premise_no", "Premise ID"),
    # ⛔ **THE THREE ASSETS TARGETS DEDUPE ON `external_ref` SINCE 2026-08-27,
    # AND THE ALTERNATIVE WAS A DEAD CONTROL.** They keyed on `asset_no`, and
    # under the PO ruling of that day `asset_no` is BLANK on every row of a
    # normal file — so *"keep the latest row when a key appears twice"* would
    # have kept its checkbox, its sentence and its counter and silently matched
    # nothing, ever (hard-won law 2's shape: built, wired, and doing nothing).
    # The utility's own legacy reference is the identifier a duplicated row in
    # a migration file actually repeats, and it is unique per tenant
    # (BR-AST-049), so it is what the option is now about.
    TARGET_ASSETS_METERS: ("external_ref", "External reference"),
    TARGET_ASSETS_SUBMETERS: ("external_ref", "External reference"),
    TARGET_ASSETS_DEVICES: ("external_ref", "External reference"),
    # ⚠ **THE CHEQUE NUMBER, AND NOT THE ACCOUNT.** Two rows naming one account
    # are ordinarily two real payments — a customer paying twice in a month is
    # not a duplicate — so keying on the account would silently drop money the
    # utility banked. What a duplicated line in a remittance file actually
    # repeats is the instrument: one cheque appearing twice is one cheque.
    # (The FILE's own double-import is guarded elsewhere and structurally, by
    # `uq_import_runs_idempotency`; this is the in-file option a clerk ticks.)
    # ⛔ **AND THE CHEQUE NUMBER IS SCOPED TO ITS ACCOUNT — `DEF-PAY-10697`
    # (lockbox audit LBX-08, 2026-10-30).** A cheque number is the PAYER's
    # chequebook number, so two customers can both send cheque 1042; keyed on
    # the reference alone this option dropped one of them as a "duplicate" —
    # a real customer's payment silently gone. `DEDUPE_SCOPE_BY_TARGET` below
    # adds the account to the key.
    TARGET_PAYMENTS: ("reference", "Reference"),
}

#: A second mapped field the *keep latest* key is SCOPED by, where the identity
#: in `DEDUPE_KEY_BY_TARGET` is unique only within it. `DEF-PAY-10697`: a
#: cheque number is unique per ACCOUNT, never across a file.
DEDUPE_SCOPE_BY_TARGET: dict[str, str] = {
    TARGET_PAYMENTS: "account_ref",
}


def _dedupe_key_of(target: str, mapped: dict[str, Any] | None) -> Any:
    """The *keep the latest row* key of one mapped row, or None when it has none."""
    key_field, _label = DEDUPE_KEY_BY_TARGET[target]
    value = (mapped or {}).get(key_field)
    if not value:
        return None
    scope_field = DEDUPE_SCOPE_BY_TARGET.get(target)
    if scope_field is None:
        return value
    scope = str((mapped or {}).get(scope_field) or "").strip().lower()
    return (scope, str(value).strip().lower())

TRUE_TOKENS = frozenset({"true", "t", "yes", "y", "1", "inside", "inside city limits"})
FALSE_TOKENS = frozenset({"false", "f", "no", "n", "0", "outside", "outside city limits"})


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _audit(actor: Any, action: str, entity_id: Any, **after: Any) -> None:
    """BR-MET-048 — who, when, and what changed, on every stage.

    A stage writes only run rows, but it is still a recorded act by a named
    person against a tenant's data, and the receipt claims exactly that
    (`RUN BY · SESSION · IP`). An audit trail that starts at stage 4 could not
    answer *who uploaded this file* for a run that never loaded.
    """
    core_audit.write_row(
        action=action,
        entity_type="import_run",
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after=after,
    )


def _refuse(code: str, *, message_key: str, **params: Any) -> None:
    """⚠ `message_key` is KEYWORD-ONLY (`DEF-546`): passed positionally, G32's
    scan cannot see it, so seven refusals shipped whose keys existed in no
    catalogue and rendered as silence. The signature now makes the visible
    form the only form that compiles."""
    raise errors.ValidationError(code, message_key=message_key, params=params)


def _text(value: Any, limit: int = 255) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] if cleaned else None


# ═══════════════════════════════════════════════════════════════════════════
# THE COLUMNS ENDPOINT (B15 §12 row 2) — BR-MET-088
# ═══════════════════════════════════════════════════════════════════════════


def _model_for(target: str) -> Any:
    """The table a target writes. ⚠ Two entries, one lookup — `BR-MET-096`."""
    model = {TARGET_PREMISES: models.Premises, TARGET_UNITS: models.Unit}.get(target)
    if model is not None:
        return model
    raise errors.ValidationError(  # pragma: no cover — stage 1 refuses first
        errors.VAL_UNKNOWN_LOOKUP,
        message_key="metering.import.kind_unknown",
        params={"allowed": list(TARGETS)},
    )


def _label_from(name: str) -> str:
    return name.replace("_", " ").capitalize()


def target_columns(target: str) -> list[dict[str, Any]]:
    """Every column this target actually has, plus this tenant's own custom
    fields, plus the explicit `— ignore —` choice (BR-MET-088).

    ⛔ **DECLARED, NOT DERIVED — CHANGED 2026-09-19 BY `DEF-MET-5802`.** This
    docstring read *"DERIVED, NOT LISTED — the names come from the model's own
    `_meta`, so the picker cannot offer a target with no column behind it and
    cannot omit one that exists"*. **Both halves of that guarantee were real
    and the feature was not**: `_meta` also cannot judge whether a column is a
    **utility's to supply**, so nine premises fields and five unit fields
    written by the address-matching process were on every customer's template
    with labels generated from their field names.

    The set now comes from `DECLARED_COLUMNS_BY_TARGET`, and the old
    guarantee's SECOND half — *cannot omit one that exists* — is the one a
    declaration loses for free and has to buy back. It is bought by
    `NOT_OFFERED_COLUMNS_BY_TARGET`, which names every withheld column WITH ITS
    REASON, and by `tests/test_def_met_5802_declared_columns.py`, which fails
    when a model field appears in neither table. **Do not add a column here
    without deciding which of the two tables it belongs in — that decision is
    the feature.**

    `custom_data` is expanded into one entry per DEFINED custom field rather
    than offered whole: a raw JSON blob pasted from a CSV cell is not a field
    map, and B15 §4.2A #14 asks for the tenant's own fields *"by name"*. It is
    listed in the declared tuple at its own position so the expansion keeps its
    place in the file order.

    ⚠ **THE ASSETS TARGETS ARE DECLARED, NOT DERIVED** (CR-028 AST-W3): their
    B16 §4.7b field map includes destinations that are not columns of one
    table — a unit tag is an ASSIGNMENT row (BR-AST-045), a service is a
    SERVICE POINT, a parent is the BR-AST-003 FK — so
    `EXPLICIT_COLUMNS_BY_TARGET` carries the signed map, and the test suite
    pins every column-named entry to a real `Asset` column so the declaration
    cannot drift from the schema (which is BR-MET-088's whole point).
    """
    explicit = EXPLICIT_COLUMNS_BY_TARGET.get(target)
    if explicit is not None:
        columns = [dict(entry) for entry in explicit]
        if target in ASSETS_TARGETS or target == TARGET_ACCOUNTS:
            # `CR-161-BRC10` W3 · `DEF-AST-9171` — one column per active
            # `assets` custom field, after the signed sheet's own columns.
            # `DEF-MET-9239` (2026-10-03) — and one per active `accounts`
            # field on the accounts sheet: the PO named accounts among the
            # imports (*"every import includes one column per custom field"*).
            columns.extend(_custom_field_columns(target))
        columns.append(
            {
                "target": IGNORE,
                "label": "— ignore —",
                "kind": KIND_TEXT,
                "required": False,
                "transforms": [],
            }
        )
        # ⚠ BOTH BRANCHES, and this one is the one that matters: the three
        # assets targets and accounts are DECLARED, so they return here — a
        # readiness note added only to the derived tail below would have been
        # dead on every target that HAS a unit column (hard-won law 2).
        return _with_unit_readiness(_with_date_format(columns))
    # ⚠ **CALLED FOR ITS REFUSAL, NOT FOR THE MODEL.** An unknown target has to
    # fail with `BR-MET-096`'s named ValidationError; reaching
    # `DECLARED_COLUMNS_BY_TARGET[target]` first would raise a bare `KeyError`
    # out of an API path instead.
    _model_for(target)
    columns: list[dict[str, Any]] = []
    for name in DECLARED_COLUMNS_BY_TARGET[target]:
        if name == "custom_data":
            columns.extend(_custom_field_columns(target))
            continue
        override = dict(FIELD_OVERRIDES_BY_TARGET[target].get(name, {}))
        kind = override.pop("kind", KIND_TEXT)
        label = override.pop("label", None) or _label_from(name)
        entry: dict[str, Any] = {
            "target": name,
            "label": label,
            "kind": kind,
            "required": bool(override.pop("required", False)),
            "transforms": list(TRANSFORMS_BY_KIND.get(kind, ())),
        }
        if kind == KIND_ENUM and name == "status":  # premises only — units has none
            entry["options"] = list(PREMISES_STATUSES)
        if kind == KIND_BOOLEAN3:
            # The three-state contract, on the screen rather than only in a
            # docstring: an operator choosing this column has to be told that
            # an empty cell stays empty (BR-RAT-101).
            entry["blank_means"] = "not recorded"
        # DEF-771: a column whose override carries `help` says what it takes,
        # on the picker. ⚠ Explicit, because every other key in `override` is
        # POPPED above and anything left over is DISCARDED — declaring `help`
        # and not reading it here would have been a sentence nobody ever saw,
        # which is the shape of the defect it was written for.
        help_text = override.pop("help", None)
        if help_text:
            entry["help"] = str(help_text)
        # ⛔ **CR-046 C2/C3 — `sample` AND `blank_means` REACH THE DERIVED
        # TARGETS TOO, AND UNTIL 2026-08-27 THEY COULD NOT.**
        # The three assets targets and the accounts target are DECLARED, so
        # `_asset_column` / `_account_column` could put a worked cell beside a
        # column. `premises` and `units` are DERIVED from the model, and this
        # loop read only `label`, `kind`, `required` and `help` — so their
        # identifier columns had no way to say *"ship this cell BLANK"* and
        # `sample_csv` fell through to `SAMPLE_TEXT_VALUES`, which proposed
        # `P-9001` and `1`. Under the ruling those are invented numbers on the
        # one column the PO objected to being asked to invent — `DEF-962`'s
        # exact failure, on the two targets `DEF-962` did not reach.
        #
        # ⚠ **`sample` IS READ WITH `in`, NEVER WITH `.pop(...) or`** — an
        # explicitly declared `""` is the whole point of the mechanism and a
        # truthiness test would discard precisely the case it exists for.
        if "sample" in override:
            entry["sample"] = str(override.pop("sample"))
        blank_means = override.pop("blank_means", None)
        if blank_means:
            entry["blank_means"] = str(blank_means)
        columns.append(entry)
    # ⛔ **CR-058 W3 · BR-MET-1030 — THE VIRTUAL TAIL, AND IT IS APPENDED
    # RATHER THAN DECLARED IN THE OVERRIDES TABLE ON PURPOSE.**
    # `BR-MET-088` says the picker may not offer a column with nothing behind
    # it, and the loop above enforces that by reading the MODEL. These six have
    # nothing behind them in `premises` and never will: they are facts about a
    # PARTY, carried for the length of one run and written to `customers`
    # through the seam. Putting them in `PREMISES_FIELD_OVERRIDES` would not
    # offer them at all — that table only PRESENTS a column the model already
    # has — so a lane that "tidies" them into it silently deletes the feature.
    # Every one is in `_NOT_A_COLUMN`, so none can reach `Premises(**record)`.
    columns.extend(dict(entry) for entry in VIRTUAL_COLUMNS_BY_TARGET.get(target, ()))
    columns.append(
        {
            "target": IGNORE,
            "label": "— ignore —",
            "kind": KIND_TEXT,
            "required": False,
            "transforms": [],
        }
    )
    return _with_unit_readiness(_with_date_format(columns))


def _with_unit_readiness(columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """⛔ **`DEF-1077` — A TENANT WITH NO UNITS IS TOLD SO, IN WORDS.**

    PO verbatim, 2026-08-27: *"when we add assets we have to tie them to units;
    and in CSV file that we download there is not unit ID or unit name that we
    can provide - what about this"*. The column was there. **What the PO was
    actually reading is a fact about their own tenant**: `_sample_reference_
    cells` ships the worked cell blank when there is no unit to name, which is
    `DEF-962`'s correct refusal to invent `U-00001` — and a blank cell in a
    column whose blank is ALSO LAWFUL (`BR-AST-045`: it loads to inventory) is
    the product stating that fact in the one way nobody can read.

    ⚠ **SO THIS IS NOT COPY ABOUT A COLUMN — IT IS A READING OF THE TENANT**,
    and it is drawn only when it is TRUE. The mirror matters as much as the
    sentence: a tenant that has units gets no key at all, so an operator who
    sees it knows it means them. Same posture as `_with_date_format` one
    function up — a tenant declaration stamped onto the offered columns, ONE
    query for the whole answer (`DEF-324`), and skipped entirely for a target
    with no unit column so premises and units never pay for it.

    ⚠ **AND ONE QUERY PER REQUEST, NOT PER ROW — CHECKED, BECAUSE `DEF-1075`
    IS EXACTLY THIS SHAPE.** `target_columns` has four call sites and every one
    is once per request: `api.import_columns`, `sample_columns`, the
    unmapped-required refusal in `_validate_locked`, and `_columns_by_target`
    (itself called once by `_auto_map` and once by `_transform_locked`).
    Nothing here runs inside a row loop. A future caller that puts it in one
    turns this `EXISTS` into `rows × 1` round trips, which is invisible at test
    latency and fatal at 15–20ms — read `DEF-1075` before doing it.

    The words name the BUILD ORDER, because that is the only next step that
    works: J20 step 1 and the README both run Premises → Units → Assets, and
    `BR-CUS-047` makes a row naming a missing unit an error rather than an
    auto-create. Telling an operator "leave it blank" would be true and would
    seat twenty meters nowhere, which is `DEF-1079`'s pairing.
    """
    if not any(entry["kind"] == KIND_UNIT_REF for entry in columns):
        return columns
    has_units = models.Unit.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True).exists()
    if has_units:
        return columns
    for entry in columns:
        if entry["kind"] == KIND_UNIT_REF:
            entry["blank_reason"] = (
                "There are no units in this utility yet, so this column has "
                "nothing to name. Import Premises first, then Units, then run "
                "this import again — a unit named here has to exist already."
            )
    return columns


def _with_date_format(columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """**BR-MET-117 (3)** — every offered DATE column carries the format it will
    be read as, so the mapping screen can print it beside the column.

    PO verbatim: *"or when date matching happen at transform level - show the
    format - and in case any issue highlight it there itself"*. The operator met
    the alternative: 9,881 rows mapped, `Matched` against every column, and the
    date problem revealed one whole stage later as 9,881 identical rejects. A
    picker that says `Matched` about a column it cannot actually read is the
    defect; the reject list is only where it surfaced.

    `None` when the tenant has selected no format — which is a real state the
    screen must be able to draw, not a gap to fill with a guess (`_date_problem`).
    """
    declared = seams.tenant_date_format()
    for entry in columns:
        if entry["kind"] == KIND_DATE:
            entry["date_format"] = declared
    return columns


def _custom_field_columns(target: str) -> list[dict[str, Any]]:
    """The tenant's OWN defined fields, as mapping targets (B15 §4.2A #14).

    *"Every legacy system has columns ours does not, and this is where they
    go."* Safe by construction: DB-17 forbids any money path from reading
    `custom_data`. Cross-module READ of tenancy's definition table, which is
    the sanctioned direction (B2 §2) — the same one `premises.area` takes.
    """
    from apps.tenancy import models as tenancy_models

    # `CR-161-BRC10` — an asset sheet's target is not the record type its
    # fields are defined on (`assets_meters` → `assets`).
    entity = CUSTOM_FIELD_ENTITY_BY_TARGET.get(target, target)
    rows = tenancy_models.CustomField.objects.filter(
        tenant_id=_tenant_id(), entity=entity, is_active=True
    ).order_by("display_order", "key")
    return [
        {
            "target": f"custom_data.{row.key}",
            "label": row.label,
            "kind": KIND_CUSTOM,
            # ⚠ **NEVER REQUIRED, WHATEVER THE FIELD SAYS (`DEF-MET-9172`).**
            # This read `bool(row.is_required)`, so a required premises field
            # refused the whole mapping as `required_column_unmapped` for a
            # file without that column. PO Rules table 2026-10-02: *"A required
            # field never blocks a screen that doesn't show it"* — and an
            # import is not a screen. A blank cell loads; a bad one is judged by
            # `_judge_custom_cells`.
            "required": False,
            "transforms": list(TRANSFORMS_BY_KIND[KIND_CUSTOM]),
            "custom_field": True,
        }
        for row in rows
    ]


def _columns_by_target(target: str) -> dict[str, dict[str, Any]]:
    return {column["target"]: column for column in target_columns(target)}


#: `CR-025` — example values for the sample file, by FIELD NAME, text kinds
#: only. ⚠ These are CELL VALUES, never columns: the header row derives from
#: `target_columns`, so a column added to the model appears in the sample the
#: same day with a kind-generic value, and a column removed disappears — the
#: drift `DEF-521` warns about cannot reach the header. A name missing here
#: falls back to `Sample <label>`.
SAMPLE_TEXT_VALUES: dict[str, str] = {
    "premise_no": "P-9001",
    "name": "Sample Building",
    "address_line": "12 Sample Street",
    "city": "Springfield",
    "state": "TX",
    "postal_code": "75001",
    "owner_manager": "Sample Owner LLC",
    "external_ref": "LEGACY-9001",
    "unit_no": "1",
    "label": "Unit 1",
    "floor_label": "1",
}


#: `CR-025` — the one worked date every sample cell is built from. A CONSTANT
#: rather than `date.today()`: a sample whose contents change with the calendar
#: cannot be diffed, and BR-TEN-043's reasoning applies here too — a date the
#: operator did not choose should never be one they can load by accident.
SAMPLE_DATE = date(2026, 1, 1)


def _sample_date(date_format: str | None) -> str:
    """**DEF-754** — the sample writes its dates in THE TENANT'S OWN DECLARED
    FORMAT, from the same single declaration stage 2 reads.

    The sample used to emit `2026-01-01` unconditionally while stage 2 told a
    US tenant, correctly, that their dates are read as `MM/DD/YYYY`
    (`BR-MET-117`). **It worked, which is why it survived**: ISO always parses,
    so the sample never failed and no test could see the contradiction. The
    cost was to trust — an operator who takes the sample as their template and
    then reads a different format on the next screen has no way to know which
    of the two to believe.

    ⚠ **THE UNSET CASE STAYS ISO, DELIBERATELY.** A tenant that has declared no
    format has nothing for this to read, and `_parse_date` tries ISO before it
    tries anything else — so ISO is the one cell that is still guaranteed to
    load. Writing a cell in a format nobody declared would be a sample that
    fails its own import (case 4 below), which is worse than the contradiction
    this fixes.

    ONE declaration (`tenant_settings.date_format`), TWO consumers (this and
    `_parse_date`), reading the SAME `DATE_FORMAT_PATTERNS` map — hard-won law
    5's shape, applied to a format instead of a file.
    """
    pattern = DATE_FORMAT_PATTERNS.get(str(date_format or ""))
    return SAMPLE_DATE.isoformat() if pattern is None else SAMPLE_DATE.strftime(pattern)


def _sample_date_from(iso_value: str, date_format: str | None) -> str:
    """A column's OWN declared sample date (`sample="2027-01-01"`), re-written
    in the tenant's format. The assets targets declare their worked cells
    beside the column and so never reached the kind branch — the same
    contradiction, in three more files than DEF-754's title names."""
    if not iso_value:
        return ""
    try:
        parsed = date.fromisoformat(iso_value)
    except ValueError:  # pragma: no cover — a declared sample is authored ISO
        return iso_value
    pattern = DATE_FORMAT_PATTERNS.get(str(date_format or ""))
    return parsed.isoformat() if pattern is None else parsed.strftime(pattern)


def _preferred_sample_code(index: dict[str, str], prefer: tuple[str, ...] = ("residential",)) -> str:
    """One code out of a tenant's own lookup index, for a worked sample cell.

    `index` is the `{lowered code or name: code}` map the `KIND_LOOKUP` branch
    of `_map_row` resolves against, so anything this returns is a value that
    tenant's OWN import can resolve — which is the whole point, and is the bug
    this lane shipped for one test run when `owner_category` had no index at
    all.

    ⚠ **THE MOST ORDINARY CODE WHERE THE TENANT HAS ONE.** Not decoration: it
    is the one a reader recognises without looking anything up, the same
    reasoning the connection-size cell states for choosing the smallest
    ratified size. `prefer` is matched as a substring and in order, so a
    utility that renamed `residential` to `residential_metered` still gets it.
    Where none matches, the first code in sorted order — deterministic, because
    a sample that reorders itself between two downloads cannot be diffed.

    ⚠ **EMPTY WHEN THE TENANT HOLDS NOTHING**, which is honest rather than a
    fallback: there is no code to demonstrate, and an invented one would be a
    cell the tenant's own stage 3 cannot resolve.
    """
    codes = sorted({str(code) for code in index.values() if str(code or "").strip()})
    if not codes:
        return ""
    for wanted in prefer:
        for code in codes:
            if wanted in code.lower():
                return code
    return codes[0]


def _sample_reference_cells() -> dict[str, str]:
    """The tenant's OWN first unit, premises and master meter — the worked
    cells the three REFERENCE kinds show in a downloaded template (`DEF-962`).

    ⚠ **THIS IS CR-036 (i)'s RULING, APPLIED TO A REFERENCE INSTEAD OF A
    VOCABULARY.** `sample_csv` already argues the case for `services_available`
    and it is the same argument: a cell shipped `""` *"for the reason that a
    tenant's own data is never guessed"* produced the incident, because a blank
    that is ALSO A LAWFUL VALUE cannot be told apart from a cell that worked.
    For a unit it is worse than it was for services — `BR-AST-045` says a blank
    unit loads to INVENTORY — so an operator who fills the template in gets a
    clean rehearsal, twenty created rows and twenty meters seated nowhere.

    A row this tenant already has is not a guess. It is the same index
    `AST.UNIT_ON_FILE` / `AST.PREMISES_ON_FILE` / `AST.PARENT_ON_FILE` judge
    every imported row against, so the cell demonstrates the link AND survives
    the tenant's own validation.

    ⚠ **BLANK WHEN THERE IS GENUINELY NOTHING TO READ, and that is the honest
    answer rather than a fallback.** A tenant with no units yet cannot link a
    meter to one; the build order is Premises → Units → Assets (README), and a
    template that invented `U-00001` would teach the opposite.

    ⚠ **DETERMINISTIC** (`order_by`), because a sample that reorders itself
    between two downloads cannot be diffed — the same reason the list cell is
    `sorted`. ONE query each, for the whole file (`DEF-324`).
    """
    unit_no = (
        models.Unit.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .exclude(unit_no__isnull=True)
        .exclude(unit_no="")
        .order_by("unit_no")
        .values_list("unit_no", flat=True)
        .first()
    )
    premise_no = (
        models.Premises.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .exclude(premise_no__isnull=True)
        .exclude(premise_no="")
        .order_by("premise_no")
        .values_list("premise_no", flat=True)
        .first()
    )
    # ⚠ THROUGH THE SEAM. `assets` is another module's table (B1/B2 r4) and the
    # index it publishes is the one the runner's own dry run reads, so the
    # parent this cell names is a parent `AST.PARENT_ON_FILE` will accept:
    # BR-AST-003 allows only a meter or a net-meter, and only an ACTIVE one.
    parents = sorted(
        str(entry["asset_no"])
        for entry in seams.assets_import_index().values()
        # ⚠ THE SAME PREDICATE `_eval_parent_meter_on_file` USES, not a
        # second statement of it: meter or net-meter, and `in_service` —
        # `"active"` is the STAGE CODE and `in_service` is its behavior class,
        # and naming the wrong one here would offer a parent the rule refuses.
        if entry.get("type_code") in ("meter", "net_meter")
        and entry.get("behavior_class") == "in_service"
    )
    # ⛔ **THERE IS NO `owner_name` HERE, AND IT WAS ADDED AND REMOVED ON THE
    # SAME DAY — THE DISTINCTION IS WORTH THE PARAGRAPH.** It briefly read the
    # tenant's own first typed owner, on this function's own reasoning: a row
    # this tenant already has is not a guess, fires no rule, and demonstrates
    # the reuse `BR-MET-150`'s unique-name index exists to force.
    #
    # **That reasoning is right for a REFERENCE and wrong for a NAME**, and the
    # difference is whether anything has to RESOLVE. A unit ref, a premise no
    # and a parent asset must name a row that exists or the sample row cannot
    # load; `owner_account_verdict` reads the owner as FREE TEXT, and a name not
    # already on file is the ordinary first-migration case. Nothing resolves, so
    # nothing needs to be real.
    #
    # ⚠ **AND READING IT COST TWO THINGS.** On the beta tenant the cell came
    # out `Creekside Laundromat` — a real `premises_owners` row — beside
    # `person` and `owner_occupier`, so the file a utility is handed to copy
    # **filed a business as an individual**, which is the very mistake
    # `PRM.OWNER_IDENTITY_MISMATCH` exists to catch. It only passed because a
    # phone is a valid identifier for a person; the same row with a Tax ID
    # answers `identity_mismatch`. **And it put a customer's real owner name in
    # a file any operator can download**, where loading it unmodified attaches a
    # property to a real party — beside `Sample Building`, `12 Sample Street`
    # and `555-0142`, which are fiction. The sample's name is fiction too now.
    return {
        "unit_ref": str(unit_no or ""),
        "premise_no": str(premise_no or ""),
        "asset_ref": parents[0] if parents else "",
    }


def sample_notes(target: str) -> dict[str, Any]:
    """⛔ **`DEF-1077` — WHAT THE TEMPLATE'S COLUMNS TAKE, SAID BEFORE THE FILE
    IS FILLED IN.**

    PO verbatim, 2026-08-27: *"when we add assets we have to tie them to units;
    and in CSV file that we download there is not unit ID or unit name that we
    can provide - what about this"*.

    The three shapes `resolve_unit_ref` accepts — the unit NUMBER, a premises
    and label pair, or a bare label unique in this utility — have been a `help`
    sentence on the column since 2026-08-27, **and stage 2 is where they were
    drawn**. Stage 2 is one stage too late: by then the operator has already
    invented a format, filled in every row and uploaded it. This is the same
    sentences, at the moment the file is DOWNLOADED, which is the only moment
    they change what someone types.

    ⚠ **ONLY THE COLUMNS THAT HAVE SOMETHING TO SAY.** A screen that draws a
    row per column is a wall an operator learns to scroll past; a screen that
    draws three is read. And when a column has nothing declared it contributes
    nothing here, so the notes panel disappears rather than rendering an empty
    box — the same posture `ImportProgressPanel` takes on a small file.

    The words are the SERVER'S in both keys, deliberately: a screen that writes
    its own copy about a matcher it cannot see is how `DEF-771`'s two halves
    came apart. `blank_reason` is a reading of THIS TENANT (see
    `_with_unit_readiness`) and is present only when it is true.
    """
    if target not in TARGETS:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.kind_unknown",
            allowed=list(TARGETS),
        )
    columns = [
        {
            "target": entry["target"],
            "label": str(entry["label"]),
            "required": bool(entry.get("required")),
            "help": str(entry.get("help") or ""),
            "blank_reason": str(entry.get("blank_reason") or ""),
        }
        for entry in sample_columns(target)
        if entry.get("help") or entry.get("blank_reason")
    ]
    return {"target": target, "filename": f"{target}_sample.csv", "columns": columns}


def sample_columns(target: str) -> list[dict[str, Any]]:
    """The columns the downloadable sample actually writes, IN FILE ORDER.

    ⚠ **PUBLISHED BECAUSE THE HEADER IS NO LONGER THE FIELD NAME (`DEF-1077`).**
    While the header row WAS `entry["target"]`, anything wanting the field order
    could read it straight out of the file — and a dozen tests did, with
    `dict(zip(header, example))`. The header is now the operator's LABEL, so the
    field order has to come from somewhere; deriving it a second time beside
    `sample_csv` is how `DEF-616` happened (one list maintained next to
    another). This IS that list.

    The tenant's own custom fields and `— ignore —` are excluded from THIS
    list: `ignore` is a mapping choice rather than a column, and the custom
    fields are the tenant's, appended by `sample_csv` itself AFTER these
    (`DEF-MET-9233` — this list stays the platform's own columns, which is what
    its callers zip against fixed rows). ⚠ It read *"a sample cannot know a
    tenant's own field keys"* until 2026-10-03; the sample is built per tenant
    at request time, so that was never true.
    """
    return [
        entry
        for entry in target_columns(target)
        if entry["target"] != IGNORE and not entry.get("custom_field")
    ]


def sample_csv(target: str) -> tuple[str, str]:
    """`CR-025` — `(filename, body)` for stage 1's sample download.

    PO 2026-08-21, verbatim: *"also we will need sample CSV files to be
    downloaded at every import at step 1"*. One runner, two targets
    (`BR-MET-096`), so the sample takes its target as a parameter exactly as
    the field map does.

    **The header row IS `target_columns`' answer** (BR-MET-088, and CR-025's
    own step 2: a hand-written sample drifts the first time a column is
    added): every real column, comma-joined, in model order, then ONE column
    per active custom field of this tenant's (`DEF-MET-9233`, PO 2026-10-02:
    *"every import includes one column per custom field"*) — `— ignore —`
    excluded, because it is a mapping choice, not a column.
    ⚠ **The headers are the columns' LABELS since 2026-08-28 (`DEF-1077`)** —
    `Unit`, not `unit_ref` — and stage 1 still auto-detects every one of them,
    because `_auto_map` derives a column's own label as an alias. See the
    comment at the `writerow` below for what that change cost and why it is
    safe now.

    **One example row, not headers only** — the judgment CR-025 step 5 left
    open, decided with the repo's own precedent: `reads_template.csv` shipped
    header-plus-one-worked-row from BR-MET-032 until CR-038 W4, which added a
    second because a demand meter is TWO records (BR-MET-049). ⚠ **THIS
    SENTENCE READ "has shipped … since BR-MET-032" UNTIL 2026-09-08**, which
    was true when it was written and stopped being true the day the peak row
    landed; `read_import.template_csv` reported the drift in its own docstring
    for a fortnight rather than fixing it here, and `CR-077` closes it. THIS
    file's sample is still ONE row per target and the precedent still holds —
    what moved is the file being cited, not the judgment. Lookup cells carry a
    ratified SEED code (BR-MET-034 / BR-MET-084) so the example validates
    clean. Someone uploading it unedited is protected by the workflow itself:
    nothing writes before the stage-4 commit, and the dry-run states what one
    sample row would do.

    ⚠ **THIS PARAGRAPH USED TO END *"tenant-specific cells (area, services) are
    left empty rather than guessed"*, AND THAT SENTENCE HAS NOW BEEN WRONG
    TWICE.** CR-036 (i) / DEF-754 struck the services half — a tenant's own
    enablement is a declaration, not a guess — and `DEF-962`/`DEF-963` struck
    the rest of it. What is read from the tenant, and where:

      * `services_available` (list) and `service` (lookup) — their own enabled
        codes, `seams.enabled_service_codes()`;
      * `unit_ref`, `premises`, `parent_asset_no` — their own first unit,
        premises and active master, `_sample_reference_cells()`.

    What is still EMPTY, and why: an `area` (free text a tenant invents, with
    no declaration to read), a plan code (BR-MET-098 — absent loads unplanned),
    and any reference on a tenant that has none of that kind on file yet, which
    is the honest statement that the build order runs Premises → Units →
    Assets.
    """
    from apps.metering import services as metering_services

    if target not in TARGETS:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.kind_unknown",
            allowed=list(TARGETS),
        )
    seed_codes = {
        "premises_type": metering_services.SEED_PREMISES_TYPES[0][0],
        "unit_type": metering_services.SEED_UNIT_TYPES[0][0],
    }
    # ONE read each, for the whole file (DEF-324's lesson): the tenant's date
    # declaration and the tenant's service enablement.
    declared_format = seams.tenant_date_format()
    # ⚠ **THE LIST CELL IS THE TENANT'S OWN ENABLEMENT, AND THAT IS THE CR-036
    # (i) FIX (DEF-754's second half).** This shipped `""` with the reasoning
    # *"tenant-specific vocabularies — never guessed"*. The reasoning is right
    # and its RESULT was the incident: a file built from this sample carries the
    # `services_available` header, maps it, reads `Matched`, and loads every
    # premises with no services at all — the ONE input in the whole importer
    # that fails silently (`_empty_columns`).
    #
    # **Enabled service codes are not a guess.** They are the tenant's own
    # declaration, and the same set `BR-MET-003` measures every imported row
    # against — so a sample carrying them is a row that validates clean by
    # construction, on THIS tenant and no other. `sorted` because the seam
    # answers a `set` and a sample that reorders itself between downloads
    # cannot be diffed.
    #
    # ⚠ It is still an EXAMPLE, not an instruction: an operator whose premises
    # sell a subset edits the cell, exactly as they edit the address. What they
    # can no longer do is take a sample whose blank cell is indistinguishable
    # from a cell that worked.
    service_codes = ",".join(sorted(seams.enabled_service_codes()))

    # DEF-962/DEF-963/DEF-935 — read ONCE for the whole file, like the two
    # above. `units_by_service` is the SAME map stage 3's AST.SERVICE_HAS_UNIT
    # judges with, so the sample and the rule cannot disagree.
    references = _sample_reference_cells()
    # ⛔ **THE OWNER BLOCK'S TWO LOOKUP CELLS, READ FROM THIS TENANT.**
    # A literal `residential` / `landlord` here would be `DEF-963`'s defect one
    # column along — a template the product's own import cannot resolve on a
    # utility that renamed its lists — and it would ship the very bug this
    # lane found: a `KIND_LOOKUP` cell that resolves to `None` still maps, still
    # reads `Matched`, and quietly creates nothing.
    #
    # ⚠ **RESIDENTIAL FIRST WHERE THE TENANT HAS IT, else the first code**,
    # which is the reasoning the `size_class` cell already uses two branches
    # down: *"the smallest connection is the residential one a reader
    # recognises"*. Deterministic (`sorted`), because a sample that reorders
    # itself between two downloads cannot be diffed.
    #
    # ⚠ **BLANK IS THE HONEST FALL-THROUGH** for a tenant holding no owner
    # categories at all: the row then loads its address and its account and
    # says at rehearsal that no owner record was created, which is true and is
    # what `PRM.OWNER_CATEGORY_MISSING` is for.
    if target == TARGET_PREMISES:
        seed_codes["owner_account_type"] = _preferred_sample_code(
            seams.account_lookup_indexes().get("account_type", {})
        )
        # ⚠ **`owner_occupier` THEN `landlord`** — the two an operator reading a
        # sample recognises instantly, and the two that describe the ordinary
        # case. Without a preference the first sorted code wins and the shipped
        # row read `builder`, which is a real category and a strange thing for
        # the template to demonstrate. Substring-matched, so a renamed code
        # still lands; first sorted otherwise, so a tenant that deleted both
        # still gets a cell that resolves.
        seed_codes["owner_category"] = _preferred_sample_code(
            _owner_category_index(), prefer=("owner_occupier", "owner-occupier", "landlord")
        )
    units_by_service = seams.service_default_uoms()
    # ⚠ **THE TENANT'S OWN SERVICE, FOR THE TWO MEASURING TARGETS' `service`
    # CELL (DEF-963) — AND THE FIRST ONE THAT CAN ACTUALLY CARRY A METER
    # (DEF-935).** CR-025 asks for a WORKED row, and a cell that this tenant's
    # own stage 3 rejects is not one. Four of the ten catalog services carry no
    # unit (`tenancy.selectors.service_default_uoms` names them: sewer, solar,
    # thermal/heat, battery), and a meter for a service with no unit cannot
    # store a reading at all — CLAUDE.md rule 3. Ottumwa Water Works sells
    # water, sewer and trash; `sorted` alone would have written `sewer` and the
    # template would reject on its own tenant, one stage earlier than before
    # but still uselessly.
    #
    # ⚠ **THE FILTER IS THE TENANT'S OWN DECLARATION, NOT A PREFERENCE.** It
    # asks the same question `AST.SERVICE_HAS_UNIT` asks, off the same map, so
    # the cell and the rule cannot disagree. When NO enabled service has a
    # unit the first enabled code is written anyway rather than a blank: the
    # row then rejects at stage 3 with a sentence naming the service and the
    # Settings screen, which tells the operator what to fix. A blank would
    # merely say "this row names no service" and send them looking in the
    # wrong place.
    # ⚠ **`DEF-MET-9056` — A UNIT IS NOT ENOUGH SINCE `CR-081`.** Sewer has had
    # one since 2026-09-08 (90% of the water volume) and still has no meter, so
    # on Ottumwa `sorted` put `sewer` first again and the worked row was a sewer
    # meter with a blank size. The service must also be BILLED ON A METERED
    # BASIS — the tenant's own declaration; `None` (unpublished) filters nothing.
    metered = seams.metered_service_codes()
    measurable = [
        code
        for code in sorted(units_by_service)
        if units_by_service.get(code) and (metered is None or code in metered)
    ]
    enabled_codes = service_codes.split(",") if service_codes else []
    seed_codes["service"] = (
        measurable[0] if measurable else (enabled_codes[0] if enabled_codes else "")
    )
    # ⛔ **`DEF-AST-8364` — THE DEVICES ROW PICKS ITS TYPE AND ITS SERVICE AS
    # ONE PAIR.** The type column declared `backflow` and the service cell took
    # the pick above — the first service with a unit, alphabetically — so on a
    # tenant selling electric the worked row was a backflow preventer on an
    # Electric connection sized `E-1P-100`, and on Ottumwa (water · sewer ·
    # trash) a backflow on SEWER. It loaded, which is why nothing caught it;
    # it taught the operator a pairing that is nonsense. The plan's devices
    # are billed under ONE service each, so the first pair THIS tenant can
    # hold — the service enabled AND the type in its own device list — is the
    # worked row, and the size and unit below then follow that service.
    # No pair (a tenant selling none of the three) keeps the pick above.
    if target == TARGET_ASSETS_DEVICES:
        device_types = set(seams.assets_lookup_index("device_types").values())
        pair = next(
            (
                (kind, service)
                for kind, service in SAMPLE_DEVICE_PAIRS
                if service in enabled_codes and kind in device_types
            ),
            None,
        )
        if pair is not None:
            seed_codes["type"], seed_codes["service"] = pair
    # ⛔ **THE CONNECTION-SIZE CELL — BR-MET-530, and it is `DEF-963`'s lesson
    # applied BEFORE the defect rather than after it.** A literal `W-58` here
    # would be a template that the product's own import rejects on a utility
    # that does not sell water, which is exactly what the hardcoded `electric`
    # service cell did. So the cell is the INTERSECTION of two facts the tenant
    # already stated: the sizes BR-TEN-171 ratified for the service THIS sample
    # row names, and the rows this tenant actually has ACTIVE on its own S8
    # card. First match wins — the ratified tuples are smallest-first, and the
    # smallest connection is the residential one a reader recognises.
    #
    # ⚠ **BLANK IS THE CORRECT FALL-THROUGH AND IS NOT A GAP.** A tenant selling
    # only sewer (ruled to have no sizes), or one that deactivated the ratified
    # rows, gets an empty cell — and an empty cell LOADS (BR-AST-500: blank is
    # lawful). That is what keeps the shipped sample surviving its own import
    # (`DEF-616`) on every tenant rather than on the ones we happened to test.
    #
    # Guarded on the target because the other four samples carry no size column
    # and this is two reads: the premises template must not pay for a lookup it
    # cannot print (DEF-324's posture, one function along).
    # ⛔ Plan U11 (2026-09-30) — the devices sheet carries a size too, and every
    # asset sheet a unit of measure: the unit cell is the SAME service's own
    # unit (`units_by_service`, the map `AST.SERVICE_HAS_UNIT` judges with), so
    # the worked row passes `AST.UOM_FOR_SERVICE` by construction.
    if target in ASSETS_TARGETS:
        seed_codes["unit"] = units_by_service.get(seed_codes["service"]) or ""
    if target in (TARGET_ASSETS_METERS, TARGET_ASSETS_DEVICES):
        tenant_sizes = seams.service_size_class_index()
        seed_codes["size_class"] = next(
            (
                code
                for code in seams.ratified_size_class_codes(seed_codes["service"])
                if code.lower() in tenant_sizes
            ),
            "",
        )

    def cell(entry: dict[str, Any]) -> str:
        name, kind = entry["target"], entry["kind"]
        if name == "type" and seed_codes.get("type"):
            # `DEF-AST-8364` — the devices row's type is chosen WITH its
            # service above, so it wins over the column's declared `backflow`.
            return seed_codes["type"]
        if "sample" in entry:
            # The assets targets declare their worked cell beside the column
            # (CR-025's header-plus-one-worked-row, per B16 §4.7b). A DATE
            # among them is still written in the tenant's own format (DEF-754).
            #
            # ⚠ **THE KEY IS PRESENT ONLY WHEN A SAMPLE WAS DECLARED
            # (`DEF-962`).** It used to be written unconditionally by
            # `_asset_column`, which made this branch swallow every declared
            # column and left the kind-aware worked values below unreachable
            # for all four explicit targets. A column that declares `""` on
            # purpose still lands here and still ships blank.
            declared = str(entry["sample"])
            if kind == KIND_DATE:
                return _sample_date_from(declared, declared_format)
            return declared
        if kind == KIND_LOOKUP:
            return seed_codes.get(name, "")
        if kind == KIND_ENUM:
            options = list(entry.get("options") or ())
            return "active" if "active" in options else (options[0] if options else "")
        if kind in (KIND_BOOLEAN3, KIND_BOOLEAN):
            return "yes" if kind == KIND_BOOLEAN3 else "no"
        if kind == KIND_INTEGER:
            return "850"
        if kind == KIND_DATE:
            return _sample_date(declared_format)
        if kind == KIND_PREMISE_REF:
            # A units row loads under an EXISTING premise (BR-MET-086). THIS
            # TENANT'S OWN first premise when they have one (DEF-962) — which
            # both demonstrates the ordering and survives `PRM`/`AST`'s
            # on-file rules — and otherwise the premises sample's own ID, so a
            # tenant with nothing on file still sees the two files line up.
            return references["premise_no"] or SAMPLE_TEXT_VALUES["premise_no"]
        if kind == KIND_UNIT_REF:
            # BR-AST-045's cell, and the PO's whole report: a meter is linked
            # to a place by NAMING A UNIT here. Blank is lawful and means
            # inventory, which is exactly why a blank one cannot be left to
            # stand for a worked example (DEF-962).
            return references["unit_ref"]
        if kind == KIND_ASSET_REF:
            # BR-AST-003 — a sub-meter REQUIRES its master, and the column is
            # `required=True`, so a template shipping this blank has a worked
            # row that can never load (DEF-962).
            return references["asset_ref"]
        if kind == KIND_DECIMAL:
            # A quantity with no declared sample is one whose blank MEANS
            # something (`allocation_share_pct` → metered, not allocated;
            # `export_capacity_kw` → not an exporting device). Empty, never
            # prose: the text fallback at the bottom of this function would
            # write "Sample allocation share %" into a numeric cell and the
            # row would be rejected at stage 2 for not being a number.
            return ""
        if kind == KIND_PLAN_REF:
            return ""  # plan codes are the tenant's own; absent loads UNPLANNED (BR-MET-098)
        if kind == KIND_LIST:
            # `services_available` is the only list column in the product; a
            # future one would be a different vocabulary with a different
            # source, so it is named rather than assumed.
            return service_codes if name == "services_available" else ""
        if kind in (KIND_AREA, KIND_CUSTOM):
            # Still empty, and still for the original reason: an AREA is free
            # text the tenant invents, and a custom field's values are its own.
            # There is no declaration to read either of them from.
            return ""
        if kind == KIND_OWNER_REF:
            # ⛔ **THIS CELL SHIPPED BLANK AND THAT IS WHAT MADE THE SAMPLE
            # MODEL THE REPORTED FAILURE.** The note here read: *"an owner NAME
            # the tenant has not typed yet cannot be sampled either, and a
            # made-up one would be worse than blank — a fictional party would
            # fire `PRM.OWNER_NOT_ON_FILE` on the one file a first-time operator
            # is told to start from."*
            #
            # **The consequence it was avoiding is a WARNING that loads**
            # (`CR-055`, 2026-08-31: FLAG_ONLY), and the consequence it CAUSED
            # is a sample whose owner section says `person` and then names
            # nobody — which answers `no_owner`, creates no party, no account,
            # and is precisely the complaint that started this work.
            #
            # ⚠ **FICTION, ALWAYS — A NAME IS NOT A LOOKUP.** This briefly read
            # the tenant's own first owner and the reasoning is unpicked in
            # `_sample_reference_cells`: nothing has to RESOLVE for a name, and
            # reading a real one filed a live `premises_owners` row as a
            # `person` in a downloadable file.
            #
            # ⚠ **A NAME NOT ON FILE IS THE FIRST-MIGRATION CASE, WHICH IS THE
            # ONE THAT MATTERS.** With the category cell beside it the party is
            # CREATED and linked — exactly what a first upload needs shown.
            # `PRM.OWNER_NOT_ON_FILE` still says *"No owner record by this name
            # yet"*, which is true and is followed by the record being made.
            #
            # ⚠ **AND IT KEEPS THE ROW COHERENT**, which the real name did not:
            # a PERSON, with a person's placeholder name, identified by a
            # reserved `555` phone. A business name under `person` is the
            # mistake `PRM.OWNER_IDENTITY_MISMATCH` exists to catch, and the
            # sample may not teach it.
            return "Sample Owner"
        return SAMPLE_TEXT_VALUES.get(name, f"Sample {entry['label'].lower()}")

    # ⚠ **`DEF-MET-9233` — AND THE UTILITY'S OWN FIELDS, ONE COLUMN EACH.** This
    # file is built per tenant at request time, so the sentence that kept them
    # out (*"a sample cannot know a tenant's own field keys"*) was never true,
    # and the PO's ruling of 2026-10-02 is *"every import includes one column
    # per custom field"*. Headed with the LABEL like every other column (so the
    # file maps itself through `_auto_map`'s label alias) and EMPTY in the
    # example row (`cell` above: a field's values are the utility's own).
    # `sample_columns` itself is untouched — it is the published field ORDER of
    # the platform's own columns, and its callers zip it against fixed rows.
    columns = sample_columns(target) + _custom_field_columns(target)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    # ⛔ **THE HEADER IS THE COLUMN'S LABEL — `DEF-1077`, LANDED 2026-08-28.**
    #
    # PO verbatim, 2026-08-27: *"when we add assets we have to tie them to
    # units; and in CSV file that we download there is not unit ID or unit name
    # that we can provide - what about this"*. The column WAS there — it was
    # headed `unit_ref` — and that was the whole complaint: the file a
    # first-time operator is told to start from spoke in OUR field names, while
    # `_asset_column("unit_ref", "Unit", …)` has declared the label **"Unit"**
    # since CR-028 and it had never reached a file.
    #
    # ⚠ **THE FILE STILL MAPS ITSELF, AND THAT IS THE HALF WORTH GUARDING.**
    # `_auto_map` derives every column's LABEL as an alias (see there), DERIVED
    # rather than hand-copied into `ALIASES_BY_TARGET` — a hand-kept copy rots
    # on the first label edit, which is `DEF-616`'s exact mechanism.
    # `test_def1077__every_label_header_maps_back_to_its_OWN_field` is the guard,
    # and it asks the STRONGER question than `DEF-616`'s: not *was this header
    # recognised* but *was it recognised as the right column*.
    #
    # ⚠ **WHY IT WAS HELD BACK ON 2026-08-27 AND IS SAFE NOW.** The first
    # attempt measured 11 failed / 12 passed and found a real collision:
    # `premises` mapped the header *Owner* to the FREE-TEXT `owner_manager`, so
    # under label headers *"Owner / manager"* went unmapped while *"Owner"* took
    # its slot — a utility's owner column silently pointed at the wrong
    # destination. `DEF-1247` closed that (the `owner` alias now reaches the
    # TYPED owner and `owner_manager` carries both spacings of its own), and
    # the collision was re-measured across all six targets before this landed:
    # **zero duplicate labels and zero labels that are another column's alias.**
    # The eleven failures were tests reading the sample back with
    # `dict(zip(header, example))`; they now key off `sample_columns(target)`,
    # which is the same list this function writes.
    writer.writerow([str(entry["label"]) for entry in columns])
    writer.writerow([cell(entry) for entry in columns])
    return f"{target}_sample.csv", buffer.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 1 · EXTRACT
# ═══════════════════════════════════════════════════════════════════════════


def file_sha256(payload: bytes) -> str:
    """SERVER-SIDE, over the bytes we received (TC-2).

    A client-supplied hash attests to what the client says it sent, which is
    not the question the receipt answers. Same posture and same one-liner as
    `read_import.file_sha256`.
    """
    return hashlib.sha256(payload).hexdigest()


def _file_bytes(data: dict[str, Any]) -> bytes:
    """The file, as bytes, from either shape the wizard can send."""
    encoded = data.get("content_b64")
    if encoded:
        try:
            return base64.b64decode(str(encoded), validate=True)
        except (binascii.Error, ValueError):
            _refuse(errors.VAL_FORMAT, message_key="metering.read_batch.file_base64")
    content = data.get("content")
    if content is None:
        _refuse(errors.VAL_REQUIRED, message_key="metering.import.file_required")
    return str(content).encode("utf-8")


def _decode(payload: bytes) -> str:
    if len(payload) > CSV_BYTE_CAP:
        raise errors.BizError(
            errors.BIZ_CAP,
            br_ref="BR-MET-038",
            message_key="metering.import.file_too_large",
            params={"max_bytes": CSV_BYTE_CAP},
        )
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        _refuse(errors.VAL_FORMAT, message_key="metering.read_import.file_not_utf8")
        raise  # pragma: no cover — _refuse always raises


def _sniff_delimiter(text: str) -> str:
    header = text.splitlines()[0] if text.splitlines() else ""
    for candidate, name in ((",", "comma"), (";", "semicolon"), ("\t", "tab"), ("|", "pipe")):
        if candidate in header:
            return name
    return "comma"


_DELIMITER_CHARS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|"}


def _auto_map(headers: list[str], target: str) -> dict[str, str]:
    """Suggested `source column → target`, by header (r10's DETECT callout:
    *"Header row recognised as Migration v2. You can still remap at the next
    stage."*).

    A SUGGESTION only. Stage 2 takes what the operator confirms, and a mapping
    the operator never confirmed is never used — which is why the run stores
    `mapping_spec` at stage 2 and not here.
    """
    offered = _columns_by_target(target)
    lowered = {str(header).strip().lower(): header for header in headers}
    mapping: dict[str, str] = {}
    for field_name, aliases in ALIASES_BY_TARGET[target].items():
        if field_name not in offered:
            continue  # the model lost the column — BR-MET-088 wins over the alias
        for alias in aliases:
            header = lowered.get(alias)
            if header is not None and header not in mapping:
                mapping[header] = field_name
                break
    # ⛔ **A COLUMN'S OWN LABEL IS ALWAYS ONE OF ITS ALIASES, BY CONSTRUCTION
    # (`DEF-1077`).** The sample file now writes the LABEL as its header — the
    # PO's complaint was that the downloadable template spoke in our field
    # names (*"there is not unit ID or unit name that we can provide"*) — and
    # the file has to keep mapping itself, which is `DEF-616`'s property.
    #
    # ⚠ **DERIVED, NOT COPIED INTO `ALIASES_BY_TARGET`, AND THE DIFFERENCE IS
    # THE WHOLE POINT.** Hand-adding every label to that table would work
    # today and rot on the first copy change: a label edited in `_asset_column`
    # would silently stop being recognised, which is `DEF-616`'s exact
    # mechanism — an offered set derived from the model beside an alias table
    # kept by hand. Reading the label straight off the offered column makes the
    # two impossible to desynchronise.
    #
    # ⚠ **LAST, AND ONLY INTO A FREE SLOT.** `ALIASES_BY_TARGET` wins wherever
    # the two disagree, so no file that mapped itself before this change maps
    # differently after it — a label is added, never substituted.
    for field_name, column in offered.items():
        if field_name in mapping.values():
            continue
        header = lowered.get(str(column.get("label") or "").strip().lower())
        if header is not None and header not in mapping:
            mapping[header] = field_name
    return mapping


def _allocate_run_no(warnings: list[dict[str, Any]]) -> str | None:
    try:
        return core_numbering.next_number(IMPORT_RUN_SERIES, seams.tenant_today())
    except core_numbering.NumberingError:
        warnings.append({"code": "numbering_series_missing", "series": IMPORT_RUN_SERIES})
        return None


#: DEF-577 — which series each target's own numbers come out of. An import
#: writes the CUSTOMER'S numbers, so these counters have to be told.
TARGET_SERIES: dict[str, tuple[str, str]] = {
    TARGET_ACCOUNTS: (core_numbering.ACCOUNT, "account_no"),
    TARGET_PREMISES: (core_numbering.PREMISES, "premise_no"),
    TARGET_UNITS: (core_numbering.UNIT, "unit_no"),
    # CR-028: all three assets targets write the ONE asset series' numbers
    # (BR-AST-026 — the per-type prefix is display, the sequence is shared).
    TARGET_ASSETS_METERS: (core_numbering.ASSET, "asset_no"),
    TARGET_ASSETS_SUBMETERS: (core_numbering.ASSET, "asset_no"),
    TARGET_ASSETS_DEVICES: (core_numbering.ASSET, "asset_no"),
}


def _issued_numbers_preview(target: str, creating: int) -> dict[str, Any]:
    """CR-046 D1 — what `_issue_target_number` WOULD hand out, without moving
    the counter. `{}` when there is nothing to issue or no series to issue
    from; the caller omits the block rather than printing zeros."""
    # ⛔ **ACCOUNTS ARE EXCLUDED BY NAME (PO ruling 2026-08-27).** They take
    # their number from the file, so there is nothing to project — and a
    # rehearsal printing *"we will issue AC-2026-00001 …"* would promise the
    # operator a renumbering the commit will not perform, on the one identifier
    # their customers actually know.
    if target == TARGET_ACCOUNTS:
        return {}
    entry = TARGET_SERIES.get(target)
    if entry is None or creating <= 0:
        return {}
    series, _field = entry
    series_format = seams.number_series_format(series)
    if series_format is None:
        return {}
    preview = seams.number_series_preview(series, count=creating)
    return dict(preview) if preview else {}


def _refuse_if_number_taken(
    target: str, record: dict[str, Any], number_field: str, row_no: int
) -> None:
    """Step 2.13's assertion, and it REFUSES rather than renumbering.

    ⚠ **A GUARANTEE THAT IS NOT ASSERTED IS A COMMENT (hard-won law 1).**
    `services._allocate_unused_number` already checks the number is free
    tenant-wide and catches the series up if it is not, so in practice this
    cannot fire. It is here because *"cannot fire"* is a claim about two
    functions in two files agreeing, and this is the one that would notice if
    they stopped.

    ⚠ **IT RAISES, WHICH TAKES THE WHOLE TRANSACTION.** That is deliberate and
    it is the safe direction: the alternative — quietly asking the series for
    another number — would paper over a counter that is genuinely out of step
    with the table, and the next hand-typed record would hit the same wall.
    """
    number = str(record.get(number_field) or "").strip()
    if not number:
        return
    model = {TARGET_PREMISES: models.Premises, TARGET_UNITS: models.Unit}.get(target)
    if model is None:  # pragma: no cover
        return
    scope: dict[str, Any] = {number_field: number}
    if target == TARGET_UNITS and record.get("premises_id"):
        # The walkthrough's own wording — *"this premises does not already hold
        # a unit with the issued number"*. Scoped rather than tenant-wide
        # because that is the question step 2.13 asks; the tenant-wide half is
        # `uq_units_tenant_unit_no` and `_allocate_unused_number`.
        scope["premises_id"] = record["premises_id"]
    if model.objects.filter(tenant_id=_tenant_id(), **scope).exists():
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-035",
            message_key="metering.import.issued_number_taken",
            params={"row": row_no, "number": number, "field": number_field},
        )


def _issue_target_number(
    actor: Any, target: str, warnings: list[dict[str, Any]]
) -> str | None:
    """⛔ **CR-046 — ONE NUMBER, OUT OF THIS TENANT'S OWN SERIES, INSIDE THE
    WRITE TRANSACTION** (PO ruling 2026-08-27, widened to all four uploads).

    ⚠ **IT GOES THROUGH `services._allocate_unused_number`, NOT
    `core_numbering.next_number`, AND THE DIFFERENCE IS `DEF-577`.** Two paths
    have historically written a premises/unit number without allocating it, so
    a tenant's counter can stand BEHIND the numbers already in the column — on
    the demo database the `unit` series stood at **102** against units up to
    **U-00420**, and the next "Add unit" answered a 500 with
    `duplicate key value violates unique constraint "uq_units_tenant_unit_no"`.
    That function allocates, checks the number is genuinely free, and on a
    collision catches the series up past everything that exists and allocates
    once more. Calling `next_number` here would re-open exactly that hole on
    the path that now writes almost every number in the table.

    ⚠ **`None` IS A REAL ANSWER AND THE ROW STILL LOADS.** A tenant with no
    series row for this entity gets a `numbering_series_missing` warning and a
    record with a NULL number — which is lawful (`premise_no` and `unit_no` are
    both nullable) and is what the product did before any of this. Refusing the
    load instead would make a missing Settings row block a 428-row migration.
    """
    entry = TARGET_SERIES.get(target)
    if entry is None:
        return None
    series, field_name = entry
    model = {TARGET_PREMISES: models.Premises, TARGET_UNITS: models.Unit}.get(target)
    if model is None:  # pragma: no cover — the other targets write via their own module
        return None
    from apps.metering import services as metering_services

    return metering_services._allocate_unused_number(
        actor, series, warnings, model=model, field=field_name
    )


def _catch_up_target_series(actor: Any, target: str, written: list[str]) -> None:
    """🔒 HUMAN-REVIEW-PENDING (numbering, DEF-577 — row in 12-governance/09-human-review-ledger.md).

    After a load, move the target's number series FORWARD past the numbers this
    run just wrote.

    ⛔ **THIS DOCSTRING SAID THE OPPOSITE OF THE RULING UNTIL 2026-08-27, AND
    AMENDING IT IS HARD-WON LAW 1.** It read: *"An import takes its number FROM
    the customer's file — that is the point of an import, and BR-TEN-035
    forbids renumbering what a customer already has."* The PO then ruled the
    other way for the three ASSETS targets — *"here we should not allow usse to
    fill in Asset ID - we have number system set in the settings, we shoudl
    call that function and get unique number and assign it"* — and a lane
    reading this paragraph would have rebuilt exactly what the ruling removed.

    **THE FUNCTION STAYS AND IS UNCHANGED.** Premises, units and accounts still
    take their identifier from the file (the PO has not ruled on those; the
    question is raised and open), so the counter is still the one thing those
    runs leave stale, and the next ordinary "Add unit" walks it into a row the
    file just created: on the demo database the `unit` series stood at **102**
    against units up to **U-00420**, and DEF-577's measured symptom was a
    duplicate-key 500.

    **ON THE ASSETS TARGETS IT SIMPLY HAS NOTHING TO CATCH UP ON.** Every
    number those runs write came OUT of the series a moment earlier, so the
    counter is already past it. The call is left in place rather than deleted:
    it is a no-op by arithmetic — `sequence_of` of a number the series itself
    issued is at most the counter's current value, and the move is forward-only
    — and removing it would silently re-open the DEF-577 hole the day anything
    on those targets writes a number of its own again.

    Numbers the tenant's own format could not have written are ignored, not
    guessed at (`sequence_of` returns None for them) — a file of `SCW-U-###`
    against a `U-{00000}` series can never collide, so it moves nothing.
    Forward-only: a file of small numbers never pulls a counter back.
    """
    entry = TARGET_SERIES.get(target)
    if entry is None:
        return
    series, _field = entry
    _catch_up_series(actor, series, written)


def _catch_up_series(actor: Any, series: str, written: list[str]) -> None:
    """🔒 HUMAN-REVIEW-PENDING (numbering, DEF-577 · DEF-2593).

    The arithmetic half of `_catch_up_target_series`, taken out of it so a
    SECOND series can use it without a second copy.

    ⚠ **IT EXISTS BECAUSE ONE RUN NOW WRITES NUMBERS FROM TWO SERIES.** Since
    `BR-CUS-1042` an accounts row may quote its own `Customer #`, so the same
    load that walks the `account` counter past the file's account numbers has to
    walk the `customer` counter past its customer numbers — the identical
    `DEF-577` hazard on a second column, and a copy of these nine lines beside
    the first is how the two would come to disagree about *forward-only*.

    Forward-only, and numbers the tenant's own format could not have written are
    ignored rather than guessed at (`sequence_of` returns None for them).
    """
    if not written:
        return
    series_format = seams.number_series_format(series)
    if series_format is None:
        return  # no series row for this tenant — reported at allocation, not here
    issue_date = seams.tenant_today()
    highest = 0
    for value in written:
        sequence = core_numbering.sequence_of(series_format, value, issue_date)
        if sequence is not None and sequence > highest:
            highest = sequence
    if highest:
        seams.advance_number_series(actor, series, highest + 1)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def extract(actor: Any, payload: Any) -> dict[str, Any]:
    """Stage 1 — receive the file, stage every row, write NO premises.

    ⚠ Refuses `target` and `source_kind` this build does not implement, by
    name, rather than half-running them. See the module docstring.
    """
    if not isinstance(payload, dict):
        _refuse(errors.VAL_FORMAT, message_key="metering.payload_not_object")
    data: dict[str, Any] = payload

    target = str(data.get("target") or "").strip()
    if target not in TARGETS:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.kind_unknown",
            allowed=list(TARGETS),
        )
    source_kind = str(data.get("source_kind") or SOURCE_FILE).strip()
    if source_kind != SOURCE_FILE:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.kind_unknown",
            allowed=[SOURCE_FILE],
        )
    # ⛔ **THE WRITE MODE IS RECORDED AT STAGE 1 — CR-046 wave B, and it was
    # the missing half of `CR-042`.**
    #
    # `CR-042` / `CR-036` (g) moved the CONTROL to step 1 — PO verbatim: *"you
    # need at step 1 or 2 itself - this is important decision how you will
    # process the data and upload it"*. The SCREEN moved; the value did not.
    # `ImportRun.write_mode` stayed *"stage 4 only"* and the client sent the
    # mode with `/dry-run` and `/load` and with nothing else, so the server
    # first learned it after stage 3 had already judged every row.
    #
    # That is why `DEF-543`'s obstacle appeared to survive CR-042: the choice
    # had moved and the FACT had not. Stage 3 can only apply the PO's ruling
    # (*"in case of insert - reject it"*) if it is told, so the run records it
    # here, once, where the operator makes it.
    #
    # ⚠ **OPTIONAL, AND ABSENT IS NOT `insert`.** A client that does not send
    # it leaves the column NULL and stage 3 keeps its pre-CR-046 warning
    # (`World.write_mode`); defaulting to `insert` would make an unstated mode
    # REJECT rows, which is the unsafe option arriving by silence — hard-won
    # law 3, and the exact shape of *"an absence must not be spelled the same
    # way as a value"* (DEF-127).
    write_mode = str(data.get("write_mode") or "").strip() or None
    if write_mode is not None:
        _refuse_withdrawn_mode(write_mode, target=target)
        if write_mode not in WRITE_MODES:
            _refuse(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="metering.import.kind_unknown",
                allowed=list(WRITE_MODES),
            )

    raw_bytes = _file_bytes(data)
    text = _decode(raw_bytes)
    delimiter_name = _sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=_DELIMITER_CHARS[delimiter_name])
    if not reader.fieldnames:
        _refuse(errors.VAL_FORMAT, message_key="metering.import.header_required")
    headers = [str(name) for name in reader.fieldnames]
    rows: list[dict[str, Any]] = []
    for raw in reader:
        rows.append({key: raw.get(key) for key in headers})
        if len(rows) > CSV_ROW_CAP:  # BR-MET-038 — refused AT UPLOAD, nothing staged
            raise errors.BizError(
                errors.BIZ_CAP,
                br_ref="BR-MET-038",
                message_key="metering.import.row_cap_exceeded",
                params={"max_rows": CSV_ROW_CAP},
            )

    # ⛔ **`DEF-PAY-10758` (L3-03) — A PAYMENTS FILE ALREADY LOADED IS REFUSED
    # AT UPLOAD.** For every other target re-uploading a file to look at it
    # again is legitimate (the constraint's own note), and the commit-time
    # refusal is the guard. For PAYMENTS the same bytes loaded twice are the
    # same money twice, and the tester met the refusal only after *"Will create
    # 7"*, as *"HTTP 409 · BIZ-IDEMPOTENT"*. Asked here, from the server's own
    # hash, with the existing sentence naming the run that carried it.
    if target == TARGET_PAYMENTS:
        _refuse_file_already_loaded(
            models.ImportRun(tenant_id=_tenant_id(), target=target, file_hash=file_sha256(raw_bytes))
        )
    mapping_row = _mapping_template(data.get("mapping_id"))
    # BR-AST-048's recognition (r10 stage 1: "Header row recognised as …"):
    # when the operator named no template, an EXACT header-set match picks one
    # — a tenant's own template beats a system default, ties go to the most
    # recently used. Recognition never blocks: an unmatched file simply keeps
    # the alias auto-detect below.
    recognised = (
        mapping_row if mapping_row is not None else _match_mapping_template(target, headers)
    )
    if recognised is not None and mapping_row is None:
        mapping_row = recognised
        seams.touch_import_mapping(recognised.pk)
    # ⛔ **`BR-MET-1032` — THE SUGGESTION IS COMPUTED HERE, NOT AT THE END, AND
    # THAT MOVE IS THE WHOLE OF THE STAGE-1 HALF OF THIS RULE.** It used to be
    # built after the rows were staged, purely to put `detected_mapping` on the
    # answer. But a run sits at `extracted` until somebody maps it — that can be
    # days — and until stage 2 confirms a map, this suggestion is the ONLY thing
    # that knows which of the operator's headers is a Social Security number.
    # Computing it first is what lets the nine digits be encrypted on the way
    # IN rather than one stage later.
    detected = _detected_mapping(recognised, headers, target)
    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        run = models.ImportRun.objects.create(
            tenant_id=_tenant_id(),
            run_no=_allocate_run_no(warnings),
            target=target,
            source_kind=source_kind,
            file_name=_text(data.get("file_name")),
            file_hash=file_sha256(raw_bytes),
            file_bytes=len(raw_bytes),
            encoding_delimiter=f"UTF-8 · {delimiter_name} (detected)",
            mapping=mapping_row,
            batch_label=_text(data.get("batch_label"), 500),
            write_mode=write_mode,  # CR-046 wave B — see the note above
            counts={"in": len(rows), "duplicates_dropped": 0, "skipped": 0, "forward": 0},
            # ⛔ **THE FILE'S OWN COLUMN ORDER, STORED AS A LIST, BECAUSE A LIST
            # IS THE ONLY JSON SHAPE POSTGRES KEEPS IN ORDER (`DEF-2513`).**
            # `_source_headers` used to re-derive this from row 1's `raw` KEYS on
            # the reasoning that `extract` builds `raw` as `{header: value for
            # header in headers}`, so "row 1's key order IS the file's column
            # order". True of a Python dict and FALSE after a round trip: `raw`
            # is a `JSONField`, Postgres stores it as `jsonb`, and **jsonb does
            # not preserve object key order** — it re-sorts by key length, then
            # bytewise. `ACCT` and `NAME` therefore came back ahead of
            # `UNIT_REF`, and `BR-CUS-673`'s "the original row, byte-identical,
            # NOT RE-ORDERED" was broken for the one job the file has: fix two
            # cells in your own spreadsheet and upload it again.
            # ⚠ **jsonb ARRAYS are ordered; only OBJECTS are not.** That is the
            # whole fix — the same store, a shape it can keep.
            mapping_spec={"source_headers": list(headers)},
            status="extracted",
            run_by_id=getattr(actor, "id", None),
            session_ref=_text(data.get("session_ref"), 120),
            ip=data.get("ip") or None,
            started_at=timezone.now(),
        )
        # ⛔ **`BR-MET-1032` — NOTHING IS STAGED IN PLAIN TEXT.** Every cell the
        # suggested map calls a government identifier is encrypted with its
        # blind index beside it before the INSERT, and the cell the screen draws
        # becomes `••••6789`. A header this suggestion does not recognise stays
        # as it is until stage 2 confirms a map and protects it there — which is
        # why `transform` protects `raw` again rather than only `mapped`.
        staged_identity = identity_source_columns(target, detected)
        models.ImportRunRow.objects.bulk_create(
            [
                models.ImportRunRow(
                    tenant_id=run.tenant_id,
                    run=run,
                    row_no=index,
                    raw=import_identity.protect_cells(raw, staged_identity),
                    outcome="staged",
                )
                for index, raw in enumerate(rows, start=1)
            ],
            batch_size=1000,  # CR-026 — one bounded INSERT per 1,000 rows
        )
        _audit(
            actor,
            "import_run.extracted",
            run.id,
            run_no=run.run_no,
            target=target,
            rows=len(rows),
            file_name=run.file_name,
            file_hash=run.file_hash,
        )
    result = run_dict(run)
    result["headers"] = headers
    result["detected_mapping"] = detected
    # ⛔ **CR-168 · `DEF-WRK-9588` / `DEF-521` — STAGE 2'S *SAMPLE VALUE*
    # COLUMN.** The first non-empty cell under each header, so an operator can
    # tell `part_no` from `name` at a glance (image 39: *MTR-W34*). A header
    # the suggested map calls a government identifier ships NO sample:
    # `BR-MET-1032` stages those cells protected, and a plain-text sample on
    # the wire would undo that.
    result["samples"] = {
        header: next(
            (str(row.get(header)).strip() for row in rows if str(row.get(header) or "").strip()),
            "",
        )
        for header in headers
        if header not in staged_identity
    }
    result["recognised_template"] = (
        {
            "id": str(recognised.pk),
            "name": recognised.name,
            "is_system": bool(recognised.is_system),
        }
        if recognised is not None and recognised.mapping
        else None
    )
    result["warnings"] = warnings
    return result


def _detected_mapping(recognised: Any, headers: list[str], target: str) -> dict[str, str]:
    """Stage 1's suggested `{the operator's header: our column}`.

    A recognised TEMPLATE's own map wins outright — that is the golden path's
    *"zero mapping work"* — and otherwise the alias auto-detect answers.

    ⚠ **LIFTED OUT OF `extract`'s TAIL BY `BR-MET-1032`, AND THE FUNCTION IS THE
    POINT RATHER THAN THE TIDINESS.** The staging half of that rule needs to
    know which header holds a Social Security number BEFORE the rows are
    inserted, and the answer used to be computed after them. One function, one
    and answer, used twice — the alternative is two derivations of the same
    suggestion, and a drift between them would mean the screen shows one mapping
    and the encryption followed another.

    ⛔ **A TEMPLATE'S TARGET IS CHECKED AGAINST THE OFFERED SET FIRST — ADDED
    BY `DEF-MET-5802`, AND WITHOUT IT THAT DEFECT'S FIX BREAKS SAVED
    MAPPINGS.** A saved `ImportMapping` is a tenant's own row written months
    ago; retiring a column does not go back and edit it. The suggestion used to
    be returned VERBATIM, so a template naming `owner_manager` would pre-fill
    the picker with a column that no longer exists, the operator would confirm
    it, and `_transform_locked` would refuse the whole run with
    `metering.import.unknown_mapping_target`. **A run that cannot be mapped at
    all is not an honest degradation — it is a crash with a message key.**
    A retired target is DROPPED instead, so its source column arrives UNMAPPED
    and the operator is asked to make a choice about it; nothing of theirs is
    loaded silently and nothing of theirs is thrown away.

    ⚠ **`_auto_map` HAS ALWAYS DONE THIS** — *"the model lost the column —
    BR-MET-088 wins over the alias"* — and only this branch was missing it. The
    asymmetry was invisible while the offered set was derived from the model,
    because a column could then only vanish by being dropped from the table.
    """
    if recognised is not None and recognised.mapping:
        offered = _columns_by_target(target)
        suggestion: dict[str, str] = {}
        for source, spec in recognised.mapping.items():
            name = (
                str((spec or {}).get("target") or IGNORE) if isinstance(spec, dict) else str(spec)
            )
            if name != IGNORE and name not in offered:
                continue
            suggestion[str(source)] = name
        return suggestion
    return _auto_map(headers, target)


def _mapping_template(mapping_id: Any) -> Any:
    """The saved template this run was started from, if one was named.

    ⚠ **IT CANNOT CARRY A COLUMN MAP AND THAT IS DEF-512.** `ImportMapping` is
    `code · name · is_system · active`; its own docstring calls the list *"saved
    ETL column mappings"* and there is no column in which a mapping could be
    saved. So the template is recorded as a LABEL for the receipt's `MAPPING
    USED` line, the run keeps its real mapping in `mapping_spec`, and *"Save
    mapping as template"* cannot round-trip until that table gains a column.
    Stated here rather than implied — hard-won law 1.
    """
    if not mapping_id:
        return None
    from apps.tenancy import models as tenancy_models

    row = tenancy_models.ImportMapping.objects.filter(
        tenant_id=_tenant_id(), pk=mapping_id, active=True
    ).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _match_mapping_template(target: str, headers: list[str]) -> Any:
    """BR-AST-048's detect order, exactly as ruled: EXACT header-set match
    wins · a tenant template beats a system default · ties go to the most
    recently used. A read of tenancy's table (the same documented direction
    `_mapping_template` takes); the WRITE half (the MRU clock) goes through
    the tenancy seam."""
    from django.db.models import F

    from apps.tenancy import models as tenancy_models

    header_set = {str(header).strip() for header in headers}
    # `DEF-MET-9233` — the sample now carries the utility's own fields as
    # columns, and no SYSTEM template can name them (they are this tenant's).
    # So a system default is also matched on the file's headers with those
    # labels set aside; a tenant's own saved template still needs the exact
    # set, because it may well have mapped them.
    own_labels = {str(column["label"]).strip() for column in _custom_field_columns(target)}
    without_own = header_set - own_labels
    rows = tenancy_models.ImportMapping.objects.filter(
        tenant_id=_tenant_id(), target=target, active=True, mapping__isnull=False
    ).order_by("is_system", F("last_used_at").desc(nulls_last=True), "-updated_at")
    for row in rows:
        keys = set((row.mapping or {}).keys())
        if keys == header_set or (row.is_system and own_labels and keys == without_own):
            return row
    return None


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def save_mapping_template(actor: Any, run_id: Any, payload: Any) -> dict[str, Any]:
    """Stage 2's "Save mapping as template" — BR-AST-048's copy-on-write,
    closing the save half of DEF-512: the run's OWN `mapping_spec` (what the
    operator actually confirmed) becomes a NEW tenant row in tenancy's
    `import_mappings` list, written by tenancy's own service through the seam.
    A system default is never touched, whatever name is chosen."""
    data = payload if isinstance(payload, dict) else {}
    name = str(data.get("name") or "").strip()
    if not name:
        _refuse(errors.VAL_REQUIRED, message_key="settings.lookups.required")
    run = _run(run_id)
    # ── Q7 (PO 2026-10-30, *"Save mapping as template switched on with a
    # name; applied automatically when a file's headers match"*) ──────────────
    # The mapping step sends the map AS THE OPERATOR SEES IT — every header of
    # the file, an ignored one as `None` — so the template's key set IS the
    # file's header set and BR-AST-048's EXACT match recognises next week's
    # file. The confirmed `mapping_spec` below drops the ignored headers, so a
    # template saved from it never matches the file it came from; it stays the
    # answer for a caller that sends no map.
    offered = data.get("mapping")
    if isinstance(offered, dict) and offered:
        headers = set(_source_headers(run))
        unknown = [str(source) for source in offered if str(source) not in headers]
        if unknown:
            _refuse(errors.VAL_FORMAT, message_key="metering.import.unknown_mapping_target")
        mapping = {
            str(source): {"target": str(target) if target else IGNORE}
            for source, target in offered.items()
        }
        saved = seams.save_import_mapping(
            actor=actor, name=name, target=run.target, mapping=mapping
        )
        if saved is None:  # pragma: no cover — tenancy ships in-tree
            _refuse_assets_unwired()
        return saved
    columns = ((run.mapping_spec or {}).get("columns")) or {}
    if not columns:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-AST-048",
            message_key="metering.import.not_validated",
        )
    mapping = {
        source: {"target": entry.get("target") if isinstance(entry, dict) else str(entry)}
        for source, entry in columns.items()
    }
    saved = seams.save_import_mapping(actor=actor, name=name, target=run.target, mapping=mapping)
    if saved is None:  # pragma: no cover — tenancy ships in-tree
        _refuse_assets_unwired()
    return saved


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 2 · TRANSFORM
# ═══════════════════════════════════════════════════════════════════════════


def _run(run_id: Any, *, locked: bool = False) -> models.ImportRun:
    queryset = models.ImportRun.objects.filter(tenant_id=_tenant_id(), pk=run_id)
    if locked:
        queryset = queryset.select_for_update()
    run = queryset.first()
    if run is None:
        raise errors.NotFoundError()
    # ⚠ **THE GUARD MOVED OUT OF THIS FUNCTION (`DEF-541`).** It used to refuse
    # every `loaded`/`rolled_back` run HERE, which killed three behaviours at
    # once: the idempotency branch in `_load_locked` (unreachable — hard rule 6
    # was a comment), the receipt read (a receipt exists ONLY for a loaded
    # run), and rollback entirely (nothing could ever be rolled back, while
    # r10 promises 30 days). A shared fetch helper may not enforce a rule that
    # only SOME callers own — the stages that must refuse a committed run
    # (transform, validate) now do it themselves via `_refuse_committed`.
    return run


def _refuse_committed(run: models.ImportRun) -> None:
    """BR-MET-090's actual scope: a COMMITTED run's rehearsal may not be
    redone. Called by transform and validate — never by load (which has its
    own idempotent answer), receipt or rollback (which exist only after)."""
    if run.status in ("loaded", "rolled_back"):
        # Reusing customers' sentence rather than minting a key: an English
        # refusal with no catalogue entry is DEF-322's shape, and adding one
        # key obliges eleven catalogues (G15) from a backend-only lane.
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-MET-090",
            message_key="customers.import.already_committed",
        )


# ── CR-026 · the deferral decision, made once and used by all three stages ──
def _row_count(run: models.ImportRun) -> int:
    """How many rows the file brought in. Stage 1 wrote it; it never changes."""
    return int((run.counts or {}).get("in") or 0)


def _defers(run: models.ImportRun, stage: str) -> bool:
    """Does this run's `stage` go to a worker? See `async_row_bar`.

    ⚠ **THE BAR IS THE TARGET'S AND THE STAGE'S OWN (`DEF-2487`).** This read
    `ASYNC_ROW_BAR` for every target until 2026-08-30, so an accounts file
    inherited a figure measured on premises rows and 1,048 accounts ran inline
    for two minutes inside a request the web worker kills at sixty seconds.
    """
    return _row_count(run) > async_row_bar(run.target, stage)


class _JobActor:
    """The actor a WORKER carries: an id, and no role.

    The rating bulk-change job says it best and this follows it verbatim —
    *"Role was checked at enqueue; the worker carries the actor id in the
    record, never a role, so it can grant nothing."* The role gate ran on the
    request that enqueued the stage (`@require_role` on `transform`/`validate`/
    `load`, plus BR-MET-098's approver check in the API layer); rebuilding a
    role in the worker would be a second, weaker place for that decision to
    live. The id is what the audit rows need, and only that.
    """

    __slots__ = ("id",)

    def __init__(self, user_id: Any) -> None:
        self.id = user_id


def _refuse_no_worker(stage: str) -> None:
    """Refuse to hand `stage` to a queue nothing is consuming (`DEF-2487`).

    ⚠ **THE REASON IS LOGGED AND NEVER SHOWN.** `core.jobs.dispatch_is_ready`
    answers with a short technical phrase — *"no Celery worker answered the
    ping"* — which is exactly what a support line needs and exactly what
    CR-016's no-internal-references rule keeps off a utility's screen. What the
    operator reads is the catalogue sentence for `metering.import.no_worker`,
    which names the two things they can actually do.
    """
    ready, reason = core_jobs.dispatch_is_ready()
    if ready:
        return
    logger.error(
        "import stage=%s REFUSED: nothing would run it (%s). See DEF-2487 — a "
        "queued stage on a deployment with no worker writes nothing, for ever.",
        stage,
        reason,
    )
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-MET-096",
        message_key="metering.import.no_worker",
    )


def _defer(
    actor: Any, run: models.ImportRun, stage: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Hand one stage to a BE-07 job and answer immediately.

    ⚠ **THE SCOPE KEY IS THE RUN AND THE STAGE**, so a double-clicked *Validate*
    folds into the job already running rather than starting a second walk over
    the same 100,000 rows (`core.jobs.enqueue` returns the existing record for
    an active (kind, scope_key) — NFR-16). This is the SAME property hard rule 6
    asks of the load and is not a substitute for it: BR-MET-090's committed-run
    refusal and `_load_locked`'s idempotent receipt still decide what a second
    COMMIT does. This only decides what a second CLICK does.

    The answer carries the run as every other stage answers it, plus the job id
    and its poll URL (B12 r1 §3), plus `deferred: true` — which is what the API
    layer turns into a 202 instead of a 200.

    ⛔ **AND IT REFUSES RATHER THAN QUEUE INTO THE VOID — `DEF-2487`.** Lowering
    the accounts bar to 100 rows moved almost every real migration onto this
    path, and on a deployment with no worker running that path ACCEPTS the file,
    says *queued*, and writes nothing, for ever. A visible 500 is a bad day; an
    upload that reports success and does nothing is worse, and it would be ours.
    So the promise is checked before it is made (CLAUDE.md law 3).
    """
    _refuse_no_worker(stage)
    record = core_jobs.enqueue(
        STAGE_JOBS[stage],
        payload={
            "run_id": str(run.id),
            "stage": stage,
            "actor_user_id": (
                str(getattr(actor, "id", None)) if getattr(actor, "id", None) else None
            ),
            **payload,
        },
        scope_key=f"import:{stage}:{run.id}",
    )
    # Written BEFORE the answer goes out so the first poll after the 202 reads
    # `queued`, not an empty gauge — which a screen cannot tell from "nothing
    # is happening". The enqueue may already have run the body (JOBS_EAGER on a
    # demo box), in which case this write is behind the body's own `done` —
    # so it is skipped when the gauge already says the stage finished.
    if not _gauge_says_finished(run, stage):
        import_progress.queued(run, stage, _row_count(run), record["id"])
    result = run_dict(_run(run.id))
    result["deferred"] = True
    result["stage"] = stage
    result.update(core_jobs.accepted(record))
    return result


def _gauge_says_finished(run: models.ImportRun, stage: str) -> bool:
    row = import_progress.read(run)
    return bool(row and row["stage"] == stage and row["state"] in ("done", "failed"))


def _reporter(run: models.ImportRun, stage: str, job_id: Any) -> import_progress.Reporter:
    """The gauge a stage writes to — a real one in a worker, `NULL` in a request.

    A synchronous run answers before anyone could poll it, so its gauge would be
    a table write nobody ever reads (see `import_progress`'s docstring).
    """
    return import_progress.Reporter(
        tenant_id=run.tenant_id,
        run_id=run.id,
        stage=stage,
        total=_row_count(run),
        job_id=job_id,
    )


def _parse_boolean3(value: str | None) -> tuple[bool | None, str | None]:
    """⚠ **THE ONE FIELD WHERE BOTH DEFAULTS ARE WRONG** (BR-RAT-101, B15 §4.2A #7).

    `True` inside · `False` outside · **`None` NOBODY RECORDED IT.** A CSV blank
    is `None` and never `False`: `rating.resolution.money_factor` REFUSES on
    `None` rather than assuming, because assuming *inside* under-charges a
    customer the utility may be entitled to surcharge and assuming *outside*
    over-charges one who never agreed. Either default is a silent pricing
    decision made on data nobody entered.

    A value that is neither — `maybe`, `partial`, `see notes` — is a PARSE
    ERROR and not a `None`, because "nobody recorded it" and "somebody recorded
    something we cannot read" are different facts and only one of them is safe
    to leave empty.
    """
    if value is None or not value.strip():
        return None, None
    token = value.strip().lower()
    if token in TRUE_TOKENS:
        return True, None
    if token in FALSE_TOKENS:
        return False, None
    return None, f"{value} does not say inside or outside the city limits."


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    for separator in (",", ";", "|"):
        if separator in value:
            return [part.strip() for part in value.split(separator) if part.strip()]
    return [value.strip()] if value.strip() else []


def _parse_date(value: str, date_format: str | None) -> str | None:
    """The cell, read as **the format this utility selected** — and as nothing
    else. `None` when it does not match.

    ⚠ **BR-MET-117 (1), PO 2026-08-26, CR-036 (a).** *"when we match the date we
    have to compare it date format that utility has selected. the format should
    match otherwise it show the error"*. No sniffing, no locale fallback, **no
    trying formats until one parses** — a format that "works" is not the format
    that was meant, and that is the whole hazard: `3/4/2026` is 4 March in most
    of the world and 3 April in the United States, and **neither reading
    raises**. On the PO's own 9,881-row units file (`1/1/2026 … 1/10/2026`)
    only the first row reads the same both ways; by the tenth the two readings
    are nine months apart, and if the column feeds a service start that is a
    first bill prorated from the wrong month on 9,881 units.

    ⚠ **THIS USED TO BE `date.fromisoformat` AND NOTHING ELSE**, so a United
    States utility's export rejected EVERY ROW: `ROWS CHECKED 9881 · PASSED
    CLEAN 0 · ERRORS 9881`, all of it *"1/1/2026 is not a date this import can
    read."* A migration tool that cannot read the dates of the country it ships
    in is not a migration tool.

    ⚠ **ISO 8601 IS ACCEPTED BESIDE THE DECLARED FORMAT, AND THAT IS A NARROW
    READING OF (1) TAKEN DELIBERATELY — it is REPORTED, not assumed silently.**
    It is not a "try the next format" fallback: `YYYY-MM-DD` cannot be read as
    any other member of `DATE_FORMAT_PATTERNS` (they use slashes or dots, or
    put the year last), so it can never shadow a declared format's meaning the
    way a US/rest-of-world pair shadows each other. It stays because it is what
    THIS PRODUCT ITSELF writes: `sample_csv` emits `2026-01-01` in the file a
    first-time operator is told to start from, and IS-11 keeps every CSV export
    on ISO — refusing our own sample file, and every round-trip of our own
    export, would be the same bug in the other direction.
    """
    token = value.strip()
    try:
        return date.fromisoformat(token).isoformat()
    except ValueError:
        pass
    pattern = DATE_FORMAT_PATTERNS.get(str(date_format or ""))
    if pattern is None:
        return None
    try:
        return datetime.strptime(token, pattern).date().isoformat()
    except ValueError:
        return None


def _parse_created(value: str, date_format: str | None) -> str | None:
    """`DEF-MET-10164` — a Created cell: `_parse_date`, plus the ONE extra form
    this product itself writes in that column.

    The premises and units exports write Created as IS-9's timestamp — the
    tenant's zone WITH its offset, `1996-03-14T00:00:00-06:00`. Refusing that
    would refuse our own download, which is `_parse_date`'s ISO reasoning one
    step on. The DAY is read as written, in the offset written beside it, which
    is the tenant's own day — never converted through UTC, which could move it.
    A bare date-time with no offset is not something we write and is refused.
    """
    token = value.strip()
    if "T" in token and len(token) > 10:
        try:
            moment = datetime.fromisoformat(token)
        except ValueError:
            return None
        if moment.tzinfo is None:
            return None
        return moment.date().isoformat()
    return _parse_date(token, date_format)


def _is_dates_only_mapping(target: str, mapped_targets: set[str]) -> bool:
    """`DEF-MET-10164` — does this MAPPING describe a dates-correction file?

    The number column and the Created column, and nothing else but explicit
    ignores. The per-row twin is `import_rules.is_dates_only_row`.
    """
    number_field = import_rules.DATES_ONLY_NUMBER_FIELD.get(target)
    if number_field is None:
        return False
    carried = set(mapped_targets) - {IGNORE}
    return carried == {number_field, CREATED_FIELD}


def _created_moment(iso_day: Any, zone: Any) -> datetime | None:
    """`DEF-MET-10164` — a Created DAY as the instant stored for it: the start
    of that day on the utility's own clock (`connections.py`'s idiom), so the
    screen, which reads the instant back in the same zone, draws the same day."""
    if not iso_day:
        return None
    day = date.fromisoformat(str(iso_day))
    return datetime.combine(day, datetime.min.time(), tzinfo=zone)


def _correct_created(
    actor: Any, run: models.ImportRun, target_row: Any, iso_day: Any, zone: Any
) -> bool:
    """`DEF-MET-10164` point 5 — correct ONE record's Created date, audited
    old → new. `False` (and nothing written) when the day is unchanged, so a
    re-run of the same correction file leaves no second audit row.

    ⚠ **A QUERYSET `.update()` AND NOT `.save()`.** `.save()` would also move
    `updated_at` and re-run every field's `pre_save`; the correction is one
    column, and the audit row is what records that it happened.
    """
    moment = _created_moment(iso_day, zone)
    if moment is None:
        return False
    old = target_row.created_at
    if old is not None and old.astimezone(zone).date() == moment.date():
        return False
    type(target_row).objects.filter(tenant_id=run.tenant_id, pk=target_row.pk).update(
        created_at=moment
    )
    target_row.created_at = moment
    core_audit.write_row(
        action=f"{'premises' if run.target == TARGET_PREMISES else 'unit'}.created_date_corrected",
        entity_type="premises" if run.target == TARGET_PREMISES else "unit",
        entity_id=target_row.pk,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before={"created_at": old.isoformat() if old else None},
        after={"created_at": moment.isoformat(), "run_no": run.run_no},
    )
    return True


def _created_problem(value: str, date_format: str | None) -> tuple[str, str]:
    """`DEF-MET-10164` — the Created column's refusal, short (B14 rule 33) and
    still naming BOTH sides as BR-MET-117 (2) requires: the value as given and
    the format this utility chose. An unset format keeps `_date_problem`'s
    sentence, which says what to do about that."""
    if not date_format:
        return _date_problem(value, date_format)
    return (f"{value} is not {date_format}.", f"Use {date_format}.")


def _date_problem(value: str, date_format: str | None) -> tuple[str, str]:
    """**BR-MET-117 (2) — the refusal names BOTH SIDES**: the format the tenant
    selected AND the value as given, in one sentence, in the clerk's words.

    PO verbatim: *"you setting says this data format and you have given differnt
    and it does not match"*. This SUPERSEDES *"1/1/2026 is not a date this
    import can read"* / *"Use YYYY-MM-DD — 2026-04-01"*, which was wrong twice:
    it implied no format works, and it named a format the tenant never chose.

    ⚠ **THE UNSET CASE IS A REFUSAL, AND IT IS NOT THE PO'S WORDS.** Provisioning
    defaults `date_format` (`tenancy.services` → `DATE_FORMATS[0]`), so a tenant
    with none should be unreachable — but "should be unreachable" is exactly the
    assumption this repo keeps being caught by, and the seam is typed
    `str | None` because the column is nullable. Under (1) an unset format has
    no authority to match against, so the cell is REFUSED and the reason is
    said out loud. Picking one on the tenant's behalf is the one thing the rule
    forbids. Recorded as the consequence of the ruling, not as the ruling.
    """
    if not date_format:
        return (
            f"This utility has not chosen a date format in Settings, so {value} "
            "cannot be matched against anything.",
            "Choose the date format your files use in Settings › Regional, then "
            "map this column again.",
        )
    if date_format in MONTH_NAME_FORMATS:
        # ⚠ **DEF-753 — THE ONE REFUSAL THAT READS AS SELF-CONTRADICTORY.**
        # To a German utility, `25-Okt-26` IS `DD-MMM-YY`, so the sentence below
        # ("your settings say DD-MMM-YY and this row has 25-Okt-26, which does
        # not match") tells them nothing they can act on — it reads as the
        # importer being broken. The month name is the part that must match, and
        # this parser reads English only; saying which twelve words it accepts is
        # the difference between a rejection and a dead end.
        months = " ".join(ENGLISH_MONTH_ABBREVIATIONS)
        return (
            f"Your settings say dates are written {date_format} with ENGLISH month "
            f"names (25-Aug-26), and this row has {value}, which does not match.",
            f"Write the month as one of {months} — this import reads English month "
            "names only, whatever language the app is set to. A numeric format "
            "(Settings › Regional) avoids month names altogether.",
        )
    return (
        f"Your settings say dates are written {date_format}, and this row has "
        f"{value}, which does not match.",
        f"Write these cells as {date_format}, or change the format in Settings › Regional.",
    )


def _apply_text_transform(value: str, transform: str | None) -> str:
    if transform == "title_case":
        return value.title()
    if transform == "uppercase":
        return value.upper()
    return value  # trim_whitespace — already applied by `_text`


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def transform(actor: Any, run_id: Any, payload: Any) -> dict[str, Any]:
    """Stage 2 — map their shape onto ours. **STILL NO PREMISES ROW.**

    Refuses when `address_line` is unmapped, and it refuses HERE rather than at
    stage 3: B15 §4.2A #3 — *"The ONLY non-null business column on the table. A
    row without it cannot be created at all, so an unmapped `address_line` is a
    stage-2 refusal, not a stage-3 warning."* A file with no address column
    cannot produce a single loadable row, so letting it walk to validation only
    to reject all 431 rows one at a time tells the operator the wrong thing
    about what is wrong.
    """
    data = payload if isinstance(payload, dict) else {}
    # CR-026 — a file over the bar goes to a worker and this answers 202. The
    # refusals a caller must get IMMEDIATELY are taken first, on the unlocked
    # read: a committed run must be refused whether or not it is big (a 202
    # that resolves to "this run is closed" would be a refusal delivered by
    # poll, which is not a refusal anyone reads).
    run = _run(run_id)
    _refuse_committed(run)
    if _defers(run, "transform"):
        return _defer(actor, run, "transform", {"data": data})
    return _transform_apply(actor, run_id, data, import_progress.NULL)


def _transform_apply(
    actor: Any, run_id: Any, data: dict[str, Any], reporter: import_progress.Reporter
) -> dict[str, Any]:
    """Stage 2's body, UNDECORATED — the one path a request and a worker share.

    ⚠ **THE LOCK MUST BE INSIDE A TRANSACTION, AND A REAL REQUEST DOES NOT
    BRING ONE (`DEF-529`, critical).** `_run(locked=True)` issues
    `SELECT … FOR UPDATE`; Postgres refuses it outside a transaction, and
    `ATOMIC_REQUESTS` is set nowhere in `config/settings`. All 49 tests over
    these two functions passed because **pytest-django wraps every test in a
    transaction** — so the lock was legal in the suite and illegal in
    production, and stage 2 returned a 500 on every real run until the first
    browser walkthrough found it.

    Role is NOT re-checked here: the decorated `transform` above checks it on
    the request, and a worker carries an id and no role by design (`_JobActor`).
    """
    with transaction.atomic():
        return _transform_locked(actor, run_id, data, reporter)


def _transform_locked(
    actor: Any, run_id: Any, data: dict[str, Any], reporter: import_progress.Reporter
) -> dict[str, Any]:
    """The body of `transform`, with the run row LOCKED. The caller already holds
    the transaction that lock requires — see the note above."""
    run = _run(run_id, locked=True)
    _refuse_committed(run)  # BR-MET-090 — a committed run's rehearsal is closed
    offered = _columns_by_target(run.target)
    mapping = data.get("mapping")
    if not isinstance(mapping, dict):
        mapping = {}

    resolved: dict[str, dict[str, Any]] = {}
    #: `{the operator's header: the column we withdrew}` — see the note at the
    #: `column is None` branch. Reported on the answer so the retirement is
    #: VISIBLE rather than merely survivable.
    retired_targets: dict[str, str] = {}
    rows = list(
        models.ImportRunRow.objects.filter(tenant_id=run.tenant_id, run=run).order_by("row_no")
    )
    headers = set((rows[0].raw or {}).keys()) if rows else set()
    for source, spec in mapping.items():
        if headers and source not in headers:
            _refuse(
                errors.VAL_FORMAT,
                message_key="metering.import.unknown_mapping_target",
                target=source,
            )
        target_name, transform_name = _mapping_entry(spec)
        if target_name == IGNORE:
            resolved[source] = {"target": IGNORE, "transform": None}
            continue
        column = offered.get(target_name)
        if column is None:
            # ⛔ **A RETIRED COLUMN IS NOT AN UNKNOWN ONE, AND CONFUSING THE
            # TWO CRASHES A CUSTOMER'S RUN (`DEF-MET-5802`).**
            # `owner_manager` and the thirteen GIS fields were on this template
            # for months. A tenant's saved `ImportMapping` still names them, a
            # script still posts them, and a spreadsheet built from last year's
            # sample still has the headers. Refusing the WHOLE RUN over a
            # column we withdrew makes our decision their outage — they cannot
            # map their way out of it, because the target they are being
            # refused for is one we removed.
            #
            # ⚠ **SO IT RESOLVES AS AN EXPLICIT IGNORE AND IS NAMED IN THE
            # ANSWER.** Nothing of theirs is written and nothing is silently
            # dropped either: the operator is told, by column, which ones this
            # product no longer takes. That is the same posture `_auto_map` and
            # `_detected_mapping` take for a retired target one stage earlier
            # — all three now agree, and they did not before.
            #
            # ⚠ **A TARGET THAT NEVER EXISTED STILL REFUSES, BY NAME.** The
            # difference is `NOT_OFFERED_COLUMNS_BY_TARGET`, which is a
            # DECLARED list of columns this product withdrew on purpose, each
            # with its reason — so a typo in a client payload is still an
            # error, and only a column we retired is forgiven. Widening this to
            # *"anything we do not recognise"* would turn every misspelled
            # target into silently-unloaded data, which is `DEF-632`'s shape
            # and the opposite of what this clause is for.
            if target_name in NOT_OFFERED_COLUMNS_BY_TARGET.get(run.target, {}):
                retired_targets[source] = target_name
                resolved[source] = {"target": IGNORE, "transform": None}
                continue
            _refuse(
                errors.VAL_FORMAT,
                message_key="metering.import.unknown_mapping_target",
                target=target_name,
            )
        if transform_name and transform_name not in column["transforms"]:
            _refuse(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="metering.import.kind_unknown",
                allowed=column["transforms"],
            )
        resolved[source] = {"target": target_name, "transform": transform_name}

    mapped_targets = {entry["target"] for entry in resolved.values()}
    missing = [
        column["target"]
        for column in offered.values()
        if column.get("required") and column["target"] not in mapped_targets
    ]
    if missing and _is_dates_only_mapping(run.target, mapped_targets):
        # `DEF-MET-10164` — a file of number + Created only corrects dates on
        # records already on file and creates nothing, so the columns a NEW
        # record needs are not missing from it (`import_rules.is_dates_only_row`
        # is the per-row half of this, and the loader reads it too).
        missing = []
    if missing:
        _refuse(
            errors.VAL_REQUIRED,
            message_key="metering.import.required_column_unmapped",
            targets=missing,
        )

    # ⛔ **AN UNRECOGNISED ROW-HANDLING OPTION IS REFUSED BY NAME (`DEF-522`).**
    # This read used to be the dict comprehension ALONE, and a comprehension
    # over a fixed key tuple turns a MISSPELLED OPTION INTO A DEFAULT: the kit
    # sent `keep_latest_on_duplicate_key` and this line answered `False` for
    # `keep_latest_on_key`, so the operator ticked *"keep the latest row when a
    # key appears twice"* and the server kept the FIRST row instead. Nothing
    # 400'd, nothing logged, and every test on both sides passed because each
    # side sent its own spelling. The page boundary maps the two spellings
    # today (DEF-520's mount), which fixes THAT caller and leaves every other
    # caller — a script, a retry, the next client — with the same silent
    # coercion. **A tolerant read of a name that decides what is written is
    # not tolerance, it is a wrong answer with no error.**
    submitted = data.get("row_handling") or {}
    if not isinstance(submitted, dict):
        _refuse(
            errors.VAL_FORMAT,
            message_key="metering.import.unknown_row_handling",
            option=type(submitted).__name__,
            allowed=list(ROW_HANDLING_KEYS),
        )
    unknown = sorted(key for key in submitted if key not in ROW_HANDLING_KEYS)
    if unknown:
        # The FIRST unrecognised name, not a list: the operator fixes one
        # spelling at a time and a refusal naming five is a refusal nobody
        # reads. `allowed` carries the whole vocabulary beside it.
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.unknown_row_handling",
            option=unknown[0],
            allowed=list(ROW_HANDLING_KEYS),
        )
    handling = {key: bool(submitted.get(key)) for key in ROW_HANDLING_KEYS}
    outcome = _apply_mapping(run, rows, resolved, handling, offered, reporter)

    reporter.mark(len(rows), "Saving the mapped rows")
    with transaction.atomic():
        # CR-026: one row.save() per row was 100,000 UPDATE statements on the
        # PO's own file sizes; bulk_update writes the same fields in bounded
        # batches. `updated_at` is auto_now and bulk_update skips auto_now, so
        # it is stamped explicitly — the audit trail keeps its truth.
        now = timezone.now()
        changed = []
        for row, state in outcome["rows"]:
            row.mapped = state["mapped"]
            # `BR-MET-1032` — `raw` joins the written set. A header the stage-1
            # suggestion did not recognise as an identifier is protected HERE,
            # from the map the operator confirmed, and this is the write that
            # makes that stick.
            row.raw = state["raw"]
            row.source_key = state["source_key"]
            row.outcome = state["outcome"]
            row.problem = state["problem"]
            row.fix_hint = state["fix_hint"]
            row.updated_at = now
            changed.append(row)
        bulk_write.update_import_rows(
            changed,
            ["raw", "mapped", "source_key", "outcome", "problem", "fix_hint", "updated_at"],
            tenant_id=run.tenant_id,
            run_id=run.id,
            batch_size=1000,
        )
        # ⚠ RE-MAPPING CLEARS THE PREVIOUS JUDGEMENT. r10 invites a remap —
        # *"You can still remap at the next stage"* — so `transform` can run
        # over a run that was already validated. Leaving the old rule results
        # and the old checked/clean/errors/warnings behind would let the screen
        # show a verdict on a mapping that no longer exists, which is the
        # stale-number shape the `counts` reconciliation exists to prevent.
        # This is NOT in tension with BR-MET-090's *stored, never recomputed*:
        # that rule protects a run whose stage 4 has HAPPENED. Nothing here has
        # loaded anything, so there is no history to rewrite — only a rehearsal
        # to redo.
        models.ImportRuleResult.objects.filter(tenant_id=run.tenant_id, run=run).delete()
        # CR-030 W1 — batch-level OPTIONS ride beside the column map rather
        # than inside it. The accounts target needs exactly one
        # (`cutover_on`, BR-CUS-049's "dated at cutover"), and it is a property
        # of the RUN, not of any column: putting it in `columns` would make it
        # look mappable from a CSV header, which it is not.
        options = data.get("options")
        run.mapping_spec = {
            # ⚠ **CARRIED FORWARD, NOT RE-DERIVED (`DEF-2513`).** Stage 2
            # REPLACES this dict wholesale, so the file's column order — written
            # at extract and unavailable anywhere else — has to be read out of
            # the old value and put back. Dropping it here would restore the
            # defect at the exact moment the run becomes downloadable.
            "source_headers": (run.mapping_spec or {}).get("source_headers") or [],
            "columns": resolved,
            "row_handling": handling,
            # BR-MET-117 (3) — served by `run_dict` on the SAME answer stage 2
            # already returns, so the mapping screen prints the format it will
            # read dates as and highlights any column it could not read without
            # a second endpoint. `date_format` is None when the tenant has
            # chosen none — a real state, drawn as such (`_date_problem`).
            "date_format": outcome["date_format"],
            "column_problems": outcome["column_problems"],
            # CR-036 (i) — mapped, `Matched`, and empty in every row. PROPOSED,
            # not ruled: it is REPORTED and never acted on (`_empty_columns`).
            "empty_columns": outcome["empty_columns"],
            # ⛔ **`DEF-MET-5802` — WHICH OF THEIR HEADERS THIS PRODUCT NO
            # LONGER TAKES, BY NAME.** A retired target resolves to `— ignore —`
            # rather than refusing the run (see the `column is None` branch), and
            # a silent ignore would be the other half of the same defect: the
            # operator would believe a column loaded. Empty on every run that
            # maps nothing retired, so a screen draws it only when it is there.
            **({"retired_columns": dict(retired_targets)} if retired_targets else {}),
            **({"options": dict(options)} if isinstance(options, dict) else {}),
        }
        run.counts = {
            key: value
            for key, value in (run.counts or {}).items()
            if key not in ("checked", "clean", "errors", "warnings")
        } | outcome["counts"]
        run.status = "transformed"
        run.save(update_fields=["mapping_spec", "counts", "status", "updated_at"])
        _audit(actor, "import_run.transformed", run.id, run_no=run.run_no, **outcome["counts"])
    return run_dict(run)


def _mapping_entry(spec: Any) -> tuple[str, str | None]:
    """`{"target": …, "transform": …}` or the bare target string."""
    if isinstance(spec, dict):
        return str(spec.get("target") or IGNORE), (
            str(spec["transform"]) if spec.get("transform") else None
        )
    return str(spec or IGNORE), None


def _apply_mapping(
    run: models.ImportRun,
    rows: list[models.ImportRunRow],
    resolved: dict[str, dict[str, Any]],
    handling: dict[str, bool],
    offered: dict[str, dict[str, Any]],
    reporter: import_progress.Reporter = import_progress.NULL,
) -> dict[str, Any]:
    """The three row-handling choices, then one mapped payload per row.

    ⚠ The counts MUST RECONCILE — `in − duplicates_dropped − skipped = forward`
    (TC-3). r10 prints three of these four as its own AFTER TRANSFORM line and
    the arithmetic is the only thing that makes them checkable.
    """
    lookup_indexes = _lookup_indexes_for(run.target)
    # CR-036 (a) — ONE read for the whole file (DEF-324's lesson), and it is a
    # STATEMENT THE TENANT MADE rather than anything inferred from the data.
    date_format = seams.tenant_date_format()
    # `DEF-MET-10164` — the utility's own day, once per file, for the Created
    # column's future-date refusal.
    tenant_day = seams.tenant_today()
    # ⛔ **`BR-MET-1032` — THE CONFIRMED MAP, WHICH IS THE AUTHORITATIVE ONE.**
    # Stage 1 protected what its SUGGESTION recognised; an operator is free to
    # point any header at `owner_ssn` here, and a header the alias table never
    # heard of would otherwise keep its nine digits for the life of the run. So
    # `raw` is protected AGAIN from what the operator actually confirmed, and
    # `mapped` is protected from the same decision.
    staged_identity = identity_source_columns(run.target, resolved)
    mapped_identity = identity_columns(run.target)
    seen_raw: set[str] = set()
    by_key: dict[str, int] = {}
    states: list[tuple[models.ImportRunRow, dict[str, Any]]] = []
    dropped = 0
    skipped = 0

    for walked, row in enumerate(rows, start=1):
        # CR-026 — the gauge. `step` throttles itself (1,000 rows / 1s), so
        # calling it once per row costs a comparison per row and nothing else.
        reporter.step(walked)
        # ⛔ **`BR-MET-1032` — THE MAPPER READS THE OPERATOR'S OWN VALUES.**
        # `row.raw` may hold `••••6789` and an envelope in
        # its vault (staged at extract, or by an earlier run of this same
        # stage), and every transform, every rule and the load itself expect the
        # number the operator typed. This is the one place that view is built.
        raw = import_identity.reveal_cells(row.raw or {}, staged_identity)
        state: dict[str, Any] = {
            "mapped": {},
            # `BR-MET-1032` — the row's own cells as they will be STORED. It
            # defaults to what is already there so the two branches below that
            # `continue` before the mapper runs (an exact duplicate, a skipped
            # row) write the row back unchanged rather than blanking it.
            "raw": row.raw or {},
            "problems": {},
            "source_key": None,
            "outcome": "staged",
            "problem": None,
            "fix_hint": None,
        }
        # ⚠ **THE SIGNATURE IS TAKEN OVER THE REVEALED VIEW, AND IT HAS TO BE.**
        # Every AES-GCM envelope carries a fresh random nonce, so two rows that
        # are byte-identical in the operator's file hold DIFFERENT ciphertexts —
        # and a signature over the stored cells would call them different rows.
        # *"Drop exact duplicates"* would silently stop dropping anything on any
        # file carrying an identifier, with no error and a correct-looking
        # count. The vault key is dropped by `reveal_cells`, so it cannot reach
        # this either.
        signature = repr(sorted(raw.items()))
        if handling["drop_exact_duplicates"] and signature in seen_raw:
            state["outcome"] = "duplicate"
            state["problem"] = "This row is an exact copy of an earlier row."
            state["fix_hint"] = "It was dropped before validation."
            dropped += 1
            states.append((row, state))
            continue
        seen_raw.add(signature)

        mapped, problems = _map_row(
            raw, resolved, offered, lookup_indexes, date_format, today=tenant_day
        )
        # `CR-161-BRC10` W3 · `DEF-MET-9172` — a custom-field cell is judged by
        # the field's OWN rules, through the one validator the screens use.
        _judge_custom_cells(run.target, mapped, problems)
        # `BR-MET-1032` — the row as it is STORED. `mapped` stays the operator's
        # own values for the rest of this loop (the dedupe key, the skip check
        # and `source_key` all read it), and the protected copy is what lands in
        # the database. Two dicts on purpose: one is a view, one is a record.
        state["mapped"] = import_identity.protect_cells(mapped, mapped_identity)
        # And the operator's own cells, protected from the CONFIRMED map.
        # `reveal_cells` above dropped the vault key, so this rebuilds it from
        # the values rather than carrying a stale one forward.
        state["raw"] = import_identity.protect_cells(raw, staged_identity)
        state["problems"] = problems
        state["source_key"] = (
            mapped.get("premise_no")
            or mapped.get("asset_no")
            # BR-AST-049 — on an assets row `asset_no` is blank in the normal
            # case now, so the operator's OWN reference is what identifies the
            # row in every sentence a receipt or a reject list prints.
            or mapped.get("external_ref")
            # CR-168 · `DEF-WRK-9588` — a parts row is named by its part number;
            # without this the KEY column of every parts reject was blank.
            or mapped.get("part_no")
            or mapped.get("address_line")
            or mapped.get("label")
            # `DEF-MET-10164` — a units dates-correction row carries no label;
            # its number is what names it on the reject list.
            or mapped.get("unit_no")
        )

        skip_field, skip_problem = SKIP_REQUIRED_BY_TARGET[run.target]
        if (
            handling["skip_rows_missing_required"]
            and not mapped.get(skip_field)
            # `DEF-MET-10164` — a dates-correction row is missing nothing.
            and not import_rules.is_dates_only_row(run.target, mapped)
        ):
            # r10's third checkbox — *"Skip rows with empty required fields
            # rather than rejecting them"*. Skipping is the operator's explicit
            # choice; with the box unticked the row goes forward and stage 3
            # refuses it, which is the default and the safer of the two.
            state["outcome"] = "skipped"
            state["problem"] = skip_problem
            state["fix_hint"] = "You chose to skip rows with an empty required field."
            skipped += 1
            states.append((row, state))
            continue
        states.append((row, state))

    if handling["keep_latest_on_key"]:
        # *"Keep the latest row when a key appears twice"* — B15 §4.2A #1 says
        # the key is `premise_no` for premises; each target names its own
        # identity (`DEDUPE_KEY_BY_TARGET` — the assets targets key on the
        # asset number, exactly as their file references rows). The LAST
        # occurrence wins, so the earlier one is dropped as a duplicate and
        # never reaches the in-file uniqueness ERROR.
        key_field, key_label = DEDUPE_KEY_BY_TARGET[run.target]
        for row, state in states:
            key = _dedupe_key_of(run.target, state["mapped"])
            if key and state["outcome"] in ("staged",):
                by_key[key] = row.row_no
        for row, state in states:
            key = _dedupe_key_of(run.target, state["mapped"])
            if key and state["outcome"] == "staged" and by_key.get(key) != row.row_no:
                shown = (state["mapped"] or {}).get(key_field)
                state["outcome"] = "duplicate"
                state["problem"] = f"{key_label} {shown} appears again later in this file."
                state["fix_hint"] = "The later row was kept."
                dropped += 1

    forward = sum(1 for _row, state in states if state["outcome"] == "staged")
    if forward != len(rows) - dropped - skipped:  # pragma: no cover — TC-3's invariant
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-MET-004",
            message_key="metering.import.errors_must_be_fixed",
            params={"errors": len(rows) - dropped - skipped - forward},
        )
    return {
        "rows": states,
        # BR-MET-117 (3) — what stage 2 knows about the columns it could not
        # read, and the format it read the date columns AS.
        "column_problems": _column_problems(states, resolved),
        "empty_columns": _empty_columns(states, resolved),
        "date_format": date_format,
        "counts": {
            "in": len(rows),
            "duplicates_dropped": dropped,
            "skipped": skipped,
            "forward": forward,
        },
    }


def _column_problems(
    states: list[tuple[Any, dict[str, Any]]],
    resolved: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """**BR-MET-117 (3)** — stage 2's own answer about WHICH MAPPED COLUMN it
    could not read, aggregated per column with the first offending row and one
    example value, so the mapping screen can highlight the column THERE.

    ⚠ **THE COUNT IS ROWS-THAT-SURFACED-THIS-COLUMN, NOT ROWS-THAT-ARE-WRONG,
    and the difference is stated rather than hidden.** `_map_row` carries ONE
    parse problem per row under a single `parse` key — a pre-existing shape
    stage 3's `*.VALUES_PARSE` rule reads — so a row whose date AND whose floor
    area are both unreadable is counted once, against whichever column the
    mapping walked last. Widening `problems` to one entry per column would
    change what stage 3 reads, which is another lane's rule; this reports what
    it can see and says what it cannot.
    """
    source_of = {
        entry["target"]: source for source, entry in resolved.items() if entry["target"] != IGNORE
    }
    found: dict[str, dict[str, Any]] = {}
    for row, state in states:
        problem = (state.get("problems") or {}).get("parse") or {}
        target = problem.get("target")
        if not target:
            continue
        entry = found.get(target)
        if entry is None:
            found[target] = {
                "source_column": source_of.get(target),
                "target": target,
                "rows": 1,
                "first_row": row.row_no,
                "example": problem.get("value"),
                "problem": problem.get("problem"),
                "fix_hint": problem.get("fix_hint"),
            }
        else:
            entry["rows"] += 1
    return sorted(found.values(), key=lambda entry: entry["first_row"])


def _empty_columns(
    states: list[tuple[Any, dict[str, Any]]],
    resolved: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Columns the operator MAPPED and that contributed nothing to a single row.

    ⚠ **THIS IS THE SHAPE CR-036 (i) ARRIVED IN AND IT IS SILENT TODAY.** The
    PO mapped `services_available`, stage 2 marked it `Matched`, stage 3 found
    zero errors, 9,881 premises loaded — and every one of them reads
    `No services` on PRM-01, because a mapped column whose cells are all empty
    is indistinguishable, at every stage, from a mapped column that worked.
    Nothing in the run says so: `Matched` is about the HEADER, not the DATA.
    **The product's own sample file is one way to arrive here** — `sample_csv`
    writes a `services_available` header with an EMPTY cell on purpose
    (*"tenant-specific vocabularies — never guessed"*, asserted by
    `tests/test_cr025_sample_csv.py`), so a file built from the sample carries
    the column, maps it, and fills nothing.

    It is reported and NEVER acted on: an empty cell is a legitimate value
    (BR-RAT-101's whole point about `inside_city_limits`), so this cannot
    reject, warn or default — it can only be SAID, at the stage where saying it
    is cheap. That is BR-MET-117 (3)'s principle applied to a second case, and
    it is **PROPOSED, not ruled**: no signed statement asks for this notice.
    """
    source_of = {
        entry["target"]: source for source, entry in resolved.items() if entry["target"] != IGNORE
    }
    forwarded = [state for _row, state in states if state["outcome"] == "staged"]
    if not forwarded:
        return []
    empty = []
    for target, source in sorted(source_of.items()):
        if all(
            (state.get("mapped") or {}).get(target) in (None, "", [], {}) for state in forwarded
        ):
            empty.append(
                {
                    "source_column": source,
                    "target": target,
                    "rows": len(forwarded),
                }
            )
    return empty


#: `CR-161-BRC10` — the import targets whose file carries one column per active
#: custom field, and the record type each one's fields are defined on. The
#: premises and units targets DERIVE their columns (`custom_data` in
#: `DECLARED_COLUMNS_BY_TARGET`); the three asset sheets DECLARE theirs and add
#: the `assets` fields at the end (`DEF-AST-9171`). Tenancy's
#: `IMPORT_FED_ENTITIES` is pinned to this map's values by a test, because a
#: field Settings calls *Filled by import* must really have a column here.
CUSTOM_FIELD_ENTITY_BY_TARGET: dict[str, str] = {
    TARGET_PREMISES: "premises",
    TARGET_UNITS: "units",
    TARGET_ASSETS_METERS: "assets",
    TARGET_ASSETS_SUBMETERS: "assets",
    TARGET_ASSETS_DEVICES: "assets",
    # `DEF-MET-9239` — the accounts sheet DECLARES its columns and adds the
    # `accounts` fields at the end, as the asset sheets do. Customer and
    # contact fields are NOT here: the accounts file carries one customer
    # block, not a customer record of its own, and no lane has been asked to
    # write a customer's answers from it.
    TARGET_ACCOUNTS: "accounts",
}

#: What a refused custom cell says on the reject list, by the validator's own
#: `message_key`. English, like every other import sentence in this file.
_CUSTOM_CELL_PROBLEMS: dict[str, str] = {
    "customFields.option_unknown": "{value} is not one of the choices for {label}.",
    "customFields.not_a_number": "{label} has to be a number.",
    "customFields.not_a_date": "{label} has to be a date written YYYY-MM-DD.",
    "customFields.not_a_boolean": "{label} has to be yes or no.",
    "customFields.too_long": "{label} is longer than {max} characters.",
}


def _judge_custom_cells(target: str, mapped: dict[str, Any], problems: dict[str, Any]) -> None:
    """`DEF-MET-9172` — every custom cell through `validate_custom_data_for`.

    ⚠ **`screen=None`, SO A REQUIRED FIELD NEVER BLOCKS AN IMPORT.** The PO's
    Rules table: *"A required field never blocks a screen that doesn't show
    it"*, and an import is not a screen — a file without the column loads.

    A good cell is replaced by its NORMALISED value (`yes` → `True`, `1,500` →
    `"1500"`, a List value exactly as the option is spelled), so the stored
    answer is the one a screen would have stored. A bad one becomes the row's
    `parse` problem — the slot `*.VALUES_PARSE` already judges — naming the
    field by its LABEL, never its key. Nothing here catches a database error,
    so hard-won law 14's aborted-transaction trap is not reachable from it.
    """
    entity = CUSTOM_FIELD_ENTITY_BY_TARGET.get(target)
    cells = mapped.get("custom_data")
    if entity is None or not cells:
        return
    try:
        mapped["custom_data"] = seams.validate_custom_data(entity, cells, screen=None)
        return
    except errors.ValidationError as refusal:
        failures = list(refusal.field_errors or [])
    labels = {
        column["target"].split(".", 1)[1]: column["label"]
        for column in _custom_field_columns(target)
    }
    sentences = []
    for failure in failures:
        key = str(failure.get("field") or "").split(".", 1)[-1]
        params = dict(failure.get("params") or {})
        template = _CUSTOM_CELL_PROBLEMS.get(
            str(failure.get("message_key")), "{label} could not be read."
        )
        sentences.append(
            template.format(
                label=labels.get(key, key),
                value=params.get("value", cells.get(key, "")),
                max=params.get("max", ""),
            )
        )
    sentence = " ".join(sentences)
    earlier = problems.get("parse")
    problems["parse"] = {
        "problem": sentence if earlier is None else f"{earlier['problem']} {sentence}",
        "fix_hint": "Correct the cell to a value the field accepts, or leave it empty.",
    }
    mapped[PARSE_PROBLEMS] = problems


def _map_row(
    raw: dict[str, Any],
    resolved: dict[str, dict[str, Any]],
    offered: dict[str, dict[str, Any]],
    lookup_indexes: dict[str, dict[str, str]],
    date_format: str | None = None,
    today: date | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One source row → the values a premises WOULD be created from.

    `today` is the tenant's own day, read ONCE per file by the caller; only the
    Created column reads it (`DEF-MET-10164`: a future date is refused).

    Nothing here coerces a value to make it fit — `read_import.py`'s ratified
    posture. A cell that will not parse is carried under `problems` with its
    ORIGINAL text, and stage 3's `PRM.VALUES_PARSE` is what judges it.
    """
    mapped: dict[str, Any] = {}
    problems: dict[str, Any] = {}
    custom: dict[str, Any] = {}
    for source, entry in resolved.items():
        target = entry["target"]
        if target == IGNORE:
            continue
        value = _text(raw.get(source), 2000)
        column = offered[target]
        kind = column["kind"]

        if target.startswith("custom_data."):
            if value is not None:
                custom[target.split(".", 1)[1]] = value
            continue
        if kind == KIND_BOOLEAN3:
            parsed, problem = _parse_boolean3(value)
            mapped[target] = parsed  # ⚠ None stays None. Never False.
            if problem:
                problems["parse"] = {
                    "problem": problem,
                    "fix_hint": "Use inside or outside, or leave the cell empty.",
                }
            continue
        if kind == KIND_LIST:
            codes = [code.lower() for code in _split_list(value)]
            mapped[target] = codes
            continue
        if kind == KIND_LOOKUP:
            # ⚠ ONE branch, EVERY table. `lookup_indexes` carries one index
            # PER LOOKUP FIELD for this run's target (premises types, unit
            # types, meter types, read methods, services, device types),
            # resolved ONCE by the caller (`_lookup_indexes_for`). A
            # `if target == units:` here is the branch BR-MET-096 forbids —
            # and a single shared index was the shape that broke the moment a
            # target carried TWO lookups (meter_type AND read_method).
            field_index = lookup_indexes.get(target) or {}
            mapped[f"{target}_raw"] = value
            resolved_code = field_index.get(value.lower()) if value else None
            mapped[target] = resolved_code
            continue
        if kind in (KIND_UNIT_REF, KIND_ASSET_REF):
            # The customer's own reference text, carried (the KIND_PREMISE_REF
            # posture): stage 3 judges it against the world's index, the load
            # resolves it through THE SAME index (import_rules.resolve_unit_ref
            # — DEF-544's lesson, applied before it can recur).
            mapped[target] = value
            continue
        if kind == KIND_DECIMAL:
            if value is None:
                continue
            token = value.replace(",", "").strip()
            try:
                parsed = Decimal(token)
            except InvalidOperation:
                problems["parse"] = {
                    "problem": f"{value} is not a number.",
                    "fix_hint": "Use digits and a decimal point — 164.0000.",
                }
                continue
            if parsed < 0:
                # A NEGATIVE OPENING BUCKET IS NOT A TYPO — it is a legacy CREDIT
                # balance (an overpayment the old system was holding), and
                # **BR-CUS-061 has ruled what happens to one since 2026-08-08**:
                # it imports as a carried ACCOUNT CREDIT (BR-PAY-010's
                # overpayment pattern) and the aging buckets stay debit-only.
                # BR-CUS-077 (PO 2026-08-24) adds the row that carries BOTH: a
                # −45.00 current cell beside a 121.00 over-90 cell keeps both,
                # separately, and is never netted to 76.00.
                #
                # ⚠ **THIS BRANCH REFUSED THE ROW, CITING OQ-065 AS OPEN — that
                # is DEF-620.** OQ-065 read CLOSED(→BR-CUS-061) in the registry
                # sixteen days before this line was written, so a utility whose
                # base held credit customers had those rows rejected and had to
                # settle them by hand in the system it was leaving. The cell is
                # CARRIED now, exactly like every other decimal, and
                # `customers.import_writer.opening_position` — the one place
                # that can see the whole row — is what splits debt from credit.
                #
                # A negative that is NOT an opening bucket is still a typo: a
                # meter cannot cost minus $164, and widening the credit reading
                # to every decimal column would make it one.
                if target not in ACCOUNTS_BUCKET_TARGETS:
                    problems["parse"] = {
                        "problem": f"{value} is negative.",
                        "fix_hint": "A cost or capacity cannot be below zero.",
                    }
                    continue
            # Carried as its STRING (HR-2: Decimal end to end, and `mapped` is
            # a JSON column); the assets service re-parses at write time.
            mapped[target] = str(parsed)
            continue
        if kind in (KIND_PREMISE_REF, KIND_PLAN_REF):
            # ⚠ **THE CUSTOMER'S OWN TEXT, CARRIED — NOT AN ID.** Resolving a
            # reference is a LOAD-time act (the posture `KIND_AREA` takes three
            # branches down, and for the same reason: a rehearsal that resolved
            # ids would depend on data that can change before the commit).
            # Stage 3 checks the row is there; `BR-MET-100` is what decides
            # whether a missing one rejects — a premise does, a plan does not.
            mapped[f"{target}_ref"] = value
            continue
        if kind == KIND_INTEGER:
            if value is None:
                continue
            token = value.replace(",", "").strip()
            if not token.lstrip("-").isdigit():
                problems["parse"] = {
                    "problem": f"{value} is not a whole number.",
                    "fix_hint": "Use digits only — 980, not 980 sq ft.",
                }
                continue
            mapped[target] = int(token)
            continue
        if kind == KIND_DATE:
            if value is None:
                continue
            if target == CREATED_FIELD:
                parsed_date = _parse_created(value, date_format)
            else:
                parsed_date = _parse_date(value, date_format)
            if (
                target == CREATED_FIELD
                and parsed_date is not None
                and today is not None
                and parsed_date > today.isoformat()
            ):
                # `DEF-MET-10164` — PO: *"Future … → that row refused with a
                # short reason."* A record cannot have been set up on a day
                # that has not happened yet in the utility's own zone.
                problems["parse"] = {
                    "problem": "Date is in the future.",
                    "fix_hint": "Use today or an earlier date.",
                    "target": target,
                    "value": value,
                }
                continue
            if parsed_date is None:
                problem, fix_hint = (
                    _created_problem(value, date_format)
                    if target == CREATED_FIELD
                    else _date_problem(value, date_format)
                )
                problems["parse"] = {
                    "problem": problem,
                    "fix_hint": fix_hint,
                    # BR-MET-117 (3) — WHICH column and WHAT value, so stage 2
                    # can highlight the column on the mapping screen instead of
                    # the operator meeting it one stage later as 9,881
                    # identical rejects.
                    "target": target,
                    "value": value,
                }
            else:
                mapped[target] = parsed_date
            continue
        if kind == KIND_BOOLEAN:
            if value is None:
                continue
            token = value.strip().lower()
            if token in TRUE_TOKENS:
                mapped[target] = True
            elif token in FALSE_TOKENS:
                mapped[target] = False
            else:
                problems["parse"] = {
                    "problem": f"{value} is not a yes or a no.",
                    "fix_hint": "Use yes or no, or leave the cell empty.",
                }
            continue
        if kind == KIND_AREA:
            # The NAME only. Resolving it to an id is a load-time act, and
            # checking it exists is stage 3's `PRM.REFERENCES_ON_FILE`.
            mapped["area_name"] = value
            continue
        if kind == KIND_OWNER_REF:
            # ── DEF-1088 · BR-MET-402 ──────────────────────────────────────
            # The operator's own NAME, carried as text — `KIND_AREA`'s posture
            # and for `KIND_AREA`'s reason: resolving a party during a
            # REHEARSAL would bind the run to a table a clerk may still be
            # editing on the matching screen, and stage 4 would then resolve
            # against a different world than the operator was shown.
            # `_resolve_owner_ref` at load time is the one resolver.
            mapped["owner_ref"] = value
            continue
        if kind == KIND_OWNER_KIND:
            # CR-058 W3 — two values and nothing else. A cell that is neither
            # is a PARSE problem carried with its original text, never coerced:
            # `person` is not a safe default for a business and `company` is not
            # one for a household, and either guess files a government
            # identifier where the other kind's matcher will never look
            # (`BR-CUS-1022`).
            if value is None:
                continue
            token = value.strip().lower()
            if token not in OWNER_KINDS:
                problems["parse"] = {
                    "problem": f"{value} is not a person or a company.",
                    "fix_hint": f"Use one of: {', '.join(OWNER_KINDS)}.",
                }
                continue
            mapped[target] = token
            continue
        if kind == KIND_ENUM:
            if value is None:
                continue
            token = value.strip().lower()
            if token not in PREMISES_STATUSES:
                problems["parse"] = {
                    "problem": f"{value} is not a status a premises can have.",
                    "fix_hint": f"Use one of: {', '.join(PREMISES_STATUSES)}.",
                }
                continue
            mapped[target] = token
            continue
        if value is not None:
            mapped[target] = _apply_text_transform(value, entry["transform"])
    if custom:
        mapped["custom_data"] = custom
    if problems:
        # ⚠ CARRIED ON THE ROW, not recomputed at stage 3. A parse problem is a
        # property of THIS mapping, so re-running stage 2 with a different
        # transform must be able to clear it — and stage 3 must be able to read
        # it without re-parsing, because re-parsing is where the two stages
        # would start disagreeing. `PARSE_PROBLEMS` is a reserved key inside
        # `mapped`; stage 4 must strip it before it builds a premises.
        mapped[PARSE_PROBLEMS] = problems
    return mapped, problems


def _premises_type_index() -> dict[str, str]:
    """`code` and `name`, both case-folded, → the code (BR-MET-034).

    Read ONCE per run. DEF-324 measured what the other shape costs: the same
    lookup answered per row spent 40% of a provisioning request on a read-only
    question.
    """
    from apps.metering import services

    services.ensure_reference_catalogs()
    index: dict[str, str] = {}
    for row in models.PremisesType.objects.filter(tenant_id=_tenant_id(), active=True):
        index[row.code.lower()] = row.code
        index[row.name.lower()] = row.code
    return index


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 3 · VALIDATE
# ═══════════════════════════════════════════════════════════════════════════


def _unit_type_index() -> dict[str, str]:
    """`code` and `name`, both case-folded, → the code. The units mirror of
    `_premises_type_index`, read once per run for the same measured reason."""
    from apps.metering import services

    services.ensure_reference_catalogs()
    index: dict[str, str] = {}
    for row in models.UnitType.objects.filter(tenant_id=_tenant_id(), active=True):
        index[row.code.lower()] = row.code
        index[row.name.lower()] = row.code
    return index


def _owner_category_index() -> dict[str, str]:
    """`code` and `name`, both case-folded, → the code — PO ruling 2026-09-19.

    ⛔ **WITHOUT THIS THE COLUMN IS DECORATION, AND IT WAS, FOR ONE TEST RUN.**
    The `KIND_LOOKUP` branch resolves against `lookup_indexes.get(target)` and
    answers `None` for a target with no index, so `owner_category` arrived on
    the template, on the picker and in the sample CSV, mapped cleanly, showed
    `Matched` — and resolved to nothing, so no party was ever created. **That
    is `DEF-771`'s exact shape** (*"a utility's 9,881-row file said `city
    customer plan` in every cell, mapped clean, showed Matched, and loaded 9,881
    units with no plan"*), and it is what the new end-to-end test caught.

    ⚠ **BOTH THE CODE AND THE NAME**, like `_premises_type_index` beside it: a
    utility's spreadsheet is as likely to say *Landlord* as `landlord`, and a
    lookup that accepts only our spelling makes the operator learn it.

    ⚠ **READ, NEVER ENUMERATED.** The five are seeded into a list a tenant may
    rename, retire or extend on Settings, so the index is whatever that table
    says today. `premises_owners._resolve_category` refuses an unknown or
    RETIRED code by name at the door; this index only decides what stage 2 can
    resolve, and it takes `active=True` for the same reason the picker does — a
    retired category must not be quietly resolvable from a file.
    """
    from apps.tenancy import models as tenancy_models

    index: dict[str, str] = {}
    for row in tenancy_models.PremisesOwnerCategory.objects.filter(
        tenant_id=_tenant_id(), active=True
    ):
        index[str(row.code).lower()] = row.code
        if getattr(row, "name", None):
            index[str(row.name).lower()] = row.code
    return index


def _assets_measuring_indexes() -> dict[str, dict[str, str]]:
    """The meters/sub-meters targets' three lookups — meter type and read
    method from the assets catalogs (through the seam: assets owns those
    lists), services from the tenant's enabled set (BR-MET-003)."""
    return {
        "meter_type": seams.assets_lookup_index("meter_types"),
        "read_method": seams.assets_lookup_index("read_methods"),
        "service": {code.lower(): code for code in seams.enabled_service_codes()},
    }


#: target → the per-field lookup indexes stage 2 resolves against, built ONCE
#: per run (DEF-324). A dict of builders, never a branch (BR-MET-096).
LOOKUP_INDEX_BUILDERS: dict[str, Any] = {
    # ⛔ **CR-058 W3 — A SECOND LOOKUP ON THIS TARGET, AND IT IS CUSTOMERS'
    # OWN VOCABULARY READ THROUGH THE SEAM.** The owner's account type is the
    # SAME list the accounts upload resolves against (`seams.
    # account_lookup_indexes`), so a utility that has already mapped its
    # categories once does not map them differently here. Read ONCE per run and
    # shared by stage 3 and stage 4 (`DEF-544`: a load that resolves against a
    # different world than stage 3 showed is a defect, not a race).
    TARGET_PREMISES: lambda: {
        "premises_type": _premises_type_index(),
        "owner_account_type": seams.account_lookup_indexes().get("account_type", {}),
        # ⛔ **A THIRD LOOKUP ON THIS TARGET (PO ruling 2026-09-19).** ⚠ **A
        # `KIND_LOOKUP` COLUMN WITH NO ENTRY HERE RESOLVES TO `None` AND SAYS
        # NOTHING** — the branch answers `lookup_indexes.get(target) or {}` —
        # so the column would ship, map, show `Matched` and create no party.
        # `tests/test_def_met_5802_declared_columns.py` asserts every lookup
        # column on this target has an index, because the failure is silent.
        "owner_category": _owner_category_index(),
    },
    TARGET_UNITS: lambda: {"unit_type": _unit_type_index()},
    # BR-MET-530 — the meters target carries a FOURTH lookup and the sub-meters
    # target does not, because the size column exists on one template and not
    # the other (PO ruling 2026-08-28, judgment 4). Spread rather than
    # parameterised so that reading this table tells you which target resolves
    # what, without opening the builder.
    #
    # ⛔ **PLAN U2 (PO ruling 2026-09-30) — `unit` (the unit of measure) on all
    # three sheets, and the DEVICES sheet gains `service` and `size_class`.**
    # A `KIND_LOOKUP` column with no index here resolves to `None` and says
    # nothing (`DEF-MET-5802`'s warning above), so each new lookup column is
    # added here in the SAME commit as its column.
    TARGET_ASSETS_METERS: lambda: {
        **_assets_measuring_indexes(),
        "size_class": seams.service_size_class_index(),
        "unit": seams.asset_upload_scopes()["uom_index"],
    },
    TARGET_ASSETS_SUBMETERS: lambda: {
        **_assets_measuring_indexes(),
        "unit": seams.asset_upload_scopes()["uom_index"],
    },
    TARGET_ASSETS_DEVICES: lambda: {
        "type": seams.assets_lookup_index("device_types"),
        "service": {code.lower(): code for code in seams.enabled_service_codes()},
        "size_class": seams.service_size_class_index(),
        "unit": seams.asset_upload_scopes()["uom_index"],
    },
    # CR-030 W1 — four lookups, one seam call. Read ONCE per run and shared by
    # stage 3 and stage 4, so the judgment and the write resolve identically
    # (DEF-544's lesson, the same reason `_unit_reference_index` is shared).
    TARGET_ACCOUNTS: seams.account_lookup_indexes,
    # ⛔ **CR-168 · `DEF-WRK-9587` — THE PARTS TARGET HAD NO ENTRY HERE, AND
    # `DEF-MET-5802`'s WARNING ABOVE IS EXACTLY WHAT IT COST.** `category` is a
    # `KIND_LOOKUP` column, so with no index it resolved to `None` on every
    # row: the heading read *Matched*, Validate said *blank in all 5 rows*,
    # and every part loaded with no category although the file named one the
    # register holds. Work's own published index answers (name AND code →
    # the name `_clean_part` resolves), read through the seam — `parts` and
    # `part_categories` are work's tables (`G78`).
    TARGET_PARTS: lambda: {"category": seams.part_category_index()},
}


def _lookup_indexes_for(target: str) -> dict[str, dict[str, str]]:
    builder = LOOKUP_INDEX_BUILDERS.get(target)
    return builder() if builder is not None else {}


def _unit_reference_index() -> dict[str, str]:
    """LOWERED unit reference → unit id, for BR-AST-045's tagging — built ONCE
    per run and shared by stage 3 (through the world) and stage 4 (the load),
    so the judgment and the write resolve identically (DEF-544).

    Three reference shapes, in the vocabulary `unit_id_for_reference` already
    ratified for the retired staged import (BR-AST-034): the unit NUMBER
    (`SCW-U-012`), a `premise · label` pair, and — for convenience only — a
    bare label that is unique across the whole tenant. An ambiguous bare label
    resolves to NOTHING rather than to a guess.
    """
    index: dict[str, str] = {}
    labels: dict[str, list[str]] = {}
    rows = models.Unit.objects.filter(
        tenant_id=_tenant_id(), deleted_at__isnull=True
    ).select_related("premises")
    for row in rows:
        unit_id = str(row.id)
        if row.unit_no:
            index[str(row.unit_no).strip().lower()] = unit_id
        label = str(row.label or "").strip().lower()
        premise_no = str(getattr(row.premises, "premise_no", "") or "").strip().lower()
        if premise_no and label:
            index[f"{premise_no} · {label}"] = unit_id
        if label:
            labels.setdefault(label, []).append(unit_id)
    for label, ids in labels.items():
        if len(ids) == 1 and label not in index:
            index[label] = ids[0]
    return index


def _unit_premises_index() -> dict[str, str]:
    """unit id → its premises id (both str) — the same-premises warning's map."""
    return {
        str(unit_id): str(premises_id)
        for unit_id, premises_id in models.Unit.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True
        ).values_list("id", "premises_id")
    }


def _premises_units_index() -> dict[str, tuple[str, ...]]:
    """LOWERED premise_no → its unit ids — the devices target's world: a named
    premises must exist, and a premises-level attach seats on its ONE unit."""
    index: dict[str, list[str]] = {}
    rows = models.Premises.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True).exclude(
        premise_no__isnull=True
    )
    for row in rows:
        index[str(row.premise_no).strip().lower()] = []
    for unit_id, premise_no in models.Unit.objects.filter(
        tenant_id=_tenant_id(), deleted_at__isnull=True, premises__premise_no__isnull=False
    ).values_list("id", "premises__premise_no"):
        index.setdefault(str(premise_no).strip().lower(), []).append(str(unit_id))
    return {key: tuple(value) for key, value in index.items()}


def _premises_offer_index() -> dict[str, dict[str, Any]]:
    """premises id → what the ADDRESS offers (BR-MET-119, CR-036 · DEF-772).

    ⚠ `services` is carried AS STORED, `None` included. `or []` here would
    erase the distinction one layer below the rule that depends on it — an
    address nobody has been asked about would read as one that answered
    "nothing" (DEF-762's shape), and the operator would be told to remove a
    service from a row instead of to go and say what the address offers.
    """
    return {
        str(row_id): {
            "ref": (
                str(premise_no or "").strip() or str(address or "").strip() or "this address"
            ),
            "services": services,
        }
        for row_id, premise_no, address, services in models.Premises.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True
        ).values_list("id", "premise_no", "address_line", "services_available")
    }


def _owner_indexes() -> dict[str, Any]:
    """The two owner indexes stage 3 judges an `Owner` cell against.

    ⚠ **ONE QUERY, TWO INDEXES, AND THEY ANSWER DIFFERENT QUESTIONS.** The
    EXACT one is the database's own uniqueness key
    (`uq_premises_owners_tenant_name_ci`), so a hit is a fact and the load
    reuses the party. The NEAR one is a normalised-name bucket, so a hit is a
    QUESTION for a person — never an answer this code may take (PO decision 3).

    ⚠ **INACTIVE PARTIES ARE IN THE *EXACT* INDEX AND NOT THE *NEAR* ONE, AND
    THE ASYMMETRY IS DELIBERATE.** `_resolve_owner` refuses to link a retired
    owner, so a file naming one must be told so precisely rather than being
    quietly offered a different party that happens to look similar.
    """
    from apps.metering.premises_owners import _normalise_owner_name

    exact: dict[str, str] = {}
    near: dict[str, list[dict[str, Any]]] = {}
    for owner_id, name, active in models.PremisesOwner.objects.filter(
        tenant_id=_tenant_id()
    ).values_list("id", "name", "active"):
        text = str(name or "").strip()
        if not text:
            continue
        exact.setdefault(text.lower(), str(owner_id))
        if not active:
            continue
        key = _normalise_owner_name(text)
        if key:
            near.setdefault(key, []).append({"id": str(owner_id), "name": text})
    return {"owner_exact": exact, "owner_near": near}


def _world(*, write_mode: str | None = None) -> import_rules.World:
    """⚠ **ONE WORLD FOR BOTH TARGETS (`BR-MET-096`).** The units half is read
    unconditionally rather than behind `if target == units`: the reads are a
    handful of small queries, and a world whose contents depend on the target
    is the branch that ruling forbids — it would also mean a units rule that
    started reading `existing_addresses` silently saw an empty set."""
    from apps.tenancy import models as tenancy_models

    tenant_id = _tenant_id()
    premises = models.Premises.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True)
    units = models.Unit.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True)
    return import_rules.World(
        enabled_services=seams.enabled_service_codes(),
        premises_type_codes=set(_premises_type_index().values()),
        area_names={
            str(name).strip().lower()
            for name in tenancy_models.Area.objects.filter(tenant_id=tenant_id).values_list(
                "name", flat=True
            )
        },
        existing_premise_nos={
            value
            for value in premises.exclude(premise_no__isnull=True).values_list(
                "premise_no", flat=True
            )
            if value
        },
        existing_addresses={
            str(value).strip().lower()
            for value in premises.values_list("address_line", flat=True)
            if value
        },
        # ── the units half (`BR-MET-096`) ────────────────────────────────
        plan_index=seams.assignable_plan_index(),
        existing_unit_keys={
            (str(premise_no or "").strip().lower(), str(label or "").strip().lower())
            for premise_no, label in units.values_list("premises__premise_no", "label")
            if label
        },
        unit_type_codes={code.lower() for code in _unit_type_index().values()},
        # ── CR-046 C3/C4 — the two identifier indexes the new rules judge
        # against. Read unconditionally, like everything else in this world
        # (BR-MET-096's posture) — a world whose contents depend on the target
        # is the branch that ruling forbids.
        existing_unit_nos={
            str(value).strip().lower()
            for value in units.exclude(unit_no__isnull=True).values_list("unit_no", flat=True)
            if value
        },
        # ⚠ THROUGH THE SEAM — `accounts` is customers' table (B1/B2 §2) and
        # this is the SAME index the accounts loader matches with, so stage 3
        # and stage 4 cannot disagree about what is on file (DEF-544).
        existing_account_nos={
            key for key in seams.accounts_import_index() if not key.startswith("ext:")
        },
        # ── the parts half (CR-077) — read through work's own published
        # index, because `parts` is work's table and this module may not query
        # it (`BR-WRK-002`, `G78`). It is the SAME index the parts loader
        # matches with, so stage 3 and stage 4 cannot disagree (DEF-544).
        existing_part_nos=set(seams.parts_import_index()),
        part_categories=seams.part_category_index(),
        # ── the payments half (`P1.1`) — read through payments' own published
        # index, because `payments` is their table. It is the SAME index
        # `_load_payments_rows` matches with, so the rehearsal an operator
        # reads and the commit they press cannot disagree (`DEF-544`).
        #
        # ⚠ **`None` SURVIVES THIS LINE UNCHANGED, WHICH IS THE POINT.** An
        # `or {}` here would turn *"payments cannot answer"* into *"this
        # utility has no accounts"* one layer above the rules that depend on
        # the distinction — `DEF-762`'s shape, on a money path.
        payments_account_index=seams.payments_import_index(),
        # `DEF-PAY-10697` (LBX-08) — asked once per run, about this file's
        # cheques only; the rule holds a cheque payments already has.
        payments_posted_cheques=seams.payments_posted_cheques,
        # ── the assets half (CR-028 AST-W3) — same unconditional posture ──
        today=seams.tenant_today(),
        asset_index=seams.assets_import_index(),
        unit_ref_index=_unit_reference_index(),
        unit_service_taken={
            (row["unit_id"], row["service"]): row["asset_no"]
            for row in seams.active_service_assignments()
        },
        unit_premises=_unit_premises_index(),
        premises_units=_premises_units_index(),
        premises_offer=_premises_offer_index(),
        # DEF-935 — ONE query for every enabled service's unit, so
        # `AST.SERVICE_HAS_UNIT` can reject at stage 3 what
        # `_check_measuring_requirements` would otherwise refuse inside the
        # commit. `service_default_uoms` and not `service_default_uom` per row,
        # for DEF-324's measured reason.
        service_units=seams.service_default_uoms(),
        # ── plan U4 (PO 2026-09-30) — the service each size and unit belongs
        # to, for `AST.SIZE_FOR_SERVICE` / `AST.UOM_FOR_SERVICE`. One read.
        **_asset_scope_world(),
        # ── CR-046 wave B — the RUN'S OWN write mode, so a rule can act on
        # the PO's *"in case of insert - reject it"*. Keyword-only and
        # defaulting to None: every other caller of `_world()` is asking a
        # question no mode changes, and None keeps the pre-CR-046 answer.
        write_mode=write_mode,
        # ── CR-047 · DEF-2519 — the two facts `ACC.UNIT_NOT_OCCUPIED` and
        # `ACC.START_DATE_REQUIRED` judge against, read ONCE (DEF-324) and
        # through the customers seam (B1/B2 §2), unconditionally like the rest
        # of this world (BR-MET-096 forbids a per-target branch here).
        occupied_unit_ids=_occupied_unit_ids(),
        occupying_status_codes=seams.occupying_account_status_codes(),
        # ── DEF-1088 · BR-MET-402 — the tenant's typed owners, read ONCE ──
        **_owner_indexes(),
    )


def _asset_scope_world() -> dict[str, Any]:
    scopes = seams.asset_upload_scopes()
    return {"size_service": scopes["size_service"], "uom_service": scopes["uom_service"]}


def _occupied_unit_ids() -> frozenset[str]:
    """The unit ids that already hold a LIVE account — BR-CUS-017's world.

    ⚠ **ONE SEAM CALL FOR THE WHOLE TENANT, NOT ONE PER ROW.**
    `seams.accounts_for_units` exists for exactly this shape (CR-029 D7: *"one
    account query plus one contact query EACH — the N+1 D7 ruled against"*),
    and DEF-324 measured what the per-row form costs: `enabled_service_codes()`
    spent 47 of 118 profiled seconds answering one question 304 times.

    ⚠ **THE UNIT IDS COME FROM `_unit_premises_index()`, WHICH THIS RUN'S WORLD
    ALREADY READS** — the same query, asked once, rather than a second walk of
    `units` for the same ids.

    ⚠ **"OCCUPIED" IS CUSTOMERS' READING AND NOT OURS.** That selector filters
    on `OCCUPYING_BEHAVIOR_CLASSES` with the same first-by-`created_at`
    tie-break `active_account_for_unit` takes, which is what
    `_refuse_if_unit_occupied` asks under the lock — so the rehearsal and the
    writer cannot come to different answers about one unit (DEF-544's law).

    An EMPTY set is a real and honest state: customers holds no occupying
    account, so no unit is taken. It is not the same as "nobody was asked" —
    that is `occupying_status_codes`' `None`, and the rules read it first.
    """
    unit_ids = list(_unit_premises_index())
    if not unit_ids:
        return frozenset()
    return frozenset(str(unit_id) for unit_id in seams.accounts_for_units(unit_ids))


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def validate(actor: Any, run_id: Any, write_mode: str | None = None) -> dict[str, Any]:
    """Stage 3 — run the rules, store them AS THEY WERE, judge every row.
    **STILL NO PREMISES ROW.**

    ⚠ Tier 1 stops the row before tier 2 is asked (B15 §4.3A), so a premises
    with no address does not also appear in the *"already on file at this
    address"* count — it has no address to compare.

    ⚠ The rule results are written from the set resolved at THIS moment and are
    never recomputed afterwards (BR-MET-090). A receipt that said *"2
    warnings"* in July must still say it in August, whatever the utility has
    since changed.
    """
    # CR-026 — over the bar this goes to a worker (see `transform` for why the
    # refusals are taken first, on the unlocked read).
    run = _run(run_id)
    _refuse_committed(run)
    if _defers(run, "validate"):
        return _defer(actor, run, "validate", {"write_mode": write_mode})
    return _validate_apply(actor, run_id, import_progress.NULL, write_mode)


def _validate_apply(
    actor: Any,
    run_id: Any,
    reporter: import_progress.Reporter,
    write_mode: str | None = None,
) -> dict[str, Any]:
    """Stage 3's body, UNDECORATED — the one path a request and a worker share.

    ⚠ **THE LOCK MUST BE INSIDE A TRANSACTION, AND A REAL REQUEST DOES NOT
    BRING ONE (`DEF-529`, critical).** `_run(locked=True)` issues
    `SELECT … FOR UPDATE`; Postgres refuses it outside a transaction, and
    `ATOMIC_REQUESTS` is set nowhere in `config/settings`. All 49 tests over
    these two functions passed because **pytest-django wraps every test in a
    transaction** — so the lock was legal in the suite and illegal in
    production, and stage 2 returned a 500 on every real run until the first
    browser walkthrough found it.
    """
    with transaction.atomic():
        return _validate_locked(actor, run_id, reporter, write_mode)


def _validate_locked(
    actor: Any,
    run_id: Any,
    reporter: import_progress.Reporter,
    write_mode: str | None = None,
) -> dict[str, Any]:
    """The body of `validate`, with the run row LOCKED. The caller already holds
    the transaction that lock requires — see the note above.

    ⚠ **`write_mode` IS RE-RECORDED HERE, NOT ONLY AT STAGE 1 (CR-046 wave B).**
    Stage 1 is where the operator CHOOSES, and stage 4 offers *Change it*, which
    walks back to step 1 (DEF-770) — so a run can be judged more than once, and
    the mode that matters is the one in force at the moment stage 3 judges. This
    is that moment. Absent leaves the run's recorded mode untouched, so a client
    that sends it nowhere behaves exactly as it did before this change."""
    run = _run(run_id, locked=True)
    if write_mode:
        _refuse_withdrawn_mode(write_mode, target=run.target)
        if write_mode not in WRITE_MODES:
            _refuse(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="metering.import.kind_unknown",
                allowed=list(WRITE_MODES),
            )
        if run.write_mode != write_mode:
            run.write_mode = write_mode
            run.save(update_fields=["write_mode", "updated_at"])
    _refuse_committed(run)  # BR-MET-090 — a committed run's rehearsal is closed
    if run.status == "extracted":
        # Validating a run nobody mapped means there is no mapping, which means
        # every required column is unmapped — the same refusal stage 2 gives,
        # arrived at from the other side, naming THIS target's own required set.
        required = [
            column["target"] for column in target_columns(run.target) if column.get("required")
        ]
        _refuse(
            errors.VAL_REQUIRED,
            message_key="metering.import.required_column_unmapped",
            targets=required or ["address_line"],
        )

    rows = list(
        models.ImportRunRow.objects.filter(tenant_id=run.tenant_id, run=run)
        .exclude(outcome__in=("duplicate", "skipped"))
        .order_by("row_no")
    )
    payloads = [
        {"row_no": row.row_no, "mapped": row.mapped or {}, "problems": _problems_for(row)}
        for row in rows
    ]
    # CR-046 wave B — the run's own mode, recorded at stage 1, decides the
    # severity of `AST.NUMBER_ON_FILE` and travels into the world the
    # evaluators read. NULL on a run extracted before this landed, and the
    # resolver returns the catalogue unchanged for that case.
    rules = import_rules.resolve(run.target, run.tenant_id, run.write_mode)
    world = _world(write_mode=run.write_mode)
    checked_total = len(payloads)

    blocked: set[int] = set()
    worst: dict[int, str] = {}
    #: The sentence a row SHOWS. The first ERROR wins outright; a warning's
    #: sentence is only shown on a row that has no error, because *"errors
    #: block the load, warnings don't"* and the operator has to be told the
    #: thing that stopped the row before the thing that merely worried us.
    said: dict[int, tuple[str, str | None]] = {}
    results: list[dict[str, Any]] = []

    for index, rule in enumerate(rules, start=1):
        # CR-026 — the gauge, and it is honest about its own arithmetic: EVERY
        # rule walks EVERY candidate row, so the work is rules x rows and the
        # figure a screen prints is that fraction expressed in the units the
        # operator counts in. *"Checking rule 4 of 11"* says where it really is.
        reporter.mark(
            int(checked_total * (index - 1) / len(rules)) if rules else 0,
            f"Checking rule {index} of {len(rules)}",
        )
        candidates = (
            payloads
            if rule.tier == import_rules.TIER_STRUCTURAL
            else [row for row in payloads if row["row_no"] not in blocked]
        )
        hits = import_rules.evaluate(rule, candidates, world)
        for hit in hits:
            if rule.severity == import_rules.ERROR:
                if worst.get(hit.row_no) != import_rules.ERROR:
                    said[hit.row_no] = (hit.problem, hit.fix_hint)
                elif run.target in ALL_PROBLEMS_TARGETS:
                    # ⛔ **PLAN U4 — "ALL PROBLEMS AT ONCE" (PO 2026-09-30,
                    # `DEF-AST-8100`).** The first error used to win outright, so
                    # a row with a wrong size, a wrong unit and no service took
                    # three uploads to fix. On the asset sheets every error is
                    # JOINED onto the row, in rule order, each sentence whole —
                    # the failures file and the rejects screen read `problem`,
                    # so both show all of them without a second column.
                    problem, fix_hint = said[hit.row_no]
                    said[hit.row_no] = (
                        f"{problem} {hit.problem}",
                        " ".join(part for part in (fix_hint, hit.fix_hint) if part) or None,
                    )
                blocked.add(hit.row_no)
                worst[hit.row_no] = import_rules.ERROR
            elif rule.severity == import_rules.WARNING:
                if hit.row_no not in worst:
                    worst[hit.row_no] = import_rules.WARNING
                    said[hit.row_no] = (hit.problem, hit.fix_hint)
        results.append({"rule": rule, "hits": len(hits)})

    reporter.mark(checked_total, "Saving the results")
    errors_count = sum(1 for value in worst.values() if value == import_rules.ERROR)
    warnings_count = sum(1 for value in worst.values() if value == import_rules.WARNING)
    checked = len(payloads)

    with transaction.atomic():
        # CR-026 — same shape as transform's: bounded bulk_update, explicit
        # `updated_at` because bulk_update skips auto_now.
        now = timezone.now()
        for row in rows:
            severity = worst.get(row.row_no)
            if severity == import_rules.ERROR:
                row.outcome = "rejected"
            elif severity == import_rules.WARNING:
                row.outcome = "flagged"
            else:
                row.outcome = "staged"
            if row.row_no in said:
                row.problem, row.fix_hint = said[row.row_no]
            else:
                row.problem = None
                row.fix_hint = None
            row.updated_at = now
        bulk_write.update_import_rows(
            rows,
            ["outcome", "problem", "fix_hint", "updated_at"],
            tenant_id=run.tenant_id,
            run_id=run.id,
            batch_size=1000,
        )

        models.ImportRuleResult.objects.filter(tenant_id=run.tenant_id, run=run).delete()
        models.ImportRuleResult.objects.bulk_create(
            [
                models.ImportRuleResult(
                    tenant_id=run.tenant_id,
                    run=run,
                    rule_code=entry["rule"].code,
                    tier=entry["rule"].tier,
                    sentence=entry["rule"].sentence,
                    severity=entry["rule"].severity,
                    action=entry["rule"].action,
                    action_value=entry["rule"].action_value,
                    hits=entry["hits"],
                    available=entry["rule"].available,
                    unavailable_reason=entry["rule"].unavailable_reason,
                    is_sample=run.is_sample,
                )
                for entry in results
            ]
        )
        run.counts = {
            **(run.counts or {}),
            "checked": checked,
            "clean": checked - errors_count - warnings_count,
            "errors": errors_count,
            "warnings": warnings_count,
            # ⛔ **CR-058 W7 · BR-CUS-1041 — THE MITIGATION FIGURE, MEASURED
            # HERE BECAUSE THIS IS THE LAST STAGE THAT CAN SEE THESE ROWS.**
            # The rule rejects them (`ACC.CUSTOMER_IDENTITY_REQUIRED`), so stage
            # 4 never meets one to count it — and a receipt that cannot say
            # *"1,213 rows need an identifier"* makes a half-identified
            # migration look identical to a finished one, which the utility
            # discovers at its first bill run. Decision log 2026-09-01,
            # judgment 2. 0 on every other target and on every run validated
            # before today, which is the honest reading of *"the run did not
            # say"* rather than a claim that nothing was missing.
            **_identity_counts(run.target, results),
        }
        run.status = "validated"
        run.save(update_fields=["counts", "status", "updated_at"])
        _audit(
            actor,
            "import_run.validated",
            run.id,
            run_no=run.run_no,
            checked=checked,
            errors=errors_count,
            warnings=warnings_count,
        )
    return run_dict(run, with_rules=True)


def _identity_counts(target: str, results: list[dict[str, Any]]) -> dict[str, int]:
    """CR-058 W7 — how many rows this file cannot create a customer for.

    Read off the rule results the validate stage just wrote, so the figure and
    the rejections come from ONE evaluation of ONE verdict function. Counting
    the rows a second time here would be a second derivation of one number,
    which is how two figures on one receipt come to disagree.

    `{}` on every other target, so the key is ABSENT rather than zero on a
    premises run: `receipt()` reads a missing key as 0 and a screen draws the
    figure only when it is non-zero.
    """
    if target != TARGET_ACCOUNTS:
        return {}
    hits = {entry["rule"].code: int(entry["hits"]) for entry in results}
    return {
        "accounts_awaiting_identity": hits.get("ACC.CUSTOMER_IDENTITY_REQUIRED", 0),
        "accounts_identity_mismatch": hits.get("ACC.CUSTOMER_IDENTITY_MISMATCH", 0),
    }


def _problems_for(row: models.ImportRunRow) -> dict[str, Any]:
    """Stage 2's carried parse problems, read back exactly as stage 2 wrote
    them — never re-parsed. See `PARSE_PROBLEMS`."""
    return dict((row.mapped or {}).get(PARSE_PROBLEMS) or {})


# ═══════════════════════════════════════════════════════════════════════════
# READS
# ═══════════════════════════════════════════════════════════════════════════


#: How many rejects ride with a run payload when the caller names no window.
#: 50 is the screen's OWN first page — `DEFAULT_PAGE_SIZE` in
#: `07-frontend/src/components/tableTypes.ts` — so the poll carries what the
#: table draws and not one row more (DEF-766).
REJECT_WINDOW_DEFAULT = 50
#: The largest window this module will build in ONE answer. 1,000 is the biggest
#: page the shared pager offers (`PAGE_SIZES` ends there), so an operator can
#: still ask for the biggest page this product has — and no client can ask for a
#: 9,881-row payload by naming a bigger number. There is deliberately NO escape
#: hatch: an unbounded path left in the module is the one the next caller uses.
REJECT_WINDOW_MAX = 1_000


def run_dict(
    run: models.ImportRun,
    *,
    with_rules: bool = False,
    reject_offset: Any = 0,
    reject_limit: Any = REJECT_WINDOW_DEFAULT,
) -> dict[str, Any]:
    """The run, as every stage answers it — and as the receipt reads it.

    `reject_offset` / `reject_limit` name the WINDOW of the reject list this
    answer carries (DEF-766). They are ignored unless `with_rules` — a payload
    with no rejects in it has no window to describe."""
    payload: dict[str, Any] = {
        "id": str(run.id),
        "run_no": run.run_no,
        "target": run.target,
        "source_kind": run.source_kind,
        "file_name": run.file_name,
        "file_hash": run.file_hash,
        "file_bytes": run.file_bytes,
        "encoding_delimiter": run.encoding_delimiter,
        "mapping_id": str(run.mapping_id) if run.mapping_id else None,
        "mapping_spec": run.mapping_spec,
        "batch_label": run.batch_label,
        "write_mode": run.write_mode,
        "counts": run.counts or {},
        "status": run.status,
        "session_ref": run.session_ref,
        "ip": run.ip,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        # CR-026 — **the gauge travels with EVERY import answer**, so a screen
        # polling a deferred stage reads one payload rather than two, and so a
        # client cannot be built that knows about the run and not about its
        # progress. `None` for every synchronous run: there was no moment at
        # which anyone could have polled it (`import_progress`'s docstring).
        "progress": import_progress.read(run),
    }
    if with_rules:
        payload["rules"] = rule_results(run)
        # ⚠ **A WINDOW, NOT THE LIST (DEF-766).** This payload is polled every
        # two seconds while a stage is in a worker, and every reject carries its
        # full `raw` cells for the inline editor. On the PO's own all-reject run
        # — 9,881 rejects — the unbounded list built 4.28 MB in 0.48s, and the
        # table on screen has drawn 50 rows a page since the fix-button work, so
        # every one of the other 9,831 rows was built, serialised, sent and
        # thrown away. The TOTAL travels beside the window: an operator must
        # read *"9,881"*, never *"50"*.
        offset, limit = reject_window(reject_offset, reject_limit)
        payload["rejects"] = rejects(run, offset=offset, limit=limit)
        payload["rejects_window"] = {
            "total": reject_total(run),
            "offset": offset,
            "limit": limit,
        }
        # ⚠ BR-MET-091's arithmetic, SERVED rather than assumed by a screen.
        # Stage 3's sub-line promises *"Errors block the load"*; since
        # `BR-MET-097` (PO 2026-08-21) ruled that an imported address is
        # accepted as given, there is no PLATFORM rule of error severity left
        # on a premises import, and the only errors that can block are the five
        # structural ones no utility can configure. `platform: 0` is the ruled
        # answer here, not a missing implementation.
        results = [
            entry
            for entry in payload["rules"]
            if entry["available"] and entry["severity"] == import_rules.ERROR
        ]
        payload["blocking_rules"] = {
            "count": len(results),
            "platform": sum(1 for entry in results if entry["tier"] == import_rules.TIER_PLATFORM),
            "structural": sum(
                1 for entry in results if entry["tier"] == import_rules.TIER_STRUCTURAL
            ),
        }
    return payload


def rule_results(run: models.ImportRun) -> list[dict[str, Any]]:
    """r10's RULES THAT RAN table — `RULE | SEVERITY | HITS | ACTION`, plus the
    unavailable ones and WHY (BR-MET-091)."""
    return [
        {
            "code": row.rule_code,
            "tier": row.tier,
            "sentence": row.sentence,
            "severity": row.severity,
            "action": row.action,
            "action_value": row.action_value,
            "hits": row.hits,
            "available": row.available,
            "unavailable_reason": row.unavailable_reason,
        }
        for row in models.ImportRuleResult.objects.filter(
            tenant_id=run.tenant_id, run=run
        ).order_by("tier", "rule_code")
    ]


def reject_window(offset: Any, limit: Any) -> tuple[int, int]:
    """`(offset, limit)`, clamped — the ONE place the window is decided.

    A garbled value takes the default rather than refusing: this is the surface
    a screen polls every two seconds and a refusal mid-poll would blank a stage
    the operator is watching. `rejects` and `run_dict` both come through here,
    so the rows served and the `limit` the payload reports cannot disagree.
    """
    try:
        start = int(offset)
    except (TypeError, ValueError):
        start = 0
    try:
        size = REJECT_WINDOW_DEFAULT if limit is None else int(limit)
    except (TypeError, ValueError):
        size = REJECT_WINDOW_DEFAULT
    return max(0, start), max(0, min(size, REJECT_WINDOW_MAX))


def _reject_rows(run: models.ImportRun):
    """This run's rejected rows, in the operator's own row order."""
    return models.ImportRunRow.objects.filter(
        tenant_id=run.tenant_id, run=run, outcome="rejected"
    ).order_by("row_no")


def reject_total(run: models.ImportRun) -> int:
    """How many rows this run rejected — a COUNT in the database, never a
    `len()` over a list this process built. It is the figure the operator reads
    (*"9,881 rejected"*), so it must not be a property of the window."""
    return _reject_rows(run).count()


def rejects(
    run: models.ImportRun,
    *,
    offset: Any = 0,
    limit: Any = REJECT_WINDOW_DEFAULT,
) -> list[dict[str, Any]]:
    """ONE WINDOW of the reject list r10 draws under the rules — row, key,
    problem, fix.

    `raw` (CR-028 debt sweep D8, 2026-08-22): the row's SOURCE cells, exactly
    as staged — what the stage-3 inline "fix here" editor edits and what
    `fix_row` patches by the same column names. Serving the cells with the
    reject is what makes the r10 sentence — *"Fix the rejects here — no need
    to re-upload"* — possible on screen; without them the operator could name
    a column but never see its current value. **Which is also why this had to
    be bounded rather than trimmed:** the cells cannot be dropped from a reject
    without taking the editor with them, so what shrinks is the NUMBER of
    rejects in one answer.

    ⚠ **DEF-766 — THIS WAS UNBOUNDED, AND IT IS POLLED.** `GET /imports/{id}`
    is asked every two seconds for as long as an operator leaves the tab open;
    on a clean run it answers in 12ms and on the PO's 9,881-reject run it built
    **4.28 MB in 0.48s**, every row carrying its full `raw` cells — while the
    table on screen has drawn one 50-row page since the fix-button work. Nothing
    caught it because **every test asserted reject CONTENT and none asserted
    payload SIZE**, and no reject fixture in the repo exceeded 20 rows;
    `tests/test_def766_reject_payload_bound.py` is the fixture that can see it.

    The caller states the window and `run_dict` serves the TOTAL beside it, so
    bounding the payload never costs the operator the figure that matters.
    """
    start, size = reject_window(offset, limit)
    # ⛔ **`BR-MET-1032` — THE CELLS TRAVEL AS THEY ARE STORED, WHICH IS THE
    # POINT.** A row staged since that rule holds `••••6789`
    # in the cell and the nine digits nowhere in this payload, so the last-four
    # promise is a property of the STORE rather than of a screen remembering to
    # mask. `masked` names which cells are showing that way, because the inline
    # editor has to treat them differently — see `fix_row`.
    return [
        {
            "row_no": row.row_no,
            "source_key": row.source_key,
            "problem": row.problem,
            "fix_hint": row.fix_hint,
            "outcome": row.outcome,
            # ⚠ **THE VAULT NEVER LEAVES THE SERVER.** It holds the envelopes;
            # a payload carrying them would put the ciphertext of every
            # identifier in the file on the wire every two seconds, and a
            # ciphertext is still the value's shadow — nothing on a screen has
            # any use for one.
            "raw": {
                key: value
                for key, value in (row.raw or {}).items()
                if key != import_identity.VAULT
            },
            "masked": import_identity.masked_keys(row.raw or {}),
        }
        for row in _reject_rows(run)[start : start + size]
    ]


def read_run(
    run_id: Any,
    *,
    with_rules: bool = True,
    reject_offset: Any = 0,
    reject_limit: Any = REJECT_WINDOW_DEFAULT,
) -> dict[str, Any]:
    run = models.ImportRun.objects.filter(tenant_id=_tenant_id(), pk=run_id).first()
    if run is None:
        raise errors.NotFoundError()
    return run_dict(
        run,
        with_rules=with_rules,
        reject_offset=reject_offset,
        reject_limit=reject_limit,
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def fix_row(actor: Any, run_id: Any, row_no: int, payload: Any) -> dict[str, Any]:
    """r10 stage 3's inline correction — *"Fix the rejects here — no need to
    re-upload"* (WFL-01.meters.3; CR-028 makes it real for every target).

    `values` patches the row's RAW cells by SOURCE COLUMN name — the exact
    cells the operator sees — so *"Load into inventory instead"* is one call
    clearing `UNIT_REF` (BR-AST-045: blank is accepted). ⚠ **THE RUN GOES BACK
    TO `extracted`**: a fixed cell invalidates that row's mapping and its
    judgment, and a load over a stale verdict is the one outcome this workflow
    exists to prevent — so stages 2–3 must run again (the stored
    `mapping_spec` makes the re-map one click) and `load` refuses until they
    have. A committed run refuses outright (BR-MET-090)."""
    data = payload if isinstance(payload, dict) else {}
    values = data.get("values")
    if not isinstance(values, dict) or not values:
        _refuse(errors.VAL_REQUIRED, message_key="metering.import.fix_values_required")
    with transaction.atomic():
        run = _run(run_id, locked=True)
        _refuse_committed(run)
        row = (
            models.ImportRunRow.objects.filter(tenant_id=run.tenant_id, run=run, row_no=row_no)
            .select_for_update()
            .first()
        )
        if row is None:
            raise errors.NotFoundError()
        raw = dict(row.raw or {})
        # `BR-MET-1032` — the vault is not a cell an operator can name.
        vault = dict(raw.pop(import_identity.VAULT, None) or {})
        unknown = [key for key in values if key not in raw]
        if unknown:
            _refuse(
                errors.VAL_FORMAT,
                message_key="metering.import.unknown_mapping_target",
                target=unknown[0],
            )
        for key, value in values.items():
            raw[key] = None if value is None else str(value)
            # ⛔ **A PATCHED IDENTITY CELL DROPS ITS OLD VAULT ENTRY AND IS
            # RE-PROTECTED BELOW.** Leaving the entry would mean the cell on
            # screen said one number and the envelope beside it held another —
            # and the envelope is the one the matcher reads, so the operator's
            # correction would appear to take and change nothing.
            vault.pop(key, None)
        if vault:
            raw[import_identity.VAULT] = vault
        # Re-protect from the map the operator confirmed. A run that has not
        # reached stage 2 has no confirmed map; those cells are protected when
        # `transform` runs, which it must before anything loads.
        row.raw = import_identity.protect_cells(
            raw,
            identity_source_columns(run.target, ((run.mapping_spec or {}).get("columns")) or {}),
        )
        row.outcome = "staged"
        row.problem = None
        row.fix_hint = None
        row.save(update_fields=["raw", "outcome", "problem", "fix_hint", "updated_at"])
        if run.status in ("transformed", "validated"):
            run.status = "extracted"
            run.save(update_fields=["status", "updated_at"])
        _audit(
            actor,
            "import_run.row_fixed",
            run.id,
            run_no=run.run_no,
            row=row_no,
            columns=sorted(values.keys()),
        )
    result = run_dict(run)
    result["fixed_row"] = {"row_no": row_no, "raw": raw}
    return result


# ══════════════════════════════════════════════════════════════════════════
# STAGE 4 · LOAD — the only stage that writes
#
# ⚠ **THREE PO RULINGS DECIDE THIS STAGE AND EACH IS IMPLEMENTED WHERE IT IS
# NAMED.** `BR-MET-098` (approval at 5% OR 10 rows, whichever first),
# `BR-MET-099` (*replace the batch* deactivates, refuses occupied, never
# deletes) and `BR-MET-100` (a units row naming a missing plan LOADS, flagged).
# ══════════════════════════════════════════════════════════════════════════

#: `BR-MET-098` — the two bars, and BOTH are the tenant's to set. These are the
#: defaults until a settings screen exists (`DEF-525`). A percentage alone makes
#: 5% mean ONE row on a 20-row correction batch; a count alone lets 200 rejects
#: in 5,000 rows pass unseen. So the big file is governed by the percentage and
#: the small one by the count, and the screen prints both beside the run's own
#: numbers.
APPROVAL_PCT = 5
APPROVAL_ROWS = 10

#: **THE APPROVER'S ANSWER, CARRIED FROM THE DOOR TO THE WORKER (`DEF-1108`).**
#: `BR-MET-098` names the approver by ROLE, and a role only exists on a request.
#: Over `ASYNC_ROW_BAR` the commit finishes in a worker carrying `_JobActor` —
#: an id and no role *by design* — so the question has to be ANSWERED where it
#: can be, and the answer travels. `load()` writes this key itself, after its
#: own role check passes, and strips any caller-supplied copy first; it is
#: therefore a statement the engine made, never one it was told.
APPROVED_BY_KEY = "approved_by_user_id"


def _has_approver_role(actor: Any) -> bool:
    """`BR-MET-098`'s approver clause, asked of an actor that HAS a role.

    *"THE APPROVER IS AN OWNER OR AN ADMIN … the same pair of roles as the
    rate-change second approval"* — and this product's answer to that pair is
    `SYSTEM_ADMIN`, exactly as `/discounts/{id}/versions/{vid}/approve` carries
    it. `getattr` and not `actor.role` because the actor may legitimately be a
    `_JobActor`, which has no such attribute at all.
    """
    return getattr(actor, "role", None) == SYSTEM_ADMIN


def _refuse_approver_role(actor: Any) -> None:
    """ONE refusal, raised by BOTH layers, so the two cannot drift apart.

    `DEF-545` put this refusal in the engine and `DEF-1108` moved it to the door;
    keeping it a single function is what stops a future edit fixing one and
    leaving the other, which is how the two bars in this rule were built and how
    `DEF-545` itself happened.
    """
    if _has_approver_role(actor):
        return
    raise errors.BizError(
        errors.BIZ_APPROVAL,
        br_ref="BR-MET-098",
        message_key="metering.import.approver_role",
    )

#: **THE TWO WRITE MODES — BR-MET-210, PO 2026-08-27 (CR-042).** Verbatim:
#: *"in all imports - we need 2 option on step 1 insert, insert & update;
#: replace option is not required"*. `insert` is FIRST because it is the only
#: mode that cannot alter a record already on file (hard-won law 3).
WRITE_MODES = ("insert", "upsert")

#: ⛔ **WITHDRAWN, AND THIS IS THE HALF OF CR-042 THAT NEEDED A JUDGMENT CALL.**
#:
#: On the READS rail `replace` did nothing `upsert` did not do, so it was
#: deleted outright (`write_modes.py`). **Here it did something no other mode
#: does**: BR-MET-099's *deactivate what the file no longer carries, skip
#: anything occupied, never delete* — a CONFIRMED PO ruling of 2026-08-21 with
#: its own worked figure (500 on file · 431 in the file · 69 not in it · 41
#: occupied → **28 deactivated**).
#:
#: So the OPTION is withdrawn and **the BEHAVIOUR is left standing, unreachable**
#: — refused at this module's two entry points by name, naming `OQ-580`, which
#: asks the PO how a utility retires a premise it no longer serves. Deleting the
#: branch would destroy a signed capability that one ruling would restore;
#: leaving the mode REACHABLE would leave a destructive write with no consequence
#: preview in front of it, which is the opposite of what BR-MET-099 requires.
#:
#: ⚠ This is the SAME shape already ratified for the assets targets on
#: 2026-08-22 (`_refuse_replace_for_assets`, OQ-326) — generalised from three
#: targets to all six, not invented.
WITHDRAWN_WRITE_MODES = ("replace",)

#: Named once so the raise sites and the catalogue sentence cannot drift apart.
#: ⚠ The key's NAME still says `unruled` because it was minted for OQ-326 and a
#: key id is internal and never shown (CR-016); its SENTENCE is rewritten in all
#: eleven catalogues to say `withdrawn`. Renaming it would churn eleven files
#: and two gate baselines to change a string no user reads.
WITHDRAWN_MODE_KEY = "metering.import.replace_unruled"

#: `BR-MET-099`'s own words: rollback *"reverses what a run created and skips
#: units with an active account"* — the SAME shape as replace, deliberately,
#: so a utility learns one sentence instead of two. r10 draws 30 days.
ROLLBACK_DAYS = 30

#: ⛔ **OQ-352 — the LEDGER half of an accounts rollback is UNRULED.** The load
#: posts BALANCED OPENING JOURNAL ENTRIES through the ledger posting service
#: (BR-CUS-049; ❄️ GT-16 — DR AR 267.30 / CR opening-balance clearing 267.30 on
#: A-12103). Hard rule 4 forbids UPDATE or DELETE on a journal entry, so a
#: rollback that closes the account and deletes its four opening buckets leaves
#: the books asserting $267.30 of receivables against an account that no longer
#: trades, with the sub-ledger detail behind that figure gone — and BR-LED-007's
#: tie-out (AR GL = Σ account balances) stops holding.
#:
#: **No signed document says what the mirror is or what DATE it takes.**
#: BR-CUS-049 reads *"immutable; corrections via J6 only"* and J6 is the BILL
#: correction journey (credit note → rebill → re-allocation), which has nothing
#: to say about un-migrating a cutover batch; B18 §5.9.4 rules only the BILLED
#: check and calls the 30-day window a courtesy. Posting the mirror at the
#: cutover date restates a period a bookkeeper may have closed; posting it on
#: the day of the rollback leaves the same $267.30 standing across every month
#: in between. Those are different books, and the prime directive forbids
#: choosing between them here.
#:
#: So the branch REFUSES BY NAME, and refuses BEFORE it touches anything: the
#: run stays `loaded` and its rollback point stays `available`, so the one
#: rollback point the run has is not spent on a question we cannot answer.
#: A run carrying NO opening position rolls back in full — nothing was posted.
OQ_ROLLBACK_OPENING = "OQ-352"

#: Named so the catalogue sentence and the raise site cannot drift apart, and so
#: a test can assert the key RESOLVES (an unresolved key renders as silence).
ROLLBACK_OPENING_UNRULED_KEY = "metering.import.rollback_opening_unruled"

#: Reserved keys `mapped` carries that are NOT columns of the target row.
_NOT_A_COLUMN = (
    PARSE_PROBLEMS,
    # `BR-MET-1032` — the staged identity vault. A reserved key inside `mapped`
    # exactly as `PARSE_PROBLEMS` is, and stripped here for exactly the same
    # reason: `Premises(**record)` with it in raises on a field that does not
    # exist.
    import_identity.VAULT,
    # CR-047 — the load result this row recorded. A reserved key, like
    # `PARSE_PROBLEMS` beside it, and stripped here for the same reason:
    # building a model from `mapped` with it in would raise on a field that
    # does not exist.
    LOAD_RESULT,
    "premises_ref",
    "rate_plan_ref",
    "area_name",
    "owner_ref",
    # ⛔ **CR-058 W3 — THE SIX VIRTUAL OWNER COLUMNS, AND THIS LINE IS WHAT
    # KEEPS THEM OFF THE MODEL.** None of them is a column of `premises`;
    # `Premises(**record)` with any of them in raises on a field that does not
    # exist, which is the same reason `PARSE_PROBLEMS` is in this tuple.
    # ⚠ Spread from ONE declaration rather than typed again here: a seventh
    # owner column added above and forgotten below would be a 500 on every row
    # of somebody's migration.
    *PREMISES_OWNER_COLUMN_NAMES,
    # The lookup branch writes `<target>_raw` beside the resolved code, and the
    # raw text is the operator's own cell — kept on the run row for the receipt
    # and never written to the object, exactly as `premises_type_raw` is.
    #
    # ⛔ **DERIVED 2026-09-19, AND IT WAS HAND-TYPED AS `"owner_account_type_raw"`
    # UNTIL THE SECOND LOOKUP COLUMN ARRIVED.** The note four lines up already
    # warned about exactly this — *"a seventh owner column added above and
    # forgotten below would be a 500 on every row of somebody's migration"* —
    # and then spread only the NAMES from one declaration while leaving the
    # `_raw` half as a single literal. Adding `owner_category` (PO ruling
    # 2026-09-19) produced precisely the predicted failure, on every row that
    # stated a category:
    #
    #     TypeError: Premises() got unexpected keyword arguments:
    #                'owner_category_raw'
    #
    # ⚠ **A WARNING THAT NAMES A FAILURE MODE IS NOT A GUARD AGAINST IT**
    # (hard-won law 1). The comment was right, it was read, and the mechanism it
    # described still fired — because only half the list was derived. So the
    # other half is derived too: any owner column of kind `KIND_LOOKUP` gets its
    # `_raw` twin here, and a third one cannot repeat this.
    *(
        f"{entry['target']}_raw"
        for entry in PREMISES_OWNER_COLUMNS
        if entry["kind"] == KIND_LOOKUP
    ),
)


def _loadable_rows(run: models.ImportRun) -> list[models.ImportRunRow]:
    """Rows stage 3 did not reject. ⚠ **FLAGGED ROWS LOAD** — that is the whole
    of `BR-MET-100`: a warning is a thing to look at, not a thing that stops."""
    return list(
        models.ImportRunRow.objects.filter(tenant_id=run.tenant_id, run=run)
        .exclude(outcome__in=("duplicate", "skipped", "rejected"))
        .order_by("row_no")
    )


def _record_from(mapped: dict[str, Any], target: str) -> dict[str, Any]:
    """The row as columns of `target`, with the carried references stripped.

    ⚠ `PARSE_PROBLEMS` MUST NOT REACH A MODEL — it is a reserved key inside
    `mapped` (stage 2 carries a parse problem rather than coercing the value),
    and building a `Premises(**mapped)` with it in would raise on a field that
    does not exist. Stated in stage 2's own docstring as *"stage 4 must strip it
    before it builds a premises"*; this is that strip.
    """
    record = {k: v for k, v in (mapped or {}).items() if k not in _NOT_A_COLUMN}
    if target == TARGET_PREMISES:
        # `premises_type` carries a resolved CODE (or None); the column holds a
        # code, so it travels as-is. `*_raw` is the operator's own text, kept on
        # the run row for the receipt and never written to the object.
        record.pop("premises_type_raw", None)
    else:
        record.pop("unit_type_raw", None)
    return record


def _existing_index(run: models.ImportRun) -> dict[str, Any]:
    """What is already on file, keyed the way a file references it.

    ⛔ **TWO KEY SPACES PER TARGET SINCE 2026-08-27 (CR-046 C2/C3), AND THEY
    ARE NAMESPACED SO THEY CANNOT COLLIDE.** Under the PO ruling the identifier
    is ISSUED by the tenant's series and never read off a file, so the FIRST
    migration's file carries no SMARTBillHub number at all — and a corrected
    re-run of that same file would match nothing, read every row as new, and
    duplicate the entire estate. The utility's own `external_ref` is the only
    identifier such a file has, and CR-046 C5 makes it unique per tenant, so it
    is a lawful match key. `ext:<lowered ref>` keeps it disjoint from our own
    numbers exactly as `assets.selectors.asset_import_index` does — a legacy
    string reading `P-00001` must never silently address our own `P-00001`.

    ⚠ **THE UNITS TARGET HAS A THIRD KEY, AND IT IS THE IDENTITY** — see
    `_key_of` and `Unit.Meta.constraints` for why `(premises, label)` is the
    identity and `unit_no` is not.
    """
    if run.target == TARGET_ACCOUNTS:
        # ⚠ **THROUGH THE SEAM, AND IT IS THE SAME DICT THE LOADER USES.**
        # `accounts` is customers' table (B1/B2 §2). Before CR-046 C4 this
        # function had no accounts branch at all and the target fell through to
        # the UNITS index below — which matched nothing, so the rehearsal
        # reported every row as a create, which is exactly what the loader then
        # did. The two agreed by both being wrong; now they agree by reading
        # one index (`DEF-544`).
        return dict(seams.accounts_import_index())
    if run.target == TARGET_PREMISES:
        index: dict[str, Any] = {}
        for row in models.Premises.objects.filter(
            tenant_id=run.tenant_id, deleted_at__isnull=True
        ):
            if row.premise_no:
                index[str(row.premise_no).strip().lower()] = row
            if row.external_ref:
                index[f"ext:{str(row.external_ref).strip().lower()}"] = row
        return index
    rows = models.Unit.objects.filter(
        tenant_id=run.tenant_id, deleted_at__isnull=True
    ).select_related("premises")
    index = {}
    for row in rows:
        # The IDENTITY key first, so a quoted number or reference can only ever
        # ADD a way to address a row that is already addressable.
        index[
            f"{str(getattr(row.premises, 'premise_no', '') or '').strip().lower()}|"
            f"{str(row.label or '').strip().lower()}"
        ] = row
        if row.unit_no:
            index[f"no:{str(row.unit_no).strip().lower()}"] = row
        if row.external_ref:
            index[f"ext:{str(row.external_ref).strip().lower()}"] = row
    return index


def _key_of(run: models.ImportRun, mapped: dict[str, Any]) -> str | None:
    """Which record on file this row is ABOUT, or `None` for a new one.

    ⛔ **THE ORDER IS THE RULE ON EVERY TARGET (CR-046):** our own number
    first, because an operator quoting a number WE issued is naming a specific
    record and that is the strongest statement available; the utility's own
    `external_ref` second, because it is the only identifier a first
    migration's corrected re-run carries.
    """
    if run.target == TARGET_PREMISES:
        value = mapped.get("premise_no")
        if value:
            return str(value).strip().lower()
        legacy = mapped.get("external_ref")
        return f"ext:{str(legacy).strip().lower()}" if legacy else None
    if run.target == TARGET_ACCOUNTS:
        # ⚠ CR-046 C4 — the accounts target had NO key at all before this: every
        # row created, unconditionally, and a corrected re-run of a 1,213-row
        # migration met 1,213 BR-CUS-017 refusals at the unit seat.
        value = mapped.get("account_no")
        if value:
            return str(value).strip().lower()
        legacy = mapped.get("external_ref")
        return f"ext:{str(legacy).strip().lower()}" if legacy else None
    if run.target == TARGET_PARTS:
        # ⚠ **ONE KEY, AND IT IS THE FILE'S OWN.** A part number is the
        # UTILITY's — there is no `part` number series to allocate from — and
        # `uq_parts_tenant_part_no_ci` makes it unique case-insensitively, which
        # is what lets it identify a row at all. There is no `external_ref`
        # column on `parts` and none is invented: a target with one identifier
        # has one key, and a second key space that matched nothing would be a
        # dead branch reading as a feature.
        value = mapped.get("part_no")
        return str(value).strip().lower() if value else None
    if run.target == TARGET_PAYMENTS:
        # ⚠ **A PAYMENT HAS NO KEY, AND `None` IS THE ANSWER RATHER THAN A
        # MISSING BRANCH.** Every other target asks *"which record on file is
        # this row about?"* because a re-run may legitimately update one. A
        # payment may never be updated (CLAUDE.md hard rule 4), so there is
        # nothing to match and every row is new by law. Returning `None`
        # explicitly — with this comment — is what stops a later reader adding
        # a key here to make the target look like its neighbours.
        #
        # ⚠ **THE FILE's DOUBLE-IMPORT IS GUARDED, JUST NOT HERE:**
        # `uq_import_runs_idempotency` refuses a second COMMIT of the same
        # bytes to the same target, and `create_payment_from_import` carries a
        # per-ROW idempotency key of `<run>:<row>`. Two guards, two different
        # facts (`DEF-058`).
        return None
    if run.target in ASSETS_TARGETS:
        # ⛔ **TWO KEYS SINCE 2026-08-27, IN THIS ORDER, AND THE ORDER IS THE
        # RULE.** This used to read *"the asset NUMBER is the file's identity …
        # blank = None = the series will allocate one"*. Under the PO ruling a
        # blank `asset_no` is now the NORMAL case rather than the fallback one,
        # so number-only matching would make every row of a corrected re-run
        # read as new — and `AST.UNIT_SERVICE_FREE` would reject the lot with
        # *"this unit already has an active water meter"*, which is the exact
        # pile of rejects the ruling's addendum warns a lane about.
        #
        # 1. `asset_no` FIRST — an operator who quotes OUR number is naming a
        #    specific record, and that is the strongest statement available.
        # 2. `external_ref` SECOND (BR-AST-049) — the only identifier a first
        #    migration's corrected file carries. Lawful because the column is
        #    `UNIQUE (tenant, lower(external_ref))`; `serial_no` could NOT do
        #    this job, because BR-AST-033 makes a duplicate serial
        #    warn-but-allow and a non-unique column cannot identify a row.
        #
        # The `ext:` prefix keeps the two key spaces DISJOINT — the index
        # published by `assets.selectors.asset_import_index` builds the same
        # shape — so a legacy string can never silently address one of our own
        # numbers that happens to read the same.
        value = mapped.get("asset_no")
        if value:
            return str(value).strip().lower()
        legacy = mapped.get("external_ref")
        return f"ext:{str(legacy).strip().lower()}" if legacy else None
    # ── the UNITS target, and CR-046 C3's identity question answered ────────
    #
    # ⛔ **A UNIT'S IDENTITY IS ITS LABEL WITHIN ITS PREMISES, NOT ITS NUMBER,
    # AND THE DATABASE IS WHAT SAYS SO.** `uq_units_tenant_premises_label` is
    # over two NOT NULL columns, so every unit that exists carries that key;
    # `uq_units_tenant_unit_no` is over a NULLABLE column, so N units may carry
    # no number at all. A column that can be absent cannot be an identity.
    #
    # So the composite is the FALLBACK — the one always available — and the two
    # quoted keys above it are stronger STATEMENTS when an operator makes them.
    # Both are namespaced (`no:` / `ext:`) so a unit number can never be read as
    # a `premise|label` pair or the reverse.
    value = mapped.get("unit_no")
    if value:
        return f"no:{str(value).strip().lower()}"
    legacy = mapped.get("external_ref")
    if legacy:
        return f"ext:{str(legacy).strip().lower()}"
    premise = str(mapped.get("premises_ref") or "").strip().lower()
    label = str(mapped.get("label") or "").strip().lower()
    return f"{premise}|{label}" if label else None


def _refuse_withdrawn_mode(write_mode: str, *, target: str | None = None) -> None:
    """⛔ **CR-042 — A WITHDRAWN WRITE MODE IS REFUSED BY NAME, ON EVERY TARGET.**

    **This generalises `_refuse_replace_for_assets`, which lived here from
    2026-08-22 and refused `replace` for the three assets targets under OQ-326.**
    That refusal was right and its shape is right; CR-042 withdrew the mode for
    the other three targets too, so the guard widens and OQ-326 becomes moot
    (the control it asked about no longer exists).

    ⚠ **IT REFUSES RATHER THAN COERCING, AND THAT IS THE WHOLE POINT.** Mapping
    `replace` onto `upsert` would be silently telling a caller *"your 28
    premises were retired"* when nothing was retired — a wrong belief about a
    destructive operation, which is worse than an error. The prime directive
    says stub the gap with the OQ id ON IT; this is that stub, as a catalogue
    refusal rather than a 500.

    Called from BOTH entry points independently. That is deliberate duplication:
    `dry_run` and `load` have always validated the mode separately, and a lane
    fixing one would otherwise leave the WRITING path open behind a rehearsal
    that refuses.
    """
    if write_mode in WITHDRAWN_WRITE_MODES:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="OQ-580",
            message_key=WITHDRAWN_MODE_KEY,
            params={"oq": "OQ-580", "target": target or "", "mode": write_mode},
        )
    _refuse_payments_write_mode(write_mode, target=target)


def _refuse_payments_write_mode(write_mode: str, *, target: str | None = None) -> None:
    """⛔ **THE PAYMENTS TARGET TAKES *Insert new only* AND NOTHING ELSE.**

    CLAUDE.md hard rule 4: **no UPDATE on a payment.** *Insert & update* would
    overwrite money already on file, so it is refused BY NAME rather than
    quietly mapped onto `insert` — telling a caller *"your 400 payments were
    updated"* when nothing was updated is a wrong belief about money, which is
    worse than an error (`_refuse_withdrawn_mode`'s own reasoning, and the
    reason this lives beside it rather than inside a loader).

    ⚠ **Raised from `_refuse_withdrawn_mode`, which BOTH entry points already
    call.** `dry_run` and `load` validate the mode separately and always have;
    hanging this off the one helper they share is what stops a lane fixing the
    rehearsal and leaving the WRITING path open behind it.
    """
    if target == TARGET_PAYMENTS and write_mode == "upsert":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="B8 hard rule 4",
            message_key="metering.import.payments_insert_only",
            params={"target": target, "mode": write_mode},
        )


def _insert_mode_on_file_sentences(
    target: str, mapped: dict[str, Any], existing: dict[str, Any]
) -> tuple[str, str]:
    """⛔ **WHY A ROW THAT NAMES A METER ALREADY ON FILE IS *REJECTED* IN
    *Insert new only* — the PO decided this outright (2026-08-27).**

    PO verbatim: *"Does this row name a meter already on file? if yes - ( in
    case of insert - reject it | in case of Insert & Update = update the
    details), if no ( generate new meter number using settings -> numbers for
    meter), assing this unquie number and upload the record"*.

    ⚠ **THIS SUPERSEDES A JUDGMENT THIS LANE HAD ALREADY MADE.** The earlier
    reading was that such a row is *skipped* — reported and left unchanged.
    The PO's word is *reject*, and the difference is what the operator does
    next: a skip reads as *"nothing needed doing"*, a reject reads as *"this
    row did not load"*. Only one of those is true.

    **THE SENTENCE STILL FORKS ON WHICH KEY MATCHED, AND THE OUTCOME DOES
    NOT.** Both are rejects. But a match on a QUOTED NUMBER means the operator
    put one of our numbers in a column whose only remaining job is to name a
    row to update — so the sentence has to say where a number actually comes
    from, or their next move is to invent a different one. A match on
    `external_ref` means they supplied their own legacy id exactly as the
    template asks, and the file simply overlaps a load they already ran; that
    wants the plain sentence and the pointer to the other mode.

    ⚠ **BOTH ARE ROW OUTCOMES, NEVER A REFUSAL OF THE RUN.** 1,846 good rows
    beside one bad one must still load; a run-level refusal would make the
    operator's fix *"cut the file again"* instead of *"clear one cell"*.

    ⚠ **THE SETTING IS NAMED BY ITS CLICK PATH, NOT BY A RULE ID** — *Settings
    › Numbers › Meter*. Standing PO instruction: things reach a person in plain
    English, never as an ID to go and look up.
    """
    # ⛔ **CR-046 C2/C3/C4 — THE SAME TWO SENTENCES ON ALL FOUR TARGETS.**
    # The PO widened the ruling from meters to every upload, and the operator's
    # question is identical on each: *why did this row not load, and where does
    # a number actually come from?* Only the noun and the number's field name
    # differ, so those are looked up rather than branched on.
    if target not in ASSET_NOUN_BY_TARGET:
        return _identifier_on_file_sentences(target, mapped, existing)
    noun = ASSET_NOUN_BY_TARGET.get(target, "asset")
    if str(mapped.get("asset_no") or "").strip():
        return (
            f"{existing['asset_no']} is a {noun} already on file, and "
            f"Insert new only writes new {noun}s.",
            f"{noun.capitalize()} numbers are issued from Settings › Numbering › "
            f"{noun.capitalize()} — leave this column blank and one is "
            f"allocated when the row is written. Fill it in only to UPDATE a "
            f"{noun} already on file, and then choose Insert & update.",
        )
    return (
        f"{existing['asset_no']} already carries this external reference, and "
        "Insert new only writes new records.",
        "Use Insert & update to update its spec fields, or remove this row "
        "from the file.",
    )


#: CR-046 — the noun a sentence about one of these rows uses, and the column
#: that holds the record's own number. Kept beside `ASSET_NOUN_BY_TARGET`
#: rather than merged into it: the assets targets share ONE number field across
#: three nouns, and these three each have their own.
IDENTIFIER_BY_TARGET: dict[str, tuple[str, str, str]] = {
    # target → (noun, the record's number field, the Settings › Numbering entry)
    TARGET_PREMISES: ("premises", "premise_no", "Premises"),
    TARGET_UNITS: ("unit", "unit_no", "Unit"),
    TARGET_ACCOUNTS: ("account", "account_no", "Account"),
}


def _identifier_on_file_sentences(
    target: str, mapped: dict[str, Any], existing: Any
) -> tuple[str, str]:
    """The insert-mode reject, for the three targets whose `existing` entry is a
    MODEL ROW rather than the assets index's dict.

    ⚠ **THE SENTENCE FORKS ON WHICH KEY MATCHED, AND THE OUTCOME DOES NOT** —
    `_insert_mode_on_file_sentences`' own law, restated per target rather than
    re-decided. A match on a QUOTED NUMBER means the operator put one of our
    numbers in a column whose only remaining job is to name a row to UPDATE, so
    the sentence has to say where a number actually comes from or their next
    move is to invent a different one. A match on `external_ref` — or, for a
    unit, on its label within its premises — means the file simply overlaps a
    load they already ran, and that wants the plain sentence and the pointer to
    the other mode.
    """
    noun, number_field, setting = IDENTIFIER_BY_TARGET.get(
        target, ("record", "", "")
    )
    # A model row on premises/units, a dict on accounts (the customers index).
    if isinstance(existing, dict):
        known = str(existing.get(number_field) or "").strip()
    else:
        known = str(getattr(existing, number_field, "") or "").strip()
    named = known or f"this {noun}"
    if number_field and str(mapped.get(number_field) or "").strip():
        return (
            f"{named} is a {noun} already on file, and Insert new only writes "
            f"new {noun}s.",
            f"{noun.capitalize()} numbers are issued from Settings › Numbering › "
            f"{setting} — leave this column blank and one is allocated when the "
            f"row is written. Fill it in only to UPDATE a {noun} already on "
            "file, and then choose Insert & update.",
        )
    return (
        f"{named} already matches a {noun} on file, and Insert new only writes "
        "new records.",
        "Use Insert & update to update its details, or remove this row from "
        "the file.",
    )


def _issued_numbers_block(
    run: models.ImportRun, rows: list[Any], creating: int
) -> dict[str, Any]:
    """**THE NUMBERS THE COMMIT WILL ISSUE, STATED IN THE REHEARSAL** — the
    last clause of the 2026-08-27 ruling: *"the dry run states the numbers it
    will issue rather than echoing the file's."*

    A rehearsal that printed *"Will create 20"* and nothing else left the
    operator with no way to know what those twenty meters would be CALLED, on
    the very change that took the naming away from them.

    ⚠ **PER ROW, IN ROW ORDER, BECAUSE THE PREFIX IS PER TYPE AND THE SEQUENCE
    IS SHARED** (BR-AST-026). A devices file of a backflow then a PV inverter
    takes `BF-00042` and `PV-00043` off one counter, so a single prefix for the
    run would print numbers that are not the ones issued.

    ⚠ **IT IS A PEEK AND IT ALLOCATES NOTHING** — `assets.selectors.
    asset_no_preview_run` walks BE-06's preview contract by an offset. A
    rehearsal is allowed to be run twice, and burning a series number per
    rehearsal is exactly the defect `asset_no_preview` was written to avoid.

    Returns `{}` when the tenant has no `asset` series row: the screen then
    says the numbering is unset rather than printing an invented range, and
    the commit's own refusal (`assets.asset_no_required_no_series`) is the
    same fact one stage later.
    """
    if creating <= 0 or not rows:
        return {}
    fixed = ASSET_TYPE_BY_TARGET.get(run.target)
    # ⚠ ONLY THE ROWS THAT WILL BE CREATED, and in the order the commit walks
    # them — an updating row consumes no number, so counting one for it would
    # shift every number after it by one and print a range nobody gets.
    type_codes = [fixed or str((row.mapped or {}).get("type") or "") for row in rows]
    preview = seams.assets_number_preview(type_codes)
    return dict(preview) if preview else {}


def _dry_run_assets(run: models.ImportRun, write_mode: str) -> dict[str, Any]:
    """The assets targets' rehearsal — same promise, same shape, the assets
    vocabulary: what will be created, what insert-and-update will touch, how
    many rows tag a unit (BR-AST-045) and how many go to inventory."""
    _refuse_withdrawn_mode(write_mode, target=run.target)
    rows = _loadable_rows(run)
    index = seams.assets_import_index()
    unit_index = _unit_reference_index()
    premises_units = _premises_units_index()
    creating = updating = tagged = to_inventory = 0
    #: The rows that will take a number out of the tenant's series, in the
    #: order the commit walks them (PO ruling 2026-08-27).
    creating_rows: list[Any] = []
    for row in rows:
        mapped = row.mapped or {}
        key = _key_of(run, mapped)
        if key is not None and key in index:
            updating += 1
        else:
            creating += 1
            creating_rows.append(row)
            if _unit_seat_for(run.target, mapped, unit_index, premises_units) is not None:
                tagged += 1
            else:
                to_inventory += 1
    figures: dict[str, Any] = {
        "will_create": creating,
        # ⛔ **`DEF-1079` — *"WILL CREATE 20"* IS NOT AN HONEST NUMBER ON ITS
        # OWN.** The Product Owner rehearsed twenty meters, read *"Will create
        # 20 · Existing records updated 0 · Rows rejected 0"*, and nothing on
        # the strip said that all twenty were going into INVENTORY — twenty
        # meters that cannot take a reading or be billed until somebody
        # assigns them. The split was already computed two lines up for the
        # receipt; the rehearsal simply did not publish it.
        #
        # ⚠ **A SUBSET, NOT A THIRD FIGURE.** These two always sum to
        # `will_create`, so a screen may print them as *"20 — all into
        # inventory"* without arithmetic of its own; `will_update` rows are
        # NOT counted here because an update never moves an asset (BR-AST-034:
        # a re-imported row never restates the seat).
        "will_create_in_service": tagged,
        "will_create_to_inventory": to_inventory,
        "will_update": updating if write_mode != "insert" else 0,
        # ⛔ **PO ruling 2026-08-27 — *"in case of insert - reject it"*.** This
        # read `skipped_existing` and the rehearsal told the operator those
        # rows would be *left unchanged*; they do not load at all. The old key
        # is served as 0 rather than dropped so one rehearsal panel still
        # renders every target.
        "skipped_existing": 0,
        "will_reject_existing": updating if write_mode == "insert" else 0,
        "rejected": int((run.counts or {}).get("errors") or 0),
        "target": run.target,
        "unplanned_units": 0,
        "unplanned_plans": [],
        "unit_tagged": tagged,
        "to_inventory": to_inventory,
    }
    # ⛔ **PO ruling 2026-08-27 — *"the dry run states the numbers it will issue
    # rather than echoing the file's."*** Absent (rather than zeroed) when the
    # tenant has no `asset` series row, so the screen can say *"your numbering
    # is not set up"* instead of printing a range nobody will get. On `insert`
    # the numbers are what the commit issues; on `upsert` the matched rows
    # consume none, which is why the block is computed from `creating_rows`.
    issued = _issued_numbers_block(run, creating_rows, creating)
    if issued:
        figures["will_issue"] = issued
    # ⛔ **CR-046 D2 — WHAT STATE EACH CREATED ROW LANDS IN, NAMED.** OQ-840's
    # PO question was literally *"what status you will ahve on this meters"*,
    # and `will_create_in_service` / `will_create_to_inventory` answered it in
    # counts without ever saying what the two states are CALLED. The counts are
    # NOT restated here — they stay the one derivation (`tagged` /
    # `to_inventory`) and this block names them, so a screen prints
    # *"3 → Inventory / Spare"* off one source rather than two.
    stages = seams.assets_outcome_stages()
    if stages:
        figures["will_create_outcomes"] = [
            {**stages[code], "rows": rows}
            for code, rows in (("active", tagged), ("inventory", to_inventory))
            if code in stages
        ]
    figures["approval"] = _approval_block(run, figures["rejected"])
    return figures


def _unit_seat_for(
    target: str,
    mapped: dict[str, Any],
    unit_index: dict[str, str],
    premises_units: dict[str, tuple[str, ...]],
) -> str | None:
    """WHERE a created asset sits, per BR-AST-045: the named unit; for a
    device, the named premises' ONE unit; else None → inventory. Both indexes
    are read ONCE by the caller (DEF-324) and are the SAME ones stage 3 judged
    with (DEF-544)."""
    unit_id = import_rules.resolve_unit_ref(mapped.get("unit_ref"), unit_index)
    if unit_id is not None:
        return unit_id
    if target == TARGET_ASSETS_DEVICES:
        premises_ref = str(mapped.get("premises_ref") or "").strip().lower()
        if premises_ref:
            units = premises_units.get(premises_ref) or ()
            if len(units) == 1:
                return units[0]
    return None


def dry_run(actor: Any, run_id: Any, write_mode: str) -> dict[str, Any]:
    """What stage 4 will write, computed and WRITTEN NOWHERE.

    ⚠ **`BR-MET-099` REQUIRES THREE NUMBERS IN WORDS BEFORE A COMMIT**, and
    they are computed here rather than on the screen so that the sentence the
    operator reads and the rows the commit touches come from one predicate —
    the same reason `DEF-380`'s matched-premise count is computed by the
    engine's own function. A dry run that disagreed with its commit would be
    worse than none.
    """
    # ⚠ **THE WITHDRAWN MODE IS REFUSED FIRST, BEFORE THE RUN IS EVEN LOADED
    # (CR-042).** A refusal that depended on the run's state would be a refusal
    # an operator could get past by retrying at a different stage, and this one
    # guards a destructive write.
    _refuse_withdrawn_mode(write_mode)
    if write_mode not in WRITE_MODES:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.kind_unknown",
            allowed=list(WRITE_MODES),
        )
    run = _run(run_id)
    if run.status not in ("validated", "loaded"):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-090",
            message_key="metering.import.not_validated",
        )
    if run.target in ASSETS_TARGETS:
        # The assets rehearsal — same predicate discipline, its own index and
        # its own OQ-326 replace refusal (the dict-dispatch shape, not a
        # second pipeline: stages 1–3 are byte-identical for every target).
        return _dry_run_assets(run, write_mode)

    rows = _loadable_rows(run)
    existing = _existing_index(run)
    plan_index = seams.assignable_plan_index() if run.target == TARGET_UNITS else {}
    seen: set[str] = set()
    creating = updating = 0
    unplanned = 0
    unplanned_plans: dict[str, dict[str, Any]] = {}
    for row in rows:
        mapped = row.mapped or {}
        key = _key_of(run, mapped)
        if key is not None:
            seen.add(key)
        if key is not None and key in existing:
            updating += 1
        else:
            creating += 1
        # BR-MET-100: counted here because the receipt must state it.
        # ⚠ **RESOLVED THE WAY THE LOAD RESOLVES (`DEF-544`)** — this used to
        # test `mapped["rate_plan_id"]`, a key stage 2 never writes (resolution
        # is a load-time act), so EVERY plan-naming row counted as unplanned
        # and r10's file would have rehearsed "246" against a receipt of "12".
        # It is `import_rules.resolve_plan_ref` for BOTH halves now (DEF-771),
        # so the rehearsal, the stage-3 rule and the commit cannot disagree
        # about what a `Plan` cell means.
        if run.target == TARGET_UNITS:
            resolved = import_rules.resolve_plan_ref(mapped.get("rate_plan_ref"), plan_index)
            if resolved is not None and resolved["plan_id"] is None:
                unplanned += 1
                _tally_unplanned_plan(unplanned_plans, resolved)

    figures: dict[str, Any] = {
        "will_create": creating,
        "will_update": updating if write_mode != "insert" else 0,
        # ⛔ **CR-046 C2/C3/C4 — *"in case of insert - reject it"*.** The
        # rehearsal used to say nothing at all about these rows on the three
        # non-assets targets: `will_update` went to 0 under `insert` and the
        # operator was left to infer that the rows had vanished. `skipped_
        # existing` is served as 0 rather than dropped so ONE rehearsal panel
        # still renders every target.
        "skipped_existing": 0,
        "will_reject_existing": updating if write_mode == "insert" else 0,
        "rejected": int((run.counts or {}).get("errors") or 0),
        "target": run.target,
        "unplanned_units": unplanned,
        "unplanned_plans": _unplanned_plan_list(unplanned_plans),
    }
    # ⛔ **THE NUMBERS THE COMMIT WILL ISSUE, PROJECTED AND NOT ALLOCATED**
    # (CR-046 D1, the ruling's own last clause: *"the dry run states the
    # numbers it will issue rather than echoing the file's"*).
    #
    # ⚠ **A PEEK. `core.numbering.preview` VALIDATES AND RENDERS AND ALLOCATES
    # NOTHING** — a rehearsal may lawfully be run twice, and N allocations per
    # rehearsal would burn numbers on rows that never load. It is also why the
    # projection is computed from `creating` alone: a matched row consumes no
    # number, so counting one for it would shift every number after it by one.
    #
    # **Absent, not zeroed, when this tenant has no series row for the target**
    # — the screen then says *"your numbering is not set up"* rather than
    # printing an invented range.
    issued = _issued_numbers_preview(run.target, creating)
    if issued:
        figures["will_issue"] = issued

    # ── BR-MET-099 — the three numbers, and only for `replace` ──────────────
    # ⛔ **KEPT AND UNREACHABLE — CR-042. DO NOT DELETE THIS BRANCH.**
    # `replace` is refused at both entry points (`_refuse_withdrawn_mode`), so
    # nothing can arrive here with it. That makes this dead code and it is dead
    # ON PURPOSE: it implements BR-MET-099, a CONFIRMED PO ruling of 2026-08-21
    # with its own worked figure, and **OQ-580** asks whether the behaviour
    # should come back under a different door. A lane that tidies it away is
    # destroying a signed capability that one ruling would restore.
    # `test_cr042__br_met_099s_behaviour_is_kept_not_deleted` fails if you do.
    if write_mode == "replace":
        untouched = [row for key, row in existing.items() if key not in seen]
        occupied = [row for row in untouched if _is_occupied(run, row)]
        figures["not_in_file"] = len(untouched)
        figures["skipped_occupied"] = len(occupied)
        figures["will_deactivate"] = len(untouched) - len(occupied)

    # ── BR-MET-098 — the two bars, whichever comes first ────────────────────
    figures["approval"] = _approval_block(run, figures["rejected"])
    return figures


def _tally_unplanned_plan(tally: dict[str, dict[str, Any]], resolved: dict[str, Any]) -> None:
    """One unresolved `Plan` cell, folded into the run's per-PLAN summary.

    ⚠ **`DEF-771` CLAUSE 3 — 9,881 FLAGGED ROWS IS NOT A REVIEW ANYBODY CAN
    PERFORM.** `BR-MET-100` is right for one typo and stays exactly as the PO
    ruled it: the row loads, unplanned and flagged. What was missing is a
    receipt a person can act on — HOW MANY rows, WHICH plan they all named, and
    WHAT TO DO — and that is one line per distinct token, not one per row.
    """
    entry = tally.setdefault(
        resolved["asked_for"].strip().lower(),
        {
            "asked_for": resolved["asked_for"],
            "rows": 0,
            "reason": resolved["outcome"],
            "detail": plan_problem_of(resolved)[0],
            "fix_hint": plan_problem_of(resolved)[1],
        },
    )
    entry["rows"] += 1


def plan_problem_of(resolved: dict[str, Any]) -> tuple[str, str]:
    """The rule's own two sentences, reused verbatim by the receipt — one
    source, so the flag on the row and the line on the receipt can never say
    two different things about one plan (hard-won law 5's shape)."""
    return import_rules.plan_ref_problem(resolved)


def _unplanned_plan_list(tally: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Worst first — the plan that cost the most rows is the one to fix."""
    return sorted(tally.values(), key=lambda entry: (-entry["rows"], entry["asked_for"]))


# ═══════════════════════════════════════════════════════════════════════════
# CR-055 · TASK 2 — TWO KINDS OF OWNERLESS, TOLD APART AT THE MOMENT OF THE
# WRITE
# ═══════════════════════════════════════════════════════════════════════════
#
# PO ruling 2026-08-31: an owner name matching no party exactly but resembling
# two or more of them LOADS THE PREMISES WITH NO OWNER, flagged, exactly as a
# blank Owner column already does. The row is no longer rejected.
#
# ⚠ **THE COST OF THAT RULING IS THE REASON THIS CODE EXISTS.** No owner means
# no master account, so the address has NOBODY TO CHARGE. It is a real premises
# — units, meters, readings — and it cannot be BILLED until somebody fills the
# owner in. The CR states the mitigation in one sentence: the receipt count is
# *"the only thing that stops this being a quiet way to lose revenue."*
#
# ⚠ **AND ONE COUNT IS NOT ENOUGH, WHICH IS TASK 2 RATHER THAN A REFINEMENT OF
# TASK 1.** A blank owner needs RESEARCH — somebody has to find out who owns
# the address. An ambiguous owner needs a DECISION between two named parties
# the file already knows. Merging them into one figure throws away the half an
# operator can act on today, from the screen, without leaving their desk.
OWNER_GAP_BLANK = "blank"
OWNER_GAP_AMBIGUOUS = "ambiguous"


def _owner_gap_kind(
    written_row: Any,
    mapped: dict[str, Any],
    owner_near: dict[str, list[dict[str, Any]]],
) -> str | None:
    """Which kind of ownerless this written row is — or `None` for neither.

    THREE OUTCOMES AND THE THIRD ONE IS THE TRAP:

    ``OWNER_GAP_BLANK``
        Nothing named anybody: no typed `owner_id`, no `Owner` cell and no
        legacy free-text name. The PO's 2026-08-27 case.

    ``OWNER_GAP_AMBIGUOUS``
        No typed `owner_id`, and the `Owner` cell normalises onto a key two or
        more EXISTING owner records share. CR-055's case.

    ``None`` — **AND THIS IS THE ONE THAT MUST NOT BE COUNTED.**
        A row whose `Owner` cell names nobody on file at all is WAITING FOR
        MATCHING (BR-MET-402 clause 4), not ownerless-and-stuck: on a utility's
        FIRST upload every single row is in this state, so counting it would
        report a whole migration as un-billable on the day it landed. It is
        already flagged by `PRM.OWNER_NOT_ON_FILE` and already listed by
        `unmatched_premises_qs()`. A row that DID resolve is `None` too.

    ⚠ **IT READS `mapped["owner_ref"]` FOR THE NAME, NOT THE ROW's FREE-TEXT
    BOX, AND THE DIFFERENCE IS DEF-544.** `owner_ref` is the `Owner` cell stage
    3 judged; `owner_manager` may instead hold an explicit *Owner name
    (legacy)* column the operator supplied separately, which
    `_resolve_owner_ref` never overwrites. Classifying off the free-text box
    would let the receipt and the row's own sentence describe the same row
    differently.

    ⚠ **AND IT READS THE ROW AS WRITTEN FOR THE OWNER, NOT THE FILE's `record`
    — WHICH ONLY THE UPSERT PATH MAKES VISIBLE.** On an insert the two agree.
    On an update `record` carries no `owner_id` for an ambiguous name and the
    premises on file keeps the owner a person chose, so reading `record` would
    count an address that HAS somebody to charge.

    ⚠ **IT RESOLVES NOTHING.** `owner_near` is read to ANSWER A QUESTION about
    the row, never to pick a party — PO decision 3 stands and CR-055 did not
    reverse it.
    """
    from apps.metering.premises_owners import _normalise_owner_name

    if getattr(written_row, "owner_id", None):
        return None
    cell = str(mapped.get("owner_ref") or "").strip()
    if not cell:
        # No Owner cell. It is only BLANK if nothing else named anybody either
        # — an explicit legacy column is still a name for a person to work.
        held = str(getattr(written_row, "owner_manager", "") or "").strip()
        return None if held else OWNER_GAP_BLANK
    key = _normalise_owner_name(cell)
    if key and owner_near.get(key):
        return OWNER_GAP_AMBIGUOUS
    return None


def _tally_owner_ambiguity(
    tally: dict[str, dict[str, Any]],
    mapped: dict[str, Any],
    owner_near: dict[str, list[dict[str, Any]]],
) -> None:
    """One ambiguous `Owner` cell, folded into the run's per-NAME summary.

    ⚠ **THE CANDIDATE NAMES TRAVEL, AND CR-055 ASKS FOR THAT IN AS MANY
    WORDS** — *"carry the candidate names through, so the person settling it
    does not have to re-run the search."* A bare count would send an operator
    back to the matching screen to rediscover what this run already computed.

    ⚠ **NAMES, NEVER IDS (B14 rule 31).** `owner_near`'s entries carry an `id`
    and it is deliberately dropped here: no database id is ever the visible
    value of a field, and this list is built to be read on a receipt.

    One line per distinct spelling, `unplanned_plans`' shape and reason — 400
    rows carrying one misspelt landlord is ONE decision, not 400.
    """
    from apps.metering.premises_owners import _normalise_owner_name

    cell = str(mapped.get("owner_ref") or "").strip()
    key = _normalise_owner_name(cell)
    entry = tally.setdefault(
        key,
        {
            "asked_for": cell,
            "rows": 0,
            "candidates": sorted(
                str(item.get("name") or "") for item in (owner_near.get(key) or [])
            ),
        },
    )
    entry["rows"] += 1


def _owner_ambiguity_list(tally: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Worst first — the spelling that cost the most addresses is the one to
    settle, which is `_unplanned_plan_list`'s ordering and its reason."""
    return sorted(tally.values(), key=lambda entry: (-entry["rows"], entry["asked_for"]))


def _approval_block(run: models.ImportRun, rejected: int) -> dict[str, Any]:
    """BR-MET-098's two bars beside the run's own numbers — ONE predicate for
    every target's dry run, so the assets rehearsal cannot drift from the
    premises one.

    ⚠ STRICTLY GREATER (`DEF-547`): BR-MET-098's word is *"exceed"*, twice —
    a run at exactly 5.00% (1 of 20) passes without approval, matching the
    row bar, which was already strict (`> 10`, so 10 rejected passes and 11
    asks). A `>=` here made the two bars disagree about what "exceed" means.
    """
    checked = int((run.counts or {}).get("checked") or 0)
    over_pct = checked > 0 and (rejected * 100) > (APPROVAL_PCT * checked)
    return {
        "threshold_pct": APPROVAL_PCT,
        "threshold_rows": APPROVAL_ROWS,
        "rejected": rejected,
        "of_rows": checked,
        "required": bool(over_pct or rejected > APPROVAL_ROWS),
        "because": ("percent" if over_pct else ("rows" if rejected > APPROVAL_ROWS else None)),
    }


def _is_occupied(run: models.ImportRun, row: Any) -> bool:
    """`BR-MET-099`'s refusal, and `BR-MET-036`'s definition of occupied.

    ⚠ Occupancy is DERIVED from an active account and there is no column for it
    (`units` has none BY DESIGN). The seam answers `None` while customers owns
    no tables, which is TRUE rather than assumed — no account can exist, so
    nothing is occupied, so nothing is skipped and everything untouched is
    deactivated. That is the correct answer for a product in this state and it
    changes by itself the day accounts land.
    """
    if run.target == TARGET_UNITS:
        return seams.active_account_for_unit(row.pk) is not None
    return any(
        seams.active_account_for_unit(unit_id) is not None
        for unit_id in models.Unit.objects.filter(
            tenant_id=run.tenant_id, premises_id=row.pk, deleted_at__isnull=True
        ).values_list("id", flat=True)
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def load(actor: Any, run_id: Any, payload: Any) -> dict[str, Any]:
    """Stage 4 · LOAD — **the only stage in this workflow that writes.**

    ⚠ The lock needs a transaction and a request does not bring one
    (`DEF-529`), so the whole commit is one `atomic` block — which it would
    have to be anyway: a half-loaded file is the one outcome nobody can undo by
    hand.
    """
    # ⚠ **A COPY, AND THE STAMP IS STRIPPED FIRST (`DEF-1108`).**
    # `APPROVED_BY_KEY` is this function's own word that the approver-role check
    # below was run and passed. A caller-supplied one is thrown away here,
    # before anything reads it, so a service-layer caller who writes the key by
    # hand gains nothing and is refused on their role exactly as they are today.
    data = dict(payload) if isinstance(payload, dict) else {}
    data.pop(APPROVED_BY_KEY, None)
    write_mode = str(data.get("write_mode") or "insert").strip()
    # CR-042 — checked HERE as well as on the dry run, independently. The two
    # have always validated the mode separately; this is the WRITING path.
    _refuse_withdrawn_mode(write_mode)
    if write_mode not in WRITE_MODES:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.kind_unknown",
            allowed=list(WRITE_MODES),
        )
    # CR-026 — over the bar the commit goes to a worker. ⚠ **THE ALREADY-LOADED
    # RUN IS ANSWERED HERE, NOT DEFERRED**: hard rule 6 says a second commit of
    # the same run returns the same receipt, and a receipt delivered by a poll
    # nobody started would be that guarantee broken by a technicality. Same for
    # a run that never validated, and for BR-MET-098's approval refusal — all
    # three are decided by `_load_locked` on figures it computes in ~1.9s
    # (dry-run, measured), so the caller gets its refusal on the call it made.
    run = _run(run_id)
    if run.status == "validated":
        # `DEF-MET-9614` — asked at the door too, so a deferred commit is
        # refused on the call the clerk made rather than in a worker.
        _refuse_file_already_loaded(run)
    if _defers(run, "load") and run.status == "validated":
        # BR-MET-098 asked BEFORE deferring, so the refusal reaches the operator
        # on the call they made, with both bars and their own numbers. It is the
        # same predicate the load itself uses (`dry_run`), for the same reason
        # B15 §16 TC-16 gives: a rehearsal that disagrees with its commit is
        # worse than none.
        figures = dry_run(actor, run.id, write_mode)
        needs_approval = bool(figures["approval"]["required"])
        if not needs_approval or bool(data.get("approved")):
            if needs_approval:
                # ⚠ **THE APPROVER IS DECIDED HERE, AT THE DOOR, AND NEVER
                # AGAIN IN THE WORKER (`DEF-1108`, high).** This call still has
                # a REAL actor with a REAL role; the worker that finishes the
                # commit carries `_JobActor`, which holds an id and no role *by
                # design*. Asking a worker for `SYSTEM_ADMIN` therefore refused
                # EVERY deferred load whose approval bar was crossed — over
                # `ASYNC_ROW_BAR` rows with rejects over `APPROVAL_PCT`/
                # `APPROVAL_ROWS` the call answered 202 and the job then died
                # with `metering.import.approver_role`, an error the operator
                # never asked for and could not act on, with not one good row
                # written. That is exactly the migration size CR-026 exists for.
                #
                # ⚠ **THE CHECK MOVED; IT WAS NOT REMOVED** — `DEF-545` is why.
                # Its engine layer exists to catch "a management command, a
                # worker, the next module", and one of those is real: a
                # service-layer `import_runs.load(clerk_actor, run, {"approved":
                # True})` skips `api.py` entirely. Under the bar the engine
                # refused it correctly; over the bar it deferred and the clerk's
                # self-approval was refused only BY ACCIDENT, in a worker.
                # Refusing here refuses that caller on their own call, on
                # purpose, with the identical `BIZ-APPROVAL` refusal.
                _refuse_approver_role(actor)
                # …and the ANSWER is carried forward rather than re-derived, so
                # `_load_locked` can ask "was this approval given by a
                # role-checked approver?" — the same question, asked where it
                # can be answered.
                data[APPROVED_BY_KEY] = str(getattr(actor, "id", None) or "")
            return _defer(actor, run, "load", {"write_mode": write_mode, "data": data})
    with transaction.atomic():
        return _load_apply(actor, run_id, write_mode, data, import_progress.NULL)


def _refuse_file_already_loaded(run: Any) -> None:
    """`DEF-MET-9614` — the same FILE already loaded to this target by ANOTHER
    run is refused BY NAME, before a row is written.

    `uq_import_runs_idempotency` (tenant, target, file_hash, scoped to
    `status='loaded'`) is the guarantee, and it fired only at the run's FINAL
    save — after every row had been written — as an unhandled `IntegrityError`:
    HTTP 500, and on PostgreSQL the whole commit rolled back with it. This is
    the friendly path to that same constraint, asked first, naming the earlier
    run's number so the clerk knows which import already carried the file. The
    constraint stays the backstop for two commits racing past this read.
    """
    if not run.file_hash:
        return
    prior = (
        models.ImportRun.objects.filter(
            tenant_id=run.tenant_id, target=run.target, file_hash=run.file_hash, status="loaded"
        )
        .exclude(pk=run.pk)
        .order_by("created_at")
        .first()
    )
    if prior is not None:
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-MET-090",
            message_key="metering.import.file_already_loaded",
            params={"run_no": prior.run_no or ""},
        )


def _load_apply(
    actor: Any,
    run_id: Any,
    write_mode: str,
    data: dict[str, Any],
    reporter: import_progress.Reporter,
) -> dict[str, Any]:
    """Stage 4's body, UNDECORATED — the one path a request and a worker share.

    ⚠ **ONE TRANSACTION, ALL OR NOTHING — and CR-026 recorded that judgment
    before building on it** (decision log 2026-08-22). A per-chunk commit would
    make a killed worker leave a run that is neither loaded nor unloaded, with
    `uq_import_runs_idempotency` (scoped to `status='loaded'`) unable to say so
    and `_key_of` unable to tell an already-created row from a new one on any
    file without a `premise_no` column. 101.5s in one transaction at 50,000
    rows is the price of the property the whole design rests on.
    """
    with transaction.atomic():
        return _load_locked(actor, run_id, write_mode, data, reporter)


def _premises_type_ids() -> dict[str, Any]:
    """Lowered CODE → PremisesType id. ⚠ **THE COLUMN IS A FOREIGN KEY AND THE
    MAPPED VALUE IS A CODE (`DEF-540`, critical)** — `_record_from` used to pass
    the code straight into `Premises(**record)` and every typed premises
    refused at commit, which made stage 4 unusable on any real export. The
    resolution is a LOAD-time act, read once per run (DEF-324's measured
    reason)."""
    return {
        row.code.lower(): row.pk
        for row in models.PremisesType.objects.filter(tenant_id=_tenant_id(), active=True)
    }


def _area_ids() -> dict[str, Any]:
    """Lowered NAME → tenancy Area id. ⚠ **THE MAPPED AREA WAS CHECKED AND THEN
    SILENTLY DROPPED (`DEF-542`)**: stage 2 carried `area_name`, stage 3 proved
    it exists (`PRM.REFERENCES_ON_FILE`), and the load stripped it — a
    migration would lose every district assignment while every rule reported
    green. `KIND_AREA`'s own docstring always said resolving is a load-time
    act; this is that act."""
    from apps.tenancy import models as tenancy_models

    return {
        str(row.name).strip().lower(): row.pk
        for row in tenancy_models.Area.objects.filter(tenant_id=_tenant_id())
    }


def _resolve_fk_columns(
    record: dict[str, Any],
    mapped: dict[str, Any],
    target: str,
    type_ids: dict[str, Any],
    area_ids: dict[str, Any],
    owner_exact: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The two premises FKs, resolved. Units' `unit_type` is TEXT and needs
    nothing. An unknown code resolves to None rather than raising: stage 3's
    rules already judged this value, and the load honours the judgment the
    operator was shown (BR-MET-090)."""
    if target != TARGET_PREMISES:
        return record
    owner_exact = owner_exact or {}
    code = record.pop("premises_type", None)
    if code:
        record["premises_type_id"] = type_ids.get(str(code).lower())
    area_name = str(mapped.get("area_name") or "").strip().lower()
    if area_name:
        area_id = area_ids.get(area_name)
        if area_id is not None:
            record["area_id"] = area_id
    record = _resolve_owner_ref(record, mapped, owner_exact)
    return record


def _resolve_owner_ref(
    record: dict[str, Any], mapped: dict[str, Any], owner_exact: dict[str, str]
) -> dict[str, Any]:
    """DEF-1088 · BR-MET-402 — the `Owner` cell becomes a PARTY, or provenance.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE ALIAS RE-POINTING IS SAFE **BECAUSE OF THIS FUNCTION** (DEF-1247)║
    ╚══════════════════════════════════════════════════════════════════════╝
    `Owner` used to feed the free-text column and now feeds the typed one, and
    the objection to changing it was that *"flipping it silently re-points every
    existing customer's template at a different column"*. It does not, because
    this writes **both**: the typed link when the party exists, and the
    operator's own string into `owner_manager` regardless — which is BR-MET-151
    clause 4's provenance, is what `unmatched_premises_qs()` reads, and is what
    the PRM-04 matching surface offers a person.

    So a utility whose CSV has always carried an `Owner` column gets everything
    it got before **plus** a resolved party. Nothing that used to be recorded
    stops being recorded.

    ⚠ **EXACT NAMES ONLY, AND NEVER A NEAR ONE.** Picking a near name here
    would be the auto-merge PO decision 3 forbids: *"two landlords with similar
    names are two parties, and merging them bills the wrong one"*. So
    `owner_exact` is keyed on the DATABASE's own case-insensitive unique index,
    a near name misses it, and `owner_id` stays NULL while `owner_manager`
    keeps the operator's string for a person to settle later.

    ⛔ **CORRECTED 2026-09-01 — `DEF-2877`. THIS PARAGRAPH USED TO SAY A NEAR
    MATCH COULD NOT REACH THIS LINE, AND SINCE CR-055 IT REACHES IT ON EVERY
    RUN.** It read: *"A near match was already REJECTED at stage 3
    (`PRM.OWNER_NEAR_MATCH`), so reaching this line with one would mean stage 3
    and stage 4 disagreed — `DEF-544`'s shape"*. **`PRM.OWNER_NEAR_MATCH` has
    been `WARNING` + `FLAG_ONLY` since 2026-08-31** (`CR-055`, v2.103.0, PO
    ruling: the premises LOADS with no owner, flagged, exactly as a blank Owner
    column already does), so stage 3 no longer throws the row away and stage 4
    now sees near names routinely. **The code was and is right; only the stated
    reason was false** — which is hard-won law 1, and is why the exact-only
    lookup below is NOT dead code and must not be "simplified" into a fuzzy one.
    `DEF-544`'s rule still holds for the EXACT answer: stage 3 and stage 4 read
    the same index, so they cannot disagree about who exists.

    ⚠ **AN EXPLICIT `Owner name (legacy)` COLUMN WINS FOR THE FREE TEXT.** A
    file that maps both columns means them separately, and a derived value must
    never overwrite one the operator actually supplied.

    ⛔ **AMENDED 2026-09-19 — `DEF-MET-5802` RETIRED THAT COLUMN FROM THIS
    TEMPLATE**, so an import can no longer supply `owner_manager` directly and
    the guard below now only protects a value already on the row. **The WRITE
    two lines down is untouched and is the reason the retirement is safe**: the
    operator's `Owner name` cell still lands in `owner_manager` as BR-MET-151
    provenance, which is what `unmatched_premises_qs()` reads, what PRM-04
    offers a person, and what `customers.create_master_account` falls back to
    for the contact's name when a row carries no email. Deleting this write
    would silently strip the name off every imported owner account — an
    absence, which CLAUDE.md records as invisible to every check this repo has.
    """
    text = str(mapped.get("owner_ref") or "").strip()
    if not text:
        return record
    owner_id = owner_exact.get(text.lower())
    if owner_id is not None:
        record["owner_id"] = owner_id
    if not str(record.get("owner_manager") or "").strip():
        record["owner_manager"] = text[:200]
    return record


# ═══════════════════════════════════════════════════════════════════════════
# CR-047 WIDENING · TASK 21 — A DATABASE REFUSAL, IN THE OPERATOR'S WORDS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **PREMISES AND UNITS FAIL DIFFERENTLY FROM THE OTHER FOUR TARGETS, AND
# THAT IS WHY THIS TABLE EXISTS.** The three assets targets and the accounts
# target write through an owning module's service, which refuses a bad row BY
# NAME with a `message_key` there are words for. The premises and units path
# writes straight through the ORM (`model.objects.create(...)` /
# `target_row.save()`), so what refuses a row is **PostgreSQL itself**: a
# unique index stage 3 does not model, a NOT NULL column, a foreign key whose
# target vanished mid-run, or a race where another user takes the same premise
# number between the rehearsal and the commit.
#
# ⚠ **A `psycopg` ERROR STRING IS NOT A SENTENCE A CLERK CAN ACT ON.** The raw
# text of the commonest one is *`duplicate key value violates unique constraint
# "uq_premises_tenant_premise_no"`* — a constraint name, a table name and a
# column name, none of which appear on the operator's spreadsheet and all of
# which are exactly the internal references CR-016 rules out. So the SQLSTATE
# is translated and the driver's message is never shown; it is still logged in
# full server-side, so support keeps it.
#
# ⚠ **THE ROW IS NAMED BY ITS OWN IDENTIFYING CELL AND NEVER BY A UUID.** The
# person reading the failures file typed `2205 Cedar Ln` or `Unit B`; they have
# never seen a `premises_id`.

#: PostgreSQL SQLSTATE → (problem, fix_hint), each a `str.format` template over
#: `noun` and `row_label`. Only the classes a migration actually meets are
#: named; everything else takes the honest generic below rather than a guess.
_DB_REFUSAL_SENTENCES: dict[str, tuple[str, str]] = {
    # 23505 unique_violation — the one a re-run or a race actually produces.
    "23505": (
        "Something on {row_label} is already on file, and it has to be unique.",
        "Two {plural} cannot share the same number or the same reference from "
        "your old system. Find the record that already has it, decide which "
        "row is right, and upload the file again.",
    ),
    # 23502 not_null_violation — a required column arrived empty.
    "23502": (
        "{row_label} leaves out something this record cannot be created without.",
        "Compare this row against one that loaded — the difference is an empty "
        "cell — fill it in, and upload the file again.",
    ),
    # 23503 foreign_key_violation — something it points at is gone.
    "23503": (
        "{row_label} points at something that is no longer on file.",
        "Something this row refers to — its premises, its type, its plan — was "
        "removed or renamed while the file was loading. Check it is still "
        "there, then upload the file again.",
    ),
    # 23514 check_violation — a value outside what the column permits.
    "23514": (
        "A value on {row_label} is outside what this record allows.",
        "Compare this row against one that loaded, correct the value that "
        "differs, then upload the file again.",
    ),
    # 22001 string_data_right_truncation — a cell longer than its column.
    "22001": (
        "A value on {row_label} is longer than this record can hold.",
        "Shorten the longest cell on this row — usually a name, an address or "
        "a note — then upload the file again.",
    ),
    # 22P02 invalid_text_representation / 22007 invalid_datetime_format.
    "22P02": (
        "A value on {row_label} is not in a shape this record can store.",
        "Check the numbers and dates on this row against one that loaded, "
        "correct the cell that differs, then upload the file again.",
    ),
    "22007": (
        "A date on {row_label} could not be read.",
        "Write the date the same way as on a row that loaded, then upload the "
        "file again.",
    ),
}

_DB_REFUSAL_UNKNOWN: tuple[str, str] = (
    "{row_label} was refused when it was written, and the run kept going.",
    "Every other row in the file loaded normally. Send this row to support "
    "with the run number on the receipt — they can see exactly what refused it.",
)

#: The word a sentence about one of these rows uses, singular and plural. The
#: assets targets have `ASSET_NOUN_BY_TARGET`; this is the same idea for the
#: two targets that write through the ORM.
_GENERIC_NOUN_BY_TARGET: dict[str, tuple[str, str]] = {
    TARGET_PREMISES: ("premises", "premises"),
    TARGET_UNITS: ("unit", "units"),
}

#: Which cells could identify the row on the OPERATOR's own spreadsheet, best
#: first. The number columns come first and are usually blank — under the PO's
#: ruling of 2026-08-27 the number is issued from the tenant's series — so in
#: practice it is the address or the label that names the row, which is exactly
#: what the person reading the failures file wrote.
_GENERIC_ROW_LABEL_FIELDS: dict[str, tuple[str, ...]] = {
    TARGET_PREMISES: ("premise_no", "address_line", "name", "external_ref"),
    TARGET_UNITS: ("unit_no", "label", "external_ref", "premises_ref"),
}


# ═══════════════════════════════════════════════════════════════════════════
# CR-058 W3 · BR-MET-1030 — DOES THIS ROW EARN THE OWNER AN ACCOUNT?
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **PO RULING 2026-09-01:** *"If owner name is given and one identify given -
# DL, SSN, Phone or Tax ID - then you create master account and Customer ID -
# otherwise dont create anything"*.
#
# ⚠ **ONE FUNCTION ANSWERS IT AND EVERY CALLER READS THE ANSWER.** Stage 3 draws
# the warning, stage 4 decides whether to create, and the receipt counts the two
# outcomes — three readers, three chances for the definition of *"enough"* to
# drift. It is computed from the MAPPED row, so the rehearsal and the commit are
# looking at the same cells (`DEF-544`).

#: The verdicts, named so no caller compares strings.
OWNER_ACCOUNT_ELIGIBLE = "eligible"
#: The row names nobody. Unchanged from before this rule: load the address.
OWNER_ACCOUNT_NO_OWNER = "no_owner"
#: A name and no identifier — the PO's *"otherwise dont create anything"*, and
#: the state the receipt has to make visible.
OWNER_ACCOUNT_AWAITING_IDENTITY = "awaiting_identity"
#: A name and an identifier and no account TYPE. Nothing may guess what a
#: customer is charged as, so this row creates nothing either — a DIFFERENT
#: missing fact from the one above, and it is counted apart because the work it
#: asks of a person is different (find the identifier vs. choose the category).
OWNER_ACCOUNT_NO_ACCOUNT_TYPE = "no_account_type"
#: The kind is missing, or an identifier belongs to the OTHER kind. Refused
#: here rather than filed: `BR-CUS-1022` — a Social Security number under a
#: company is stored where the company matcher never looks.
OWNER_ACCOUNT_IDENTITY_MISMATCH = "identity_mismatch"


def owner_account_verdict(mapped: dict[str, Any]) -> dict[str, Any]:
    """What this row's owner cells earn, and WHY — one answer, three readers.

    Returns `{"verdict": <one of the constants above>, "kind": …,
    "identifiers": {<customers' field name>: <value>}, "account_type": …}`.

    ⚠ **IT DECIDES ONLY WHAT THE IMPORT SCREEN SAYS.** Whether the evidence is
    actually enough to MINT a Customer # is `BR-CUS-1023`'s question and
    customers answers it, inside the account door, with its own vocabulary. This
    is the file-side mirror so an operator is told on their own spreadsheet
    instead of meeting the refusal on row 9,881 — the same reason
    `account_lookup_indexes` exists.
    """
    # ⛔ **`BR-MET-1032` — THE MATCHER'S VIEW, AND IT IS WHY THIS RULE DID NOT
    # BREAK THE FEATURE IT HARDENED.** `mapped` holds `••••6789`
    # and an envelope; `customers` needs the nine digits, because a blind index
    # cannot be built from four. A redaction on the way IN would have looked
    # like security and silently created a second customer for every returning
    # person.
    mapped = revealed_mapped(mapped, TARGET_PREMISES)
    name = str(mapped.get("owner_ref") or "").strip()
    kind = str(mapped.get("owner_kind") or "").strip().lower() or None
    account_type = mapped.get("owner_account_type")
    # ⚠ **CARRIED, NEVER JUDGED HERE (PO ruling 2026-09-19).** Whether the
    # code names a real, active category is `premises_owners._resolve_category`'s
    # question and it answers it against the tenant's own list. This function
    # decides what the IMPORT SCREEN says, so it reports only whether the
    # operator STATED one — a second opinion about a lookup somebody else owns
    # is exactly what `BR-MET-096` and the `identity_match` note above forbid.
    #
    # ⚠ **IT IS NOT PART OF ANY VERDICT.** A missing category does NOT stop an
    # owner account being created: the PO's ruling adds a way to state the
    # category, and the 2026-08-27 ruling that an ownerless address still loads
    # is untouched. So there is no `OWNER_ACCOUNT_NO_CATEGORY` verdict, by
    # design — the five verdicts below are about the ACCOUNT, and the category
    # is about the PARTY.
    category = str(mapped.get("owner_category") or "").strip() or None
    # ⛔ **BOTH, AND THE PAIR IS THE POINT.** `owner_category` is the RESOLVED
    # code and the lookup answers `None` for a value that is not on the tenant's
    # list — so *"the row said nothing"* and *"the row said something we do not
    # recognise"* arrive here identically. They are different facts with
    # different next actions: one is a decision nobody has taken, the other is a
    # typo or a list that needs a new entry.
    #
    # ⚠ **FOUND BY THE WALK, NOT BY A TEST.** On its first real run case 8 —
    # a category of `not_a_real_category` — was counted as *no category
    # stated*, which is the receipt telling an operator the opposite of what
    # they did. `_map_row` keeps the operator's own text in `<target>_raw` for
    # exactly this, and reading it is what lets the two be told apart.
    category_raw = str(mapped.get("owner_category_raw") or "").strip() or None
    presented = {
        column: str(mapped.get(column) or "").strip()
        for column in OWNER_IDENTIFIER_COLUMNS
        if str(mapped.get(column) or "").strip()
    }
    out: dict[str, Any] = {
        "kind": kind,
        "identifiers": {},
        "account_type": account_type,
        "category": category,
        "category_raw": category_raw,
        "presented_columns": sorted(presented),
    }
    if not name:
        # ⚠ **AN IDENTIFIER WITH NO NAME IS STILL NOTHING.** The ruling's first
        # word is *"If owner name is given"*, and a government identifier with
        # no party attached is not a party — it is a cell nobody can act on.
        out["verdict"] = OWNER_ACCOUNT_NO_OWNER
        return out
    if not presented:
        out["verdict"] = OWNER_ACCOUNT_AWAITING_IDENTITY
        return out
    if kind is None or kind not in OWNER_IDENTIFIER_COLUMNS_BY_KIND:
        out["verdict"] = OWNER_ACCOUNT_IDENTITY_MISMATCH
        out["reason"] = "kind_not_stated"
        return out
    allowed = OWNER_IDENTIFIER_COLUMNS_BY_KIND[kind]
    borrowed = sorted(column for column in presented if column not in allowed)
    if borrowed:
        out["verdict"] = OWNER_ACCOUNT_IDENTITY_MISMATCH
        out["reason"] = "identifier_belongs_to_the_other_kind"
        out["borrowed"] = borrowed
        return out
    if not account_type:
        out["verdict"] = OWNER_ACCOUNT_NO_ACCOUNT_TYPE
        return out
    out["identifiers"] = {
        OWNER_IDENTIFIER_FIELD[column]: value for column, value in presented.items()
    }
    out["verdict"] = OWNER_ACCOUNT_ELIGIBLE
    return out


def owner_customer_block(mapped: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    """The `customer` block the account door resolves, built from the file.

    ⚠ **IT RESOLVES NOTHING AND MATCHES NOTHING.** Under `CR-058`'s governing
    ruling every door resolves the customer in ONE act, inside the module that
    owns customers — match first, create only on no match, and only where an
    identifier is present. This assembles the EVIDENCE and hands it over; a
    second matcher on this side of the boundary is exactly what *"no door
    repeats the logic"* forbids.
    """
    return {
        "display_name": str(mapped.get("owner_ref") or "").strip()[:200],
        "kind": verdict["kind"],
        "identity": dict(verdict["identifiers"]),
    }


def owner_contact_block(mapped: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    """`DEF-MET-5803` — how this owner is REACHED, as `create_master_account`
    spells it. `owner_customer_block`'s twin: that one carries who they ARE.

    ⚠ **EMPTY UNLESS THERE IS AN EMAIL, AND THAT IS A DELIBERATE NON-CHANGE.**
    With no email this answers `{}`, `_validate_contact` reads `{}` as `None`,
    and the account door falls back to the premises' own `owner_manager` —
    which `_resolve_owner_ref` has already written from the very same `Owner
    name` cell. So a file with no email behaves EXACTLY as it did before this
    column existed, down to the contact's name, and the only rows whose
    behaviour moves are the ones that now carry something new to say.

    ⚠ **`full_name` IS SENT WITH THE EMAIL BECAUSE THE DOOR REQUIRES IT.**
    `_validate_contact` refuses a contact block with no `full_name` by name, so
    an email alone would turn a good row into a refused owner account. It is
    never absent here in practice — this is only ever called on an ELIGIBLE
    verdict, and `owner_account_verdict` cannot answer ELIGIBLE without a name
    — but it is passed explicitly rather than relying on that, because the two
    functions are free to change apart.

    ⚠ **A MALFORMED EMAIL REFUSES THE OWNER ACCOUNT, AND THE PREMISES STILL
    LOADS.** `_validate_contact` checks the `@`, so a typo raises an
    `ApiError`, which the caller counts and names on the receipt as an owner
    refusal. That is this path's existing posture for every other refusal and
    it is the honest one: the alternative is dropping a cell the operator
    typed, which is `DEF-632`'s shape — a clerk believing something was stored
    when it was not.
    """
    email = str(mapped.get("owner_email") or "").strip()
    if not email:
        return {}
    return {
        "full_name": str(mapped.get("owner_ref") or "").strip()[:200],
        "email": email[:254],
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-058 W7 · BR-CUS-1041 — WHAT AN ACCOUNTS ROW'S CUSTOMER CELLS EARN
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **PO RULING 2026-09-01:** a name **and one identifier** loads the account
# and matches-or-creates its customer; a name **alone** loads NOTHING and is
# counted on the receipt as needing an identifier.
#
# ⚠ **THIS IS THE PREMISES SHAPE (`owner_account_verdict`) AND NOT A SECOND
# ONE.** Same three readers — stage 3's evaluators, stage 4's loader and the
# receipt — reading ONE function, so the warning an operator is shown and the
# act taken cannot disagree (`DEF-544`'s law applied to a judgment).
#
# ⚠ **TWO FAILURE VERDICTS WHERE PREMISES HAS THREE, AND THE MISSING ONE IS
# MISSING BY ARITHMETIC.** `PRM.OWNER_ACCOUNT_TYPE_MISSING` exists because the
# premises file's owner account type is optional; on THIS target `account_type`
# is `required=True` and `ACC.TYPE_IN_LOOKUP` already refuses a row without
# one, so a third verdict here would be a branch no row can reach.

#: The row earns an account and a matched-or-created customer.
ACCOUNT_IDENTITY_ELIGIBLE = "eligible"
#: A name and no identifier for the stated kind — the PO's *"otherwise dont
#: create anything"*, and the state the receipt has to make visible.
ACCOUNT_IDENTITY_AWAITING = "awaiting_identity"
#: An identifier is present and the kind is unstated, or the identifier belongs
#: to the OTHER kind. Refused rather than filed: `BR-CUS-1022` — a Social
#: Security number under a company is stored where the company matcher never
#: looks.
ACCOUNT_IDENTITY_MISMATCH = "identity_mismatch"
#: The row names nobody at all. `customer_name` is `required=True`, so this is
#: a blank CELL rather than an unmapped column — and under the ruling a row
#: with no name has nothing to identify, so it creates nothing either.
ACCOUNT_IDENTITY_NO_NAME = "no_customer_name"


def account_identity_verdict(mapped: dict[str, Any]) -> dict[str, Any]:
    """What this row's customer cells earn, and WHY — one answer, three readers.

    Returns `{"verdict": <one of the constants above>, "kind": …,
    "identifiers": {<customers' field name>: <value>}, "name": …}`.

    ⚠ **IT DECIDES ONLY WHAT THE IMPORT SAYS AND WRITES NOTHING.** Whether the
    evidence is actually enough to MINT a Customer # is `BR-CUS-1023`'s question
    and `customers` answers it, inside the account door, in its own vocabulary.
    This is the file-side mirror so an operator is told on their own spreadsheet
    rather than meeting the refusal on row 9,881.

    ⛔ **`customer_ref` AND `customer_no` ARE ABSENT FROM THIS FUNCTION ON
    PURPOSE.** The first is the utility's reconciliation key into the system we
    are migrating FROM and the second is our own number for a row we may
    already hold. Both name a ROW; neither evidences a PERSON, and satisfying
    the minimum with either is exactly the invented value the ruling forbids —
    the matcher would then read a foreign primary key as identity.
    """
    # `BR-MET-1032`, the accounts door's half — identical to
    # `owner_account_verdict`'s, and identical on purpose: one decision fixed
    # both doors because both stage through `import_run_rows`.
    mapped = revealed_mapped(mapped, TARGET_ACCOUNTS)
    name = str(mapped.get("customer_name") or "").strip()
    kind = str(mapped.get("customer_kind") or "").strip().lower() or None
    presented = {
        column: str(mapped.get(column) or "").strip()
        for column in ACCOUNT_IDENTIFIER_COLUMNS
        if str(mapped.get(column) or "").strip()
    }
    out: dict[str, Any] = {
        "kind": kind,
        "name": name,
        "identifiers": {},
        "presented_columns": sorted(presented),
    }
    if not name:
        # ⚠ **AN IDENTIFIER WITH NO NAME IS STILL NOTHING**, the same reading
        # `owner_account_verdict` takes: the ruling's first word is *"If … name
        # is given"*, and a government identifier with no party attached is a
        # cell nobody can act on.
        out["verdict"] = ACCOUNT_IDENTITY_NO_NAME
        return out
    if not presented:
        out["verdict"] = ACCOUNT_IDENTITY_AWAITING
        return out
    if kind is None or kind not in ACCOUNT_IDENTIFIER_COLUMNS_BY_KIND:
        out["verdict"] = ACCOUNT_IDENTITY_MISMATCH
        out["reason"] = "kind_not_stated"
        return out
    allowed = ACCOUNT_IDENTIFIER_COLUMNS_BY_KIND[kind]
    borrowed = sorted(column for column in presented if column not in allowed)
    if borrowed:
        # ⚠ **BORROWED, NOT MERELY EXTRA.** A company row carrying a phone has
        # only the phone: the phone is a PERSON's identifier and filing it under
        # a company puts it where the company matcher never looks. The row is
        # refused by name so the operator moves the value or corrects the kind.
        out["verdict"] = ACCOUNT_IDENTITY_MISMATCH
        out["reason"] = "identifier_belongs_to_the_other_kind"
        out["borrowed"] = borrowed
        return out
    out["identifiers"] = {
        ACCOUNT_IDENTIFIER_FIELD[column]: value for column, value in presented.items()
    }
    out["verdict"] = ACCOUNT_IDENTITY_ELIGIBLE
    return out


def account_customer_block(mapped: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    """The `customer` block the account door resolves, built from the file.

    ⚠ **IT RESOLVES NOTHING AND MATCHES NOTHING.** Under `CR-058`'s governing
    ruling every door resolves the customer in ONE act, inside the module that
    owns customers — match first, create only on no match, and only where an
    identifier is present. This assembles the EVIDENCE and hands it over; a
    second matcher on this side of the boundary is what *"no door repeats the
    logic"* forbids. `owner_customer_block` is its twin, one target along.

    Two keys ride beside the evidence and neither is evidence: `external_ref`
    is the utility's legacy id for the PERSON (`BR-CUS-054`) and `customer_no`
    is ours (`BR-CUS-1042`). Both are exact-match keys the door may LINK on;
    neither can create a customer by itself.
    """
    return {
        "display_name": verdict["name"][:200],
        "kind": verdict["kind"],
        "identity": dict(verdict["identifiers"]),
        "external_ref": mapped.get("customer_ref"),
        "customer_no": mapped.get("customer_no"),
    }


def _generic_row_label(target: str, mapped: dict[str, Any]) -> str:
    """The name the OPERATOR knows this row by — their cell, never our uuid."""
    noun, _plural = _GENERIC_NOUN_BY_TARGET.get(target, ("record", "records"))
    for field in _GENERIC_ROW_LABEL_FIELDS.get(target, ()):
        value = str((mapped or {}).get(field) or "").strip()
        if value:
            return f"The {noun} {value}"
    return f"This {noun}"


#: The driver exception class names, for the case where no SQLSTATE survives
#: the wrapping. psycopg names its exception classes after the PostgreSQL
#: condition, so the class IS the state under another spelling — and reading
#: it is the only thing left that is not the driver's English message.
_DB_STATE_BY_DRIVER_CLASS: dict[str, str] = {
    "UniqueViolation": "23505",
    "NotNullViolation": "23502",
    "ForeignKeyViolation": "23503",
    "CheckViolation": "23514",
    "ExclusionViolation": "23505",
    "StringDataRightTruncation": "22001",
    "InvalidTextRepresentation": "22P02",
    "InvalidDatetimeFormat": "22007",
    "NumericValueOutOfRange": "22003",
}

#: ⛔ **SQLITE IS READ TOO, AND IT IS NOT A CONVENIENCE — IT IS THE ONLY REASON
#: ANY OF THIS IS TESTED.** The product runs on PostgreSQL 16 and always will;
#: `config/settings/test.py` runs the suite on in-memory sqlite, so a
#: translation table that read only psycopg's states would produce the generic
#: sentence for every case in this repo's own tests and nothing would ever have
#: exercised the seven rows above. That is hard-won law 1 in its usual disguise:
#: an untested table is a comment about a table.
#: sqlite exposes `sqlite_errorname` from Python 3.11; the names below are its
#: extended result codes, mapped onto the PostgreSQL state that means the same
#: thing so there is ONE sentence table and not two.
_DB_STATE_BY_SQLITE_NAME: dict[str, str] = {
    "SQLITE_CONSTRAINT_UNIQUE": "23505",
    "SQLITE_CONSTRAINT_PRIMARYKEY": "23505",
    "SQLITE_CONSTRAINT_ROWID": "23505",
    "SQLITE_CONSTRAINT_NOTNULL": "23502",
    "SQLITE_CONSTRAINT_FOREIGNKEY": "23503",
    "SQLITE_CONSTRAINT_CHECK": "23514",
    "SQLITE_TOOBIG": "22001",
    "SQLITE_MISMATCH": "22P02",
}

#: How far up the `__cause__` / `__context__` chain to look for the driver's
#: own exception. Small and bounded: this runs per refused row, and a chain
#: longer than this is not a database refusal we can name anyway.
_DB_CAUSE_DEPTH = 6


def _db_state(exc: Exception) -> str:
    """The PostgreSQL SQLSTATE behind a Django database exception, or "".

    ⚠ **THE CHAIN IS WALKED, NOT READ ONCE, AND THAT IS `DEF-2519`'s WIDENING
    LANE FINDING IT THE HARD WAY.** The obvious `exc.__cause__.sqlstate` is
    what the first draft did and it returned `None` on every real refusal:
    Django's `DatabaseErrorWrapper` is entered more than once on the path a row
    takes — the ORM's own wrapper and the savepoint's — so the caught
    `IntegrityError`'s `__cause__` is ANOTHER Django `IntegrityError`, and the
    driver's exception is two or three hops further down. A one-hop read
    silently produced the generic sentence for every row, which is exactly the
    kind of failure that looks handled.

    psycopg 3 exposes the five-character state as `sqlstate` and psycopg 2 as
    `pgcode`; both are read, and the driver's class NAME is the last fallback,
    so this does not become a defect the day the driver moves.
    """
    seen = exc
    for _hop in range(_DB_CAUSE_DEPTH):
        state = getattr(seen, "sqlstate", None) or getattr(seen, "pgcode", None)
        if state:
            return str(state)
        by_sqlite = _DB_STATE_BY_SQLITE_NAME.get(
            str(getattr(seen, "sqlite_errorname", "") or "")
        )
        if by_sqlite:
            return by_sqlite
        by_class = _DB_STATE_BY_DRIVER_CLASS.get(type(seen).__name__)
        if by_class:
            return by_class
        nxt = getattr(seen, "__cause__", None) or getattr(seen, "__context__", None)
        if nxt is None or nxt is seen:
            break
        seen = nxt
    return ""


def _db_refusal_sentences(
    exc: Exception, target: str, mapped: dict[str, Any]
) -> tuple[str, str]:
    """One caught database refusal → the two sentences the row carries.

    ⚠ **THE DRIVER'S MESSAGE IS LOGGED AND NEVER RENDERED.** It is `DEF-322`'s
    ruling one layer down: an operator sees the sentence for the FAILURE CLASS
    and nothing else, and a constraint name is the purest form of the internal
    reference CR-016 forbids on a customer-facing surface.
    """
    noun, plural = _GENERIC_NOUN_BY_TARGET.get(target, ("record", "records"))
    facts = {
        "noun": noun,
        "plural": plural,
        "row_label": _generic_row_label(target, mapped),
    }
    state = _db_state(exc)
    templates = _DB_REFUSAL_SENTENCES.get(state)
    if templates is None:
        templates = _DB_REFUSAL_UNKNOWN
    logger.warning(
        "import: %s row refused by the database (sqlstate %s): %s",
        target,
        state or "unknown",
        exc,
    )
    problem, fix_hint = templates
    try:
        return problem.format(**facts), fix_hint.format(**facts)
    except (KeyError, IndexError, ValueError):  # pragma: no cover — defensive
        unknown_problem, unknown_fix = _DB_REFUSAL_UNKNOWN
        return unknown_problem.format(**facts), unknown_fix.format(**facts)


def _load_locked(
    actor: Any,
    run_id: Any,
    write_mode: str,
    data: dict[str, Any],
    reporter: import_progress.Reporter = import_progress.NULL,
) -> dict[str, Any]:
    run = _run(run_id, locked=True)
    if run.status == "loaded":
        # ⚠ **IDEMPOTENCY, AND IT IS SCOPED TO THE COMMIT** — hard rule 6. The
        # same file may be uploaded and rehearsed as often as anyone likes
        # (TC-21); only a second COMMIT of the same run is a double-load, and
        # the receipt is returned rather than the rows being written twice.
        #
        # ⚠ **SAME MODE ONLY.** A second commit in a DIFFERENT mode is not a
        # retry — it is a request to do something the run already refused to
        # be: `insert` then `replace` would retire every row the first commit
        # deliberately left alone. That refuses as the committed-run immutable
        # (the first suite run under the DEF-541 fix caught exactly this: the
        # branch answered a `replace` with the `insert` receipt and called it
        # idempotency).
        if write_mode != run.write_mode:
            raise errors.BizError(
                errors.BIZ_IMMUTABLE,
                br_ref="BR-MET-090",
                message_key="customers.import.already_committed",
            )
        return receipt(run)
    if run.status != "validated":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-090",
            message_key="metering.import.not_validated",
        )
    _refuse_file_already_loaded(run)

    figures = dry_run(actor, run.id, write_mode)
    if figures["approval"]["required"] and not bool(data.get("approved")):
        # BR-MET-098 — refused BY NAME with both bars and the run's own numbers,
        # so the operator can see WHICH one they crossed.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-098",
            message_key="metering.import.approval_required",
            params={
                "pct": APPROVAL_PCT,
                "rows": APPROVAL_ROWS,
                "rejected": figures["approval"]["rejected"],
                "of_rows": figures["approval"]["of_rows"],
            },
        )
    if figures["approval"]["required"] and not (
        _has_approver_role(actor) or data.get(APPROVED_BY_KEY)
    ):
        # ⚠ **THE SECOND CLAUSE IS `DEF-1108` (high), AND IT IS THE WHOLE FIX.**
        # This body is *"the one path a request and a worker share"* — and a
        # worker carries `_JobActor`, which holds an id and no role BY DESIGN.
        # So `_has_approver_role(actor)` is false in a worker for EVERY deferred
        # load, and asking it alone refused every commit over `ASYNC_ROW_BAR`
        # whose rejects crossed the bar: the operator got a 202, then a job that
        # died with `metering.import.approver_role` — a role demand they could
        # not satisfy, on a run where not one good row was written.
        #
        # The question is now *"was this approval given by a role-checked
        # approver?"* rather than *"does this actor hold a role?"*. It is the
        # SAME question — `load()` answered it at the door, where a real role
        # still existed, and stamped `APPROVED_BY_KEY` on the job payload only
        # after `_refuse_approver_role` passed. **The stamp cannot be forged**:
        # `load()` strips any caller-supplied copy from its own dict before
        # anything reads it, so this key can only have been written by the check
        # passing.
        #
        # ⛔ **BR-MET-098's APPROVER IS A ROLE, AND THIS LINE IS WHERE IT IS
        # CHECKED IN THE ENGINE (`DEF-545`).** The rule's own words: *"THE
        # APPROVER IS THE SAME PAIR OF ROLES AS THE RATE-CHANGE SECOND
        # APPROVAL (BR-RAT-091's 10 percent bar): Owner or Admin"*. The
        # arithmetic above was implemented in full — both bars, the refusal,
        # its params — and the APPROVER clause, one sentence inside a long
        # rule about two thresholds, was not: `load()` is
        # `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`, so a Billing Clerk who
        # crossed the bar could tick the box and be their own second pair of
        # eyes.
        #
        # ⚠ **THIS IS THE SECOND LAYER, NOT THE FIRST** (BR-SHL-025, defence in
        # depth). `api.py::import_load` refuses `approved` from a non-admin at
        # the edge; that is the OUTER layer and a service-layer caller — a
        # management command, a worker, the next module — bypasses it entirely.
        #
        # ⚠ **AND IT IS DELIBERATELY NARROWER THAN THE OUTER LAYER. Read this
        # before "aligning" the two.** `api.py` refuses `approved` from a
        # non-admin ALWAYS, including on a clean run where no approval is
        # required. Here the refusal fires only where the rule actually speaks:
        # when the bar IS crossed and the flag is what lets the load through.
        # BR-MET-098 names an approver for a load that needs approving; it says
        # nothing about a flag on a run that needs none, where the flag grants
        # nothing and refusing it would be a rule this repo has not been given.
        # The strict edge stays strict, the engine refuses exactly the hazard,
        # and neither layer invents law (CLAUDE.md: AI implements signed law).
        #
        # Raised through the shared helper so the engine's refusal and the
        # door's are literally the same code (`DEF-1108`). `actor` is passed and
        # re-tested there rather than raising inline: the helper is a no-op for
        # an approver and a refusal for anyone else, and this branch is only
        # reached when neither clause above held — so it always refuses here.
        _refuse_approver_role(actor)

    if run.target in ASSETS_TARGETS:
        # ⚠ **THE ASSETS COMMIT DELEGATES EVERY ROW WRITE TO `apps.assets.
        # services` THROUGH THE SEAM** (B2 r4 / B16 §4.7: the runner stages
        # and judges; the owning module writes). The guards ABOVE this line —
        # idempotency, status, BR-MET-098's approval, OQ-326's replace
        # refusal (inside the dry run) — are shared with every target; only
        # the row-writing half differs, exactly as the units half already
        # does below for its plan/premise resolution.
        return _load_assets_rows(actor, run, write_mode, data, reporter)
    if run.target == TARGET_ACCOUNTS:
        # CR-030 W1, same law and same line as the assets branch above: this
        # module stages, maps and judges; `accounts` is customers' table and
        # customers writes it (B1/B2 §2).
        return _load_accounts_rows(actor, run, write_mode, data, reporter)
    if run.target == TARGET_PARTS:
        # CR-077, the THIRD instance of the same law and the same line: `parts`
        # is work's table, `BR-WRK-002` forbids a foreign write and `G78` fails
        # one — so work writes it, through `work.import_writer`, and nothing in
        # this module names the table at all.
        return _load_parts_rows(actor, run, write_mode, data, reporter)
    if run.target == TARGET_PAYMENTS:
        # `P1.2` — the FOURTH instance of the same law and the same line:
        # `payments` is the payments module's table, so payments writes it,
        # through `payments.import_writer`, and nothing in this module names
        # the table at all.
        return _load_payments_rows(actor, run, write_mode, data, reporter)

    rows = _loadable_rows(run)
    existing = _existing_index(run)
    model = _model_for(run.target)
    type_ids = _premises_type_ids() if run.target == TARGET_PREMISES else {}
    area_ids = _area_ids() if run.target == TARGET_PREMISES else {}
    # DEF-1088 — the SAME exact index stage 3 judged against (DEF-544: a load
    # that resolves against a different world than stage 3 showed is a defect
    # in its own right, not a race).
    #
    # ⛔ **CR-055 — THE *NEAR* INDEX IS READ HERE TOO NOW, AND FOR THE SAME
    # DEF-544 REASON.** Under the PO ruling of 2026-08-31 an ambiguous owner
    # name LOADS ownerless instead of being rejected at stage 3, so the loader
    # is the first thing that has to tell *"the column named nobody"* from
    # *"the name matched two parties"* — two states that both end with no owner
    # and need opposite work from a person. It reads the near index from the
    # SAME `_owner_indexes()` call stage 3 judged against, so the receipt
    # cannot classify a row differently from the sentence the operator was
    # shown. ⚠ It is used ONLY to classify. Nothing here resolves a near name
    # to a party — that is the auto-merge PO decision 3 forbids, and CR-055
    # explicitly did not reverse it.
    owner_indexes = (
        _owner_indexes()
        if run.target == TARGET_PREMISES
        else {"owner_exact": {}, "owner_near": {}}
    )
    owner_exact = owner_indexes["owner_exact"]
    owner_near = owner_indexes["owner_near"]
    plan_index = seams.assignable_plan_index() if run.target == TARGET_UNITS else {}
    premises_by_no = (
        {
            str(row.premise_no).strip().lower(): row.pk
            for row in models.Premises.objects.filter(
                tenant_id=run.tenant_id, deleted_at__isnull=True
            ).exclude(premise_no__isnull=True)
        }
        if run.target == TARGET_UNITS
        else {}
    )

    created = updated = unplanned = 0
    #: `DEF-MET-10164` — how many records' Created date this run moved, and the
    #: utility's own zone the days are stamped in (read once, not per row).
    created_corrected = 0
    created_zone = seams.tenant_timezone()
    #: ⚠ **A MISSING NUMBER SERIES IS REPORTED, NEVER FAKED** (BR-MET-001, and
    #: `services._allocate_number`'s own posture). The rows still load — a
    #: premises with no number is a lawful row and always has been — and the
    #: receipt carries `numbering_series_missing` so the operator is told, in
    #: the one place they are looking, that their Settings are not set up.
    warnings: list[dict[str, Any]] = []
    #: ⛔ **CR-046 C2/C3 — REJECTED, NOT SKIPPED, AND THE PO CHOSE THE WORD.**
    #: *"in case of insert - reject it"*. A skip reads on a receipt as *"left
    #: unchanged"* — benign, nothing to do. A reject reads as *"this row did
    #: not load"*, which is what the operator has to act on.
    rejected_existing = 0
    #: How many rows took their number from the tenant's series rather than
    #: from the file — which, since the ruling, is every created row. Counted
    #: rather than assumed, so a receipt read a year from now says where those
    #: numbers came from without anyone having to know the rule.
    issued_from_series = 0
    #: ⛔ **CR-047 WIDENING · TASK 21 — rows the DATABASE refused, one savepoint
    #: each.** The same counter name and the same meaning as the accounts and
    #: assets loaders', because one receipt screen renders every target. On
    #: this path the refusal comes from PostgreSQL rather than from a module's
    #: validator, and it is the same fact to an operator: the row was
    #: attempted and turned down, and everything else loaded.
    rejected_at_write = 0
    #: ⛔ **HOW MANY PREMISES LANDED OFFERING NO SERVICES AT ALL — a number on
    #: a receipt instead of an invisible migration failure.**
    #: A premises whose `services_available` is empty offers NOTHING, so every
    #: unit under it refuses every service — and the symptom appears TWO
    #: UPLOADS LATER, as meters rejected for a service the utility plainly
    #: sells (`AST.SERVICE_AT_PREMISES`). By then the operator is debugging the
    #: meters file, which is not where the problem is.
    #: ⚠ **COUNTED, NEVER REFUSED.** An empty list is lawful — a premises can
    #: legitimately offer nothing yet — and rejecting it would block a
    #: migration over a column a utility may fill in later. The row loads and
    #: the receipt says how many did.
    no_services = 0
    #: ⛔ **HOW MANY PREMISES LANDED WITH NO OWNER AT ALL — PO ruling 2026-08-27,
    #: the narrowing of `BR-MET-401`.** Verbatim: *"what if owner column is
    #: empty - in such case we create the premises and keep owner name empty -
    #: we cna edit and updaste it later"*.
    #: ⚠ **NO OWNER MEANS NO MASTER ACCOUNT, SO THAT ADDRESS HAS NOBODY TO
    #: CHARGE.** It is a real premises — it holds units and meters and can be
    #: read — and it cannot be BILLED until somebody fills the owner in. That is
    #: the cost of the ruling, and the whole reason this is a NUMBER on a
    #: receipt rather than a state a row quietly sits in: a blank-owner row must
    #: never be indistinguishable from a complete one. The worklist behind it is
    #: `unmatched_premises_qs()`, which already existed.
    #:
    #: ⛔ **CR-055 (2026-08-31) — THIS COUNTER IS NOW A SUM OF TWO, AND THE
    #: SPLIT IS THE POINT.** The PO widened the ruling above to cover a name
    #: that matches two or more parties: it LOADS ownerless too, so it belongs
    #: in this figure. But *"the column named nobody"* and *"the name matched
    #: two parties"* need opposite work from a person, so the run records both
    #: components and the total is derived from them at the bottom of this
    #: function. There is no bare `no_owner` counter any more, on purpose: one
    #: would be a second place the same fact could be written, and the two
    #: would eventually disagree.
    #: ⛔ **CR-055 TASK 2 — THE SAME TOTAL, SPLIT IN TWO, BECAUSE THE TWO HALVES
    #: NEED DIFFERENT WORK FROM A PERSON.** PO ruling 2026-08-31 adds the
    #: ambiguous-name case to the ownerless pool, and the CR says why the split
    #: is the task rather than the total: *"a blank needs research, a
    #: near-match needs a decision between two named parties the file already
    #: knows"*. A receipt that merged them into one figure would throw away the
    #: more actionable half — the operator can settle an ambiguity from the
    #: screen, and cannot settle a blank without going to a filing cabinet.
    #: `premises_with_no_owner` is DERIVED from these two at the bottom of this
    #: function and keeps meaning exactly what it always meant.
    no_owner_blank = 0
    no_owner_ambiguous = 0
    #: ⛔ **CR-058 W3 · BR-MET-1030 — WHICH ROWS GOT AN OWNER ACCOUNT AND
    #: WHICH ARE WAITING FOR SOMEBODY TO IDENTIFY THE OWNER.**
    #: PO ruling 2026-09-01: *"If owner name is given and one identify given -
    #: DL, SSN, Phone or Tax ID - then you create master account and Customer
    #: ID - otherwise dont create anything"*, and `CR-058` task 12 asks for
    #: exactly this pair on the receipt.
    #:
    #: ⚠ **THE SECOND FIGURE IS THE WHOLE MITIGATION, NOT A STATISTIC.** Without
    #: it a migration that identified half its owners is indistinguishable from
    #: one that identified all of them — the same failure `premises_with_no_
    #: owner` was created to make visible, one rule later. A row waiting for
    #: identity has an address that loads, holds units and meters, and **cannot
    #: be billed to anybody**, exactly as an ownerless one cannot.
    #:
    #: ⚠ **THREE COUNTERS AND NOT TWO, BECAUSE THE WORK IS DIFFERENT.** *No
    #: identifier* needs somebody to go and find one; *no account type* needs
    #: somebody to choose a category; *identity mismatch* needs somebody to say
    #: whether this owner is a person or a company. A receipt that merged them
    #: would tell an operator that N rows need attention and nothing about what
    #: kind of attention, which is `DEF-771` clause 3's lesson.
    owner_accounts_created = 0
    owner_awaiting_identity = 0
    owner_no_account_type = 0
    owner_identity_mismatch = 0
    #: Rows whose owner account could not be created because the ACCOUNT DOOR
    #: refused — a unit already occupied, a missing plan, a duplicate. Counted
    #: apart from the three above: those are facts missing from the FILE, this
    #: is the product declining. The premises still loaded.
    owner_account_refused = 0
    owner_account_refusals: list[dict[str, Any]] = []
    #: ⛔ **THE PARTY, COUNTED SEPARATELY FROM THE ACCOUNT (PO 2026-09-19).**
    #: An account and an owner RECORD are two different things and the whole
    #: reported defect was that the receipt counted the first and said nothing
    #: about the second — `premises_owner_accounts_created = 2` was TRUE of an
    #: account attached to a building with nobody named on it. Three figures,
    #: because the next action differs: a party was created — a party was
    #: refused, and by what — or the row simply did not say what kind of owner
    #: this is, which is a thirty-second decision on `PRM-04`.
    owner_parties_created = 0
    owner_no_category = 0
    owner_party_refused = 0
    owner_party_refusals: list[dict[str, Any]] = []
    #: ⛔ **THE FIFTH VERDICT, WHICH HAD NO COUNTER AT ALL (PO 2026-09-19,
    #: *"this is correct"*).** `owner_account_verdict` answers five ways and the
    #: chain below had a branch for four. A row naming NOBODY was warned at
    #: rehearsal (*"This row names no owner."*) and then counted nowhere, so
    #: `premises_owner_blank` and `premises_with_no_owner` both read 0 over it.
    #:
    #: ⚠ **THAT IS LAW 7'S *REPORTING ZERO OVER A SCOPE IT SILENTLY EXCLUDES*,
    #: IN A RECEIPT INSTEAD OF A GATE.** Four owner figures printed and a fifth
    #: could not, so four zeroes read as a clean run. The check was not lying
    #: about what it could see; nothing said what it could not.
    owner_no_owner_named = 0
    #: CR-055 — WHICH parties each ambiguous row looked like, keyed by the
    #: normalised name so one spelling repeated across 400 rows is one line.
    #: Same shape and same reason as `unplanned_plans` below (DEF-771 clause 3:
    #: *"the count alone cannot be reviewed"*).
    owner_ambiguities: dict[str, dict[str, Any]] = {}
    #: DEF-771 — the per-PLAN summary the receipt states, accumulated as the
    #: rows are written so it costs the load nothing extra.
    unplanned_plans: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    # DEF-577: every number this run puts in the table, so the series can be
    # moved clear of them once the writing is done.
    numbers_written: list[str] = []
    number_field = TARGET_SERIES.get(run.target, (None, None))[1]
    reporter.mark(0, "Writing rows")
    for written, row in enumerate(rows, start=1):
        # CR-026 — the gauge (throttled; see `_apply_mapping`'s note). It is
        # written on a SECOND connection precisely because this transaction has
        # not committed: from inside here, nothing else is visible to a poller.
        reporter.step(written)
        mapped = dict(row.mapped or {})
        # CR-055 — the row this iteration actually WROTE, or None if it
        # wrote nothing. Assigned in BOTH write branches below; the
        # branches that write nothing `continue` before the counters, and
        # this default is the belt to that braces so a future branch
        # cannot reach them undefined.
        written_row = None
        key = _key_of(run, mapped)
        if key is not None:
            seen.add(key)
        record = _record_from(mapped, run.target)
        record = _resolve_fk_columns(
            record, mapped, run.target, type_ids, area_ids, owner_exact
        )
        # `DEF-MET-10164` — the Created day travels BESIDE the record, never in
        # it: `created_at` is `auto_now_add`, so `objects.create(created_at=…)`
        # would be silently overwritten with now, and a `setattr` on the update
        # path would move it with no old → new audit row.
        created_day = record.pop(CREATED_FIELD, None)

        # ── `DEF-MET-10164` point 5 — THE DATES-ONLY CORRECTION ROW ─────────
        # A row carrying only our number and a Created date corrects that date
        # on the record it names and touches NOTHING else: no other column, no
        # owner, no plan, no number. Stage 3 judged it with the same predicate
        # (`import_rules.is_dates_only_row`). Under `insert` it falls through to
        # the ordinary on-file refusal below — the PO ruled insert never alters
        # a record already on file.
        if (
            write_mode != "insert"
            and key is not None
            and key in existing
            and import_rules.is_dates_only_row(run.target, mapped)
        ):
            target_row = existing[key]
            try:
                with transaction.atomic():
                    changed = _correct_created(actor, run, target_row, created_day, created_zone)
            except (IntegrityError, DataError) as refusal:
                rejected_at_write += 1
                row.outcome = "rejected"
                row.problem, row.fix_hint = _db_refusal_sentences(refusal, run.target, mapped)
                row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
                target_row.refresh_from_db()
                continue
            if changed:
                created_corrected += 1
            updated += 1
            row.outcome = "loaded" if row.outcome != "flagged" else "flagged"
            row.mapped = {
                **mapped,
                LOAD_RESULT: _generic_load_result_from(
                    run.target,
                    {number_field: getattr(target_row, number_field, None)} if number_field else {},
                    mapped,
                ),
            }
            row.save(update_fields=["outcome", "mapped", "updated_at"])
            continue

        if run.target == TARGET_UNITS:
            # The two references resolve HERE, at load time — the posture
            # `KIND_AREA` set and the reason stage 2 carried them as text.
            premise_id = premises_by_no.get(str(mapped.get("premises_ref") or "").strip().lower())
            if premise_id is None:
                # Stage 3's ERROR rule rejected these, so reaching this line
                # would mean the two disagreed. Refuse rather than write an
                # orphan: a unit with no premises cannot be billed or found.
                raise errors.BizError(
                    errors.BIZ_STATE,
                    br_ref="BR-MET-090",
                    message_key="metering.import.parent_premise_missing",
                    params={
                        "row": row.row_no,
                    },
                )
            record["premises_id"] = premise_id
            # ⚠ **CODE *OR* NAME, THROUGH THE ONE RESOLVER (`DEF-771`).** This
            # read `plan_ids.get(...)` over a code-only index, so a file whose
            # `Plan` column held plan NAMES wrote `rate_plan_id = NULL` on every
            # row and the run reported it as 9,881 rows to review.
            resolved = import_rules.resolve_plan_ref(mapped.get("rate_plan_ref"), plan_index)
            plan_id = resolved["plan_id"] if resolved is not None else None
            record["rate_plan_id"] = plan_id
            if resolved is not None and plan_id is None:
                _tally_unplanned_plan(unplanned_plans, resolved)
                # ⚠ **BR-MET-100, AND THE FLAG IS NOT ENOUGH.** The PO ruled
                # this row LOADS without a plan, having been told the cost in
                # plain English: *"a unit with no plan does not fail — it
                # simply never appears on a bill."* What makes that safe is
                # that it is COUNTED AND FINDABLE, so the count travels to the
                # receipt and the row keeps its `flagged` outcome.
                unplanned += 1

        if key is not None and key in existing and write_mode != "insert":
            target_row = existing[key]
            for field, value in record.items():
                # ⚠ **AN UPDATE NEVER CLEARS THE RECORD'S OWN NUMBER (CR-046).**
                # Under the ruling the identifier column is blank on almost
                # every row, and `_record_from` carries it through — so a
                # straight `setattr` of a blank cell would WIPE a number the
                # series issued, on the one path whose whole purpose is to
                # leave a known record recognisable. Blank means *"I am not
                # telling you"*, never *"set this to nothing"*.
                if field == number_field and not str(value or "").strip():
                    continue
                if field == "custom_data":
                    # `CR-161-BRC10` W3 — the file's custom columns are ADDED to
                    # the answers already held: a file carrying one field must not
                    # wipe the others a clerk typed on a screen. A blank cell is
                    # not in the blob at all, so it clears nothing either.
                    value = {**(target_row.custom_data or {}), **(value or {})}
                setattr(target_row, field, value)
            # ⛔ **THE SAVEPOINT — CR-047 WIDENING TASK 21. SEE THE LONG NOTE
            # ON THE CREATE BRANCH BELOW; IT IS THE SAME MECHANISM.**
            try:
                with transaction.atomic():
                    target_row.save()
                    _audit(
                        actor,
                        f"{run.target}.updated",
                        target_row.pk,
                        run_no=run.run_no,
                        row=row.row_no,
                    )
                    # `DEF-MET-10164` — a Created cell on an ordinary upsert row
                    # corrects the date too, with its own old → new audit row.
                    if created_day and _correct_created(
                        actor, run, target_row, created_day, created_zone
                    ):
                        created_corrected += 1
            except (IntegrityError, DataError) as refusal:
                rejected_at_write += 1
                row.outcome = "rejected"
                row.problem, row.fix_hint = _db_refusal_sentences(refusal, run.target, mapped)
                row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
                # ⚠ **THE IN-MEMORY INSTANCE IS PUT BACK, AND THIS LINE IS NOT
                # TIDINESS.** The `setattr` loop above has already written this
                # row's rejected values onto the object `existing` is holding.
                # The savepoint undid the DATABASE and can do nothing about
                # Python: leave it mutated and any later pass over `existing`
                # — BR-MET-099's `replace` sweep is the one in this function —
                # would save the refused values as a side effect of doing
                # something else entirely.
                target_row.refresh_from_db()
                continue
            updated += 1
            # CR-055 — the row the counters below must ask about. See the
            # comment at `_owner_gap_kind`'s call site: on an UPDATE the file's
            # `record` may carry no `owner_id` while the premises on file
            # already has one, and counting that as ownerless would put an
            # address on an operator's "nobody to charge" list that has
            # somebody to charge.
            written_row = target_row
        elif key is not None and key in existing:
            # ⛔ **PO ruling 2026-08-27 — *"in case of insert - reject it"*.**
            # This used to `continue`, which left the row's outcome untouched
            # and the operator reading a receipt that said nothing about it.
            rejected_existing += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _insert_mode_on_file_sentences(
                run.target, mapped, existing[key]
            )
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue
        else:
            # ⛔ **THE NUMBER IS ISSUED HERE, INSIDE THE WRITE TRANSACTION, AND
            # NEVER READ OFF THE FILE (PO ruling 2026-08-27, widened to all four
            # uploads by CR-046).**
            #
            # The PO's own words about WHEN: *"these decisiona should be taken
            # just before updating teh record in the database"*. Inside the
            # transaction means a rejected row burns no number and a rollback
            # returns the counter — which is the whole reason the dry run only
            # PROJECTS numbers and never allocates them.
            #
            # ⚠ **THE CELL IS POPPED RATHER THAN TRUSTED TO BE EMPTY.** Stage 3
            # already refuses a number that is not on file
            # (`PRM.PREMISE_NO_NOT_ON_FILE` / `UNT.NUMBER_NOT_ON_FILE`) and
            # this branch is only reached when the key matched nothing, so in
            # practice the value IS blank. Popping it is the belt to that
            # braces, and it makes the guarantee STRUCTURAL rather than a
            # promise two files apart (hard-won law 1).
            if number_field:
                record.pop(number_field, None)
                issued = _issue_target_number(actor, run.target, warnings)
                if issued is not None:
                    record[number_field] = issued
                    issued_from_series += 1
                    # ⛔ **THE LAST CHECK BEFORE ANYTHING IS WRITTEN — step 2.13
                    # of the signed unit walkthrough, and it is NOT the series'
                    # own guarantee restated.**
                    #
                    # The series guarantees the number is unique AT ISSUE. This
                    # asserts that THIS PREMISES does not already hold a unit
                    # carrying it — made after the number exists and immediately
                    # before the row is written. It costs one indexed existence
                    # check and it catches what a series alone cannot: a series
                    # renumbered or reset, a number typed by hand on the MET-02
                    # screen, or two runs racing on one address.
                    #
                    # ⚠ **THE COST OF NOT HAVING IT IS NOT A DUPLICATE ROW, IT
                    # IS A WRONG BILL.** A number used twice is a unit two
                    # things can point at, and a meter or an account pointing at
                    # the wrong flat is not a mistake anybody notices until a
                    # bill arrives.
                    _refuse_if_number_taken(run.target, record, number_field, row.row_no)
            # ⛔⛔ **ONE SAVEPOINT PER RECORD — CR-047 WIDENING TASK 21, AND ON
            # THIS PATH THE SAVEPOINT IS MANDATORY RATHER THAN TIDY.**
            #
            # `DEF-2519` was fixed for accounts on 2026-08-29 and the same hole
            # was live here: the generic path writes straight through the ORM
            # with no guard at all, under stage 4's one outer
            # `transaction.atomic()`. What escapes is a unique-index or NOT
            # NULL violation stage 3 does not model, or a race where another
            # user takes the same premise number between the rehearsal and the
            # commit — and any one of them on row 63 of a 9,881-unit migration
            # left **ZERO** units on file.
            #
            # ⚠ **IN POSTGRESQL A FAILED STATEMENT POISONS THE WHOLE
            # TRANSACTION.** After an `IntegrityError` the connection answers
            # *`current transaction is aborted, commands ignored until end of
            # transaction block`* to EVERY subsequent query — so a bare
            # `except IntegrityError: continue` would not merely be untidy, it
            # **cannot work**: the next row's first read would fail and the run
            # would die anyway, one row later and with a worse message. A
            # nested `atomic()` is a SAVEPOINT, and rolling back to it is the
            # only thing that makes the connection usable again. That is the
            # whole reason this shape is what it is; a lane that "simplifies"
            # the savepoint away re-breaks every row after the first bad one.
            #
            # ⚠ **`_refuse_if_number_taken` IS CALLED OUTSIDE THIS BLOCK, ON
            # PURPOSE.** Its own docstring states the posture: *"IT RAISES,
            # WHICH TAKES THE WHOLE TRANSACTION. That is deliberate and it is
            # the safe direction."* It fires when the tenant's series and the
            # table have genuinely come apart, which is true of every row that
            # follows and not of this one — so it stays a run-level abort.
            try:
                with transaction.atomic():
                    fresh = model.objects.create(tenant_id=run.tenant_id, **record)
                    # `DEF-MET-10164` — the old system's Created day, stamped
                    # AFTER the insert because `auto_now_add` overwrites any
                    # value handed to `create`. A blank cell leaves the import
                    # day the insert just stamped (PO: *"Blank → the import
                    # day"*). Inside the savepoint, so a refused row leaves no
                    # half-dated record.
                    created_moment = _created_moment(created_day, created_zone)
                    if created_moment is not None:
                        model.objects.filter(tenant_id=run.tenant_id, pk=fresh.pk).update(
                            created_at=created_moment
                        )
                        fresh.created_at = created_moment
                    # INSIDE the savepoint: an audit row for a record that was
                    # rolled back would be a record of something that did not
                    # happen.
                    _audit(
                        actor,
                        f"{run.target}.created",
                        fresh.pk,
                        run_no=run.run_no,
                        row=row.row_no,
                        created_at=fresh.created_at.isoformat() if fresh.created_at else None,
                    )
            except (IntegrityError, DataError) as refusal:
                # ⚠ **THESE TWO CLASSES AND NOT `Exception`** — the accounts
                # loader's judgment, in the vocabulary this path fails in.
                # `IntegrityError` and `DataError` are the database saying
                # *"this ROW's data is wrong"*; `OperationalError`,
                # `InterfaceError` and anything unforeseen are the server or a
                # bug, they will refuse every row that follows in the same way,
                # and a run reporting *"9,881 failed"* over a dropped
                # connection would be a data-quality report about an outage.
                rejected_at_write += 1
                row.outcome = "rejected"
                row.problem, row.fix_hint = _db_refusal_sentences(refusal, run.target, mapped)
                row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
                continue
            existing[key] = fresh if key is not None else existing.get(key)
            created += 1
            written_row = fresh
        if number_field:
            written_no = record.get(number_field)
            if written_no:
                numbers_written.append(str(written_no))
        if run.target == TARGET_PREMISES:
            if not (record.get("services_available") or []):
                no_services += 1
            # ⛔ **CR-055 TASK 2 — TWO KINDS OF OWNERLESS, COUNTED APART.**
            #
            # This used to be one test with both halves ANDed together, and
            # the comment that stood here said why: *"a row with no typed
            # `owner_id` but a name in `owner_manager` is WAITING FOR MATCHING
            # — a different state with a different worklist"*. That is still
            # true of an UNKNOWN name, and it is what `_owner_gap_kind` keeps
            # out of both counters.
            #
            # What the 2026-08-31 ruling adds is a THIRD state that used never
            # to reach this line at all, because stage 3 rejected it: a name
            # that matches two or more parties. It has a name in
            # `owner_manager` like the unknown case, and it is ownerless like
            # the blank case — and it is the one an operator can settle from
            # the screen, because the file already knows which parties it
            # looked like.
            # ⚠ **THE ROW AS WRITTEN, NOT THE FILE'S `record` — AND ONLY THE
            # UPSERT PATH SHOWS WHY.** On an INSERT the two agree. On an
            # UPDATE they do not: `_resolve_owner_ref` puts no `owner_id` in
            # `record` for an ambiguous name, and `setattr` therefore never
            # touches the premises' existing owner — correctly, because the
            # import may not clear an owner a person chose. Reading `record`
            # there would report an address that HAS an owner as having none.
            kind = (
                _owner_gap_kind(written_row, mapped, owner_near)
                if written_row is not None
                else None
            )
            if kind == OWNER_GAP_BLANK:
                no_owner_blank += 1
            elif kind == OWNER_GAP_AMBIGUOUS:
                no_owner_ambiguous += 1
                _tally_owner_ambiguity(owner_ambiguities, mapped, owner_near)
            # ⛔ **CR-058 W3 · BR-MET-1030 — THE OWNER'S ACCOUNT AND CUSTOMER #,
            # WHERE THE ROW EARNS THEM.**
            #
            # ⚠ **THROUGH THE ONE DOOR CUSTOMERS OWNS, AND NEVER AROUND IT**
            # (B1/B2 §2). `ensure_master_account_for_premises` reaches
            # `customers.create_master_account` through the seam — the same door
            # `ensure_owner_master_account` and New Connect walk through — so
            # `BR-CUS-017`'s family, `BR-CUS-1011` and the whole customer
            # resolution apply to an imported owner exactly as to a hand-typed
            # one. **This module writes no account and matches no customer.**
            #
            # ⚠ **ONE SAVEPOINT, AND IT IS THE SAME LAW AS THE ROW WRITE ABOVE
            # (CLAUDE.md law 14).** In PostgreSQL a failed statement poisons the
            # whole transaction: without a nested `atomic()` a single refused
            # owner account would make every later query in this run raise
            # `InFailedSqlTransaction`, and the premises rows already written
            # would be lost at COMMIT. **The suite runs on SQLite, which has no
            # aborted-transaction state, so the version without this savepoint
            # passes every test and destroys a real migration.** A lane that
            # "simplifies" it away re-breaks every row after the first refusal.
            #
            # ⚠ **THE PREMISES IS NOT ROLLED BACK WHEN THE ACCOUNT IS REFUSED.**
            # The address is a real address whether or not anybody can be billed
            # for it — that is the 2026-08-27 ruling and it is not reversed
            # here. The refusal is COUNTED and NAMED on the receipt instead.
            if written_row is not None:
                verdict = owner_account_verdict(mapped)
                if verdict["verdict"] == OWNER_ACCOUNT_ELIGIBLE:
                    # ⚠ **IMPORTED HERE, NOT AT MODULE TOP, AND IT IS A CYCLE
                    # AND NOT A STYLE CHOICE.** `premises_owners` imports
                    # `apps.metering.services`, which imports `read_rejects`,
                    # which imports THIS module — so a top-level import fails at
                    # startup with a half-built module rather than a clear
                    # error. The lazy import is the shape every cross-file
                    # metering call in this package already takes.
                    from apps.metering import premises_owners

                    # ⛔ **THE PARTY, WHERE THE ROW STATES A CATEGORY — PO
                    # RULING 2026-09-19.** Until today a row naming an owner
                    # who was NOT already on file got a master account with
                    # `premises.owner_id` NULL and no `premises_owners` row:
                    # an account attached to a building with nobody named on
                    # it. `ensure_master_account_for_premises` has two
                    # branches and the one that writes the link is the one a
                    # FIRST MIGRATION can never take, because on a first
                    # upload nobody is on file.
                    #
                    # ⚠ **THIS IS NOT A THIRD PATH.** It creates the party
                    # through `match_premises_owner` — the same door a person
                    # uses on `PRM-04`, which takes the CALLER'S category,
                    # defaults the name, links `premises.owner_id`, audits
                    # both writes and deliberately leaves `owner_manager`
                    # alone as `BR-MET-151` clause 4 provenance. The premises
                    # then HAS a typed owner, so the call below takes its
                    # already-on-file branch unchanged and
                    # `ensure_owner_master_account` writes
                    # `premises_owners.master_account_id`.
                    #
                    # ⚠ **A BLANK CATEGORY IS NOT AN ERROR AND MUST NOT
                    # BECOME ONE.** No category means exactly today's
                    # behaviour — the account is created, the party is left
                    # for `PRM-04` — counted below and flagged at rehearsal
                    # by `PRM.OWNER_CATEGORY_MISSING`. Inventing one would be
                    # reading a category off a name, which `BR-MET-151`
                    # clause 3 forbids in as many words.
                    #
                    # ⚠ **ONLY ON THE ELIGIBLE PATH, DELIBERATELY.** A row
                    # with a name and a category but NO identifier creates
                    # nothing, exactly as the PO ruled on 2026-09-01
                    # (*"otherwise dont create anything"*). The 2026-09-19
                    # ruling is about the master account not being generated;
                    # it does not widen what earns one.
                    #
                    # ⚠ **ITS OWN SAVEPOINT (law 14).** A refused category
                    # — unknown code, retired code, a name already taken —
                    # raises, and on PostgreSQL that poisons the transaction
                    # unless it is rolled back to a savepoint. The premises
                    # and the account still stand: the party is the part that
                    # did not happen, and it is counted rather than hidden.
                    if verdict.get("category") and not getattr(
                        written_row, "owner_id", None
                    ):
                        # ⛔ `DEF-MET-8104` — `.__wrapped__`, as DEF-2515 ruled
                        # for the customers writer: over the 200-row bar this
                        # runs as `_JobActor` (no role, by design) and the
                        # guard could only refuse — and the `except` below
                        # counted that as an ordinary owner refusal. The role
                        # was checked at the door (`load`, BR-MET-035). G140.
                        try:
                            with transaction.atomic():
                                premises_owners.match_premises_owner.__wrapped__(
                                    actor,
                                    written_row.pk,
                                    {
                                        "category": verdict["category"],
                                        "name": owner_customer_block(mapped, verdict)[
                                            "display_name"
                                        ],
                                    },
                                )
                            owner_parties_created += 1
                            written_row.refresh_from_db(fields=["owner_id"])
                        except errors.ApiError as refusal:
                            owner_party_refused += 1
                            owner_party_refusals.append(
                                {
                                    "row": row.row_no,
                                    "row_label": _generic_row_label(run.target, mapped),
                                    "message_key": getattr(refusal, "message_key", None),
                                }
                            )
                    elif not getattr(written_row, "owner_id", None):
                        # ⚠ **TWO OUTCOMES, NOT ONE.** An UNRECOGNISED category
                        # is counted as a refusal with the reason the tenant's
                        # own lookup gives, because the operator DID say
                        # something and telling them they said nothing is the
                        # receipt contradicting their file. A truly blank cell
                        # is the decision nobody has taken.
                        if verdict.get("category_raw"):
                            owner_party_refused += 1
                            owner_party_refusals.append(
                                {
                                    "row": row.row_no,
                                    "row_label": _generic_row_label(run.target, mapped),
                                    "message_key": "metering.premises_owner.category_unknown",
                                }
                            )
                        else:
                            owner_no_category += 1

                    try:
                        with transaction.atomic():
                            result = premises_owners.ensure_master_account_for_premises.__wrapped__(
                                actor,
                                written_row.pk,
                                {
                                    "account_type": verdict["account_type"],
                                    "opened_at": str(seams.tenant_today()),
                                    "customer": owner_customer_block(mapped, verdict),
                                    # ⚠ **`DEF-MET-5803` — PASSED HERE OR THE
                                    # COLUMN IS DEAD UI (hard-won law 2).** A
                                    # column offered on the picker, written to
                                    # the sample CSV and read by nothing
                                    # renders, tests green and does not exist.
                                    # `ensure_master_account_for_premises`
                                    # already forwards `contact` verbatim and
                                    # `create_master_account` already validates
                                    # it — no seam and no module boundary moves
                                    # for this.
                                    "contact": owner_contact_block(mapped, verdict),
                                },
                            )
                    except errors.ApiError as refusal:
                        owner_account_refused += 1
                        owner_account_refusals.append(
                            {
                                "row": row.row_no,
                                # The operator's own cell, never a uuid — the
                                # person reading this typed `2205 Cedar Ln`.
                                "row_label": _generic_row_label(run.target, mapped),
                                "message_key": getattr(refusal, "message_key", None),
                            }
                        )
                    else:
                        if result.get("created"):
                            owner_accounts_created += 1
                elif verdict["verdict"] == OWNER_ACCOUNT_AWAITING_IDENTITY:
                    owner_awaiting_identity += 1
                elif verdict["verdict"] == OWNER_ACCOUNT_NO_ACCOUNT_TYPE:
                    owner_no_account_type += 1
                elif verdict["verdict"] == OWNER_ACCOUNT_IDENTITY_MISMATCH:
                    owner_identity_mismatch += 1
                elif verdict["verdict"] == OWNER_ACCOUNT_NO_OWNER:
                    # ⚠ **THE BRANCH THAT WAS MISSING.** Every other verdict
                    # had one; this row — an address whose Owner cell names
                    # nobody — fell off the end of the chain and was counted
                    # nowhere. It is owed work like the other four: the
                    # address loaded and has nobody to charge.
                    owner_no_owner_named += 1
        row.outcome = "loaded" if row.outcome != "flagged" else "flagged"
        # ⛔ **WHAT THIS ROW ACTUALLY WROTE, RECORDED AS IT IS WRITTEN (CR-047
        # WIDENING TASK 22).** The successes file takes `receipt()`'s posture —
        # *"every figure is what the run RECORDED at the moment it loaded"* —
        # and on these two targets it has no choice either: under the PO's
        # ruling of 2026-08-27 the premise and unit numbers come from the
        # tenant's series, so they are NOT on the operator's file and cannot be
        # read back out of `mapped`. `record` is what was written, so `record`
        # is what is recorded.
        row.mapped = {
            **mapped,
            LOAD_RESULT: _generic_load_result_from(run.target, record, mapped),
        }
        row.save(update_fields=["outcome", "mapped", "updated_at"])

    # ── BR-MET-099 — retire what the file no longer carries. NEVER delete ────
    # ⛔ **KEPT AND UNREACHABLE — CR-042. DO NOT DELETE THIS BRANCH.**
    # `replace` is refused at both entry points (`_refuse_withdrawn_mode`), so
    # nothing can arrive here with it. That makes this dead code and it is dead
    # ON PURPOSE: it implements BR-MET-099, a CONFIRMED PO ruling of 2026-08-21
    # with its own worked figure, and **OQ-580** asks whether the behaviour
    # should come back under a different door. A lane that tidies it away is
    # destroying a signed capability that one ruling would restore.
    # `test_cr042__br_met_099s_behaviour_is_kept_not_deleted` fails if you do.
    deactivated = skipped_occupied = 0
    if write_mode == "replace":
        for key, target_row in existing.items():
            if key in seen:
                continue
            if _is_occupied(run, target_row):
                skipped_occupied += 1
                continue
            target_row.status = "inactive"
            target_row.save(update_fields=["status", "updated_at"])
            deactivated += 1
            _audit(
                actor,
                f"{run.target}.deactivated_by_replace",
                target_row.pk,
                run_no=run.run_no,
                reason="not in the file this run replaced the batch with",
            )

    # DEF-577 — before the receipt, and inside this transaction: a run that
    # rolls back must not leave the counter moved for numbers it did not write.
    _catch_up_target_series(actor, run.target, numbers_written)

    point = None
    if bool(data.get("create_rollback_point", True)):
        point = models.RollbackPoint.objects.create(
            tenant_id=run.tenant_id,
            point_no=_allocate_point_no(),
            run=run,
            expires_at=timezone.now() + timedelta(days=ROLLBACK_DAYS),
            status="available",
        )

    run.write_mode = write_mode
    run.counts = {
        **(run.counts or {}),
        "created": created,
        "updated": updated,
        # ⛔ CR-046 C2/C3 — the PO's own word for these rows, and the count the
        # rehearsal promised. `skipped_existing` is served as 0 rather than
        # dropped so one receipt panel still renders every target.
        "skipped_existing": 0,
        "rejected_existing": rejected_existing,
        # ⛔ CR-047 WIDENING task 21 — see the counter's own note above the
        # loop. `receipt()` already serves this key for every target.
        "rejected_at_write": rejected_at_write,
        # `DEF-MET-10164` — records whose Created date this run moved (each one
        # has its own old → new audit row).
        "created_dates_corrected": created_corrected,
        "numbers_issued_from_series": issued_from_series,
        "numbering_warnings": [dict(entry) for entry in warnings],
        "premises_with_no_services": no_services,
        # ⛔ CR-058 W3 · BR-MET-1030 — task 12's two sentences, as numbers.
        # 0 on every other target and on every run loaded before today, which
        # is the honest reading of *"the run did not say"*.
        "premises_owner_accounts_created": owner_accounts_created,
        "premises_owner_awaiting_identity": owner_awaiting_identity,
        "premises_owner_no_account_type": owner_no_account_type,
        "premises_owner_identity_mismatch": owner_identity_mismatch,
        "premises_owner_account_refused": owner_account_refused,
        # The count alone cannot be acted on (DEF-771 clause 3): WHICH rows, by
        # the operator's own cell.
        "premises_owner_account_refusals": owner_account_refusals[:50],
        # ⛔ **PO RULING 2026-09-19 — THE OWNER RECORD, COUNTED APART FROM THE
        # ACCOUNT.** The reported defect was that these two were the same
        # number and they are not: an account can exist on an address with
        # nobody named on it, which is what every row of a first migration
        # produced. 0 on every other target and on every run loaded before
        # today, which is the honest reading of *"the run did not say"*.
        "premises_owner_parties_created": owner_parties_created,
        "premises_owner_no_category": owner_no_category,
        "premises_owner_party_refused": owner_party_refused,
        "premises_owner_party_refusals": owner_party_refusals[:50],
        # ⛔ **THE FIFTH VERDICT (PO 2026-09-19, *"this is correct"*).** Rows
        # whose Owner cell names nobody. It had no counter at all, so four
        # owner figures printed and this one could not.
        "premises_owner_no_owner_named": owner_no_owner_named,
        # ⛔ **CR-055 — THE TOTAL IS THE SUM, AND THE TWO HALVES TRAVEL BESIDE
        # IT.** `premises_with_no_owner` keeps meaning exactly what it has
        # always meant — addresses that landed with nobody to charge — and it
        # now includes the ambiguous ones, which is the whole of the ruling.
        # The two component keys are NEW, so a run loaded before today carries
        # neither: a reader must draw the split only when it is present, never
        # infer that an old run's total was all blanks.
        "premises_with_no_owner": no_owner_blank + no_owner_ambiguous,
        "premises_owner_blank": no_owner_blank,
        "premises_owner_ambiguous": no_owner_ambiguous,
        "premises_owner_ambiguous_names": _owner_ambiguity_list(owner_ambiguities),
        "deactivated": deactivated,
        "skipped_occupied": skipped_occupied,
        "unplanned_units": unplanned,
        # DEF-771 clause 3 — the count alone cannot be reviewed; this says WHICH
        # plan those rows named and what to do about it.
        "unplanned_plans": _unplanned_plan_list(unplanned_plans),
    }
    run.status = "loaded"
    run.finished_at = timezone.now()
    run.save(update_fields=["write_mode", "counts", "status", "finished_at", "updated_at"])
    _audit(
        actor,
        "import_run.loaded",
        run.id,
        run_no=run.run_no,
        write_mode=write_mode,
        created=created,
        updated=updated,
        rejected_at_write=rejected_at_write,
        deactivated=deactivated,
        unplanned_units=unplanned,
        rollback_point=getattr(point, "point_no", None),
    )
    return receipt(run)


# ── the assets targets' load half (CR-028 AST-W3 · B16 §4.7a) ───────────────

#: Which asset TYPE a target creates. Devices carry theirs in the file
#: (DEVICE_TYPE, resolved at stage 2), so they have no entry here.
#: The word a sentence about one of these rows uses. Kept beside the type map
#: so the two cannot drift; `_insert_mode_on_file_sentences` is the only reader.
ASSET_NOUN_BY_TARGET: dict[str, str] = {
    TARGET_ASSETS_METERS: "meter",
    TARGET_ASSETS_SUBMETERS: "sub-meter",
    TARGET_ASSETS_DEVICES: "device",
}

ASSET_TYPE_BY_TARGET: dict[str, str] = {
    TARGET_ASSETS_METERS: "meter",
    TARGET_ASSETS_SUBMETERS: "sub_meter",
}


def multiplier_or_default(raw: Any) -> str:
    """B16 §4.7b's `W → default ×1`, performed: a positive whole number is
    kept, anything else becomes "1". THE SAME predicate the warning evaluator
    uses (`_eval_multiplier_positive_int`), so the flag and the write cannot
    disagree about which rows were defaulted."""
    token = str(raw or "").strip()
    return token if token.isdigit() and int(token) > 0 else "1"


def _months_after(iso_date: str, months: int) -> str:
    """install date + N months, clamped to the month's length — the devices
    target's `derive next test from the install date` action."""
    start = date.fromisoformat(iso_date)
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    lengths = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return date(year, month, min(start.day, lengths[month - 1])).isoformat()


def _asset_payload_from(target: str, mapped: dict[str, Any]) -> dict[str, Any]:
    """One judged row → the payload `apps.assets.services.create_from_import`
    validates and writes. Nothing is invented: every value is the row's own,
    plus the two ruled defaults (×1 multiplier · derived next test), each of
    which stage 3 flagged out loud on the rows it applies to."""
    payload: dict[str, Any] = {
        # ⚠ **`asset_no` IS STILL CARRIED HERE AND IS POPPED BEFORE A CREATE**
        # (`_load_assets_rows`). It is needed on the UPDATE path — it is the
        # row the operator named — and it must never reach a create, because
        # under the PO ruling of 2026-08-27 a new asset's number comes from the
        # tenant's series and from nowhere else.
        "asset_no": mapped.get("asset_no"),
        # BR-AST-049 — the utility's OWN legacy reference, and BR-TEN-035's
        # protection made real: `serial_no` is the manufacturer's number and
        # is written exactly as the file gives it.
        "external_ref": mapped.get("external_ref"),
        "serial_no": mapped.get("serial_no"),
        "manufacturer": mapped.get("manufacturer"),
        "model": mapped.get("model"),
        "install_date": mapped.get("install_date"),
        "warranty_end": mapped.get("warranty_end"),
        "certification_due": mapped.get("certification_due"),
        "supplier": mapped.get("supplier"),
        "purchase_cost": mapped.get("purchase_cost"),
        # ⛔ PLAN U6 (PO 2026-09-30) — every sheet's own unit of measure, the
        # code stage 2 resolved and `AST.UOM_FOR_SERVICE` judged. Absent when
        # blank, so a create takes the service's default unit
        # (`_create_asset_inner` → `seams.service_default_uom`) and an update
        # leaves the stored one alone.
        "unit": mapped.get("unit"),
        "service": mapped.get("service"),
        # `CR-161-BRC10` W3 · `DEF-AST-9171` — the sheet's custom-field columns,
        # already normalised by `_judge_custom_cells`. Absent (None) when no
        # cell was filled, so an update never touches the stored answers; given,
        # `_validate_asset` MERGES it into them.
        "custom_data": mapped.get("custom_data") or None,
    }
    if target in ASSET_TYPE_BY_TARGET:
        payload["type"] = ASSET_TYPE_BY_TARGET[target]
        payload["meter_type"] = mapped.get("meter_type")
        payload["read_method"] = mapped.get("read_method")
        payload["register_digits"] = mapped.get("register_digits")
        if str(mapped.get("multiplier") or "").strip():
            payload["multiplier"] = multiplier_or_default(mapped.get("multiplier"))
    if target == TARGET_ASSETS_METERS:
        # Plan U6 — `net_metering` is a yes/no cell; `None` (blank) is left
        # out below, so a blank never switches net metering OFF on an update.
        payload["net_metering"] = mapped.get("net_metering")
    if target == TARGET_ASSETS_METERS:
        # BR-AST-500 / BR-MET-530 — the size the file named, RESOLVED to a
        # ratified code by stage 2 and already judged by stage 3. A row whose
        # cell named something unknown never reaches here: `AST.SIZE_CLASS_IN_
        # LOOKUP` rejects it, so the only two values this line can carry are a
        # code the tenant has, or None. The `is not None` filter at the bottom
        # of this function is what makes a blank cell mean "no size recorded"
        # rather than an explicit clear — which matters on the UPDATE path,
        # where a blank column would otherwise wipe a size somebody typed.
        payload["size_class"] = mapped.get("size_class")
    if target == TARGET_ASSETS_SUBMETERS:
        payload["parent_asset_no"] = mapped.get("parent_asset_no")
        payload["allocation_share_pct"] = mapped.get("allocation_share_pct")
        # Plan U6 — the method canonicalised to its stored CODE by the one
        # resolver stage 3 judged with (DEF-544): `Split equally` → `equal`.
        payload["allocation_rule"] = import_rules.allocation_rule_code(
            mapped.get("allocation_rule")
        )
        payload["loss_tolerance_pct"] = mapped.get("loss_tolerance_pct")
    if target == TARGET_ASSETS_DEVICES:
        payload["type"] = mapped.get("type")
        # ⛔ Plan U6 (PO ruling 2026-09-30) — the device's size and the meter it
        # sits behind. The SERVICE rides the common block above: with a seat,
        # `_create_asset_inner` attaches the device to that service's point on
        # the unit (`ensure_service_point`, plan U5), which is what makes
        # `billable_asset_count` count it.
        payload["size_class"] = mapped.get("size_class")
        payload["parent_asset_no"] = mapped.get("parent_asset_no")
        payload["test_interval_months"] = mapped.get("test_interval_months")
        payload["export_capacity_kw"] = mapped.get("export_capacity_kw")
        if (
            not payload.get("certification_due")
            and mapped.get("test_interval_months")
            and mapped.get("install_date")
        ):
            # AST.NEXT_TEST_DERIVABLE's DEFAULT_TO, performed where stage 3
            # said it would be.
            payload["certification_due"] = _months_after(
                str(mapped["install_date"]), int(mapped["test_interval_months"])
            )
    return {key: value for key, value in payload.items() if value is not None}


#: ⛔ **HOW FAR BACK A PROVISIONAL CHANGEOVER DATE SITS, AND WHY BACKWARDS**
#: (PO ruling 2026-08-27). 90 days is far enough that a migrated 60-day arrear
#: still reads as a 60-day arrear rather than as something in the future, and
#: near enough that the provisional books are recognisable while somebody finds
#: the real date. **The direction is the decision, not the number:** a FUTURE
#: date would date every opening balance in the future — nothing overdue, no
#: ageing, no reminder ever firing — and would be wrong in the utility's
#: favour, which is the direction nobody checks.
PROVISIONAL_CHANGEOVER_DAYS = 90


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-MET-035")
def confirm_changeover_date(actor: Any, run_id: Any, changeover_on: Any) -> dict[str, Any]:
    """⛔ **THE ACTION THAT POSTS A HELD OPENING BATCH** (PO ruling 2026-08-27).

    The accounts loaded without a changeover date; their opening balances are
    written as buckets but **no journal entry exists**, so the date is still
    provisional. This re-dates the buckets to the real date and hands the batch
    to the ledger, once.

    ⚠ **RE-DATING A HELD BUCKET IS LAWFUL AND RE-DATING A POSTED ONE IS NOT,
    AND THE DIFFERENCE IS THE WHOLE DESIGN.** `AccountOpeningBucket`'s docstring
    says the rows are append-only, and gives the reason in as many words: *"a
    wrong opening balance is corrected by a J6 adjustment, **because the moment
    US-CUS-022 posts, an immutable journal entry exists against these
    numbers**"*. While the batch is HELD no such entry exists — which is
    precisely what makes the PO's *"we can always change this date later"* true,
    and precisely why the hold cannot be simplified away.

    ⚠ **ONCE ONLY.** A second call finds nothing held and returns the receipt
    unchanged, the same idempotency posture stage 4 takes (hard rule 6): a
    second posting would double a migration's AR.

    ⚠ **THE DATE IS THE OPERATOR'S AND IS NEVER READ OFF A CLOCK** (BR-TEN-043).
    *The last day your old system was in charge of the money* — that is what the
    screen must ask for, in those words. It is not the go-live date and not the
    day Commit was clicked: a customer 45 days overdue on 31 July would read as
    14 days overdue if the import's own day were used, and every ageing band,
    reminder, late fee and collections decision would be wrong by the gap.
    """
    run = _run(run_id)
    if run.target != TARGET_ACCOUNTS:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-049",
            message_key="metering.import.changeover_not_accounts",
            params={"target": run.target},
        )
    counts = run.counts or {}
    if not int(counts.get("opening_held") or 0):
        # Nothing is waiting. Returning the receipt rather than refusing is the
        # same idempotency posture stage 4 takes: a second click must not be an
        # error, and it must not post twice either.
        return receipt(run)
    parsed = changeover_on if isinstance(changeover_on, date) else None
    if parsed is None:
        try:
            parsed = date.fromisoformat(str(changeover_on)[:10])
        except (TypeError, ValueError):
            _refuse(errors.VAL_FORMAT, message_key="customers.account.date_invalid")
    if parsed > seams.tenant_today():
        # A future changeover date puts every opening balance in the future —
        # nothing overdue, no ageing, no reminder ever firing. Refused by name
        # rather than accepted and silently wrong in the utility's favour.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-049",
            message_key="metering.import.changeover_in_future",
            params={"given": parsed.isoformat(), "today": str(seams.tenant_today())},
        )
    with transaction.atomic():
        posted = seams.confirm_opening_changeover(
            actor=actor,
            import_run_id=run.id,
            changeover_on=parsed,
            # DEF-1713 — the deposit half of the held batch. `accounts` carries
            # no import-run column, so the set of accounts this run created is
            # OUR fact and is handed over rather than inferred: rebuilding it
            # from the bucket rows would silently drop every account that holds
            # a deposit and owes nothing.
            deposit_account_ids=[
                str(value)
                for value in models.ImportRunRow.objects.filter(tenant_id=run.tenant_id, run=run)
                .exclude(created_record_id=None)
                .values_list("created_record_id", flat=True)
            ],
        )
        if posted is None:
            # Customers could not answer. REFUSE rather than mark a batch
            # posted whose journal entries do not exist (the DEF-075 lesson).
            _refuse_accounts_unwired()
        run.refresh_from_db()
        run.counts = {
            **(run.counts or {}),
            "opening_held": 0,
            "changeover_provisional": None,
            "changeover_on": parsed.isoformat(),
            "opening_ar": posted.get("ar_debits", "0"),
            "opening_deposits": posted.get("deposit_credits", "0"),
        }
        run.save(update_fields=["counts", "updated_at"])
        _audit(
            actor,
            "import_run.changeover_confirmed",
            run.id,
            run_no=run.run_no,
            changeover_on=parsed.isoformat(),
            accounts=posted.get("posted"),
        )
    return receipt(run)


def _accounts_cutover(run: models.ImportRun) -> date | None:
    """The batch's cutover date — ONE per run, and the opening JE's entry date.

    ⚠ **THERE IS NO DEFAULT, AND "today" WOULD BE A MONEY ERROR.** BR-CUS-049
    dates the opening entries *at cutover*; BR-TEN-043 says the caller names the
    business event's date and this kernel never reads a clock on their behalf.
    Falling back to today would date a utility's migrated books on the day
    somebody happened to run the import rather than the day the balances were
    struck — every ageing band wrong by the gap between them, silently, and
    uncorrectable by edit once the entries post (hard rule 4).

    So it returns None when unset and the caller REFUSES.
    """
    spec = run.mapping_spec or {}
    raw = (spec.get("options") or {}).get("cutover_on")
    if not raw:
        return None
    return date.fromisoformat(str(raw)[:10])


def _refuse_accounts_no_cutover() -> None:
    raise errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-CUS-049",
        message_key="customers.import.cutover_required",
    )


def _account_update_from(mapped: dict[str, Any]) -> dict[str, Any]:
    """⛔ **CR-046 C4 — WHAT A RE-RUN MAY CHANGE ON AN ACCOUNT ALREADY ON FILE.**

    Built from `_account_payload_from` by SUBTRACTION rather than written out
    again, so a column added to the create payload cannot silently go missing
    here — and every exclusion is named where it is taken.

    ⚠ **A KEY WHOSE CELL IS BLANK IS DROPPED, NOT SENT AS `None`.** `partial=True`
    validation acts on PRESENCE, so sending `{"autopay": None}` would clear a
    flag the file simply did not mention. Blank means *"I am not telling you"*,
    never *"set this to nothing"* — the same rule the premises/units update
    branch takes for the number column, for the same reason.
    """
    payload = _account_payload_from(mapped)
    return {
        field: value
        for field, value in payload.items()
        # `account_type` and `contact`/`addresses` are create-only
        # (`IMPORT_UPDATE_FIELDS`); the four `ob_*` buckets and the deposit
        # never enter this payload at all — hard rule 4 forbids restating a
        # posted opening position from a spreadsheet.
        if field in _IMPORT_UPDATABLE_ACCOUNT_FIELDS and value not in (None, "")
    }


#: The customers-side `IMPORT_UPDATE_FIELDS`, named here so this module can
#: filter without importing another module's service constants across the
#: boundary. ⚠ A test asserts the two agree, because two lists of field names
#: in two modules is exactly how a column comes to be updatable on one side and
#: refused on the other.
_IMPORT_UPDATABLE_ACCOUNT_FIELDS: frozenset[str] = frozenset(
    {
        "account_subtype",
        "status",
        "opened_at",
        "closed_at",
        "autopay",
        "tax_exempt",
        "tax_exempt_ref",
        "tax_exempt_expires",
        "bad_address",
        "preferred_language",
        "external_ref",
        "custom_data",
    }
)


def _account_payload_from(mapped: dict[str, Any]) -> dict[str, Any]:
    """One judged row → the payload `customers.services._open_account`
    validates. Nothing is invented; every value is the row's own.

    The four `ob_*` columns are deliberately ABSENT: they are not account
    fields, they become `account_opening_buckets` rows, and passing them here
    would push them at a validator that would rightly refuse them."""
    payload: dict[str, Any] = {
        "account_type": mapped.get("account_type"),
        "account_subtype": mapped.get("account_subtype"),
        "status": mapped.get("status"),
        "opened_at": mapped.get("opened_at"),
        "closed_at": mapped.get("closed_at"),
        "autopay": mapped.get("autopay"),
        "tax_exempt": mapped.get("tax_exempt"),
        "tax_exempt_ref": mapped.get("tax_exempt_ref"),
        "tax_exempt_expires": mapped.get("tax_exempt_expires"),
        "bad_address": mapped.get("bad_address"),
        "preferred_language": mapped.get("preferred_language"),
        "deposit_on_file": mapped.get("deposit_on_file"),
        # US-CUS-023 — the ORIGINAL receipt date. Interest accrues from it
        # (BR-CUS-050/057), so importing the deposit without its date starts the
        # clock at cutover and quietly under-pays every migrated customer.
        "deposit_received_on": mapped.get("deposit_received_on"),
        # ⛔ **`external_ref` IS PRESENT SINCE 2026-08-27, AND ITS ABSENCE WAS
        # `DEF-1660`.** This comment used to read *"deliberately ABSENT: it is
        # a CUSTOMER field (BR-CUS-054's legacy id), not an account one, and
        # `create_from_import` hands it to `link_customer` instead"* — and the
        # first half was right about `customer_ref` and wrong about this
        # column. `link_customer` is handed `mapped["customer_ref"]`, never
        # this, so the value was mapped, reported `Matched` at stage 2, and
        # written nowhere at all.
        #
        # `accounts.external_ref` (BR-CUS-172, customers/0033) is the ACCOUNT's
        # own legacy id and is a different fact from the CUSTOMER's: one
        # landlord is one customer row with one `customers.external_ref` and
        # fourteen accounts with fourteen of these. Under CR-046 it is also the
        # MATCH KEY a corrected re-run needs, because `account_no` is blank on
        # every row of a first migration.
        "external_ref": mapped.get("external_ref"),
        # `DEF-MET-9239` — the sheet's custom-field columns, already judged and
        # normalised by `_judge_custom_cells`. `None` when no cell was filled,
        # so `_account_update_from` drops it and an update never touches the
        # stored answers; given, `customers.update_from_import` MERGES it.
        "custom_data": mapped.get("custom_data") or None,
        # ── ⚠ **`DEF-1661` IS NOT VISIBLE FROM THIS FILE, AND THAT IS WHAT
        # MADE IT SURVIVE THREE MONTHS.** `closed_at`, `bad_address`,
        # `deposit_on_file` and `deposit_received_on` are all above and always
        # were; `IMPORT_ACCOUNT_FIELDS` accepts all four; and
        # `customers._validate_account` had a branch for none of them, so
        # `_reject_unknown` waved them through and nothing turned them into
        # column values. **Every check on this side passes** — the payload is
        # complete, the vocabulary is correct, the seam returns a real account.
        # The fix is in `customers/services.py` where the drop happened; this
        # note is here because this is the file a reader arrives at first.
    }
    contact = {
        "full_name": mapped.get("customer_name"),
        "email": mapped.get("email"),
        "phone": mapped.get("phone"),
    }
    if any(value for value in contact.values()):
        payload["contact"] = {k: v for k, v in contact.items() if v}
    mailing = {
        "kind": "mailing",
        "line1": mapped.get("mailing_line1"),
        "city": mapped.get("mailing_city"),
        "state": mapped.get("mailing_state"),
        "postal_code": mapped.get("mailing_postal_code"),
    }
    if mailing["line1"]:
        payload["addresses"] = [{k: v for k, v in mailing.items() if v}]
    return {key: value for key, value in payload.items() if value not in (None, "")}


#: ⛔ **CR-058 W7 · BR-CUS-1041 — WHY THIS ROW LOADED NOTHING, IN THE
#: OPERATOR'S OWN WORDS.** The same posture `_WRITE_REFUSAL_SENTENCES` takes:
#: two short sentences, no rule id, no internal code, and the operator's own
#: cell rather than a uuid (B14 rules 31 and 32).
#:
#: ⚠ **THE WORDING FOLLOWS THE TEST**, which is `identity_match`'s own rule for
#: the same fact: telling a business it needs a driving licence sends somebody
#: to find a document that does not exist.
def _identity_refusal_sentences(verdict: dict[str, Any]) -> tuple[str, str]:
    name = verdict.get("name") or "This row"
    if verdict["verdict"] == ACCOUNT_IDENTITY_NO_NAME:
        return (
            "This row does not say who the account is for.",
            "Fill in the customer name, and one way to identify them — a "
            "Social Security number, a driving licence or a phone for a "
            "person, or a Tax ID for a company.",
        )
    if verdict["verdict"] == ACCOUNT_IDENTITY_AWAITING:
        return (
            f"{name} has a name and no way to identify them.",
            "Add one of a Social Security number, a driving licence or a "
            "phone for a person, or a Tax ID for a company, and upload again. "
            "Nothing is created for this row until then.",
        )
    if verdict.get("reason") == "kind_not_stated":
        return (
            f"{name} has an identifier and the row does not say who it belongs to.",
            "Fill in whether this customer is a person or a company. A person "
            "is known by a Social Security number, a driving licence or a "
            "phone; a company by its Tax ID, and the two are never "
            "interchangeable.",
        )
    return (
        f"{name} is a {verdict.get('kind')}, and this identifier belongs to the other kind.",
        "A person is identified by a Social Security number, a driving licence "
        "or a phone. A company is identified by its Tax ID. Move the value "
        "into the right column, or correct the kind.",
    )


def _refuse_accounts_unwired() -> None:  # pragma: no cover — customers ships in-tree
    """The seam contract's honest failure. A load that cannot reach customers'
    writer REFUSES rather than writing half a file — and for accounts the stakes
    are higher than for assets: half a migration is a utility whose receivables
    are partly in the new system and partly in the old, with no way to tell
    which rows are which."""
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-MET-096",
        message_key="metering.import.accounts_unwired",
    )


# ═══════════════════════════════════════════════════════════════════════════
# CR-047 · DEF-2519 — A REFUSAL THE WRITER RAISES, IN THE OPERATOR'S WORDS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **THE ROW HAS TO SAY WHY, AND `BIZ-STATE` IS NOT WHY.** PO ruling
# 2026-08-29, verbatim: *"if it is fail - you display on screen shich record
# failed and why (dont write to dB) and continue to uplaod next record"*. The
# four failure modes this loader already handled write `problem` and `fix_hint`
# in plain English with no ids in them, and a refusal caught at the write must
# read exactly the same — an operator cannot tell, and should not have to,
# which side of the module boundary refused their row.
#
# ⚠ **THE KEY IS RESOLVED HERE RATHER THAN RENDERED FROM `params.detail`,
# WHICH IS `DEF-322`.** A refusal's words come from its `message_key` and from
# nothing else; `params` carries facts (an account number, an earliest lawful
# date), and only the ones an operator can act on are put into a sentence. A
# uuid never is — `unit_id` is in every one of these refusals and in none of
# these sentences, because the operator's own `unit_ref` cell is on the row.
#
#: `message_key` → (problem, fix_hint), each a `str.format` template over
#: `unit_ref` (the operator's own cell) plus the refusal's own params.
_WRITE_REFUSAL_SENTENCES: dict[str, tuple[str, str]] = {
    # BR-CUS-017 (`_refuse_if_unit_occupied`) — one live account per unit, ever.
    "customers.account.unit_already_occupied": (
        "Unit {unit_ref} already has a live account on it, {account_no}.",
        "Close {account_no} before this one starts, or point this row at the "
        "unit its customer actually lives in. One unit carries one live "
        "account at a time — two would bill the same meter twice.",
    ),
    # BR-CUS-022 (`_make_occupying`) — the date the first bill is counted from.
    "customers.account.start_date_required": (
        "This account is going live and the file gives no date its service started.",
        "Fill in the day this customer's service began. It is the day the "
        "first bill is counted from, so it cannot be guessed — if the account "
        "is not live yet, set its status to pending activation instead.",
    ),
    # BR-CUS-056 — the outgoing account is paid through the move day.
    "customers.account.start_on_prior_move_day": (
        "The start date on this row belongs to whoever lived in unit "
        "{unit_ref} before, {prior_account_no}.",
        "Start this account on {earliest_start} or later. The day somebody "
        "moves out is already billed to them, so starting on it bills that "
        "day twice.",
    ),
    # BR-CUS-020 — a deactivated unit is neither vacant nor reserved.
    "customers.account.unit_not_eligible": (
        "Unit {unit_ref} is not taking accounts.",
        "It has been switched off. Turn the unit back on, or point this row "
        "at the unit its customer actually lives in.",
    ),
    # ⚠ **BR-MET-040 IS HERE AND IS EXPECTED TO GO QUIET, NOT TO FIRE.** The
    # plan-on-unit refusal is being moved OUT of the import path by the
    # customers lane of this same change, so this entry is a sentence for a
    # refusal that should stop arriving. It is written anyway and deliberately:
    # a row is worthless without a reason, and the day this key stops being
    # raised the entry costs nothing but stops a blank one arriving in the
    # window between the two halves landing. There is no stage-3 rule for it —
    # that would be a second copy of a rule being retired.
    "customers.account.plan_required_at_activation": (
        "Unit {unit_ref} has no rate plan, so an account cannot go live on it.",
        "Set the unit's plan first — Premises › the unit › Plan — then upload "
        "this file again.",
    ),
}

#: The catalog CLASS, for a refusal whose own key has no sentence above. It is
#: a fallback, and it is written to be READ ALOUD rather than looked up: no
#: code, no key, no rule id. The `else` branch of `_write_refusal_sentences`
#: explains why a generic sentence beats a rendered `params.detail`.
_WRITE_REFUSAL_BY_CODE: dict[str, tuple[str, str]] = {
    errors.BIZ_COMPLETENESS: (
        "Something this account needs before it can go live is missing from this row.",
        "Compare this row against one that loaded — the difference is an "
        "empty cell — then upload the file again.",
    ),
    errors.BIZ_STATE: (
        "This account cannot be created in the state this row describes.",
        "Check the unit this row names and the status it asks for against "
        "what is already on file, then upload the file again.",
    ),
    errors.BIZ_CAP: (
        "This row asks for more than this account is allowed to hold.",
        "Reduce the value the row carries, then upload the file again.",
    ),
}

_WRITE_REFUSAL_UNKNOWN: tuple[str, str] = (
    "This account was refused when it was written, and the run kept going.",
    "Every other row in the file loaded normally. Send this row to support "
    "with the run number on the receipt — they can see exactly what refused it.",
)


def _write_refusal_sentences(exc: errors.ApiError, mapped: dict[str, Any]) -> tuple[str, str]:
    """One caught write-time refusal → the two sentences the row carries.

    ⚠ **THE OPERATOR'S OWN `unit_ref` IS THE NOUN, NEVER THE REFUSAL'S
    `unit_id`.** Every one of these refusals names the unit by its uuid,
    because that is what the writer holds; the person reading the failures
    file typed `2205 Cedar Ln · Unit B` and has never seen a uuid. Nothing
    below prints one.

    ⚠ **AN UNKNOWN KEY GETS A GENERIC SENTENCE AND NOT `params.detail`.**
    Rendering the refusal's free text is exactly `DEF-322` — the ruling is that
    a customer sees the sentence for the key and nothing else — and a key with
    no sentence is a gap to close in this table, not a licence to leak the
    diagnostic. The refusal is still logged in full server-side by
    `core.errors._log_refusal`, so support keeps it.
    """
    facts: dict[str, Any] = {
        "unit_ref": str((mapped or {}).get("unit_ref") or "").strip() or "the unit this row names",
        "account_no": "the one already there",
        "prior_account_no": "the previous occupant",
        "earliest_start": "the day after they left",
    }
    for name, value in (exc.params or {}).items():
        # `unit_id` and `account_id` are uuids and are deliberately not offered
        # to a template; anything else the refusal knows is a fact a person can
        # act on (an account number, a date, a status word).
        if name.endswith("_id") or value in (None, ""):
            continue
        facts[name] = value
    templates = _WRITE_REFUSAL_SENTENCES.get(exc.message_key)
    if templates is None:
        templates = _WRITE_REFUSAL_BY_CODE.get(exc.code, _WRITE_REFUSAL_UNKNOWN)
        logger.warning(
            "import: no operator sentence for refusal key %s (code %s) — "
            "the rejected row carried the generic wording",
            exc.message_key,
            exc.code,
        )
    problem, fix_hint = templates
    try:
        return problem.format(**facts), fix_hint.format(**facts)
    except (KeyError, IndexError, ValueError):  # pragma: no cover — defensive
        # A template naming a fact this refusal did not carry must not turn a
        # rejected row into a crashed run: the row still gets its reason.
        return _WRITE_REFUSAL_UNKNOWN


def _load_accounts_rows(
    actor: Any,
    run: models.ImportRun,
    write_mode: str,
    data: dict[str, Any],
    reporter: import_progress.Reporter,
) -> dict[str, Any]:
    """The accounts commit — every row through the customers seam, one
    transaction (the caller's), one receipt, and ONE ledger handoff at the end.

    ⚠ **THE BATCH POST IS AFTER THE LOOP, NOT INSIDE IT, AND THAT IS GT-16's
    OWN SHAPE.** B5 GT-16's batch line — *"Σ of all opening JEs = Σ of all
    imported buckets (1,213 accounts → $184,320.55)"* — is a statement about the
    BATCH, and no per-row call can make it. `opening_balances.post_opening_batch`
    refuses to report success unless Σ AR debits = Σ clearing credits, which is
    the check that stops a migration landing 1,212 correct entries and one wrong
    one, to be found by a bookkeeper next quarter with no lawful way to edit any
    of them (hard rule 4).

    ⚠ **BR-CUS-047 — the unit is RESOLVED, never created.** The migration order
    is Premises → Units + Plans → Assets → **Accounts** → opening reads, and a
    row naming a unit that is not on file is an ERROR. Auto-creating it would
    silently invent the premise half of a utility's estate from a billing
    spreadsheet.
    """
    rows = _loadable_rows(run)
    unit_index = _unit_reference_index()
    premises_units = _premises_units_index()
    currency = seams.tenant_currency() if hasattr(seams, "tenant_currency") else None
    # ⛔⛔ **A MISSING CHANGEOVER DATE NO LONGER STOPS THE MIGRATION — IT HOLDS
    # THE BOOKS (PO ruling 2026-08-27).** This block used to call
    # `_refuse_accounts_no_cutover()` and refuse the WHOLE RUN.
    #
    # PO verbatim, on meeting the field: *"in account upload - 2.2 Has a cutover
    # date been given for this run? what is this ?"* — **the Product Owner of
    # this product could not tell what it was for**, on a screen that blocks
    # people. So the accounts LOAD, and only the money waits.
    #
    # ⚠ **HOLDING IS NOT CAUTION. IT IS THE ONLY CONSTRUCTION IN WHICH THE PO'S
    # OWN *"we can always change this date later"* IS TRUE**, and a lane that
    # "simplifies" the hold away welds a DEFAULTED date to the ledger. **Hard
    # rule 4 forbids editing a posted journal entry** — a correction is a new
    # entry, never an edit — so the moment `post_account_opening_batch` runs,
    # the changeover date is permanent. Until then it is provisional and
    # everything about it is still changeable. That is the whole argument; do
    # not remove it.
    #
    # ⚠ **THE PROVISIONAL DATE IS TODAY MINUS 90 DAYS, AND THE DIRECTION IS THE
    # POINT.** A FUTURE date would put every opening balance in the future —
    # nothing overdue, no ageing band, no reminder ever firing, and the error
    # runs in the utility's favour, which is the direction nobody checks.
    # Backwards is the safe way to be wrong, and the buckets are re-dated to
    # the real date at confirmation before anything is posted.
    cutover = _accounts_cutover(run)
    opening_held = cutover is None
    if opening_held:
        cutover = seams.tenant_today() - timedelta(days=PROVISIONAL_CHANGEOVER_DAYS)
    created = skipped_existing = with_opening = 0
    #: ⛔ **CR-046 C4 — the two counters the ruling adds, and the PO chose the
    #: first word: *"in case of insert - reject it"*.**
    updated = rejected_existing = 0
    #: ⛔ **CR-047 · DEF-2519 — rows the WRITER refused, one savepoint each.**
    #: A DIFFERENT counter from the three rejects above it, because it answers
    #: a different question: those rows were judged before anything was
    #: attempted, and these were attempted and turned down. An operator reading
    #: *"1,210 created · 3 failed"* needs both halves of the 3 to add up, and a
    #: run where this number is not zero is a run whose rehearsal did not see
    #: everything — which is the signal that stage 3 has a rule to grow.
    rejected_at_write = 0
    #: ⛔ **CR-047 — how many SERVICES the created accounts inherited from their
    #: units.** PO ruling 2026-08-29: *"if account is created then money is
    #: also lands"*. An account on a unit whose services never linked has
    #: nothing to bill and looks identical on a receipt to one that is ready,
    #: which is the same failure `opening_held` exists to make visible.
    with_services = 0
    #: ⛔ **ZERO, ALWAYS, ON THIS TARGET — and it is SERVED rather than dropped
    #: because one receipt screen renders every run.** PO ruling 2026-08-27:
    #: accounts are the one upload of six that does not call Settings ›
    #: Numbering. A non-zero here would be a claim that we renumbered somebody's
    #: account, which is the thing the ruling exists to prevent.
    issued_from_series = 0
    #: Rows rejected for carrying no account number at all. A DIFFERENT
    #: counter from `rejected_existing`: one says *"you already have this"* and
    #: the other says *"you did not tell us what to call it"*, and an operator
    #: fixes them in two different ways.
    no_number = 0
    #: ⛔ **CR-058 W7 · BR-CUS-1041 — ROWS THAT NAME A CUSTOMER AND DO NOT
    #: IDENTIFY THEM.** PO 2026-09-01: *"Without identifier we cannot create
    #: Customer ID or master account ot regular account"*. Stage 3 rejects these
    #: before they reach this loop (`ACC.CUSTOMER_IDENTITY_REQUIRED`), so these
    #: three counters are the BELT to that braces and are normally 0 — they move
    #: only when the file was validated under an older build or the mapping
    #: changed underneath. **The receipt's own figure is measured at VALIDATE**,
    #: from the same verdict function, because a row rejected at stage 3 never
    #: arrives here to be counted (decision log 2026-09-01, judgment 2).
    awaiting_identity = 0
    identity_mismatch = 0
    no_customer_name = 0
    #: ⛔ **WHAT THE RUN DID ABOUT THE CUSTOMERS, SEPARATELY.** *Matched* and
    #: *created* are different facts to a migrating utility: the first says the
    #: file joined people it already held, the second says it brought new ones
    #: in. One number covering both cannot tell a re-run from a first load.
    customers_created = 0
    customers_matched = 0
    #: ⛔ **THE CUSTOMER NUMBERS THE FILE ITSELF QUOTED (`DEF-2593`).** Collected
    #: for the same reason `numbers_written` is: the `customer` series has to be
    #: walked past them or the next hand-typed customer collides (`DEF-577`).
    customer_numbers_written: list[str] = []
    #: ⛔ **THE INDEX, READ ONCE (DEF-324) AND THROUGH THE SEAM (B1/B2 §2).**
    #: It is the SAME index stage 3's `ACC.NUMBER_ON_FILE` judged against, so
    #: the rehearsal and the commit cannot disagree about what is on file —
    #: `DEF-544`'s law.
    index = seams.accounts_import_index()
    numbers_written: list[str] = []
    #: What the ONE ledger call at the end is built from. Accounts with an empty
    #: opening position are ABSENT rather than zero-valued: a zero journal entry
    #: says nothing and can never be corrected away (hard rule 4).
    opening: list[dict[str, Any]] = []
    #: ⛔ **THE SECOND MONEY COLUMN ON THE SAME ROW (DEF-1713).** A migrated
    #: deposit is money the utility HOLDS OF THE CUSTOMER'S, and until today it
    #: was written to `accounts.deposit_on_file` and posted NOWHERE — a
    #: liability the balance sheet never heard about, $750.00 of it on the
    #: seeded estate. It rides the SAME handoff as the opening balances, under
    #: the same batch id and the same cutover date (BR-CUS-670 / BR-CUS-049).
    #: ⚠ It is a SEPARATE list from `opening` because an account may hold a
    #: deposit and owe nothing — three of the seeded five do — so it cannot be
    #: a key on a row that only exists when there is an opening balance.
    deposits: list[dict[str, Any]] = []
    reporter.mark(0, "Writing rows")

    for written, row in enumerate(rows, start=1):
        reporter.step(written)
        mapped = dict(row.mapped or {})
        unit_id = _unit_seat_for(run.target, mapped, unit_index, premises_units)
        if unit_id is None:
            # Stage 3 already refuses these; reaching here means the estate
            # changed under a validated run, so it is reported, not guessed at.
            skipped_existing += 1
            row.outcome = "skipped"
            row.problem = "This row names no unit that is on file."
            row.fix_hint = (
                "Import premises and units first (BR-CUS-047), then re-run. "
                "An account import never creates a unit."
            )
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue

        # ⛔ **CR-046 C4 — DOES THIS ROW NAME AN ACCOUNT ALREADY ON FILE?**
        # The accounts loader asked this of nothing before today: every row was
        # created, so a corrected re-run of a 1,213-row migration met 1,213
        # `BR-CUS-017` refusals at the unit seat. `_key_of` tries our own
        # `account_no` first and the utility's `external_ref` second.
        key = _key_of(run, mapped)
        if key is not None and key in index:
            if write_mode == "insert":
                rejected_existing += 1
                row.outcome = "rejected"
                row.problem, row.fix_hint = _insert_mode_on_file_sentences(
                    run.target, mapped, index[key]
                )
                row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
                continue
            # ⚠ **AN UPDATE POSTS NO JOURNAL ENTRY AND TOUCHES NO BUCKET** —
            # hard rule 4, and `customers.update_from_import`'s own docstring
            # carries the reasoning. It is also why this branch does not add to
            # `opening`: a second posting for an account whose opening batch is
            # already on the books would double a migration's AR.
            updated_row = seams.update_account_from_import(
                actor=actor,
                account_no=index[key]["account_no"],
                changes=_account_update_from(mapped),
            )
            if updated_row is None:
                _refuse_accounts_unwired()
            updated += 1
            _audit(
                actor,
                "accounts.updated_by_import",
                updated_row["id"],
                run_no=run.run_no,
                row=row.row_no,
            )
            row.outcome = "loaded" if row.outcome != "flagged" else "flagged"
            row.save(update_fields=["outcome", "updated_at"])
            continue

        # ⛔ **THE NUMBER COMES OFF THE FILE, VERBATIM (PO ruling 2026-08-27) —
        # AND THIS PARAGRAPH REPLACED ITS OWN OPPOSITE ELEVEN HOURS LATER.**
        # It read *"THE NUMBER NEVER REACHES A CREATE"* and passed `None` so
        # the `account` series would allocate. The PO reversed that for this
        # target alone: *"we use utility provdied account number here - we dont
        # create our own number … here we dont call settings -> account number
        # logic"*. The old text is quoted rather than deleted because a lane
        # reading only the four-target shape would rebuild exactly what the
        # reversal removed (hard-won law 1).
        #
        # ⚠ **A BLANK CELL CANNOT REACH THIS LINE**, and if it does the row is
        # REJECTED rather than numbered: `ACC.NUMBER_REQUIRED` refuses it at
        # stage 3, and this is the belt to that braces.
        account_no = str(mapped.get("account_no") or "").strip()
        if not account_no:
            rejected_existing += 0  # not an "already on file" reject — see below
            row.outcome = "rejected"
            row.problem = "This row has no account number."
            row.fix_hint = (
                "The account number is YOURS — the one already on the "
                "customer's bills and in your old system. SMART360 Next does "
                "not issue one here, because renumbering an account means "
                "writing to every customer. Fill the cell in and re-run."
            )
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            no_number += 1
            continue

        # ⛔⛔ **CR-058 W7 · BR-CUS-1041 — NO IDENTIFIER, NO ACCOUNT.**
        #
        # PO ruling 2026-09-01, verbatim: *"Without identifier we cannot create
        # Customer ID or master account ot regular account"*. A row with a name
        # and one identifier loads and its customer is matched-or-created; a row
        # with a name alone loads NOTHING and is reported as needing one.
        #
        # ⚠ **THIS IS THE BELT AND `ACC.CUSTOMER_IDENTITY_REQUIRED` IS THE
        # BRACES** — the same relationship `ACC.NUMBER_REQUIRED` has with the
        # blank-number check above it. Stage 3 rejects these rows, so this
        # normally moves nothing; it exists because a run validated under an
        # older build must not reach `create_from_import` with no evidence.
        #
        # ⚠ **NOTHING IS INVENTED TO GET PAST IT** — no placeholder phone, no
        # zeroed Tax ID, and neither `customer_ref` nor `customer_no` is read as
        # identity: *"a filled column that means nothing is worse than an empty
        # one, because the matcher will read it."*
        identity = account_identity_verdict(mapped)
        if identity["verdict"] != ACCOUNT_IDENTITY_ELIGIBLE:
            if identity["verdict"] == ACCOUNT_IDENTITY_AWAITING:
                awaiting_identity += 1
            elif identity["verdict"] == ACCOUNT_IDENTITY_MISMATCH:
                identity_mismatch += 1
            else:
                no_customer_name += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _identity_refusal_sentences(identity)
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue
        # ⛔⛔ **ONE SAVEPOINT PER RECORD — CR-047 TASK 8, AND ITS ABSENCE WAS
        # `DEF-2519` (critical).**
        #
        # PO ruling 2026-08-29, verbatim: *"if it is success then you read next
        # record, if it is fail - you display on screen shich record failed and
        # why (dont write to dB) and continue to uplaod next record"*. That is
        # `BR-CUS-051`'s signed standard — *"staged → per-row errors →
        # skip-errors ON → 'N created · N failed' summary"* — and until this
        # block existed the accounts loader delivered it for the four failures
        # it checked BEFORE the write and for none of the ones the writer
        # itself raises.
        #
        # **What that cost, measured:** `customers._make_occupying` refuses a
        # unit that already holds a live account (BR-CUS-017), a row activating
        # with no start date (BR-CUS-022) and a start on the previous
        # occupant's move day (BR-CUS-056). Any one of those escaped this loop
        # and aborted `_load_apply`'s `transaction.atomic()`, so a 1,213-row
        # cutover with **one** bad row on row 63 left **zero** accounts on file
        # — and the operator was shown a refusal about one account with no way
        # to tell which of the 1,213 it was.
        #
        # ⚠ **A NESTED `atomic()` IS A SAVEPOINT, WHICH IS THE WHOLE POINT.**
        # The refusal is caught OUTSIDE the inner block, so Postgres has
        # already rolled back to the savepoint: this row wrote nothing (the
        # PO's *"dont write to dB"*), the outer transaction is still healthy,
        # and the loop keeps going. The all-or-nothing property CR-026 recorded
        # for the RUN is untouched — a killed worker still leaves nothing —
        # because that property is about the outer transaction and this is
        # inside it.
        #
        # ⚠ **THE ADVISORY LOCK IS NOT RELEASED BY THE SAVEPOINT AND DOES NOT
        # NEED TO BE.** `lock_unit_scope` takes `pg_advisory_xact_lock`, which
        # is held to the end of the OUTER transaction; a later row naming the
        # same unit re-takes it as a no-op in the same transaction.
        #
        # ⚠ **`_refuse_accounts_unwired()` IS RAISED OUTSIDE THE `try`, ON
        # PURPOSE.** It is a `BizError` too, and catching it here would turn
        # *"customers cannot answer at all"* into 1,213 politely-rejected rows
        # — a migration reported as fully-judged when nothing was ever asked.
        # That is DEF-075's shape, and it aborts the run exactly as before.
        result: dict[str, Any] | None = None
        try:
            with transaction.atomic():
                result = seams.create_account_from_import(
                    actor=actor,
                    payload={
                        "mapped": mapped,
                        "unit_id": unit_id,
                        "account_no": account_no,
                        "currency": mapped.get("currency") or currency,
                        "cutover_on": cutover,
                        "import_run_id": run.id,
                        "account": _account_payload_from(mapped),
                        # ⛔ **CR-058 W7 — THE EVIDENCE, NOT A DECISION.** The
                        # door resolves the customer: match first, create on no
                        # match, create nothing with no identifier. This module
                        # writes no customer and runs no matcher (B1/B2 §2), the
                        # same boundary `owner_customer_block` keeps for the
                        # premises import.
                        "customer": account_customer_block(mapped, identity),
                    },
                )
                if result is not None:
                    # INSIDE the savepoint: an audit row for an account that
                    # was rolled back would be a record of something that did
                    # not happen (hard rule 7 is about money that MOVED).
                    _audit(
                        actor,
                        "accounts.created_by_import",
                        result["id"],
                        run_no=run.run_no,
                        row=row.row_no,
                    )
        except (errors.BizError, errors.ValidationError) as refusal:
            # ⚠ **THESE TWO CLASSES AND NOT `Exception`.** `BizError` and
            # `ValidationError` are the catalog's two ways of saying *"this
            # ROW's data is wrong"* (B12 §3's BIZ and VAL classes), which is
            # the only kind of failure a per-row skip is the right answer to.
            # Everything else is deliberately left to propagate and take the
            # run down, because none of it is about this row:
            #   · `AuthError` — the actor's role. It would refuse every row
            #     identically, and 1,213 "rejected" rows would hide one
            #     permission problem behind a data-quality report.
            #   · `SysError` — the account-number series unusable, the ledger
            #     unreachable. The next row will fail the same way and the
            #     file's books would come out half-posted.
            #   · `NotFoundError`, `IntegrityError`, anything unforeseen — a
            #     bug or a broken invariant. Swallowing those is how a
            #     migration reports "43 failed" over a fault nobody diagnoses.
            rejected_at_write += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _write_refusal_sentences(refusal, mapped)
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue
        if result is None:
            _refuse_accounts_unwired()
        created += 1
        row.created_record_id = result["id"]
        if result.get("account_no"):
            numbers_written.append(str(result["account_no"]))
        if not result.get("opening_empty"):
            with_opening += 1
            opening.append(
                {
                    "account_id": result["id"],
                    "account_ref": result.get("account_no"),
                    "balance": Decimal(result["opening_total"]),
                }
            )
        # ⛔ **CR-047 — THE CROSS-LANE FIGURE, AND IT IS READ DEFENSIVELY ON
        # PURPOSE.** PO ruling 2026-08-29: *"if account is created then money
        # is also lands"* — an account that inherited none of its unit's
        # services has nothing to bill, so the receipt must be able to say how
        # many DID. `customers.create_from_import` returns `services_linked`;
        # a build where that half has not landed yet returns no such key, and
        # `0` is then the honest reading of *"the writer did not say"* rather
        # than a claim that no services were linked. It never crashes the load
        # over a key.
        with_services += int(result.get("services_linked") or 0)
        # ⛔ **CR-058 W7 — MATCHED OR CREATED, READ DEFENSIVELY** for the reason
        # `with_services` states one line up: a build where the writer does not
        # yet answer returns no such key, and silence is not a claim that no
        # customer was created.
        if result.get("customer_created"):
            customers_created += 1
        elif result.get("customer_no"):
            customers_matched += 1
        if result.get("customer_no_from_file"):
            customer_numbers_written.append(str(result["customer_no"]))
        held = Decimal(result.get("deposit_on_file") or 0)
        if held:
            deposits.append(
                {
                    "account_id": result["id"],
                    "account_ref": result.get("account_no"),
                    "held": held,
                    # BR-CUS-050's ORIGINAL receipt date — carried for the memo
                    # and the audit row, NEVER used as the entry date.
                    "received_on": result.get("deposit_received_on"),
                }
            )
        row.outcome = "loaded" if row.outcome != "flagged" else "flagged"
        # ⛔ **WHAT THIS ROW ACTUALLY WROTE, RECORDED ON THE ROW AS IT IS
        # WRITTEN (CR-047 task 13).** The successes file is a RECEIPT and takes
        # `receipt()`'s own posture: *"every figure is what the run RECORDED at
        # the moment it loaded … nothing on this path counts rows again."* The
        # opening total in particular is the writer's OWN figure, carried, never
        # re-summed from the four `ob_*` cells — `create_from_import`'s
        # docstring gives the reason in as many words (*"two derivations of one
        # number is how they come to disagree"*), and `import_writer` splits a
        # negative bucket into a carried credit, so a second sum here would
        # disagree with the ledger on exactly the rows that matter.
        #
        # It rides `mapped` under a RESERVED key — stage 2's own `__…__`
        # convention (`PARSE_PROBLEMS`), and `_NOT_A_COLUMN` strips it so it can
        # never reach a model — because it costs no migration and no extra
        # write: `mapped` joins an UPDATE this line was making anyway.
        row.mapped = {**mapped, LOAD_RESULT: _load_result_from(result)}
        row.save(update_fields=["outcome", "created_record_id", "mapped", "updated_at"])

    # DEF-577 — the account series moves clear of the file's own numbers, so the
    # next hand-typed account cannot collide with one this run brought in.
    _catch_up_target_series(actor, run.target, numbers_written)
    # ⛔ **AND THE CUSTOMER SERIES TOO, SINCE `DEF-2593` MADE THE FILE ABLE TO
    # QUOTE ONE.** Exactly `DEF-577`'s arithmetic on a second series: a file
    # quoting `C-00500` against a counter standing at 12 would otherwise collide
    # the first time a clerk adds a customer by hand. Forward-only, and a number
    # the tenant's own format could not have written moves nothing.
    _catch_up_series(actor, core_numbering.CUSTOMER, customer_numbers_written)

    # ⛔ **HELD MEANS THE LEDGER IS NOT CALLED AT ALL** — not called with a
    # placeholder, not called and reversed. A journal entry that exists is
    # permanent (hard rule 4), so the only way to keep the date changeable is
    # for no entry to exist yet. `confirm_changeover_date` below is the door
    # that posts it, and it is the ONLY door.
    if opening_held:
        posting = None
    else:
        # US-CUS-022 — the ONE handoff. Customers asks; the LEDGER writes the
        # journal lines (hard rule 5).
        posting = seams.post_account_opening_batch(
            actor=actor,
            batch_id=run.id,
            cutover_on=cutover,
            imported_at=timezone.now(),
            currency=currency or "USD",
            accounts=opening,
            deposits=deposits,
        )
    if posting is None and (opening or deposits) and not opening_held:
        # The ledger could not answer and money was supposed to move. Refuse
        # rather than report a migration whose books do not exist (DEF-075).
        _refuse_accounts_unwired()

    if bool(data.get("create_rollback_point", True)):
        # The FK lives on the POINT, not on the run — `RollbackPoint.run`. The
        # row is created for that link; nothing here holds a handle to it.
        models.RollbackPoint.objects.create(
            tenant_id=run.tenant_id,
            point_no=_allocate_point_no(),
            run=run,
            expires_at=timezone.now() + timedelta(days=ROLLBACK_DAYS),
            status="available",
        )

    run.write_mode = write_mode
    run.counts = {
        **(run.counts or {}),
        "created": created,
        "updated": updated,
        "skipped_existing": skipped_existing,
        "rejected_existing": rejected_existing,
        "rejected_no_number": no_number,
        # ⛔ CR-058 W7 · BR-CUS-1041 — see the counters' own note above the loop.
        # These are the LOADER's belt figures; `accounts_awaiting_identity` on
        # the receipt is measured at validate and is the one an operator reads.
        "rejected_awaiting_identity": awaiting_identity,
        "rejected_identity_mismatch": identity_mismatch,
        "rejected_no_customer_name": no_customer_name,
        "customers_created": customers_created,
        "customers_matched": customers_matched,
        # ⛔ CR-047 · DEF-2519 — see the counter's own note above the loop.
        "rejected_at_write": rejected_at_write,
        # ⛔ CR-047 — the cross-lane figure. `customers.create_from_import`
        # returns `services_linked` per account; this is their sum, and it is 0
        # on every run loaded before that key existed, which is the honest
        # reading of "the run did not say".
        "with_services": with_services,
        "numbers_issued_from_series": issued_from_series,
        "with_opening_balance": with_opening,
        # ⛔ **A MIGRATION THAT IS 90% DONE MUST NOT LOOK IDENTICAL TO ONE THAT
        # IS FINISHED.** The receipt says, as a number: *"412 accounts loaded ·
        # 412 opening balances waiting for your changeover date."* Without it
        # the operator closes the tab believing the books are on the system,
        # and finds out at the first bill run that no account has a balance.
        "opening_held": with_opening if opening_held else 0,
        # The provisional date the buckets currently carry, so the confirm
        # screen can show what it is about to replace rather than an empty box.
        "changeover_provisional": cutover.isoformat() if opening_held else None,
        "changeover_on": cutover.isoformat() if not opening_held else None,
        "opening_ar": (posting or {}).get("ar_debits", "0"),
        # DEF-1713 — what the migration told the balance sheet the utility owes
        # its customers back. On the receipt beside the receivables, because a
        # migration that moved one and not the other is exactly the failure this
        # counter exists to make visible.
        "opening_deposits": (posting or {}).get("deposit_credits", "0"),
        "deposits_held": len(deposits),
        "deactivated": 0,
        "skipped_occupied": 0,
    }
    run.status = "loaded"
    run.finished_at = timezone.now()
    run.save(update_fields=["write_mode", "counts", "status", "finished_at", "updated_at"])
    return receipt(run)


# ═══════════════════════════════════════════════════════════════════════════
# CR-047 WIDENING · TASK 20 — THE ASSETS WRITER'S REFUSALS, IN THE OPERATOR'S
# WORDS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **THE SAME TABLE AS `_WRITE_REFUSAL_SENTENCES`, FOR THE OTHER WRITER.**
# The accounts half of CR-047 built the shape; this is that shape applied to
# `apps.assets.services._create_asset_inner`, which refuses a row at least
# nineteen ways by name. It is a SECOND TABLE rather than more entries in the
# first because the two writers' keys never collide and the NOUN differs — an
# accounts row is refused about "this account", an assets row about "this
# meter" / "this sub-meter" / "this device", which is `ASSET_NOUN_BY_TARGET`'s
# word and not a synonym invented here.
#
# ⚠ **NO IDS, NO CODES, NO UUIDS** — CR-016's no-internal-references rule, and
# `DEF-322`'s ruling that a customer sees the sentence for the KEY and never
# the refusal's `params.detail`. `unit_id`, `service_point_id`,
# `parent_asset_id` and `recreated_from_asset_id` are all uuids that appear in
# these refusals' params and in none of these sentences.
#
# ⚠ **THE OPERATOR'S OWN CELL IS THE NOUN.** An assets row loaded under the
# 2026-08-27 ruling takes its number from the tenant's series, so on a REFUSED
# row that number does not exist yet and never appeared on their spreadsheet —
# `{row_label}` is the utility's own legacy reference, then the serial, then
# the unit cell, because those are the cells actually in front of them.

#: `message_key` → (problem, fix_hint), each a `str.format` template over
#: `noun` / `row_label` (the operator's own cells) plus the refusal's own
#: params. Keys are `apps.assets.services`'s own; a key with no row here falls
#: through to the class table below rather than to `params.detail`.
_ASSET_REFUSAL_SENTENCES: dict[str, tuple[str, str]] = {
    # BR-AST-033 — the hard block. `asset_no` is OURS and is printed only
    # because the refusal is precisely that this number is already in use.
    "assets.asset_no_duplicate": (
        "The number {asset_no} is already on another {noun}.",
        "This {noun} was given a number that is already in use. Nothing on the "
        "row needs changing — upload the file again and it will be issued the "
        "next free number. If it keeps happening, the counter under Settings › "
        "Numbering is behind the records already on file.",
    ),
    # BR-AST-049 — the utility's OWN legacy reference is unique per tenant.
    "assets.external_ref_duplicate": (
        "Your own reference {external_ref} is already on {noun} {asset_no}.",
        "Two rows cannot carry the same reference from your old system. Check "
        "whether this is the same device listed twice — if it is, delete one "
        "row; if it is genuinely a second device, give it its own reference "
        "and upload the file again.",
    ),
    # BR-AST-011 — an assign-on-create asset states the day it went in.
    "assets.install_date_required": (
        "{row_label} is being fitted to a unit and the file gives no date it "
        "was installed.",
        "Fill in the day it was installed. It is the day that unit's readings "
        "start counting from, so it cannot be guessed — if this one is not "
        "fitted anywhere yet, clear the unit cell and it will load into "
        "inventory instead.",
    ),
    # BR-AST-009 — a measuring asset declares its service.
    "assets.service_required": (
        "{row_label} measures something and the file does not say what.",
        "Fill in the service this {noun} measures — electric, water, gas and "
        "so on — then upload the file again.",
    ),
    # CLAUDE.md hard rule 3 — consumption always carries an explicit unit.
    "assets.uom_required": (
        "{row_label} measures something and the file does not say in what "
        "units.",
        "Fill in the unit it reads in — kWh, gallons, therms and so on. A "
        "reading with no unit cannot be billed, so it is never assumed.",
    ),
    # BR-MET-003 — the service must be one this utility actually sells.
    "assets.service_not_enabled": (
        "{row_label} names the service {service}, which this utility does not "
        "offer.",
        "Either correct the service on this row, or switch that service on "
        "under Settings › Services first and upload the file again.",
    ),
    # BR-AST-003 — a sub-meter hangs off a master.
    "assets.parent_required": (
        "{row_label} is a sub-meter and the file does not say which master "
        "meter it sits under.",
        "Fill in the master meter's number. A sub-meter's share is worked out "
        "from its master's reading, so it cannot stand on its own.",
    ),
    "assets.parent_must_be_a_meter": (
        "The master named on {row_label} is not a meter.",
        "A sub-meter must hang off a meter or a net meter. Check the master "
        "cell against the meters already on file, then upload again.",
    ),
    # BR-AST-026 — no number on the row and no series to issue one.
    "assets.asset_no_required_no_series": (
        "There is no numbering series set up for this kind of {noun}, so this "
        "row could not be given a number.",
        "Set the series up under Settings › Numbering, then upload the file "
        "again. Nothing on the row itself needs changing.",
    ),
    # The type catalog and the two BR-AST-043/044 flat catalogs — a value that
    # is not one of this tenant's own. `allowed` is the tenant's live list and
    # IS printed: it is their own vocabulary, never an internal reference.
    "assets.type_unknown": (
        "{row_label} names a kind of asset this utility does not have: {value}.",
        "Use one of the kinds already set up, or add this one under Settings "
        "first, then upload the file again.",
    ),
    "assets.read_method_unknown": (
        "{row_label} names a way of reading that this utility does not have: "
        "{value}.",
        "Use one of your own reading methods, or add this one under Settings "
        "first, then upload the file again.",
    ),
    "assets.meter_type_unknown": (
        "{row_label} names a meter class this utility does not have: {value}.",
        "Use one of your own meter classes, or add this one under Settings "
        "first, then upload the file again.",
    ),
    # BR-AST-044 / BR-AST-010 — a classification on a thing it cannot describe.
    "assets.meter_type_unavailable": (
        "{row_label} is not a meter, so it cannot carry a meter class.",
        "Clear the meter-class cell on this row, or change the kind of asset "
        "it says it is, then upload the file again.",
    ),
    "assets.net_metering_unavailable": (
        "{row_label} is not a kind of asset that can do net metering.",
        "Clear the net-metering cell on this row, or change the kind of asset "
        "it says it is, then upload the file again.",
    ),
    # The validator's numeric and range refusals.
    "assets.not_a_number": (
        "A cell on {row_label} should hold a number and does not.",
        "Find the numeric cell on this row — the multiplier, the cost, the "
        "capacity or the share — correct it, and upload the file again.",
    ),
    "assets.must_be_positive": (
        "A cell on {row_label} must be greater than zero and is not.",
        "The multiplier is the usual one: it is what a reading is multiplied "
        "BY, so zero would make every reading nothing. Correct it and upload "
        "the file again.",
    ),
    "assets.must_not_be_negative": (
        "A cell on {row_label} cannot be a negative number.",
        "Correct the negative value on this row and upload the file again.",
    ),
    "assets.register_digits_range": (
        "The number of dials on {row_label} has to be between 1 and 9.",
        "Correct the register-digits cell and upload the file again. Leave it "
        "empty and it takes the usual 9.",
    ),
    "assets.test_interval_range": (
        "A number of months or years on {row_label} has to be at least 1.",
        "Correct the test-interval or expected-life cell and upload the file "
        "again. Leave it empty and this {noun} simply has no test cadence.",
    ),
    "assets.allocation_share_range": (
        "The share on {row_label} is more than 100 percent.",
        "A sub-meter's share of its master cannot be more than the whole. "
        "Correct it and upload the file again.",
    ),
    # The transform stage maps the file's columns onto ours, so a field the
    # validator does not know is a MAPPING that survived stage 2.
    "assets.unknown_field": (
        "{row_label} carries a column this {noun} has nowhere to put.",
        "Go back to the mapping step and unmap that column, or point it at a "
        "field that exists, then run the file again.",
    ),
}

#: The catalog CLASS, for a refusal whose own key has no sentence above —
#: written to be READ ALOUD, with no code, no key and no rule id in it. It is
#: a separate table from the accounts one for the same reason the key table is:
#: the noun differs.
_ASSET_REFUSAL_BY_CODE: dict[str, tuple[str, str]] = {
    errors.VAL_REQUIRED: (
        "Something this {noun} needs before it can be created is missing from "
        "{row_label}.",
        "Compare this row against one that loaded — the difference is an empty "
        "cell — then upload the file again.",
    ),
    errors.VAL_FORMAT: (
        "A cell on {row_label} is not in a shape this {noun} can accept.",
        "Compare this row against one that loaded, correct the cell that "
        "differs, then upload the file again.",
    ),
    errors.VAL_RANGE: (
        "A value on {row_label} is outside what this {noun} allows.",
        "Compare this row against one that loaded, correct the value, then "
        "upload the file again.",
    ),
    errors.VAL_UNKNOWN_LOOKUP: (
        "{row_label} names something this utility does not have on file.",
        "Check the row's lookup cells — the kind, the service, the reading "
        "method — against what is set up under Settings, then upload again.",
    ),
    errors.VAL_UOM_MISMATCH: (
        "The unit on {row_label} does not match what its service is measured in.",
        "Correct the unit cell so it matches the service, then upload the file "
        "again.",
    ),
    errors.BIZ_COMPLETENESS: (
        "Something this {noun} needs before it can be created is missing from "
        "{row_label}.",
        "Compare this row against one that loaded — the difference is an empty "
        "cell — then upload the file again.",
    ),
    errors.BIZ_STATE: (
        "This {noun} cannot be created in the state {row_label} describes.",
        "Check the unit this row names and the status it asks for against what "
        "is already on file, then upload the file again.",
    ),
    errors.BIZ_CAP: (
        "{row_label} asks for more than this {noun} is allowed to hold.",
        "Reduce the value the row carries, then upload the file again.",
    ),
    errors.BIZ_IMMUTABLE: (
        "{row_label} names a {noun} that can no longer be changed.",
        "A retired {noun} is permanent — add the replacement as a new row "
        "instead, then upload the file again.",
    ),
}

_ASSET_REFUSAL_UNKNOWN: tuple[str, str] = (
    "This {noun} was refused when it was written, and the run kept going.",
    "Every other row in the file loaded normally. Send this row to support with "
    "the run number on the receipt — they can see exactly what refused it.",
)


def _asset_row_label(target: str, mapped: dict[str, Any]) -> str:
    """The name the OPERATOR knows this row by.

    ⚠ **IT IS NOT `asset_no` FIRST, AND THAT IS THE POINT.** Under the PO's
    ruling of 2026-08-27 a created asset takes its number from the tenant's
    series, so on a refused row that number does not exist yet and has never
    appeared on their spreadsheet. What IS on the spreadsheet is their own
    legacy reference, the manufacturer's serial, or the unit the thing sits in
    — tried in that order, which is the order of how precisely each one
    identifies one row of the file.
    """
    noun = ASSET_NOUN_BY_TARGET.get(target, "asset")
    for field, shape in (
        ("external_ref", "The {noun} you list as {value}"),
        ("serial_no", "The {noun} with serial {value}"),
        ("asset_no", "{noun} {value}"),
        ("unit_ref", "The {noun} for unit {value}"),
        ("premises_ref", "The {noun} at {value}"),
    ):
        value = str((mapped or {}).get(field) or "").strip()
        if value:
            return shape.format(noun=noun, value=value)
    return f"This {noun}"


def _asset_write_refusal_sentences(
    exc: errors.ApiError, target: str, mapped: dict[str, Any]
) -> tuple[str, str]:
    """One caught assets refusal → the two sentences the row carries.

    The accounts half's `_write_refusal_sentences` is the model and its
    reasoning holds verbatim: the words come from the `message_key` and from
    nothing else, `params` supplies FACTS a person can act on, and every
    `*_id` is dropped before a template can see it.

    ⚠ **`allowed` IS FLATTENED RATHER THAN DROPPED.** Two of these refusals
    carry the tenant's own live vocabulary as a LIST, and a Python list
    rendered into a sentence prints its brackets and quotes at the operator.
    It is their own list, so it is printed — as words, joined with commas.
    """
    facts: dict[str, Any] = {
        "noun": ASSET_NOUN_BY_TARGET.get(target, "asset"),
        "row_label": _asset_row_label(target, mapped),
        "asset_no": "the one already there",
        "external_ref": str((mapped or {}).get("external_ref") or "").strip()
        or "the one on this row",
        "service": str((mapped or {}).get("service") or "").strip() or "a service",
        "value": "the value on this row",
    }
    for name, value in (exc.params or {}).items():
        # Every `*_id` here is a uuid the writer holds and the operator has
        # never seen (`unit_id`, `service_point_id`, `parent_asset_id`).
        if name.endswith("_id") or value in (None, "", [], {}):
            continue
        facts[name] = ", ".join(str(item) for item in value) if isinstance(value, list) else value
    templates = _ASSET_REFUSAL_SENTENCES.get(exc.message_key)
    if templates is None:
        templates = _ASSET_REFUSAL_BY_CODE.get(exc.code, _ASSET_REFUSAL_UNKNOWN)
        logger.warning(
            "import: no operator sentence for assets refusal key %s (code %s) — "
            "the rejected row carried the generic wording",
            exc.message_key,
            exc.code,
        )
    problem, fix_hint = templates
    try:
        return problem.format(**facts), fix_hint.format(**facts)
    except (KeyError, IndexError, ValueError):  # pragma: no cover — defensive
        # A template naming a fact this refusal did not carry must not turn a
        # rejected row into a crashed run: the row still gets its reason.
        unknown_problem, unknown_fix = _ASSET_REFUSAL_UNKNOWN
        return unknown_problem.format(**facts), unknown_fix.format(**facts)


def _asset_unexpected_failure_sentences(
    exc: BaseException, target: str, mapped: dict[str, Any]
) -> tuple[str, str]:
    """A row the writer could not save for a reason that is NOT a data rule
    (`DEF-AST-8102`). A known refusal still gets its own catalogue sentence; any
    other fault gets a plain one — never a class name or an id (B14 rule 31)."""
    if isinstance(exc, errors.ApiError):
        return _asset_write_refusal_sentences(exc, target, mapped)
    label = _asset_row_label(target, mapped)
    return (
        f"{label} could not be saved.",
        "Upload this row again. If it fails again, tell support the row number.",
    )


def _refuse_parts_unwired() -> None:  # pragma: no cover — work ships in-tree
    """The seam contract's honest failure, `DEF-075`'s rule made operational.

    ⚠ **AN EMPTY `parts_import_index()` IS NOT THIS.** A tenant that has never
    added a part has an empty register, which is ordinary and common; a module
    that cannot answer is a deployment fault. The two are told apart by asking
    for the WRITER — `None` from `seams.create_part_from_import` means work
    published nothing — and never by the size of a read."""
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-MET-096",
        message_key="metering.import.parts_unwired",
    )


def _part_payload_from(mapped: dict[str, Any]) -> dict[str, Any]:
    """The row as the fields `work.services._clean_part` takes, and no others.

    ⚠ **A KEY THAT IS ABSENT IS NOT A KEY THAT IS BLANK, AND `_clean_part`
    READS THE DIFFERENCE.** It is `partial`-aware: a field that is present is
    validated and written, a field that is missing is left alone. So a column
    the operator did not map must not travel as `""` — on the update half that
    would blank a name the file never mentioned. Only mapped, non-`None` cells
    are carried."""
    # ⚠ **THIS TUPLE IS `work.services._clean_part`'s ALLOW LIST AND NOTHING
    # ELSE.** An unknown field is REFUSED there, not ignored, so a field added
    # here that work does not take rejects every row of every file at the write
    # — which is how `active` was found and removed on 2026-09-07.
    fields = ("part_no", "name", "category", "unit_of_measure", "unit_cost")
    return {name: mapped[name] for name in fields if mapped.get(name) is not None}


#: `work.services._clean_part`'s refusal keys → the two sentences a rejected row
#: carries. ⚠ **THE WORDS COME FROM THE `message_key` AND FROM NOTHING ELSE** —
#: the assets and accounts halves' rule, followed rather than re-derived. A key
#: with no entry here logs a warning and falls back to the generic pair, so a
#: new refusal in `work` degrades to a truthful sentence instead of a crash.
_PART_REFUSAL_SENTENCES: dict[str, tuple[str, str]] = {
    "work.parts.duplicate_no": (
        "Part {row_label} is already in the register as {existing}.",
        "Part numbers are unique, and upper and lower case count as the same "
        "number. Give this row a different one, or re-run in Insert & update "
        "so the row on file is updated instead.",
    ),
    "work.parts.category_unknown": (
        "{row_label} names a category you do not have.",
        "Use one of yours — {allowed} — or leave the cell empty and the part "
        "loads with no category. Categories are added on Settings.",
    ),
    "work.parts.cost_number": (
        "The unit cost on {row_label} is not a number.",
        "Take out currency symbols, spaces and thousands separators; "
        "12.50 rather than $12.50.",
    ),
    "work.parts.cost_negative": (
        "The unit cost on {row_label} is below zero.",
        "A part cannot cost less than nothing. Leave the cell empty if you do "
        "not know the price yet.",
    ),
    "work.parts.cost_places": (
        "The unit cost on {row_label} carries more than {max} decimals.",
        "Round it to {max} decimals in the file and upload it again.",
    ),
    "work.lookups.required": (
        "{row_label} is missing something the register needs.",
        "A part needs a part number, a description and a unit. Fill the empty "
        "cell in and upload the file again.",
    ),
    "work.lookups.too_long": (
        "A value on {row_label} is longer than {max} characters.",
        "Shorten it in the file and upload it again.",
    ),
    "work.lookups.unknown_field": (
        "{row_label} carries a column the parts register does not take.",
        "Go back to the mapping step and leave that column out.",
    ),
}

_PART_REFUSAL_UNKNOWN: tuple[str, str] = (
    "Part {row_label} was refused when it was written, and the run kept going.",
    "Every other row in the file loaded normally. Send this row to support with "
    "the run number on the receipt — they can see exactly what refused it.",
)


def _part_write_refusal_sentences(
    exc: errors.ApiError, mapped: dict[str, Any]
) -> tuple[str, str]:
    """One caught parts refusal → the two sentences the row carries.

    ⚠ **`allowed` IS FLATTENED RATHER THAN DROPPED**, exactly as the assets
    half does it: `work.parts.category_unknown` carries the tenant's own live
    category list, and a Python list rendered into a sentence prints its
    brackets and quotes at the operator. It is their own list, so it is
    printed — as words, joined with commas.
    """
    facts: dict[str, Any] = {
        "row_label": str((mapped or {}).get("part_no") or "").strip() or "this row",
        "existing": "the one already there",
        "allowed": "the ones on your register",
        "max": "the limit",
    }
    for name, value in (exc.params or {}).items():
        if name.endswith("_id") or value in (None, "", [], {}):
            continue
        facts[name] = (
            ", ".join(str(one) for one in value) if isinstance(value, (list, tuple)) else value
        )
    templates = _PART_REFUSAL_SENTENCES.get(exc.message_key)
    if templates is None:
        templates = _PART_REFUSAL_UNKNOWN
        logger.warning(
            "import: no operator sentence for parts refusal key %s (code %s) — "
            "the rejected row carried the generic wording",
            exc.message_key,
            exc.code,
        )
    problem, fix_hint = templates
    try:
        return problem.format(**facts), fix_hint.format(**facts)
    except (KeyError, IndexError, ValueError):  # pragma: no cover — defensive
        # A template naming a fact this refusal did not carry must not turn a
        # rejected row into a crashed run: the row still gets its reason.
        return _PART_REFUSAL_UNKNOWN[0].format(**facts), _PART_REFUSAL_UNKNOWN[1]


def _load_parts_rows(
    actor: Any,
    run: models.ImportRun,
    write_mode: str,
    data: dict[str, Any],
    reporter: import_progress.Reporter,
) -> dict[str, Any]:
    """The parts commit — every row through work's own writer, one receipt.

    ⚠ **THE SHAPE IS THE ASSETS LOADER'S AND THE DIFFERENCES ARE THREE, ALL OF
    THEM ABSENCES.** There is no unit to seat a part on, no number series to
    allocate from (`part_no` is the utility's own and comes off the file), and
    no rollback consequence beyond the row itself. What is identical is the
    part that matters: `insert` REJECTS a row already on file and says so on
    that row; `upsert` updates it through the same validator an edit on
    `Work-025` goes through; `replace` never reaches here (refused in the dry
    run this commit shares).

    ⚠ **ONE SAVEPOINT PER ROW, AND CLAUDE.md LAW 14 IS WHY IT IS NOT
    OPTIONAL.** On PostgreSQL a refused INSERT aborts the whole transaction, so
    a `try/except` with no nested `atomic()` would lose every row written
    before the bad one — at COMMIT, silently, with the suite green because
    `config/settings/test.py` hardcodes SQLite, which has no aborted-
    transaction state. Do not "simplify" it away.
    """
    rows = _loadable_rows(run)
    index = seams.parts_import_index()
    created = updated = rejected_existing = rejected_at_write = 0
    reporter.mark(0, "Writing rows")
    for written, row in enumerate(rows, start=1):
        reporter.step(written)
        mapped = dict(row.mapped or {})
        key = _key_of(run, mapped)
        payload = _part_payload_from(mapped)
        on_file = key is not None and key in index
        if on_file and write_mode == "insert":
            rejected_existing += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _insert_mode_on_file_sentences(
                run.target, mapped, index[key]
            )
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue

        result: dict[str, Any] | None = None
        try:
            with transaction.atomic():  # ← SAVEPOINT. Law 14. Do not remove.
                if on_file:
                    result = seams.update_part_from_import(
                        actor=actor, part_id=index[key]["id"], payload=payload
                    )
                    if result is not None:
                        # INSIDE the savepoint: an audit row for a part that was
                        # rolled back would record something that did not happen.
                        _audit(
                            actor,
                            "parts.updated_by_import",
                            result["id"],
                            run_no=run.run_no,
                            row=row.row_no,
                        )
                else:
                    result = seams.create_part_from_import(actor=actor, payload=payload)
                    if result is not None:
                        _audit(
                            actor,
                            "parts.created_by_import",
                            result["id"],
                            run_no=run.run_no,
                            row=row.row_no,
                        )
        except (errors.BizError, errors.ValidationError) as refusal:
            # ⚠ **THESE TWO CLASSES AND NOT `Exception`** — the assets loader's
            # judgment, followed rather than re-derived. They are B12 §3's two
            # ways of saying *"this ROW's data is wrong"*, which is the only
            # kind of failure a per-row skip is the right answer to. An
            # `AuthError` would refuse every row identically and hide one
            # permission problem behind a data-quality report; a `SysError` or
            # an `IntegrityError` is a fault nobody would then diagnose.
            rejected_at_write += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _part_write_refusal_sentences(refusal, mapped)
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue
        if result is None:
            _refuse_parts_unwired()

        # THE COUNTERS MOVE AFTER THE WRITE, NEVER BEFORE IT — the assets
        # loader's own note applies here word for word.
        if on_file:
            updated += 1
        else:
            created += 1
            row.created_record_id = result["id"]
        row.outcome = "loaded" if row.outcome != "flagged" else "flagged"
        row.mapped = {
            **mapped,
            LOAD_RESULT: {
                "part_no": result.get("part_no"),
                "name": result.get("name"),
            },
        }
        row.save(update_fields=["outcome", "created_record_id", "mapped", "updated_at"])

    point = None
    if bool(data.get("create_rollback_point", True)):
        point = models.RollbackPoint.objects.create(
            tenant_id=run.tenant_id,
            point_no=_allocate_point_no(),
            run=run,
            expires_at=timezone.now() + timedelta(days=ROLLBACK_DAYS),
            status="available",
        )

    run.write_mode = write_mode
    run.counts = {
        **(run.counts or {}),
        "created": created,
        "updated": updated,
        # Kept at zero rather than dropped: ONE receipt screen renders every
        # target, and a key that is absent on one target and present on another
        # is how a figure comes to mean two things.
        "skipped_existing": 0,
        "rejected_existing": rejected_existing,
        "rejected_at_write": rejected_at_write,
        "unit_tagged": 0,
        "to_inventory": 0,
        "numbers_issued_from_series": 0,
        "deactivated": 0,
        "skipped_occupied": 0,
        "unplanned_units": 0,
        "unplanned_plans": [],
    }
    run.status = "loaded"
    run.finished_at = timezone.now()
    run.save(update_fields=["write_mode", "counts", "status", "finished_at", "updated_at"])
    _audit(
        actor,
        "import_run.loaded",
        run.id,
        run_no=run.run_no,
        write_mode=write_mode,
        created=created,
        updated=updated,
        rejected_existing=rejected_existing,
        rejected_at_write=rejected_at_write,
        rollback_point=getattr(point, "point_no", None),
    )
    return receipt(run)


def _refuse_payments_unwired() -> None:  # pragma: no cover — payments ships in-tree
    """The seam contract's honest failure, `DEF-075`'s rule on the money path.

    ⚠ **AN EMPTY ACCOUNT INDEX IS NOT THIS** — that is a tenant with no
    accounts, which is ordinary, and every row correctly reports that it names
    an account not on file. A module that cannot ANSWER is a deployment fault,
    and the two are told apart by asking for the WRITER, never by the size of a
    read."""
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-MET-096",
        message_key="metering.import.payments_unwired",
    )


def _payment_payload_from(
    mapped: dict[str, Any], *, run: models.ImportRun, row_no: int, recorded_at: Any
) -> dict[str, Any]:
    """The row as `payments.import_writer.create_payment_from_import` takes it.

    ⚠ **THIS KEY SET IS THAT FUNCTION'S SIGNATURE AND NOTHING ELSE** — the
    parts half's lesson, applied before running a file rather than after: a key
    added here that the writer does not take rehearses clean at stage 3 and
    rejects every row of every file at the write.

    ⚠ **THE DATE IS THE FILE'S, AND THE FALLBACK IS THE OPERATOR'S BUSINESS
    DAY, NEVER A CLOCK** (`BR-PAY-033`, `BR-TEN-043`). `OQ-131`'s ruling is
    what makes this load-bearing: a cheque banked on 20 Aug against a bill due
    22 Aug and imported on 25 Aug is **not late**, and reading the import day
    would charge that customer a late fee for money that was in the bank two
    days early.
    """
    paid_on = mapped.get("paid_on")
    return {
        "account_ref": mapped.get("account_ref"),
        "payer_name": mapped.get("payer_name"),
        "amount": mapped.get("amount"),
        "reference": mapped.get("reference"),
        "memo": mapped.get("memo") or f"imported from {run.file_name or 'a remittance file'}",
        "paid_at": _payment_moment(paid_on) if paid_on else None,
        "recorded_at": recorded_at,
        "idempotency_reference": f"{run.id}:{row_no}",
        # Q6 — the store network's name, or None for a lockbox row.
        "network": mapped.get("network"),
    }


def _payment_moment(value: Any) -> Any:
    """A stage-2 date cell → the instant the payment is posted and cleared at.

    Midday in the tenant's own frame rather than midnight, for the reason every
    other date-to-instant conversion in this product takes it: a midnight
    instant lands on the previous DAY in any timezone west of UTC, which would
    silently move an arrival date across a due date.

    ⚠⚠ **A STAGE-2 DATE CELL IS AN ISO *STRING*, AND THIS FUNCTION ANSWERED
    `None` TO EVERY ONE OF THEM UNTIL 2026-09-23 (`DEF-PAY-6294`).**
    `_parse_date` returns `date.fromisoformat(...).isoformat()` — text — and
    `import_run_rows.mapped` stores it as text; a real row of run
    `IMP-260923-02` reads `{"paid_on": "2026-09-19", …}`. The old body tested
    `hasattr(value, "year")`, which is False for a string, so `paid_at` was
    `None` on every row and `create_payment_from_import` fell back to the
    OPERATOR'S BUSINESS DAY. **Measured on a booted stack: 72 payments from a
    file dated 09/19 and 09/20 were all stored `posted_at = cleared_at =
    2026-09-23`** — which is the exact harm `BR-PAY-033` and `OQ-131`'s ruling
    exist to prevent: a customer charged a late fee for money that was in the
    store's till three days early.

    ⚠ **IT SURVIVED TWO TESTS AIMED AT THIS ADAPTER BECAUSE BOTH ASSERT A KEY
    AND NEITHER ASSERTS A VALUE** —
    `test_every_column_reaches_the_payload_and_none_is_dropped_in_the_adapter`
    builds its cells as `f"x-{target}"` and checks `"paid_at" in payload`, which
    is true of a `None`. `tests/test_cr135_p114_lockbox_dates.py` is the one that
    asks what is behind the key, and it was watched fail on this line first.

    ⚠ **AN UNREADABLE CELL IS STILL `None`, DELIBERATELY.** `None` means *the
    file did not say*, and the writer then takes the operator's business day —
    the PO's 2026-08-12 ruling, which *"forgives nothing"*. Widening this to
    guess at `09/19/26` would be `BR-MET-117`'s forbidden sniff on a money path:
    a two-digit year is matched against the tenant's DECLARED format at stage 2
    or not at all (`DEF-MET-6291`), and nothing downstream may second-guess it.
    """
    from datetime import date as _date, datetime, time as _time

    if isinstance(value, datetime):
        return value
    parsed: Any = value
    if isinstance(parsed, str):
        token = parsed.strip()
        if not token:
            return None
        try:
            # ISO ONLY, and that is not a narrowing: this reads what STAGE 2
            # wrote, and stage 2 has already matched the tenant's declared
            # format and normalised it to ISO. Any other spelling arriving here
            # is a cell stage 2 refused, and it must stay refused.
            parsed = _date.fromisoformat(token)
        except ValueError:
            return None
    if not hasattr(parsed, "year"):
        return None
    return timezone.make_aware(datetime.combine(parsed, _time(12, 0)))


#: `payments.import_writer`'s refusal keys → the two sentences a rejected row
#: carries. ⚠ **THE WORDS COME FROM THE `message_key` AND FROM NOTHING ELSE** —
#: the parts and assets halves' rule, followed rather than re-derived. A key
#: with no entry here logs a warning and falls back to the generic pair.
_PAYMENT_REFUSAL_SENTENCES: dict[str, tuple[str, str]] = {
    # ⛔ **`P1.12` — THE ONE THAT CARRIES CS-2 RULE 2 ONTO THE SCREEN.**
    # A name-and-amount guess never commits on its own, and the row has to say
    # why in words a clerk can act on rather than argue with.
    "payments.import.name_only_match": (
        "{row_label} was matched only by the payer's name.",
        "A name is not an account number. Put the account number in the file "
        "and upload it again, or record this one payment by hand.",
    ),
    "payments.import.account_not_on_file": (
        "{row_label} names an account you do not have.",
        "Check the number in the file. If the customer was never migrated, "
        "load the account first and upload this file again.",
    ),
    "payments.import.no_identifier": (
        "{row_label} names no account and no payer.",
        "There is nothing to match this money to. Add the account number to "
        "the row and upload the file again.",
    ),
    "payments.import.amount_missing": (
        "{row_label} carries no readable amount.",
        "Take out currency symbols, spaces and thousands separators; "
        "247.30 rather than $247.30.",
    ),
    "payments.import.amount_not_positive": (
        "The amount on {row_label} is zero or below.",
        "A refund is a different act with different books. Record it on the "
        "account instead of importing it.",
    ),
    # `DEF-PAY-10696` (LBX-06) — an imported payment is recorded under the
    # tenant's Lockbox method, so a tenant that switched it off is told so.
    "payments.import.lockbox_method_off": (
        "{row_label} could not be recorded as a lockbox payment.",
        "Lockbox is off in payment methods. Switch it on, then upload again.",
    ),
    "payments.import.accounts_unwired": (
        "The account list could not be read, so no row could be matched.",
        "Nothing was written. Send the run number on the receipt to support.",
    ),
}

_PAYMENT_REFUSAL_UNKNOWN: tuple[str, str] = (
    "{row_label} was refused when it was written, and the run kept going.",
    "Every other row in the file loaded normally. Send this row to support with "
    "the run number on the receipt — they can see exactly what refused it.",
)


def _payment_write_refusal_sentences(
    exc: errors.ApiError, mapped: dict[str, Any], *, row_no: int | None = None
) -> tuple[str, str]:
    """One caught payments refusal → the two sentences the row carries.

    ⚠ **NO IDS IN EITHER SENTENCE** (CR-016's ruling, gate G28, B14 rule 32).

    ⛔ **THE ROW IS LABELLED BY ITS ROW NUMBER — `DEF-PAY-10756` (L2-08).** It
    was labelled by the first cell it carried (the reference, else the account,
    else the payer), so a refused row read *"Row 30505"* — a cheque number
    printed where the operator looks for a line of their file. The row number
    is what they count by; the cells are on the same line of the failures file.
    """
    facts: dict[str, Any] = {"row_label": f"Row {row_no}" if row_no else "This row"}
    for name, value in (exc.params or {}).items():
        if name.endswith("_id") or value in (None, "", [], {}):
            continue
        facts[name] = (
            ", ".join(str(one) for one in value) if isinstance(value, (list, tuple)) else value
        )
    templates = _PAYMENT_REFUSAL_SENTENCES.get(exc.message_key)
    if templates is None:
        templates = _PAYMENT_REFUSAL_UNKNOWN
        logger.warning(
            "import: no operator sentence for payments refusal key %s (code %s) — "
            "the rejected row carried the generic wording",
            exc.message_key,
            exc.code,
        )
    problem, fix_hint = templates
    try:
        return problem.format(**facts), fix_hint.format(**facts)
    except (KeyError, IndexError, ValueError):  # pragma: no cover — defensive
        return _PAYMENT_REFUSAL_UNKNOWN[0].format(**facts), _PAYMENT_REFUSAL_UNKNOWN[1]


def _load_payments_rows(
    actor: Any,
    run: models.ImportRun,
    write_mode: str,
    data: dict[str, Any],
    reporter: import_progress.Reporter,
) -> dict[str, Any]:
    """The payments commit — every row through payments' own writer, one receipt.

    ⚠ **THE SHAPE IS THE PARTS LOADER'S AND THE DIFFERENCES ARE THREE, EVERY
    ONE OF THEM A RULE RATHER THAN A CONVENIENCE.**

    **1 · There is no `on_file` half and no `upsert`.** A payment may never be
    updated (CLAUDE.md hard rule 4), so *Insert & update* would overwrite money
    on file. `_refuse_payments_write_mode` refuses that mode by name at both
    entry points, and `_key_of` answers `None` for this target, so there is no
    branch here to take.

    **2 · NO ROLLBACK POINT IS CREATED — the `if create_rollback_point` block
    every other loader carries is ABSENT ON PURPOSE (`P1.22`).** A posted
    payment cannot be unwritten; it is REVERSED, which is a new row and a
    different act with different books. Creating a point would put a live
    *Roll back this run* button over a run that cannot be rolled back, and
    `rollback()` refuses this target by name — so a point would be a promise
    nothing can keep. Reads is the only other target that refuses outright.

    **3 · A REFUSED ROW IS REJECTED AND REPORTED, NEVER SKIPPED**
    (`BR-PAY-023`). Money that disappears from a report is money nobody chases.

    ⚠ **ONE SAVEPOINT PER ROW, AND CLAUDE.md LAW 14 IS WHY IT IS NOT
    OPTIONAL.** On PostgreSQL a refused statement aborts the WHOLE transaction,
    so a `try/except` with no nested `atomic()` would lose every payment
    written before the bad one — at COMMIT, silently, with the suite green
    because `config/settings/test.py` hardcodes SQLite, which has no
    aborted-transaction state. `P1.11` proves exactly this on a real
    PostgreSQL 16 with one bad row among four hundred. Do not "simplify" it.
    """
    rows = _loadable_rows(run)
    # ⚠ **READ ONCE, AND SHARED WITH STAGE 3** (`DEF-544`): the rehearsal the
    # operator read and the write they pressed resolve against the same world.
    index = seams.payments_import_index()
    if index is None:
        _refuse_payments_unwired()
    recorded_at = _payment_moment(seams.tenant_today())
    created = rejected_at_write = 0
    reporter.mark(0, "Writing rows")
    for written, row in enumerate(rows, start=1):
        reporter.step(written)
        mapped = dict(row.mapped or {})
        payload = _payment_payload_from(
            mapped, run=run, row_no=row.row_no, recorded_at=recorded_at
        )
        payload["index"] = index

        result: dict[str, Any] | None = None
        try:
            with transaction.atomic():  # ← SAVEPOINT. Law 14. Do not remove.
                result = seams.create_payment_from_import(actor=actor, payload=payload)
                if result is not None:
                    # INSIDE the savepoint: an audit row for a payment that was
                    # rolled back would record money that was never taken.
                    _audit(
                        actor,
                        "payments.created_by_import",
                        result["id"],
                        run_no=run.run_no,
                        row=row.row_no,
                        amount=result.get("amount"),
                    )
        except (errors.BizError, errors.ValidationError) as refusal:
            # ⚠ **THESE TWO CLASSES AND NOT `Exception`** — the parts and assets
            # loaders' judgment, followed rather than re-derived. They are
            # B12 §3's two ways of saying *"this ROW's data is wrong"*, which is
            # the only kind of failure a per-row skip is the right answer to. An
            # `AuthError` would refuse every row identically and hide one
            # permission problem behind a data-quality report.
            rejected_at_write += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _payment_write_refusal_sentences(
                refusal, mapped, row_no=row.row_no
            )
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue
        if result is None:
            _refuse_payments_unwired()

        # THE COUNTERS MOVE AFTER THE WRITE, NEVER BEFORE IT.
        created += 1
        row.created_record_id = result["id"]
        row.outcome = "loaded" if row.outcome != "flagged" else "flagged"
        row.mapped = {
            **mapped,
            LOAD_RESULT: {
                "payment_no": result.get("payment_no"),
                "account_no": result.get("account_no"),
                "amount": result.get("amount"),
            },
        }
        row.save(update_fields=["outcome", "created_record_id", "mapped", "updated_at"])

    # ⚠ **NO `RollbackPoint.objects.create(...)` HERE.** See point 2 above. A
    # lane adding one back has to answer `rollback()`'s refusal first.

    run.write_mode = write_mode
    run.counts = {
        **(run.counts or {}),
        "created": created,
        "updated": 0,
        # Kept at zero rather than dropped: ONE receipt screen renders every
        # target, and a key absent on one target and present on another is how
        # a figure comes to mean two things.
        "skipped_existing": 0,
        "rejected_existing": 0,
        "rejected_at_write": rejected_at_write,
        "unit_tagged": 0,
        "to_inventory": 0,
        "numbers_issued_from_series": 0,
        "deactivated": 0,
        "skipped_occupied": 0,
        "unplanned_units": 0,
        "unplanned_plans": [],
    }
    run.status = "loaded"
    run.finished_at = timezone.now()
    run.save(update_fields=["write_mode", "counts", "status", "finished_at", "updated_at"])
    _audit(
        actor,
        "import_run.loaded",
        run.id,
        run_no=run.run_no,
        write_mode=write_mode,
        created=created,
        updated=0,
        rejected_existing=0,
        rejected_at_write=rejected_at_write,
        rollback_point=None,
    )
    return receipt(run)


def _refuse_assets_unwired() -> None:  # pragma: no cover — assets ships in-tree
    """The seam contract's honest failure: a load that cannot reach the owning
    module's writer REFUSES rather than writing half a file or faking rows."""
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-MET-096",
        message_key="metering.import.assets_unwired",
    )


def _load_assets_rows(
    actor: Any,
    run: models.ImportRun,
    write_mode: str,
    data: dict[str, Any],
    reporter: import_progress.Reporter,
) -> dict[str, Any]:
    """The assets commit — every row through the assets services seam, one
    transaction (the caller's), one receipt.

    BR-AST-045 per row: named unit → created ASSIGNED (the service writes the
    assignment under `uq_asset_assignments_current`, so one-asset-one-current-
    unit is the database's promise); blank → created in INVENTORY. A device
    naming only a premises seats on that premises' one unit (stage 3 already
    rejected the ambiguous cases). `insert` skips an existing number and SAYS
    SO on the row; `upsert` updates its spec fields through the same validator
    an edit uses. `replace` never reaches here (OQ-326 refused in the dry run
    this commit shares — B15 §16 TC-16's one-predicate law).
    """
    rows = _loadable_rows(run)
    index = seams.assets_import_index()
    unit_index = _unit_reference_index()
    premises_units = _premises_units_index()
    today = seams.tenant_today()
    created = updated = tagged = to_inventory = 0
    #: ⛔ **REJECTED, NOT SKIPPED, AND THE PO CHOSE THE WORD (2026-08-27).**
    #: Verbatim: *"Does this row name a meter already on file? if yes - ( in
    #: case of insert - reject it | in case of Insert & Update = update the
    #: details)"*. This counter was `skipped_existing`, and a skip reads on a
    #: receipt as *"left unchanged"* — benign, nothing to do. A reject reads as
    #: *"this row did not load"*, which is what the operator has to act on.
    rejected_existing = 0
    #: How many rows took their number from the tenant's series rather than
    #: from the file — which, since the 2026-08-27 ruling, is every created
    #: row. Counted rather than assumed, so the receipt can state it.
    issued_from_series = 0
    #: ⛔ **CR-047 WIDENING · TASK 20 — rows the WRITER refused, one savepoint
    #: each.** The SAME counter name and the same meaning as the accounts
    #: loader's, because one receipt screen renders every target and a figure
    #: that meant different things on different targets would be worse than no
    #: figure. A DIFFERENT counter from `rejected_existing` above it: those
    #: rows were judged before anything was attempted, and these were
    #: attempted and turned down. A run where this is not zero is a run whose
    #: rehearsal did not see everything — the signal that stage 3 has a rule
    #: to grow.
    rejected_at_write = 0
    numbers_written: list[str] = []
    #: unit id → label, read once on the first UPDATED row (`DEF-AST-8103`).
    unit_labels: dict[str, str] | None = None
    reporter.mark(0, "Writing rows")
    for written, row in enumerate(rows, start=1):
        reporter.step(written)
        mapped = dict(row.mapped or {})
        key = _key_of(run, mapped)
        payload = _asset_payload_from(run.target, mapped)
        on_file = key is not None and key in index
        if on_file and write_mode == "insert":
            rejected_existing += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _insert_mode_on_file_sentences(
                run.target, mapped, index[key]
            )
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue

        unit_id: Any = None
        if not on_file:
            # ⛔ **THE NUMBER NEVER REACHES A CREATE (PO ruling 2026-08-27).**
            # `create_from_import` allocates from the tenant's `asset` series
            # when `asset_no` is absent (BR-AST-026), and honours it when
            # present — so leaving the key on the payload is the whole of the
            # behaviour the ruling removed. Stage 3 already refuses a number
            # that is not on file (`AST.NUMBER_NOT_ON_FILE`) and this branch is
            # only reached when the key matched nothing, so in practice the
            # value is already blank; popping it is the belt to that braces,
            # and it is what makes the guarantee STRUCTURAL rather than a
            # promise two files apart (hard-won law 1).
            payload.pop("asset_no", None)
            # ⛔ **THE MASTER IS RESOLVED HERE, THROUGH THE SAME RESOLVER
            # STAGE 3 JUDGED WITH (`DEF-544`).** The file may name it by our
            # meter number, by its serial, or by the utility's own external
            # reference — and `assets.services._resolve_parent` knows only the
            # first, because until 2026-08-27 that was the only one a file
            # could hold. Rather than teach two modules the same three-way
            # lookup (which is how a rehearsal and a commit come apart), the
            # cell is canonicalised to the master's OWN number before it
            # crosses the seam. Stage 3 has already rejected an unresolvable
            # or ambiguous parent, so a miss here leaves the value untouched
            # and the assets validator refuses it by name.
            # Plan U6 (2026-09-30): a DEVICE's optional parent goes the same way.
            if run.target in (
                TARGET_ASSETS_SUBMETERS,
                TARGET_ASSETS_DEVICES,
            ) and payload.get("parent_asset_no"):
                master = import_rules.resolve_parent_ref(payload["parent_asset_no"], index)
                if master is not None and not master.get("ambiguous"):
                    payload["parent_asset_no"] = master["asset_no"]
            unit_id = _unit_seat_for(run.target, mapped, unit_index, premises_units)
            if unit_id is not None:
                payload["unit_id"] = unit_id
                # The create path requires an install date on an assigned
                # asset (BR-AST-011); a dated file wins, an undated one gets
                # the tenant's today — `create_asset_for_unit`'s own posture.
                payload.setdefault("install_date", str(today))

        # ⛔⛔ **ONE SAVEPOINT PER RECORD — CR-047 WIDENING TASK 20, AND THE
        # DEFECT IS `DEF-2519` LIVE ON THREE MORE TARGETS.**
        #
        # The accounts loader was fixed on 2026-08-29 and this loop had the
        # identical hole: no `try`, no `except` and no savepoint anywhere in
        # it, under stage 4's one outer `transaction.atomic()`. So a refusal
        # from `assets.services._create_asset_inner` escaped the loop and took
        # the whole file with it — and that writer refuses by name at least
        # nineteen ways, four of them ordinary in a real migration: an asset
        # number already on file (BR-AST-033), the utility's own legacy
        # reference used twice (BR-AST-049), an assign-on-create asset with no
        # install date (BR-AST-011), and a service or lookup that is not one of
        # the tenant's own (`VAL_UNKNOWN_LOOKUP`). Any ONE of those on row 63
        # of a 1,846-meter migration left **ZERO** meters on file.
        #
        # PO ruling 2026-08-29, verbatim, and it names no target: *"if it is
        # success then you read next record, if it is fail - you display on
        # screen shich record failed and why (dont write to dB) and continue to
        # uplaod next record"*.
        #
        # ⚠ **A NESTED `atomic()` IS A SAVEPOINT, WHICH IS THE WHOLE POINT.**
        # The refusal is caught OUTSIDE the inner block, so Postgres has
        # already rolled back to the savepoint: this row wrote nothing (the
        # PO's *"dont write to dB"*) — not the asset, not its BR-AST-045
        # assignment row, not its audit entry — the outer transaction is still
        # healthy, and the loop keeps going. CR-026's all-or-nothing property
        # for the RUN is untouched, because that is a property of the OUTER
        # transaction and this sits inside it.
        #
        # ⚠ **IT IS OUR OWN SAVEPOINT AND NOT `create_from_import`'s.** That
        # function opens an `atomic()` of its own, so today the rollback would
        # happen either way — and relying on it would be a guarantee held in
        # another module's body with nothing asserting it here, which is
        # hard-won law 1 exactly. `update_from_import` has no such block at
        # all, so on the update half there would be no savepoint whatsoever.
        #
        # ⚠ **`_refuse_assets_unwired()` IS RAISED OUTSIDE THE `try`, ON
        # PURPOSE.** It is a `BizError` too, and catching it here would turn
        # *"the assets module cannot answer at all"* into 1,846
        # politely-rejected rows — a migration reported as fully judged when
        # nothing was ever asked. That is DEF-075's shape, and it must abort
        # the run exactly as it did before.
        result: dict[str, Any] | None = None
        try:
            with transaction.atomic():
                if on_file:
                    result = seams.update_asset_from_import(
                        actor=actor, asset_no=index[key]["asset_no"], changes=payload
                    )
                    if result is not None and not result.get("assigned_to"):
                        # `DEF-AST-8103` — the unit's LABEL from the index this
                        # run already holds, never a unit read per row.
                        seat = index[key].get("unit_id")
                        if seat:
                            if unit_labels is None:
                                unit_labels = dict(
                                    models.Unit.objects.filter(
                                        tenant_id=run.tenant_id
                                    ).values_list("id", "label")
                                )
                                unit_labels = {str(k): v for k, v in unit_labels.items()}
                            result["assigned_to"] = unit_labels.get(str(seat))
                    if result is not None:
                        # INSIDE the savepoint: an audit row for an asset that
                        # was rolled back would be a record of something that
                        # did not happen.
                        _audit(
                            actor,
                            "assets.updated_by_import",
                            result["id"],
                            run_no=run.run_no,
                            row=row.row_no,
                        )
                else:
                    result = seams.create_asset_from_import(actor=actor, payload=payload)
                    if result is not None:
                        _audit(
                            actor,
                            "assets.created_by_import",
                            result["id"],
                            run_no=run.run_no,
                            row=row.row_no,
                        )
        except (errors.BizError, errors.ValidationError) as refusal:
            # ⚠ **THESE TWO CLASSES AND NOT `Exception`** — the accounts
            # loader's judgment, followed rather than re-derived. `BizError`
            # and `ValidationError` are B12 §3's two ways of saying *"this
            # ROW's data is wrong"*, which is the only kind of failure a
            # per-row skip is the right answer to. Everything else propagates
            # and takes the run down, because none of it is about this row:
            #   · `AuthError` — the actor's role. It would refuse every row
            #     identically, and 1,846 "rejected" rows would hide one
            #     permission problem behind a data-quality report.
            #   · `SysError` — the asset-number series unusable, a lifecycle
            #     stage missing (`assets.stage_missing`). The next row fails
            #     the same way and the registry comes out half-written.
            #   · `NotFoundError` — the cross-tenant 404 `seams.unit_row` and
            #     `service_point_ref` raise. It is not an `ApiError` at all,
            #     and a tenant-boundary denial is never a data-quality note.
            #   · `IntegrityError`, anything unforeseen — a bug or a broken
            #     invariant. Swallowing those is how a migration reports "43
            #     failed" over a fault nobody diagnoses.
            rejected_at_write += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _asset_write_refusal_sentences(
                refusal, run.target, mapped
            )
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue
        except Exception as failure:  # noqa: BLE001 — see the ruling below
            # ⛔⛔ **`DEF-AST-8102` — THE PARAGRAPH ABOVE WAS RIGHT IN PRINCIPLE
            # AND COST A WHOLE UPLOAD IN PRACTICE, SO THE PO RULED IT
            # (2026-09-30, GO on the >200-row defect): a non-rule exception on
            # ONE row rejects THAT row with its reason, and the load continues.**
            # The `AuthError` it names is exactly what happened: a load over the
            # 200-row async bar ran as `_JobActor` (an id, no role, by design),
            # the opening-read helper's role guard refused row 1, the refusal
            # escaped this loop, and the whole run rolled back — 0 written of
            # 201. The cause is fixed at the source (`_create_asset_for_import`)
            # and guarded by a gate; this is the net under it, so that the next
            # unforeseen fault costs one row and not the file.
            #
            # ⚠ **SAFE ON POSTGRESQL ONLY BECAUSE OF THE SAVEPOINT ABOVE (law
            # 14).** The `transaction.atomic()` around the write is a nested
            # savepoint, so a statement that failed inside it has already been
            # rolled back to it and the outer transaction is healthy. Without it
            # this `except` would pass every SQLite test and lose the run on
            # PostgreSQL with `InFailedSqlTransaction`.
            #
            # ⚠ **NOT SWALLOWED:** logged with its traceback for support, and a
            # worker's time limit is re-raised — that is the job's deadline, not
            # this row's data.
            core_jobs.reraise_if_time_limit(failure)
            logger.exception(
                "import %s row %s: unexpected %s — row rejected, load continues",
                run.run_no,
                row.row_no,
                type(failure).__name__,
            )
            rejected_at_write += 1
            row.outcome = "rejected"
            row.problem, row.fix_hint = _asset_unexpected_failure_sentences(
                failure, run.target, mapped
            )
            row.save(update_fields=["outcome", "problem", "fix_hint", "updated_at"])
            continue
        if result is None:
            _refuse_assets_unwired()

        # ⚠ **THE COUNTERS MOVE AFTER THE WRITE, NEVER BEFORE IT.** They used
        # to be incremented on the way INTO the create branch, which was
        # harmless while a refusal killed the run and is a lie the moment one
        # does not: a receipt reading *"1,846 tagged to a unit"* over 1,843
        # assets is the invisible failure this whole change exists to remove.
        if on_file:
            updated += 1
        else:
            created += 1
            issued_from_series += 1
            if unit_id is not None:
                tagged += 1
            else:
                to_inventory += 1
            row.created_record_id = result["id"]
            if result.get("asset_no"):
                numbers_written.append(str(result["asset_no"]))
        row.outcome = "loaded" if row.outcome != "flagged" else "flagged"
        # ⛔ **WHAT THIS ROW ACTUALLY WROTE, RECORDED AS IT IS WRITTEN (CR-047
        # WIDENING TASK 22).** The successes file takes `receipt()`'s posture —
        # *"every figure is what the run RECORDED at the moment it loaded"* —
        # and on this target it has no choice: under the 2026-08-27 ruling the
        # asset's number comes from the tenant's series, so it is NOT on the
        # operator's file and cannot be read back from `mapped` at all. The
        # writer's own answer is the only truthful source.
        row.mapped = {**mapped, LOAD_RESULT: _asset_load_result_from(result)}
        row.save(update_fields=["outcome", "created_record_id", "mapped", "updated_at"])

    # DEF-577 — the shared asset series moves clear of the file's own numbers.
    _catch_up_target_series(actor, run.target, numbers_written)

    point = None
    if bool(data.get("create_rollback_point", True)):
        point = models.RollbackPoint.objects.create(
            tenant_id=run.tenant_id,
            point_no=_allocate_point_no(),
            run=run,
            expires_at=timezone.now() + timedelta(days=ROLLBACK_DAYS),
            status="available",
        )

    run.write_mode = write_mode
    run.counts = {
        **(run.counts or {}),
        "created": created,
        "updated": updated,
        # ⚠ **ZERO, AND THE NEW KEY BESIDE IT IS THE SAME ROWS UNDER THE NAME
        # THE PO GAVE THEM.** Kept rather than deleted because one receipt
        # screen renders every target and the accounts loader still skips.
        "skipped_existing": 0,
        "rejected_existing": rejected_existing,
        # ⛔ CR-047 WIDENING task 20 — see the counter's own note above the
        # loop. `receipt()` already serves this key for every target, so the
        # figure reaches the receipt screen with no change there.
        "rejected_at_write": rejected_at_write,
        "unit_tagged": tagged,
        "to_inventory": to_inventory,
        # PO ruling 2026-08-27 — how many numbers this run took from the
        # tenant's series. It equals `created` by construction today; it is
        # recorded rather than derived so a receipt read a year from now says
        # where those numbers came from without anyone having to know the rule.
        "numbers_issued_from_series": issued_from_series,
        "deactivated": 0,
        "skipped_occupied": 0,
        "unplanned_units": 0,
        "unplanned_plans": [],
    }
    run.status = "loaded"
    run.finished_at = timezone.now()
    run.save(update_fields=["write_mode", "counts", "status", "finished_at", "updated_at"])
    _audit(
        actor,
        "import_run.loaded",
        run.id,
        run_no=run.run_no,
        write_mode=write_mode,
        created=created,
        updated=updated,
        rejected_existing=rejected_existing,
        rejected_at_write=rejected_at_write,
        unit_tagged=tagged,
        to_inventory=to_inventory,
        rollback_point=getattr(point, "point_no", None),
    )
    return receipt(run)


def _allocate_point_no() -> str | None:
    """r10 draws `RB-2813`. ⚠ There is no rollback numbering SERIES in
    `core.numbering`'s known set, and inventing a format here would be the
    hard-coded vocabulary B12 forbids — so the point falls back to its own id
    and the receipt prints that. A series can be added later without moving a
    row: nothing keys off the label."""
    return None


# ═══════════════════════════════════════════════════════════════════════════
# CR-047 TASK 13 — THE TWO FILES A MIGRATION COMES OUT AS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **PO ruling 2026-08-29, verbatim:** *"at the end we need 2 CsV file 1 for
# success record and other for failed records"*.
#
# ⚠ **THE FAILURES FILE IS THE ORIGINAL FILE PLUS TWO COLUMNS, AND THAT IS THE
# WHOLE DESIGN RATHER THAN A CONVENIENCE.** The operator's next act is to fix
# the rows and upload again. If we hand them OUR column names, OUR quoting and
# OUR column order they have to re-map a file they already had mapped — so the
# rejects come back under the file's own headers, in the file's own order,
# carrying the row's own cells, with `why_it_failed` and `how_to_fix_it`
# appended. They delete two columns and re-upload the spreadsheet they know.
#
# ⚠ **`raw`, NOT `mapped`.** `ImportRunRow.raw` is the row *"AS EXTRACTED,
# never coerced"* — a date the transform could not read is still the text the
# operator typed, and a value stage 2 dropped is still there. `mapped` is our
# reading of the row and would silently hand back a corrected file that was
# never corrected.
#
# ⚠ **NOTHING IS RE-DERIVED ON EITHER FILE.** The successes file reads what the
# load RECORDED on each row (`LOAD_RESULT`), exactly as `receipt()` reads what
# the run recorded — *"a receipt that said 245 loaded in August must still say
# it in December"*. In particular the opening total is `create_from_import`'s
# own figure and is never re-summed from the four `ob_*` cells: `import_writer`
# splits a negative bucket into a carried credit (BR-CUS-061), so a second sum
# would disagree with the ledger on precisely the rows that matter.

#: The two appended columns, in this order. Named as constants because the
#: header row and the per-row writer must not be able to drift apart.
FAILURE_REASON_COLUMN = "why_it_failed"
FAILURE_FIX_COLUMN = "how_to_fix_it"

#: `kind=` → the outcomes it serves. **The two sets PARTITION every row a run
#: holds**, so a row cannot be missing from both files: `staged` is in neither
#: list only because a loaded run has none — stage 4 leaves every row in one of
#: these six states. `duplicate` and `skipped` are FAILURES, not omissions: the
#: operator asked for them to be dropped, the row did not load, and it is
#: exactly the row they need back in order to decide whether that was right.
RESULT_KINDS: dict[str, tuple[str, ...]] = {
    "successes": ("loaded", "flagged"),
    "failures": ("rejected", "skipped", "duplicate"),
}

#: The successes file's own columns for the ACCOUNTS target, in order. Five,
#: and each one answers a question the operator asked of the file they
#: uploaded: *did this account land, under whose name, on which unit, carrying
#: what, ready to bill?*
SUCCESS_COLUMNS: tuple[str, ...] = (
    "account_number",
    "customer_name",
    "unit_reference",
    "opening_balance_total",
    "services_inherited",
)

# ═══════════════════════════════════════════════════════════════════════════
# CR-047 WIDENING · TASK 22 — ONE COLUMN SET PER TARGET
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **THE ENDPOINT IS KEYED BY RUN, SO IT ALREADY SERVED ALL SIX TARGETS —
# WITH THE ACCOUNTS TARGET'S COLUMNS.** A premises run downloaded its
# successes file and got `account_number,customer_name,unit_reference,…` with
# every cell empty, which is worse than no file: it reads as *"nothing
# landed"* over a migration that landed everything. Same shape as DEF-320's
# *"a path that looks handled and communicates nothing"*.
#
# ⚠ **THE `failures` FILE IS UNCHANGED AND IS THE SAME ON EVERY TARGET.** It
# is the operator's original row, byte for byte, in the file's own column
# order, plus exactly two appended columns — that rule is absolute and it is
# what makes the file re-uploadable. Only the SUCCESSES half differs per
# target, because only it is OUR summary of what we wrote.
#
# ⚠ **EVERY CELL IS READ FROM WHAT THE LOADER RECORDED ON THE ROW
# (`LOAD_RESULT`), NEVER RE-DERIVED.** On five of the six targets it could not
# be re-derived anyway: under the PO's ruling of 2026-08-27 the premise, unit
# and asset numbers all come from the tenant's own series, so the number that
# identifies the record is NOT on the operator's file and exists only in what
# the writer answered.

#: `target` → the successes file's columns, in order. Six entries, one per
#: member of `TARGETS`; `_success_cells` below is the only reader and the two
#: are kept adjacent so a column and its value cannot drift apart.
SUCCESS_COLUMNS_BY_TARGET: dict[str, tuple[str, ...]] = {
    # What an operator asks of a premises file: *which address landed, under
    # what number, offering which services, and does it have an owner?* The
    # last two are the ones that matter after a migration — a premises
    # offering nothing refuses every meter two uploads later
    # (`premises_with_no_services`), and one with no owner has nobody to
    # charge (`premises_with_no_owner`, the PO's 2026-08-27 narrowing). Both
    # are receipt COUNTS today; this is the list behind the count.
    TARGET_PREMISES: (
        "premise_number",
        "address",
        "city",
        "services_offered",
        "owner",
    ),
    # For a unit: *which unit landed, under what number, at which premises, on
    # what plan?* The plan cell is blank exactly when the unit loaded WITHOUT
    # one — BR-MET-100's ruled-lawful state, whose cost the PO was told in
    # plain English: *"a unit with no plan does not fail — it simply never
    # appears on a bill."* A blank cell here is that unit, by name.
    TARGET_UNITS: (
        "unit_number",
        "unit_label",
        "premises_reference",
        "rate_plan",
    ),
    # For an asset: *which meter landed, under what number, of what kind, on
    # which unit, measuring what?* A blank unit cell is an asset that went to
    # inventory rather than onto a seat (BR-AST-045), which is lawful and is
    # the thing an operator most often wants to check.
    #
    # ⛔ **IN THE SIX-GROUP ORDER SINCE 2026-09-30, AND WIDER (plan U8, PO:
    # every downloaded file follows the plan tables' order).** Identity ·
    # Location · Service and billing — the same order the template and the
    # sample print — then `billing_changes`: every 💲 field a RE-UPLOAD changed
    # on this asset, old → new (PO: *"we need to override it in case of
    # upload"*, with the result file naming each override so none is silent).
    # Blank on a created row, and blank on an update that moved no bill.
    #
    # ⚠ **THE SUB-METERS SET CARRIES ITS MASTER AND THE DEVICES SET ITS LINKED
    # METER, AND THAT IS WHY THIS IS A MAP RATHER THAN ONE LIST WITH A BRANCH
    # IN IT.** A sub-meter's share is worked out FROM its master (BR-AST-003),
    # and the runner canonicalises that cell before the write, so the file's
    # own value and the one actually linked are not always the same string.
    TARGET_ASSETS_METERS: (
        "asset_number",
        "asset_type",
        "external_reference",
        "serial_number",
        "unit_assigned",
        "service",
        "connection_size",
        "unit_of_measure",
        "multiplier",
        "net_metering",
        "register_digits",
        "billing_changes",
    ),
    TARGET_ASSETS_SUBMETERS: (
        "asset_number",
        "asset_type",
        "external_reference",
        "serial_number",
        "unit_assigned",
        "master_meter",
        "service",
        "unit_of_measure",
        "multiplier",
        "allocation_share_pct",
        "allocation_rule",
        "loss_tolerance_pct",
        "register_digits",
        "billing_changes",
    ),
    TARGET_ASSETS_DEVICES: (
        "asset_number",
        "asset_type",
        "external_reference",
        "serial_number",
        "unit_assigned",
        "linked_meter",
        "service",
        "size",
        "unit_of_measure",
        "export_capacity_kw",
        "billing_changes",
    ),
    TARGET_ACCOUNTS: SUCCESS_COLUMNS,
    # ⛔ **`DEF-PAY-10756` (L2-08).** The payments target had no entry and fell
    # through to the PREMISES cells, so *"Download the payments that loaded"*
    # gave premises headings over empty cells — read by the tester as *"0
    # records"*. What a clerk asks of a loaded payment: which number, whose
    # account, how much, which receipt, which day.
    TARGET_PAYMENTS: (
        "payment_number",
        "account_number",
        "amount",
        "reference",
        "date_paid",
    ),
}

#: The payments download's headings, in the template's words (`Account #`,
#: `Amount`, `Reference`, `Date paid`) so the two files read alike.
PAYMENTS_SUCCESS_HEADERS = ("Payment #", "Account #", "Amount", "Reference", "Date paid")

#: How many rows are read from the database at a time while a file streams.
#: `.iterator(chunk_size=…)` keeps a 100,000-row download off the heap — the
#: CR-026 file sizes the PO named (*"50,000 or 100,000 units or premises at a
#: time"*) are the sizes this has to survive, and a `list()` of them is the
#: 4.28 MB payload DEF-766 measured, times twenty.
RESULT_CSV_CHUNK = 1000

#: ⛔ **`DEF-AST-8363` — THE ASSET RESULT FILE IS HEADED IN THE TEMPLATE'S OWN
#: WORDS.** `SUCCESS_COLUMNS_BY_TARGET` names are LOOKUP KEYS for
#: `_success_cells`, and until 2026-09-30 they were also printed as the header
#: row — so the operator who filled in `Device number` and `Unit` got back
#: `asset_number` and `unit_assigned`, while the template, the sample and the
#: rejected-rows file all said the labels. Each key names the sheet FIELD it
#: reports, and the header prints that field's label from the same
#: `EXPLICIT_COLUMNS_BY_TARGET` the template prints — one source, so the two
#: cannot drift. `billing_changes` is the one result-only column and has no
#: template field; it is named here.
SUCCESS_COLUMN_FIELD: dict[str, str] = {
    "asset_number": "asset_no",
    "asset_type": "type",
    "external_reference": "external_ref",
    "serial_number": "serial_no",
    "unit_assigned": "unit_ref",
    "master_meter": "parent_asset_no",
    "linked_meter": "parent_asset_no",
    "service": "service",
    "connection_size": "size_class",
    "size": "size_class",
    "unit_of_measure": "unit",
    "multiplier": "multiplier",
    "net_metering": "net_metering",
    "register_digits": "register_digits",
    "allocation_share_pct": "allocation_share_pct",
    "allocation_rule": "allocation_rule",
    "loss_tolerance_pct": "loss_tolerance_pct",
    "export_capacity_kw": "export_capacity_kw",
}
BILLING_CHANGES_HEADER = "Billing changes"


def success_headers(target: str) -> list[str]:
    """The successes file's header row for one target, as a person reads it.

    The three asset sheets print each column's TEMPLATE label (`DEF-AST-8363`);
    a column whose field the sheet does not declare — the meters sheet has no
    `type` column, so its `asset_type` — is labelled `Asset type`, never left
    as a key. Every other target keeps the header it has always printed.
    """
    columns = SUCCESS_COLUMNS_BY_TARGET.get(target, SUCCESS_COLUMNS)
    if target == TARGET_PAYMENTS:
        return list(PAYMENTS_SUCCESS_HEADERS)
    if target not in ASSETS_TARGETS:
        return list(columns)
    labels = {
        column["target"]: column["label"] for column in EXPLICIT_COLUMNS_BY_TARGET[target]
    }
    fallback = {"asset_type": "Asset type", "billing_changes": BILLING_CHANGES_HEADER}
    return [
        labels.get(SUCCESS_COLUMN_FIELD.get(name, ""))
        or fallback.get(name)
        or name.replace("_", " ").capitalize()
        for name in columns
    ]


def _load_result_from(result: dict[str, Any]) -> dict[str, Any]:
    """What `customers.create_from_import` just wrote, as the row will keep it.

    Small on purpose: five facts, all of them the writer's own answer rather
    than anything re-derived from the file. `services_linked` is read
    defensively for the reason `with_services` states — a build where the
    customers half has not landed returns no such key, and `0` is *"the writer
    did not say"*, never a claim that no services were linked.
    """
    return {
        "account_no": result.get("account_no"),
        "customer_no": result.get("customer_no"),
        "opening_total": result.get("opening_total"),
        "opening_empty": bool(result.get("opening_empty")),
        "services_linked": int(result.get("services_linked") or 0),
    }


def _asset_load_result_from(result: dict[str, Any]) -> dict[str, Any]:
    """What `assets.services.create_from_import` / `update_from_import` just
    wrote, as the row will keep it (CR-047 widening task 22).

    Small on purpose, and every value is the WRITER's own answer. The number in
    particular cannot come from anywhere else: under the PO's ruling of
    2026-08-27 a created asset takes it from the tenant's `asset` series, so
    the operator's file does not carry it and `mapped` never will.

    `.get` throughout rather than `[…]`: this reads another module's dict
    across a seam, and a build where a key has not landed yet must produce an
    empty cell — *"the run did not say"* — never a `KeyError` that takes a
    whole migration down after it has already written every row.
    """
    return {
        "asset_no": result.get("asset_no"),
        # `type_name` is the tenant's own word for it ("Meter", "Sub-meter");
        # `type` is the code behind it and is the fallback, not the first
        # choice, because the file is read by a person.
        "asset_type": result.get("type_name") or result.get("type"),
        # The unit's LABEL, which is what the operator typed — `assigned_to`.
        # `assigned_unit_id` is a uuid and is deliberately not carried.
        "unit_assigned": result.get("assigned_to"),
        "service": result.get("service"),
        "serial_no": result.get("serial_no"),
        "parent_asset_no": result.get("parent_asset_no"),
        # ⛔ Plan U8 (PO 2026-09-30) — the new and 💲 fields, as WRITTEN.
        "external_ref": result.get("external_ref"),
        "size_class": result.get("size_class"),
        "unit": result.get("unit"),
        "multiplier": result.get("multiplier"),
        "net_metering": result.get("net_metering"),
        "register_digits": result.get("register_digits"),
        "allocation_share_pct": result.get("allocation_share_pct"),
        "allocation_rule": result.get("allocation_rule"),
        "loss_tolerance_pct": result.get("loss_tolerance_pct"),
        "export_capacity_kw": result.get("export_capacity_kw"),
        # Every 💲 field a re-upload CHANGED, old → new — `[]` on a create.
        "billing_changes": list(result.get("billing_changes") or []),
    }


def _generic_load_result_from(
    target: str, record: dict[str, Any], mapped: dict[str, Any]
) -> dict[str, Any]:
    """What the premises/units write just put in the table (CR-047 widening
    task 22).

    ⚠ **`record`, NOT `mapped`.** `record` is the dict that was handed to
    `objects.create(...)`, so it holds the number the series ISSUED — which is
    the whole point, because under the 2026-08-27 ruling that number is not on
    the operator's file at all. The two REFERENCE cells (`premises_ref`,
    `rate_plan_ref`) come from `mapped` instead, because `record` holds only
    their resolved uuids and a uuid is never printed at an operator.
    """
    if target == TARGET_UNITS:
        return {
            "unit_no": record.get("unit_no"),
            "label": record.get("label"),
            "premises_ref": mapped.get("premises_ref"),
            # ⚠ **THE PLAN CELL IS THE OPERATOR'S OWN, AND IT IS CARRIED ONLY
            # WHEN THE PLAN ACTUALLY LINKED.** A unit may load with no plan
            # (BR-MET-100) and the file's cell may name a plan that resolved to
            # nothing — writing that cell anyway would tell the operator the
            # unit is on a plan it is not on, which is the one thing this
            # column exists to answer.
            "rate_plan_ref": mapped.get("rate_plan_ref") if record.get("rate_plan_id") else None,
        }
    return {
        "premise_no": record.get("premise_no"),
        "address": record.get("address_line"),
        "city": record.get("city"),
        "services": list(record.get("services_available") or []),
        # ⚠ **THE OWNER CELL AS WRITTEN, BLANK WHEN THERE IS NONE — AND THE
        # BLANK IS THE POINT.** PO ruling 2026-08-27 lets a premises load with
        # no owner, and the cost is that the address has nobody to charge.
        # `premises_with_no_owner` counts them; this names them.
        "owner": str(record.get("owner_manager") or mapped.get("owner_manager") or "").strip()
        or None,
    }


def _refuse_results_not_loaded(run: models.ImportRun) -> None:
    """A run with no result has no result file — refused BY NAME, not by an
    empty download.

    ⚠ **A ZERO-ROW CSV WOULD BE THE WORSE ANSWER AND IT IS WORTH SAYING WHY.**
    An operator who clicks *Failed rows* on a run that has not loaded and gets
    a file with a header and nothing under it reads *"nothing failed"* — the
    exact shape of DEF-320, *"a path that looks handled and communicates
    nothing"*. A refusal names the state instead.

    ⛔ **ITS OWN KEY, BECAUSE THE PREDICATE IS SHARED AND THE SENTENCE IS NOT
    (CR-047 widening lane, 2026-08-29).** This refusal and the rollback door's
    ask the identical question (`run.status != "loaded"`) and carry the
    identical `br_ref`, and until today they shared
    `metering.import.not_loaded` as well — whose English ends *"…so there is
    nothing to reverse."* That tail is right at the rollback door and WRONG
    here: an operator clicking *Failed rows* is not trying to reverse
    anything, and a sentence about reversing a run tells them their download
    failed for a reason that has nothing to do with what they asked for.
    So the download refusal carries `metering.import.not_loaded_no_download`
    — *"That run has not been loaded, so there is nothing to download."* — and
    the rollback door keeps the key it had.

    ⚠ **THE SENTENCE IS TWELVE WORDS AND THAT IS NOT AN ACCIDENT.** `G33` caps
    a refusal at twelve, and the obvious wording — *"…nothing to download
    yet"* — is thirteen. The `yet` was the first word to go because the two
    doors' sentences should read as the same sentence with one clause changed,
    which is what tells a reader they are the same refusal.

    ⚠ **THE TWO KEYS MUST NOT BE MERGED BACK.** Two doors asking one question
    is not two doors needing one sentence: the shared half is the PREDICATE,
    which is why both live behind `run.status != "loaded"`, and the half that
    differs is the only half the operator reads.
    """
    if run.status != "loaded":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-090",
            message_key="metering.import.not_loaded_no_download",
        )


#: A run whose rows have been JUDGED. Stage 3 writes `outcome`, `problem` and
#: `fix_hint` on every row it refuses, so from `validated` onward the failures
#: file has real content; before that every row is undecided and the file would
#: be a header with nothing under it.
DECIDED_STATUSES = ("validated", "loaded", "rolled_back")


def _refuse_failures_not_decided(run: models.ImportRun) -> None:
    """The FAILURES half is offered as soon as any row has been decided —
    `DEF-2487`, and the reason is the moment it was missing.

    ⛔ **THE ONE MOMENT A PERSON MOST NEEDS THE LIST OF WHAT FAILED WAS THE ONE
    MOMENT THE PRODUCT WOULD NOT GIVE IT.** Both result files hung off the
    stage-5 Result screen, which a failed commit never reaches, and the download
    door refused anything that had not `loaded`. So an operator whose load fell
    over was left on stage 4 with a number — *"Rows rejected 41"* — and no way
    to see WHICH 41 or why, which is the only thing that lets them fix the file
    and try again.

    ⚠ **THE SUCCESSES HALF STILL REQUIRES A LOAD, AND THAT IS NOT AN
    OVERSIGHT.** Before the commit nothing has loaded, so *"download the rows
    that loaded"* over a validated run would hand back a header and no rows —
    `_refuse_results_not_loaded`'s own argument, which is that an empty file
    reads as an ANSWER. A failures file for a validated run is not empty and not
    ambiguous: it is exactly the rows stage 3 refused, with the reason and the
    fix already written on each one.
    """
    if run.status not in DECIDED_STATUSES:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-090",
            message_key="metering.import.not_checked_no_download",
        )


def _result_rows(run: models.ImportRun, outcomes: tuple[str, ...]) -> Any:
    """The run's rows for one half of the partition, oldest row number first,
    STREAMED. `.only()` because neither file reads a column it does not name,
    and `raw`/`mapped` are the two big ones."""
    return (
        models.ImportRunRow.objects.filter(
            tenant_id=run.tenant_id, run=run, outcome__in=outcomes
        )
        .only("row_no", "raw", "mapped", "outcome", "problem", "fix_hint")
        .order_by("row_no")
        .iterator(chunk_size=RESULT_CSV_CHUNK)
    )


def _source_headers(run: models.ImportRun) -> list[str]:
    """The uploaded file's OWN header row, in the file's own order.

    ⛔⛔ **THIS READ THE ORDER OUT OF A PLACE THAT CANNOT KEEP IT (`DEF-2513`),
    AND THE FIX IS THE WHOLE OF `BR-CUS-673`'s "NOT RE-ORDERED".**

    The version this replaces returned `[str(h) for h in (row_1.raw or {})]` and
    argued, correctly for Python and wrongly for the database:

        "`extract` builds every row's `raw` as `{header: value for header in
         headers}` from one `csv.DictReader`, so row 1's key order IS the file's
         column order."

    `raw` is a `JSONField`. Postgres stores it as **jsonb**, and jsonb does not
    preserve OBJECT key order — it re-sorts by key length, then bytewise. So a
    file whose first column is `UNIT_REF` came back starting `ACCT`, `NAME`, and
    the operator's own row was returned re-ordered. That breaks the one job the
    failures file has: **fix two cells in the spreadsheet you already know and
    upload that file again.** Re-ordered columns make it unusable, and the
    operator must reconcile a file we handed them.

    ⚠ **IT ALSO EXPLAINS WHY THE TESTS DISAGREED ACROSS LANES** — 23/23 green in
    one worktree, 2 failures reported by another, 4 on the merged branch. Same
    code; different key ordering coming back from a different database state. A
    defect that depends on how the store happened to lay out a dictionary reads
    as flakiness until it is pinned.

    **The order now comes from `mapping_spec["source_headers"]`, written at
    extract as a LIST — because jsonb ARRAYS are ordered and only objects are
    not.** Same store, a shape it can keep.

    ⚠ **THE FALLBACK IS DELIBERATE AND IS NOT THE OLD BEHAVIOUR RESTORED.** A run
    extracted BEFORE this change has no stored order, and there is nowhere else
    the true order survives — so the old derivation is the only thing left. It is
    kept, named, and reported as approximate rather than silently returning a
    wrong order that looks right. A historical run's failures file is still
    downloadable; its columns may be re-sorted, which is what was already true of
    it.

    A run with no headers at all (an empty file) yields the two appended columns
    alone — a header and no rows, which is what an empty file honestly produces.
    """
    stored = (run.mapping_spec or {}).get("source_headers")
    if stored:
        # The file's own order, as `extract` read it off the header row.
        return [str(header) for header in stored]

    # ── Pre-`DEF-2513` runs only. See the docstring: this is the derivation the
    # defect was filed against, kept because for those rows nothing better
    # exists — not because it is correct.
    # ⚠ `BR-MET-1032` — the vault is a reserved key, never a column of the
    # operator's file, so it is excluded below. Nothing that reached this
    # fallback can carry one (it only fires for runs extracted before
    # `DEF-2513`, which predate the vault by weeks); the filter is here so that
    # stays true rather than because it is currently reachable.
    first = (
        models.ImportRunRow.objects.filter(tenant_id=run.tenant_id, run=run)
        .order_by("row_no")
        .values_list("raw", flat=True)
        .first()
    )
    return [str(header) for header in (first or {}) if header != import_identity.VAULT]


def _csv_line(values: list[Any]) -> str:
    """One CSV line, quoted by `csv` itself.

    ⚠ **A ROW IS WRITTEN THROUGH `csv.writer`, NEVER JOINED WITH COMMAS.** A
    customer name is `"Harmon, Luis"` on the very first row of the CR-030
    fixture, and a hand-joined line would split that account across two
    columns in the file the operator re-uploads.

    `\\r\\n` is the `csv` module's own default terminator and is what Excel
    expects; nothing here trims it.
    """
    buffer = io.StringIO()
    csv.writer(buffer).writerow(["" if value is None else value for value in values])
    return buffer.getvalue()


def _plain_number(value: Any) -> str | None:
    """`1.000000` → `1`, `12.500000` → `12.5` — a stored decimal as a person
    reads it in a spreadsheet. Blank stays blank; a non-number passes as is."""
    if value in (None, ""):
        return None
    try:
        return format(Decimal(str(value)).normalize(), "f")
    except (InvalidOperation, ValueError):
        return str(value)


def _billing_changes_cell(target: str, changes: Any) -> str | None:
    """⛔ **PLAN U8 — EVERY 💲 CHANGE A RE-UPLOAD MADE, OLD → NEW, IN ONE CELL**
    (PO 2026-09-30: a re-upload OVERRIDES billing fields, and the result file
    says so per asset so an override is never silent). Each change is named by
    the sheet's own column LABEL — `Multiplier: 1 → 2; Connection size: W-58 →
    W-2` — because the file is read by a person, and a blank old value prints
    as `(blank)` rather than as nothing. `None` when nothing moved a bill."""
    labels = {
        column["target"]: column["label"] for column in EXPLICIT_COLUMNS_BY_TARGET.get(target, ())
    }
    parts = []
    for change in changes or ():
        field_name = str(change.get("field") or "")
        old = str(change.get("old") or "") or "(blank)"
        new = str(change.get("new") or "") or "(blank)"
        parts.append(f"{labels.get(field_name, field_name)}: {old} → {new}")
    return "; ".join(parts) or None


def _success_cells(target: str, mapped: dict[str, Any], loaded: dict[str, Any]) -> list[Any]:
    """One loaded row → the cells its target's successes file names, in order.

    ⚠ **IT MUST RETURN EXACTLY AS MANY CELLS AS `SUCCESS_COLUMNS_BY_TARGET`
    DECLARES**, or every column after the short one shifts and the file lies
    quietly. `_successes_csv` asserts it on the header rather than trusting it
    (hard-won law 1), because a shifted CSV passes every test that only counts
    rows.
    """
    if target == TARGET_ACCOUNTS:
        return [
            # The number the account carries. It is the writer's answer and not
            # the file's cell: under the PO's 2026-08-27 ruling the two are the
            # same on this target, and reading the writer's keeps this file
            # honest if that ever changes again.
            loaded.get("account_no") or mapped.get("account_no"),
            mapped.get("customer_name"),
            mapped.get("unit_ref"),
            # ⚠ **THE WRITER'S OWN TOTAL, CARRIED.** Never re-summed from the
            # four `ob_*` cells — see this section's header. A row loaded
            # before CR-047 recorded none, and an empty cell says *"the run did
            # not say"* rather than claiming $0.00.
            loaded.get("opening_total"),
            loaded.get("services_linked") if loaded else None,
        ]
    if target in ASSETS_TARGETS:
        # ⛔ Plan U8 — ONE cell per `SUCCESS_COLUMNS_BY_TARGET` name, looked up
        # by NAME rather than appended by branch, so the six-group order lives
        # in exactly one place and a cell cannot land under the wrong heading.
        net = loaded.get("net_metering")
        cell_by_name: dict[str, Any] = {
            "asset_number": loaded.get("asset_no"),
            "asset_type": loaded.get("asset_type"),
            "external_reference": loaded.get("external_ref"),
            "serial_number": loaded.get("serial_no"),
            # Blank means INVENTORY — lawful, and the thing an operator most
            # often wants to check after a meter migration (BR-AST-045).
            "unit_assigned": loaded.get("unit_assigned"),
            # The master the row was actually hung on, canonicalised by the
            # runner before the write, so this is not always the file's own
            # spelling of it.
            "master_meter": loaded.get("parent_asset_no"),
            "linked_meter": loaded.get("parent_asset_no"),
            "service": loaded.get("service"),
            "connection_size": loaded.get("size_class"),
            "size": loaded.get("size_class"),
            "unit_of_measure": loaded.get("unit"),
            "multiplier": _plain_number(loaded.get("multiplier")),
            "net_metering": None if net is None else ("yes" if net else "no"),
            "register_digits": loaded.get("register_digits"),
            "allocation_share_pct": _plain_number(loaded.get("allocation_share_pct")),
            "allocation_rule": loaded.get("allocation_rule"),
            "loss_tolerance_pct": _plain_number(loaded.get("loss_tolerance_pct")),
            "export_capacity_kw": _plain_number(loaded.get("export_capacity_kw")),
            "billing_changes": _billing_changes_cell(target, loaded.get("billing_changes")),
        }
        return [cell_by_name.get(name) for name in SUCCESS_COLUMNS_BY_TARGET[target]]
    if target == TARGET_PAYMENTS:
        # The writer's own answer for the number, account and amount
        # (`LOAD_RESULT`); the reference and the day are the file's, as stage 2
        # read them. Money shows 2 places (hard rule 2).
        return [
            loaded.get("payment_no"),
            loaded.get("account_no") or mapped.get("account_ref"),
            _money_2(loaded.get("amount") or mapped.get("amount")),
            mapped.get("reference"),
            mapped.get("paid_on"),
        ]
    if target == TARGET_UNITS:
        return [
            loaded.get("unit_no"),
            loaded.get("label") or mapped.get("label"),
            loaded.get("premises_ref") or mapped.get("premises_ref"),
            # Blank exactly when the unit loaded with NO plan (BR-MET-100).
            loaded.get("rate_plan_ref"),
        ]
    return [
        loaded.get("premise_no"),
        loaded.get("address") or mapped.get("address_line"),
        loaded.get("city") or mapped.get("city"),
        # A list would print its brackets and quotes at the operator; it is
        # their own vocabulary, so it is printed as words.
        ", ".join(str(item) for item in (loaded.get("services") or [])),
        # Blank means this address has nobody to charge (PO 2026-08-27).
        loaded.get("owner"),
    ]


def _money_2(value: Any) -> Any:
    """A stored amount (`253.0000`) as a person reads it (`253.00`) — hard rule
    2's *display 2*. An unreadable value passes through rather than vanishing."""
    if value in (None, ""):
        return value
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError, ArithmeticError):
        return value


def _successes_csv(run: models.ImportRun) -> Any:
    """The records that LANDED, one line each — a generator, never a list.

    ⚠ **THE COLUMNS ARE THIS RUN'S TARGET'S** (CR-047 widening task 22). The
    endpoint is keyed by RUN and always served every target; until today it
    served all six under the accounts columns, so a premises run downloaded
    five empty accounts columns and read them as *"nothing landed"*.
    """
    target = run.target
    columns = SUCCESS_COLUMNS_BY_TARGET.get(target, SUCCESS_COLUMNS)
    # `DEF-AST-8363`: the header is the template's words; `columns` stays the
    # cell LOOKUP (and the width the assertion below holds every row to).
    yield _csv_line(success_headers(target))
    for row in _result_rows(run, RESULT_KINDS["successes"]):
        mapped = row.mapped or {}
        loaded = mapped.get(LOAD_RESULT) or {}
        cells = _success_cells(target, mapped, loaded)
        # ⚠ **THE WIDTH IS ASSERTED, NOT ASSUMED.** A row one cell short shifts
        # every column after it and still parses as a CSV — it passes any test
        # that counts rows, and an operator reads a wrong value under a right
        # heading. Padding is the honest repair: a missing cell is empty, and
        # nothing moves.
        if len(cells) < len(columns):  # pragma: no cover — defensive
            cells = [*cells, *([None] * (len(columns) - len(cells)))]
        yield _csv_line(cells[: len(columns)])


def _asset_ordered_headers(
    target: str, headers: list[str], columns: dict[str, Any]
) -> list[str]:
    """⛔ **THE ASSET SHEETS' FAILURES FILE FOLLOWS THE SIX-GROUP ORDER (PO
    confirmation 2026-09-30, `DEF-AST-8101`).** Verbatim from the coordinator's
    relay of the ruling: every DOWNLOADED file — the template, the sample, the
    error/rejected-rows file and the result file — follows the plan tables'
    column order.

    ⚠ **THIS NARROWS `BR-CUS-673`'s "NOT RE-ORDERED" FOR THE THREE ASSET
    TARGETS AND FOR NOTHING ELSE**, and it does not break what that rule
    protects: the CELLS still travel byte for byte under their OWN headers, so
    the file still re-uploads (stage 1 maps by header name, never by position).
    Only the column ORDER moves: a header the operator mapped to a sheet column
    takes that column's place in the plan; a header mapped to nothing (ignored,
    or a custom field) keeps its own relative order AFTER them. A file built
    from our template was already in this order, so for it nothing moves.
    """
    order = {name: index for index, name in enumerate(asset_column_order(target))}
    tail = len(order)

    def position(item: tuple[int, str]) -> tuple[int, int]:
        index, header = item
        entry = columns.get(header)
        field_name = entry.get("target") if isinstance(entry, dict) else entry
        return (order.get(str(field_name or ""), tail), index)

    return [header for _, header in sorted(enumerate(headers), key=position)]


def _failures_csv(run: models.ImportRun) -> Any:
    """The rows that did NOT land: the original row, plus two columns.

    ⚠ **THE ORIGINAL CELLS TRAVEL UNCHANGED AND UNREORDERED.** `raw.get(header)`
    for each of the file's own headers, in the file's own order — nothing is
    re-derived from `mapped`, nothing is re-formatted, and a header the row
    happens not to carry writes an empty cell rather than shifting every column
    after it.
    """
    headers = _source_headers(run)
    if run.target in ASSETS_TARGETS:
        headers = _asset_ordered_headers(
            run.target, headers, ((run.mapping_spec or {}).get("columns")) or {}
        )
    # ⛔ **`BR-MET-1032` — THIS FILE CARRIES THE WHOLE NUMBER, AND THAT IS THE
    # PO's OWN RULING RATHER THAN AN EXEMPTION FROM IT.** *"in spreadsheet we
    # will porvide entire SSN number if required"* (2026-09-01). This IS a
    # spreadsheet: it is the operator's own rows handed back so they can fix two
    # cells and upload the file again, which is the one job it has
    # (`BR-CUS-673`). Writing `••••6789` here would be redaction that BREAKS the
    # feature — `normalise_identifier` strips the bullets, so the re-upload
    # would file `6789` as a Social Security number, match nobody and mint a
    # second customer. The SCREEN is where the last-four rule bites; a file the
    # operator already holds is not a place it can help.
    identity = identity_source_columns(run.target, ((run.mapping_spec or {}).get("columns")) or {})
    # ⛔ **THE HEADER ROW — `DEF-2991`, AND IT WAS DROPPED BY THE VERY BLOCK
    # REPLACEMENT THAT ADDED THE COMMENT ABOVE IT.** The operator's own column
    # names, then the two we append, in that order: a re-upload maps by header
    # name, so a file without this line is a file that cannot do the one job it
    # has. It went out at `0179d7a0` and the lane's own new test passed over it,
    # because that test asserted the number was IN the file and never that the
    # file had a shape.
    yield _csv_line([*headers, FAILURE_REASON_COLUMN, FAILURE_FIX_COLUMN])
    for row in _result_rows(run, RESULT_KINDS["failures"]):
        raw = import_identity.reveal_cells(row.raw or {}, identity)
        yield _csv_line(
            [
                *(raw.get(header) for header in headers),
                # A row rejected by stage 3 and a row refused by the writer both
                # carry these two columns and neither says which stage it was:
                # the operator fixes the cell either way, and naming our own
                # stages on their spreadsheet is the internal reference CR-016
                # rules out.
                row.problem,
                row.fix_hint,
            ]
        )


def results_csv(run_id: Any, kind: Any) -> tuple[str, Any]:
    """`(filename, line generator)` for one half of a loaded run's result.

    The generator is what makes a 100,000-row download safe: `_result_rows`
    streams from the database in chunks and each line is formatted and handed
    away, so nothing larger than one row is ever held.

    ⚠ **REFUSED BY NAME ON THREE THINGS, IN ORDER**: a run of another tenant
    (`_run` raises `NotFoundError` — 404-never-403, HR-1), a run that has not
    loaded, and a `kind` that is not one of the two. The last is a
    `VAL_UNKNOWN_LOOKUP` naming what IS allowed rather than a silent default to
    one of them: a typo that quietly served the successes file would tell an
    operator that nothing failed.
    """
    run = _run(run_id)
    key = str(kind or "").strip().lower()
    if key not in RESULT_KINDS:
        _refuse(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.kind_unknown",
            allowed=sorted(RESULT_KINDS),
        )
    # ⛔ **THE TWO HALVES NO LONGER ASK THE SAME QUESTION — `DEF-2487`.** The
    # successes file is a receipt and needs a load; the failures file is a
    # worklist and needs only that the rows have been judged. Ordered AFTER the
    # `kind` check, because *"which file did you ask for"* has to be answered
    # before *"may you have it"* can be.
    if key == "successes":
        _refuse_results_not_loaded(run)
    else:
        _refuse_failures_not_decided(run)
    # The run's OWN number in the name, because an operator downloads both
    # halves of several runs into one folder and `results.csv` twice is a file
    # they cannot tell apart (`sample_csv`'s precedent).
    filename = f"{run.run_no or run.id}-{key}.csv"
    body = _successes_csv(run) if key == "successes" else _failures_csv(run)
    return filename, body


def receipt(run: models.ImportRun) -> dict[str, Any]:
    """Stage 5 — the receipt, read from the run and NOT recomputed.

    ⚠ Every figure here is what the run RECORDED at the moment it loaded
    (`BR-MET-090`'s posture, applied past the commit): a receipt that said
    *"245 loaded"* in August must still say it in December, whatever anyone has
    since deactivated. Nothing on this path counts rows again.
    """
    point = (
        models.RollbackPoint.objects.filter(tenant_id=run.tenant_id, run=run)
        .order_by("-created_at")
        .first()
    )
    payload = run_dict(run, with_rules=True)
    counts = run.counts or {}
    payload["receipt"] = {
        "run_id": str(run.id),
        "run_no": run.run_no,
        "loaded": int(counts.get("created") or 0) + int(counts.get("updated") or 0),
        # ⛔ **`DEF-PAY-10756` (L2-08) — A ROW THE WRITER REFUSED DID NOT LOAD
        # EITHER.** This read stage 3's `errors` alone, so a row the rehearsal
        # passed and the writer refused (`rejected_at_write`) was in no tile at
        # all: the tester's ten rows read *"4 loaded, 3 rejected"* with three
        # explained nowhere. Every row now lands in loaded or rejected.
        "rejected": int(counts.get("errors") or 0) + int(counts.get("rejected_at_write") or 0),
        "flagged": int(counts.get("warnings") or 0),
        "unplanned_units": int(counts.get("unplanned_units") or 0),
        # DEF-771 — one line per distinct plan the unplanned rows named, worst
        # first. `or []` because a run loaded before this landed carries no such
        # key and "the run did not say" must draw the same nothing as "there
        # were none", never an empty panel on every historical receipt.
        "unplanned_plans": list(counts.get("unplanned_plans") or []),
        "deactivated": int(counts.get("deactivated") or 0),
        "skipped_occupied": int(counts.get("skipped_occupied") or 0),
        # ── the assets targets' own figures (CR-028) — 0 on every other
        # target, so one receipt screen renders every run.
        "unit_tagged": int(counts.get("unit_tagged") or 0),
        "to_inventory": int(counts.get("to_inventory") or 0),
        "skipped_existing": int(counts.get("skipped_existing") or 0),
        # PO ruling 2026-08-27 — rows REJECTED because they name a meter
        # already on file and the mode is Insert new only. 0 on every other
        # target and on every run loaded before the ruling, which is the
        # honest reading of "the run did not say".
        "rejected_existing": int(counts.get("rejected_existing") or 0),
        # ── CR-046 — the three figures the widened ruling adds. All 0 on a run
        # loaded before it, which is the honest reading of *"the run did not
        # say"*; a screen draws them only when they are non-zero, so a
        # historical receipt is unchanged.
        #
        # ⚠ **`premises_with_no_owner` IS THE ONE THAT MATTERS AND IT IS NOT A
        # STATISTIC.** PO ruling 2026-08-27 lets a blank Owner column LOAD, and
        # the cost is that the address has **nobody to charge**. A number on
        # the receipt is what stops those rows being silently
        # indistinguishable from complete ones — which is the difference
        # between a migration a utility can finish and one it discovers is
        # incomplete at the first bill run.
        "numbers_issued_from_series": int(counts.get("numbers_issued_from_series") or 0),
        "premises_with_no_owner": int(counts.get("premises_with_no_owner") or 0),
        # ⛔ **CR-055 TASK 2 — THE SAME TOTAL, SPLIT INTO THE TWO KINDS OF WORK
        # IT REPRESENTS.** PO ruling 2026-08-31 puts ambiguous owner names into
        # the ownerless pool beside blank ones. Both end with no owner and
        # therefore nobody to charge; they need OPPOSITE work from a person —
        # a blank needs research, an ambiguity needs a decision between two
        # named parties — so a receipt that printed only the total would throw
        # away the half an operator can settle today.
        #
        # ⚠ **0 AND `[]` ON A RUN LOADED BEFORE TODAY, WHICH IS THE HONEST
        # READING OF *"THE RUN DID NOT SAY"* AND NOT A CLAIM THAT ITS ROWS WERE
        # ALL BLANKS.** A historical premises run carries a non-zero
        # `premises_with_no_owner` and neither component, so a screen draws the
        # breakdown only when a component is present. Back-filling the blank
        # count from the total would be inventing a measurement nobody made.
        "premises_owner_blank": int(counts.get("premises_owner_blank") or 0),
        "premises_owner_ambiguous": int(counts.get("premises_owner_ambiguous") or 0),
        # ⚠ **THE COUNT ALONE CANNOT BE REVIEWED (DEF-771 clause 3's lesson,
        # applied).** CR-055: *"carry the candidate names through, so the
        # person settling it does not have to re-run the search."* One line per
        # distinct spelling, worst first, NAMES ONLY (B14 rule 31).
        "premises_owner_ambiguous_names": list(
            counts.get("premises_owner_ambiguous_names") or []
        ),
        "premises_with_no_services": int(counts.get("premises_with_no_services") or 0),
        # ⛔ **CR-058 W3 · BR-MET-1030 — WHICH ROWS GOT AN OWNER ACCOUNT AND
        # WHICH ARE WAITING FOR SOMEBODY TO IDENTIFY THE OWNER.** `CR-058`
        # task 12 asks for exactly this pair, and the second figure is the
        # mitigation rather than a statistic: without it a migration that
        # identified half its owners looks identical to one that identified all
        # of them, and the utility finds out at its first bill run.
        # ⚠ 0 on every other target and on every run loaded before today, which
        # is the honest reading of *"the run did not say"* — a screen draws
        # each one only when it is non-zero.
        "premises_owner_accounts_created": int(
            counts.get("premises_owner_accounts_created") or 0
        ),
        "premises_owner_awaiting_identity": int(
            counts.get("premises_owner_awaiting_identity") or 0
        ),
        "premises_owner_no_account_type": int(counts.get("premises_owner_no_account_type") or 0),
        "premises_owner_identity_mismatch": int(
            counts.get("premises_owner_identity_mismatch") or 0
        ),
        "premises_owner_account_refused": int(counts.get("premises_owner_account_refused") or 0),
        # The count alone cannot be acted on (DEF-771 clause 3): WHICH rows, by
        # the operator's own cell, never by a uuid (B14 rule 31).
        "premises_owner_account_refusals": list(
            counts.get("premises_owner_account_refusals") or []
        ),
        # ⛔ **PO RULING 2026-09-19 — AN ACCOUNT AND AN OWNER RECORD ARE TWO
        # FIGURES.** A receipt that reports only the first tells an operator
        # their migration is done while every address it loaded has nobody
        # named on it. ⚠ 0 on every other target and on every run loaded
        # before today, so a screen draws each only when it is non-zero — an
        # old run's 0 means *the run did not say*, never *there were none*.
        "premises_owner_parties_created": int(
            counts.get("premises_owner_parties_created") or 0
        ),
        "premises_owner_no_category": int(counts.get("premises_owner_no_category") or 0),
        "premises_owner_party_refused": int(counts.get("premises_owner_party_refused") or 0),
        "premises_owner_party_refusals": list(
            counts.get("premises_owner_party_refusals") or []
        ),
        "premises_owner_no_owner_named": int(
            counts.get("premises_owner_no_owner_named") or 0
        ),
        # ⛔ **A MIGRATION THAT IS 90% DONE MUST NOT LOOK IDENTICAL TO ONE THAT
        # IS FINISHED (PO ruling 2026-08-27).** *"412 accounts loaded · 412
        # opening balances waiting for your changeover date."* Without the
        # figure the operator closes the tab believing the books are on the
        # system and finds out at the first bill run that no account has a
        # balance. 0 on every other target and on every run that had its date.
        "opening_held": int(counts.get("opening_held") or 0),
        "changeover_provisional": counts.get("changeover_provisional") or None,
        "changeover_on": counts.get("changeover_on") or None,
        "kept_reads": int(counts.get("kept_reads") or 0),
        # ⛔ **CR-047 · DEF-2519 — the rows the WRITER turned down, one
        # savepoint each.** It is beside `rejected_existing` rather than folded
        # into it because the two are different acts: that one was judged
        # before anything was attempted, this one was attempted and refused.
        # 0 on every other target and on every run loaded before CR-047, which
        # is the honest reading of *"the run did not say"*.
        "rejected_at_write": int(counts.get("rejected_at_write") or 0),
        # ⛔ **CR-047 — PO 2026-08-29: *"if account is created then money is
        # also lands"*.** How many services the created accounts inherited from
        # their units. An account that inherited none has nothing to bill and
        # is otherwise indistinguishable on this receipt from one that is ready
        # — the same failure `opening_held` exists to make visible.
        "with_services": int(counts.get("with_services") or 0),
        # ⛔ **CR-058 W7 · BR-CUS-1041 — WHICH ROWS GOT A CUSTOMER AND WHICH
        # ARE WAITING FOR SOMEBODY TO IDENTIFY ONE.** The ruling asks for
        # exactly this pair and the second figure is the mitigation rather than
        # a statistic: without it a migration that identified half its customers
        # looks identical to one that identified all of them.
        # ⚠ 0 on every other target and on every run loaded before today, which
        # is the honest reading of *"the run did not say"*; a screen draws each
        # one only when it is non-zero.
        "accounts_awaiting_identity": int(counts.get("accounts_awaiting_identity") or 0),
        "accounts_identity_mismatch": int(counts.get("accounts_identity_mismatch") or 0),
        "customers_created": int(counts.get("customers_created") or 0),
        "customers_matched": int(counts.get("customers_matched") or 0),
        # ── the accounts target's own figures (CR-030 W1) — 0 elsewhere, so one
        # receipt screen still renders every run.
        "kept_billed": int(counts.get("kept_billed") or 0),
        "kept_missing": int(counts.get("kept_missing") or 0),
        "source_label": run.file_name,
        "file_sha256": run.file_hash,
        "file_hash_verified": bool(run.file_hash),
        "run_by": getattr(getattr(run, "run_by", None), "email", None),
        "session_and_ip": " · ".join(part for part in (run.session_ref, run.ip) if part) or None,
        "mapping_used": getattr(run.mapping, "name", None),
        "write_mode": run.write_mode,
        "finished_at": run.finished_at,
        "rollback_point": (
            {
                "id": point.point_no or str(point.pk),
                "status": point.status,
                "expires_at": point.expires_at,
            }
            if point is not None
            else None
        ),
    }
    # ⛔ **DEF-AST-8360 — `with_services` BELONGS TO THE TARGET THAT COUNTS IT.**
    # Only `_load_accounts_rows` sums `services_linked`; every other target
    # recorded nothing, and a `0` here was drawn by the receipt screen as
    # *"Wired to no services: N … nothing to bill them for yet"* — on a devices
    # run whose five carts and fire lines were each seated on their trash and
    # fire service point (U14 browser walk, 2026-09-30). An ABSENT key is what
    # the screen already reads as *"the run did not say"* and draws nothing.
    if run.target != TARGET_ACCOUNTS:
        payload["receipt"].pop("with_services", None)
    return payload


def _refuse_accounts_rollback_with_opening_books(run: models.ImportRun) -> None:
    """⛔ **OQ-352 — REFUSED, NOT GUESSED (the prime directive).**

    Raised BEFORE a single account is touched and before the rollback point is
    spent, so a run whose books this product cannot lawfully unwind is still
    exactly where it was when the day comes that the rule is ruled. The reason
    lives on `OQ_ROLLBACK_OPENING` above; the short version is that the load
    posted balanced opening journal entries and hard rule 4 forbids deleting
    one, so removing the buckets underneath them would break BR-LED-007's
    tie-out with nothing in the product reporting it.

    ⚠ **THE PREDICATE IS THE RUN'S OWN RECORD, NOT A LEDGER READ.**
    `with_opening_balance` is what `_load_accounts_rows` COUNTED at the moment
    it built the one ledger handoff (`opening` is the same list), so it answers
    *"did this run post opening entries"* without metering reaching across a
    module boundary to ask (B1/B2 §2). Zero means every row's four buckets were
    blank, `post_opening_batch` was handed nothing, and no entry exists to
    reverse — which is why that run rolls back in full.
    """
    if int((run.counts or {}).get("with_opening_balance") or 0) <= 0:
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref=OQ_ROLLBACK_OPENING,
        message_key=ROLLBACK_OPENING_UNRULED_KEY,
        params={"oq": OQ_ROLLBACK_OPENING, "accounts": int(run.counts["with_opening_balance"])},
    )


@require_role(SYSTEM_ADMIN, br_ref="BR-MET-035")
def rollback(actor: Any, run_id: Any) -> dict[str, Any]:
    """Reverse what a run CREATED, and skip anything now occupied.

    ⚠ **IT DEACTIVATES; IT DOES NOT DELETE** — hard rule 4 again, and the same
    answer `replace` gives. A row an issued invoice was written against cannot
    leave, and a row somebody has since moved into is not this run's to take
    back. Both are reported rather than silently skipped.

    ⚠ **ONE BRANCH PER TARGET FAMILY, AND A MISSING BRANCH IS SILENT.**
    (A defect row for this escape is OWED in `12-governance/10-defect-log.csv`
    and is NOT written — this lane was scoped away from that file. Its
    `escape_reason`: no gate reads a `rollback` receipt, and the fall-through
    path is legitimate for the targets it was written for, so every test and
    every gate passed over a rollback that reversed nothing.)
    This function read `if run.target in ASSETS_TARGETS:` and let EVERYTHING else
    fall through to the premises/units path — which keys a row as
    `f"{premises_ref}|{label}"`. An accounts row carries neither field, so
    `_key_of` returned None, the loop `continue`d on every single row, and the
    run still marked its point `used`, set `status = "rolled_back"`, wrote
    `rolled_back: 0` and emitted `import_run.rolled_back`. **A reported success
    that reversed nothing and permanently spent the one rollback point the run
    had.** Nothing failed, because the fall-through path is a legitimate path —
    which is why a seventh target must add its branch HERE, in the same commit
    that registers it.
    """
    with transaction.atomic():
        run = _run(run_id, locked=True)
        if run.target == TARGET_PAYMENTS:
            # ⛔ **`P1.22` — THE PAYMENTS BRANCH IS A REFUSAL, AND IT IS FIRST.**
            #
            # CLAUDE.md hard rule 4: **a posted payment cannot be unwritten.**
            # It is REVERSED, which is a new row, a different act and different
            # books — not the absence of the original. So this target has no
            # rollback, `_load_payments_rows` creates no rollback point to
            # spend, and the kit draws no *Roll back this run* button over it.
            # **Discard this batch before the commit is the only way to throw a
            # payments run away.** Reads is the only other target that refuses
            # outright, and for the same reason one layer along (BR-MET-017: a
            # posted reading is superseded, never un-created).
            #
            # ⚠ **IT IS ABOVE THE `status != loaded` CHECK ON PURPOSE.** The
            # answer is the same whatever state the run is in, and a refusal
            # that depends on the status would tell an operator *"this run is
            # not loaded"* about a run that is — sending them to look for a
            # state that would make the button work. There is no such state.
            #
            # ⚠ **AND IT IS ABOVE THE POINT LOOKUP FOR A STRONGER REASON:** the
            # accounts escape this function's own docstring records is a run
            # that SPENT its one rollback point and reversed nothing. Refusing
            # before anything is read means there is nothing to spend.
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-PAY-023",
                message_key="metering.import.payments_no_rollback",
            )
        if run.status != "loaded":
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-090",
                message_key="metering.import.not_loaded",
            )
        point = (
            models.RollbackPoint.objects.filter(tenant_id=run.tenant_id, run=run)
            .order_by("-created_at")
            .first()
        )
        if point is None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-090",
                message_key="metering.import.no_rollback_point",
            )
        if point.status != "available":
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-090",
                message_key="metering.import.rollback_spent",
            )
        if point.expires_at is not None and point.expires_at < timezone.now():
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-MET-090",
                message_key="metering.import.rollback_expired",
            )

        if run.target in ASSETS_TARGETS:
            # ⚠ **THE AST-04 CALLOUT, MADE TRUE:** *"Meters already carrying
            # reads are kept and reported."* Every asset THIS RUN CREATED
            # (`created_record_id` — spec updates are not reversed, they were
            # never this run's rows to un-write) is handed to the assets
            # service, which keeps a read-carrying or retired asset and
            # returns the rest to inventory with its assignment closed.
            reversed_rows = kept_reads = kept_other = 0
            for row in models.ImportRunRow.objects.filter(
                tenant_id=run.tenant_id, run=run, outcome__in=("loaded", "flagged")
            ).exclude(created_record_id__isnull=True):
                outcome = seams.rollback_asset_from_import(
                    actor, row.created_record_id, run_no=run.run_no
                )
                if outcome == "reversed":
                    reversed_rows += 1
                    continue
                if outcome == "kept_reads":
                    kept_reads += 1
                    row.problem = "Kept on rollback — this meter already carries reads."
                    row.fix_hint = "Retire it from its detail page if it truly must go."
                else:
                    kept_other += 1
                    row.problem = "Kept on rollback — it was retired or removed after the load."
                    row.fix_hint = None
                row.save(update_fields=["problem", "fix_hint", "updated_at"])
            point.status = "used"
            point.save(update_fields=["status"])
            run.status = "rolled_back"
            run.counts = {
                **(run.counts or {}),
                "rolled_back": reversed_rows,
                "kept_reads": kept_reads,
                "kept_other": kept_other,
            }
            run.save(update_fields=["status", "counts", "updated_at"])
            _audit(
                actor,
                "import_run.rolled_back",
                run.id,
                run_no=run.run_no,
                reversed=reversed_rows,
                kept_reads=kept_reads,
                kept_other=kept_other,
            )
            return receipt(run)

        if run.target == TARGET_ACCOUNTS:
            # ⚠ **THE LEDGER HALF FIRST, AND IT IS A REFUSAL — OQ-352.** Nothing
            # below may run for a migration that posted opening books, and the
            # check is here rather than inside the loop so the rollback point is
            # not spent on a question no signed rule answers.
            _refuse_accounts_rollback_with_opening_books(run)
            # B18 §5.9.4's load-bearing constraint, made true per row: *"an
            # account that has been billed cannot be rolled back, because hard
            # rule 4 forbids deleting an issued invoice. The window is a
            # courtesy; the billed check is the law."* Every account THIS RUN
            # CREATED (`created_record_id`) is handed to customers, which owns
            # the table (B1/B2 §2) and answers reversed | kept_billed | missing.
            reversed_rows = kept_billed = kept_missing = 0
            for row in models.ImportRunRow.objects.filter(
                tenant_id=run.tenant_id, run=run, outcome__in=("loaded", "flagged")
            ).exclude(created_record_id__isnull=True):
                outcome = seams.rollback_account_from_import(
                    actor, row.created_record_id, run_no=run.run_no
                )
                if outcome == "reversed":
                    reversed_rows += 1
                    continue
                if outcome == "kept_billed":
                    kept_billed += 1
                    # ⚠ NO IDS IN THIS SENTENCE (CR-016's ruling, gate G28). The
                    # provenance — hard rule 4, B18 §5.9.4 — belongs in this
                    # comment, where support can reach it and a clerk cannot.
                    row.problem = "Kept on rollback — this account has already been billed."
                    row.fix_hint = (
                        "A bill that has been issued cannot be unmade. "
                        "Close the account instead if it must go."
                    )
                else:
                    kept_missing += 1
                    row.problem = "Kept on rollback — this account was closed or removed since."
                    row.fix_hint = None
                row.save(update_fields=["problem", "fix_hint", "updated_at"])
            point.status = "used"
            point.save(update_fields=["status"])
            run.status = "rolled_back"
            run.counts = {
                **(run.counts or {}),
                "rolled_back": reversed_rows,
                "kept_billed": kept_billed,
                "kept_missing": kept_missing,
            }
            run.save(update_fields=["status", "counts", "updated_at"])
            _audit(
                actor,
                "import_run.rolled_back",
                run.id,
                run_no=run.run_no,
                reversed=reversed_rows,
                kept_billed=kept_billed,
                kept_missing=kept_missing,
            )
            return receipt(run)

        if run.target == TARGET_PARTS:
            # ⚠ **THE BRANCH THIS FUNCTION'S OWN DOCSTRING DEMANDS OF A NEW
            # TARGET (CR-077).** Without it a parts run would fall through to
            # the premises/units path below, which keys a row as
            # `f"{premises_ref}|{label}"` — a parts row carries neither field,
            # so every row would `continue`, the point would be spent, and the
            # run would report `rolled_back: 0` as a success. That is the
            # accounts escape this docstring records, repeated.
            reversed_rows = kept_issued = kept_missing = 0
            for row in models.ImportRunRow.objects.filter(
                tenant_id=run.tenant_id, run=run, outcome__in=("loaded", "flagged")
            ).exclude(created_record_id__isnull=True):
                outcome = seams.rollback_part_from_import(
                    actor=actor, part_id=row.created_record_id
                )
                if outcome == "reversed":
                    reversed_rows += 1
                    continue
                if outcome == "kept_issued":
                    kept_issued += 1
                    # ⚠ NO IDS IN THIS SENTENCE (CR-016's ruling, gate G28).
                    row.problem = "Kept on rollback — this part has been issued to a job."
                    row.fix_hint = (
                        "Deleting it would take the job's materials record with it. "
                        "It is switched off instead, so nobody can issue it again."
                    )
                else:
                    # ⚠ **`None` LANDS HERE AND IS REPORTED AS KEPT, NOT AS
                    # REVERSED** — `DEF-075`: a seam that cannot answer must
                    # never be read as *"there was nothing to do"*.
                    kept_missing += 1
                    row.problem = "Kept on rollback — this part was removed since."
                    row.fix_hint = None
                row.save(update_fields=["problem", "fix_hint", "updated_at"])
            point.status = "used"
            point.save(update_fields=["status"])
            run.status = "rolled_back"
            run.counts = {
                **(run.counts or {}),
                "rolled_back": reversed_rows,
                "kept_issued": kept_issued,
                "kept_missing": kept_missing,
            }
            run.save(update_fields=["status", "counts", "updated_at"])
            _audit(
                actor,
                "import_run.rolled_back",
                run.id,
                run_no=run.run_no,
                reversed=reversed_rows,
                kept_issued=kept_issued,
                kept_missing=kept_missing,
            )
            return receipt(run)

        reversed_rows = kept_occupied = 0
        # ⚠ Read ONCE, not per row — `DEF-324` measured what the other shape
        # costs on a path like this, and a 431-row rollback would rebuild the
        # whole index 431 times.
        index = _existing_index(run)
        for row in models.ImportRunRow.objects.filter(
            tenant_id=run.tenant_id, run=run, outcome__in=("loaded", "flagged")
        ):
            key = _key_of(run, row.mapped or {})
            if key is None:
                continue
            target_row = index.get(key)
            if target_row is None:
                continue
            if _is_occupied(run, target_row):
                kept_occupied += 1
                continue
            target_row.status = "inactive"
            target_row.save(update_fields=["status", "updated_at"])
            reversed_rows += 1
            _audit(actor, f"{run.target}.rolled_back", target_row.pk, run_no=run.run_no)
        point.status = "used"
        point.save(update_fields=["status"])
        run.status = "rolled_back"
        run.counts = {
            **(run.counts or {}),
            "rolled_back": reversed_rows,
            "kept_occupied": kept_occupied,
        }
        run.save(update_fields=["status", "counts", "updated_at"])
        _audit(
            actor,
            "import_run.rolled_back",
            run.id,
            run_no=run.run_no,
            reversed=reversed_rows,
            kept_occupied=kept_occupied,
        )
    return receipt(run)


#: CR-045 wave D (D.13–D.15) · BR-SHL-011 — the filter vocabulary the three
#: Imports tabs declare. `status` is the runner's own six-token status; `target`
#: is `TARGETS`, the six upload targets.
#:
#: ⚠ **`run_list` TOOK A `params` ARGUMENT AND IGNORED IT FROM CR-023 UNTIL
#: 2026-08-27 (DEF-1702).** `apps/metering/api.py` has passed
#: `request.query_params` into it since the route was written, so the parameter
#: looked wired and answered nothing — every Imports tab fetched the whole list
#: and narrowed it in the browser. Two lanes measured the gap and REPORTED it
#: rather than inventing the leg (`AssetImportsTab`'s and `AccountImportsTab`'s
#: exception lines both say so), and **B18 TC-IMP-12 already writes
#: `GET /imports?target=accounts`**. This is that leg, in BR-SHL-011's `f.<name>`
#: grammar rather than TC-IMP-12's bare `?target=`, because the grammar is the
#: signed one and `FilterBar` speaks it.
RUN_LIST_FILTERS: tuple[str, ...] = ("status", "target")


#: ── PRM-04's SORT VOCABULARY (`BR-CUS-1046` / `DEF-CUS-5061`) ──────────────
#: ⚠ **THIS LIST ALREADY OPENED NEWEST-FIRST** (`-created_at`), so the ruling
#: asked nothing of its default. What it had was a 200-row CAP and no count.
#: The vocabulary is declared anyway, because the column the three Imports tabs
#: draw as `STARTED` is this ordering and a pager over a server-side page needs
#: the sort to be stable and total — `-created_at` alone is neither.
#: ⚠ **EVERY NAME HERE IS THE SCREEN'S EXISTING COLUMN KEY, NOT A NEW ONE.**
#: `DataTable` stores a clerk's show/hide/reorder preference keyed by
#: `screenId` + column key (`BR-SHL-013`, `DEF-647`), so renaming a column to
#: match a tidier server name would silently discard every saved column set on
#: this screen. The server name moved instead; it is the cheaper half.
RUN_SORTS: dict[str, tuple[Any, ...]] = {
    #: ⚠ **WRITTEN ASCENDING, LIKE EVERY TERM IN THIS MAP — `order_terms` FLIPS
    #: IT AND `DEFAULT_DIR` IS `desc`.** The first draft of this pass stored
    #: `-created_at` here AND defaulted to `desc`, so the flip cancelled the
    #: minus and every list opened on the OLDEST row: the exact inversion of
    #: the ruling, shipped as a working feature. Nothing raised — it was found
    #: by curling the endpoint and reading the first three rows.
    "started": ("created_at", "id"),
    "run_no": ("run_no", "id"),
    "status": ("status", "id"),
}
RUN_DEFAULT_SORT = "started"
RUN_DEFAULT_DIR = "desc"


def run_list(params: Any = None) -> dict[str, Any]:
    """PRM-04's run table — r10's nine columns, newest first, SERVER-PAGED.

    ⚠ This is what the Imports tab has been STATING AS ABSENT since CR-023 P0
    (*"an empty table here would assert you have never imported anything"*).
    It is a table now, so the stated absence comes off in the same commit.

    ⚠ **THE 200-ROW CAP IS GONE AND THE PAGE IS TAKEN IN SQL — `DEF-CUS-5061`,
    `NFR-3` AND `NFR-5` (2026-09-12).** This read ended `[:200]` and returned a
    bare `{"rows": …}` with no count, so the three Imports tabs paged in the
    BROWSER over a capped array: at the 201st run the history stopped and the
    screen looked complete. Both rules `CLAUDE.md` calls the T4/T5 flexibility
    deliverable were breached at once — *"nobody may add a per-tenant cap, an
    unpaginated list, or an account maximum that would have to be removed when
    T4 arrives"* — and the cap had never been reconciled with either: the
    decision log of 2026-08-27 (`DEF-1702`) reasons carefully about where a
    filter runs RELATIVE to the cap and never asks whether the cap may exist.

    ⚠ **`f.status` AND `f.target` ARE STILL APPLIED IN THE QUERYSET, AND
    `DEF-1702`'s REASONING NOW HOLDS UNCONDITIONALLY.** That defect's point was
    that a filter applied on the CLIENT would narrow the newest 200 runs rather
    than the tenant's runs — *a subset of a subset, silently*. With the cap gone
    `f.target=accounts` means *this tenant's accounts runs*, full stop, rather
    than *the newest 200 of them*; the ordering of the two operations is no
    longer load-bearing and the filter stays in SQL because that is where it
    belongs.

    ⚠ **THE ENVELOPE GREW AND NOTHING WAS TAKEN AWAY.** `rows` is still `rows`,
    so a client that reads only that key keeps working; `total`, `page`, `per`
    and `pages` join it, which is the shape the four sibling worklists already
    serve (`move_reads`, `transfer_reads`, `disconnect_reads`,
    `connection_reads`). A caller that passes no `page`/`per` gets the first
    page at the IS-2 default of 50.

    BR-SHL-011's fall-back law: an undeclared `f.<name>` is ignored, and a
    declared one carrying a value no row holds returns an empty list — never an
    error; `page` and `per` clamp rather than refusing.
    """
    listing = pagination.parse_list_params(
        params if params is not None else {},
        allowed_sorts=tuple(RUN_SORTS),
        default_sort=RUN_DEFAULT_SORT,
        default_dir=RUN_DEFAULT_DIR,
        allowed_filters=RUN_LIST_FILTERS,
    )
    filters = listing.filters
    rows = models.ImportRun.objects.filter(tenant_id=_tenant_id()).select_related("run_by")
    if status := filters.get("status"):
        rows = rows.filter(status=str(status))
    if target := filters.get("target"):
        rows = rows.filter(target=str(target))
    rows = rows.order_by(
        *pagination.order_terms(
            listing.sort, listing.dir, columns=RUN_SORTS, default=RUN_DEFAULT_SORT
        )
    )
    # ⚠ **COUNT FIRST, THEN SLICE — and the count is over the FILTERED set.**
    # A count taken before the filters would tell the pager there are more pages
    # than exist, and the clerk would meet an empty last page.
    total = rows.count()
    per = pagination.clamp_page_size(listing.per)
    pages = max(1, math.ceil(total / per)) if total else 1
    page = min(max(listing.page, 1), pages)
    start = (page - 1) * per
    rows = rows[start : start + per]
    return {
        "total": total,
        "page": page,
        "per": per,
        "pages": pages,
        "sorts": list(RUN_SORTS),
        "sort": listing.sort if listing.sort in RUN_SORTS else RUN_DEFAULT_SORT,
        "dir": listing.dir,
        "rows": [
            {
                "id": str(row.id),
                "run_no": row.run_no,
                "target": row.target,
                "file_name": row.file_name,
                "rows_in": int((row.counts or {}).get("in") or 0),
                "loaded": int((row.counts or {}).get("created") or 0)
                + int((row.counts or {}).get("updated") or 0),
                "rejected": int((row.counts or {}).get("errors") or 0),
                "status": row.status,
                "run_by": getattr(row.run_by, "email", None),
                "started_at": row.started_at,
                "finished_at": row.finished_at,
            }
            for row in rows
        ]
    }


# ══════════════════════════════════════════════════════════════════════════
# CR-026 · THE JOB BODIES — what a worker runs, registered in AppConfig.ready()
#
# `core.jobs.run_pending(job_id)` loads the record, reads its `kind` and calls
# the body registered for it (apps/metering/apps.py). The tenant context is
# entered by `run_job` from the RECORD before a line of this runs (B3), which
# is what makes an RLS-FORCED read legal in a worker with no request.
#
# ⚠ **A BODY IS NOT A SECOND PIPELINE.** Each one calls the same `_*_apply`
# function the synchronous request calls, with a real gauge instead of the null
# one. BR-MET-096's ONE runner is the rule these obey — the day a third target
# arrives it inherits all of this without a line changing here.
# ══════════════════════════════════════════════════════════════════════════


def _stage_job(record: dict[str, Any], stage: str) -> str | None:
    """Run one deferred stage under its own tenant's context.

    ⚠ **THE GAUGE IS THE ONLY PLACE A FAILURE IS EXPLAINED IN ENGLISH.** The
    job record carries the exception for `/jobs/{id}` (BE-07), and this writes
    the same sentence where the IMPORT screen is already looking — then
    re-raises, so Celery's retry policy and the job record both see the truth
    (apps/tenancy/tasks.py's contract). It never swallows.
    """
    payload = record["payload"]
    run_id = payload["run_id"]
    actor = _JobActor(payload.get("actor_user_id"))
    run = _run(run_id)
    reporter = _reporter(run, stage, record["id"])
    reporter.start()
    try:
        if stage == "transform":
            _transform_apply(actor, run_id, payload.get("data") or {}, reporter)
        elif stage == "validate":
            # CR-046 wave B — the deferred stage 3 carries the mode the
            # request was made with, exactly as the load stage already does.
            _validate_apply(actor, run_id, reporter, payload.get("write_mode"))
        else:
            _load_apply(
                actor,
                run_id,
                payload["write_mode"],
                payload.get("data") or {},
                reporter,
            )
    except Exception as exc:  # noqa: BLE001 — recorded in English, then re-raised
        reporter.failed(f"{type(exc).__name__}: {exc}")
        raise
    reporter.finished(message=None)
    # No result_link: the client already holds the run id it polled with, and
    # the run's own endpoint is where the answer lives. A link built here would
    # have to guess the tenant path segment (core.tenancy.tenant_path needs the
    # request), and a guessed URL in a job record is a link that 404s later.
    return None


def run_transform_job(record: dict[str, Any]) -> str | None:
    """Stage 2 in a worker. NO PREMISES ROW — the same body, the same promise."""
    return _stage_job(record, "transform")


def run_validate_job(record: dict[str, Any]) -> str | None:
    """Stage 3 in a worker. Still no write outside the three run tables."""
    return _stage_job(record, "validate")


def run_load_job(record: dict[str, Any]) -> str | None:
    """Stage 4 in a worker — the only stage that writes, in ONE transaction.

    ⚠ Re-delivery (CELERY_TASK_ACKS_LATE is on) is safe by hard rule 6, not by
    resumption: a redelivered load of a run that is already `loaded` returns the
    receipt from `_load_locked`'s idempotency branch and writes nothing twice.
    """
    return _stage_job(record, "load")


# ══ THE RUN THAT MADE A ROW — PUBLISHED, SO ANOTHER MODULE NEED NOT READ OURS ══
#
# ⚠ **`DEF-PAY-6213` IS A MISSING READ AND NOT A MISSING LINK, AND THIS IS THE
# READ.** `import_run_rows.created_record_id` has carried *"what it made, for
# rollback"* since CR-023, every row carries `run_id`, and `_load_payments_rows`
# sets both exactly as the accounts and parts loaders do. So the payment → run
# link has existed since the eighth target landed; what nothing outside this
# module could do was ASK for it without touching `import_run_rows`, which is
# metering's table (B2 §2 — a cross-module read goes through a published
# callable, never through a neighbour's ORM).
#
# ⚠ **IT ANSWERS IN BULK BECAUSE THE CALLER IS A PAGED LIST.** A per-row lookup
# from a 50-row payments page is 50 queries, and `NFR-3` pages in SQL precisely
# so that one page costs one page. A single `IN` over `created_record_id`
# answers the whole page.
#
# ⚠ **`target` IS REQUIRED AND IS NOT DECORATION.** `created_record_id` is a
# bare `UUIDField` shared by every target, so two targets can in principle hold
# the same uuid; asking for ONE target's runs makes the answer a statement
# about that target rather than about whatever happened to match.


def created_record_runs(target: str, record_ids: Any) -> dict[str, dict[str, Any]]:
    """`created_record_id` → the run that created it, for one target.

    Returns `{record id: {"run_id": str, "run_no": str | None}}`, with a record
    ABSENT when no run of this target created it — an absence is a fact ("this
    payment was not imported") and is not the same statement as a null label.

    **`run_no` travels exactly as stored, null included.** `ImportRun.run_no` is
    nullable, and a caller that invented a label for a null would print a number
    no other screen in the product shows.
    """
    wanted = [str(one) for one in (record_ids or []) if one]
    if not wanted:
        return {}
    rows = (
        models.ImportRunRow.objects.filter(
            tenant_id=_tenant_id(),
            run__target=target,
            created_record_id__in=wanted,
        )
        .select_related("run")
        .values_list("created_record_id", "run_id", "run__run_no")
    )
    return {
        str(record_id): {"run_id": str(run_id), "run_no": run_no}
        for record_id, run_id, run_no in rows
        if record_id is not None
    }


def records_created_by_run_no(target: str, run_no: str) -> list[str]:
    """Every record of `target` that the run NUMBERED `run_no` created.

    The mirror of `created_record_runs` above, and it exists for the payments
    list's BATCH FILTER (`CR-136-BRC07` `P2.8`, the blueprint's §03 2·1 note
    ③ — *"Batch filter · one batch at a time"*). That screen shows an imported
    payment its run's NUMBER, so the filter has to take the same number back.

    ⚠ **THE NUMBER, NOT THE ID** (B14 rule 31 — no database id is ever the
    visible value of a field, so the id is not what a clerk has to hand). An
    unknown number answers `[]` rather than raising: a list URL never 4xxs over
    its params (BR-SHL-011), and an empty answer and a refusal are the same
    screen to a clerk who mistyped.

    ⚠ **BOUNDED BY THE RUN, WHICH IS BOUNDED BY `BR-MET-038`** — 10,000 rows a
    file. The caller turns this into one `IN`, which is the same shape
    `created_record_runs` already uses for a page.
    """
    wanted = (run_no or "").strip()
    if not wanted:
        return []
    rows = models.ImportRunRow.objects.filter(
        tenant_id=_tenant_id(),
        run__target=target,
        run__run_no=wanted,
        created_record_id__isnull=False,
    ).values_list("created_record_id", flat=True)
    return [str(one) for one in rows if one]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-004@8bf4be8 (CR-023 P4 — design B15 §4.1–§4.3A, §12 endpoints 1–4; BR-MET-085/088/090/091 CONFIRMED 2026-08-21)
# generated: 2026-08-21 by the CR-023 P3/P4 lane · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (the three assets targets — declared column sets + aliases + samples (B16 §4.7b), per-field lookup indexes, KIND_DECIMAL/UNIT_REF/ASSET_REF, BR-AST-045 unit tagging at load through the assets seam, OQ-326 replace refusal, assets dry-run/load/rollback halves, fix_row inline correction, BR-AST-048 default templates + recognition + save_mapping_template) · AMENDED 2026-08-26 by lane PAYLOAD (DEF-766 — the reject list travels as a WINDOW: run_dict serves REJECT_WINDOW_DEFAULT = 50 rejects plus rejects_window {total, offset, limit}, GET /imports/{id} takes ?reject_offset/?reject_limit, and the stage-3 table pages through the SERVER. The poll surface was building the whole list with every row's raw cells every two seconds — 4.28 MB on the PO's 9,881-reject run. Measured: a 600-reject run answers 26,401 B where the unbounded list answered 273,302 B, and the payload no longer grows with the reject count at all — 60 rejects 26,392 B, 600 rejects 26,401 B)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — WFL-01.premises.1–3 and PRM-04 are P6/WFL, the screen lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr023_import_stages.py · golden 33/33 · makemigrations --check clean · run_gates no new failure
# exceptions: this module holds its own ORM against metering's OWN tables rather than routing through services.py — the `sample_data.py` posture, taken deliberately so a concurrent CR-024 lane editing services.py and this lane never touch one file (LAW 0 is a MODULE boundary, and no table outside metering is written) · NO new i18n key is minted: every refusal reuses an existing catalogue sentence, because G32 is a ratchet at 0 and one new key obliges eleven catalogues under G15 — `customers.import.already_committed` is reused for a run past commit and that cross-module reuse is REPORTED · `target=units` and `source_kind` other than `file` are refused by name (B15 §17 P8, §4.1) · `Standardise to USPS` and `ZIP+4 split` are NOT offered, each with its reason served
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
