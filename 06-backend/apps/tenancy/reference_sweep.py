# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-020 (EP-TEN-03 — keeping EXISTING tenants current as seed data
#           evolves: the fixture-version sweep over the built `reference_seed_runs`
#           ledger, its mandatory dry-run, the "which tenants are behind" read and
#           the version-bump guard)   Screens: none (S8 → Reference data is where
#           the new rows APPEAR; A4 records that no UI exposes cross-tenant data
#           and the Bynry admin console is v2, so this has no screen of its own)
# Rules:    BR-TEN-070 (the seed ledger IS the update mechanism) · BR-TEN-071
#           (insert-if-absent; never UPDATE, never DELETE) · BR-TEN-072 (renames
#           forbidden in seed data) · BR-TEN-073 (three categories, three paths) ·
#           BR-TEN-074 (per-tenant context + transaction, failures isolated) ·
#           BR-TEN-075 (audited, no new action name for the seed half) ·
#           BR-TEN-076 (a dry-run must exist and must write nothing) ·
#           BR-TEN-077 (version-bump policy + the content guard) · BR-TEN-078 (no
#           bill-run interlock) · BR-TEN-079 ("which tenants are behind" is a read) ·
#           BR-TEN-003 (tenant resolved server-side) · BR-TEN-010 (idempotent) ·
#           BR-TEN-012 (versioned platform fixtures) · BR-TEN-013 (cross-module
#           writes via the owning module's service functions only) · BR-TEN-016
#           (every write lands an audit row) · BR-TEN-067 (structural catalogues
#           are exempt from the S111 toggle)
# Tests:    06-backend/tests/test_us_ten_020_sweep.py
# Impacts:  apps/tenancy/management/commands/sweep_reference_data.py (its only
#           caller) · 06-backend/docker-entrypoint.sh (OQ-087: automatic
#           post-migrate) · every module that owns a reference list (rating,
#           billing, payments, metering→assets, customers) — through the EXISTING
#           seed seam, never a new one
# ───────────────────────────────────────────────────────
"""US-TEN-020 — the reference-data SWEEP: how a tenant provisioned in August
receives the vocabulary we ship in September.

WHAT THIS MODULE ADDS, AND WHAT IT DELIBERATELY DOES NOT (BR-TEN-070)
--------------------------------------------------------------------
The delivery mechanism already existed and this module invents no second one:

  * `reference_seed_runs` carries UNIQUE (tenant_id, list_code, fixture_version),
    so a version bump makes every list eligible again — a seed-migration ledger
    in the same shape as Django's own.
  * `services._seed_reference_data()` skips any list that already has a row for
    the current version, and each owning module's seeder looks its entry up by
    natural key before every create, so only genuinely NEW rows are inserted.
  * `services.seed_reference_data_for_tenant()` backfills ONE tenant.

What was missing is all this module supplies: **nothing walked all tenants**,
there was **no dry-run**, and there was **no "which tenants are behind" read**.
Every write still goes through `seed_reference_data_for_tenant()`; this file
owns the WALK, the PLAN and the REPORT, and writes no reference row itself.

THE THREE PO RULINGS OF 2026-08-10 THAT THIS FILE IMPLEMENTS
------------------------------------------------------------
The story's frontmatter still says `blocked_by: [OQ-086, OQ-087, OQ-088]` and its
TC-6/TC-13 still ask for `NotImplementedError` stubs citing those questions. **All
three CLOSED on 2026-08-10** (`12-governance/01-open-questions.md`), so those
stubs would be stale — G8 fails a stub citing a closed OQ, and the prime
directive's point is to implement the ruling once it exists:

  OQ-086 → a corrected value reaches a tenant only through an **audited, opt-in
    "apply correction" that NAMES each affected row**; never a silent forced
    UPDATE. So the sweep never corrects (BR-TEN-071) and `divergences()` below
    is the "names each affected row" half — REPORTED on every run, applied by
    nothing. The apply half is NOT built here and its absence is stated in the
    build report rather than hidden: it needs a per-row "has the tenant touched
    this?" signal no table carries, plus an UPDATE path through each owning
    module. See `divergences()` for exactly which fields are even comparable.

  OQ-087 → the sweep runs **automatic post-migrate, across all tenants**. That
    is wiring, not code: `06-backend/docker-entrypoint.sh` runs it after
    `migrate`. It is here in prose so the next reader knows the command is not
    merely available — hard-won law 2, built is not wired.

  OQ-088 → **persist the S111 toggle first, then honour it**, and *"until that
    column exists the sweep delivers STRUCTURAL lists only, never discretionary
    ones — a tenant that asked for no charge codes must not receive them because
    a bump happened."* `tenants.reference_defaults_opted_in` does NOT exist
    today, so `sweep_tenant()` passes `structural_only=True` UNCONDITIONALLY and
    every discretionary list is reported DEFERRED by name. The residue the
    ruling did not settle — what value backfills the column for tenants
    provisioned before it exists — is OQ-216, minted with this lane and cited on
    `DISCRETIONARY_DEFERRAL_OQ` below.

WHY THE VERSION GUARD REFUSES RATHER THAN WARNS (BR-TEN-077)
-------------------------------------------------------------
`fixture_version` is ONE string for the whole file, so a bump re-opens every
list — harmless, because re-processed lists are insert-if-absent and write zero
rows. The dangerous direction is the other one: a fixture edited WITHOUT a bump
reaches nobody and looks like it worked. `assert_fixture_version_matches_content()`
pins the fixture's content digest to its declared version and refuses the run,
naming the rule. Adding a version to `RATIFIED_FIXTURE_DIGESTS` is the reviewable
diff that says "this content was shipped deliberately at this version".

TENANCY (CLAUDE.md rule 1, BR-TEN-074)
--------------------------------------
`tenants` is the platform registry and is RLS-exempt (B2 §3), so enumerating it
is legal. EVERYTHING else — `reference_seed_runs` included, which is RLS FORCE —
happens inside `core.tenancy.tenant_context(tenant.id)`. There is no cross-tenant
queryset anywhere in this file, and the `--report` read is a per-tenant loop for
that reason and not for style.
"""

import hashlib
import json
import logging
import re
from typing import Any

from django.db import transaction

from apps.tenancy import models, seams, selectors, services
from core import audit as core_audit
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.tenancy")

#: BR-TEN-077 grammar, AMENDED by the PO's CR-010 ruling of 2026-08-17 —
#: verbatim: *"it should ve V1.0.0.0 something like this and then increment"*.
#: A literal `V` and four numeric parts, starting at V1.0.0.0. The old grammar
#: (`YYYY.MM[.N]`) is LEGACY: it is refused for the fixture's own declared
#: version, but `version_key` still orders it, because every
#: `reference_seed_runs` row written before this ruling carries it and those
#: rows are the honest record of what each tenant actually received —
#: rewriting history to the new grammar would forge the ledger, not migrate it.
FIXTURE_VERSION_RE = re.compile(r"^V\d+\.\d+\.\d+\.\d+$")

#: The retired YYYY.MM[.N] grammar, kept ONLY so version ordering and the
#: behind-report can read rows seeded before 2026-08-17.
LEGACY_FIXTURE_VERSION_RE = re.compile(r"^\d{4}\.(0[1-9]|1[0-2])(\.\d+)?$")

#: BR-TEN-077's content guard. digest → the version that content was ratified at.
#: The digest covers the LIST PAYLOADS only (see `fixture_content_digest`), so
#: editing the fixture's prose comments does not demand a bump and adding,
#: re-pricing or re-labelling an entry does.
#:
#: TO BUMP: add the new `version` to the fixture, run the sweep (or the guard
#: test) once, and paste the digest it names here with a one-line reason. The
#: manual step is the review — an auto-updating pin guards nothing.
RATIFIED_FIXTURE_DIGESTS: dict[str, str] = {
    # The W0 platform fixture as it stands on 2026-08-15: 6 UoM · 6 charge codes ·
    # 5 reason codes · 7 payment methods · 5 meter types · 5 read methods ·
    # 12 asset types · 5 asset statuses · 5 account statuses · 4 account types ·
    # 2 TX jurisdictions. `premises_types` deliberately carries no entries —
    # metering's own BR-MET-034 SEED_PREMISES_TYPES is the single ratified source.
    "2026.08": "fd5015b4085c315caae39c8fa05d46f6ae79f76caa7477f3317da1260cdbc92e",
    # 2026.08.1 — CR-004 + DEF-185. SIX lists added (areas · meter_size_classes ·
    # occupancy_statuses · device_types · certification_types · import_mappings,
    # the last deliberately empty), and FOUR of them then CORRECTED: the first
    # pass claimed its vocabulary was transcribed verbatim from prototype r10 and
    # it was not — certification_types matched r10 on 1 of 6 codes. These are
    # r10's own codes (HV-AW, BF-TST, TRAF, FA-CPR, TRENCH; DTWN, IND; BATT,
    # COMM, OTHER; E-1P-100, E-1P-200). occupancy_statuses is the exception and
    # is sourced deliberately: r10 carries NO row data for it, so its five codes
    # come from the PO's own SET-04.occupancy screenshot.
    #
    # THE BUMP IS THE POINT, and it was nearly missed. DEF-185 corrected the
    # CONTENT and left `version` at 2026.08, which BR-TEN-077 exists to catch:
    # a corrected vocabulary that no existing tenant will ever receive is not a
    # correction. The guard named the rule and the fix in one message; this entry
    # is the other half of it.
    "2026.08.1": "2f559683eacbd6edc08c97440451e9219ea6682c3abfc7c206f4076ab5b029ba",
    # 2026.08.2 — AND THE RULE CAUGHT ITSELF A SECOND TIME, ONE COMMIT AFTER THE
    # ENTRY ABOVE SAID SO. The DEF-187 fix (`fbdde9c`) corrected three
    # meter-size-class names whose phase symbol was DOUBLE-ESCAPED — they shipped
    # reading `Electric 1\u03c6 100A` on screen instead of `Electric 1φ 100A` —
    # and again left `version` where it was. Three characters, and by BR-TEN-077
    # exactly as consequential as any other content change: every tenant already
    # provisioned would have kept the mojibake for ever, because the sweep only
    # delivers what a NEW version carries.
    #
    # ⚠ AND THE COST WAS NOT ONLY THE UNDELIVERED FIX. The guard does not warn,
    # it REFUSES — so from that commit until 2026-08-17 every seeding path was
    # dead: `seed_demo`, the sweep, and provisioning a new tenant all raised
    # `FixtureVersionError`, and 13 cases in this suite plus 3 in
    # `test_us_ten_002_seeding` went red and STAYED red (DEF-213). A guard that
    # fails closed is right; a guard whose failure nobody reads for a day is the
    # process gap, and it is why those 16 reds were the thing to fix rather than
    # the thing to work around.
    "2026.08.2": "0c203b1636ef70df8aa3848ffa3ffe36058a6fdb15377fc0cf6c07dfd669b00a",
    # V1.0.0.0 — CR-010 item 9 (PO 2026-08-17): the version GRAMMAR moves to
    # `V<a>.<b>.<c>.<d>` and the fixture re-declares itself under it. The
    # CONTENT is byte-identical to 2026.08.2 — same digest, two keys — because
    # this bump changes the version's SPELLING, not a list. Every tenant whose
    # newest seed-run row is a legacy version reads as BEHIND V1.0.0.0 (legacy
    # sorts below every V-version by construction in `version_key`), so the
    # next automatic sweep re-visits each one, inserts nothing (insert-missing
    # over identical content), and writes the V1.0.0.0 seed-run rows — after
    # which the ledger speaks one grammar for everything that happens next.
    "V1.0.0.0": "0c203b1636ef70df8aa3848ffa3ffe36058a6fdb15377fc0cf6c07dfd669b00a",
    # V1.0.0.1 — CR-010 A-section rulings (PO 2026-08-17, decision log same
    # date): charge codes 6 → 25 (*"extend this list to 25 items"* — every
    # unruled dollar was flagged ⚠ on the artifact the PO confirmed from);
    # meter size classes 7 → 9 (G-250 gas, CART-96 cart) AND the "· base $X"
    # figures stripped from all seven existing names (*"you dont need Base
    # charge - we agreed"* — base is priced by plans, and a money figure in a
    # display name was DEF-189's disease); the four area names cleaned of
    # r10's "· N sub-areas" counts, which claimed sub-areas no tenant has.
    # (`pricing: per_case` markers ride the same bump: the four codes the PO
    # ratified WITHOUT a figure — DAMAGE · TAP · IMPACT · BULK-WATER — carry
    # their unpriced-ness explicitly, so "ratified blank" and "nobody priced
    # it" can never read alike again.)
    "V1.0.0.1": "a87e87fd15a288a390f775a2b97f98e24ead46b7e507e25e956d9cbf0ac84ae9",
    # V2.12.0.0 — the PO endorsed tying the seed version to the PRODUCT version
    # the same afternoon (*"I like your idea of version of seeding data =
    # product version; that way it is perfect match"*), so the grammar's four
    # parts now read `V<release>.<change>.<fix>.<seed-serial>`: the first three
    # ARE the product version (07-frontend/package.json, 2.12.0 when this
    # landed), and the fourth counts fixture-only changes between product
    # bumps. Content is byte-identical to V1.0.0.1 — same digest, spelling
    # bump only. "Which seed data does this tenant have" and "which build is
    # it running" are now one question, which was the whole point.
    "V2.12.0.0": "a87e87fd15a288a390f775a2b97f98e24ead46b7e507e25e956d9cbf0ac84ae9",
    # V2.13.0.0 — CR-010 10.2 CONFIRMED (*"yes pls"*) + the tax ruling
    # (*"a and B - default available"*): UoMs 6 → 26 covering all ten services,
    # new entries carrying an EXPLICIT `service` scope the seeder validates
    # against the catalog (stated-over-derived, the charge_type precedent);
    # and tax_jurisdictions gains the `ALL` scaffold — County · City · Special
    # district, NO rates — merged with the tenant's own state's rows by
    # `services.tax_jurisdiction_entries`, so a non-Texas tenant stops seeding
    # zero jurisdictions without a single pre-filled figure.
    "V2.13.0.0": "d05c76c4eeec0934713834d34276cd366e9d1d3684bdd76541fc3e3f6bab4538",
    # V2.13.0.1 — CR-010 schema slices (2026-08-18): a SEED-SERIAL bump with
    # deliberately identical content (same digest, third pair of twin keys).
    # No fixture list changed; what changed is the SET OF LISTS the sweep
    # delivers — `account_subtypes` (BR-CUS-067, 12 rows from customers'
    # SEED_ACCOUNT_SUBTYPES) and `unit_types` (BR-MET-084, 5 rows from
    # metering's SEED_UNIT_TYPES) joined SEED_LIST_OWNERS, both fixture-empty
    # on purpose (the DEF-026 posture). Without a bump the two lists reach
    # only NEW tenants: `_seed_reference_data` skips a list whose seed-run row
    # exists AT THE CURRENT VERSION, and a tenant already at V2.13.0.0 would
    # never be revisited. The serial (not <change>) moves because the product
    # version is assigned centrally and no product digit rode this landing —
    # BR-TEN-077's grammar names the fourth part for exactly this case.
    "V2.13.0.1": "d05c76c4eeec0934713834d34276cd366e9d1d3684bdd76541fc3e3f6bab4538",
    # V2.18.0.0 — the respell the schema lane's own report asked for: its two
    # slices (account sub-types + unit-type rows) took product digit 2.18.0,
    # so the fixture follows, per "seed version = product version" (PO
    # 2026-08-17). Content digest IDENTICAL to V2.13.0.0/V2.13.0.1 — neither
    # new list rides the fixture (sub-types seed from customers' ratified
    # constant, unit types from metering's, both the DEF-026 posture) — and
    # the third key over one digest is exactly how a spelling-only bump reads.
    "V2.18.0.0": "d05c76c4eeec0934713834d34276cd366e9d1d3684bdd76541fc3e3f6bab4538",
    # V2.19.0.0 — THE FIVE RULED TEXAS TAX ROWS, condition included (DEF-254 /
    # DEF-273; PO ruling 2026-08-18, verbatim twice: *"Tax jurisdiction rates (5
    # TX rows) - already answered"* and *"I ahve already answered it; close
    # it"*). The answer is prototype r10's own tax table and this is the first
    # bump whose content carries a MONEY FIGURE that will reach a customer's
    # bill, so read the entry rather than the digest:
    #
    #   · TX State Utility Tax **6.25 %** — commercial + industrial ONLY,
    #     residential EXEMPT, monthly to the Comptroller, GL 2300
    #   · Local · Bexar County **2.00 %** — every class, monthly, GL 2301
    #   · PUC Regulatory Fee **$0.85 FLAT per bill** — electric only,
    #     quarterly to the TX PUC, GL 2302
    #   · City Franchise Fee **1.50 %** — electric + gas, INSIDE CITY LIMITS
    #     only, quarterly, GL 2303
    #   · Water Conservation Surcharge **$0.25 / kgal above 10 kgal** — water
    #     only, annual to the TWDB, GL 2304
    #
    # The TX jurisdiction list grows 2 → 5 (Texas PUC, City and the Texas Water
    # Development Board join Texas State and Local); `City` deliberately shares
    # its name with the `ALL` scaffold's city row, so a Texas tenant gets ONE
    # city authority carrying the franchise fee rather than two rows meaning the
    # same thing. The ALL scaffold stays RATE-LESS — that is the 2026-08-17
    # ruling (*"a and B - default available"*) and this bump does not reverse it.
    #
    # ⚠ THE CITY FRANCHISE FEE SHIPS WITH ITS SCOPE FIELD SET AND ITS VALUE
    # BLANK, and that is deliberate: r10 says *"Inside city limits"* and names
    # no city, so the utility types their own on S13. Until they do the fee
    # reaches NOBODY — under-charging, which is recoverable, rather than
    # charging r10's 61 outside-city accounts, which is a refund.
    "V2.19.0.0": "452e470081d234b552b3102b6b69387ed9d54a4e2218a1772d0a6975327e17c8",
    # V2.48.0.0 — BR-CUS-107 (PO ruling 2026-08-25, closing DEF-701): ONE row
    # added to `account_statuses`, 5 → 6. The sixth is `disconnected` /
    # "Disconnected" / behaviour class **`non_billable`** — the state a CUT
    # account is in, which BR-CUS-055's five could not express: a cut account
    # read `Marked disconnect / billable`, the rung BEFORE the cut, whose own
    # seed comment says *"consuming until cut"* about a customer who has
    # stopped consuming. The other three classes were each ruled out with a
    # stated reason and are not a later lane's to revisit — `billable` bills a
    # service that no longer runs; `billable_base_only` was eliminated by
    # BR-CUS-103 the same day (base stops at the cut, so there is no base to
    # bill); `terminal` is what `Closed` means, and a cut account is not closed:
    # it holds a debt, it can pay, and it comes back. Worked: `A-11488`, cut
    # 2026-08-18 owing **$612.75**, reads `Disconnected / non-billable`.
    #
    # ⚠ THE BUMP IS THE DELIVERY, NOT THE PAPERWORK. `_seed_reference_data`
    # skips a list whose seed-run row already exists AT THE CURRENT VERSION, so
    # a tenant sitting on V2.19.0.0 would never be revisited and the sixth
    # status would reach NEW tenants only — the exact shape of 2026.08.2's
    # undelivered fix. Migration `customers.0025` delivers the same row directly
    # so that a deployment which never runs a sweep is not left five-status.
    #
    # ⛔ AND NOTHING ASSIGNS THE ROW TO AN ACCOUNT YET. It is reference data on
    # arrival: `disconnects.commit_cut` still writes no `accounts` column. Two
    # measured consequences of the CLASS must close first — occupancy (a
    # `non_billable` account stops occupying its unit) and billing (a
    # `non_billable` account is dropped from the run entirely, not merely
    # relieved of its base). Both are named in
    # `apps/customers/services.SEED_ACCOUNT_STATUSES` and in
    # `disconnects.DISCONNECTED_STATUS_ASSIGNED` (renamed 2026-08-31 when the
    # status started being assigned at the cut — PO ruling 2026-08-30, OQ-1170).
    "V2.48.0.0": "742343816cbdc718a39773f3a5064ecfd33cc3adc6ca58042a6a0bee862c3788",
    # V2.48.0.1 — CR-039 wave E task 22 (PO 2026-08-26, verbatim: *"Why you
    # dont have sub areas below - Areas metering 4 North district · Downtown ·
    # East district · Industrial corridor"*). `areas` grows **4 → 7**: NORTH
    # gains `NORTH-NE` "NE" and `NORTH-NW` "NW", EAST gains `EAST-SE` "SE".
    # Downtown and Industrial corridor deliberately gain none.
    #
    # ⚠ **THIS ENTRY IS THE OTHER HALF OF THE ONE FOUR LINES ABOVE IT.**
    # V1.0.0.1's own note records that CR-010 *"cleaned the four area names of
    # r10's '· N sub-areas' counts, which claimed sub-areas no tenant has."*
    # That was right: the counts were words in a NAME asserting rows that did
    # not exist. This bump creates the rows. So the count comes back — as
    # `sub_area_count`, a COUNTED FIELD on the serialized row (`services.
    # AreaLookupHandler.serialize`), never again as text baked into a name.
    #
    # ⚠ **THE SEED HANDLER HAD TO CHANGE FOR THE FIXTURE TO MEAN ANYTHING, AND
    # THAT IS THE FINDING.** `HostedFlatLookupHandler.seed` reads `code` and
    # `name` and discards every other key, so a `parent_code` in this file
    # landed the row TOP-LEVEL with nothing raised anywhere. `areas` is the one
    # hosted list that is not flat (BR-MET-066b), and its second level had a
    # column, two refusals, a Parent picker, a two-select premises tag and a
    # `"South · SE"` path string — all built, all reachable only by a human
    # typing on a settings screen. Hard-won law 2, on a field that had been
    # sitting there since 2026-08-17. `AreaLookupHandler.seed` now overrides it
    # in two passes (parents, then children through the SAME `_resolve_parent`
    # the settings screen uses, so the depth cap is stated once).
    #
    # ⚠ **THE SERIAL MOVES, NOT A PRODUCT DIGIT.** The product version is
    # assigned centrally by the integrator at merge (PO ruling 2026-08-26) and
    # no product digit rode this landing — which is precisely the case
    # BR-TEN-077's fourth part exists for, and V2.13.0.1's entry says so in the
    # same words.
    #
    # NO MIGRATION ACCOMPANIES THIS ONE, and the difference from V2.48.0.0 is
    # worth stating: account_statuses is STRUCTURAL, so a deployment that never
    # sweeps must not be left five-status and `customers.0025` delivers it
    # directly. `areas` is SAMPLE content under BR-TEN-067 — a tenant that
    # declined the defaults has no areas at all — so there is nothing a
    # migration would be repairing. The repair door for an existing tenant is
    # `manage.py seed_demo --tenant <subdomain>`, which re-offers the list and
    # inserts the three missing rows.
    "V2.48.0.1": "8d2813ac311b10d724d3bbb97e41384e414d4f2c1d2a4eb0da7487dc24b1b549",
    # V2.48.0.2 — BR-MET-142 (PO ruling 2026-08-27 closing OQ-392, verbatim:
    # *"(a) Rule each onto one of the five or you can add new categories"*).
    # `read_methods` grows **5 → 8**: `drive_by` "Drive-by", `self_read`
    # "Self-read", `field_visit` "Field visit".
    #
    # ⚠ **THE PO DELEGATED THE CHOICE AND THE BUILD MADE IT.** The three words
    # are the legacy `read_batches.source_detail` values that mapped to NO
    # method at all, so every reading collected under them served
    # `read_method_origin = not_stated`. Adding them as CATEGORIES rather than
    # mapping them onto Manual/Mobile/AMR is the recorded judgment: each states
    # a different fact — `self_read` WHO read the meter, `field_visit` WHY
    # somebody went, `mobile` WHAT DEVICE was used — and mapping would have
    # RE-LABELLED history nobody verified. The reasoning is in
    # `12-governance/02-decision-log.md` and in BR-MET-142 itself.
    #
    # ⚠ **NO COMMITTED READING IS REWRITTEN BY THIS BUMP OR BY ANYTHING ELSE.**
    # CLAUDE.md hard rule 4 makes an issued reading append-only and several of
    # them are BILLED; the legacy translation stays applied ON READ, in
    # `read_import.LEGACY_READ_METHOD_BY_DETAIL`. What the bump delivers is the
    # tenant's own `read_methods` rows, nothing else.
    #
    # ⚠ **THE SERIAL MOVES, NOT A PRODUCT DIGIT** — the product version is
    # assigned centrally by the integrator at merge (PO ruling 2026-08-26),
    # BR-TEN-077's fourth part, same as the two entries above.
    #
    # NO MIGRATION ACCOMPANIES THIS ONE, and the reason is a THIRD one — worth
    # stating because both precedents above give different ones. `areas` needed
    # none because it is SAMPLE content. `account_statuses` needed
    # `customers.0025` because it is STRUCTURAL and a deployment that never
    # sweeps must not be left five-status. `read_methods` is structural TOO —
    # and it is the one structural list that sits behind
    # `apps.assets.services.ensure_reference_catalogs()`, a `get_or_create`
    # safety net called on every asset write AND by
    # `apps.assets.selectors.reference_list_options`, which is the selector the
    # S28 read-upload picker reads its options from. So an existing tenant gets
    # the three rows the first time anyone opens a screen that could use them,
    # sweep or no sweep. A migration would be a second delivery mechanism for a
    # job already done. The repair door is unchanged:
    # `manage.py seed_demo --tenant <subdomain>`.
    "V2.48.0.2": "b0e8985422a6b9ee2c6e9ad3b6f453354022025103fcb530be1f6264a4b16c50",
    # V2.48.0.3 — BR-TEN-170 + BR-TEN-171 (PO ruling 2026-08-27, CR-039 wave E
    # tasks 20–21). **A RENAME AND A GROWTH IN ONE BUMP, and the rename is the
    # part a digest cannot express.** The list `meter_size_classes` becomes
    # `service_size_classes` — PO verbatim, *"it is utility service size
    # class"* — and grows **9 → 40**.
    #
    # ⚠ **WHY THE RENAME WAS THE RULING AND NOT TIDYING.** Four of the five
    # services these bands add have NO METER: storm water is sized by the
    # PROPERTY (impervious area → ERU), broadband by the TIER BOUGHT (Mbps),
    # solar by INVERTER CAPACITY (kW DC), battery by ITS RATING. A list called
    # *meter* size classes would have had to exclude them — leaving four of ten
    # services unable to carry a base charge that varies by size — or carry
    # them while lying about what it was sizing.
    #
    # THE FORTY: water **9** (5/8" · 3/4" · 1" · 1½" · 2" · 3" · 4" · 5" · 6",
    # and the **5" is the PO's OWN addition**, not in the proposal) · electric
    # **6** · gas **4** · trash **7** · storm water **4** · solar **4** ·
    # broadband **3** · thermal chilled water **3** · sewer **NONE by ruling**
    # (priced as a share of the water usage charge, BR-RAT-015, and it reads no
    # register of its own).
    #
    # ⛔ **TWO SERVICES ARE UNSEEDED ON PURPOSE AND ARE NOT A HOLE IN THIS
    # FIXTURE.** Thermal **STEAM** (OQ-560) and **BATTERY** (OQ-561) were put to
    # the PO as a DIMENSION with no boundaries — *"steam by thousand pounds per
    # hour"*, *"by kW and kWh together … the pair is the class"* — so *"rest all
    # are correct in this"* ratified the dimension and not bands nobody was
    # shown. A signature covers only what was shown (PO 2026-08-11), and a band
    # boundary decides which base charge a customer pays.
    # `apps.tenancy.service_size_classes` raises `NotImplementedError` naming
    # each OQ, and its `UNBANDED_SERVICE_DIMENSIONS` register is what keeps
    # "ruled to have none" (sewer, an empty tuple) from ever reading the same as
    # "nobody has said" (these two, a raise).
    #
    # ⚠ **THE FIXTURE ENTRIES ARE A MIRROR HERE, NOT THE SOURCE.**
    # `service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES` is the law — it is the
    # only place that can hold WHICH SERVICE a row belongs to and which services
    # have none for which of the two reasons, three facts a flat `{code, name}`
    # fixture cannot state. `test_cr039_e20_size_class_bands.py` asserts the two
    # are identical, so a row edited in one and not the other goes RED.
    #
    # ⚠ **ONE SEEDED CODE LEAVES: `E-3P` "Electric 3φ".** The ratified electric
    # list names 3φ **200A** and 3φ **400A**, and a bare 3φ with no amperage is
    # neither. Removing it from this file means no NEW tenant receives it.
    # **BR-TEN-071 deletes nothing** — a tenant that already has the row keeps
    # it, deactivatable on S8 and never resurrected by a later sweep, which is
    # BR-TEN-072's "add the new code, deactivate the old" reached by the only
    # mechanism seed data actually has.
    #
    # ⚠ **AND A RENAMED LIST CODE ORPHANS ITS OWN LEDGER ROWS, WHICH IS WHY THE
    # BUMP IS HARMLESS RATHER THAN MERELY UNTESTED.** Every existing
    # `reference_seed_runs` row for this list says `meter_size_classes`. Nothing
    # reads them again: `_seed_reference_data` walks SEED_LIST_OWNERS, which now
    # says `service_size_classes`, finds no row at any version, and offers the
    # whole list insert-missing by natural key — so a tenant already holding
    # W-58 and G-250 receives the thirty-one it lacks and no duplicate of the
    # nine it has. The old rows stay as the honest record of what that tenant
    # received under the old name, exactly as the legacy version grammar is kept
    # above rather than rewritten.
    #
    # THE SERIAL MOVES, NOT A PRODUCT DIGIT — the product version is assigned
    # centrally by the integrator at merge (PO ruling 2026-08-26), BR-TEN-077's
    # fourth part, same as the three entries above.
    #
    # NO MIGRATION ACCOMPANIES THIS ONE. The list is SAMPLE content under
    # BR-TEN-067 (a tenant that declined the defaults has no size classes at
    # all), so there is nothing a migration would repair — the `areas` reasoning
    # of V2.48.0.1, not the `account_statuses` reasoning of V2.48.0.0. The repair
    # door for an existing tenant is `manage.py seed_demo --tenant <subdomain>`.
    # ⚠ DEF-902 is open on exactly that: the sweep does not re-offer this class
    # of list to an existing tenant, so the door is the command, not the bump.
    "V2.48.0.3": "11f497776cd123ebf9186aab83c1417182cd02fbeaf895b786470d452c3df032",
    # V2.48.0.3 — BR-TEN-150 (PO ruling 2026-08-27, verbatim: *"category is
    # okay, no richer text"*). A NEW list, `owner_categories`, with FIVE rows:
    # `owner_occupier` · `landlord` · `property_manager` · `hoa` · `builder`,
    # in the exact order the five were put to the PO.
    #
    # ⚠ **THE QUESTION THE PO WAS ANSWERING WAS NOT "which words".** It was
    # whether a premises owner is a TYPED PARTY RECORD — kind, contact details,
    # linked to the customer they already are — or richer free text. The typed
    # record was ruled; this list is its vocabulary and `premises_owners`
    # (metering 0040) is the record. *"No richer text"* is the other half of the
    # ruling and is why neither the category nor the owner row has a
    # description column.
    #
    # ⚠ **STRUCTURAL, so `structural_only` does NOT defer it.**
    # `premises_owners.category_id` is NOT NULL, so a tenant whose S111 toggle
    # emptied this list could not record a single owner. That is the exact state
    # BR-TEN-067 was written to prevent, and it is why this list sits in
    # `STRUCTURAL_REFERENCE_LISTS` rather than being deferred under OQ-088.
    #
    # ⚠ **TENANT-EXTENSIBLE BY THE HOUSE PATTERN, NOT BY A RULING.** DB-14 /
    # BR-TEN-036 make every tenant-facing vocabulary seeded-and-extensible and
    # nothing was put to the PO about this one — `OQ-502` asks them to close or
    # confirm it. Recorded here because a reviewer will otherwise read the five
    # `is_system` rows as a closed enum.
    #
    # ⚠ **THE SERIAL MOVES, NOT A PRODUCT DIGIT** — the product version is
    # assigned centrally by the integrator at merge (PO ruling 2026-08-26),
    # BR-TEN-077's fourth part, same as the three entries above.
    #
    # A MIGRATION DOES ACCOMPANY THIS ONE — `tenancy 0022` — and it is a FOURTH
    # reason, distinct from all three above. `areas` needed none because it is
    # sample content; `account_statuses` needed `customers.0025` because it is
    # structural and a deployment that never sweeps must not be left
    # five-status; `read_methods` needed none because a `get_or_create` safety
    # net already delivers it. This list is structural AND NEW, so there is no
    # existing tenant holding a stale version of it and no safety net to lean
    # on. The migration builds the TABLE; the rows arrive through the ordinary
    # seed, and the repair door for a tenant provisioned before the bump is the
    # usual `manage.py seed_demo --tenant <subdomain>`.
    #
    # ⚠ **NO PREMISES IS MATCHED TO A CATEGORY BY THIS BUMP.** The twelve
    # existing free-text owner names stay exactly where they are (BR-MET-151):
    # they are real data on a live tenant, and guessing which string is which
    # party is precisely what the ruling forbade.
    # ⚠ **RENUMBERED FROM V2.48.0.3 AT MERGE, AND THE DIGEST IS RECOMPUTED
    # RATHER THAN CARRIED (DEF-892, one identifier family further on).** Two
    # lanes each took "the next free FIXTURE SERIAL" — exactly as three lanes
    # took the next free rule id this morning — and both landed on V2.48.0.3.
    # The size-class lane merged first and keeps it.
    #
    # ⚠ **AND CARRYING EITHER LANE'S DIGEST FORWARD WOULD HAVE BEEN THE REAL
    # DAMAGE.** This digest is taken over the fixture's LIST PAYLOADS, and the
    # merged file contains BOTH lanes' lists — the 40 utility-service size
    # classes and the five owner categories. So it matches NEITHER lane's
    # recorded hash; it is recomputed here over the merged content, which is
    # the only value that can be right. A merge that kept one side's digest
    # would leave BR-TEN-077's guard asserting a hash of a file that no longer
    # exists, and the sweep would refuse every tenant it was built to repair.
    "V2.48.0.4": "03a50cba6a5f8e0f3f6bf7181d6e1fc6af5355476038a0f9a30326f3f19a1a70",
    # V2.48.0.5 — TWO rulings of 2026-09-02 that landed hours apart, delivered
    # together because the fixture mirrors ONE source and that source now holds
    # both. `service_size_classes` 40 -> 60.
    #
    # CR-062 group A (BR-TEN-171 as amended) is the larger half and is a
    # REVERSAL of two ratified lists rather than an addition to them: solar's
    # four inverter bands and storm water's four ERU bands are WITHDRAWN, and 21
    # rows arrive (solar 10 panel types, battery 6 capacities, storm water 5
    # property sizes).
    #
    # CR-063 tasks A4/A5 is the smaller half: FIRE joins as the ELEVENTH service
    # with SEVEN BANDS, appended with nothing renumbered. ⚠ **Those seven are the
    # only rows in this list the Product Owner has never seen** — they are seeded
    # DEFAULTS a tenant edits on Settings, never signed law, and the going-live
    # customer's real list is `OQ-1360`, OPEN.
    #
    # Eight out, twenty-eight in, and NOTHING ELSE MOVES — the diff was read as
    # arithmetic and every surviving code keeps its name, because BR-TEN-072
    # forbids a rename in seed data.
    #
    # THE BUMP IS THE DELIVERY, not the paperwork. `_seed_reference_data` skips
    # a list whose seed-run row already exists AT THE CURRENT VERSION, so
    # without this line the ten solar panel types and six battery capacities
    # would reach NEW tenants only and every utility already provisioned would
    # keep the four inverter bands for ever — and no existing utility could be
    # given a fire size list at all.
    #
    # BR-TEN-071 DELETES NOTHING. A tenant already holding the eight withdrawn
    # codes keeps them and can deactivate them on S8; the withdrawal means no
    # NEW tenant receives them. That is the only mechanism seed data has.
    #
    # NO MIGRATION IS OWED and the delivery shape is unchanged: a row is still
    # a flat `{code, name}` pair. What CR-062 added — the capacity as a number
    # with its unit — is ratified LAW in `apps/tenancy/service_size_classes.py`,
    # never a column on the hosted table, and this fixture mirrors that module
    # (`test_cr039_e20_size_class_bands.py` refuses any drift between the two).
    #
    # THE SERIAL MOVES, NOT A PRODUCT DIGIT — BR-TEN-077's fourth part and the
    # V2.13.0.1 / V2.48.0.1 / V2.48.0.2 precedent: the product version is
    # assigned centrally by the integrator at merge (PO ruling 2026-08-26).
    "V2.48.0.5": "abbb0ebd5859d0aedae71abaeff2a5da40796a738062b54517e91b2809223827",
    # V2.48.0.6 — CR-063 task A3 (PO ruling 2026-09-02). `uoms` 26 -> 27 with
    # `connection` / "Connection", scoped `"service": "fire"`: the unit a fire
    # service is billed in, so a fire line can be priced per connection the way
    # trash is priced per cart.
    #
    # ⚠ **THE CONTENT LANDED IN `fb279703` AND THIS LINE DID NOT — `DEF-3089`,
    # AND IT IS THE THIRD TIME BR-TEN-077 HAS CAUGHT ITSELF.** The guard does not
    # warn, it REFUSES, so between that commit and this one
    # `assert_fixture_version_matches_content()` raised `FixtureVersionError` and
    # **every seeding path on this branch was dead** — `seed_demo`, the sweep and
    # provisioning a new tenant alike. That is exactly `DEF-213`'s outage
    # (2026-08-16 to 2026-08-17, 16 tests red and staying red) arriving a third
    # time; `DEF-185` was the first and `DEF-187` the second.
    #
    # **The digest is recorded here rather than the bump reverted**, because the
    # bump is CORRECT and is the half that matters: without it `connection` would
    # reach NEW tenants only and no fire utility already provisioned could be
    # given the unit it bills in. What was missing is this line, which is the
    # REVIEWABLE half — it is what says the new content shipped deliberately.
    "V2.48.0.6": "da9fa3d795bbc2ee3d0b879e7a565aeef8deb4f6b7346c5f09374b1710543a2f",
    # V2.48.0.7 — CR-065 tasks A1-A3 (PO ruling 2026-09-02). Every one of the
    # 60 `service_size_classes` rows now carries `service_code`, the utility
    # service it belongs to. **THE COUNT DOES NOT MOVE** — same 60 codes, same
    # names, same order; what changes is that each row finally says which
    # service it is, which is why this bump adds no row and removes none.
    #
    # PO verbatim, with a screenshot of the Fire rate schedule offering
    # *Electric CT-metered*: *"This is where we are setting rates for fire  you
    # should show only capacity for fire . in Setting a capacity needs to tags
    # to utility services ."* It SUPERSEDES `BR-TEN-078` for this one list —
    # that rule had named it unscoped, twice — and the supersession is written
    # into the rule, `BR-TEN-170` and the decision log, dated.
    #
    # ⚠ **A FIXTURE ONLY EVER REACHES A NEW TENANT, WHICH IS WHY THIS BUMP IS
    # HALF THE CHANGE.** Every tenant that already exists is filled in by
    # `tenancy/0035`, once, platform-seeded rows only (BR-TEN-012). The sweep
    # cannot do it: `BR-TEN-071` makes seeding insert-if-absent, so it delivers
    # rows a tenant lacks and never rewrites one they hold — which is correct,
    # and is exactly why a column added to existing rows needs a migration.
    "V2.48.0.7": "34c77c38fd03330f2e31084c7338c71ab0339b1e63b184503c7dcc1b446b99cf",
    # V2.48.0.8 — PO ruling 2026-09-03, verbatim: *"remove private hydrants
    # from list"*. `service_size_classes` SHRINKS **60 -> 59**: `HYD` "Private
    # hydrant", seeded a day earlier by CR-063 and priced `$25.0000`, leaves
    # fire's list. **This is the first row a Product Owner has ever taken OFF
    # this fixture** — every previous shrink was a lane withdrawing its own
    # proposal.
    #
    # ⚠ **IT SUPERSEDES A WORKED FIGURE APPROVED THE DAY BEFORE.** CR-063 was
    # signed with *"a warehouse with a 6-inch line and two private hydrants is
    # charged $60.00 for the line plus $25.00 for each hydrant — $110.00 in
    # total"*. **That warehouse now bills `$60.00` — minus $50.00 a month on
    # that customer.** The six line diameters and their prices do NOT move: a
    # 2" line still bills $12.00, and fire still COUNTS rather than SUMS.
    #
    # ⚠ **A SHRINK IS THE ONE SHAPE THIS SWEEP CANNOT DELIVER, AND SAYING SO
    # IS THE POINT OF THIS NOTE.** `BR-TEN-071` makes seeding
    # insert-if-absent: it delivers rows a tenant lacks and never deletes one
    # they hold. So a tenant provisioned at V2.48.0.5..0.7 KEEPS its `HYD` row
    # and can deactivate it on S8 — exactly `E-3P`'s posture, and exactly what
    # hard rule 4 wants, since a bill may already cite it. **The withdrawal
    # means no NEW tenant receives it**, which is all a fixture can mean. No
    # migration accompanies this and none may be written: one that deleted the
    # row would be the DELETE that rule forbids.
    "V2.48.0.8": "410763a567546964c20972db635012e4b240633f2f27a72890b412e2a216bd14",
    # V2.48.0.9 — CR-077, PO ruling 2026-09-07, verbatim: *"Can you have Tax
    # jurisdictions - for all states - atleast 1 - you seed based on customer
    # selection - if they select Iowa you seed in Iowa, but you ahve to ahve a
    # list for all 50 states"*, and on the shape *"yes this is good - you can
    # have 0 filled in"*.
    #
    # `tax_jurisdictions` goes from **2 keys to 53**: `TX`, `ALL` and now every
    # remaining code in `tenancy.selectors.US_STATES` — the fifty states plus DC
    # and Puerto Rico, which is exactly what the sign-up form accepts and
    # nothing more. Each new key carries TWO rows, its revenue authority and its
    # utility commission, both `level: state`. A tenant that names Iowa now
    # holds five jurisdictions (Iowa Department of Revenue · Iowa Utilities
    # Commission · County · City · Special district) where it held three.
    #
    # ⚠ **NOT ONE OF THE 102 NEW ROWS CARRIES A `taxes` BLOCK, AND THAT IS THE
    # CONTENT OF THE CHANGE RATHER THAN A CAVEAT.** `rating.services
    # ._seed_fixture_taxes` mints a `taxes` row only from a stated figure, so an
    # entry with no `taxes` key cannot price anything at all — which is stronger
    # than shipping a blank one. **BLANK IS NOT ZERO (`DEF-127`):** a NULL rate
    # means nobody has answered yet and PLN-03 step 5 can say so; a seeded
    # `0.00` is a real tax position that bills silently at nothing and looks
    # deliberate. The Texas set above keeps its five ruled figures untouched
    # (DEF-254 / DEF-273) — "no rate anywhere" is one careless edit away from
    # "the PO's own 2026-08-18 ruling was deleted", and it was not.
    #
    # ⚠ **THIS IS A GROWTH, SO THE SWEEP CAN DELIVER IT — BUT NOT BY THE SWEEP.**
    # `tax_jurisdictions` is DISCRETIONARY, so `plan_for_tenant` defers it under
    # OQ-216 and `sweep_tenant` runs `structural_only=True`. The path that
    # reaches an existing tenant is the one DEF-444 built: this list is exempt
    # from the seed-run latch (`services.RERUN_REFERENCE_LISTS`), so the S8
    # Regional save and the `--tenant` repair door both deliver a state recorded
    # after sign-up — for all fifty-one new sets, not only for Texas, which is
    # what `tests/test_cr077_fifty_state_tax_jurisdictions.py` asserts by name.
    "V2.48.0.9": "09314c881bb4780f8b2928f60522d2f48cc1ac56ffc1d14cde39cb2de6647393",
    # V2.48.0.10 — PO ruling 2026-09-07, verbatim: *"use only Inventory and
    # Installed"*. `asset_statuses` keeps all five rows and all five CODES; two
    # NAMES change — `Inventory/Spare` → **Inventory** and `Installed/Active` →
    # **Installed**. Needs repair, In repair and Retired are untouched.
    #
    # Nothing branches on these strings by construction: BR-AST-031 gives every
    # stage a `behavior_class` *"so list filters and billing/rating logic stay
    # sound regardless of tenant labels"*, and the seeded rows are matched by
    # CODE everywhere. The slash had also reached a customer's screen — the
    # portal asset list printed `Installed/Active`, a stored value with a slash
    # in it (portal wireframe delta 37.6).
    #
    # ⚠ **A RENAME IS THE ONE SHAPE THE FIXTURE CANNOT DELIVER ON ITS OWN, AND
    # THIS IS THE MIRROR OF V2.48.0.8's NOTE ABOUT A SHRINK.** `BR-TEN-071`
    # makes seeding insert-if-absent BY CODE: a tenant provisioned yesterday
    # already holds `inventory`, so every future run finds it present and writes
    # nothing, and no version bump would ever reach the NAME. So this bump ships
    # with `assets/0011_po_2026_09_07_stage_names`, which renames the live rows
    # — and renames ONLY a row whose name is still byte-identical to the
    # superseded seeded string. A tenant who typed their own label keeps it,
    # which is BR-TEN-012's *"a tenant-touched row is never overwritten"*
    # applied as conservatively as it can be: no touch-tracking column exists to
    # tell a pristine seeded row from an edited one, so the CONTENT is the only
    # evidence available and it is used as the whole test.
    "V2.48.0.10": "d879b1fc8421aaf6490684d7366dac471f09faa763cb9f6db98f0941826f521a",
    # V2.48.0.11 — `CR-080`, PO ruling 2026-09-07, verbatim: *"connected tonnage
    # - it is capacity not metering; i will ahve 100 tonne or 200 tonne etc"*.
    # THERMAL/HEAT stops being a metered service and is billed on connected
    # tonnage, and TWO lists move with it. `uoms` 27 → 28 with `ton` /
    # "Refrigeration ton (connected)", scoped to thermal_heat — the REFRIGERATION
    # ton (12,000 BTU/hr), not the metric tonne. `ton-hr` STAYS: `BR-TEN-071`
    # deletes nothing and a utility that meters chilled-water energy still has
    # the unit to pick. `service_size_classes` 59 → 64: the three `TH-CW-*` rows
    # are WITHDRAWN — each is a RANGE ("<=25 tons", "25-100") and a range has no
    # single value a capacity could be — and eight connected-tonnage capacities
    # `TH-T5` … `TH-T800` take their place, with 25 and 100 deliberately kept
    # because they were the withdrawn ranges' own boundaries.
    "V2.48.0.11": "aa155edfe22d66fa8df8aef296ac04eaea9238e1632b878b636cb696bc5aceec",
    # V2.48.0.12 — PO ruling 2026-09-17, verbatim: *"utility can get their own
    # account types"*, which SUPERSEDES `BR-CUS-094`'s platform posture. ⚠ **THE
    # CONTENT CHANGE IS FOUR MISSING ROWS THAT HAD BEEN MISSING SINCE 2026-08-24
    # AND WERE HARMLESS UNTIL TODAY.** `BR-CUS-094` ratified SEVEN categories and
    # seeded the four new ones through migration `customers.0019` into the
    # PLATFORM table; this fixture went on listing the original four, and it did
    # not matter, because the seam was insert-missing over a global table that
    # already held all eight. `customers.0019`'s own docstring reported the drift
    # and could not fix it from its lane. Now that the rows are per tenant, a
    # tenant provisioned from this fixture would have received FOUR types and no
    # Agricultural, Institutional, Municipal or Builder. So `account_types`
    # 4 -> 8: `BR-CUS-094`'s seven in the ruled order plus `government`, which
    # customers seeds `legacy=True` (unselectable on new records, valid
    # everywhere it already is). Nothing else in the file moves.
    "V2.48.0.12": "b5681a647c3d5abb5a56095dbf322c71a6e3abe925b1e3466224e8850d0d038b",
    # V2.48.0.13 — `payment_methods` gains ONE row, `tap_pay` / "Tap & pay"
    # (CR-139-BRC07 `P5.11`, PO ruling 2026-09-23, verbatim: *"user will
    # manually use it and add reference # and Tap & pay options in system - we
    # are not going to integrate them drectly"*). Nothing else in the file moves
    # — verified by comparing the fixture's list payloads across `955f1d64c`
    # and its parent: one entry added, no entry removed, re-priced or
    # re-labelled. The full reasoning is the fixture's own
    # `_v2_48_0_13_comment`, and the seven tenders are untouched.
    #
    # ⚠ **THE BUMP LANDED WITHOUT THIS LINE ON 2026-09-23 AND THAT BROKE THE
    # SWEEP FOR EVERY TENANT (`DEF-TEN-6786`, 2026-09-25).** `BR-TEN-077` says
    # the bump and its digest land in one commit, and `955f1d64c` carried the
    # version, the row and a 1,200-word justification — and not the digest. The
    # guard did its job and refused `sweep_reference_data` outright, for every
    # tenant, on every run, with `FixtureVersionError`. It surfaced only as a
    # red isolation case nobody had read
    # (`test_us_ten_020_tc8__sweep_is_per_tenant_and_rls_scoped`). This entry
    # completes that commit; it ratifies no content that was not already
    # decided.
    "V2.48.0.13": "7e7fe8f16731343f87500ead1edf9fe6969864c68086ec720b8a193016ccc2f7",
    # V2.48.0.14 — `service_size_classes` gains ONE row, storm water's
    # `SW-FLAT` / "Flat" = 2 ERU (PO ruling 2026-10-03, option A: storm water
    # stays charged per unit, and one flat of a block gets its own size).
    # Nothing else moves. The list is DISCRETIONARY, so the sweep does not
    # deliver it; `tenancy/0058` adds it where a tenant's storm-water list is
    # still the untouched seed. Bump and digest in ONE commit (`DEF-TEN-6786`).
    "V2.48.0.14": "2131ecd46d31f65946bc99e907882cd77bd63ac02c9ef068b974ee7a23b1e1a9",
    # V2.48.0.15 — the seeded `NSF` charge code DECLARES `is_nsf_fee: true`
    # (`DEF-PAY-10698`, PO 2026-10-30: a bounce charges the plan's NSF code,
    # never a hard-coded one). No price or label moves; `rating/0068` marks the
    # row every existing tenant already holds.
    "V2.48.0.15": "6bf0d83d0ea1c90c468249d1e5dce75842697d182cb442ee11b005beeeeba2db",
}

#: OQ-088's residue, minted with this lane: the ruling says persist the S111
#: toggle and honour it, and leaves open what value the column carries for the
#: tenants that already exist. Until the PO rules that, discretionary lists are
#: DEFERRED by name — never delivered on a guess, never silently omitted.
DISCRETIONARY_DEFERRAL_OQ = "OQ-216"

#: The three outcomes a swept tenant can have. `planned` is the dry-run's.
OUTCOME_SWEPT = "swept"
OUTCOME_FAILED = "failed"
OUTCOME_PLANNED = "planned"

#: Per-list plan verbs.
ACTION_SEED = "seed"
ACTION_CURRENT = "current"  # already holds a row at this fixture version
ACTION_DEFERRED = "deferred"  # discretionary, OQ-088 ruling — see above
ACTION_NO_ENTRIES = "no-entries"  # the fixture ships none for this list/state
ACTION_PLATFORM = "platform"  # not a per-tenant list at all — see below

#: ⚠ **EMPTY SINCE 2026-09-17, AND `account_types` IS THE ONLY LIST THAT WAS
#: EVER IN IT.** B2 r5 #12 [D5] made it a PLATFORM table — no `tenant_id`,
#: RLS-excluded, seeded by migration `customers.0003` before any tenant existed
#: — so it was neither swept nor OQ-216-deferred, because the S111 toggle never
#: governed it and a per-tenant sweep was never its delivery path. **The PO
#: reversed that posture (*"utility can get their own account types"*)**: the
#: rows are per tenant, `customers.ensure_account_types()` seeds them and the
#: list is STRUCTURAL, because `accounts.account_type_id` is NOT NULL and a
#: tenant whose toggle emptied this list could not create an account at all —
#: exactly the state `BR-TEN-067` exists to prevent.
#:
#: The set is KEPT rather than deleted: `declared_lists()` reads it, the
#: category it produces is part of `BR-TEN-073`'s vocabulary, and the next list
#: that is genuinely platform-wide belongs here.
PLATFORM_REFERENCE_LISTS: frozenset[str] = frozenset()

#: BR-TEN-079's three states for the "which tenants are behind" read.
STATE_CURRENT = "current"
STATE_BEHIND = "behind"
STATE_NEVER = "never seeded"


class FixtureVersionError(RuntimeError):
    """BR-TEN-077: the fixture's content and its declared version disagree.

    Raised BEFORE any tenant is touched. Refusing is the whole point: a fixture
    edited without a bump reaches nobody and looks like it worked, which is the
    failure this rule exists to end.
    """


# ── the fixture, and its version guard (BR-TEN-077) ─────────────────────────
def fixture_version() -> str:
    """The platform fixture's declared version. Refuses a malformed one."""
    version = str(services._load_seed_fixture()["version"])
    if not FIXTURE_VERSION_RE.match(version):
        raise FixtureVersionError(
            f"fixture version {version!r} does not match BR-TEN-077's grammar "
            "V<a>.<b>.<c>.<d> (e.g. 'V1.0.0.0' — CR-010 item 9, PO 2026-08-17; "
            "the old YYYY.MM[.N] spellings are legacy ledger history, not valid "
            "for the fixture itself)"
        )
    return version


def fixture_content_digest() -> str:
    """SHA-256 over the fixture's LIST PAYLOADS, canonically serialised.

    Keys beginning `_` are prose comments and `version` is the thing being
    pinned, so both are excluded: a lane may explain itself in the fixture
    without triggering a bump, and may not add, re-price or re-label an entry
    without one.
    """
    fixture = services._load_seed_fixture()
    payload = {key: value for key, value in fixture.items() if not key.startswith("_")}
    payload.pop("version", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assert_fixture_version_matches_content() -> str:
    """BR-TEN-077's guard. Returns the version; raises FixtureVersionError.

    Two failure shapes, deliberately worded differently because they need
    different fixes:
      · the version is UNKNOWN to the pin  → somebody bumped and did not record
        the new content; add the digest below with a reason.
      · the version is known but the digest MOVED → somebody edited the content
        and did not bump; bump `version` in the SAME commit (BR-TEN-077).
    """
    version = fixture_version()
    digest = fixture_content_digest()
    ratified = RATIFIED_FIXTURE_DIGESTS.get(version)
    if ratified is None:
        raise FixtureVersionError(
            f"fixture version {version!r} has no ratified content digest. The content "
            f"currently hashes to {digest}. If this bump is deliberate, add\n"
            f'    "{version}": "{digest}",\n'
            "to RATIFIED_FIXTURE_DIGESTS in apps/tenancy/reference_sweep.py with a "
            "one-line reason (BR-TEN-077: the bump and the content land in one commit)."
        )
    if ratified != digest:
        raise FixtureVersionError(
            f"lookup_defaults.json content changed but `version` is still {version!r} "
            f"(expected digest {ratified}, got {digest}). BR-TEN-077: a fixture change "
            "with no version bump is an incomplete change, not a small one — a list "
            "that already ships and gains, re-prices or re-labels an entry reaches NO "
            "existing tenant until the version moves. Bump `version` (YYYY.MM[.N]) and "
            "record the new digest in RATIFIED_FIXTURE_DIGESTS, in the same commit."
        )
    return version


# ── version ordering (BR-TEN-079) ───────────────────────────────────────────
def version_key(version: str) -> tuple[int, ...]:
    """`V1.0.0.0` → (1, 1, 0, 0, 0); `2026.08.2` → (0, 2026, 8, 2, 0).

    The FIRST element is an epoch — 1 for the V-grammar, 0 for legacy — and it
    exists because numeric comparison alone gets the answer BACKWARDS: 1 < 2026,
    so without it every tenant seeded at `2026.08.x` would read as AHEAD of
    V1.0.0.0 and the sweep would never deliver the new grammar to anybody.
    Within each epoch, parts compare as numbers rather than strings, so a
    `2026.9` typo cannot sort after `2026.10` and V1.0.0.9 sorts below
    V1.0.0.10.
    """
    if version.startswith("V"):
        parts = [int(part) for part in version[1:].split(".") if part.isdigit()]
        epoch = 1
    else:
        parts = [int(part) for part in version.split(".") if part.isdigit()]
        epoch = 0
    while len(parts) < 4:
        parts.append(0)
    return (epoch, *parts[:4])


# ── the declared lists, and which category each is in (BR-TEN-073) ──────────
def declared_lists() -> list[dict[str, Any]]:
    """Every list the seeder routes, with its owner and category.

    Category is BR-TEN-073's: `structural` (schema-required vocabulary, exempt
    from the S111 toggle per BR-TEN-067), `discretionary` (tenant-owned reference
    data, gated by OQ-088's ruling until the opt-in column exists), or `platform`
    (`account_types` — see PLATFORM_REFERENCE_LISTS).
    """
    rows = []
    for list_code, owner_module in services.SEED_LIST_OWNERS:
        if list_code in PLATFORM_REFERENCE_LISTS:
            category = "platform"
        elif list_code in services.STRUCTURAL_REFERENCE_LISTS:
            category = "structural"
        else:
            category = "discretionary"
        rows.append({"list": list_code, "owner": owner_module or "tenancy", "category": category})
    return rows


def _fixture_entries(fixture: dict[str, Any], list_code: str, state_code: str | None) -> list:
    if list_code == "tax_jurisdictions":
        # ONE resolver for state rows + the ALL scaffold (CR-010 tax ruling),
        # shared with both provisioning-side sites — a second copy of the
        # merge here would be the next thing to drift.
        return services.tax_jurisdiction_entries(fixture, state_code)
    return list(fixture.get(list_code, []))


def _held_codes(list_code: str) -> set[str] | None:
    """The codes this tenant already holds for a list, lowercased — or None when
    no module has registered a lookup handler for it.

    Read through the OWNING module's registered handler (BR-TEN-029/031), which
    is the only sanctioned cross-module read; this file imports no other
    module's ORM. None is not "empty": `premises_types` has five rows and no
    handler, and reporting it as empty would be false (the `uncounted` state
    `reference_data_report()` had to grow for exactly this reason).
    """
    definition = services.LOOKUP_LISTS.get(list_code)
    handler = definition.handler if definition is not None else None
    if handler is None:
        return None
    codes: set[str] = set()
    for row in handler.search(None):
        payload = handler.serialize(row)
        code = payload.get("code")
        if code:
            codes.add(str(code).strip().lower())
    return codes


def _seed_run_versions() -> dict[str, list[str]]:
    """list_code → every fixture version this tenant has a seed-run row for.

    Under the caller's tenant context; `reference_seed_runs` is RLS FORCE, so
    this is never a cross-tenant SELECT (BR-TEN-074/079).
    """
    versions: dict[str, list[str]] = {}
    rows = models.ReferenceSeedRun.objects.filter(
        tenant_id=core_tenancy.current_tenant_id()
    ).values_list("list_code", "fixture_version")
    for list_code, version in rows:
        versions.setdefault(list_code, []).append(str(version))
    return versions


# ── the plan (BR-TEN-076: what a dry-run prints, and what a real run does) ───
def plan_for_tenant(tenant: models.Tenant) -> dict[str, Any]:
    """The per-list plan for ONE tenant. Read-only; must run inside that
    tenant's context.

    `would_seed` is exact where the owning module has registered a lookup
    handler (fixture codes minus held codes) and None where it has not — the
    honest answer, because the count is then knowable only after the run.
    """
    version = fixture_version()
    fixture = services._load_seed_fixture()
    state_code = selectors.us_state_code(tenant.state) if tenant.state else None
    seeded_versions = _seed_run_versions()

    lists: list[dict[str, Any]] = []
    for row in declared_lists():
        list_code = row["list"]
        entries = _fixture_entries(fixture, list_code, state_code)
        held = _held_codes(list_code)
        at_version = version in seeded_versions.get(list_code, [])
        if row["category"] == "platform":
            action, detail = ACTION_PLATFORM, (
                "PLATFORM table (B2 r5 #12 [D5]: no tenant_id, RLS-excluded), seeded by "
                "migration customers.0003 before any tenant exists — a per-tenant sweep "
                "is not its delivery path"
            )
        elif row["category"] == "discretionary":
            # OQ-088 (PO 2026-08-10): STRUCTURAL ONLY until the opt-in column
            # exists. Named, never silently dropped — a tenant reading this
            # report must be able to see what it did not get and why.
            action, detail = ACTION_DEFERRED, (
                "the S111 opt-in is not persisted (`tenants.reference_defaults_opted_in` "
                f"does not exist), so 'declined' and 'did not exist yet' are the same "
                f"absence — {DISCRETIONARY_DEFERRAL_OQ}"
            )
        elif at_version:
            action, detail = ACTION_CURRENT, f"already holds a seed-run row at {version}"
        elif not entries and held is not None and list_code != "premises_types":
            action, detail = ACTION_NO_ENTRIES, "the fixture ships no entries for this list"
        else:
            action, detail = ACTION_SEED, "eligible: no seed-run row at this version"
        would_seed: int | None
        if action != ACTION_SEED:
            would_seed = 0
        elif held is None:
            would_seed = None  # no handler — knowable only after the run
        else:
            would_seed = len({str(e.get("code", "")).strip().lower() for e in entries} - held)
        lists.append(
            {
                **row,
                "entries_in_fixture": len(entries),
                "held": None if held is None else len(held),
                "action": action,
                "detail": detail,
                "would_seed": would_seed,
            }
        )
    return {
        "subdomain": tenant.subdomain,
        "from_version": current_version_of(seeded_versions),
        "to_version": version,
        "lists": lists,
    }


def current_version_of(seeded_versions: dict[str, list[str]]) -> str | None:
    """The highest fixture version this tenant holds ANY seed-run row for, or
    None for a tenant that has never been seeded at all."""
    every = [v for versions in seeded_versions.values() for v in versions]
    return max(every, key=version_key) if every else None


# ── the "behind" read (BR-TEN-079) ──────────────────────────────────────────
def behind_report_for_tenant(tenant: models.Tenant) -> dict[str, Any]:
    """Per list: `current` / `behind (X < Y)` / `never seeded`. Read-only.

    Must run inside the tenant's own context — the table is RLS FORCE and this
    is deliberately a per-tenant loop rather than one cross-tenant SELECT.
    """
    version = fixture_version()
    seeded_versions = _seed_run_versions()
    lists = []
    for row in declared_lists():
        versions = seeded_versions.get(row["list"], [])
        if not versions:
            state, at = STATE_NEVER, None
        else:
            at = max(versions, key=version_key)
            state = STATE_CURRENT if version_key(at) >= version_key(version) else STATE_BEHIND
        lists.append({**row, "at_version": at, "state": state})
    return {
        "subdomain": tenant.subdomain,
        "fixture_version": version,
        "lists": lists,
        "behind": [row["list"] for row in lists if row["state"] == STATE_BEHIND],
        "never_seeded": [row["list"] for row in lists if row["state"] == STATE_NEVER],
    }


# ── OQ-086: divergences are NAMED, never applied (BR-TEN-071) ───────────────
#: Serialized fields that are plumbing, not content — never compared.
_NON_CONTENT_FIELDS = frozenset({"id", "used_by", "active", "is_system", "code"})


def divergences(tenant: models.Tenant) -> dict[str, Any]:
    """Fixture entries whose value differs from what this tenant already holds.

    OQ-086 (CLOSED, PO 2026-08-10) rules that a corrected value reaches a tenant
    only through an audited, opt-in "apply correction" that NAMES each affected
    row. This function is the naming half and nothing else: it writes nothing,
    changes nothing, and the sweep prints what it returns. Silence would be the
    DEF-016 failure in a new place — the sweep quietly not applying a correction
    it can see.

    ⚠ WHAT IT CANNOT SEE, SAID OUT LOUD (hard-won law 1). The only sanctioned
    cross-module read here is the registered lookup handler's `serialize()`, and
    those payloads carry identity, not money: rating's charge-code handler
    deliberately omits `amount`, `percent` and `min_amount` because "a fee's
    MONEY is rating law, not reference-data plumbing" (its own docstring), and
    no handler exposes a tax rate. So a corrected NAME is detected and a
    corrected RATE is not — TC-6's own worked case (TX Local 2.00 % → 1.75 %)
    is in the invisible half. Closing that needs a `reference_seed_divergences`
    read seam published by each owning module; it is REPORTED in the build
    report, not faked here, and `unverifiable` below names every list in that
    state on every run so the gap cannot go quiet.
    """
    fixture = services._load_seed_fixture()
    state_code = selectors.us_state_code(tenant.state) if tenant.state else None
    found: list[dict[str, Any]] = []
    unverifiable: list[str] = []
    for row in declared_lists():
        list_code = row["list"]
        definition = services.LOOKUP_LISTS.get(list_code)
        handler = definition.handler if definition is not None else None
        entries = _fixture_entries(fixture, list_code, state_code)
        if not entries:
            continue
        if handler is None:
            unverifiable.append(list_code)
            continue
        held = {}
        for obj in handler.search(None):
            payload = handler.serialize(obj)
            code = payload.get("code")
            if code:
                held[str(code).strip().lower()] = payload
        comparable = False
        for entry in entries:
            code = str(entry.get("code", "")).strip().lower()
            payload = held.get(code)
            if payload is None:
                continue  # absent = an INSERT, not a correction
            for field, fixture_value in entry.items():
                if field in _NON_CONTENT_FIELDS or field not in payload:
                    continue
                comparable = True
                held_value = payload[field]
                if str(held_value) != str(fixture_value):
                    found.append(
                        {
                            "list": list_code,
                            "code": entry.get("code"),
                            "field": field,
                            "fixture": fixture_value,
                            "tenant_holds": held_value,
                        }
                    )
        if not comparable:
            # The handler answered, but shares no field with the fixture entry —
            # money-only lists land here. Same honesty as an absent handler.
            unverifiable.append(list_code)
    return {"divergences": found, "unverifiable": sorted(set(unverifiable))}


# ── the actor (BR-TEN-075) ──────────────────────────────────────────────────
def owner_actor(tenant: models.Tenant) -> Any:
    """A System Admin actor whose id is the tenant's REAL owner user, so the
    audit rows name a person and not a synthetic uuid.

    Both seams are optional here: an unresolvable owner yields
    `actor_user_id = NULL` — a system action — rather than a foreign-key
    violation or an invented id. Same fallback `seed_demo._backfill_actor` uses,
    and the same reason.
    """
    from types import SimpleNamespace

    from core.permissions import SYSTEM_ADMIN

    owner_user_id = None
    try:
        email = seams.owner_email_for(tenant.id)
    except seams.SeamNotWired:
        email = None
    if email:
        from apps.identity import selectors as identity_selectors

        owner = identity_selectors.user_by_email(tenant.id, email)
        owner_user_id = str(owner.id) if owner is not None else None
    return SimpleNamespace(id=owner_user_id, pk=owner_user_id, role=SYSTEM_ADMIN)


def _record_sweep_failure(tenant: models.Tenant, exc: Exception) -> None:
    """BR-TEN-075: `reference.sweep_failed` — tenant, list and exception class
    only. NO PII and no fixture payload; the same posture as US-TEN-004's
    `tenant.provision_failed`, and best-effort for the same reason: the failure
    answer must never be masked by a trail problem."""
    try:
        core_audit.write_row(
            action="reference.sweep_failed",
            entity_type="tenant",
            entity_id=tenant.id,
            actor_user_id=None,
            after={"subdomain": tenant.subdomain, "error": type(exc).__name__},
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("reference.sweep_failed trace could not be written")


# ── the sweep itself (BR-TEN-074) ───────────────────────────────────────────
def sweep_tenant(tenant: models.Tenant, *, dry_run: bool = False) -> dict[str, Any]:
    """Sweep ONE tenant. Enters that tenant's context; one transaction.

    `dry_run` (BR-TEN-076) computes the same plan and returns before any write:
    no reference rows, no `reference_seed_runs` rows, no audit rows.

    A failure rolls this tenant back WHOLE, records `reference.sweep_failed`
    and returns `outcome='failed'` — it never raises at the caller, because
    BR-TEN-074's point is that the sweep continues to the next tenant.
    """
    with core_tenancy.tenant_context(tenant.id):
        plan = plan_for_tenant(tenant)
        divergence = divergences(tenant)
        result: dict[str, Any] = {
            **plan,
            "divergences": divergence["divergences"],
            "unverifiable": divergence["unverifiable"],
            "seeded": {},
            "skipped": {},
            # DEF-253 — see the top-up call below. Always present so a caller
            # never has to ask whether this sweep was one of the ones that
            # renewed a calendar; `0` on a dry run, by construction.
            "holidays_added": 0,
            "deferred": {
                row["list"]: row["detail"]
                for row in plan["lists"]
                if row["action"] == ACTION_DEFERRED
            },
            "outcome": OUTCOME_PLANNED,
            "error": None,
        }
        if dry_run:
            return result
        try:
            with transaction.atomic():
                # BR-TEN-070: the EXISTING backfill service, with BR-TEN-067's
                # structural narrowing forced on per OQ-088's ruling.
                summary = services.seed_reference_data_for_tenant(
                    tenant, owner_actor(tenant), structural_only=True
                )
                # DEF-253 — THE HOLIDAY RENEWAL, and this is the right place
                # for it for one reason: **the sweep is the only thing in this
                # product that walks every tenant that already exists.** A
                # change to provisioning never reaches them (hard-won law 4),
                # and the calendar is the one seeded object whose absence is
                # not merely missing data but WRONG MONEY — a late fee a day
                # early, on a public holiday, computed confidently.
                #
                # It is deliberately NOT gated on the fixture version. The
                # fixture version answers *"has this tenant received the
                # current standard vocabulary"*; the calendar horizon answers
                # *"has time passed"*, and time passes without anyone bumping a
                # fixture. Gating it would have reproduced the original defect
                # with an extra step.
                #
                # ⚠ It never re-seeds an emptied calendar — that refusal lives
                # in `ensure_us_holidays_through` and is asserted by
                # tests/test_cr010_silent_seed_gaps.py, because re-imposing US
                # federal dates on a non-US tenant every sweep is the failure
                # this fix must not cause.
                result["holidays_added"] = services.top_up_holiday_calendar(tenant)
        except Exception as exc:  # noqa: BLE001 — isolation is the rule (BR-TEN-074)
            logger.exception("reference sweep failed for tenant %s", tenant.subdomain)
            _record_sweep_failure(tenant, exc)
            result["outcome"] = OUTCOME_FAILED
            result["error"] = type(exc).__name__
            return result
        result["outcome"] = OUTCOME_SWEPT
        result["seeded"] = {code: count for code, count in summary["seeded"].items() if count}
        result["skipped"] = dict(summary["skipped_reasons"])
        return result


def sweep(tenants: list[models.Tenant], *, dry_run: bool = False) -> dict[str, Any]:
    """Walk the given tenants in subdomain order. Returns the run record.

    The caller supplies the tenant list because `tenants` is the PLATFORM
    registry (RLS-exempt, B2 §3) and selecting from it is the one thing this
    module does outside a tenant context.
    """
    results = [sweep_tenant(tenant, dry_run=dry_run) for tenant in tenants]
    return {
        "fixture_version": fixture_version(),
        "dry_run": dry_run,
        "tenants": results,
        "failed": [row["subdomain"] for row in results if row["outcome"] == OUTCOME_FAILED],
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-020@e7c1a94 (EP-TEN-03 — the fixture-version sweep; co-packet US-TEN-002@178c282, whose reference_seed_runs ledger this finishes)
# generated: 2026-08-15 by story-coder (tenancy/identity lane) · AMENDED 2026-08-18 by story-coder (CR-010 silent-seed-gaps lane — DEF-253: the post-migrate sweep tops up every existing tenant's holiday calendar, ungated on the fixture version because time passes without anyone bumping a fixture)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — BR-TEN-079: no A1 screen, no cross-tenant UI; the surface is the command's stdout) E=deferred(no-frontend-half, same reason) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff check .✔ (16 findings repo-wide, every one in a concurrent lane's test file, none in this lane's) · black --target-version py312 on this lane's 7 files✔ · pytest tests/test_us_ten_020_sweep.py 26 tests: sqlite 25 passed/1 skipped (the isolation TC, via the requires_postgres VENDOR skipif — never a bare skip), live PostgreSQL 16 26 passed · full backend suite `pytest tests` 2581 passed / 160 skipped / 1 xfailed, with 1 PRE-EXISTING FAIL (tests/test_be11_openapi.py snapshot) that was PROVED pre-existing on the untouched baseline BEFORE this lane wrote a line (2400 passed / 144 skipped / 1 xfailed + the same openapi failure) · run_gates: 19 PASS / 2 FAIL / 0 SKIP — and BOTH FAILS ARE OTHER LANES' (G6 names apps/ledger/billing_seam.py:41; G7 names 6 files under apps/ledger, apps/notifications and apps/billing with no review-ledger row). Enumerated mechanically, not assumed: no file of this lane appears in either. The baseline when this lane started was 20 PASS / 0 FAIL (G21 arrived from a concurrent lane mid-session) · no migration in this lane (no schema change — BR-TEN-070's whole point) · LIVE on PostgreSQL 16 against a real seeded tenant: --dry-run left reference_seed_runs/audit_log/premises_types at 12/87/5 exactly; the real run at 2026.08→2026.09 took them to 18/93/5 (6 structural seed-run rows + 6 reference.seeded audit rows, 0 reference rows inserted because the tenant already held them) and named 5 discretionary lists DEFERRED; the replay left 18/93 unchanged · RED-PROVED, three guards, each broken and watched to fail: (1) BR-TEN-077 — one asset type added to lookup_defaults.json with `version` left at 2026.08 makes the command exit 1 with `lookup_defaults.json content changed but \`version\` is still '2026.08' (expected digest fd5015b4…, got 71d69fd7…)`; (2) OQ-088 — flipping structural_only to False fails TC-13 with `AssertionError: charge_codes was delivered to a tenant whose S111 answer is unknown`; (3) BR-TEN-074 — hoisting the work out of tenant_context fails the isolation TC with `core.errors.AuthError: AUTH-003`, the deny-by-default refusal, instead of running globally
# exceptions: US-TEN-020's frontmatter `blocked_by: [OQ-086, OQ-087, OQ-088]` and its TC-6/TC-13 stub instructions are STALE — all three CLOSED 2026-08-10, and G8 fails an OQ-citing stub whose question is closed, so the rulings are implemented instead and the epic carries a dated amendment · OQ-088's residue (what value backfills `tenants.reference_defaults_opted_in` for tenants provisioned before the column exists) is MINTED as OQ-216 and cited at DISCRETIONARY_DEFERRAL_OQ; no column is added and no default is chosen here · OQ-086's APPLY half is NOT built: it needs a per-row "has the tenant touched this?" signal no table carries and an UPDATE path through each owning module — the sweep detects and NAMES divergences and applies none, and `divergences()['unverifiable']` names every list whose money fields the lookup-handler contract does not expose (rating's charge-code handler omits amount/percent/min_amount by design), so TC-6's own worked case — a corrected TX Local rate — is in the invisible half and says so on every run · TC-3's "a 2026.09 row is written for EVERY list including unchanged ones" is narrowed by OQ-088: discretionary lists get no row because they are not delivered at all
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
