# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data: seed it, tag it, report
#           it, remove it)   Screens: S8 (Settings → Company profile — both
#           actions, BR-TEN-069), S62 (the honesty report, BR-TEN-060)
# Rules:    BR-TEN-056 (stops at reads · every row tagged · background + honest
#           reporting) · BR-TEN-057 (the tag is a column on the owning row) ·
#           BR-TEN-058 (reference vocabulary is NOT sample data) · BR-TEN-060
#           (an unwired seam is a NAMED line, not a skip) · BR-TEN-061 (removal
#           order) · BR-TEN-063 (atomic per module, idempotent, audited) ·
#           BR-TEN-064 (runs in production, never automatic — a human asks) ·
#           BR-TEN-065 (sample accounts are non-billable) · BR-TEN-066 (removal
#           is partial-and-named) · BR-TEN-068 (sample plans are promoted on
#           first real attachment) · BR-TEN-069 (both actions on Company
#           profile) · BR-TEN-013 (cross-module writes via the owning module's
#           service functions ONLY) · BR-TEN-016 (audited)
# Tests:    06-backend/tests/test_us_ten_019_sample_data.py
# Impacts:  S62 checklist rendering · apps/metering · apps/assets ·
#           apps/customers · apps/rating (each owes the seam named below)
# ───────────────────────────────────────────────────────
"""US-TEN-019 — the tenancy-side sample-data ORCHESTRATOR and its run ledger.

⚠ THIS DOCSTRING USED TO SAY "TODAY THIS SEEDS NOTHING, ON PURPOSE". IT SEEDS
NOW — 2026-08-16, DEF-153
------------------------------------------------------------------------------
The old text was accurate when it was written and became the most expensive kind
of comment in this repository the day it stopped being true, so it is REWRITTEN
rather than left standing beside working code (hard-won law 1).

What it said, correctly, was that all four things US-TEN-019 asks for except the
report belonged to the owning modules, and that the blocker was a COLUMN:
BR-TEN-057 puts the tag — `is_sample boolean NOT NULL DEFAULT false` — **on the
owning row**, and every row it names lives in a metering-, assets-, customers-
or rating-owned table that tenancy may not touch (B1 / BR-TEN-013).

**The column landed on 2026-08-16** (`rating 0005`, `metering 0008`,
`assets 0006`, `customers 0010`) and every owning module now publishes its
`seed_sample_records` / `remove_sample_records` pair. So:

  1. the sample RECORDS         → the owning modules'    ✔ built
  2. the `is_sample` tag        → the owning modules'    ✔ built
  3. the removal                → the owning modules'    ✔ built
  4. **the honest report**      → **tenancy's, and it is what this file is**

WHY THAT MATTERED ENOUGH TO BE A CRITICAL DEFECT
--------------------------------------------------
DEF-153, from the Product Owner on the live deployment: *"currently is is not
working even for new tenants"*. The orchestrator, the panel and every documented
seam existed and NOT ONE MODULE IMPLEMENTED THE SEAM, so a brand-new tenant was
empty — zero accounts, zero bills, zero payments — and nobody could evaluate the
product by using it. Because the panel reported the absence honestly, every gate
was satisfied and nothing counted the unimplemented seams as a gap. That is
built-is-not-wired at its purest.

THE HONEST REPORT IS STILL THE POINT
--------------------------------------
A run that reports truthfully that it did nothing is worth building. One that
reports success is DEF-016 exactly — a fixture covered four lists, `charge_codes`
silently skipped because a seam had never been written, the skip went into a
summary nobody read, and the PO found the empty cards by opening Settings on the
live deployment. BR-TEN-060 is that defect's prevention, and it did its job here:
the panel named the missing seams by name for a day, which is how they were
found.

WHAT "NAMED" MEANS HERE (BR-TEN-060)
-------------------------------------
Not a count, not a percentage, not "3 modules skipped". A row per module with a
machine-readable `reason_code` and a sentence an operator can act on, so S62 can
render *"Meter reads — not loaded: metering publishes no seed_sample_records"*.
`run_summary()` additionally answers `succeeded = False` whenever any module is
non-`seeded`: **a run with any skip does not report success**, which is
BR-TEN-056 clause 3 in one boolean.

WHAT IS DELIBERATELY NOT HERE
------------------------------
* **A trigger FOR NEW TENANTS — since 2026-08-17, and it is a REVERSAL.**
  BR-TEN-064 (PO 2026-08-10) made the trigger `on request`, never automatic,
  and TC-1 used to assert provisioning called nothing. CR-010 new mandate 1
  (PO 2026-08-17, verbatim in the decision log: *"we need this seed data …
  we are offering free trials to utilities, they will not able to build all
  data on their own on day one"*) SUPERSEDES that for NEW tenants:
  `provision_tenant` enqueues `PLANT_JOB_KIND` after its commit, gated by the
  S111 `load_defaults` toggle (BR-TEN-067's narrowing — the toggle governs
  sample RECORDS, which is exactly this). EXISTING tenants keep the
  on-request trigger — hard-won law 4, in its data form. TC-1 now asserts the
  new law, both halves.
* **No `seed_demo`-style production refusal.** BR-TEN-064 again: this job runs
  in production because its beneficiary is a real new operator on the live
  system, and it mints no tenant, user, credential or subscription. `seed_demo`
  keeps its refusal because it publishes an owner password; two paths, asserted
  separately.
* **No direct money write.** Tenancy still imports no billing, payments or
  ledger module — B1 / BR-TEN-013 have not moved. What DID move is BR-TEN-056
  clause 1: the sample set no longer stops at reads (PO ruling 2026-08-16), so
  billing and payments seed their OWN money rows through their OWN services,
  reached through the same seam every other block uses. `FORBIDDEN_MODULES` is
  now an empty tuple and says why in its own comment.
"""

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.tenancy import models, sample_errors, sample_notes, seams
from core import audit as core_audit
from core import diagnostics as core_diagnostics
from core import jobs
from core import sample_fixture as fixture
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.tenancy")


class SampleModule:
    """One module's block of the sample set: what it owns, and what it owes.

    `seam` is the function the owning module must publish for its block to run.
    `tables` is what BR-TEN-057 needs an `is_sample` column on before that
    function could tag anything — quoted here so the missing piece is nameable
    rather than merely absent.
    """

    def __init__(self, module: str, seam: str, label: str, tables: tuple[str, ...]) -> None:
        self.module = module
        self.seam = seam
        self.label = label
        self.tables = tables

    @property
    def key(self) -> str:
        """`module:seam` — what identifies a BLOCK, as against a module.

        The ledger row is keyed on the module (BR-TEN-060), and four blocks
        share a module with another. This is the identifier a per-block retry
        names, the key `BLOCK_DEPENDENCIES` is written in, and what
        `sample_data_runs.blocks[].block` is scoped inside.
        """
        return f"{self.module}:{self.seam}"


#: The sample set, in the order BR-TEN-061 reverses for removal. Rating is last
#: because BR-TEN-068 (PO 2026-08-10, OQ-083) puts plans and rate schedules IN
#: the set — tagged, and PROMOTED (tag dropped) the moment a non-sample account
#: references one — so a plan must exist before customers attaches an agreement
#: to it, and must not be removed while a real agreement holds it.
#:
#: ⚠ **ADDING OR REMOVING A ROW HERE MOVES THREE THINGS OUTSIDE THIS FILE, AND
#: TWO OF THEM GO RED. Read this before you edit the tuple.**
#:   1. `10-scripts/gates/g68_plant_on_postgres.py` COUNTS the constructor calls
#:      between this line and the tuple's closing `\n)\n` to write its PASS
#:      sentence. It carried the literal `17` over a tuple one block longer for
#:      a day (`DEF-3509`), which is why it reads the catalogue now. Prose
#:      counts INSIDE this file spell the number out — `_OUTCOME_NOT_STARTED`'s
#:      comment, `step_states`' docstring and the two in `api.py` — and none of
#:      them is read by anything, so they go stale silently on the same edit.
#:      ⚠ **THEY HAVE NOW BEEN WRONG TWICE**: two blocks short from the moment
#:      `CR-070` wave M added the aged-meters and work-rules blocks
#:      (`DEF-WRK-4085`), and again when `CR-083` added the integrations block.
#:      Say TWENTY-EIGHT or say nothing — and note that `test_cr064_tc10` is the
#:      only thing that will tell you, so run it. ⚠ **AND WIDEN THAT TEST'S
#:      WORD LIST WHEN THE TUPLE PASSES ITS TOP**: it stopped short of the
#:      tuple's own length for two days and was therefore red at the tip,
#:      refusing to answer rather than answering wrongly. Its own message says
#:      *widen it rather than deleting it*.
#:   2. `07-frontend/src/features/tenancy/provisioningSteps.test.ts` counts the
#:      SAME calls, so a row added here without moving that test turns it red.
#:   3. A row whose module publishes no such seam is a NAMED not-loaded line
#:      (BR-TEN-060) and `run_summary()` then answers `succeeded = False` — so
#:      G68 goes PASS → FAIL until the owning module implements it. That is the
#:      rule working, not a surprise, but it means the row and its seam land in
#:      ONE commit or the branch is merge-blocked in between.
#:
#: ⚠ **AND THE LEDGER HAS NO ROW HERE AT ALL, WHICH IS `CR-060` C26's REAL
#: BLOCKER.** Seven modules appear below and `ledger` is not one of them, so a
#: captured supplier invoice has no seam to be written through and no block to
#: be reported in — and *"a supplier invoice per building"* is one of the four
#: things C26's acceptance line asks for. `CR-060` T3(b) describes that work as
#: *"the eight `seed_sample_records` seams"*; measured against the code on
#: 2026-09-03 it is also a second tenant (only `seed_demo.py` provisions one,
#: and its payload is a module constant), a second estate shape in
#: `core/sample_fixture.py`, and the master/member accounts in
#: `apps/customers/sample_data.py`. The full measurement, and why that lane
#: wrote nothing rather than half of it, is the 2026-09-03 row in
#: `12-governance/02-decision-log.md`.
SAMPLE_MODULES: tuple[SampleModule, ...] = (
    # ── CR-010 new mandate 1 (PO 2026-08-17): *"along with member login i
    # will create 2 new sample users"* — a Billing Clerk and an Executive,
    # invited and uncredentialed (identity discards their temp passwords
    # unread, so the OWNER stays the only login). First in creation order
    # because they depend on nothing; BR-TEN-061's reversal handles the rest.
    SampleModule(
        "identity",
        "seed_sample_records",
        "Sample staff users (Billing Clerk + Executive, invitation-pending)",
        ("users", "tenant_memberships"),
    ),
    SampleModule(
        "rating",
        "seed_sample_records",
        "Plans & rates",
        ("rate_plans", "plan_services", "tariffs"),
    ),
    SampleModule(
        "metering",
        "seed_sample_records",
        "Premises, units & service points",
        ("premises", "units", "service_points"),
    ),
    SampleModule(
        "assets",
        "seed_sample_records",
        "Meters",
        ("assets", "asset_assignments"),
    ),
    # ── CR-070 wave M · M5 (DEF-WRK-4085) ──────────────────────────────────
    # *"Fixture: AST-04412 and two more meters past certification life"*.
    #
    # ⚠ **AN `assets` BLOCK FOR A `work` FIXTURE, AND IT HAS TO BE.** Work may
    # not write `assets` (`BR-WRK-002`; `G78` fails a foreign write from Work's
    # first commit), so the RULES are the `work` block near the end of this
    # tuple and the SUBJECTS they fire on are here, in the module that owns the
    # table. Work reads them back through `seams/assets_seam`.
    #
    # ⚠ **ITS OWN BLOCK RATHER THAN THREE MORE ROWS IN THE METERS BLOCK ABOVE**
    # — `BR-TEN-060`. Three assets inside a block that writes ~130 are invisible
    # whether they land or not; a named line on `S62` can be seen to have
    # failed. It also leaves that block's counts and its tests untouched.
    SampleModule(
        "assets",
        "seed_sample_aged_meters",
        "Meters past their certification life (what the nightly rule finds)",
        ("assets",),
    ),
    SampleModule(
        "customers",
        "seed_sample_records",
        "Accounts, customers & service agreements",
        (
            "accounts",
            "customers",
            "customer_accounts",
            "contacts",
            "addresses",
            "service_agreements",
        ),
    ),
    # ── DEF-MET-6302 · THE OWNERS' ACCOUNTS (PO 2026-09-23) ────────────────
    # PO verbatim: ***"attach master accounts to the sample data"***, after
    # creating one by hand, linking it to a premises, and finding the Premises
    # list's Owner column empty on every row. Measured on a seeded clone that
    # day: **79 premises, 0 naming a master account**.
    #
    # ⚠ **THE POSITION IS THE FEATURE, the same way the enrolment below says it
    # is.** These accounts are opened through metering's `ensure_master_account_
    # for_premises`, which reaches customers' own `create_master_account` — so
    # they must come AFTER the block above, or four accounts would take numbers
    # ahead of the estate's fifty and renumber every one of them (BR-TEN-035).
    # Moving it earlier writes nothing: there is no seeded address to own yet.
    #
    # ⚠ **AND IT IS ITS OWN BLOCK RATHER THAN FOUR MORE ROWS IN THE ONE ABOVE**
    # — `BR-TEN-060`, the same reasoning `assets:seed_sample_aged_meters` gives.
    # Four accounts inside a block that writes fifty are invisible whether they
    # land or not; a named line on the panel can be SEEN to have failed. It also
    # leaves that block's counts and its tests untouched.
    #
    # ⚠ **`premises` IS NOT IN ITS TABLE LIST, DELIBERATELY.** This block causes
    # `premises.master_account_id` to be written, but METERING writes it, under
    # metering's own audit row; `tables` is what BR-TEN-057 needs an `is_sample`
    # column on, and the tag here goes on the `accounts` family.
    SampleModule(
        "customers",
        "seed_sample_owner_accounts",
        "Owner accounts (the master account on the addresses that have a landlord)",
        (
            "accounts",
            "customers",
            "customer_accounts",
            "contacts",
            "addresses",
            "service_agreements",
        ),
    ),
    # ── CR-062 ADDENDUM J2 · THE FIRST SEEDED ENROLMENT (PO 2026-09-02) ─────
    # PO verbatim: *"What is the government discount called? Municipal account -
    # yes; What rate? 20% off the bill before taxes - yes"*.
    #
    # ⚠ **THE POSITION IS THE FEATURE, exactly as it is for the money blocks
    # below.** An enrolment needs an ACCOUNT, and rating's own block runs before
    # customers' — it has to, because a plan must exist before customers can
    # attach an agreement to one. Moving this row up beside `rating:seed_sample_
    # records` writes NOTHING: there is no account to grant to, and the block's
    # own named no-op fires. Moving it down past the billing block writes the
    # same row and destroys what it demonstrates — the reduction would miss the
    # June document a person opens.
    #
    # **Worked:** the seeded municipal building's water + sewer + trash subtotal
    # is $157.50; the Municipal discount takes $31.50 and it pays $126.00.
    # ⚠ $129.70 / $25.94 / $103.76 until `CR-081` (2026-09-08) moved the sewer
    # line from $26.20 (40% of the water charge) to $54.00 (90% of 12 kgal).
    SampleModule(
        "rating",
        "seed_sample_enrolments",
        "The Municipal discount, granted to the municipal account",
        ("discount_enrolments",),
    ),
    SampleModule(
        "metering",
        "seed_sample_reads",
        "Meter reads",
        ("meter_reads",),
    ),
    # ── PO ruling 2026-09-07 — THE PORTAL'S OWN SELF-SERVICE DATA (CR-082) ──
    # Verbatim: *"before step 29 this - you ahve to set all the self service
    # data in settings -> configure -> Customer portal - {overview, branding,
    # Help & Answer, Tips  + service centers }"*, where step 29 of the plan
    # they were shown is *"a customer who can sign into the portal"*.
    #
    # ⚠ **BOTH SEEDERS ALREADY EXISTED AND NEITHER WAS EVER REACHED FROM HERE.**
    # `apps/tenancy/published_content_sample.py` (answers, tips, centres) and
    # `apps/portal/sample_data.py` (the switches and the branding) are called
    # ONLY by `manage.py seed_portal_demo`, which builds the two hand-made demo
    # tenants. Measured 2026-09-07: `pine-hill` held 1 settings row, 8 answers,
    # 6 tips and 3 centres; `brazosbend` and every tenant provisioned through
    # the real sign-up path held **zero of all seven tables**. Built, and not
    # wired — CLAUDE.md hard-won law 2, and the third instance of that shape
    # found on one day.
    #
    # ⚠ **THE ORDER IS THE RULING AND NOT A CONVENIENCE.** Configuration first,
    # login second: a customer who signs in to an unconfigured portal sees
    # branding that is not there, no answers, no tips and no counter to walk
    # into.
    #
    # ⚠ **AND THE MODULE IS `tenancy` BECAUSE `G81` REFUSES A SEEDING SEAM IN
    # `apps/portal/services.py`** — that file may hold only the portal's six
    # declared write points. Every row is still written by the module that owns
    # its table; `apps/tenancy/portal_sample.py` is the body and says why.
    SampleModule(
        "tenancy",
        "seed_sample_portal_content",
        "The customer portal — switched on, branded, with answers, tips and counters",
        (
            "portal_settings",
            "help_answers",
            "help_answer_variants",
            "help_answer_feedback",
            "tips",
            "service_centres",
            "service_centre_hours",
        ),
    ),
    # ⚠ **MOVED AHEAD OF THE MONEY ON 2026-09-23 (`DEF-PAY-6321`), AND THE
    # RULING ABOVE IS UNTOUCHED BY THE MOVE.** It says *configuration first,
    # login second*, and the login is still last; what it never said is where
    # the configuration sits relative to the money. It sat AFTER it, so the
    # SERVICE CENTRES — which live in this block — did not exist when the
    # payments block ran, and **a counter is a till AT a place**: the sample
    # utility could not open one, so no counter payment could name a till, so
    # no deposit batch could exist, so the Payments list's BATCH column read
    # *No batch yet* over every row the Product Owner looked at.
    #
    # It is also the more truthful order. A utility sets up the desks customers
    # walk into before it starts taking their money at them; the old order had
    # the counters appear after a month of counter receipts.
    #
    # Nothing else in this block cares where it runs: `seed_published_content`
    # and `seed_sample_portal_settings` are both idempotent BY REFUSAL and
    # neither reads an account, a bill or a payment.
    # ── the MONEY blocks (BR-TEN-056 clause 1 as AMENDED, PO 2026-08-16) ────
    # These two were forbidden until 2026-08-16 and the reason was sound:
    # invoices, lines, payments and journal entries are append-only (hard rule
    # 4), so a sample row there can never be removed. The Product Owner ruled
    # the other way — *"if we are able to seed the data refernece as well as
    # transaction data, then we can test the application end to end and see
    # what are the issues"* — and the fixture spec of the same day requires
    # June and July BILLED and mostly PAID.
    #
    # THE OLD REASONING IS PRICED, NOT DISCARDED: removal becomes PARTIAL, and
    # both blocks report BY NAME what cannot be removed (BR-TEN-066).
    SampleModule(
        "billing",
        "seed_sample_records",
        # ⚠ **THIS LABEL SAID "June billed — July is staged and yours to run"
        # UNTIL 2026-08-27 AND IT BECAME FALSE THAT DAY** (CR-040 task C9): July
        # is billed by the second-cycle block below. A label is what an operator
        # reads on the Sample data panel, so a stale one is a comment claiming a
        # guarantee (hard-won law 1) with a screen attached to it.
        # CR-010 Part-10.4's *"ONE month billed, the next READY"* is superseded;
        # what survives it is that the LAST period stays unbilled, and August
        # still is.
        "Bills, first cycle (June — issued and mostly paid)",
        ("invoices", "invoice_lines"),
    ),
    SampleModule(
        "payments",
        "seed_sample_records",
        "Payments, deposits and the bank statement",
        ("payments", "allocations"),
    ),
    # ── CR-040 tasks D12 · D13 · D14 (PO 2026-08-27) ────────────────────────
    # *"you need credit and refunds cases, overcharge cases, creit cases"*.
    #
    # ⚠ **D14 IS THE REQUIREMENT AND IT IS A POSITION, NOT A CONTENT.** Both
    # blocks sit HERE — after the payments block, before the second billing
    # block — and moving either one outside that gap writes exactly the same
    # rows while destroying what they demonstrate:
    #
    #   * an overcharge correction **cannot exist before run 1**: it corrects a
    #     bill that has issued, and there is none;
    #   * a refund or a correction written **after run 2** is a row rather than
    #     a history — the second cycle would then bill an estate that had never
    #     been credited, refunded or corrected, which is the one thing wave C
    #     split the billing block to make possible.
    #
    # The ordering is asserted on `created_at` in
    # `tests/test_cr040_wave_d_money_between_cycles.py` — the only clock the
    # fixture does not choose. The business dates on these rows are July, which
    # is BEFORE the busy day the payments above are dated on, so a test that
    # compared business dates would read the order backwards and pass on a
    # tree where the blocks had been swapped (the mistake `test_cr040_two_
    # cycles.py` records making).
    #
    # ⚠ **THE REFUND IS A `payments` BLOCK AND THE CORRECTION IS A `billing`
    # ONE**, even though they are one story: each module owns its own tables
    # and drives its own services (B1 / BR-TEN-013). The refund's four steps are
    # `apps/payments/refunds.py`'s; the correction's three are
    # `apps/billing/bulk_corrections.py`'s, and the READ it corrects underneath
    # is superseded through metering's own `correct_billed_read` — BR-MET-053's
    # only door for a reading a bill has already priced.
    SampleModule(
        "payments",
        "seed_sample_refund",
        "A refund (requested, approved, issued, cleared — spec §4 case 14)",
        ("refunds",),
    ),
    # ── CR-059 CS-12 / task 74 (2026-09-03) ────────────────────────────────
    # ⚠ **THE POSITION IS THE FEATURE, exactly as the refund's is.** This cheque
    # settles the landlord's THREE June bills, which `payments:seed_sample_
    # records` above deliberately leaves open (`_share_for`), so it must run
    # AFTER that block and BEFORE the second billing cycle — a multi-property
    # cheque dated 8 August that arrived after July had billed would be paying
    # bills the demo's own timeline says were already settled.
    SampleModule(
        "payments",
        "seed_sample_multi_account_tender",
        "One cheque covering three properties of one customer (CR-059 CS-12)",
        ("payment_tenders", "payments", "allocations"),
    ),
    SampleModule(
        "billing",
        "seed_sample_correction",
        "An overcharge, corrected (restatement — spec §4 case 15)",
        ("correction_cases", "correction_case_bills", "invoices", "invoice_lines"),
    ),
    # ── CR-040 task C8 (PO 2026-08-27) ──────────────────────────────────────
    # *"first you will run first billing, then you will create payment record,
    # refunds, credit over charges records, add meter reading for second month
    # and then again run the billing"*.
    #
    # ⚠ **THE POSITION IN THIS TUPLE IS THE FEATURE.** Billing appears TWICE
    # and the payments block sits between the two, because the second cycle
    # exists to bill an estate that has a financial past — collections, a credit
    # balance, a refund and an overcharge correction. Move this row up beside
    # the first billing block and every ROW it writes is identical while the
    # HISTORY it demonstrates disappears, which is the kind of change that
    # looks like tidying and is not.
    #
    # ⚠ **AND IT CHANGES WHEN BILLING'S MODULE VERDICT MAY BE DERIVED.** The
    # `owned` set below is every seam a module has in this tuple, and a module's
    # verdict is re-derived only once EVERY owned block is recorded. Billing now
    # owns two, so a run that seeds cycle one and dies before cycle two leaves
    # billing's verdict on the failing block rather than reporting the module
    # seeded. That is the existing rule doing its job, not a new one.
    # ── THE SECOND CYCLE'S WALK (PO 2026-09-01) ─────────────────────────────
    # PO verbatim: *"reading data when you seed first time add reading then bill
    # it, then add reading data again, then bill it and then again add reading
    # data - you can not add reading data once for 3 months"*.
    #
    # ⚠ **THE POSITION IS THE FEATURE, AND IT IS THE THIRD TIME THAT SENTENCE
    # HAS HAD TO BE WRITTEN IN THIS TUPLE.** Between the correction and the
    # second bill run: the readings cycle two bills are taken AFTER cycle one
    # has been billed and paid, which is the order a utility works in. Moving
    # this row up beside `metering:seed_sample_reads` writes byte-identical rows
    # and destroys the thing it demonstrates — exactly what the payments block
    # and the second billing block already say about themselves.
    SampleModule(
        "metering",
        "seed_sample_second_cycle_reads",
        "Meter reads for the second cycle (walked after the first bill)",
        ("meter_reads",),
    ),
    SampleModule(
        "billing",
        "seed_sample_second_cycle",
        "Bills, second cycle (July — billed after the money above)",
        ("invoices", "invoice_lines"),
    ),
    # ── THE THIRD-CYCLE STEP (PO 2026-09-01) ────────────────────────────────
    # PO verbatim: *"we have seed data process that seed data at the time of new
    # tenant creation - I want to know all steps are working, secondly after
    # second bill is generated, I want to add another step which will add -
    # meter reads and payment data - so that We can run the next bill cycle on
    # our own and see how it is working?"* — and, when it was put to them a
    # second time: *"Without meter reads for 3rd cycle billing cycle will not
    # run - hence you have to add meter reads also."*
    #
    # ⚠ **TWO BLOCKS, BECAUSE EACH MODULE OWNS ITS OWN TABLES (B1 /
    # BR-TEN-013)** — metering writes `meter_reads` and payments writes
    # `payments`, and one block spanning both would be a cross-module write.
    # The same split `customers:seed_sample_payment_plans` +
    # `payments:seed_sample_plan_payments` already makes for one story.
    #
    # ⚠ **THE POSITION IS THE FEATURE, EXACTLY AS IT IS FOR THE BLOCK ABOVE.**
    # The walk is posted AFTER the second cycle because that is when a clerk
    # walks it — the third month's readings used to be handed in before June was
    # billed, which is not a thing any utility does — and the collections are
    # recorded after the bills they pay exist, because before that there is
    # nothing to pay.
    SampleModule(
        "metering",
        "seed_sample_next_cycle_reads",
        "Meter reads for the cycle YOU run (the third month's walk)",
        ("meter_reads",),
    ),
    SampleModule(
        "payments",
        "seed_sample_cycle_collections",
        "Collections against the second cycle (paid, part-paid, unpaid, overpaid)",
        ("payments", "allocations"),
    ),
    # ── THE ONE TENANCY THAT ENDS (DEF-CUS-4628, 2026-09-07) ────────────────
    # Measured on a freshly planted `brazosbend` that morning: **69 Active, 1
    # Marked disconnect, 1 Pending activation, 1 Vacation hold, and ZERO
    # accounts with a `closed_at`** — on every seeded tenant this product has
    # ever built. `Closed` is the TERMINAL state the whole move-out flow exists
    # to reach, and nothing had ever reached it, so the button, the wizard and
    # every screen that draws a finished tenancy had never been walked against
    # real data.
    #
    # ⚠ **THE POSITION IS THE FEATURE, exactly as it is for the refund and the
    # correction above.** A closed account is not in
    # `OCCUPYING_BEHAVIOR_CLASSES`, so it leaves `accounts_in_cycle` and no bill
    # run can see it: move this row ABOVE either billing block and the estate
    # loses two of that account's bills, its collections and its August reading
    # story. Here, the tenancy is billed twice, part-collected exactly as the
    # fixture intends, and only then ends — which is the order a real move-out
    # happens in.
    SampleModule(
        "customers",
        "seed_sample_move_out",
        "A move-out, right through to closed",
        ("accounts", "service_agreements", "move_records"),
    ),
    # ── the COLLECTIONS block (CR-010 Part-10.4 amendment 3, PO 2026-08-17) ──
    # *"you did not cover outstanding repcrds, payment plans"* — the seeded
    # tenant carries a REAL `payment_plans` row with instalments, mid-plan, on
    # a genuinely outstanding June balance. Two blocks, because the tables
    # split across the module boundary exactly as the product splits them:
    # customers drives the S24 wizard (schedule math is GT-47's, BR-CUS-043)
    # and hands the rows to payments through the wizard's own seam; payments
    # then records the down payment and the instalment payments through
    # record_payment, its own and only writer of `payments`.
    SampleModule(
        "customers",
        "seed_sample_payment_plans",
        "Payment plan (live, mid-schedule — spec §4 case 6)",
        ("payment_plans", "payment_plan_installments"),
    ),
    SampleModule(
        "payments",
        "seed_sample_plan_payments",
        "Payment-plan money (down payment + paid instalments)",
        ("payments", "allocations"),
    ),
    # ── CR-035 step 6 row 6 (PO 2026-08-26) ─────────────────────────────────
    # *"a seeded parked example, so the screen is not empty on a demo."* ONE
    # parked move-in draft, so Accounts → **Waiting on** (S17.2) demonstrates
    # the feature instead of an empty state.
    #
    # ⚠ **LAST IN CREATION ORDER, WHICH MAKES IT FIRST TO BE REMOVED — and it
    # depends on nothing.** `wizard_parks` carries no foreign key to anything it
    # describes (BR-SHL-048 (a)), so it can neither hold another block open nor
    # be held open by one. It is placed last because it READS the estate above:
    # the draft's subject is the one seeded unit that is vacant.
    #
    # ⚠ **AND IT IS A `customers` BLOCK OVER A `tenancy`-HOSTED TABLE.** The
    # five parkable flows span two modules, so the table sits on the shell's
    # scratch pad (`models.WizardPark`: *"hosting ≠ owning"*) while the fixture
    # rows it plants are B18 §5.5.7's, which are customers'. The write goes
    # through `apps.tenancy.wizard_parks.park` via `apps/customers/seams.py` —
    # BR-TEN-013's *"cross-module writes via the owning module's own service
    # function ONLY"*.
    #
    # ⛔ **`wizard_parks` HAS NO `is_sample` COLUMN**, so BR-TEN-057's predicate
    # does not exist for it and removal is keyed on the seeded draft itself
    # (`remove_sample_wizard_parks`, a NARROWER key — a clerk's own draft is
    # never touched). The column is **OWED**; the same divergence
    # `disconnect_cases`, `disconnect_notices` and `account_protections` already
    # carry, reported the same way rather than papered over.
    # ── CR-070 wave M · M5 (DEF-WRK-4085) ──────────────────────────────────
    # **THE ELEVENTH MODULE'S FIRST BLOCK.** Wave M shipped a nightly rules
    # engine and could not run its own demo, because `work` was not a
    # sample-data module and a freshly seeded tenant held ZERO rules — the
    # engine proved on 25 cases, the SCREEN proved by nothing (hard-won law 6).
    #
    # ⚠ **THE POSITION IS THE FEATURE, exactly as it is for the money blocks
    # above, and for TWO independent reasons.**
    #
    #   * **Creation:** `work_order_rules.template` is NOT NULL and refused with
    #     a sentence when it is missing, and the template it points at —
    #     *Meter exchange — residential* — is published by
    #     `metering:seed_sample_records` at the top of this tuple. Moving this
    #     row above it seeds NOTHING and reports the named refusal every time.
    #   * **Removal, which walks this tuple BACKWARDS (`BR-TEN-061`):** a rule
    #     holds a PROTECT foreign key to that template and to a
    #     `work_priorities` row. Removed after them, every delete would be
    #     refused; removed before them — which is what being late here buys —
    #     the rules go first and the templates are then free.
    # ── CR-070 · THE CREW (2026-09-07) ─────────────────────────────────────
    # **THIRTY-NINE WORK ORDERS AND NOBODY TO SEND.** Measured that day across
    # all six seeded tenants: `crews` 0, `technicians` 0, `technician_skills`
    # 0, `technician_certifications` 0, `parts` 0, `labour_rates` 0,
    # `work_settings` 0 — against 39 raised work orders, 8 skills, 6
    # certificate types and 4 part categories, every one of those a REFERENCE
    # list seeded at provisioning with nobody and no price attached. So Work >
    # Crews opened onto an empty table and **no work order in the product could
    # be costed**, because costing multiplies a labour rate by minutes.
    #
    # ⚠ **THE POSITION IS A FOREIGN KEY, not a preference.**
    # `technicians.user_id` is NOT NULL and Work may not create a login
    # (`BR-WRK-002`; `G78` fails the merge), so the four field-technician
    # logins are `identity:seed_sample_records`' — the FIRST row of this tuple
    # — and this block attaches a profile to each. Placed above them it seeds
    # the crews, the parts and the rates and reports the technicians as not
    # loaded BY NAME, which is `BR-TEN-060` working and still the wrong answer.
    #
    # Removal walks this tuple BACKWARDS (`BR-TEN-061`), and technicians
    # PROTECT their crew while materials PROTECT their part — so this block
    # going late is also what lets its own removal succeed.
    SampleModule(
        "work",
        "seed_sample_workforce",
        "Crews, technicians, parts and labour rates",
        ("crews", "technicians", "parts", "labour_rates"),
    ),
    # ── CR-070 · THE JOB (2026-09-07) ──────────────────────────────────────
    # **A TEMPLATE WITH NO TASKS IS A FORM WITH NO QUESTIONS.** The same
    # measurement found six published templates with six `wot_details` rows and
    # `wot_tasks` 0, `wot_materials` 0, `wot_readings` 0, `wot_safety` 0,
    # `wot_help` 0, `wot_asset_types` 0 — and downstream, `work_order_tasks` 0,
    # `work_order_assignments` 0, `work_order_cost_lines` 0.
    #
    # ⚠ **IT FILLS THE SIX THAT EXIST AND CREATES NO SEVENTH** (hard-won law
    # 5: one source of truth). It runs AFTER the workforce block because a
    # template requiring a skill nobody holds is a job the dispatcher can never
    # assign — `skill_match()` would offer an empty candidate list, correctly,
    # with nothing on the screen to say why.
    #
    # ⛔ **NONE OF ITS TABLES CARRIES `is_sample`**, so the `tables` tuple below
    # names them for `BR-TEN-057` to be able to see what is owed. Removal is a
    # NAMED REFUSAL rather than a delete, for three reasons each already ruled
    # elsewhere: a published template's content is a VERSION (`BR-WRK-011`), an
    # assignment history is APPEND-ONLY (`BR-WRK-025`, and a PostgreSQL trigger
    # enforces it), and a cost line is FROZEN (`work/0011`).
    SampleModule(
        "work",
        "seed_sample_field_work",
        "Filled job templates, and one job assigned, worked and costed",
        (
            "wot_tasks",
            "wot_materials",
            "wot_readings",
            "wot_safety",
            "wot_help",
            "wot_asset_types",
            "work_order_assignments",
            "work_order_cost_lines",
        ),
    ),
    SampleModule(
        "work",
        "seed_sample_records",
        "Rules that raise work orders on their own (seven, six on)",
        ("work_order_rules",),
    ),
    SampleModule(
        "customers",
        "seed_sample_wizard_parks",
        "A parked move-in (Waiting on — S17.2)",
        ("wizard_parks",),
    ),
    # ⚠ **LAST, AND AFTER THE MONEY.** The seeded customer signs in to their own
    # bills, payments and readings; enrolled before those blocks they would open
    # a portal with an account and nothing in it. It also has to be after
    # `customers:seed_sample_records`, because `create_credential` REFUSES an
    # account with no `customer_accounts` row — *"this account is linked to no
    # customer, so there is nobody to enrol"*.
    SampleModule(
        "tenancy",
        "seed_sample_portal_login",
        "A customer who can sign in to the portal",
        ("portal_credentials",),
    ),
    # ── PO ruling 2026-09-07 — "STEP 30, INTEGRATIONS" (`CR-083`) ───────────
    # Verbatim: *"Im okay with this - please add- Step 30, Integrations"*,
    # where step 29 of the plan they were shown is the portal login above. The
    # four-part plan that sentence approved is written out in full in
    # `12-governance/02-decision-log.md`, 2026-09-07, because *"I'm okay with
    # this"* is a complete answer that carries none of what it approved.
    #
    # ⚠ **THE SEEDER HAS BEEN FINISHED AND UNREACHED SINCE 2026-09-04.**
    # `apps/integrations/sample_runs.py` writes five runs through the real
    # `start_run`/`finish_run` so `BR-INT-018` COMPUTES every outcome word —
    # and `"integrations"` appeared in this tuple ZERO times, so the only
    # tenant that ever held a run was one somebody had typed a management
    # command at. Every tenant provisioned through the real sign-up path read
    # **0** on every integrations table. Built, and not wired — CLAUDE.md
    # hard-won law 2, and the fourth instance of that shape found in a week.
    #
    # ⚠ **THE POSITION IS THE FEATURE, exactly as it is for the money blocks
    # above.** The block records one ACCOUNTING HANDOVER, and a handover needs
    # a month that is CLOSED with books that foot (`BR-LED-017`/`BR-LED-007`).
    # Last is the only place where the first cycle's accounting month can
    # honestly be shut: both cycles have billed, the refund, the correction and
    # the collections have all been written, and nothing after this posts into
    # it. Moved up beside the billing blocks it would seed the same three
    # connections and record no handover at all.
    #
    # ⚠ **THE MONTH IS JULY AND NOT JUNE, WHICH IS NOT WHAT ANYONE GUESSES.**
    # The demo bills June and ISSUES those bills on 2 July, so the earliest
    # journal entry a seeded tenant holds is dated 2026-07-02 and June contains
    # none at all. A June batch was recorded on a proof tenant on 2026-09-07 and
    # came back with 0 rows and the content hash of an empty list — lawful,
    # useless, and invisible to every check in this repository. The block
    # derives the month from `bill_on` for that reason.
    #
    # ⛔ **`integration_connection`, `integration_run` AND `export_batches`
    # HAVE NO `is_sample` COLUMN**, so `BR-TEN-057`'s predicate does not exist
    # for them and removal is keyed on the fixture's own labels — a NARROWER
    # key, so a mail server the utility connected itself is never touched. The
    # runs are append-only (`BR-INT-039`) and the batch is a financial record
    # (hard rule 4), so both are RETAINED BY NAME (`BR-TEN-066`). The column is
    # OWED on the connection table; the same divergence `wizard_parks`,
    # `disconnect_cases` and `account_protections` already carry.
    SampleModule(
        "integrations",
        "seed_sample_records",
        "Integrations — the mail server, the meter cloud and the bank's file, with what has run",
        ("integration_connection", "integration_run"),
    ),
)

#: ⚠ EMPTY SINCE 2026-08-16, AND THE EMPTINESS IS THE RULING.
#:
#: This tuple was `("billing", "payments", "ledger")` and enforced BR-TEN-056
#: clause 1 — *"the sample set stops at reads"* — as a checkable fact rather
#: than a promise. The Product Owner amended the rule on 2026-08-16 (see
#: SAMPLE_MODULES above and `04-docs/05-modules/01-tenancy/02-business-rules.md`),
#: so the constraint it encoded is no longer the law and a test that still
#: asserted it would be pinning a superseded rule.
#:
#: It is kept as an EMPTY tuple rather than deleted, and that is deliberate:
#: tenancy STILL may not import billing, payments or ledger directly (B1 /
#: BR-TEN-013). What changed is only WHICH MODULES may seed their own money
#: rows through their OWN services — which is exactly what the seam mechanism
#: already does, and why no import appears in this file either way.
FORBIDDEN_MODULES: tuple[str, ...] = ()

OUTCOME_SEEDED = "seeded"
OUTCOME_SKIPPED = "skipped"
OUTCOME_FAILED = "failed"

REASON_SEAM_NOT_WIRED = "seam_not_wired"
REASON_EXCEPTION = "exception"

#: The run-level row that has always been written: totals only, once per run.
AUDIT_RUN = "sample.seeded"
#: CR-039 wave B task 10 — ONE row per FAILED block, with its stable code.
AUDIT_BLOCK_FAILED = "sample.block_failed"
#: CR-039 wave B task 8 — a single block re-run on its own.
AUDIT_BLOCK_RETRIED = "sample.block_retried"

#: A failure that nothing upstream explains — the block that ACTUALLY broke.
FAILURE_ROOT = "root"
#: A failure downstream of one already reported. Honest, and not the one to fix.
FAILURE_CONSEQUENCE = "consequence"


# ══════════════════════════════════════════════════════════════════════════
# WHICH BLOCK NEEDS WHICH — CR-039 wave B task 7 (PO 2026-08-26)
# ══════════════════════════════════════════════════════════════════════════
# THE PROBLEM, MEASURED RATHER THAN IMAGINED. `apps/assets/sample_data.py`
# records it in its own comment, from the day it happened (DEF-660, 2026-08-24):
# a retirement in the meters block made the reads batch refuse, and that took
# *"billing, payments, the payment plan and all plan money with it in a chain of
# five failures that read like five separate bugs."* Five reds, one cause, and
# an operator with no way to tell which one to fix.
#
# ⚠ **EVERY EDGE BELOW IS QUOTED FROM CODE THAT ALREADY STATED IT, AND NOTHING
# ELSE IS DECLARED.** The temptation here is to write down the dependency graph
# everyone "knows" — reads need meters, meters need units, bills need reads. Some
# of that is stated in the code and some of it is folklore, and a graph nobody
# ratified would be this file inventing law (CLAUDE.md: never resolve an open
# question by choosing a value). So an edge exists here only where a seeder or
# this file ALREADY says so in words, the words are quoted verbatim beside it,
# and `test_cr039_…::…_every_declared_edge_is_quoted_from_the_file_it_cites`
# greps each quote out of the file it names — so a reworded seeder turns the
# citation RED instead of leaving a silent invention behind.
#
# Four blocks declare NO dependency and can therefore only ever be reported as
# ROOT: identity's staff users, rating's plans, metering's premises/units, and
# the parked move-in (whose own comment says it *"depends on nothing"*).
# THAT IS A REPORTED GAP, NOT A CLAIM OF INDEPENDENCE: the reads block's
# dependency on ASSETS is stated, `customers` needing units is stated, and
# whether e.g. rating must precede billing is not stated anywhere a lane may
# read. Those stay unmarked rather than guessed.
#: The blocks that depend on NOTHING — declared, because an empty edge list and
#: an unconsidered block look identical in a dict that only holds edges.
#:
#: ⚠ **THIS EXISTS BECAUSE THREE BLOCKS LANDED EDGELESS AND NOTHING OBJECTED
#: (CR-040 task E17, 2026-08-27).** CR-039 wave B built the dependency graph and
#: two tests over it, and both ask *"is every declared edge true?"* — neither can
#: ask *"is every block declared?"*, so a graph can be perfectly honest and half
#: empty. Waves C and D then added `payments:seed_sample_refund`,
#: `billing:seed_sample_correction` and `billing:seed_sample_second_cycle` with
#: no edges, and `_root_for` marked all three as their own ROOT: an operator
#: whose first bill run failed was told *"Start here"* four times over one cause.
#:
#: ⚠ **A ROOT CARRIES NO QUOTE AND AN EDGE DOES, deliberately.** An edge is a
#: CLAIM about the code and is greppable back out of it; a root is the ABSENCE
#: of a claim, so there is no sentence to cite and what is checked instead is
#: that somebody decided. The reasoning for each of the four is in the comment
#: block below, exactly where it already was.
ROOT_BLOCKS: frozenset[str] = frozenset(
    {
        # "First in creation order because they depend on nothing."
        "identity:seed_sample_records",
        # Plans and rate schedules are the priced catalogue everything else
        # attaches to; nothing in the sample set has to exist before them.
        "rating:seed_sample_records",
        # Premises and units are the estate. Every other block seats something
        # on them.
        "metering:seed_sample_records",
        # Its own comment: *"it depends on nothing"* — `wizard_parks` carries no
        # foreign key to anything it describes (BR-SHL-048 (a)), so it can
        # neither hold another block open nor be held open by one.
        "customers:seed_sample_wizard_parks",
        # PO 2026-09-07. The portal's configuration stands on the TENANT, not on
        # the sample estate: the switches are the tenant's own row, the branding
        # offers the services it ticked at sign-up (both facts of provisioning,
        # not of any block above), and the answers, tips and centres are text
        # that points at nothing. It is late in the tuple because the ruling puts
        # it immediately before the login, not because anything holds it back.
        "tenancy:seed_sample_portal_content",
    }
)

BLOCK_DEPENDENCIES: dict[str, tuple[tuple[str, str, str], ...]] = {
    # (upstream block key, the file that states it, the words it states it in)
    # PO 2026-09-07 — a login needs somebody to belong to. `create_credential`
    # refuses an account with no `customer_accounts` row, and the seeder says so
    # in its own words rather than this file inventing the edge.
    "tenancy:seed_sample_portal_login": (
        (
            "customers:seed_sample_records",
            "apps/portal/sample_data.py",
            "this account is linked to no customer, so there is nobody to enrol",
        ),
    ),
    "assets:seed_sample_records": (
        (
            "metering:seed_sample_records",
            "apps/assets/sample_data.py",
            # ⚠ AMENDED BY THE MERGE LANE 2026-08-26. This quote read "One WATER
            # meter per seeded unit" until CR-039 wave A made the estate
            # service-shaped and rewrote that sentence — so this test went RED
            # on the merge, correctly, and it is the only check in the repo that
            # could have. That is what quoting VERBATIM buys: a dependency
            # declared from prose stays true only while the prose does, and an
            # edge whose evidence has moved is an edge nobody has re-checked.
            # The new sentence carries the same claim (assets seeds meters onto
            # units that metering's block created) in the service-agnostic form.
            "meter per seeded unit",
        ),
    ),
    # CR-062 addendum J2 — a grant needs an ACCOUNT and an ACTIVE discount, so
    # this block stands on both of the blocks that make those.
    # DEF-MET-6302 — an owner's account needs an ADDRESS to stand on and a UNIT
    # COUNT to be selected by, and metering's estate block plants both. The
    # second edge is the account NUMBER SERIES rather than a row: four accounts
    # opened ahead of the estate's fifty would renumber every one of them.
    "customers:seed_sample_owner_accounts": (
        (
            "metering:seed_sample_records",
            "apps/customers/sample_owner_accounts.py",
            "metering's estate block has planted the premises",
        ),
        (
            "customers:seed_sample_records",
            "apps/customers/sample_owner_accounts.py",
            "places the block after the fifty",
        ),
    ),
    "rating:seed_sample_enrolments": (
        (
            "customers:seed_sample_records",
            "apps/rating/discount_sample_data.py",
            "AFTER the Accounts block and BEFORE the first bill run",
        ),
        (
            "rating:seed_sample_records",
            "apps/rating/discount_sample_data.py",
            "discount is not on file, so the seeded",
        ),
    ),
    # CR-083 (PO 2026-09-07) — the Integrations block records one ACCOUNTING
    # HANDOVER, and a handover is refused over a month that is not closed and
    # over books that do not foot. Both facts are made by the first bill run;
    # without it the block still seeds its three connections and reports the
    # missing handover by name rather than failing.
    "integrations:seed_sample_records": (
        (
            "billing:seed_sample_records",
            "apps/integrations/sample_data.py",
            "The accounting handover needs a CLOSED month with balanced books",
        ),
    ),
    # CR-070 wave M — a rule needs a PUBLISHED template to raise, and the
    # *Meter exchange — residential* template is published by metering's own
    # block. Without it the work block reports a named refusal rather than
    # seeding seven rules that would each show `This month 0` for ever.
    "work:seed_sample_records": (
        (
            "metering:seed_sample_records",
            "apps/work/sample_data.py",
            "which is what publishes it",
        ),
    ),
    "metering:seed_sample_reads": (
        (
            "assets:seed_sample_records",
            "apps/metering/sample_data.py",
            "check the Meters and Premises blocks above.",
        ),
        (
            "metering:seed_sample_records",
            "apps/metering/sample_data.py",
            "check the Meters and Premises blocks above.",
        ),
    ),
    "customers:seed_sample_records": (
        (
            "metering:seed_sample_records",
            "apps/customers/sample_data.py",
            "the premises/units block has to load first",
        ),
        (
            "rating:seed_sample_records",
            "apps/tenancy/sample_data.py",
            "a plan must exist before customers attaches an agreement",
        ),
    ),
    "billing:seed_sample_records": (
        (
            "metering:seed_sample_reads",
            "apps/billing/sample_data.py",
            "The Meter reads block above has to",
        ),
    ),
    "payments:seed_sample_records": (
        (
            "billing:seed_sample_records",
            "apps/payments/sample_data.py",
            "the Bills block above is what issues it",
        ),
        # `DEF-PAY-6321`, 2026-09-23 — the edge that was not there and cost the
        # BATCH column. Counter money is taken into a TILL, a till is at a
        # SERVICE CENTRE, and the centres are seeded by the portal-content
        # block. It ran AFTER this one, so no counter could be opened and every
        # seeded payment banked nowhere. Declared here as well as ordered above,
        # because an operator whose payments block reports a till it could not
        # open must be sent to the block that owes it the centre and not left
        # reading a payments seeder that is working correctly.
        (
            "tenancy:seed_sample_portal_content",
            "apps/payments/sample_data.py",
            "The centres are seeded by",
        ),
    ),
    "customers:seed_sample_payment_plans": (
        (
            "customers:seed_sample_records",
            "apps/customers/sample_data.py",
            "account does not exist. The Accounts",
        ),
        (
            "payments:seed_sample_records",
            "apps/customers/sample_data.py",
            "Payments' block above",
        ),
    ),
    "payments:seed_sample_plan_payments": (
        (
            "customers:seed_sample_records",
            "apps/payments/sample_data.py",
            "plan account does not exist. The Accounts block above has to load first.",
        ),
        (
            "customers:seed_sample_payment_plans",
            "apps/payments/sample_data.py",
            "The 'Payment plan' block above (customers' seed_sample_payment_plans)",
        ),
    ),
    # ── CR-040 task E17 (2026-08-27) — the three blocks waves C and D added ──
    # Every quote below was ALREADY IN THE CODE on the day those blocks landed:
    # each is the sentence the block prints at a person when it refuses. Nothing
    # here is a new claim about the product; what was missing was the machine
    # -readable half of a statement the seeders had already made in English.
    "payments:seed_sample_refund": (
        (
            "customers:seed_sample_records",
            "apps/payments/sample_data.py",
            "overpays does not exist. The Accounts block above has to load first.",
        ),
        (
            "payments:seed_sample_records",
            "apps/payments/sample_data.py",
            "The Payments block above is what records it",
        ),
    ),
    # ── CR-059 CS-12 / task 74 (2026-09-03) ────────────────────────────────
    # Both quotes are ALREADY the sentences the block prints at a person when it
    # refuses — nothing here is a new claim about the product, which is the rule
    # the twelve rows above were written under.
    "payments:seed_sample_multi_account_tender": (
        (
            "customers:seed_sample_records",
            "apps/payments/sample_data.py",
            "three accounts are not seeded, so there is nobody holding three properties",
        ),
        (
            "payments:seed_sample_records",
            "apps/payments/sample_data.py",
            "one of the landlord's three properties owes nothing",
        ),
    ),
    "billing:seed_sample_correction": (
        (
            "customers:seed_sample_records",
            "apps/billing/sample_data.py",
            "June bill was over-read does not exist. The Accounts block above has to load first.",
        ),
        (
            "billing:seed_sample_records",
            "apps/billing/sample_data.py",
            "The first Bills block above is what issues it",
        ),
    ),
    # ⚠ **THE SECOND CYCLE DEPENDS ON THE READS AND NOT ON THE FIRST CYCLE, AND
    # THE MISSING EDGE IS THE CONSIDERED ONE.** Both billing blocks call the
    # same `_preconditions`, so a tenant with no cycle or an unmapped tax
    # authority fails BOTH — but that is a COMMON CAUSE, not a dependency. July
    # bills from July's own reads and needs no June invoice, so an edge from
    # cycle two to cycle one would tell an operator that fixing the first run
    # fixes the second, when what fixes both is the setup fact underneath them.
    # Two roots and one fix is the honest report, and `_root_for`'s own
    # docstring already chooses that direction.
    # ⚠ **RE-POINTED 2026-09-01 (`DEF-2968`): CYCLE TWO'S READS ARE CYCLE TWO'S
    # OWN BLOCK NOW.** This edge named `metering:seed_sample_reads`, which was
    # true while that block walked every period in one pass. It walks the first
    # billed period only, so an edge still pointing at it would send an operator
    # whose SECOND run failed to the block that prepared the FIRST — which is
    # precisely the "five reds, one cause, and the wrong one named" failure this
    # graph exists to prevent (DEF-660).
    "billing:seed_sample_second_cycle": (
        (
            "metering:seed_sample_second_cycle_reads",
            "apps/billing/sample_data.py",
            "The Meter reads block above has to",
        ),
    ),
    # ── THE THIRD-CYCLE STEP (PO 2026-09-01) ────────────────────────────────
    # Every quote below is a sentence the block itself prints at a person when
    # it refuses, exactly as CR-040 task E17's three are.
    "metering:seed_sample_second_cycle_reads": (
        (
            "assets:seed_sample_records",
            "apps/metering/sample_data.py",
            "can put a register on, so there are no meters to read.",
        ),
        (
            "metering:seed_sample_records",
            "apps/metering/sample_data.py",
            "can put a register on, so there are no meters to read.",
        ),
    ),
    "metering:seed_sample_next_cycle_reads": (
        (
            "assets:seed_sample_records",
            "apps/metering/sample_data.py",
            "can put a register on, so there are no meters to read.",
        ),
        (
            "metering:seed_sample_records",
            "apps/metering/sample_data.py",
            "can put a register on, so there are no meters to read.",
        ),
    ),
    # DEF-CUS-4628 — the seat has to exist before a tenancy can end on it, and
    # the sentence quoted is the one that block prints when it refuses.
    "customers:seed_sample_move_out": (
        (
            "customers:seed_sample_records",
            "apps/customers/sample_data.py",
            "holds no sample account. The UPSTREAM block is 'Accounts, customers & service "
            "agreements'",
        ),
    ),
    "payments:seed_sample_cycle_collections": (
        (
            "billing:seed_sample_second_cycle",
            "apps/payments/sample_data.py",
            "second cycle is what issues them and it runs immediately above this block",
        ),
    ),
}


def _seeded_note(spec: SampleModule) -> str | None:
    """WHAT A BLOCK THAT SUCCEEDED STILL HAS TO SAY — DEF-3224.

    ⛔ **THIS RETURNED NOTHING BECAUSE IT DID NOT EXIST, AND THAT IS THE
    DEFECT.** A block that FAILS has carried a sentence to the Sample data panel
    since CR-039 wave B; a block that SUCCEEDS had `detail=None` hardcoded on
    every path. So a run could build a whole estate, deliberately leave a
    service the utility SELLS out of it, and have no way to say so.

    It was live and it cost a round trip with the Product Owner. They ticked
    Electric, Water and Sewer; the estate takes ONE metered backbone and water
    won it; **electric got no service point, no meter, no read and no line on any
    of the 95 issued bills — not even its `$12.00` monthly base, which is
    `$576.00` a month across 48 units.** 0 of 17 blocks failed. The seeder
    composed a correct sentence naming electric and why, and wrote it to
    `logger.info` — a server log no clerk can open — beside a comment saying *"a
    utility that cannot see gas in its demo will ask why"*, which is CLAUDE.md
    law 1 exactly: a comment claiming a guarantee is not the guarantee.

    ⚠ **IT IS THE GENERAL CASE AND NOT THE ELECTRIC ONE.** Other services are
    still legitimately refused after this is fixed — sewer behind no water is
    the standing example and it is CORRECT rather than a fault — so the note is
    whatever the OWNING module says it is. Tenancy composes nothing: it resolves
    the optional `<seam>_note` seam, and a module that publishes none reports
    exactly what it reported before (`None`).

    Three things this deliberately does NOT do:

      * **it never fails the run.** A seam that raises is logged and treated as
        having no note. Narration that can break seeding is worse than silence;
      * **it never turns a seeded block red.** The outcome is still `seeded`,
        because the block DID what it was asked; the note is what it could not
        say before;
      * **it never puts an internal reference on a screen.** The sentence goes
        through `sample_notes.for_screen`, which is B14 rule 31's line.
    """
    fn = seams.resolve(spec.module, f"{spec.seam}_note")
    if fn is None:
        return None
    try:
        # ⚠ **THE NESTED `atomic()` IS A SAVEPOINT AND IT IS THE ONLY THING THAT
        # MAKES THE `except` BELOW TRUE — CLAUDE.md law 14. DO NOT "SIMPLIFY" IT
        # AWAY.** This runs INSIDE the caller's per-module transaction. The note
        # seam READS the tenant's own tables, so it can raise a DATABASE error —
        # and on PostgreSQL any failed statement aborts the whole transaction:
        # catching it here and carrying on would make `_record`'s write below
        # fail with `InFailedSqlTransaction`, and the block that seeded
        # perfectly well would be reported as FAILED because its NARRATION broke.
        # A savepoint is what lets the outer transaction survive.
        #
        # ⚠ And the test suite runs on in-memory SQLite, which has no
        # aborted-transaction state, so the version without this line passes
        # every test on every machine and fails the first time a note seam meets
        # a real database error in production. That is why the guard is written
        # here rather than left to be discovered.
        with transaction.atomic():
            note = fn()
    except Exception:  # noqa: BLE001 — a note never fails a seeding run
        logger.exception("sample-data note seam failed for %s", spec.key)
        return None
    return sample_notes.for_screen(note if isinstance(note, str) else None)


def _seam_missing_detail(spec: SampleModule) -> str:
    """The S62 line's tail: what is missing, in a form somebody can act on."""
    return (
        f"apps.{spec.module}.services.{spec.seam} is not published, so nothing can "
        f"write this block. It also needs BR-TEN-057's `is_sample` column on "
        f"{', '.join(spec.tables)} — tenancy may not add it (B1 boundary rule, "
        "BR-TEN-013: the tag is written only by the owning module's own service "
        "function on the sample path)"
    )


#: Worst-first. A module reporting two blocks reports the WORST of them, because
#: S62 renders one line per module and "seeded" next to a block that did not run
#: is the DEF-016 sentence in a smaller font.
_OUTCOME_SEVERITY = {OUTCOME_SEEDED: 0, OUTCOME_SKIPPED: 1, OUTCOME_FAILED: 2}


def _block_entry(
    spec: SampleModule,
    outcome: str,
    *,
    count: int,
    reason: str | None,
    detail: str | None,
    error_code: str | None,
) -> dict[str, Any]:
    """One block's own line, for `sample_data_runs.blocks` (CR-039 wave B).

    This is the fact the module row cannot carry: WHICH of a module's blocks
    did what. The module row stays BR-TEN-060's worst-first line; this says
    which of the three it is about.
    """
    return {
        "block": spec.seam,
        "label": spec.label,
        "outcome": outcome,
        "count": int(count),
        "reason_code": reason,
        # The vocabulary code — for counting across tenants. Null when seeded.
        "error_code": error_code,
        # The seeder's own sentence — for the person. NEVER written to
        # `audit_log`: see apps/tenancy/sample_errors.py on why.
        "detail": detail,
        "finished_at": timezone.now().isoformat(),
    }


def _merged_blocks(
    existing: list[Any] | None, entry: dict[str, Any], *, merge: bool
) -> list[dict[str, Any]]:
    """`existing` with `entry` in it — replacing the same block, never doubling.

    `merge=False` is the same REPLAY entry the module row uses: the first block
    of a module in a fresh run RESETS the list, so yesterday's blocks cannot sit
    beside today's and be read as one run. Every later block of the same module
    appends to it.
    """
    if not merge or not isinstance(existing, list):
        return [entry]
    kept = [row for row in existing if isinstance(row, dict) and row.get("block") != entry["block"]]
    kept.append(entry)
    return kept


def _record(
    spec: SampleModule,
    outcome: str,
    *,
    count: int = 0,
    reason: str | None = None,
    detail: str | None = None,
    merge: bool = True,
    error_code: str | None = None,
) -> models.SampleDataRun:
    """Upsert this module's row (BR-TEN-063: idempotent per tenant).

    Keyed on (tenant, module) — the UNIQUE constraint US-TEN-019 §5 specifies —
    so a replay updates rather than accumulating a history nobody reads.

    THE KEY IS THE MODULE AND METERING OWNS TWO BLOCKS (premises/units/service
    points, and reads), so the two have to be reconciled into one row. They are
    merged WORST-FIRST and never last-writer-wins: counts add up, and the
    outcome is the more severe of the two with its own reason. A module whose
    reads block cannot run has not delivered its sample set, and a row saying
    `seeded` because the earlier block happened to work would be the DEF-016
    sentence again — a real gap, reported as a success.

    `merge=False` is the REPLAY entry: a fresh run must not inherit the previous
    run's severity, or a module fixed since yesterday could never report seeded.
    """
    tenant_id = core_tenancy.current_tenant_id()
    entry = _block_entry(
        spec, outcome, count=count, reason=reason, detail=detail, error_code=error_code
    )
    # ⚠ The block entry is built from THIS block's own verdict, BEFORE the
    # worst-first merge below rewrites `outcome`/`reason`/`detail` into the
    # MODULE's. That ordering is the whole point of the column: the merge is
    # what makes the module line honest and is also what used to destroy the
    # answer to "which of the three blocks broke".
    existing = (
        models.SampleDataRun.objects.filter(tenant_id=tenant_id, module=spec.module).first()
        if merge
        else None
    )
    blocks = _merged_blocks(
        getattr(existing, "blocks", None) if existing is not None else None,
        entry,
        merge=merge,
    )
    if existing is not None and _OUTCOME_SEVERITY[existing.outcome] > _OUTCOME_SEVERITY[outcome]:
        outcome, reason, detail = existing.outcome, existing.reason_code, existing.detail
    total = count + (existing.seeded_count if existing is not None else 0)
    row, _ = models.SampleDataRun.objects.update_or_create(
        tenant_id=tenant_id,
        module=spec.module,
        defaults={
            "outcome": outcome,
            "seeded_count": total,
            "reason_code": reason,
            "detail": detail,
            "blocks": blocks,
            "finished_at": timezone.now(),
        },
    )
    return row


class _AttributedActor:
    """The caller's actor, with an id the `users` table actually carries.

    ⚠ WHY THIS EXISTS, measured rather than imagined: several tables the
    seeders write carry a **DEFERRED** foreign key to `users` —
    `unit_plan_assignments.actor_user_id` is the one that bit. A deferred FK is
    not checked at INSERT; it is checked at COMMIT. So an actor whose id names
    no user does not fail where the row is written, inside a savepoint that
    could contain it — it fails at commit, taking the whole transaction and
    everything else in it, and the traceback points at teardown rather than at
    the seeder.

    So the id is checked ONCE, before any block runs, against identity's own
    published read. An id that names nobody is dropped and the load proceeds
    with an UNATTRIBUTED trail, which is the honest half of the trade: an audit
    row that says "we do not know who asked" is worth having; a fixture that
    silently corrupts a foreign key is not, and an invented user id would
    attribute a demo load to a person who never asked for it.
    """

    def __init__(self, actor: Any, user_id: Any) -> None:
        self._actor = actor
        self.id = user_id
        self.pk = user_id

    def __getattr__(self, name: str) -> Any:
        # Role, permissions, everything else stays the caller's — only the id
        # is second-guessed, and only because a deferred FK demands it.
        return getattr(self._actor, name)


def _attributed(actor: Any) -> Any:
    """`actor` with an id `users` carries, or with no id at all."""
    user_id = getattr(actor, "pk", None) or getattr(actor, "id", None)
    if user_id is None:
        return actor
    exists = seams.resolve("identity", "user_exists")
    if exists is None:
        # Identity publishes no such read. The id is kept: dropping it would
        # lose attribution on every deployment for the sake of a check that
        # cannot be made, and the FK is right to complain if it is wrong.
        return actor
    return actor if exists(user_id) else _AttributedActor(actor, None)


def _root_for(
    block_key: str, non_seeded: set[str], _visited: frozenset[str] = frozenset()
) -> str | None:
    """The block that ACTUALLY broke behind `block_key`, or None if it is that block.

    CR-039 wave B task 7. Walks the DECLARED edges only (`BLOCK_DEPENDENCIES`),
    and only into blocks that did NOT seed in the same run, so:

      * a block whose declared upstreams all seeded is a ROOT — whatever went
        wrong is its own, and it is the line an operator should read first;
      * a block with a failing upstream is a CONSEQUENCE, and the answer is the
        upstream's OWN root, recursively — so a five-red cascade names the one
        block at the bottom of it rather than the one immediately above.

    ⚠ A missing edge makes a block look like a ROOT, never like a consequence.
    That direction is chosen deliberately: an unmarked failure is reported as
    something to look at, which is at worst noise, while a wrongly-marked
    CONSEQUENCE would tell an operator to ignore a real, separate fault.

    `_visited` makes it cycle-proof. `BLOCK_DEPENDENCIES` is acyclic today and
    a future edge that closed a loop would otherwise recurse forever inside a
    report screen.
    """
    for upstream, _file, _quote in BLOCK_DEPENDENCIES.get(block_key, ()):
        if upstream not in non_seeded or upstream in _visited:
            continue
        deeper = _root_for(upstream, non_seeded, _visited | {block_key, upstream})
        return deeper or upstream
    return None


def _failure_class(block_key: str, non_seeded: set[str]) -> tuple[str, str | None]:
    """`(root|consequence, the root block key or None)` for one non-seeded block."""
    root = _root_for(block_key, non_seeded)
    return (FAILURE_CONSEQUENCE, root) if root else (FAILURE_ROOT, None)


def _audit_failed_block(
    spec: SampleModule,
    *,
    error_code: str,
    failure_class: str,
    root_block: str | None,
    actor: Any,
    reference: str | None = None,
) -> None:
    """CR-039 wave B task 10 — ONE audit row per FAILED block.

    PO 2026-08-26, verbatim: *"Can we write all failed job detialsin audit log
    of that tenant along wt=ith error code so that we can trace it back
    later?"*. Before this, `audit_log` held exactly ONE row for a whole run
    (`sample.seeded`, carrying `seeded_total`/`succeeded`/`not_loaded`), so the
    permanent trail could say a run went badly and could not say what failed.

    ⚠ **WHAT IS DELIBERATELY NOT IN THE PAYLOAD, AND WHY IT IS THE MOST
    IMPORTANT LINE IN THIS FUNCTION.** The seeder's own sentence is NOT written
    here. `audit_log` is append-only (BR-AUD-002, hard rule 4) — a row put
    there survives an erasure request — and the seeders interpolate live values
    into their sentences: `payments` embeds an `invoice_no` and the raw
    `str(exc)` of whatever refused, `metering` embeds read-validation row
    messages, `customers` embeds an account BALANCE. So the trail carries the
    CODE and the fixed catalogue sentence for that code, which is text from
    `apps/tenancy/sample_errors.py` with no interpolation in it at all. The
    operator's sentence lives in `sample_data_runs`, an ordinary tenant table
    that "Remove sample data" deletes.

    ⚠ **IT MAY NOT BREAK THE RUN.** `write_row` raises when the sink is missing
    or fails, and *"one module must not stop the rest"* (BR-TEN-063) outranks
    an extra trail row here: the run-level `sample.seeded` row is still written
    unconditionally at the end, so rule 7's "the run was audited" holds either
    way. Same posture, and the same shape, as `enqueue_provisioning_plant`'s
    own "…and the sample.seed_incomplete audit row failed too".
    """
    try:
        core_audit.write_row(
            action=AUDIT_BLOCK_FAILED,
            entity_type="tenant",
            entity_id=core_tenancy.current_tenant_id(),
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            after={
                "module": spec.module,
                "block": spec.seam,
                # An English source string from SAMPLE_MODULES — platform copy,
                # never a tenant's or a customer's value.
                "label": spec.label,
                "error_code": error_code,
                "reason_code": REASON_EXCEPTION,
                "failure_class": failure_class,
                "root_block": root_block,
                "meaning": sample_errors.audit_safe_sentence(error_code),
                # The operator sentence lives on the run record
                # (`sample_data_runs.blocks[].detail`) and is deliberately NOT
                # copied into this append-only row, per BR-AUD-002. That
                # reasoning belongs here; the value below is what a person
                # reads on the audit log (DEF-2377).
                "detail_location": (
                    "the full wording is on the setup screen for this utility; "
                    "this entry is kept short on purpose"
                ),
                # CR-067 task A4 — THE JOIN, AND IT IS A VALUE, NOT A KEY.
                # `error_diagnostics` holds the technical account of this same
                # failure under this same reference: the exception type, where
                # in the code, the settings in force, the release. There is no
                # foreign key in either direction on purpose — this row is
                # permanent and that one expires (CR-067 §3), and a foreign key
                # would make one hostage to the other's retention.
                #
                # ⚠ THE REFERENCE OUTLIVES THE DETAIL, AND THAT IS THE DESIGN.
                # Ninety days from now the diagnostic is swept and this row is
                # unchanged: it still says what failed, under which code, in the
                # fixed catalogue sentence above. What it can no longer do is be
                # rebuilt into a test.
                "reference": reference,
            },
        )
    except Exception:  # noqa: BLE001 — BR-TEN-063 outranks an extra trail row
        logger.exception(
            "sample-data: the %s row for block %s failed to write; the block's "
            "outcome is still in sample_data_runs and the run-level "
            "sample.seeded row is still written",
            AUDIT_BLOCK_FAILED,
            spec.key,
        )


#: How much of a failing block's own sentence reaches the panel. Long enough to
#: carry a named cause; short enough that the S8 line stays readable.
FAILURE_DETAIL_CHARS = 600


def _failure_detail(exc: BaseException) -> str:
    """The failing block's REASON, not merely the name of its exception class.

    ⚠ AMENDED 2026-08-16 — DEF-166/DEF-167. This used to record
    `type(exc).__name__`, so a block whose seeder said in one careful sentence
    exactly what was wrong reached the operator as the single word `BizError`.
    BR-TEN-060 asks for *"a sentence an operator can act on"* and the class name
    is not one.

    `core.sample_fixture.BlockCannotRun` is the type a seeder raises when it
    cannot do its job, and its message IS that sentence, so it is rendered
    alone; every other exception keeps its class name in front, because a
    `ValidationError` with no class is unreadable and the class is the clue.
    """
    text = str(exc).strip()
    if isinstance(exc, fixture.BlockCannotRun):
        body = text or "the block reported that it could not run and gave no reason"
    else:
        body = f"{type(exc).__name__}: {text}" if text else type(exc).__name__
    body = " ".join(body.split())
    if len(body) > FAILURE_DETAIL_CHARS:
        body = body[: FAILURE_DETAIL_CHARS - 1].rstrip() + "…"
    return body


def declare_estate_metering(actor: Any) -> tuple[str, ...]:
    """`BR-RAT-081` for the tenant in context: say which of this estate's
    services is priced WITHOUT a register. **`DEF-2414`, PO ruling 2026-09-01.**

    PO verbatim: *"we will ahve to set in seeder as well as in setting the sizes
    also on Units - so it works properly - please evaluate and fix it"*. The
    SETTINGS half has existed since `DEF-2310`: `SettingsServicesTab` writes
    `tenant_services.billing_basis` through `services.update_tenant_service`.
    **The SEEDER half is this function**, and until it existed the shipped demo
    tenant contradicted its own fixture — an estate built to be priced by
    counting carts (`BR-RAT-090`), declared metered.

    ⚠ **IT WRITES `capacity` NOW, NOT `metered=False` — `BR-TEN-1180`, PO ruling
    2026-09-02, closing `DEF-2409`.** The column carries three values and the
    false side of the old boolean meant exactly one of them: *priced from a COUNT
    of the unit's assets*. That is `capacity`, and every service this function
    names is one — trash by the PO's own cart example, and solar, broadband and
    battery by the ruling that classed all three capacity-based.

    ⚠ **AND ON A TENANT PROVISIONED SINCE THAT RULING IT NOW MOVES NOTHING, WHICH
    IS THE POINT AND NOT A REGRESSION.** `_enable_signup_services` names the basis
    from `SERVICE_DEFAULT_UOMS` when the row is created, so the declaration is
    already correct before this runs and the loop below finds no candidates. It
    stays because it is the REPAIR path for every tenant provisioned before
    2026-09-02 whose rows took the model default, and because a function that
    reports *"0 moved"* is how a reader learns provisioning is doing its job.

    ⚠ **IT IS A STEP, NOT A BLOCK, AND THAT IS DELIBERATE.** `SAMPLE_MODULES`
    does not grow for it. A block is a MODULE's seam answering for its own tables
    (`BR-TEN-060`); `tenant_services` is tenancy's own row and tenancy is the
    orchestrator, so a block here would be this module reporting to itself. It
    runs BEFORE the loop because `metering.seed_sample_records` reads the
    declaration the moment it builds a service point, and a declaration written
    afterwards would reach the reads seam a whole run late.

    ⚠ **IT DECLARES ONLY WHAT `core.sample_fixture` NAMES, AND IT NEVER
    DECLARES A SERVICE METERED.** The constant is `UNMETERED_ESTATE_SERVICES`
    and its own comment carries the reasoning, `sewer`'s deliberate absence
    included — sewer is a PERCENTAGE of the water usage charge (`BR-RAT-015`),
    which is `share` and not `capacity`, and routing it through an asset count
    would price a connection that has no assets at `$0.00`. `metered` is
    `BR-TEN-1180`'s safe default — *"the unsafe option is the one you type"* —
    so this only ever moves a row in the direction the fixture states, and a
    tenant that has since said otherwise on Settings keeps its answer: **the
    write is guarded on `billing_basis == "metered"`**, so a replay
    (`BR-TEN-063`) never overwrites a human's later choice, and a row already
    seeded `capacity` is left exactly as it is rather than rewritten to the same
    value with a spurious audit row behind it.

    Returns the service codes it actually moved, for the log line. Audited
    under the SAME action the Settings screen writes
    (`settings.service_metering.updated`, CLAUDE.md rule 7), because it is the
    same fact changing and a trail that spells it two ways cannot be searched.
    """
    codes = tuple(fixture.UNMETERED_ESTATE_SERVICES)
    if not codes:  # pragma: no cover - the constant is non-empty today
        return ()
    tenant_id = core_tenancy.current_tenant_id()
    moved: list[str] = []
    for code in codes:
        row = models.TenantService.objects.filter(
            tenant_id=tenant_id,
            service__code=code,
            billing_basis=models.BILLING_BASIS_METERED,
        ).first()
        if row is None:
            # Either the tenant does not sell it, a human already said so, or —
            # since 2026-09-02 — provisioning already seeded the right basis.
            # All three are correct answers and none of them is an error.
            continue
        row.billing_basis = models.BILLING_BASIS_CAPACITY
        row.save(update_fields=["billing_basis", "updated_at"])
        core_audit.write_row(
            # The SAME action the Settings screen writes, deliberately: it is
            # the same fact changing and a trail that spells it two ways cannot
            # be searched. The payload names the basis rather than a boolean,
            # so a row says *capacity, not share* — the ambiguity DEF-2409 was
            # filed about was in the audit trail too.
            action="settings.service_metering.updated",
            entity_type="tenant_service",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            before={"service": code, "billing_basis": models.BILLING_BASIS_METERED},
            after={"service": code, "billing_basis": models.BILLING_BASIS_CAPACITY},
        )
        moved.append(code)
    if moved:
        logger.info(
            "sample data: declared %s capacity-based (BR-TEN-1180) — the estate "
            "prices %s by a COUNT of the unit's assets (BR-RAT-090), not by a register",
            ", ".join(moved),
            ", ".join(moved),
        )
    return tuple(moved)


def seed_sample_data(
    actor: Any,
    *,
    progress: Any = None,
    job_kind: str | None = None,
    job_id: Any = None,
) -> dict[str, Any]:
    """Run the sample-data job for the tenant in context. Returns the summary.

    `progress` is an OPTIONAL callable `(done, total, label) -> None`, called
    once after each block finishes — seeded, skipped or failed alike. It exists
    for CR-017 (PO 2026-08-19): the signup screen narrates the plant while it
    runs, and it can only do that if something reports each block as it lands.
    Default None, so the S8 action and `manage.py load_sample_data` are
    unchanged. **It is never allowed to break the run**: a progress callback
    that raises is logged and swallowed — a status update that could roll back
    a seeded block would be worse than no status at all.

    BR-TEN-063: each module's block is its OWN transaction, so one unwired
    module cannot roll back the rest; the job is idempotent per tenant; and it
    writes an `audit_log` row (CLAUDE.md rule 7 / BR-TEN-016).

    `job_kind` / `job_id` are OPTIONAL and name the job this run is happening
    inside, so a diagnostic written for a failed block can say which one
    (CR-067 task A3). Both default to None because two of the three callers are
    not jobs at all — the S8 action and `manage.py load_sample_data` run in the
    foreground — and a record that invented a job for them would be wrong.

    Callers, and there are exactly three: the S8 Company-profile action
    (BR-TEN-069), `manage.py load_sample_data`, and — since CR-010 new
    mandate 1 (PO 2026-08-17) — the `PLANT_JOB_KIND` job `provision_tenant`
    enqueues for a NEW tenant after its commit. One function for all three,
    so no two paths can seed a tenant differently.
    """
    if core_tenancy.current_tenant_id() is None:
        # Deny-by-default. The same refusal `_tenant_id()` makes everywhere in
        # this module — a job that walked tenants would set context per tenant
        # (BR-TEN-074's shape), never run globally.
        raise core_audit.AuditWriteError(
            "sample-data run needs tenant context (CLAUDE.md rule 1, BR-TEN-003)"
        )
    actor = _attributed(actor)
    declare_estate_metering(actor)
    results: list[dict[str, Any]] = []
    # Modules already recorded IN THIS RUN. `_record` merges worst-first, and a
    # fresh run must not inherit YESTERDAY's severity — a module fixed since
    # then could otherwise never report seeded again (BR-TEN-063 idempotency
    # means a replay changes no count, not that it freezes an old verdict).
    seen: set[str] = set()
    # CR-039 wave B task 7: what each BLOCK did, as the run goes. Every declared
    # dependency is an EARLIER block (SAMPLE_MODULES is in creation order), so
    # by the time a block fails, the state of everything it needs is already in
    # here — root-versus-consequence is decided on facts, never predicted.
    non_seeded: set[str] = set()
    total_blocks = len(SAMPLE_MODULES)

    def report(done: int, label: str) -> None:
        if progress is None:
            return
        try:
            progress(done, total_blocks, label)
        except Exception:  # noqa: BLE001 — narration never fails the seeding
            logger.exception("sample-data progress callback failed at block %s", done)

    for index, spec in enumerate(SAMPLE_MODULES, start=1):
        fn = seams.resolve(spec.module, spec.seam)
        if fn is None:
            # BR-TEN-060: NAMED, not swallowed. This is every module today.
            non_seeded.add(spec.key)
            failure_class, root_block = _failure_class(spec.key, non_seeded)
            with transaction.atomic():
                _record(
                    spec,
                    OUTCOME_SKIPPED,
                    reason=REASON_SEAM_NOT_WIRED,
                    detail=_seam_missing_detail(spec),
                    merge=spec.module in seen,
                    error_code=sample_errors.CODE_SEAM_MISSING,
                )
            seen.add(spec.module)
            results.append(
                {
                    "module": spec.module,
                    "block": spec.seam,
                    "label": spec.label,
                    "outcome": OUTCOME_SKIPPED,
                    "reason_code": REASON_SEAM_NOT_WIRED,
                    "error_code": sample_errors.CODE_SEAM_MISSING,
                    "failure_class": failure_class,
                    "root_block": root_block,
                    "detail": _seam_missing_detail(spec),
                    "count": 0,
                }
            )
            # ⚠ NO `sample.block_failed` ROW HERE, AND THE OMISSION IS THE
            # RULING READ LITERALLY: the PO asked for *"all failed job
            # detials"*. An unwired seam is not a failed job on THIS tenant —
            # it is a platform gap, identical on every tenant of this build, and
            # a row per tenant per run would bury the tenant-specific failures
            # the request exists to find. The C-15 `sample.seed_incomplete` row
            # already names every short module, skips included.
            report(index, spec.label)
            continue
        try:
            with transaction.atomic():  # BR-TEN-063: atomic PER MODULE
                # The ACTOR travels with the call: every service the seeder
                # drives writes an `audit_log` row naming who asked for it
                # (CLAUDE.md rule 7 / BR-TEN-064 — a human asks for this).
                count = int(fn(actor))
                # DEF-3224 — READ AFTER THE SEEDER RAN, INSIDE ITS TRANSACTION.
                # The note describes the estate this block just built, so a
                # value read before the call would answer for the tenant as it
                # was a moment earlier.
                note = _seeded_note(spec)
                _record(spec, OUTCOME_SEEDED, count=count, detail=note, merge=spec.module in seen)
            seen.add(spec.module)
        except Exception as exc:  # noqa: BLE001 — one module must not stop the rest
            logger.exception("sample-data block failed for %s", spec.module)
            detail = _failure_detail(exc)
            error_code = sample_errors.classify(exc)
            non_seeded.add(spec.key)
            failure_class, root_block = _failure_class(spec.key, non_seeded)
            with transaction.atomic():
                _record(
                    spec,
                    OUTCOME_FAILED,
                    reason=REASON_EXCEPTION,
                    detail=detail,
                    merge=spec.module in seen,
                    error_code=error_code,
                )
            seen.add(spec.module)
            # CR-067 task A3 — THE TECHNICAL ACCOUNT, BESIDE THE PERMANENT ONE.
            # This is the failure the Product Owner actually hit on 2026-09-02:
            # seven steps green, step 8 stopped on an unset DOCUMENT_STORAGE_BUCKET,
            # and the only readable record afterwards was a sentence on a screen.
            #
            # It is FIRST because the reference must exist before the audit row
            # that quotes it. `capture()` never raises and always returns the
            # reference, so a store that is unavailable costs the detail and
            # never the trail — the row below still reads correctly with a
            # reference that leads to "no longer held".
            #
            # ⚠ NOTHING FROM `exc` GOES IN BY VALUE. `capture()` takes the
            # exception OBJECT and reads its TYPE, its module, its cause chain
            # and its frames; `str(exc)` is not read anywhere in
            # `core.diagnostics`. The seeder's own sentence stays in
            # `sample_data_runs`, an ordinary tenant table that "Remove sample
            # data" deletes.
            reference = core_diagnostics.capture(
                error_code=error_code,
                exception=exc,
                component=spec.key,
                job_kind=job_kind,
                job_id=job_id,
                step=index,
                step_total=total_blocks,
                audit_action=AUDIT_BLOCK_FAILED,
            )
            # CR-039 wave B task 10 — the permanent, per-block trail. Outside
            # the atomic above on purpose: the outcome is recorded whether or
            # not the trail row lands, and `_audit_failed_block` swallows its
            # own failure so one module still cannot stop the rest.
            _audit_failed_block(
                spec,
                error_code=error_code,
                failure_class=failure_class,
                root_block=root_block,
                actor=actor,
                reference=reference,
            )
            results.append(
                {
                    "module": spec.module,
                    "block": spec.seam,
                    "label": spec.label,
                    "outcome": OUTCOME_FAILED,
                    "reason_code": REASON_EXCEPTION,
                    "error_code": error_code,
                    "failure_class": failure_class,
                    "root_block": root_block,
                    "detail": detail,
                    # ⚠ THE REFERENCE IS DELIBERATELY NOT HERE, AND THE NEXT
                    # LANE NEEDS TO KNOW WHY. It is on the permanent audit row
                    # (CR-067 task A4) and on the diagnostic. Putting it in this
                    # dict alone would be dead data — `run_summary` reads named
                    # keys and this list never leaves the process. Getting it
                    # onto the SETUP SCREEN means carrying it in the stored
                    # `sample_data_runs.blocks[]` entry, which changes that
                    # column's shape and the reads over it; that is CR-067 task
                    # B1's surface and is REPORTED rather than half-done here.
                    "count": 0,
                }
            )
            report(index, spec.label)
            continue
        results.append(
            {
                "module": spec.module,
                "block": spec.seam,
                "label": spec.label,
                "outcome": OUTCOME_SEEDED,
                "reason_code": None,
                "error_code": None,
                "failure_class": None,
                "root_block": None,
                # DEF-3224 — a SEEDED block can carry a sentence too. This was
                # `None`, unconditionally, and that is how a whole service could
                # be left out of the estate with every surface reporting success.
                "detail": note,
                "count": count,
            }
        )
        report(index, spec.label)
    summary = run_summary(results)
    # BR-TEN-016 / BR-TEN-063: `sample.seeded` with counts, every run. Written
    # even when the counts are all zero — "we ran and seeded nothing" is the
    # fact an operator needs, and it is the one a silent job never records.
    core_audit.write_row(
        action=AUDIT_RUN,
        entity_type="tenant",
        entity_id=core_tenancy.current_tenant_id(),
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "seeded_total": summary["seeded_total"],
            "succeeded": summary["succeeded"],
            "not_loaded": summary["not_loaded"],
        },
    )
    return summary


def run_summary(results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The S62 payload (BR-TEN-060), from `results` or from the stored ledger.

    `succeeded` is False whenever ANY module is not `seeded` — BR-TEN-056 clause
    3's "a run with any skip does not report success", as one boolean rather
    than as a paragraph somebody has to read.

    `counts_toward_progress` is False and stays False: BR-TEN-060 makes these
    lines ADVISORY. BR-TEN-015's completion predicate is "the underlying fields
    are filled", and no operator action can wire a seam — counting an unwired
    module against a checklist an operator is being asked to complete would ask
    them for something they cannot do.

    CR-039 wave B adds `blocks` beside `modules` and changes NOTHING about
    `modules`, `not_loaded`, `seeded_total` or `succeeded`. The module lines are
    BR-TEN-060's rule and three callers already read them; the block lines are
    the finer answer the Product Owner asked for. Two views of one ledger, and
    the one that is a signed rule is the one that did not move.
    """
    block_rows: list[dict[str, Any]] | None = None
    if results is None:
        # Read from the ledger: module lines from the row, block lines from the
        # `blocks` column behind it.
        block_rows = stored_blocks()
        results = [
            {
                "module": row.module,
                "label": next(
                    (s.label for s in SAMPLE_MODULES if s.module == row.module), row.module
                ),
                "outcome": row.outcome,
                "reason_code": row.reason_code,
                "detail": row.detail,
                "count": row.seeded_count,
            }
            for row in models.SampleDataRun.objects.filter(
                tenant_id=core_tenancy.current_tenant_id()
            ).order_by("module")
        ]
    not_loaded = [
        {
            "module": row["module"],
            "label": row["label"],
            "reason_code": row["reason_code"],
            "detail": row["detail"],
        }
        for row in results
        if row["outcome"] != OUTCOME_SEEDED
    ]
    return {
        "modules": results,
        # CR-039 wave B: the same run, one line per BLOCK rather than per
        # module, each marked ROOT or CONSEQUENCE. `modules` is untouched —
        # BR-TEN-060's line and every existing reader of it keep working.
        "blocks": block_rows if block_rows is not None else _blocks_from(results),
        "seeded_total": sum(int(row["count"]) for row in results),
        "not_loaded": not_loaded,
        "succeeded": bool(results) and not not_loaded,
        "counts_toward_progress": False,
    }


#: The blocks a module owns, in SAMPLE_MODULES order — used to sort the stored
#: breakdown back into the order it was planted in, which is the order that
#: makes a cascade readable top to bottom.
_BLOCK_ORDER: dict[str, int] = {spec.key: index for index, spec in enumerate(SAMPLE_MODULES)}


def _spec_for(module: str, block: str) -> SampleModule | None:
    return next(
        (spec for spec in SAMPLE_MODULES if spec.module == module and spec.seam == block), None
    )


def _blocks_from(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Block lines out of live per-block `results` — already one entry per block."""
    return [
        {
            "module": row["module"],
            "block": row.get("block") or "",
            "label": row["label"],
            "outcome": row["outcome"],
            "count": int(row["count"]),
            "reason_code": row.get("reason_code"),
            "error_code": row.get("error_code"),
            "failure_class": row.get("failure_class"),
            "root_block": row.get("root_block"),
            "root_label": _root_label(row.get("root_block")),
            "detail": row.get("detail"),
            "finished_at": row.get("finished_at"),
            "retryable": row["outcome"] != OUTCOME_SEEDED,
        }
        for row in results
    ]


def _root_label(root_block: str | None) -> str | None:
    """The English label of the block a cascade actually started at.

    Sent beside `root_block` so the screen can say *"waiting on Meter reads"*
    without holding a second copy of the catalogue — and so a block key that no
    longer exists renders as itself rather than as nothing.
    """
    if not root_block:
        return None
    module, _, seam = root_block.partition(":")
    spec = _spec_for(module, seam)
    return spec.label if spec is not None else root_block


def stored_blocks() -> list[dict[str, Any]]:
    """The per-block breakdown for the tenant in context, from the LEDGER.

    CR-039 wave B task 6. `run_summary()` reads module rows (BR-TEN-060's
    line); this reads the `blocks` column behind them, puts the blocks back in
    planting order, and marks each non-seeded one ROOT or CONSEQUENCE from the
    state the whole run finished in — which is what makes the screen say *"five
    reds, one cause"* after a page reload rather than only in the response to
    the run itself.

    A module row written before the column existed carries `[]` and contributes
    NO block lines. The screen must therefore not read an empty list as "this
    tenant has no blocks": `run_summary()['modules']` is non-empty in exactly
    that case, and the panel says so (`blocks_recorded`).
    """
    rows = models.SampleDataRun.objects.filter(tenant_id=core_tenancy.current_tenant_id()).order_by(
        "module"
    )
    flat: list[dict[str, Any]] = []
    for row in rows:
        for entry in row.blocks or ():
            if not isinstance(entry, dict):
                continue
            flat.append({**entry, "module": row.module})
    flat.sort(key=lambda entry: _BLOCK_ORDER.get(f"{entry['module']}:{entry.get('block')}", 999))
    non_seeded = {
        f"{entry['module']}:{entry.get('block')}"
        for entry in flat
        if entry.get("outcome") != OUTCOME_SEEDED
    }
    out: list[dict[str, Any]] = []
    for entry in flat:
        key = f"{entry['module']}:{entry.get('block')}"
        failure_class: str | None = None
        root_block: str | None = None
        if key in non_seeded:
            failure_class, root_block = _failure_class(key, non_seeded)
        spec = _spec_for(entry["module"], entry.get("block") or "")
        out.append(
            {
                "module": entry["module"],
                "block": entry.get("block") or "",
                "label": entry.get("label") or (spec.label if spec else entry["module"]),
                "outcome": entry.get("outcome"),
                "count": int(entry.get("count") or 0),
                "reason_code": entry.get("reason_code"),
                "error_code": entry.get("error_code"),
                "failure_class": failure_class,
                "root_block": root_block,
                "root_label": _root_label(root_block),
                "detail": entry.get("detail"),
                "finished_at": entry.get("finished_at"),
                # A block whose seeder is not published cannot be retried into
                # existence, but the retry still RE-CHECKS the seam — which is
                # exactly what an operator wants after a deploy.
                "retryable": spec is not None and entry.get("outcome") != OUTCOME_SEEDED,
            }
        )
    return out


#: ⚠ SERVED, NEVER STORED — CR-064 task A4 (PO 2026-09-02).
#:
#: The three outcomes above are what a run WRITES. This fourth one is what a
#: reader is told about a step the run has not reached yet, and it exists
#: because the alternative is the defect CR-064's own sizing section names:
#: *"a step list that reports Done because a row is missing would be worse than
#: the three lines it replaces"*. `sample_data_runs.blocks[]` holds a row per
#: block that HAS run; the catalogue holds all twenty-eight; the difference is
#: real information and this is its name.
#:
#: It is deliberately NOT in `_OUTCOME_SEVERITY`. That map ranks the verdicts a
#: module's row merges worst-first, and "we have not got there yet" is not a
#: verdict — ranking it would let an unreached block out-rank a real failure or
#: be silently treated as a success, which is the same error in both directions.
OUTCOME_NOT_STARTED = "not_started"


def step_catalogue() -> list[dict[str, Any]]:
    """The TWENTY-EIGHT steps, in creation order, BEFORE anything has run.

    CR-064 task A1 (PO 2026-09-02, verbatim): *"can you show all 17 step -
    -list down all 17 steps and show 1 by 1 when they finish"*. The first half
    of that sentence is this function: the list is a TUPLE in source order, so
    it can be answered with nothing seeded, nothing running and no tenant that
    has ever asked for a sample set.

    `position` is 1-based and is what the screen numbers the rows with. It is
    the INDEX IN THIS TUPLE and not a database id — B14 rule 31 (*"no database
    id is ever the visible value of a field"*) is why the row identity a client
    keys on is `key` (`module:seam`, a stable name) and why nothing here serves
    a primary key at all.

    `label` is the ENGLISH source string from `SAMPLE_MODULES`. A screen renders
    the user's language from its own catalogue keyed on `key`; this travels as
    the fallback for a key the frontend does not know yet, which is the one
    thing that keeps a TWENTIETH step visible on screen instead of silently
    absent (CLAUDE.md's hard-won law 2, and the shape the eleventh service
    failed in for ten days).
    """
    return [
        {
            "position": index,
            "key": spec.key,
            "module": spec.module,
            "block": spec.seam,
            "label": spec.label,
            "tables": list(spec.tables),
        }
        for index, spec in enumerate(SAMPLE_MODULES, start=1)
    ]


def step_states() -> list[dict[str, Any]]:
    """All twenty-eight steps with WHAT THE LEDGER RECORDED FOR EACH, or nothing.

    CR-064 tasks A3 + A4. This is the read the sign-up screen narrates from
    while the plant is still running, and every fact in it was already being
    written by `_record` — the work is serving it, not inventing it.

    ⚠ **THE LENGTH IS ALWAYS `len(SAMPLE_MODULES)` — TWENTY-EIGHT TODAY — AND
    THAT IS THE POINT.** It is the
    catalogue LEFT-JOINED onto the stored blocks, never the stored blocks
    listed. A run that died at block 6 answers with twelve `not_started` rows
    rather than a list that stops — because a list that stops cannot be told
    apart from a list that finished, which is exactly the class of production
    report this screen was asked for on 2026-09-02: *"the product said a thing
    succeeded and the thing had not happened"*.

    ⚠ **AND AN ABSENT ROW IS `not_started`, NEVER `seeded` AND NEVER
    `failed`.** CR-064's own sizing section calls this out as the one genuine
    risk in the change, which is why the test for it was written before the
    screen was.

    `detail` is the SERVER's own sentence for that block — the one
    `SettingsSampleData` already renders verbatim and untranslated because it
    names the exact seam function and the exact tables. CR-064 task B3 puts the
    same sentence on the same step's own line one surface earlier, which is
    what the Product Owner asked for in the words *"you ahve to provide
    specific error on the screen itself"*.
    """
    recorded = {
        f"{row['module']}:{row['block']}": row for row in stored_blocks() if row.get("block")
    }
    steps: list[dict[str, Any]] = []
    for entry in step_catalogue():
        row = recorded.get(entry["key"])
        if row is None:
            steps.append(
                {
                    **entry,
                    "outcome": OUTCOME_NOT_STARTED,
                    "count": 0,
                    "reason_code": None,
                    "error_code": None,
                    "failure_class": None,
                    "root_block": None,
                    "root_label": None,
                    "detail": None,
                    "finished_at": None,
                }
            )
            continue
        steps.append(
            {
                **entry,
                # ⚠ The catalogue's `label` wins over the stored one on purpose.
                # A block row keeps the label it was written with, so a run from
                # before a label was corrected would put the OLD wording on a
                # live screen — which is the stale-label defect the billing
                # block's own comment records (CR-040 task C9).
                "outcome": row.get("outcome"),
                "count": int(row.get("count") or 0),
                "reason_code": row.get("reason_code"),
                "error_code": row.get("error_code"),
                "failure_class": row.get("failure_class"),
                "root_block": row.get("root_block"),
                "root_label": row.get("root_label"),
                "detail": row.get("detail"),
                "finished_at": row.get("finished_at"),
            }
        )
    return steps


class UnknownSampleBlock(LookupError):
    """No block of the sample set is named `module:block`.

    Raised rather than silently doing nothing: a retry that reports success
    over a block name the catalogue does not hold is the DEF-016 shape (a gap
    reported as a success), and a typo in a URL should say so.
    """


def _rerecord_module(spec: SampleModule, entry: dict[str, Any]) -> models.SampleDataRun:
    """Write one block's fresh verdict and RE-DERIVE the module line from it.

    ⚠ THIS IS THE ONE PLACE A MODULE'S VERDICT MAY IMPROVE WITHOUT A FULL RUN,
    and the restriction on it is what keeps `_record`'s worst-first merge
    meaningful. `_record` never improves a verdict inside a run, correctly: a
    module whose reads block failed has not delivered its sample set, whatever
    its earlier block managed. But a RETRY is the operator saying *"I fixed the
    named cause; run that block again"*, and a module row that could never
    recover from a failure the operator has since fixed would make the retry
    button a lie.

    So the module line is recomputed as worst-first over the module's BLOCKS —
    the same rule, applied to the same facts, one level down — and ONLY when
    the recorded blocks cover every block the module owns. If they do not (a
    row written before `blocks` existed, carrying one merged verdict and no
    breakdown), the old behaviour stands and the verdict cannot improve: there
    is no honest way to tell which of three merged blocks the old failure was,
    and guessing is the exact error CR-039 exists to prevent. A full re-run
    fixes such a row, and the panel says so.
    """
    tenant_id = core_tenancy.current_tenant_id()
    existing = models.SampleDataRun.objects.filter(tenant_id=tenant_id, module=spec.module).first()
    previous = next(
        (
            row
            for row in (getattr(existing, "blocks", None) or ())
            if isinstance(row, dict) and row.get("block") == entry["block"]
        ),
        None,
    )
    blocks = _merged_blocks(getattr(existing, "blocks", None), entry, merge=True)
    owned = {s.seam for s in SAMPLE_MODULES if s.module == spec.module}
    # ⚠ TWO CONDITIONS, AND THE SECOND ONE FAILS CLOSED (hard-won law 3). The
    # module verdict may be re-derived only when every block it owns is
    # recorded AND every recorded outcome is one this module understands. A
    # `.get(outcome, 0)` default would rank an entry nobody can read as SEEDED
    # and let a retry turn a module green on an outcome we cannot interpret —
    # the unsafe option must be the one you type.
    covered = owned <= {row.get("block") for row in blocks} and all(
        row.get("outcome") in _OUTCOME_SEVERITY for row in blocks
    )

    if covered:
        worst = max(blocks, key=lambda row: _OUTCOME_SEVERITY[row["outcome"]])
        outcome = worst["outcome"]
        reason = worst.get("reason_code")
        detail = worst.get("detail")
        total = sum(int(row.get("count") or 0) for row in blocks)
    else:
        outcome, reason, detail = entry["outcome"], entry["reason_code"], entry["detail"]
        if (
            existing is not None
            and _OUTCOME_SEVERITY[existing.outcome] > _OUTCOME_SEVERITY[outcome]
        ):
            outcome, reason, detail = existing.outcome, existing.reason_code, existing.detail
        carried = existing.seeded_count if existing is not None else 0
        total = carried - int((previous or {}).get("count") or 0) + int(entry["count"])

    row, _ = models.SampleDataRun.objects.update_or_create(
        tenant_id=tenant_id,
        module=spec.module,
        defaults={
            "outcome": outcome,
            "seeded_count": max(total, 0),
            "reason_code": reason,
            "detail": detail,
            "blocks": blocks,
            "finished_at": timezone.now(),
        },
    )
    return row


def retry_block(actor: Any, *, module: str, block: str) -> dict[str, Any]:
    """CR-039 wave B task 8 — run ONE block again, and record what it did.

    The gap this closes, stated plainly: the whole plant could be re-run and a
    single failed block could not. On a tenant where ten blocks landed and the
    eleventh failed for a named, fixable reason (*"add a bill template on
    Settings > Bill templates and load the sample data again"*), the only
    control an operator had was the one that re-walks all eleven.

    Everything the full run guarantees is guaranteed here, because it is the
    same machinery:

      * **its own transaction** — `transaction.atomic()` around the seeder
        alone, so a failed retry rolls back its own writes and nothing else;
      * **the same tenant context** — the caller's, refused if absent
        (CLAUDE.md rule 1), never a tenant taken from an argument;
      * **idempotent** — the seeders are insert-what-is-missing (BR-TEN-063),
        so retrying a block that already seeded writes nothing and reports the
        count it wrote THIS time, which for a replay is honestly 0;
      * **a fresh outcome row** — the block's entry is replaced, the module
        line re-derived, and a failure writes its own `sample.block_failed` row
        exactly as a run does.

    Returns the whole report, not just this block, so the caller re-renders the
    cascade: fixing the ROOT block does not by itself clear the CONSEQUENCE
    lines below it, and an operator needs to see which ones are still red.
    """
    if core_tenancy.current_tenant_id() is None:
        raise core_audit.AuditWriteError(
            "sample-data retry needs tenant context (CLAUDE.md rule 1, BR-TEN-003)"
        )
    spec = _spec_for(module, block)
    if spec is None:
        raise UnknownSampleBlock(f"no sample block is named {module}:{block}")

    actor = _attributed(actor)
    fn = seams.resolve(spec.module, spec.seam)
    error_code: str | None = None
    # CR-067 task A3 — kept so the diagnostic below can read the exception's
    # TYPE, its cause chain and its frames. Never its message: `_failure_detail`
    # above is the operator's sentence and stays in `sample_data_runs`, an
    # ordinary tenant table that removal deletes.
    failure_exc: BaseException | None = None
    if fn is None:
        outcome, count = OUTCOME_SKIPPED, 0
        reason: str | None = REASON_SEAM_NOT_WIRED
        detail: str | None = _seam_missing_detail(spec)
        error_code = sample_errors.CODE_SEAM_MISSING
    else:
        try:
            with transaction.atomic():  # BR-TEN-063: this block's own transaction
                count = int(fn(actor))
                # DEF-3224 — the retry reports what the run reports. A block
                # that seeds here and says nothing, while the same block in a
                # full run names the service it left out, would be two answers
                # to one question depending on which button was pressed.
                retry_note = _seeded_note(spec)
            outcome, reason, detail = OUTCOME_SEEDED, None, retry_note
        except Exception as exc:  # noqa: BLE001 — a retry reports, never raises
            logger.exception("sample-data retry failed for %s", spec.key)
            outcome, count = OUTCOME_FAILED, 0
            reason = REASON_EXCEPTION
            detail = _failure_detail(exc)
            error_code = sample_errors.classify(exc)
            failure_exc = exc

    entry = _block_entry(
        spec, outcome, count=count, reason=reason, detail=detail, error_code=error_code
    )
    with transaction.atomic():
        _rerecord_module(spec, entry)

    failure_class: str | None = None
    root_block: str | None = None
    if outcome != OUTCOME_SEEDED:
        non_seeded = {
            f"{row['module']}:{row['block']}"
            for row in stored_blocks()
            if row["outcome"] != OUTCOME_SEEDED
        }
        non_seeded.add(spec.key)
        failure_class, root_block = _failure_class(spec.key, non_seeded)
    if outcome == OUTCOME_FAILED and error_code is not None:
        # CR-067 task A3 — a RETRY that fails is as worth reproducing as a run
        # that fails, and it is the more likely one to be watched by a person.
        # `capture()` is called first so the permanent row can quote its
        # reference, and it never raises (see `core/diagnostics.py`).
        reference = (
            core_diagnostics.capture(
                error_code=error_code,
                exception=failure_exc,
                component=spec.key,
                audit_action=AUDIT_BLOCK_FAILED,
            )
            if failure_exc is not None
            else None
        )
        _audit_failed_block(
            spec,
            error_code=error_code,
            failure_class=failure_class or FAILURE_ROOT,
            root_block=root_block,
            actor=actor,
            reference=reference,
        )
    # The retry itself is an operator action on a live tenant and leaves its own
    # trace whatever the outcome — including the outcome "it worked this time",
    # which is the fact a support conversation actually turns on. Same posture
    # as `remove_sample_data`'s row: an action a human pressed a button for must
    # leave a trace EVEN WHEN IT CHANGED NOTHING.
    core_audit.write_row(
        action=AUDIT_BLOCK_RETRIED,
        entity_type="tenant",
        entity_id=core_tenancy.current_tenant_id(),
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "module": spec.module,
            "block": spec.seam,
            "label": spec.label,
            "outcome": outcome,
            "seeded_count": count,
            "error_code": error_code,
        },
    )
    return {
        "block": {
            "module": spec.module,
            "block": spec.seam,
            "label": spec.label,
            "outcome": outcome,
            "count": count,
            "reason_code": reason,
            "error_code": error_code,
            "failure_class": failure_class,
            "root_block": root_block,
            "root_label": _root_label(root_block),
            "detail": detail,
        },
        **run_summary(),
    }


def removal_plan() -> dict[str, Any]:
    """What "Remove sample data" would delete, and what it cannot reach.

    BR-TEN-066 (CONFIRMED, PO 2026-08-10, OQ-081) rules removal
    partial-and-named: *"remove what is free, report the rest BY NAME"* — one
    transaction per module deletes every sample row nothing real references and
    returns the survivors named ("Unit A — kept, your account A-10001 is
    attached").

    THIS IS A READ. It reports what each module currently HOLDS, per module, and
    which modules could not answer at all. It deletes nothing — `remove_sample_
    data` is the action, and the two are separate functions precisely so a
    confirm dialog can render this one.

    The ORDER is stated in the rule's own words because it is the part that is
    easy to get wrong later: B2 declares no `ON DELETE CASCADE` on ANY of these
    FKs, so the order is not an optimisation — it is the only thing that makes
    the delete possible.
    """
    holdings: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    total = 0
    for spec in _distinct_modules():
        counter = seams.resolve(spec.module, "sample_record_count")
        remover = seams.resolve(spec.module, "remove_sample_records")
        if counter is None or remover is None:
            blocked.append(
                {
                    "module": spec.module,
                    "label": spec.label,
                    "reason_code": REASON_SEAM_NOT_WIRED,
                    "detail": (
                        f"apps.{spec.module}.services.remove_sample_records is not "
                        "published, so nothing here could select this module's rows"
                    ),
                }
            )
            continue
        held = int(counter())
        total += held
        holdings.append({"module": spec.module, "label": spec.label, "holds": held})
    return {
        "order": BR_TEN_061_REMOVAL_ORDER,
        "removable": total,
        "modules": holdings,
        "retained": [],
        "blocked": blocked,
    }


def _distinct_modules() -> tuple[SampleModule, ...]:
    """SAMPLE_MODULES with each module's repeated blocks collapsed to one row.

    Removal is per MODULE, not per block: `remove_sample_records` deletes
    everything that module tagged, reads included. Running it twice for one
    module would double-count the answer and make the panel lie about how much
    it removed.

    ⚠ **THIS DOCSTRING SAID "metering's two blocks" UNTIL 2026-08-27.** It named
    one module because metering was the only one with a second block when it was
    written; the CODE has always deduped by module name and never knew which
    module it was collapsing. **Customers has had four blocks since 2026-08-17
    and billing has two since CR-040 task C8**, so the sentence was describing
    one case of three. It is corrected rather than deleted because the next
    reader needs to know the collapse is general — a lane adding a second block
    to a fifth module needs no change here, and a lane trusting the old sentence
    might have added one.

    Dedupe keeps the FIRST occurrence, and `remove_sample_data` walks the result
    in reverse for BR-TEN-061's dependency order. Billing's first block already
    sits before payments, so the second billing block changes no removal order.
    """
    seen: set[str] = set()
    out: list[SampleModule] = []
    for spec in SAMPLE_MODULES:
        if spec.module in seen:
            continue
        seen.add(spec.module)
        out.append(spec)
    return tuple(out)


def remove_sample_data(actor: Any) -> dict[str, Any]:
    """BR-TEN-069's SECOND S8 action: remove the sample set, and be told what
    stayed.

    Two functions rather than one, and the distinction is the whole feature:

      · `removal_plan()` is a READ. It answers "what would happen", writes
        nothing, and a screen may call it to render a confirm dialog.
      · `remove_sample_data()` is the ACTION a human pressed a button for. It
        must leave a trace EVEN WHEN IT DELETES NOTHING, because "the operator
        asked us to remove the demo data and we removed none of it" is precisely
        the fact that has to survive the conversation (CLAUDE.md rule 7 /
        BR-TEN-016). A silent no-op is how an operator ends up believing the
        sample data is gone.

    **BR-TEN-061's REVERSE ORDER IS WHY THE MODULE LOOP RUNS BACKWARDS.** B2
    declares no `ON DELETE CASCADE` on any of these FKs, so reads must go before
    the meters they were taken on, accounts before the units they occupy, and
    plans last of all. `SAMPLE_MODULES` is in CREATION order; removal walks it
    in reverse, which is the rule expressed as one `reversed()` rather than as a
    second list somebody would have to keep in step.

    **What CANNOT be removed is named, never hidden.** An issued invoice, its
    lines, its payments and its journal entries are append-only (CLAUDE.md hard
    rule 4), so an account that has been billed is RETAINED and says so. That is
    BR-TEN-066 — *"remove what is free, report the rest BY NAME"* — and it is
    the price of BR-TEN-065's 2026-08-16 amendment, stated here rather than
    discovered by a utility.
    """
    if core_tenancy.current_tenant_id() is None:
        raise core_audit.AuditWriteError(
            "sample-data removal needs tenant context (CLAUDE.md rule 1, BR-TEN-003)"
        )
    removed = 0
    retained: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for spec in reversed(_distinct_modules()):  # BR-TEN-061 reverse dependency order
        fn = seams.resolve(spec.module, "remove_sample_records")
        if fn is None:
            blocked.append(
                {
                    "module": spec.module,
                    "label": spec.label,
                    "reason_code": REASON_SEAM_NOT_WIRED,
                    "detail": (
                        f"apps.{spec.module}.services.remove_sample_records is not "
                        "published, so nothing here could select this module's rows"
                    ),
                }
            )
            continue
        try:
            with transaction.atomic():  # BR-TEN-063: atomic PER MODULE
                result = fn()
        except Exception as exc:  # noqa: BLE001 — one module must not stop the rest
            logger.exception("sample-data removal failed for %s", spec.module)
            blocked.append(
                {
                    "module": spec.module,
                    "label": spec.label,
                    "reason_code": REASON_EXCEPTION,
                    "detail": type(exc).__name__,
                }
            )
            continue
        removed += int(result.get("removed") or 0)
        for row in result.get("retained") or []:
            retained.append({**row, "module": spec.module, "label_module": spec.label})
        models.SampleDataRun.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), module=spec.module
        ).delete()

    core_audit.write_row(
        action="sample.removed",
        entity_type="tenant",
        entity_id=core_tenancy.current_tenant_id(),
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "removed": removed,
            "retained": [row.get("label") for row in retained],
            "blocked": [row["module"] for row in blocked],
        },
    )
    return {
        "order": BR_TEN_061_REMOVAL_ORDER,
        "removed": removed,
        "removable": removed,
        "retained": retained,
        "blocked": blocked,
        "requested": True,
    }


# ══════════════════════════════════════════════════════════════════════════
# PLANTING AT PROVISIONING — CR-010 new mandate 1 (PO 2026-08-17)
# ══════════════════════════════════════════════════════════════════════════
# PO verbatim (decision log, 2026-08-17): *"TRANSACTION RECORDS — deliberately
# ZERO at provisioning - this is where youa re wrong; we need this seed data …
# otherwise we cannot rrun the platform, we are offering free trials to
# utilities, they will not able to build all data on their own on day one"*.
#
# This SUPERSEDES BR-TEN-064's on-request-only trigger FOR NEW TENANTS: a new
# tenant is planted automatically; the S8 panel and `load_sample_data` stay
# the operator path for tenants that already exist (hard-won law 4 — a
# provisioning-time change never reaches a tenant that is already there).
# BR-TEN-064's other clauses stand untouched: this runs in production, and it
# mints no tenant, user credential or subscription (identity's block discards
# the temp passwords unread).
#
# THE SHAPE IS BR-TEN-063's OWN, WHICH ALWAYS DESCRIBED THIS: *"the job is
# enqueued by provisioning and runs after that transaction commits; its
# failure NEVER fails provisioning"*. So: ONE BE-07 job, enqueued by
# `provision_tenant` after its atomic block, running THE SAME
# `seed_sample_data` the S8 panel and `load_sample_data` call — never a second
# seeder. Eager deployments (JOBS_EAGER, every dev/demo box) plant inside the
# signup request; broker deployments plant on the worker, and the job RECORD
# is the truth either way. The S111 `load_defaults` toggle governs it
# (BR-TEN-067's narrowing: the toggle governs sample RECORDS — this is
# exactly that), so an unticked signup stays empty on purpose.

PLANT_JOB_KIND = "tenancy.sample_data_plant"

#: One plant per tenant, ever — BE-07 folds a re-enqueue into the active job.
_PLANT_SCOPE_KEY = "sample-data-plant"


class _PlantActor:
    """The provisioning owner, shaped the way the seeded services need.

    Same shape as `load_sample_data`'s actor and for the same reason: every
    service the seeders drive writes an `audit_log` row naming who asked
    (CLAUDE.md rule 7), and the owner is who this plant is performed for.
    The role is what `@require_role` guards read; the owner IS the tenant's
    System Admin (BR-TEN-001).
    """

    def __init__(self, user_id: Any) -> None:
        self.id = user_id
        self.pk = user_id
        self.role = "system_admin"
        self.roles = ("system_admin",)
        self.is_authenticated = True


def enqueue_provisioning_plant(*, owner_user_id: Any) -> dict[str, Any] | None:
    """Called by `provision_tenant` AFTER its transaction — never inside it
    (BR-TEN-063: the plant's failure must not be able to roll back a tenant).

    Returns the job record, or None with a LOUD trail when the job machinery
    itself refuses — C-15 (PO 2026-08-17, ruling 15) makes incompleteness
    SOFT: *"flag on the S62 checklist + alert support, tenant still opens"*.
    """
    from core import jobs

    try:
        return jobs.enqueue(
            PLANT_JOB_KIND,
            scope_key=_PLANT_SCOPE_KEY,
            payload={"actor_user_id": str(owner_user_id) if owner_user_id else None},
        )
    except Exception as exc:  # noqa: BLE001 — C-15: soft, loud, never fatal
        logger.error(
            "CR-010 plant could not even be ENQUEUED for tenant %s (%s: %s) — the "
            "tenant opens empty; load it from Settings > Company profile or "
            "`manage.py load_sample_data`",
            core_tenancy.current_tenant_id(),
            type(exc).__name__,
            exc,
        )
        try:
            core_audit.write_row(
                action="sample.seed_incomplete",
                entity_type="tenant",
                entity_id=core_tenancy.current_tenant_id(),
                actor_user_id=owner_user_id,
                after={"stage": "enqueue", "error": f"{type(exc).__name__}: {exc}"},
            )
        except Exception:  # noqa: BLE001 — the refusal above must still stand
            logger.exception("…and the sample.seed_incomplete audit row failed too")
        return None


def run_provisioning_plant(record: dict[str, Any]) -> str | None:
    """THE BE-07 JOB BODY (registered in apps.py). Tenant context is already
    entered by `run_job` from the record's own tenant_id (B3).

    ⚠ CR-017 (PO 2026-08-19): it reports PROGRESS as it goes, block by block,
    so `GET /api/jobs/{id}` answers *"3 of 10 — Meters"* rather than only
    "running". That is what the signup screen narrates, and NFR-4 has asked
    every heavy job for it since BE-07 was written; this is the first job kind
    that actually reports it.

    The `checkpoint` carries the LABEL of the block just finished. The record
    contract already has that field (it is TD-17's resume marker) and the poll
    endpoint does not serve it, so the label travels for the log and for a
    future resume; the screen reads `progress.done` / `progress.total` and
    names the blocks from its own catalogue, because the labels here are
    English source strings and a screen must render the user's language.
    """
    actor = _attributed(_PlantActor(record["payload"].get("actor_user_id")))

    def report(done: int, total: int, label: str) -> None:
        jobs.record_progress(record["id"], done, total, checkpoint=label)

    summary = seed_sample_data(
        actor, progress=report, job_kind=PLANT_JOB_KIND, job_id=record["id"]
    )
    # The JOB's id is the alert's idempotency key (DEF-3422): a resumed or
    # retried plant finds its own message and writes nothing.
    completeness_check(summary, actor, run_ref=record["id"])
    return None


#: WHAT the C-15 alert says ran, in a clerk's words. One spelling, here, so the
#: bell and a future caller cannot end up with two nouns for one thing. NOT
#: "plant" — that is this file's word for it, not a person's (B14 rule 32).
SAMPLE_ALERT_OPERATION = "Sample data setup"

#: The queue row's `job`, so a dispatch home can group these.
SAMPLE_ALERT_JOB = "tenancy.sample_data"


def completeness_check(summary: dict[str, Any], actor: Any, run_ref: Any = None) -> None:
    """C-15 (PO 2026-08-17, CR-010 ruling 15): the SOFT completeness check.

    PO verbatim: *"B ✅ soft: flag on the S62 checklist + alert support,
    tenant still opens"*. Three things happen when any seeder came up short,
    and none of them stops the tenant:

    1. **The S62 flag** is the run ledger itself: every short block already
       holds a named `sample_data_runs` row (BR-TEN-060), which is exactly
       what S62 renders — nothing extra to store, and nothing that could
       disagree with it.
    2. **The loud trail**: an ERROR log and a `sample.seed_incomplete`
       audit row naming every short block (CLAUDE.md rule 7).
    3. **The support alert**, through notifications' staff-alert seam —
       resolved by name like every cross-module call here (BR-TEN-013).

       ⚠ **THIS PARAGRAPH SAID THE SEAM DID NOT EXIST UNTIL 2026-09-03
       (DEF-3422), AND IT WAS TRUE FOR THE WHOLE OF THAT TIME.** It read:
       *"None is published today … so the audit row records `support_alert:
       not delivered` WITH that reason rather than pretending."* That is
       exactly what it did, on every provisioning run that came up short, and
       the Product Owner's report was the first anybody noticed: *"this says -
       staff notification - but we dont get any notification"*, with the bell
       reading *"You're all caught up."*

       `apps.notifications.services.queue_staff_alert` is published now, so
       the alert reaches the person who started the run PLUS every active
       System Admin (BR-NOT-021, the ruled audience for a failure), as ONE
       message in their notifications (BR-NOT-020), delivered by the ordinary
       dispatch cycle (BR-NOT-005 — nothing is sent inline from here).

       The alert carries WHAT ran and HOW MANY parts did not load, and never
       the parts' own names: those are module keys and reason codes, and the
       setup screen already lists every one of them in a clerk's words
       (BR-TEN-060). B14 rule 32, and DEF-2377's own lesson about what a
       person ends up reading.

       **The minimum C-15 asks — flag + loud log + audit row — is still
       delivered unconditionally**, and the seam is still OPTIONAL: an unwired
       notifications leaves all three of those standing and records that
       nobody was told.
    """
    if summary.get("succeeded"):
        return
    short = [
        f"{row['module']}: {row.get('reason_code') or 'failed'}"
        for row in summary.get("not_loaded", ())
    ]
    logger.error(
        "C-15: the sample set landed SHORT at provisioning for tenant %s — %s. "
        "S62 renders each block by name; re-run from Settings > Company profile "
        "once the named cause is fixed.",
        core_tenancy.current_tenant_id(),
        "; ".join(short) or "no blocks reported",
    )
    alert_note = "nobody was told: this deployment has no way to raise a notification."
    try:
        outcome = seams.queue_staff_alert(
            actor=actor,
            # A clerk's phrase. NOT "plant", not a module name, not a reason
            # code — B14 rule 32, and the alert is read by whoever has to act.
            operation=SAMPLE_ALERT_OPERATION,
            # The RUN's own id, so a retried provisioning job says it once
            # (CLAUDE.md rule 6). The tenant is the fallback for a direct call
            # with no job behind it, which no production path has.
            operation_id=run_ref or core_tenancy.current_tenant_id(),
            total_count=len(summary.get("modules", ()) or ()),
            failed_count=len(summary.get("not_loaded", ()) or ()),
            # BR-TEN-043 — notifications never reads a clock, so the caller
            # names the moment. This is the caller.
            finished_at=timezone.now(),
            job=SAMPLE_ALERT_JOB,
        )
        if outcome is not None:
            alert_note = str(outcome.get("note") or "")
    except Exception as exc:  # noqa: BLE001 — the alert must not mask the flag
        # The seam promises not to raise. This is the belt on top of that
        # promise: C-15's other two limbs — the named lines on the setup screen
        # and the audit row below — must land whatever happened here.
        logger.exception("the sample-shortfall alert could not be raised")
        alert_note = f"nobody was told: {type(exc).__name__}"
    core_audit.write_row(
        action="sample.seed_incomplete",
        entity_type="tenant",
        entity_id=core_tenancy.current_tenant_id(),
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "not_loaded": [row["module"] for row in summary.get("not_loaded", ())],
            "detail": short,
            "seeded_total": summary.get("seeded_total"),
            # WAS `"s62_flag": "the named sample_data_runs rows this run stored
            # (BR-TEN-060)"`, and the Product Owner read that sentence — a rule
            # id AND a table name — on the deployed audit log (DEF-2377). The
            # rule is unchanged: BR-TEN-060 is why the setup screen lists every
            # block by name, and it is cited here where an engineer reads it.
            # ⚠ THE KEY IS READ TOO, NOT JUST THE VALUE. S61 humanises a payload
            # key into the field LABEL, so `owner_is_told` would draw "Owner is
            # told" and `s62_flag` drew "S62 flag" — a screen id (DEF-2377).
            "what_the_owner_sees": "the setup screen names every part that did not load, and why",
            "support_alert": alert_note,
        },
    )


#: BR-TEN-061 verbatim, as data so a later lane implements the RULE and not a
#: remembered version of it. Reverse dependency order; a hard DELETE, never
#: `deleted_at` — a soft-deleted sample row keeps occupying
#: UNIQUE (tenant_id, premises_id, label) and UNIQUE (tenant_id, account_no), so
#: the operator could never reuse "Unit A" or their own `A-10001`.
BR_TEN_061_REMOVAL_ORDER: tuple[str, ...] = (
    "meter_reads",
    "service_agreements",
    "addresses",
    "contacts",
    "customer_accounts",
    "customers",
    "accounts",
    "asset_assignments",
    "assets",  # sub-meters before their parents (self-FK)
    "service_points",
    "units",
    "premises",
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 (EP-TEN-03 — the sample-data orchestrator and its honest report; parts 1-3 of the story are the owning modules' and are NOT built here)
# generated: 2026-08-15 by story-coder (tenancy/identity lane) · AMENDED 2026-08-19 by story-coder (CR-017 lane — `seed_sample_data(progress=…)` reports each block as it lands and `run_provisioning_plant` writes it to the job record through `jobs.record_progress`, so `GET /api/jobs/{id}` answers "3 of 10" rather than only "running"; NFR-4 has asked every heavy job for this since BE-07 and this is the first kind that reports it)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S8 action is EP-TEN-05's surface and OQ-084's placement ruling has no endpoint yet; the service is published for it) E=deferred(no-frontend-half — S62's line and the S8 buttons ride the screens' own lanes) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff check .✔ black✔ · pytest tests/test_us_ten_019_sample_data.py 16 tests: sqlite 15 passed/1 skipped (the isolation TC, via requires_postgres), live PostgreSQL 16 16 passed · full backend suite `pytest tests` 2581 passed / 160 skipped / 1 xfailed, with 1 PRE-EXISTING FAIL (tests/test_be11_openapi.py snapshot) that was PROVED pre-existing on the untouched baseline BEFORE this lane wrote a line (2400 passed / 144 skipped / 1 xfailed + the same openapi failure) · run_gates: 19 PASS / 2 FAIL / 0 SKIP — and BOTH FAILS ARE OTHER LANES' (G6 names apps/ledger/billing_seam.py:41; G7 names 6 files under apps/ledger, apps/notifications and apps/billing with no review-ledger row). Enumerated mechanically, not assumed: no file of this lane appears in either. The baseline when this lane started was 20 PASS / 0 FAIL (G21 arrived from a concurrent lane mid-session) · RED-PROVED, three ways: (1) the report reads the SEAM and not a constant — wiring a fake seed_sample_records + seed_sample_reads on apps.metering.services flips metering's row to `seeded` with count 7+3=10 while the other three stay named (kept as tc5c/tc5e, so it cannot regress into a hardcoded 'all skipped'); (2) the CHECK constraint — a reasonless skip raises IntegrityError (tc5d); (3) the RLS policy — dropping it from db/rls_tenancy_sample_data.sql makes the isolation TC fail under the non-superuser probe role with `AssertionError: sample_data_runs: LEAK — tenant … can read tenant …'s rows`, which is the assertion being genuine rather than vacuous
# exceptions: THIS JOB SEEDS NOTHING TODAY and says so in its own docstring, in the model's, in the migration's and in every run it records — BR-TEN-057's `is_sample` column belongs on six tables owned by apps/metering and apps/assets, which tenancy may not edit (B1, BR-TEN-013) · parts 1-3 of US-TEN-019 (records, tag, removal) are therefore NOT built and carry no OQ-citing stub either: OQ-081/083/084/085 are all CLOSED, so such a stub would fail G8 — the gap is a MISSING SEAM in another module, which is what `sample_data_runs` records and what 10-scripts/gates/seam_known_gaps.txt parks with an `absent=` guard that expires the moment the column arrives · the four seam contracts are declared in apps/tenancy/seams.py, the documented home, so G20 sees them rather than being routed around · BR-TEN-069's S8 buttons and BR-TEN-060's S62 line are frontend surfaces and belong to those screens' lanes; the services they call are published here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
