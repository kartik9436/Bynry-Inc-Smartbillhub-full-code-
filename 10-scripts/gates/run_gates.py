#!/usr/bin/env python3
"""Merge-blocking gate runner — B12 Addendum r2 (G1-G12, PO-confirmed 2026-08-09);
G13-G16 PO-ratified 2026-08-11; G17-G20 Eng-Lead additions of 2026-08-11, on the
daily PO batch for the same ratification (see each gate's own docstring).

Runs every gate, prints one table row per gate (gate | PASS/FAIL/SKIP | detail),
and exits non-zero if ANY gate FAILs. SKIP is legitimate only when a gate's
target does not exist yet — each SKIP detail says what is missing.

Usage:
    python3 10-scripts/gates/run_gates.py [--wave-close] [--tier1 | --changed [<base>]]

THREE TIERS (PO-approved 2026-09-10). The DEFAULT is unchanged — every gate,
and the only mode that produces a merge verdict.

    (no flag)            TIER 3 — all 123 gates. What runs at merge.
    --tier1              TIER 1 — the always-run set: cheap gates whose damage
                         is irreversible or invisible until much later
                         (duplicate ids, register shape, the ❄️ FROZEN
                         figures, the 🔒 guard list, version/changelog).
    --changed [<base>]   TIER 2 — tier 1 plus every gate whose declared
                         surface the diff touches. Base defaults to
                         origin/<this branch>; the diff is the WORKING TREE
                         against it, untracked files included.

⚠ A SELECTIVE RUN IS NOT A MERGE VERDICT AND SAYS SO. It never prints
`merge allowed`, it prints how many of the 123 gates it did not run, and it
NAMES every one of them. A selective green that reads like a full green would
be the most dangerous thing in this file.

WHAT CHANGED SINCE THE LAST RUN, printed at the top before the rows: gates
NEWLY FAILING, gates NEWLY FIXED, gates whose FAILURE DETAIL CHANGED (red both
runs, findings moved — a new problem hiding inside an old failure), and the
count unchanged. The record lives in `10-scripts/gates/last-run.json`, is
gitignored, and gates nothing; on the first run of a machine the output says
in as many words that there is nothing to compare against, rather than
reporting zero.

--wave-close switches G12 (journeys) from its per-merge checks to its wave-close
ones: every ACTIVATED journey must also be green in a durable run receipt
(07-frontend/journey-evidence/ — moved there by DEF-113 because the old path
inside Playwright's output directory was purged by every run, so a receipt could
vanish nine seconds after being produced). Boot the stack and run the suite
first — `08-qa/01-e2e/stack/boot_stack.sh` then `npx playwright test` in
07-frontend — or the wave close fails for want of a receipt, which is the point.
Python 3.12 stdlib only; safe to run from any cwd. A gate that crashes counts as
FAIL — a broken gate must block the merge, never wave it through.

⚠ THIS RUNNER PRINTS NOTHING UNTIL IT FINISHES, AND AN EMPTY LOG IS
INDISTINGUISHABLE FROM A HANG. Two lanes were misled by that on 2026-09-09:
one killed a healthy run it read as stuck, the other read a truncated tail as
a clean sheet and reported a claim it had not measured. Neither was careless —
the output simply cannot tell a reader "still working" from "wedged", which is
hard-won law 7's own shape (a check whose output cannot distinguish pass from
fail is worse than none, because it is trusted).

So: a quiet log here means WAIT, not restart. A full suite takes tens of
minutes and longer when several lanes share the machine. If you need to know
it is alive, watch the process rather than the output, and never conclude
anything from a partial capture — the failures print at the END, so a tail
taken early shows a clean run that is not clean.
"""
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_unwired_props  # noqa: F401  (imported by g13_unwired)
import g01_packet
import g02_code_trace
import g03_checklist
import g04_golden
import g05_isolation
import g06_forbidden
import g07_human_owned
import g08_stub_honesty
import g09_error_envelope
import g10_tc_tests
import g11_tag
import g12_journeys
import g13_unwired
import g14_prototype_conformance
import g15_i18n_parity
import g16_partition_coverage
import g17_duplicate_ids
import g18_i18n_call_sites
import g19_env_hostnames
import g20_seam_implementers
import g21_refactor_contract
import g22_picker_vocabulary
import g23_surface_deferrals
import g24_holiday_horizon
import g25_screen_coverage
import g26_defect_register
import g31_declared_classes
import g26_required_rows
import g27_engine_surface
import g27_translation_keys
import g28_internal_references
import g29_screen_ids
import g32_refusal_keys
import g33_refusal_copy_length
import g34_type_scale_escape
import g123_one_change_one_version
import g35_version_lockstep
import g36_breakpoint_direction
import g37_row_actions
import g38_stated_absences
import g39_conflict_markers
import g40_unmounted_components
import g41_tenant_guc_form
import g42_gate_entrypoints
import g43_list_toolbar_contract
import g44_display_truth
import g45_declared_filters_rendered
import g46_register_vocabularies
import g47_service_catalog_parity
import g48_import_money_posts
import g49_identifier_series_contract
import g50_filed_claims_resolve
import g51_closed_claims_match_register
import g52_role_gated_doors
import g53_guard_list_coverage
import g54_image_build
import g55_commit_fix_claims
import g56_rls_runtime_guard
import g57_tenant_guc_not_faked
import g58_streamed_tenant_context
import g59_billing_queue_split
import g60_no_address_from_a_vendor_return
import g61_frozen_figures
import g62_cr_task_blockers
import g63_guard_claims_match_list
import g64_golden_engine_coverage
import g65_module_ring
import g66_seeder_savepoints
import g67_fix_leaves_a_trace
import g68_plant_on_postgres
import g69_id_slice_on_screen
import g70_charge_code_gl_default
import g71_audit_payload_prose
import g72_counted_prose
import g73_storm_water_estate
import g74_tables_nobody_reads
import g75_connection_table_no_secret
import g76_operation_modes
import g77_provider_key_branches
import g81_portal_write_points
import g82_cwp_screen_register
import g83_measured_not_asserted
import g88_published_gate_in_the_query
import g85_one_address_home
import g87_declared_dependencies
import g86_house_style_controls
import g90_dead_custom_properties
import g94_credential_three_exits
import g91_portal_staff_separation
import g92_guest_leaks_nothing
import g93_one_build_destination
import g84_module_write_tables
import g95_trace_tests_exist
import g96_portal_reads_name_the_tenant
import g97_routed_views_are_decorated
import g98_lint_clean
import g99_portal_admission
import g135_backend_suite_receipt
import g79_no_send_route
import g80_integrations_queue_split
import g89_provider_error_seam
import g78_work_writes_nothing_foreign
import g100_every_screen_has_a_door
import g101_seeded_starters_have_a_reader
import g102_flows_raise_without_blocking
import g103_holds_cannot_rot
import g106_cited_ids_exist
import g107_one_responsive_direction
import g104_one_declaration_per_component
import g105_screen_matches_its_drawing
import g108_provider_calls_are_guarded
import g109_work_queue_split
import g110_safety_gate_server_side
import g111_no_tax_no_finance_arrow_on_work
import g113_closure_drift
import g114_list_envelope
import g115_runbooks_import_census
import g116_cited_tests_exist
import g117_runbooks_queue_split
import g118_client_calls_have_a_caller
import g119_shadowed_definitions
import g120_the_application_starts
import g121_plans_name_their_late_fee_code
import g122_reads_that_failed_are_visible
import g124_case_chips_the_engine_raises
import g125_decisions_reach_the_money
import g126_integration_reads_name_the_tenant
import g127_a_shape_cannot_compute
import g128_one_address_resolver
import g129_premises_units_copy_caps
import g130_no_card_fields
import g131_immutability_allow_list
import g132_beat_entries_are_installed
import g133_export_columns_agree
import g134_route_b_utilities_compile
import g136_release_step_cannot_be_skipped
import g139_no_database_id_in_a_refusal
import g137_declared_constraints_are_built
import g140_job_bodies_reach_no_role_gate
import g141_one_price_lookup
import g142_one_tariff_version_lookup
import g143_read_modules_name_the_tenant
import g112_computed_key_families

# Modules that live beside the gates and are NOT gates. Each name here is a
# decision someone wrote down; anything else on disk must be registered in
# GATES or `_assert_registry_sane` refuses to start the suite.
GATE_NOT_A_GATE: dict[str, str] = {
    # G12's executable red-proof. It was run by .github/workflows/gates.yml and
    # never here; that workflow is disabled (2026-09-04), so nothing runs it
    # automatically now — see .github/workflows/README.md.
    # It BREAKS things on purpose to prove G12 still bites, so running it inside
    # the suite would report a deliberate failure as a gate failure.
    "g12_selftest": "G12's own red-proof — runs in CI, breaks things on purpose",
    # G53's own red-proof (DEF-2790, 2026-08-31). Same shape as g12_selftest: it
    # builds a SYNTHETIC repository in a temp directory, breaks exactly one thing
    # per case, and asserts G53 says so in words. Running it inside the suite
    # would report thirteen deliberate failures as gate failures.
    #     python3 10-scripts/gates/g53_selftest.py
    "g53_selftest": "G53's own red-proof — breaks a synthetic repo on purpose",
}

# ── `DEF-GOV-3654` / `DEF-CWP-3734`, 2026-09-04 ────────────────────────────
# The ONE gate number this repo lets two rows share, and the reason it is a
# frozen constant rather than a list anything may append to.
#
# `g27_engine_surface` (2026-08-16) and `g27_translation_keys` (2026-08-19)
# both answer to `G27`. Renumbering either moves **259 citations across 66
# files, 155 of them inside the four shared registers** (defect log 83,
# decision log 40, change requests 24, review ledger 8) — the mass shared-file
# rewrite `CLAUDE.md` refuses zero-padding to avoid — and every one of those
# 259 would first have to be classified BY HAND as engine-surface or
# translation-keys, where one misread creates the exact wrong-pointer bug the
# check below exists to remove. `G84` had four such citations and was
# renumbered; `G27` has 259 and is not. The same answer is not right for both.
#
# ⚠ ADDING TO THIS SET IS A DECISION, NOT A FIX. It is a visible diff that has
# to be defended in `12-governance/02-decision-log.md`, exactly the convention
# `GATE_NOT_A_GATE` above already sets — *a decision someone wrote down rather
# than an omission nobody noticed*. The check below also DELETES an entry that
# has stopped colliding, so this set can only ever shrink.
NUMBER_COLLISION_FROZEN: set[str] = {"G27"}

GATES = [
    ("G1 packet", g01_packet),
    ("G2 code-trace", g02_code_trace),
    ("G3 checklist", g03_checklist),
    ("G4 golden", g04_golden),
    ("G5 isolation", g05_isolation),
    ("G6 forbidden", g06_forbidden),
    ("G7 human-owned", g07_human_owned),
    ("G8 stub-honesty", g08_stub_honesty),
    ("G9 error-envelope", g09_error_envelope),
    ("G10 tc-tests", g10_tc_tests),
    ("G11 tag-stamp", g11_tag),
    ("G12 journeys", g12_journeys),
    # G13 added 2026-08-10 by Eng-Lead, from the defect log's own numbers: the
    # largest single category was `unwired-prop` (4 of 21 — DEF-007..010), a
    # component built, styled and fully tested, then never given its data. All
    # twelve gates above passed on every one of them, because each asks about
    # law, traceability or output shape and none asks whether a component was
    # wired. RATIFIED 2026-08-11 (PO, option A "keep all four blocking"):
    # G1–G16 are ALL the confirmed merge-blocking set. G13–G16 were Eng-Lead
    # additions from defects that reached the running product; they are now
    # confirmed law, and loosening one is a change to a ratified decision.
    ("G13 unwired-props", g13_unwired),
    # G14 added 2026-08-10 by Eng-Lead, from hard-won law 6: "diff the running
    # app against 05-prototype/ — no gate looks at rendered output". DEF-021
    # was found by a human doing exactly that, and G1–G13 all passed on it.
    # This repeats the part of that walk a machine can: prototype copy vs
    # shipped copy, and no screen drawing its own page head. It does NOT claim
    # a pixel diff — that needs a browser and stays a Playwright journey.
    ("G14 prototype-conf", g14_prototype_conformance),
    # G15 added 2026-08-10 by Eng-Lead. i18n/index.ts registers five languages
    # and no gate had ever compared the five catalogues to each other: the S1
    # port (US-TEN-018) put 18 `public.plan.*` keys in en.json and in none of
    # the other four, and G1-G14 all passed on it. Non-English prospects got a
    # pricing card that fell back to English mid-list. This asserts key-set
    # parity in both directions plus an EXPLICIT allowlist of the strings that
    # may legitimately stay English (product name, acronyms, loanwords).
    ("G15 i18n-parity", g15_i18n_parity),
    # G16 added 2026-08-11 by Eng-Lead, from DEF-031: NFR-24 names five tables
    # that MUST be monthly-partitioned, "No exceptions", and invoice_lines (W3)
    # and journal_lines (W5) shipped flat with G1-G15 green — no gate reads
    # NFR-24, and the partition guard only asks whether the partitions that
    # EXIST are RLS-guarded. DEF-031's prevention column calls this the durable
    # half of the fix. The tables genuinely blocked on OQ-107/OQ-108 are excused
    # only through partition_exceptions.txt, which expires with its OQ (the G8
    # pattern), so the exception cannot outlive the question that justified it.
    ("G16 partition-cov", g16_partition_coverage),
    # ── G17–G19 added 2026-08-11 by Eng-Lead, from five defect rows that each
    # named a missing comparison and left it unbuilt. G1–G16 are the PO-ratified
    # set (2026-08-11, option A "keep all four blocking"); these three are
    # Eng-Lead additions and are merge-blocking from the moment they are wired,
    # so each is REPORTED for the daily PO batch and recorded in
    # 12-governance/02-decision-log.md rather than treated as routine.
    #
    # G17, from DEF-053: two lanes minted OQ-117 for two different questions in
    # one hour, the THIRD such collision in a day (OQ-113/114 were the first).
    # `common.oq_status_by_id()` keys a dict on the id, so one row silently wins
    # and G8 can validate a stub against the wrong question's status. Eight
    # vocabularies, one rule: an ID the repo references by ID is defined once.
    ("G17 duplicate-ids", g17_duplicate_ids),
    # G18, from DEF-036 + DEF-041 + DEF-049 — three defects, ONE missing
    # comparison. G15 proves the eleven catalogues agree with EACH OTHER, which
    # is exactly as strong as en.json being right; nothing had ever compared a
    # catalogue to the CODE. G15 is untouched (DEF-036: replacing one with the
    # other would reopen the gap it closed) and this is a second gate: every
    # catalogue key has a call site, every lookup resolves to a key.
    ("G18 i18n-callsites", g18_i18n_call_sites),
    # G19, from DEF-050: the sign-in help string types the live production host
    # into the copy, in all eleven catalogues. A 2026-08-10 fix was meant to
    # catch exactly this class and missed it because that sweep searched for the
    # DEAD domain — "a search shaped by the bug you already know about finds
    # only that bug". This gate carries no domain list at all; it matches the
    # SHAPE of a host, and both instances are replayed as self-test fixtures.
    ("G19 env-hostnames", g19_env_hostnames),
    # G20, from DEF-075 — and DEF-035 and DEF-047 are the same family. Three
    # gate-shaped holes were named in three prevention columns and none was
    # built: nothing had ever asked whether a DOCUMENTED cross-module seam has
    # an implementer. `apps/tenancy/seams.py` documents BR-TEN-042's currency
    # lock as `financial_records_exist()` in BOTH billing and payments; only
    # payments authored it, so a tenant holding issued bill BL-2606-000001
    # (108.88 USD) changed its currency USD→CAD at 200 OK, measured live. 1,961
    # tests and 19 gates were green over it. G20 harvests every seam contract
    # from the prose AND from the late-bound lookups, and fails when the named
    # callable is absent (DEF-075) or lives at another kind (DEF-035). Gaps that
    # are legitimately unwired are PARKED in seam_known_gaps.txt, each with the
    # guard that keeps its reason true — and the gate re-asks the guard, so a
    # park cannot outlive the emptiness it was justified by.
    ("G20 seam-impl", g20_seam_implementers),
    ("G21 refactor-contract", g21_refactor_contract),
    # G22, from DEF-114 — and DEF-095, eight hours earlier, is the same family.
    # A screen offers a list of ids and some OTHER endpoint has to accept them,
    # and nothing had ever compared the two vocabularies. The S15 Assign-plan
    # picker read `GET /rate-schedules` while `POST /units/{id}/plan-assignments`
    # resolved the id against `rate_plans`, so every option the screen offered
    # was refused 422 — `unit_plan_assignments` was empty on a fully seeded
    # stack, no human could put a unit on a plan, and BR-MET-040 held every
    # account activation behind it. Both halves were correct alone and both were
    # tested; 21 gates were green. This is the STATIC half of a two-lock guard:
    # it re-extracts each wrapper's own path literal and fails on drift, on a
    # picker no screen calls, and on a missing live probe. The LIVE half —
    # 06-backend/tests/test_def_114_picker_vocabulary.py — posts what the picker
    # serves at the real endpoint, which is the part no comment can fake.
    # Eng-Lead addition, merge-blocking from wiring; REPORTED for the daily PO
    # batch like G17-G21 and recorded in 12-governance/02-decision-log.md.
    ("G22 picker-vocab", g22_picker_vocabulary),
    # G23 added 2026-08-15 by the DEF-112 lane, and that defect's prevention
    # column is its specification, verbatim: "a story whose trailer says
    # `E=deferred(no-frontend-half)` is not done, and nothing today
    # distinguishes it from one that is. Every lane wrote its gap down honestly
    # and the module still ended up unreachable, so the missing check is one
    # that ADDS UP the deferrals per module and refuses to call a module
    # complete while its surface is absent. THE COUNTING WAS NEVER DONE, BY
    # ANYONE OR ANYTHING."
    #
    # G1-G22 were all green while the ENTIRE finance surface was unreachable —
    # 2,400 tests passing against a module a user could not open — because each
    # of them asks about law, traceability, wiring or output shape WITHIN ONE
    # FILE, and none adds two honest notes together. This is the first gate that
    # counts across files. Its register is surface_debt.txt and the count there
    # is EXACT, not a ceiling: adding a deferral raises it and building a
    # surface lowers it, so neither can happen without somebody reading the
    # sentence beside the number. Eng-Lead class, merge-blocking from wiring;
    # REPORTED for the daily PO batch like G17-G22 and recorded in
    # 12-governance/02-decision-log.md.
    ("G23 surface-debt", g23_surface_deferrals),
    # G24 holiday-horizon (DEF-042). A tenant's holiday calendar covered the
    # SIGN-UP YEAR only and nothing renewed it, so on 1 January every
    # business-day grace calculation quietly reverted to skipping weekends.
    # The PO's own case is the measurement: a bill due Thu 24 Dec 2026 with 5
    # business days' grace must charge on Tue 5 Jan 2027, and without 1 Jan
    # 2027 in the calendar the fee lands Mon 4 Jan — a day early, ON a public
    # holiday. Two clauses: the CODE must seed beyond the current year (holds
    # with no database, which is where CI runs), and every NON-EMPTY tenant
    # calendar must reach the horizon. An EMPTY calendar is never a failure —
    # BR-TEN-039 makes it the tenant's, and a utility outside the US deletes
    # every seeded date legitimately.
    ("G24 holiday-horizon", g24_holiday_horizon),
    # G26 added 2026-08-16 by the DEF-116/123 lane, and DEF-123's escape column
    # is its specification, verbatim: "Nothing in this repository asks whether a
    # REQUIRED per-tenant row has any way of coming into existence."
    #
    # `bill_templates` landed with a complete lifecycle service whose own tests
    # passed AGAINST ROWS THE TESTS CREATED. In the product nothing ever wrote
    # one: S8's Templates tab had no endpoint, provisioning had no billing
    # seeder, no migration planted a default. So the pin BR-BIL-026 makes
    # non-optional could not be resolved and NO BILL COULD BE ISSUED ON ANY
    # DEPLOYMENT — with 24 gates and ~2,800 tests green over it. G13 is the
    # closest gate and it looks the other way: it catches code unreachable from
    # CODE (a prop nothing passes); this is code unreachable from DATA, which no
    # gate modelled. Four clauses over required_rows.txt: the refusal still
    # raises, the writer exists, the writer is REACHED (an AST call site, or a
    # view inside a mounted path — a comment is not a call, hard-won law 1), and
    # a discovery pass that fails on any "this tenant has no ..." refusal the
    # register cannot account for. Its blind spot is written into its own
    # docstring rather than left to be discovered. Eng-Lead class,
    # merge-blocking from wiring; REPORTED for the daily PO batch like G17-G25
    # and recorded in 12-governance/02-decision-log.md.
    ("G26 required-rows", g26_required_rows),
    # G27 added 2026-08-16 by the DEF-128 lane, and that defect's prevention
    # column is its specification, verbatim: "a check that counts a module's
    # ENGINE lines against its SURFACE lines and fails when a module with
    # thousands of lines of tested logic serves no route. ZERO is the number to
    # fail on, because a module at zero is invisible to every completeness
    # measure the repo currently computes."
    #
    # `apps/notifications` measured 7,084 lines — dispatcher 877, services 897,
    # template_service 796, notices 701, delivery_ops 635, rendering 568 and
    # more, every one of them tested — behind an `api.py` of 72 BYTES with no
    # urlpatterns and no include naming it. NOTHING A CUSTOMER WAS EVER SENT
    # could be triggered, listed or audited through the product, and it was the
    # FOURTH occurrence at whole-module scale in one release (billing, payments
    # and ledger are the other three, each recorded in config/urls.py).
    #
    # G23 is the closest gate and it cannot catch this: it COUNTS a module's
    # declared-unreachable stories and passes as long as the number in
    # surface_debt.txt matches, so a module can declare twelve and stay
    # unreachable forever. DEF-080's proposed gate compares exported urlpatterns
    # against contracted routes and has nothing to compare when a module exports
    # none. Both need the module to have started; this one asks whether the pile
    # of code has a door AT ALL, and counts an UNMOUNTED route as zero because a
    # 404 is what a user gets either way. Eng-Lead class, merge-blocking from
    # wiring; REPORTED for the daily PO batch like G17-G26 and recorded in
    # 12-governance/02-decision-log.md.
    ("G27 engine-surface", g27_engine_surface),
    # G25 added 2026-08-16 by the DEF-129 lane, from hard-won law 8 broken THREE
    # times: DEF-006 (S1, the public landing page, half-missing for a week),
    # DEF-129 (S7, the tenant dashboard — the first screen after every sign-in —
    # rendering the literal string "SMARTBillHub — W0 scaffold") and DEF-137
    # (S113, step 4 Review of the signup flow, found in review). Each is one
    # screen in the inventory that no story owned, so it was nobody's to build
    # and nobody's to notice, and G1–G24 all passed on every one of them.
    #
    # It asserts the STORY half only — every inventory screen is claimed by a
    # story's `screens:` frontmatter. It deliberately does NOT assert that a
    # claimed screen exists in the app: DEF-137 measured that signal and found it
    # over-reports absence on nineteen WORKING screens, because screens carry no
    # id in the frontend (SignupWizard.tsx is built, driven end to end by J1, and
    # names neither S4 nor S5). The convention that unblocks the second half — a
    # `screens:` line in each screen file's Lifecycle trailer — is stated in this
    # gate's docstring and adopted by the files that lane wrote.
    #
    # ⚠ Eng-Lead-class addition: merge-blocking from the moment it is wired, so
    # REPORTED for the daily PO batch and recorded in 12-governance/02-decision-log.md
    # (the G17–G24 route).
    ("G25 screen-coverage", g25_screen_coverage),
    # ⚠ **G27-translation-keys WAS NEVER REGISTERED HERE, AND THAT IS ITS OWN
    # FINDING (CR-016, 2026-08-19).** It was written on 2026-08-19 for DEF-307
    # — a whole card rendering `notifications.rights.title` and ten siblings as
    # its own text — proved RED, proved green over 126 components, and left as a
    # standalone script no runner called. That is hard-won law 2 exactly ("built
    # is not wired"), committed by the lane that was fixing a law-2 defect. A
    # gate nothing runs is a comment claiming a guarantee (law 1). Both are
    # wired now.
    #
    # ⚠ The FILE is `g27_translation_keys.py` while `g27_engine_surface.py`
    # already held the number. The collision is left alone deliberately — the
    # file names are cited from DEF-307 and from CR-016 — and the row labels
    # below are what a reader of this table sees, so they disambiguate.
    ("G27 i18n-keys", g27_translation_keys),
    # G28 (CR-016, 2026-08-19) — the sibling of the line above and its exact
    # complement. G27 asks "does this key resolve?"; G28 asks "should a utility
    # be READING what it resolves to?" The PO photographed a deployed Settings
    # screen showing a database column name, an HTTP route, a dotted module path
    # and two quoted PO rulings, and said: *"you should follow screen that is
    # given - you are adding your own content and details on screen/Ui - too
    # much problem"*. Proved RED at 219 violations against the tip that carried
    # them, green at 0 after the sweep. Eng-Lead class, merge-blocking, REPORTED
    # for the daily PO batch on the G17–G26 route.
    ("G28 internal-refs", g28_internal_references),
    # G29 (CR-016 addendum, 2026-08-19) — the OTHER half of G25. G25 reads the
    # inventory against the STORIES and its own docstring says it cannot read it
    # against the CODE, because *"screens do not carry their id"*. They do now:
    # `07-frontend/src/routing/screenIds.ts` is one row per routed screen
    # carrying the id A1 allocates and the badge r10 draws, and this gate
    # refuses an id neither authority defines — which is the failure that would
    # otherwise reach a screen, get photographed, and be filed as a defect
    # against an id no document can resolve. It also RATCHETS the screens that
    # have no id at all: hard-won law 8, counted, with a written reason each.
    # Proved RED three ways (an invented S-id, an invented r10 badge, and a
    # screen silently losing its id) before being trusted green. Eng-Lead class,
    # merge-blocking, REPORTED for the daily PO batch on the G17–G28 route.
    ("G29 screen-ids", g29_screen_ids),
    # G30 (2026-08-19) — the defect register's own gate: duplicate ids, row
    # width, the status vocabulary, prose smuggled into a status column, and an
    # empty escape_reason. It was WRITTEN on 2026-08-19 and NEVER REGISTERED
    # HERE, so for a day it checked nothing at all.
    #
    # ⚠ That is hard-won law 2 for the SECOND time in this file and the THIRD in
    # two days — `g27_translation_keys` was written, proved RED, and left
    # unwired by the very lane that was fixing a law-2 defect (see its note
    # above), and this one was written by the lane that wrote THAT note. A gate
    # nobody runs is a comment claiming a guarantee (law 1), and the reason it
    # keeps happening is that writing the file FEELS like shipping the check.
    # The guard in main() below now makes an unregistered gate module the one
    # thing this runner refuses to start without — see `_assert_registry_sane`.
    #
    # ⚠ It is numbered **G30, not G26**, because `g26_required_rows` already
    # holds 26 and the FILE was named `g26_defect_register.py` by a lane reading
    # the highest number it could see in a tree six lanes were writing — the
    # DEF-284 id-collision mechanism, one register over. The file name is left
    # alone (it is cited from DEF-300 and from `file_defect.py`'s docstring) and
    # the LABEL disambiguates, which is the convention the G27 pair already set.
    ("G30 defect-register", g26_defect_register),
    # G31 (CR-016, 2026-08-19) — every class a component asks for must be
    # DECLARED by a stylesheet. A `className` naming nothing renders as nothing,
    # and the three checks that should catch it cannot: `tsc` sees a string,
    # eslint sees a string, and `toHaveClass("bil-layout-card")` PASSES because
    # the class IS on the element — nobody asked whether it means anything. So
    # the screen looks broken to a customer and healthy to every automated check
    # this repo owns.
    #
    # DEF-244, DEF-305, DEF-308, DEF-314 and DEF-315 are all this one shape,
    # across five months, every one found by a human reading a screenshot.
    # DEF-308 was 26 files asking for `.kicker`, the shared PageHeader among
    # them, so it was on nearly every screen at once.
    #
    # Requested in as many words by the lane that filed DEF-314/315: *"every
    # className in *.tsx vs every class declared in *.css, fail on the
    # difference."* Ratcheted at 125, because 125 are undeclared TODAY and a
    # gate that is red from birth earns a noqa instead of a fix.
    ("G31 declared-classes", g31_declared_classes),
    # G32 / G33 (DEF-322, 2026-08-19) — the two halves of one PO ruling, and
    # they are registered TOGETHER because either alone is a trap.
    #
    # The PO ruled that server `detail` text never reaches a customer screen:
    # a refusal's words come from the catalogue entry for its `message_key` and
    # from nothing else. On the day of the ruling 48 of the 319 keys the backend
    # raised resolved to NOTHING, so suppressing `detail` on its own would have
    # turned 48 refusals from ugly to SILENT — the user clicks, nothing happens,
    # no explanation anywhere. G32 is the guard that this can never happen
    # again: every raised message_key must resolve, plural-suffix aware
    # (DEF-323), ratcheted at 0 because the 48 were written FIRST.
    #
    # G33 holds the second half of the same ruling — *"you need shorter
    # sentences not long ones"* — as a number: no sentence over SIX words, at
    # most two sentences. ⚠ SIX SINCE 2026-08-30, NOT TWELVE — PO ruling,
    # verbatim: *"Refusal copy is short - your 12-word ruling - this shuld be 6
    # words only - not too long; this family BORN ASPIRATIONAL it cannot be
    # ASPIRATIONAL any more - there are so many bugs becuase of this."* Twelve
    # was the catalogue's own median longest sentence rounded up from 9 and it
    # held at 96% passing; six passes 30%, so the 598 messages already over it
    # are named in `g33_refusal_copy_baseline.txt`, which may only shrink, and
    # six binds every new or CHANGED refusal from today (DEF-2606). English
    # only, in the ruling's own words, because the eleven locales follow their
    # own language's natural length.
    #
    # ⚠ AND THE CLAUSE THAT KEEPS SIX FROM BEING WORSE THAN TWELVE, which G33
    # now prints in its own failure output: SHORTEN BY DELETING THE RATIONALE,
    # NEVER THE INSTRUCTION. Two sentences of six beat one sentence of twelve —
    # cutting the sentence that says what to do next PASSES the gate and makes
    # the message useless, and nothing downstream can catch that.
    #
    # Both proved RED before being trusted green, and both proved GREEN on the
    # false positive that would otherwise switch them off: a plural-only key for
    # G32, a long NON-refusal value for G33.
    ("G32 refusal-keys", g32_refusal_keys),
    ("G33 refusal-copy", g33_refusal_copy_length),
    # G129 is G33's rule pointed at the OTHER four kinds of rule-33 copy, on the
    # premises and units screens. G33 caps refusals; B14 records the other four
    # as RATIFIED and NOT ENFORCED, and 218 strings were over the cap the day
    # this landed (DEF-MET-5836). Same measurement — G33's own `sentences()`,
    # imported rather than copied — same baseline-that-may-only-shrink, and the
    # same English-only scope, because rule 35 says the ten others follow their
    # own language's natural length.
    ("G129 premises/units copy caps", g129_premises_units_copy_caps),
    # G130 — THE NEW WORLD CARD ATTRIBUTES NEVER CARRY A VALUE (CR-132-BRC07,
    # 2026-09-22; amended 2026-10-21, DEF-INT-10304: PO option A, the four
    # names are written present and always "" — this gate now fails any code
    # or file that could give one a value). Original note:
    # Their receipt specification carries four `ReceiptPaymentCreditCard*`
    # fields. Populating one pulls cardholder data into a partner file and
    # destroys this product's PCI scoping. The PO ruled NOT BUILT rather than
    # built-and-switched-off, so there is nothing to turn on — and this gate is
    # what keeps it that way when a lane meets their spec beside our emitter and
    # helpfully "completes" it. It allows the name in PROSE (every file that
    # explains the absence names them on purpose) and refuses it as a quoted
    # string, an XML element or an identifier.
    ("G130 newworld-card-fields", g130_no_card_fields),
    # G131 — HARD RULE 4's ALLOW LIST MOVED ONCE, FOR THREE COLUMNS, AND STAYS
    # THERE (CR-137-BRC07 P3.8, 2026-09-23). The PO narrowed financial
    # immutability on 2026-09-02 for `confirmation`, `memo` and `method_id` and
    # for nothing else, and CLAUDE.md says `payments/0014` is the ONLY place
    # that list moves. Until this gate, that sentence was enforced by two
    # docstrings asking politely — hard-won law 1 exactly. The realistic breach
    # is not malice: the trigger freezes EVERY new column on `payments` the day
    # it is created, so a lane needing to stamp one on a frozen row has a
    # four-character fix that makes their migration work and quietly widens hard
    # rule 4 for every payment this product will ever take. It also refuses the
    # bypass — arrays untouched, the branch that CONSULTS them removed — and its
    # own red proof runs as part 0 of every invocation rather than once at birth.
    ("G131 payment-immutability-allow-list", g131_immutability_allow_list),
    # G132 — A BEAT ENTRY THAT IS DECLARED IS ONE THAT IS INSTALLED
    # (CR-136-BRC07 P2.11, 2026-09-23). This is G117's third clause asked of
    # every module rather than of the `runbooks` queue alone, and it is the
    # clause `DEF-PAY-6268` was: the sweep that tells a supervisor about a
    # counter nobody closed, and the command that runs it, both landed correct
    # and **nothing on any clock called either**, so a PO ruling was unmet in
    # practice while every check passed. It reads the SYNTAX TREE rather than
    # the text, because three of these `apps.py` files name `install()` in a
    # comment or a docstring and a substring search is satisfied by prose. It
    # also refuses two modules claiming one entry key — every installer does
    # `existing.update(schedule)`, so that is one schedule erasing another.
    ("G132 beat-entries-installed", g132_beat_entries_are_installed),
    # G133 — 6·2's TICKED COLUMNS ARE THE SERVER'S OWN COLUMN NAMES
    # (CR-140-BRC09 P4.12, 2026-09-24). `P4.13` put `columns` on
    # `POST /exports` and `columns_for()` DROPS a name the resource does not
    # have, falling back to the default set when it knows none of them — both
    # right, both SILENT. So a column renamed on either side of the wire ships a
    # spreadsheet with columns the clerk did not ask for, and every test on both
    # sides stays green because each asserts its own literal against itself. The
    # check has to read TSX and Python together, which is what a gate is for.
    ("G133 export-columns-agree", g133_export_columns_agree),
    # G134 — THE ROUTE B COMPILER CHECK IS IN THE MERGE SET AT ALL
    # (2026-09-25). `G31` skips every file on `route-b-migrated.txt` BY DESIGN
    # and hands it to `07-frontend/src/styles/routeBUtilities.test.ts`, which is
    # the only check here that can ask the real Tailwind compiler whether a
    # class token emits a rule. Nothing ran it: this runner is Python, and
    # `ci-frontend.yml` — the workflow that did `npm test` — has been
    # `.disabled` since 2026-09-04. So `moveOutTables.tsx` drew with no border
    # and no background from 2026-09-24 on `border-danger` / `bg-danger-50`,
    # with tsc, eslint, `toHaveClass()` and all 134 gates green over it. This
    # row shells that one file and reports its orphan list; when vitest is not
    # installed it SKIPs and PRINTS HOW MANY FILES WENT UNCHECKED, because a
    # declared blind spot with no number is indistinguishable from an empty one.
    ("G134 route-b-utilities-compile", g134_route_b_utilities_compile),
    # G136 — THE RELEASE STEP CANNOT BE SKIPPED SILENTLY (DEF-INF-7683,
    # 2026-09-28). `CR-144-BRC07` H4 moved `migrate` out of the web entrypoint
    # for three correct reasons, and a GUARANTEE left with it: while every web
    # task migrated on boot, a task could not serve a schema older than its
    # code. The invariant was an implementation detail, never a check — so the
    # day the detail moved, nothing went red and the product was down within
    # hours, answering 500 to every sign-in while `/api/health` said 200.
    # This row holds the two halves together: the migrate stays OUT of the web
    # entrypoint, the web entrypoint ASKS whether the schema is current BEFORE
    # `exec gunicorn`, `docker-release.sh` is still what migrates, `make up`
    # still runs it, and the runbook still names the one-line recovery. Every
    # check reads EXECUTABLE lines only, because the prose that predicted this
    # outage was itself a comment.
    ("G136 release-step-not-skippable", g136_release_step_cannot_be_skipped),
    # G139 — A DATABASE UUID MAY NOT REACH A CLERK THROUGH A REFUSAL
    # (DEF-RAT-7991, 2026-09-29). The One-time bill screen showed four at once,
    # out of an f-string in the rating chain, through a `detail` field on a
    # **200-response body** — a shape `BR-SHL-020 r2`'s stripper never sees.
    # G28 and G69 both read SOURCE and neither can see an f-string's runtime
    # value, so this gate RUNS the chain and reads the payload. It prints how
    # many raise sites and render sites it does NOT cover, every run, because
    # G32 once reported `0 unresolved` truthfully over 21 live refusals.
    ("G139 no-uuid-in-a-refusal", g139_no_database_id_in_a_refusal),
    # G137 — A CONSTRAINT B2 SIGNS IS A CONSTRAINT THE DATABASE HAS
    # (DEF-RAT-7980, 2026-09-29). B2 §2 signs an `EXCLUDE USING gist` no-overlap
    # constraint on `tariff_versions`; `btree_gist` was never added to
    # `db/000_extensions.sql`, migration 0001 never created it, migration 0004
    # REPORTED that honestly in its own header and left it to a human review
    # that never happened, and `rating/services.py` was then written citing the
    # constraint as the reason two open-ended windows cannot collide. Four
    # versions of one sewer schedule went in force on the same date at a live
    # tenant; one-time and move-out final bills refuse and the ordinary run
    # picks one of the four. Nothing in this repo had ever asked whether a line
    # of the signed schema was BUILT — the docstrings that described it are
    # hard-won law 1 exactly. With a migrated PostgreSQL named by
    # `SBH_SCHEMA_DB_URL`/`DATABASE_URL` it compares B2's table-level UNIQUE,
    # PRIMARY KEY and EXCLUDE declarations against `pg_constraint`; with no
    # database it still decides the EXCLUDE class from migration source read as
    # EXECUTABLE TEXT ONLY, because `rating/0004`'s docstring quotes the missing
    # constraint in full and a grep of raw source passes green on the defect.
    # Both modes PRINT WHAT THEY DID NOT CHECK with a number beside it (law 7's
    # fifth shape), and its detector is shown red on synthetic cases as part 0
    # of every run rather than once at birth.
    ("G137 declared-constraints-are-built", g137_declared_constraints_are_built),
    # G140 — A BACKGROUND JOB REACHES NO ROLE-GUARDED FUNCTION (DEF-AST-8102,
    # 2026-09-30, PO GO). A job's actor carries an id and no role by design, so
    # a `@require_role` function a job can reach can only refuse — and an
    # asset upload over the 200-row bar lost every row that way, three calls
    # below the seam DEF-2515's test looked at. Static call graph from every
    # `set_job_handler` body; `fn.__wrapped__(...)` is the lawful door. Prints
    # the job bodies walked and the functions reached, because a call through
    # a variable is invisible to it (law 7, fifth shape).
    ("G140 job-bodies-reach-no-role-gate", g140_job_bodies_reach_no_role_gate),
    # G141 — A CHARGE CODE'S PRICE IS READ IN ONE PLACE (CR-156-BRC10, PO GO
    # 2026-10-01: *"a repo gate failing any direct query of the price table"*,
    # the third of three locks). Outside `rating/charge_prices.py`, no
    # `ChargeCodeAmount.objects`, no `.amounts.<manager>()`, no
    # `legacy_amount` (the retired `charges.amount`), no raw SQL on the table.
    # Prints the files it read and skipped; a `charge.amount` read is refused
    # at RUN time by the model instead, because no AST can type a variable.
    ("G141 one-price-lookup", g141_one_price_lookup),
    # G142 — A RATE SCHEDULE'S VERSION IS FOUND IN ONE PLACE (CR-157-BRC10, PO
    # GO 2026-10-01: *"a gate failing direct version queries"*). Outside
    # `rating/selectors.py` and the save paths of `rating/services.py` (by
    # function), no `TariffVersion.objects`, no `tariffversion_set.<manager>()`,
    # no `get_model(..., "TariffVersion")`, no raw SQL on the table — except a
    # reasoned (file, function) list that fails when a listed reader stops
    # querying, so it can only shrink by deletion. Prints what it read and skipped.
    ("G142 one-tariff-version-lookup", g142_one_tariff_version_lookup),
    # G143 — A READ MODULE NAMES THE TENANT IN EVERY QUERY (DEF-RAT-9791,
    # 2026-10-06). Production's Edit plan listed twenty utilities' BASE-SOL
    # because `plan_reads.py` trusted RLS alone and RLS was not holding.
    # Every `*_reads.py`, `*_read.py` and `selectors.py` chain rooted at a
    # tenant model's manager must name `tenant…`; outside rating a ratchet
    # holds what was there (may only shrink), rating may never be pardoned.
    # Prints what it skipped: unscoped models, unrooted chains, non-read files.
    ("G143 read-modules-name-the-tenant", g143_read_modules_name_the_tenant),
    # G34 — THE RULED TYPE SCALE HAS NO BACK DOOR (CR-018 Phase 2b, 2026-08-19).
    # Clearing Tailwind's `--text-*` namespace kills `text-2xl` and does NOT kill
    # `text-[12.5px]`: arbitrary values compile from a namespace no @theme block
    # can empty, so every half-step Phase 2 absorbed could come straight back in
    # bracket notation with tsc, eslint and vitest all green. It was not
    # hypothetical — the gate's first run found SEVEN live uses in the one
    # Route-B component, both at values the ruled scale already names.
    # It ALSO holds the count of literal `font-size:` declarations EXACT, which
    # is the check that answers "what can still put an off-scale size on screen".
    # This gate is why the answer has a number: six, all OQ-279.
    # ⚠ Its narrowness is deliberate: `text-[color-mix(in_srgb,…)]` is a COLOUR
    # and passes, because the opacity modifier that would replace it emits
    # `color-mix(in oklab)` and this system writes `in srgb`. A gate that fired
    # on the correct spelling would be switched off, and this whole gate exists
    # because a rule nobody runs is not enforcement (DEF-339).
    ("G34 type-scale-escape", g34_type_scale_escape),
    # G35 (2026-08-19) — the two version literals must be EQUAL. Change-process
    # step 7 declares one version derived everywhere; it is not derived, it is
    # COPIED by a human between two files in two languages, and until now
    # nothing compared them — 36 gates and not one opened pyproject.toml.
    #
    # Third occurrence: DEF-242, DEF-296, and DEF-341, where commit 8ea7847 left
    # package.json at 2.29.7 against pyproject.toml at 2.29.6. Each earlier one
    # was fixed by correcting the number and none made the pair checkable, which
    # is exactly why there was a third.
    #
    # Blind to every other check for a structural reason: each literal is
    # individually well-formed, so JSON, TOML, lint and every test on either side
    # is clean. The fault is a RELATIONSHIP BETWEEN TWO FILES and no file can see
    # that from inside itself. It is also the LAST edit a lane makes, after its
    # own checks have passed — the one moment the mistake is possible is the one
    # moment nobody is looking.
    #
    # Proved RED on the real commit, not a planted one.
    ("G35 version-lockstep", g35_version_lockstep),
    # G123 (2026-09-13) — G35 asks whether the literals AGREE; this asks
    # whether a number names ONE change. Three collisions in one afternoon
    # with eight lanes in one tree (DEF-GOV-5139), and the oldest had been
    # published twice for eight days with nothing looking.
    ("G123 one-change-one-version", g123_one_change_one_version),
    # G36 (2026-08-20) — every responsive rule is DESKTOP-FIRST, and every
    # width is a ruled step. OQ-274 ratified the direction; NOTHING HAD EVER
    # READ ONE. Thirteen max-width rules and two min-width ones coexisted for
    # months because each is individually valid CSS — no lint rule, no test and
    # no gate looks at the SHAPE of a breakpoint, and the two survivors were
    # found by grepping for a report rather than by a check (DEF-345).
    #
    # The mismatch is silent by construction: Tailwind's own breakpoints are
    # min-width, so with both directions live `lg:` and `max-lg:` both compile
    # and mean different viewports — a mistake reads as a working utility.
    #
    # Proved RED on the two real rules, on an off-scale width, and on the theme
    # disagreeing with the gate; proved NOT to fire on `min-width` as a CSS
    # PROPERTY, which shares a name and nothing else.
    ("G36 breakpoint-direction", g36_breakpoint_direction),
    # G37 (2026-08-20) — B14 rule 15: row actions are ICONS WITH AN ACCESSIBLE
    # NAME, from ONE vocabulary. The rule was RATIFIED and enforced by nothing
    # for months, and DEF-337 is what that cost on a live deployment: four red
    # words in one cell on Settings > Users & roles. Sixteen tables were like
    # that and seven were not, and nothing could tell them apart.
    #
    # ⚠ IT CHECKS THE ACCESSIBLE NAME, NOT JUST THE ABSENCE OF TEXT. An icon
    # with no name renders beautifully, passes every text-absence assertion in
    # the suite, and cannot be used without a mouse — and the first draft of
    # that check PASSED on it, because it searched a file for a string that
    # three elements carry. Proved RED three ways after that was fixed: a text
    # link back in a cell, a nameless icon, and a fifth inline pencil.
    ("G37 row-actions", g37_row_actions),
    # A STATED ABSENCE CITES THE ROW THAT WILL KILL IT (DEF-445, DEF-421,
    # DEF-467..473). The plan wizard told staff the Accounts module was not
    # built for weeks after it was, and the PO found it by walking the screen.
    # No gate here can read a sentence for truth, so this reads the ONE property
    # that makes a sentence self-expiring: the DEF or OQ behind it. Ratcheted.
    # Proved RED twice — a stale baseline, and a note losing its id.
    ("G38 stated-absences", g38_stated_absences),
    # AN UNRESOLVED MERGE WAS COMMITTED INTO A MODULE'S LAW (DEF-490). Nothing
    # here compiles a markdown table, so `<<<<<<< HEAD` sat in the rating rules
    # file for two commits with every other gate green over it. One grep,
    # anchored at column 0, with the `=======` divider counted only where a
    # side marker proves it is git's and not a setext heading.
    ("G39 conflict-markers", g39_conflict_markers),
    ("G40 unmounted-components", g40_unmounted_components),
    # A TENANT POLICY THAT RAISES ON AN UNSET MARKER MAKES A FRESH DATABASE
    # UN-BUILDABLE (DEF-639). Every policy read `current_setting('app.tenant_id')
    # ::uuid`, which CASTS AND FAILS when the marker is empty. The denial was
    # correct and it was LOUD — and the same policy is evaluated during FOREIGN
    # KEY VALIDATION, so three committed migrations that clear tenant context
    # before their own deferred FKs are validated killed the build at step 12 of
    # 168. The PO ruled the class fix on 2026-08-24 (*"Change the security rule
    # instead, in a new step"*): the predicate is now NULLIF-wrapped, an unset
    # marker compares NULL, NULL is not TRUE, the row is denied silently on
    # reads and still refused loudly on writes.
    #
    # ⚠ THIS EXISTS BECAUSE THE TEST THAT PROVES IT CANNOT RUN WHERE IT MATTERS.
    # `test_def639_unset_tenant_denies.py::tc6` asks `pg_policies` directly and
    # needs live PostgreSQL, which the unit tier does not provision — so the one
    # check that would catch a new policy in the old form runs on no machine
    # before merge. This one needs no database.
    #
    # A RATCHET, not a ban, and deliberately: the old string legitimately
    # survives in two docstrings that narrate what the predicate USED to be and
    # one `--` comment. Banning it outright would delete the explanation of why
    # the current form exists (hard-won law 10). Proved RED twice — a new file
    # introducing the form, and a baselined file whose count rose.
    ("G41 tenant-guc-form", g41_tenant_guc_form),
    # ── G42, and it exists because BOTH halves of this file's own contract broke
    # on 2026-08-25, in opposite directions, hours apart.
    #
    # A gate is reached two ways: `module.run()` from here, and `__main__` when a
    # human runs the file. A module can satisfy either alone and be silently dead
    # in the other. DEF-672: sixteen modules had `run()` and no main block, so a
    # direct run exited 0 printing nothing — and two commit messages on this branch
    # claim a "G7 PASS" obtained exactly that way. DEF-674: `g41` had `main()` and
    # no `run()`, so THIS FILE crashed on it from the day it was added and counted
    # the crash as one FAIL among many.
    #
    # Deliberately NOT a registry check — `_assert_registry_sane()` below already
    # owns that, does it better, and two checks over one fact disagree the first
    # time somebody edits either. Proved RED in both directions before trusting it.
    ("G42 gate-entrypoints", g42_gate_entrypoints),
    # ── G43, and it exists because EVERY FINDING IN CR-041 WAS A THING FIXED
    # ONCE THAT RECURRED SOMEWHERE ELSE. `.met-filters` was diagnosed twice, a
    # day apart, each time with the conclusion written into the file, and
    # neither diagnosis asked *where else* — the third site had never been
    # looked at. `searchPlaceholder` landed on `TableConfig` to close DEF-510
    # and no screen was wired to it for five days, three of the keys sitting
    # translated in eleven catalogues with nothing rendering them. DEF-900's
    # `max-w-prose` sweep found four files where there are twelve.
    #
    # A comment does not sweep, and a grep run by hand at the moment of a fix
    # measures that moment and decays from the next commit. Two clauses, two
    # shapes on purpose: rule 19 is an INVARIANT at zero (all 23 searchable
    # lists carry a prompt, so the 24th must bring one), rule 18 is a RATCHET
    # over DEF-1006's real 50-element backlog. Proved RED three times — a
    # deleted placeholder, a reverted `max-w-measure`, and a gain not banked.
    ("G43 list-toolbar-contract", g43_list_toolbar_contract),
    # ── G44 · A STORED VALUE MAY NOT REACH A SCREEN WEARING ITS STORAGE ─────
    #
    # SIX instances of one defect, five fixes, and the sixth was still live:
    # DEF-646 (the Meters tab), DEF-894 (consumption), DEF-968 (money and
    # percentage in priced sentences), DEF-899 and DEF-937 (database keys), and
    # DEF-1086 — a REGISTER READING, a fourth kind of number that was in none
    # of the four searches, printing `1008.000000` two columns from a cell that
    # was right. Every fix named the columns it knew about; nothing asked the
    # general question, which is the Product Owner's own words for it: *"why
    # this decimal case keep happen … find it on our won all errors"*.
    #
    # Three clauses, three shapes on purpose. (a) A cell renderer may not index
    # its row by a VARIABLE — an invariant at zero, because a renderer that
    # cannot name its field cannot be given a treatment at all, whatever the
    # rule turns out to be. (b) A field the server already composes may not be
    # rendered raw — an invariant at zero, read exactly out of the API
    # interfaces rather than guessed, and the clause that makes BR-SHL-250
    # self-enforcing: adding a sibling forbids the raw field everywhere.
    # (c) A classified value in a text position with no treatment — a RATCHET
    # over a real 33-element backlog, because a gate red from birth earns a
    # `# noqa` instead of a fix.
    #
    # Proved RED on DEF-1086 itself before its fix; the verbatim failures are
    # in the module's `# RED PROOF` blocks.
    ("G44 display-truth", g44_display_truth),
    # ── G45 · A DECLARED CAPABILITY THAT NOTHING RENDERS ────────────────────
    #
    # THE THIRD QUESTION IN THE "built is not wired" FAMILY, and it is a
    # SIBLING because G13 is PO-ratified and cannot be edited into a different
    # question (G40 set that precedent for exactly this reason):
    #
    #   G13  a PROP nothing passes       → dead UI behind a prop
    #   G40  a COMPONENT nothing mounts  → dead UI behind an import
    #   G45  a CONFIG KEY nothing reads  → dead UI behind a declaration
    #
    # `AssetRegistryPage` declared SEVEN `TableConfig.filters`, every one of
    # them genuinely served, and never passed `filterBarSlot` — so all four
    # asset tabs had search and no filters, and G13 reported PASS because there
    # is no prop to ask about when a prop is simply absent (DEF-1701). The PO
    # found it by looking at four screens.
    #
    # Invariant at ZERO. Proved RED on the tree the PO photographed, where it
    # named THREE files against the two the PO could see — the third,
    # `ServiceRequestsListPage`, carried a comment saying it had no filter
    # control, which is a note and never a plan (hard-won law 1).
    ("G45 declared-filters-rendered", g45_declared_filters_rendered),
    # ── G46 · THE REGISTER'S OWN CONTROLLED COLUMNS ─────────────────────────
    #
    # `severity` held NINE values across TWO vocabularies for seventeen days,
    # so every count ever taken from it was wrong: the figure carried to the PO
    # as "40 high open" was really 90 (DEF-1710). 173 `major` rows were being
    # read as though they did not exist, and step 4 of the execution sequence
    # triages FROM these numbers.
    #
    # ⚠ THIS ROW IS THE SECOND HALF OF ONE JOB AND IT SHIPPED WITHOUT THE
    # FIRST, WHICH IS ITS OWN DEFECT (DEF-1783). The gate landed at `f5c9fb1`
    # deliberately unregistered, with the reason written in its docstring — and
    # `_assert_registry_sane` reads the REGISTRY, not prose, so the whole suite
    # REFUSED TO START for every lane on the branch until this row existed.
    # Hard-won law 1, committed by the lane that wrote the law's own gate: a
    # comment claiming a boundary is not the boundary. The rows are normalised
    # in this same commit, so the suite goes green to green.
    #
    # It REFUSES an unknown value; it never remaps one. The 270-row collapse was
    # a recorded, reversible migration (decision log 2026-08-27, with the full
    # before/after ID lists), not a script left in the tree to run again.
    ("G46 register-vocabularies", g46_register_vocabularies),
    # ── G47 · THE FIRST GATE THAT CROSSES INTO THE DATABASE ─────────────────
    #
    # Step 3 of `12-governance/19-execution-sequence.md`, PO-approved: "EVERY
    # EXISTING GATE COMPARES A FRONTEND ARTEFACT TO ANOTHER FRONTEND ARTEFACT,
    # OR A DOCUMENT TO A DOCUMENT." G13/G40/G15/G18/G31/G43/G44/G45 are all the
    # first kind and G1/G2/G12/G28 are all the second. Signup offered SIX of the
    # platform's TEN services with a green tick for ten days after the ruling,
    # and no check anywhere could see it, because seeing it means reading a
    # Django migration and a React constant in the same breath.
    #
    # This gate reads `SERVICE_SEED` out of tenancy migration 0001 and asks it
    # of every hand-written service list in the repo — fourteen of them, across
    # the frontend, the backend, a fixture and a migration. `signupServices.
    # test.ts` already pins ONE of the fourteen and is not replaced: a test
    # guards the file it names, a gate asks the whole tree, and DEF-1702's
    # lesson is that the sweep finds what the walk did not.
    #
    # Proved RED at 97e745c~1 in a throwaway worktree — it names SignupWizard
    # and the four services a utility could not tick. Order is deliberately NOT
    # checked: two files are correctly out of seed order by a ruling, and a gate
    # that argues with a ruling gets switched off (G45's words).
    ("G47 service-catalog-parity", g47_service_catalog_parity),
    # ── G48 · THE IMPORT↔LEDGER BOUNDARY ────────────────────────────────────
    #
    # Step 3 of `19-execution-sequence.md`. DEF-1713, measured on a full plant:
    # a migrated deposit wrote accounts.deposit_on_file and posted NOTHING —
    # register $750.00 against a 2300 GL of $0.00. **And the books footed.** All
    # 155 seeded journal entries balanced, so hard rule 5 held perfectly; the
    # entry was not unbalanced, it was never made. That is why nothing saw it.
    #
    # DEF-1713's own prevention names the asymmetry this gate looks for: "the
    # opening AR position posts a balanced opening JE, and the deposit half of
    # THE SAME ROW posts nothing at all". So: a money column the shipped import
    # template accepts must be NAMED by a module that posts. Hard rule 5 makes
    # that universe two modules wide, which is what makes the check possible.
    #
    # Ships with ONE banked offender, NAMED not counted — deposit_on_file,
    # DEF-1713, whose fix is 🔒 ledger-posting work owned by step 4. A named set
    # is stronger than a baseline of 1: a SECOND unposted column fails at its
    # own name instead of hiding inside the count. It may fall and never rise,
    # and the gate goes RED as STALE when the fix lands and the row is left
    # behind (DEF-490).
    ("G48 import-money-posts", g48_import_money_posts),
    # ── G49 · THE TEMPLATE↔SERIES BOUNDARY ──────────────────────────────────
    #
    # Step 3 of `19-execution-sequence.md`, third escape: meters were numbered
    # FROM THE FILE rather than from Settings › Numbering, against the CR-046
    # identifier law. That law has three moving parts in three places — the
    # SERIES (core/numbering.SERIES_CATALOG), the WIRING (import_runs.
    # TARGET_SERIES) and the shipped TEMPLATE — and nothing had ever compared
    # them. A target can name a series the catalogue lacks, a series can be
    # wired to a column the file does not carry, and a column can ship a worked
    # sample number that teaches an operator to invent the very identifier the
    # ruling took away. All three are silent: the file loads and the dry run is
    # clean.
    #
    # It reads the REAL built column dicts through a subprocess (no database —
    # module-level declarations only), because `_asset_column` writes `sample`
    # only when one was declared and no regex can tell a declared "" from an
    # absent key. That conditional IS DEF-962's fix.
    #
    # Clause (d) found DEF-1840 on its first run: five served strings send an
    # operator to a Settings tab that does not exist. NOT fixed here — two tests
    # pin the wrong wording and the decision log carries it, so the suite is
    # GREEN ON THE BUG and only the CR-046 owner can rule which name is the
    # product's. Banked BY NAME so a sixth still fails and a fix left in the
    # list goes RED as stale.
    ("G49 identifier-series-contract", g49_identifier_series_contract),
    # ── G50 · A CLAIM THAT A DEFECT WAS FILED ───────────────────────────────
    #
    # "Filed as DEF-1790" appeared in three governance documents and the
    # register carried no such row (DEF-1792). The finding was real; only the
    # row was missing. Worse, max id was DEF-1789, so the next allocation WAS
    # DEF-1790 and went to an unrelated defect — which would have pointed all
    # three citations at a real row about a different subject.
    #
    # ⚠ THE OBVIOUS GATE — "every cited DEF-### resolves" — WAS WRITTEN AND
    # THROWN AWAY. Measured, it reported 24 dangling ids of which nearly all
    # were false positives of the check: reservation RANGES, an unpadded id, a
    # TRUNCATED German quote, and abandoned ids cited as abandoned (which
    # g26_defect_register itself calls legitimate). Shipping it would have made
    # a fifth gate that describes its own output wrongly, after DEF-1788/1861/
    # 1862/1863. So this asks the narrow question the defect was about: not
    # "does every id resolve" but "does every id we CLAIMED TO HAVE FILED".
    #
    # Baseline HARD ZERO with no legacy — 51 claims, all resolving, the one
    # offender fixed in the commit before this one. That is the condition the
    # 2026-08-27 analysis names as why a gate stays green and stays read.
    ("G50 filed-claims-resolve", g50_filed_claims_resolve),
    # ── G51 · A CLAIM THAT A DEFECT IS CLOSED ───────────────────────────────
    #
    # G50's mirror, and the same shape of miss. Seven of the nine high-severity
    # `customers` defects step 4 triaged as OPEN on 2026-08-27 were already
    # fixed in the shipped product, and the code said so in its own words:
    # `apps/customers/service_request_service.py:12` reads
    # `# Defects: DEF-634 ✅ · DEF-635 ✅ · DEF-637 ✅ — all closed` over rows
    # that all read `status: open`. A whole lane was aimed at work already
    # shipped (DEF-1930).
    #
    # ⚠ IT DOES NOT ASK WHETHER AN OPEN ROW IS REALLY OPEN — no source-reading
    # check can know that, and one pretending to would be DEF-182 again. It
    # asks only the question a lane already answered in writing.
    #
    # ⚠ AND A SUB-CLAUSE TICK IS A NARROWER CLAIM. `DEF-638 12.a ✅` over a
    # `fixed-in-part` row is the register AGREEING, not drifting; the gate's
    # first run reported three files for exactly that and was wrong.
    #
    # Baseline HARD ZERO: 3 stale claims measured at the tip, all three rows
    # corrected in the commit that adds this file.
    ("G51 closed-claims-match-register", g51_closed_claims_match_register),
    # ── G52 · AN ACTION THE CODE SAYS A PERSON PERFORMS, WITH NO DOOR ───────
    #
    # The fifth member of the "built is not wired" family, and the mechanism the
    # other four cannot see (DEF-1793). G13 (a prop nothing passes), G40 (a
    # component nothing mounts) and G45 (a config key nothing reads) scan
    # 07-frontend only. G27 is backend but WHOLE-MODULE and fails only at zero
    # routes, by the specification quoted in its own docstring — "ZERO is the
    # number to fail on" — so `apps/rating` serving 32 routes hides DEF-478's
    # six unroutable discount write services perfectly.
    #
    # The scope is `@require_role`, and the reason is that it is a DECLARATION
    # and not a Django convention: a lane writes it to say *a human with this
    # role performs this action*. The previous lane measured the unscoped
    # version — 69 candidates, dominated by apps.py, models.py and management
    # commands — and correctly declined to ship it (decision log 2026-08-27,
    # "THE THREE BOUNDARY GATES, AND WHY THERE IS NO FOURTH").
    #
    # ⚠ IT DOES NOT COVER DEF-438. The R1–R7 chain carries no role decorators
    # and its shape is a whole subsystem with no caller — a different mechanism
    # at a different scale. It uses DEF-438's DEFINITION of reachable ("a route
    # a person can actually get to") so the two cannot diverge, and claims no
    # more than that.
    #
    # Baseline: a NAMED SET of 29, measured at the tip the day it landed —
    # 1,838 lines of built, tested, role-gated write behind no door, in 7 files
    # across 5 modules. Not a hard zero, because no lane in flight is opening
    # those doors and a gate that is red from birth earns a `# noqa` instead of
    # a fix (G44's own words).
    ("G52 role-gated-doors", g52_role_gated_doors),
    # G53 (2026-08-28) — the REVERSE of G7. G7 walks the guard list and checks
    # each file it names; it cannot see a file MISSING from the list, because
    # the list is where it starts. Four money paths escaped exactly that way —
    # issue.py, decisions.py, read_analysis.py, and the three added by PO ruling
    # on 2026-08-28 — each found by a person reading code, never by a check.
    #
    # It ADDS NOTHING to human_owned.txt and must never be made to: that is a
    # process event and the PO's call, not a lane's. It only makes the gap
    # visible. Baseline is a NAMED SET of 50 measured the day it landed, for
    # G52's reason — a count lets one file leave while another joins and reports
    # green over the swap.
    ("G53 guard-list-coverage", g53_guard_list_coverage),
    # ── G54 · RUN THE COMMAND THE IMAGE RUNS ────────────────────────────────
    #
    # DEF-2464, and it is the only defect on this branch that STOPPED A DEPLOY.
    # The Product Owner ran `docker compose build` and got TS2459 on a test
    # file. The lane that wrote it reported `tsc` clean and was telling the
    # truth about the command it ran; `vitest` passed too, because vitest never
    # type-checks. What fails is the image's own `tsc --noEmit && vite build`,
    # which type-checks the test files as well.
    #
    # So a GREEN BRANCH AND A BUILDABLE BRANCH WERE TWO DIFFERENT THINGS and
    # nothing in this repo could tell them apart. `ci-frontend.yml` does run
    # `npm run build` — and only on pushes touching `07-frontend/**`, in a
    # workflow separate from the gate suite every lane runs before merge, so
    # the one check that would have caught it was neither reached nor read.
    #
    # It takes its command FROM `07-frontend/Dockerfile` rather than retyping
    # it, because a gate that runs a SIMILAR command is the same bug wearing a
    # different hat — which is the entire content of this defect. Measured at
    # 44.5 s (tsc ~33 s, vite build 11.06 s); G4 and G5 already cost 94 s and
    # 134 s, so it is the third-most expensive gate and not the most.
    ("G54 image-build", g54_image_build),
    # ── G55 · A COMMIT SUBJECT THAT CLAIMS A FIX ────────────────────────────
    #
    # The third member of the G50/G51 family, on the one surface where a claim
    # is timestamped and immutable:
    #   G50 prose claims a defect was FILED  → the row must EXIST
    #   G51 code  claims a defect is CLOSED  → the row must not read `open`
    #   G55 a COMMIT SUBJECT claims a fix    → the row must not read `open`
    #
    # ⚠ THE BROADER CHECK — every open row named in a commit subject — WAS
    # MEASURED AND DELIBERATELY NOT MADE BLOCKING: 119 at the tip, and the
    # narrowing that suggests itself (`fixed_commit` empty) removes exactly ONE
    # of them, because an open row has no fixed_commit by construction. That
    # population is REPORTED instead — in this gate's own detail line, behind
    # `--report`, and in `10-scripts/defect_report.py`, which is where step 4
    # triages from. Decision log 2026-08-30, with all four numbers.
    ("G55 fix-claims", g55_commit_fix_claims),
    # ── G56 · THE RUNTIME RLS GUARD STAYS WIRED ─────────────────────────────
    #
    # Added 2026-08-31 from DEF-2717, with DEF-2760 beside it. Every bill-run
    # performance figure this repo published was measured on a connection that
    # BYPASSED row-level security, because the benchmark's role had been made
    # SUPERUSER to create a database — one command, for an unrelated reason.
    #
    # ⚠ G5 IS NOT THIS CHECK, AND THE DIFFERENCE IS THE WHOLE DEFECT. G5 proves
    # the POLICIES EXIST, asserting under a dedicated `sbh_rls_probe` role
    # precisely BECAUSE the app's own role may be a superuser. So it proves the
    # policies are right by using a role that is deliberately NOT the one the
    # application connects as, and nothing ever asked whether the RUNNING
    # APPLICATION is subject to them. Before this, `rolsuper`/`rolbypassrls`
    # appeared ZERO times in 06-backend/apps/, config/ and core/.
    #
    # No gate can open a production database, so the runtime answer comes from
    # 06-backend/core/rls_guard.py, which refuses to boot on a bypassing role
    # (fail-closed in base.py; tolerated only where local.py types it). THIS
    # gate is hard-won law 2 applied to that guard: it stays present, stays
    # wired into all three boot paths, and stays fatal by default. Seven
    # sabotages are re-run on every invocation and each must bite, so the gate
    # cannot quietly become a formality.
    ("G56 rls-runtime-guard", g56_rls_runtime_guard),
    # G57 — DEF-2761. G56 above asks whether the RUNNING APPLICATION is subject
    # to row-level security. This asks the question one layer down and it had
    # never been asked of anything: whether the TESTS are.
    #
    # `tests/test_us_ten_helpers.sqlite_guc` was an `autouse=True` fixture that
    # replaced `core.tenancy.connection` with a recording fake on EVERY vendor.
    # Through `from ... import *` it reached 447 collected modules / 6,575 cases,
    # in all of which `set_config('app.tenant_id', ...)` went to a Python list and
    # never reached PostgreSQL. Measured on live PostgreSQL 16.13: the kernel is
    # asked for a tenant, the ContextVar mirror agrees, and `current_setting`
    # returns the nil sentinel on the very next statement.
    #
    # NOTHING COULD SEE IT, AND THAT IS THE POINT OF ADDING A GATE RATHER THAN
    # A TEST. The default suite is sqlite (law 14), where the question is
    # meaningless; G5 is honest precisely because `live_tenant_context` swaps the
    # real connection BACK, so it proves the policies while saying nothing about
    # the 447 modules beside it; and while the app role was SUPERUSER the missing
    # marker had no observable consequence at all -- RLS bypassed, no policy
    # consulted, every run green over a claim nobody was testing.
    #
    # It flags the IMPLICIT forms only -- `autouse=True` fixtures and `setUp` --
    # because being invisible at the call site IS the mechanism. A recorder a
    # test asks for by name is allowed: `test_be01_tenancy.py`'s `db` fixture
    # asserts the STATEMENT TEXT (that the tenant id travels as a bind parameter
    # and is never interpolated), which is a claim about the kernel's own code,
    # holds on every vendor, and cannot be made against a real connection.
    ("G57 tenant-guc-not-faked", g57_tenant_guc_not_faked),
    # G58 — DEF-2734, and it is the THIRD layer of the question G56 and G57 ask.
    # G56 asks whether the RUNNING APPLICATION is on a role subject to RLS; G57
    # asks whether anything in the TEST FIXTURES stands in front of the kernel
    # that sets `app.tenant_id`; this one asks whether the RESPONSE is still
    # inside that context when it queries. A `StreamingHttpResponse` returns
    # with its body unconsumed, `TenantContextMiddleware` clears the marker in a
    # `finally` the moment the view returns, and WSGI iterates the body
    # afterwards — so the first query runs with no marker, RLS denies it in
    # silence, and the download succeeds with 200, a header row and NO ROWS. An
    # empty rejects file reads as "nothing was rejected".
    #
    # ⚠ TWO LANES WROTE THE IDENTICAL TRAP INDEPENDENTLY, a day apart, for two
    # different features — which is why it is a gate and not a review note.
    # Fifty-seven gates passed on it, and so did the two end-to-end tests of
    # those very routes: both assert on the CSV header, a constant yielded
    # before any query runs, so both were true over an empty file.
    ("G58 streamed-tenant-context", g58_streamed_tenant_context),
    # G59 — CR-051 task 29, and it is a gate rather than a review note because
    # what it guards is a RELATIONSHIP BETWEEN TWO FILES that neither file can
    # see from inside itself. Billing's named queue is routing (Python) plus a
    # consumer (`docker-compose.yml`), and either half alone is worse than
    # neither: routing with no consumer means a bill run is accepted, says
    # `queued`, and never runs; a consumer with no routing is an idle container
    # whose CPU limit bounds nothing. Both states pass every test in the repo.
    # It also holds the third half nobody remembers — the DEFAULT worker must
    # not drain `billing` too, or the split is cosmetic — and `celery-beat` at
    # exactly one replica, because the person who scales a worker is the person
    # who will scale the clock, and two clocks do not conflict: they both fire.
    ("G59 billing-queue-split", g59_billing_queue_split),
    # G60 — BR-CUS-674, the PO's ruling of 2026-08-31 closing OQ-1171:
    # *"(a) Ignore it — mailing only, our record unchanged - we cannot make
    # chnges until account confirm it"*. A mail house's NCOA lookup does not
    # only clean an address — it finds people who have MOVED and hands back
    # the new one — so the moment a print hand-over exists, a return file
    # arrives holding a fact we do not have, and writing it is the obvious
    # thing to do with it.
    #
    # It guards an ABSENCE, which is exactly the kind of guarantee that
    # stops being true without anybody editing the sentence claiming it
    # (hard-won law 1). Today nothing writes an address from a vendor's
    # answer: there is no inbound vendor path at all, `mark_returned` writes
    # `returned_at/returned_by/updated_at`, and the geocoder — the one third
    # party that DOES answer about an address — writes `lat`/`lng` only.
    # A deleted subject file is a FAILURE here and not a silent pass: "the
    # code that could break this is gone" and "I could not find it" look
    # identical to a check that skips, and only one of them is good news.
    ("G60 no-address-from-a-vendor-return", g60_no_address_from_a_vendor_return),
    # G61 — CR-052 task 19. G4 above runs the golden suite; this asks the
    # question running it TWICE was trying to ask and cannot: DID A SIGNED
    # FIGURE MOVE?
    #
    # `10-scripts/03-golden-verify.py` opens exactly one file and checks that it
    # is consistent WITH ITSELF, so a lane that edits an input and its result
    # together leaves it perfectly consistent. Measured 2026-08-31: GT-3's base
    # charge moved $30.50 -> $31.00 with its proration (15/30 x 31.00 = 15.50)
    # and the harness's WHOLE summary line came back byte-identical —
    # `33 PASS, 0 FAIL | ... | 12 PASS, 0 FAIL, 4 NOT-CHECKABLE |
    # self-test: 8/8 guards bite`. $30.50 is the empty-unit charge CLAUDE.md's
    # own CR-052 section quotes. A second mutation on GT-1's rate showed the
    # headline 33/33 is blind there too and only GT-10's CROSS-CHECK caught it,
    # which a GT without one does not have.
    #
    # CLAUDE.md says a signed figure changes by finance re-sign through
    # HUMAN-GUIDE §6, "never an inline edit", and nothing enforced those words.
    # G1 comes closest and disclaims it in its own docstring.
    #
    # It pins the FIGURES and not the file, so prose is free and a number is
    # not — a gate that fired on a typo fix is a gate somebody switches off, and
    # that half is proved on every run by a second self-sabotage.
    ("G61 frozen-figures", g61_frozen_figures),
    # G62 — the fourth member of the claims-about-a-register family (G50 prose,
    # G51 code, G55 a commit subject, G62 a CR task row). The Product Owner
    # asked for a status of CR-051..055 twice on 2026-08-31 and got two
    # different answers, because the record is derived from markers wrong in
    # BOTH directions.
    #
    # It deliberately does NOT ask "is this task done" — CR-051's own write-up
    # of the same day says why, and is right: "a gate that demanded a shipped
    # row for every task would be satisfied by writing the row, not by doing
    # the work." Prose claiming completion is its own evidence.
    #
    # A BLOCK is falsifiable, which is the whole idea: a row saying "BLOCKED ON
    # OQ-291" makes a claim about a DIFFERENT FILE. Measured before it was
    # built: 489 task rows, 2 claiming a block, and BOTH were stale — one of
    # them a signed rule (BR-RAT-960/961) built while its row still said it was
    # waiting on the PO, which is law 13's re-ask with the register as the
    # cause. Baselined at what is actually there (3) per the 2026-08-27 ruling
    # on why gates breach: "a baseline that may fall and never rise is a
    # ratchet; a baseline nobody can reach is decoration."
    ("G62 cr-task-blockers", g62_cr_task_blockers),
    # G63 (DEF-2791, 2026-09-01) — the fifth member of the same family, and the
    # one that reads a claim a file makes ABOUT ITSELF. Six guarded money files
    # told their reader, in the present tense, that no glob in human_owned.txt
    # matched them and that G7 therefore reported conform over them. Every one
    # was guarded, two of them since 2026-08-11.
    #
    # It is hard-won law 1 running BACKWARDS — not a comment claiming a
    # guarantee, but a comment claiming an ABSENCE that has stopped being true —
    # and the specific cost is law 13's: the sentence usually ends by asking for
    # a glob, which reads as a live instruction, so the next lane files a closed
    # finding or puts a settled question back to the PO.
    #
    # G7 walks the list forward and reads MARKERS; G53 asks the reverse question
    # and reads MARKERS. The claim lives in PROSE and both pass over it. Every
    # PO ruling that widens the watched list re-creates this for free, which is
    # why it is a gate and not the prose sweep DEF-2791 explicitly warns off.
    ("G63 guard-claims", g63_guard_claims_match_list),
    # G64 (DEF-2846, 2026-09-01) — the two golden numbers must be nameable
    # apart. `33/33` is quoted across this repo beside "GT-1..61 are the
    # billing-math contract", and a reader takes the pair as the ENGINE being
    # checked against 61 signed figures. It is not: the harness recomputes
    # B4/B5's own figures, imports no application code, and therefore cannot go
    # red when the engine drifts. What runs the engine is 06-backend/tests/
    # golden/ — 14 of the 61.
    #
    # The harness never claimed otherwise; its own docstring says "it is not the
    # rating engine". The CITATIONS lied, which is why this gate reads prose as
    # well as filenames. It touches 03-golden-verify.py in neither direction:
    # no priced arithmetic is anywhere near it.
    ("G64 golden-engine-coverage", g64_golden_engine_coverage),
    # G65 — DEF-2845. B1's ring structure was true BY HABIT: nothing anywhere
    # read which module an `apps/billing` file imports, so it degraded one
    # import at a time with no commit anybody could point at. G20 checks a seam
    # has an implementer and G27 checks a module is not invisible; neither asks
    # whether the seam was BYPASSED.
    #
    # The measurement is the argument for the gate rather than a detail of it:
    # the defect counted SEVEN in five files on 2026-08-31 and there are TEN in
    # eight files one day later. Baselined at what is actually there, as a
    # ratchet that may fall and never rise.
    ("G65 module-ring", g65_module_ring),
    # G66 — DEF-2795's own stated prevention, and the reason it is a GATE and
    # not a test is the reason DEF-2795 exists at all. DEF-2722's guard walks
    # ONE FILE (`apps/customers/sample_data.py`) and went red naming 25 sites
    # there; the same shape was sitting unseen in six more seeders — billing 8,
    # metering 5, payments 3, identity 2, assets 1, rating 1 — because nothing
    # looked at the directory.
    #
    # CLAUDE.md law 14 is the whole argument: on PostgreSQL a failed statement
    # aborts the WHOLE transaction, these blocks all run inside tenancy's
    # per-module `atomic()` (BR-TEN-063), and `config/settings/test.py`
    # hardcodes in-memory SQLite — which has no aborted-transaction state — so
    # the broken version passes the entire suite green on every machine. There
    # is no test that can catch this on the default suite, which is exactly
    # when a static gate earns its place.
    ("G66 seeder-savepoints", g66_seeder_savepoints),
    # G67 (DEF-2792, 2026-09-01) — the claims-about-a-register family again, and
    # the one that reads the register's own pointer BACK into the code. A fix's
    # write-up cited the WRONG defect id, so the row it fixed sat `open` for
    # twelve days: a lane grepping for DEF-340 found nothing in the one file the
    # register said to look in, and concluded the fix was never made.
    #
    # ⚠ IT IS NOT THE CHECK THAT DEFECT ASKED FOR, and the docstring says why
    # with the measurement. The forward direction — does a file's cited id have a
    # surface naming this file — is 97% mismatch even at its narrowest, because a
    # Trace header names the defect that MOTIVATED the file and that is almost
    # always somewhere else. A report at that ratio is read once and never again.
    # The mirror direction is 29% and is the shape of the defect itself.
    ("G67 fix-leaves-a-trace", g67_fix_leaves_a_trace),
    # G68 (DEF-2395, 2026-09-01) — the gate that asks whether this repo's OWN
    # PROOF STANDARD is reachable. Law 14 says transaction-sensitive code must
    # be proved on real PostgreSQL because `config/settings/test.py` hardcodes
    # in-memory SQLite; every such proof needs a seeded tenant; and on
    # 2026-09-01 three lanes found independently that provisioning produced no
    # owner, so the sample plant collapsed and there was no fixture to prove
    # anything on. Nothing could catch it — no gate asked whether a developer
    # can seed a tenant on the database the law names.
    #
    # ⚠ ITS SECOND HALF IS THE ONE THAT MATTERS: it reports SKIP, never PASS,
    # for a run that happened on SQLite. The underlying test passes there and
    # that is worth having, but calling it a pass would restate the exact
    # confusion the defect is about — a green suite implying coverage of the
    # aborted-transaction case it cannot reach.
    ("G68 plant-on-postgres", g68_plant_on_postgres),
    # G69 (DEF-3158, 2026-09-02) — B14 rule 31 has three enforcers and SEVEN
    # live breaches walked past all of them, because a TRUNCATED id is not
    # uuid-shaped. `01a00000` has no dashes, is eight characters, and reads like
    # a reference number; G28 inspects strings and this is a runtime
    # expression, and the two rendered checks that exist cover S30 and S15
    # alone. This is the mechanical source pattern DEF-3158's own prevention
    # column prescribes — `<expr>.<id-ish>.slice(` — at a ceiling of ZERO,
    # because all seven were fixed in the commit that added it and a baseline
    # file for an empty set is where a rule quietly stops being one.
    ("G69 id-slice-on-screen", g69_id_slice_on_screen),
    # G70 (DEF-2386 / CR-066 task D1, 2026-09-02) — a fee line resolves its GL
    # account from its CHARGE CODE and refuses the WHOLE bill when there is
    # none, while a usage or base line resolves from the service's designation
    # and never looks at a code. So a platform charge code shipped with no
    # mapping is not a missing line, it is every bill that carries that code,
    # refused at issue — and the sample estate issues 95 invoices anyway,
    # because every line it writes is usage or base. THAT is why nothing caught
    # it: no check in this repo compared the charge-code fixture against the GL
    # mapping. This is that comparison, plus the half a mapping table cannot
    # answer for itself — an account the map names and SEED_CHART does not
    # plant leaves the identical NULL column and reads like a correct row.
    ("G70 charge-code-gl-default", g70_charge_code_gl_default),
    # G71 — DEF-2377. The Product Owner read a summary row on the deployed audit
    # log that said "the named sample_data_runs rows this run stored
    # (BR-TEN-060)": our rule id and a database table name, in a sentence written
    # for a clerk. An audit payload is the one kind of server prose that IS a
    # screen — S61 renders it as words — and it was in none of G28's three
    # corpora: not a catalogue value, not one of the five modules on its
    # served-prose list, and expressly excluded from its raise-site sweep. This
    # reads every before=/after= payload with `ast` and asks G28's question of it.
    ("G71 audit-payload-prose", g71_audit_payload_prose),
    # G72 — DEF-3320. The seeding estate grew from seventeen blocks to eighteen
    # and FIVE sentences in `apps/tenancy/sample_data.py` went on saying
    # seventeen, including the one the sign-up screen narrates from. It survived
    # because every backend test asserts against `len(SAMPLE_MODULES)` — which
    # is the RIGHT way to write them and is exactly why none of them could see
    # it: a derived assertion can never disagree with the thing it derives from.
    # The gap is that nothing in this repo reads PROSE for truth, which is r11
    # step 0's own warning turned into a defect, and it is the same shape as
    # CLAUDE.md's services line (wrong three times) and B14's rule count (wrong
    # three times). This reads the length out of the source with `ast` and
    # compares it with every count sentence that claims it.
    ("G72 counted-prose", g72_counted_prose),
    # G73 — DEF-2368, and it is G72 one fixture along with a DECIMAL instead of
    # a count. CR-062's addendum appended two premises to the seeded estate, so
    # its storm-water assessment went from 54 ERU across 41 premises to 59
    # across 43 — $243.00 a month to $265.50 — and the two constants stating it
    # did not move, because the PLAN is derived and the totals were LITERALS.
    # The check that caught it already existed and worked: the D6 suite says in
    # its own docstring that the stated constant and the ratified ladder are two
    # independent statements of one figure. It took a day because running it
    # costs six minutes of PostgreSQL and a lane appending two premises had no
    # reason to. This makes the same comparison with no database and no Django,
    # in milliseconds, on every lane.
    ("G73 storm-water-estate", g73_storm_water_estate),
    ("G74 unread-tables", g74_tables_nobody_reads),
    # CR-069 wave A (2026-09-03) — the integrations substrate's three gates,
    # each proven RED on its own defect before it was trusted green (law 7):
    #   G75  the connection table may never hold a secret (US-INT-014 TC-3;
    #        CR-069 §13 gate 2's schema half) — RED with an EncryptedTextField
    #        added to IntegrationConnection;
    #   G76  every declared operation names its idempotency mode AND its
    #        completion mode (§13 gate 3) — RED with `completion` stripped
    #        from email_smtp's send operation;
    #   G77  nothing outside adapters/ and manifests/ branches on a provider
    #        key (§13 gate 1, US-INT-013 TC-5) — RED with `if provider_key ==
    #        "email_smtp"` written into services.py.
    ("G75 connection-table-no-secret", g75_connection_table_no_secret),
    ("G76 operation-modes", g76_operation_modes),
    ("G77 provider-key-branches", g77_provider_key_branches),
    # CR-068 wave A (2026-09-03) — the customer portal's two gates. G78–G79 were
    # reserved by the CR-069 wave B lane the same morning, so the plan's "G75"
    # and "G78" are these two numbers; the register is the authority.
    #   G81  the portal surface reaches exactly FOUR writes, declared as data in
    #        apps/portal/write_points.py (BR-CWP-001..003, CR-068 R12) — RED with
    #        a fifth `def` in services.py, RED with an ORM write in guest_api.py;
    #   G82  every portal route carries a CWP id CR-068 §9 allocates and no route
    #        invents one (§13) — RED with `CWP-999` written into the register.
    ("G81 portal-write-points", g81_portal_write_points),
    ("G82 cwp-screen-register", g82_cwp_screen_register),
    # G83 · CR-071 — a portal walkthrough MEASURES a response time, and no
    #        walkthrough prints "meets target" without the figure on the same
    #        line (11-response-times.md §5: reported, never rounded). RED three
    #        ways — the instrument deleted, the walkthrough's percentiles
    #        removed, and a bare verdict added — all quoted in its docstring.
    ("G83 measured-not-asserted", g83_measured_not_asserted),
    # CR-068 wave D (2026-09-04) — a draft never leaves the API, and the reason
    # is in the SQL. `published_content.GUEST_READS` names the functions a
    # visitor can reach and the keyword each query must carry; the third clause
    # is the load-bearing one — the portal's seam may call NOTHING ELSE from
    # that module, so `back_office_answers`, which holds all three states,
    # cannot be put on the guest surface by adding one convenient seam
    # function. RED on the real code twice before it was trusted (law 7): the
    # `status=` keyword removed from `published_answers`, and a seam function
    # returning the back-office list — both failures quoted in its docstring.
    # ⚠ It was `G84` until 2026-09-04 and so were two other gates: three lanes
    # read the folder, each correctly took the next free number, and each got
    # 84 (DEF-CWP-3731). This one landed last and renumbered.
    ("G88 published-gate-in-the-query", g88_published_gate_in_the_query),
    ("G85 one-address-home", g85_one_address_home),
    ("G87 declared-dependencies", g87_declared_dependencies),
    # B14 rule 36 (PO 2026-09-04): the two of its breaches that source text
    # can answer — a wireframe annotation style in a screen, and a button a
    # screen drew for itself where the kit's `Button` would serve.
    ("G86 house-style-controls", g86_house_style_controls),
    # DEF-CWP-3736 (2026-09-04) — a CSS custom property a component SETS and no
    # `var()` anywhere READS. The customer portal fetched the utility's own
    # colour, threaded it through three components, wrote it onto the frame as
    # `--brand` / `--accent`, and `--accent` was consumed by nothing at all:
    # hard-won law 2 one layer below the prop nothing passes. Every check here
    # was green because the tests assert the style attribute is PRESENT, which
    # it was. ⚠ It reads the MARKUP as well as the stylesheets, and that is
    # load-bearing rather than thorough: this product's styles moved into the
    # markup under Route B, `text-[var(--brand)]` is a real reader, and a
    # stylesheet-only scanner would have called a live property dead on its
    # first run. Proved RED on the shipped tree before it was trusted green.
    ("G90 dead-custom-properties", g90_dead_custom_properties),
    # CR-068 wave E (2026-09-04) — the two the plan called G76 and G77.
    # The NUMBERS are the register's at PUSH time, not the plan's: G76-G90
    # were all taken by the time these landed (DEF-CWP-3734).
    ("G91 portal-staff-separation", g91_portal_staff_separation),
    ("G92 guest-leaks-nothing", g92_guest_leaks_nothing),
    # CR-070 wave O (2026-09-04) — a build has ONE destination. The PO ruled the
    # connection detail one screen too many (*"you cannot have two differnt
    # screen - this is an integration problem"*); the screen is deleted and the
    # route is kept as a redirect so no bookmark breaks. **Nothing else in this
    # repo can see the destination coming back**: a link to `/connections/<id>`
    # type-checks, lints and satisfies every test that asserts a link exists,
    # and the only symptom is a person watching the address bar change twice
    # (law 6 — no gate reads rendered output). RED on the two shipped test
    # assertions that still named the retired path, and on a link put back on
    # purpose in `OrdersPage.tsx`, through THIS harness rather than through
    # `__main__` (DEF-GOV-3733). ⚠ It was written as G91 and renumbered twice on
    # the day it landed — a sibling lane had taken 91 and 92 while this one was
    # building (DEF-CWP-3734: three lanes, three correct computations, one
    # number). The number was re-read from the PINNED TIP at push time.
    ("G93 one-build-destination", g93_one_build_destination),
    ("G94 credential-three-exits", g94_credential_three_exits),
    # G95 · 2026-09-04 — a `Tests:` line names files that EXIST. Two lanes in
    # one day cited test files that had never been written (DEF-CWP-3743,
    # DEF-CWP-3766), and a citation to a test nobody wrote reads exactly like a
    # citation to one that passes. A RATCHET: 150 broken citations are parked in
    # `trace_tests_known_gaps.txt` and that file can only shrink — a new one fails
    # outright, and a parked one that starts resolving fails until its line is
    # deleted in the same diff.
    ("G95 trace-tests-exist", g95_trace_tests_exist),
    ("G96 portal-reads-name-the-tenant", g96_portal_reads_name_the_tenant),
    ("G97 routed-views-are-decorated", g97_routed_views_are_decorated),
    # ── G98 · THE LINTER RUNS, AND SOMETHING READS ITS EXIT CODE ────────────
    #
    # DEF-CUS-3935, and it is DEF-159 one language over: that row put `tsc`
    # into this suite on 2026-08-16 and the linter was never added, so for
    # three weeks the only thing reading eslint was a human who happened to
    # type it. On 2026-09-05 it was RED at the tip with TEN errors while
    # `tsc --noEmit`, `vitest` and `vite build` were all green — correctly:
    # an unused import is legal TypeScript, nothing imports a dead symbol, and
    # the bundler strips types without reading them.
    #
    # ⚠ TWO OF THE TEN WERE ASSERTIONS THAT HAD GONE MISSING, not dead code.
    # `centreStatusLine` was imported by a case NAMED *"the status line is
    # built from the server's FACTS"* that asserted the two INGREDIENTS and
    # never the sentence (DEF-CWP-3940). An unused symbol in a TEST file is
    # one of the cheapest signals available that a check was lost, and nothing
    # here was reading it.
    #
    # It takes its command from `07-frontend/package.json`'s `scripts.lint`
    # rather than retyping it — G54's rule. And it never shells out to
    # `npx eslint`: with nothing installed that fetches eslint 10 from the
    # registry, which cannot read this repo's `.eslintrc.cjs` and exits 2
    # having linted nothing, so the gate would be red everywhere for a reason
    # that has nothing to do with the code. Measured at 41 s over 743 files.
    ("G98 lint-clean", g98_lint_clean),
    # ── G99 · EVERY PORTAL ENDPOINT CARRIES THE CONNECTION BUDGET ──────────
    #
    # DEF-CWP-3931. `NFR-39` names the budget and the per-tenant rate as build
    # tasks, not aspirations. `guest_api.py` had them on 15 of 15 endpoints;
    # `api.py` had them on 8 of 62, and all eight of those are `AllowAny`. The
    # fifty-four AUTHENTICATED endpoints — home, bills, the balance, usage —
    # carried neither, which is the traffic `NFR-38` counts and the traffic
    # `guards.py`'s own docstring was written about.
    #
    # Forgetting was the DEFAULT, not an accident: `portal_admission` is a
    # per-view decorator and `api.py`'s stated convention is that a wave
    # appends `urlpatterns += [...]` at the end and copies the block above it.
    # An endpoint shipped without the budget is indistinguishable from one that
    # has it — nothing fails and nothing logs; the protection is just absent
    # under the load it exists for.
    #
    # It reads decorator lists with `ast`, never a grep: the four docstrings in
    # these files that EXPLAIN the guard would satisfy a text search, which is
    # the false positive G78's header warns about (DEF-741's shape).
    ("G99 portal-admission", g99_portal_admission),
    # G135 · DEF-RAT-6980 (2026-09-27) — a DECLARED slice of the backend suite
    # has been RUN, and its reds are read. 28 tests sat red in a money
    # neighbourhood for four days because a lane running ONE file sees green
    # and no workflow gates a merge (every one in .github/workflows/ is
    # .disabled). This reads a RECEIPT and runs nothing, so it costs a lane a
    # file read — the split prove_isolation.py already argues for, because a
    # gate that costs a quarter of an hour is a gate lanes stop running.
    # ⚠ Its PASS message prints how many test files are NOT in scope, beside
    # how many are: a declared blind spot with no number attached is
    # indistinguishable from an empty one (law 7's fifth shape).
    ("G135 backend-suite-receipt", g135_backend_suite_receipt),
    # G84 · CR-068 wave C — a portal file with a write allowance writes ONLY
    # the models `write_points.MODULE_WRITE_TABLES` names. G81 bounds WHICH
    # files may write; this bounds WHAT, because "may write something" is one
    # plausible line away from "may write anything" (CR-068 §13).
    ("G84 module-write-tables", g84_module_write_tables),
    # CR-070 wave A (2026-09-03) — the Work module's boundary gate (§12 gate 1,
    # US-WRK-005 TC-2..4): nothing under apps/work/ writes another module's
    # table, and a foreign models import is lawful only under seams/. RED on
    # the real services.py with `Asset.objects.filter(pk=…).update(status=
    # "retired")` and its import, before it was trusted (law 7).
    ("G78 work-writes-nothing-foreign", g78_work_writes_nothing_foreign),
    # DEF-CWP-3954 (2026-09-05) — every screen in the CWP register has
    # SOMETHING pointing at it. Twenty-six of the portal's fifty had nothing:
    # shipped, routed, tested, answering at their own address, and unreachable.
    # G13 asks whether a prop is passed; this asks whether a screen is opened,
    # which is the same question one level up and belonged to nobody. It also
    # refuses a portal `to=` with no leading slash — `usePortalPath`
    # concatenates, and four live links resolved to `/{tenant}/portalhelp-paying`.
    ("G100 every-screen-has-a-door", g100_every_screen_has_a_door),
    # CR-070 wave E (2026-09-05) — `BR-WRK-014` / §12 gate 3 / `US-WRK-019`
    # TC-6: every row the seeder plants in `work_order_templates` reaches a
    # screen. 24 starters sat in every tenant for eleven days with nothing
    # reading one of them, behind a page that said *not built yet*. G74 asks
    # whether a TABLE has a reader and cannot see this, because
    # `work_order_templates` has been read by `create_work_order` since long
    # before those rows existed. RED first on all four sabotages through this
    # same `run()` — the queryset excluding a service (TC-6's own), the
    # queryset narrowed by a filter, the screen dropping `listTemplates`, and
    # the seeder going back around `templates_svc`.
    ("G101 seeded-starters-have-a-reader", g101_seeded_starters_have_a_reader),
    ("G102 flows-raise-without-blocking", g102_flows_raise_without_blocking),
    # DEF-CWP-3925 · 3959 · 3962 · 3824 (2026-09-05) — a hold is a rule with a
    # CLOCK in it, and four rotted in one week: the front page's six shut
    # doors, *Something else* grey for 32 hours over a live screen, the bills
    # list holding *Pay* after Pay now shipped, and *New answer* disabled over
    # a served `create_answer`. G13 asks whether a prop is passed and G100
    # whether a screen is pointed at — G100 CREDITS A HELD CONTROL AS A
    # POINTER and says so itself. Nobody owned *is this refusal still true*.
    # Every hold now states its expiry as data in `portal/routing/holds.ts`;
    # this fails when a `screen` row's screen lands or an `endpoint` row's
    # symbol is served. RED first through this same `run()` on the real tree
    # (`settings.portalHelp.addHeld` over `create_answer`) and on six
    # in-memory cases, two of which — a key that appears only in a comment,
    # and a template whose INTERPOLATION is named `held` — found real flaws in
    # the gate before it was trusted.
    ("G103 holds-cannot-rot", g103_holds_cannot_rot),
    ("G104 one-declaration-per-component", g104_one_declaration_per_component),
    # G105 · DEF-CWP-3989 (audit row D14) — the portal's fifty screens against
    #        `08-screen-layouts.md`, which NOTHING in this repo read. Every
    #        other check that knows about a portal screen carries its own
    #        hardcoded list, so it goes stale the day the drawing moves; this
    #        one derives the whole expectation from the drawing at run time.
    #        A handful of landmarks, each a SHAPE a screen can fail while
    #        showing perfectly correct facts: T1 `CardGrid3`, T2 `Stepper`,
    #        T3 `TwoCol` (the rail), T4 `TwoEqual`, T5 `DataTable` (the shared
    #        list — toolbar, sorting, footer), plus any of those a screen's own
    #        heading names. `PageHead` is deliberately NOT here: it belongs to
    #        `pageHeadCensus.test.ts`, and two checks on one fact are two
    #        checks that can disagree. RED first through this same `run()`.
    ("G105 screen-matches-its-drawing", g105_screen_matches_its_drawing),
    # CR-069 wave B (2026-09-03) — the modal, the gate, the queue:
    #   G79  no URLconf mounts `POST /integrations/{key}/send` (BR-INT-008 —
    #        the module sends nothing itself) — RED with the route added;
    #   G80  the `integrations` queue has BOTH halves (routing in jobs.py, a
    #        `celery-integrations` consumer) and the default worker does not
    #        drain it — G59's clauses for the second named queue; RED with
    #        the worker's `-Q integrations` removed and with `-Q celery,
    #        integrations` on the default worker.
    ("G79 no-send-route", g79_no_send_route),
    ("G80 integrations-queue-split", g80_integrations_queue_split),
    # G84 · CR-069 wave C (US-INT-020) — `provider_error` is the one column
    #        where another utility's customer can arrive, quoted back at us by
    #        a mail server, and RLS cannot see inside a text column. One
    #        writer, and it scrubs. RED with the seam's `scrub()` removed
    #        (*"assigns provider_error without scrub()"*) and with a second
    #        writer added to `runners/deliver.py`.
    ("G89 provider-error-seam", g89_provider_error_seam),
    # G106 · DEF-GOV-4014 — `G17` requires an id to be DEFINED exactly once
    #        and has nothing to say about one that was NEVER defined, so a
    #        citation could point into empty space forever with every gate
    #        green. RED first through THIS runner on the real tree: 16
    #        phantoms in source, `DEF-CWP-3647` among them.
    ("G106 cited-ids-exist", g106_cited_ids_exist),
    # G107 · DEF-CWP-4004 — the portal wrote MIN-width variants in a theme that
    #        says in capitals it is DESKTOP-FIRST, so the directory carried two
    #        scales pointing in opposite directions under overlapping names.
    #        Nothing could see it and nothing was visibly wrong: BOTH forms
    #        compile, so `tsc`, eslint, every `toContain` and even
    #        `routeBUtilities.test.ts` — which asks the real Tailwind compiler
    #        whether a class is REAL — all pass, because the wrong-direction
    #        class IS a real class. G36 is the same rule for `@media` queries
    #        in STYLESHEETS and cannot open a `.tsx`, which is the whole gap.
    #        The portal is at zero and stays there; the sites elsewhere are
    #        recorded in a baseline that may only fall.
    ("G107 one-responsive-direction", g107_one_responsive_direction),
    # G108 · CR-069 wave F. TWO clauses, and the second is the one that fails
    #        on the state this branch was actually in on 2026-09-04: every
    #        adapter call goes through the timeout/cap/breaker guard, AND that
    #        guard has a caller at all. `runtime.py` shipped with 427 lines of
    #        correct policy, 297 lines of green tests and ZERO importers
    #        (DEF-INT-4015), because every test called it directly and nothing
    #        in this repo asks whether a Python module is reached. G13 is the
    #        built-is-not-wired gate and it reads React props.
    ("G108 provider-calls-are-guarded", g108_provider_calls_are_guarded),
    # G109 — CR-070 wave J, US-WRK-030. G59's shape for the queue the phone's
    # push rides. A named queue is two statements in two languages and either
    # alone is worse than neither: routing with no consumer means every push is
    # accepted, says `queued`, and never runs (DEF-320); a consumer with no
    # routing is an idle container whose CPU limit bounds nothing.
    #
    # ⚠ THE FAILURE IS QUIETER THAN BILLING'S, which is why it needs its own
    # gate rather than a line in G59. A bill run that never runs is noticed
    # within a day — nobody got a bill. A push that never fires is INVISIBLE:
    # the technician's phone still gets the job on its next ordinary sync,
    # because the sync is the delivery and the push is only the doorbell. The
    # product looks correct and merely feels slow, and nothing anywhere says so.
    ("G109 work-queue-split", g109_work_queue_split),
    # G110 — CR-070 §12 gate 2, US-WRK-043 TC-5. r10: *"A screen that greys a
    # list is a convenience; a server that refuses a completion with an
    # unticked mandatory safety row is the guarantee. Build both or you have
    # built neither."*
    #
    # The suite proves the refusal WORKS; this proves it still EXISTS, and the
    # two fail differently. A lane refactoring `submit_field_result` — for wave
    # L's sync, say — deletes the call and the suite goes red in a way that
    # reads as *fix the test*. This goes red in a way that reads as *you have
    # removed a safety rule*. It also checks the guard DELEGATES to
    # `checklist.safety_lock` rather than re-deriving the condition, because a
    # hand-rolled copy is where the phone and the server begin to disagree
    # about whether a job may proceed.
    ("G110 safety-gate-server-side", g110_safety_gate_server_side),
    ("G111 no-tax-no-finance-arrow-on-work", g111_no_tax_no_finance_arrow_on_work),
    # G113 — a commit that SAYS it fixed a defect, over a row that still reads
    # `open`. Written 2026-09-05 by the register-truth audit, because the open
    # count the Product Owner plans from was wrong in one direction only: the
    # portal's 67 open rows were 24 real ones, and `DEF-WRK-4027` — the migration
    # blocker that stopped every PostgreSQL build on this branch — was fixed at
    # 17:10 and still read `open` hours later. Closing the row that REPORTED a
    # fault is a second act, and only the first one feels like the work.
    # Deliberately narrow: it matches only ASSERTING forms and drops any clause a
    # conditional governs, because a draft that matched every fix-shaped word was
    # right 40% of the time and a merge gate that wrong gets switched off.
    ("G113 closure-drift", g113_closure_drift),
    ("G114 list-envelope", g114_list_envelope),
    # G112 — DEF-GOV-4044. The question no i18n check was asking: does a key
    # the code BUILDS name a family the catalogue HAS?
    #
    # G15 compares the eleven catalogues to each other, so a family missing
    # from ALL ELEVEN is parity-clean — which is how `work.tabs.crews` reached
    # a clerk on every Work screen (`DEF-WRK-4036`). G18 closes that for a
    # LITERAL key, but reads a COMPUTED key only as a prefix it uses to stop a
    # catalogue key being called dead; it never asks the mirror question, so
    # `` t(`work.order.tabs.${id}`) `` renders a dotted key into six tabs with
    # every gate green.
    #
    # ⚠ A SEPARATE GATE RATHER THAN A THIRD DIRECTION INSIDE G18, ON PURPOSE.
    # `DEF-WRK-4036`'s escape column is that G18 DID report its key and the
    # finding was invisible anyway — red for a long backlog, and a new entry
    # does not stand out in a count of 113. A finding added to a red gate is a
    # finding nobody can see. This one ships GREEN so its first new finding is
    # the only thing on its line.
    ("G112 computed-key-families", g112_computed_key_families),
    # G115 (CR-075 wave A task A6, 2026-09-06) — the Runbooks module's boundary,
    # enforced from its first commit exactly as G78 is for `work`. Runbooks owns
    # seven tables, reads nine other modules through one seam file each, and
    # writes none of them: every write is one of thirteen ports and not one has
    # a writer bound in phase 1. That is what makes a Check trustworthy — it is
    # CONSTRUCTED with no ports, so a write from one is a construction error and
    # not a runtime refusal.
    #
    # It is stricter than G78 in three places, each for a stated reason: no seam
    # write is sanctioned (here a write is a port); `seams/__init__.py` is NOT a
    # door, because a re-export there launders a foreign name into the whole
    # package with no file appearing to import it; and a dynamic import is
    # refused outside the doors and COUNTED inside them, because a declared
    # blind spot with no number attached is indistinguishable from an empty one
    # (G32 reported `0 unresolved` truthfully over 21 live refusals).
    #
    # It also asserts the PORT LIST: thirteen, and `raise_work_item` is not one
    # of them. The source says "four named calls" in seven places and names
    # raising a work item among them; the contract says thirteen and that
    # raising work items is an ENGINE act. A lane grepping for *port* finds the
    # wrong answer seven times out of eight, and building the four-call version
    # gives every Check a writer.
    ("G115 runbooks-import-census", g115_runbooks_import_census),
    # G116 — DEF-RBS-4335, and the same shape twice more the same day. A file's
    # `Tests:` line is how the next lane decides whether a change is already
    # guarded; three files named test files that had never been written, so the
    # line read "this is covered" and no case got written. 65 of 913 citations
    # pointed at nothing. Nothing else looks: trace_lint reads the header's
    # SHAPE, and a suite reports on the files it FINDS, so an absent one is
    # silence rather than a failure.
    ("G116 cited-tests-exist", g116_cited_tests_exist),
    # G117 — CR-075 wave I task I1. G59's shape for the FOURTH named queue, plus
    # one clause the other three do not need: a BEAT ENTRY. The other queues are
    # fed by a person pressing something; this one is fed by a clock, so it can
    # be correctly plumbed and receive nothing for ever while every screen goes
    # on drawing *Next run · 06:00*. ⚠ AND ITS FAILURE IS THE QUIETEST OF THE
    # FOUR: a scheduled Check that never runs leaves an EMPTY WORK LIST, which
    # looks exactly like a good morning. DEF-RBS-4353 is why it exists — the
    # execution plan recorded this task as done while the two job-kind strings
    # lived in three documents and no Python file.
    ("G117 runbooks-queue-split", g117_runbooks_queue_split),
    # G118 — DEF-CWP-4359, reported by the PO on the running product: *"we dont
    # have sign out in Customer portal"*. `POST portal/auth/sign-out` was
    # served, `portalClient.signOut()` was exported, and nothing under
    # `src/portal/` imported it, so a customer's session ended only when the
    # cookie expired and the next person at a shared machine got their bills.
    # This is `G13`'s question one shape over: G13 asks whether a component
    # PROP is ever supplied, and an exported FUNCTION is not a prop, so nothing
    # looked. `tsc` is content with an unimported export and eslint stops at
    # the module boundary. `G100` covers the other end of the same wire (every
    # screen has a door); this covers the wire.
    ("G118 client-calls-have-a-caller", g118_client_calls_have_a_caller),
    # G119 — DEF-RBS-4365. A second `def _person()` 1,250 lines below the
    # first in one file: Python binds the LAST one, silently, and each function
    # reads correctly at its own call site, so `GET /runbooks/{key}` answered 500
    # for every runbook the code had added rather than a person edited. Nothing
    # in this repo looks — ruff's set here does not carry it at module scope, the
    # trace gates read a header's SHAPE, and both suites pass because each
    # asserts its own layer. The only way to see it was to grep a file for its
    # own function names.
    ("G119 shadowed-definitions", g119_shadowed_definitions),
    # G120 — the 2026-09-07 outage. A runbook parameter refused at CONSTRUCTION,
    # so `django.setup()` itself died and a deployed build would not start. The
    # refusal was correct; what was wrong is that the symptom was thirty
    # unrelated red lines, which reads as a broken environment. This says the
    # one sentence a reader needs: the application will not start.
    ("G120 the-application-starts", g120_the_application_starts),
    # G121 — `CR-078`. A plan naming no late-fee charge code charges $0.00, by
    # PO ruling. That is correct AND it is silent: nothing raises, nothing logs,
    # and every test passes over a customer who was simply not charged. This
    # counts the plans in that state and refuses a re-introduced fallback to the
    # tenant's Billing defaults.
    ("G121 plans-name-their-late-fee-code", g121_plans_name_their_late_fee_code),
    # G122 — DEF-WRK-4518. `Work-008` asked fourteen `<uuid:order_id>` routes
    # for an order by its NUMBER, got fourteen 404s, and drew a dash for each,
    # so the screen looked finished and said nothing. The dash is not the bug —
    # a dash is right for a value that is genuinely absent; the bug is a dash
    # standing in for "we do not know". `tsc`, 75 component cases and 165 gates
    # were all green, because a screen that renders is a screen that passes, and
    # only opening the page could see it (law 6). This asks the general question
    # of every screen whose job is to display fields, and it found a second live
    # one on its first run (DEF-WRK-4637).
    ("G122 reads-that-failed-are-visible", g122_reads_that_failed_are_visible),
    # G124 — DEF-2596. The bill run's case filter declared FIFTEEN case kinds
    #        and the engine emits NINE, so six filters could never have a row
    #        behind them and a clerk could not tell "none this run" from "this
    #        can never happen". The two lists live in two LANGUAGES — a
    #        TypeScript constant and a Python tuple plus a constructor's string
    #        literals — and nothing in this repo had ever compared them.
    #        Every check was green and every one was right to be: `tsc` types a
    #        list of strings, and the unit tests assert the families partition
    #        the tabs, which they did — exactly, all fifteen of them.
    #        RED first through THIS runner on the real tree, naming all six
    #        (`overcharge, no_usage, owes, past_due, late_fee, extra_charge`).
    ("G124 case-chips-the-engine-raises", g124_case_chips_the_engine_raises),
    # G125 — DEF-BIL-5270 + DEF-BIL-5271, 2026-09-14. THREE CALLS, in three
    #        files five lanes edit, and deleting any one of them puts a money
    #        defect straight back with every unit test still green: the
    #        phase-4 gate (`authorise_release` → `refuse_stale_drafts`), the
    #        billed-through anchor (`_decisions_for` → `_continuity_decisions`)
    #        and the scoped re-price (`run_exception_resolve` →
    #        `reprice_accounts`). It is hard-won law 2 pointed at the exact
    #        shape `decisions.apply_decisions` sat in for five days — built,
    #        tested, correct, and called by nothing.
    #        RED first through THIS runner, three times, once per wiring.
    ("G125 decisions-reach-the-money", g125_decisions_reach_the_money),
    # G126 — DEF-INT-5568, 2026-09-17. FOUR reads over the six integrations
    #        tenant tables named neither a tenant nor a row already fetched
    #        under one, out of 78 chains; the access log a manager opens to
    #        see who has been reading their payment history was one of them,
    #        scoped only by a provider key every utility shares.
    #        RLS FORCE stops all four on a healthy PostgreSQL, which is
    #        exactly why nothing found them: the suite runs on SQLite, where
    #        that mechanism does not exist, so an unscoped integrations read
    #        passes every test in this repository (law 14 + law 7).
    #        `serve.py::_connection_for` had already written the rule down in
    #        its own docstring; a comment is not a guarantee (law 1).
    #        RED first through THIS runner, naming all four.
    ("G126 integration-reads-name-the-tenant", g126_integration_reads_name_the_tenant),
    # G127 (2026-09-17, `CR-111-BRC04`) — a partner's response SHAPE may re-key a
    # record and may never compute one. The module is built so the boundary is
    # structural; this is what keeps it structural, because the change that
    # breaks it is one `Callable` field added under pressure and it would pass
    # every test in this repository.
    ("G127 a-shape-cannot-compute", g127_a_shape_cannot_compute),
    # G128 (2026-09-17, `CR-115-BRC05` §6 lane 1) — an operation's address is
    #        decided in ONE file. There were SEVEN places on the day this
    #        landed and the brief named three; the four it did not name were
    #        found by looking, and one of them printed a dash on 9 of 91
    #        operations where the connection view printed an address. It is not
    #        a grep for a function name: an inlined copy has no name to grep
    #        for, and an inlined copy is how every one of the seven arose.
    #        RED first through THIS runner.
    ("G128 one-address-resolver", g128_one_address_resolver),
]


# ══════════════════════════════════════════════════════════════════════════
# CHANGE 1 — WHAT MOVED SINCE THE LAST RUN (PO-approved 2026-09-10)
# ══════════════════════════════════════════════════════════════════════════
# The PO did not understand the proposal until it was put in these words: *"the
# runner remembers last run's results and prints three lines at the top — 2
# newly failing, 1 newly fixed, 38 unchanged"*. That sentence is the spec.
#
# WHY IT IS NEEDED, IN THIS REPO'S OWN TERMS. The verdict line is binary and 40
# gates fail today, so EVERY run prints `MERGE BLOCKED` and every run has
# printed it for weeks. A number that never changes carries no information: a
# reader cannot tell a run that broke two gates from a run that broke none, and
# hard-won law 7's dominant 2026-09-05 shape is exactly that — *"a true red
# acquires the protective colouring of a known one"*, with `G78` red for three
# lanes and the message-kind guard red for days. This block is the smallest
# thing that restores the signal: not "is the suite green" (it is not) but
# "did YOUR work move anything".
#
# ⚠ AND THE THIRD CATEGORY IS THE ONE THAT IS ACTUALLY NEW. A gate red in both
# runs whose DETAIL grew is a new problem hiding inside an old failure — the
# shape that let two duplicate ids be added on top of an already-red `G17`,
# where the status column said FAIL before and FAIL after and nothing said the
# findings had grown from 1 to 3.
#
# ── WHY THE RECORD IS NOT COMMITTED ───────────────────────────────────────
# `last-run.json` is gitignored (`10-scripts/gates/.gitignore`, added with it).
# The choice was between two real costs and neither is free:
#
#   * COMMITTED: every lane's run rewrites every line of it, in a tree where
#     several lanes work at once. That is precisely hard-won law 11's
#     whole-file-write hazard — a pathspec commit naming it publishes whatever
#     another lane's run left there (mechanism five), and a re-derived blob
#     reverts a run a sibling recorded four minutes ago (mechanism two). The
#     register-shaped damage would be invisible inside a 123-line diff, and it
#     would happen on EVERY run rather than on every edit.
#   * NOT COMMITTED (chosen): the record cannot be compared across machines,
#     and a fresh container has none — the environment restores from a
#     session-start snapshot (law 12), so the first run of most sessions has
#     nothing to compare against.
#
# The second cost is real and is paid ONCE PER MACHINE, visibly: the first run
# prints, in as many words, that there is no record and that nothing is being
# compared. The first cost would be paid silently on every run by every lane.
# A comparison against a record another machine wrote would also be a lie of a
# worse kind — it would attribute a sibling's tree to your work.
#
# ⚠ THE RECORD IS A MEASUREMENT, NOT A BASELINE. It gates nothing, no gate
# reads it, and no verdict depends on it. Deleting it costs one run's
# comparison and nothing else, which is why it can be gitignored at all.
RECORD_PATH = Path(__file__).with_name("last-run.json")

#: Bumped when the shape below changes. A record written by another schema is
#: reported as unreadable rather than half-read — a partly-understood record
#: would compare some gates and silently skip others, which is the "reporting
#: zero over a scope it excludes" shape (law 7).
RECORD_SCHEMA = 1

REPO_ROOT = Path(__file__).resolve().parents[2]


# ══════════════════════════════════════════════════════════════════════════
# CHANGE 2 — CONDITIONAL RUNNING, THREE TIERS (PO-approved 2026-09-10)
# ══════════════════════════════════════════════════════════════════════════
# TIER 1 (`--tier1`)  — always, everywhere, in every mode. The cheap gates
#                       where the damage is IRREVERSIBLE or INVISIBLE later.
# TIER 2 (`--changed`)— tier 1 PLUS every gate whose declared surface the diff
#                       touches.
# TIER 3 (no flag)    — everything. The default, unchanged, and the only mode
#                       that produces a merge verdict.
#
# ⚠ NOTHING HERE CHANGES A GATE'S VERDICT. No baseline moves, no gate is made
# green, `CARRIED_NUMBER_SHARES` and every `*_baseline.txt` are untouched. The
# tiers decide WHICH gates run, never WHAT they decide.
#
# ⚠ AND THE ONE THING A SELECTIVE RUN MUST NEVER DO IS LOOK LIKE A FULL ONE.
# A selective run never prints `merge allowed`, prints the count of gates it
# did not run beside the result AND names every one of them, and says in words
# that it is not a merge verdict. A selective green that reads like a full
# green is the most dangerous thing this file could contain.

#: TIER 1 — the always-run set, chosen by reading what each gate does and
#: timing it (measured 2026-09-10, one gate at a time, whole set ≈ 13s against
#: a full run of tens of minutes). Two questions decided membership, and both
#: had to answer yes:
#:
#:   (1) IS IT CHEAP? Everything here ran in under 3 seconds. Nothing that
#:       boots Django, builds an image, runs pytest, npm or a browser is in
#:       this set at any price.
#:   (2) IS THE DAMAGE IRREVERSIBLE OR INVISIBLE UNTIL MUCH LATER? A duplicate
#:       id, a corrupted register, a ❄️ FROZEN figure that moved, a 🔒 file
#:       that never joined the guard list, a version that does not match its
#:       changelog — every one of these is cheap to prevent, expensive to undo,
#:       and reads as perfectly healthy in the meantime. Compare a lint error,
#:       which is loud, local and free to fix later.
#:
#: ⚠ THE FAMILY THIS SET CANNOT COVER, SAID PLAINLY BECAUSE A DECLARED BLIND
#: SPOT WITH NO NUMBER IS INDISTINGUISHABLE FROM AN EMPTY ONE (law 7):
#: **MIGRATION ORDERING HAS NO GATE IN THIS REPO — ZERO of the 123.** Nothing
#: loads the migration graph; `DEF-2872`'s conflicting-leaf failure is caught
#: by Django at test time and diagnosed by `10-scripts/diagnose_migration_drift.py`,
#: which is not a gate and is not run here. What tier 1 carries of that subject
#: is the migration-READING pair — `G7` (every 🔒 migration carries its
#: human-review marker) and `G16` (the partition DDL the migrations create) —
#: and that is all it carries. Do not read this set as covering migration
#: ordering; it does not, because nothing does.
TIER_1: tuple[str, ...] = (
    # ── ids and the registers that hold them: a duplicate or a dangling id is
    # not a broken build, it is a citation that silently resolves to the WRONG
    # REAL THING (`OQ-119` for `OQ-1190`, nine `G84` citations at the wrong
    # gate) and it gets copied onward before anyone notices.
    "G17 duplicate-ids",
    "G30 defect-register",
    "G46 register-vocabularies",
    "G106 cited-ids-exist",
    # ── claims against the registers. Each of these is a sentence somewhere
    # asserting something about a row; when it drifts, the register stops
    # being the place an answer lives (law 13) and three lanes get misled by a
    # body that contradicts its own status column (`DEF-WRK-4030`).
    "G50 filed-claims-resolve",
    "G51 closed-claims-match-register",
    "G55 fix-claims",
    "G62 cr-task-blockers",
    "G67 fix-leaves-a-trace",
    "G113 closure-drift",
    # ── signed law and the markers that protect it. A ❄️ FROZEN B4/B5 figure
    # that moves is a finance re-sign (HUMAN-GUIDE §6), not a fix; a 🔒 money
    # file that never joined `human_owned.txt` is reviewed by nobody and says
    # so nowhere. Four recorded occurrences before `G53` existed, every one
    # found by a person.
    "G61 frozen-figures",
    "G7 human-owned",
    "G53 guard-list-coverage",
    "G63 guard-claims",
    # ── the migration-reading pair (see the blind spot named above).
    "G16 partition-cov",
    # ── version and changelog. `12-governance/13-change-process.md` step 7
    # exists because this is *"many times not followed correctly"*, and two
    # lanes shipped `2.141.0` on the same afternoon (`DEF-GOV-3756`). 0.01s.
    "G35 version-lockstep",
    # ── corruption in the tree itself: a committed conflict marker. Scans
    # every tracked file in 0.9s and there is no version of "later" that is
    # cheaper than now.
    "G39 conflict-markers",
    # ── the suite's own wiring. `G42` asks whether each gate exposes both
    # entry points; `DEF-GOV-3733` is two gates announced green through
    # `__main__` while the suite reported `module has no attribute 'run'`.
    # A tier that runs when nothing else does must know its own gates run.
    "G42 gate-entrypoints",
)

#: ⚠ SURFACES ARE DELIBERATELY COARSE — TOP-LEVEL DIRECTORIES, NOT MODULES.
#: A surface that is too WIDE over-runs: some gates run for a diff they cannot
#: judge, which costs seconds. A surface that is too NARROW under-runs: a gate
#: that would have failed never runs, and the diff ships. Those two mistakes
#: are not symmetric, so this map is wide by construction. `06-backend/apps/rating`
#: would be a legal entry — matching is by path prefix — and is deliberately
#: not used: nobody has measured which files each gate really reads, and a
#: guess written as a declaration is hard-won law 1 (a comment claiming a
#: guarantee is not the guarantee).
#:
#: Derived by reading every gate for the paths it opens — `common.BACKEND_APPS`,
#: `FRONTEND_SRC`, `MODULE_DOCS`, `OQ_REGISTRY`, `code_files()`, and every
#: literal path in the file — then hand-corrected against what each gate's own
#: docstring says it checks.
#:
#: ⚠ A GATE MISSING FROM THIS MAP RUNS IN EVERY MODE, and the selection banner
#: prints how many did so. That is the fail-closed default (law 3: the unsafe
#: option must be the one you type) — a new gate that nobody remembered to
#: declare over-runs, it never silently stops running. The harsher option, a
#: `SystemExit` from `_assert_registry_sane`, was rejected: it would stop every
#: lane's suite over a missing one-line declaration, and the safe behaviour
#: costs nothing but seconds. A label that is in this map or in `TIER_1` and is
#: NOT a registered gate IS refused, because that one is a rename or a typo
#: silently removing a gate from a tier — an under-run, the direction that
#: matters.
SURFACE_ROOT = "<root>"
GATE_SUITE_DIR = "10-scripts/gates"

SURFACES: dict[str, tuple[str, ...]] = {
    "G1 packet": ("06-backend", "07-frontend", "04-docs"),
    "G2 code-trace": ("06-backend", "07-frontend", "04-docs"),
    "G3 checklist": ("06-backend", "07-frontend", "04-docs"),
    "G4 golden": ("06-backend", "10-scripts"),
    "G5 isolation": ("06-backend", "10-scripts", "12-governance"),
    "G6 forbidden": ("06-backend",),
    "G7 human-owned": ("06-backend", "12-governance"),
    "G8 stub-honesty": ("04-docs", "06-backend", "07-frontend", "12-governance"),
    "G9 error-envelope": ("06-backend",),
    "G10 tc-tests": ("06-backend", "07-frontend", "04-docs"),
    "G11 tag-stamp": ("06-backend", "07-frontend"),
    "G12 journeys": ("07-frontend", "08-qa", "10-scripts"),
    "G13 unwired-props": ("07-frontend",),
    "G14 prototype-conf": ("05-prototype", "07-frontend"),
    "G15 i18n-parity": ("07-frontend",),
    "G16 partition-cov": ("04-docs", "06-backend", "12-governance"),
    "G17 duplicate-ids": ("04-docs", "12-governance"),
    "G18 i18n-callsites": ("06-backend", "07-frontend", "12-governance"),
    "G19 env-hostnames": ("07-frontend", "12-governance"),
    "G20 seam-impl": ("06-backend",),
    "G21 refactor-contract": ("04-docs", "06-backend", "10-scripts"),
    "G22 picker-vocab": ("06-backend", "07-frontend"),
    "G23 surface-debt": ("06-backend", "07-frontend"),
    "G24 holiday-horizon": ("06-backend",),
    "G26 required-rows": ("06-backend",),
    "G27 engine-surface": ("06-backend",),
    "G25 screen-coverage": ("04-docs",),
    "G27 i18n-keys": ("07-frontend",),
    "G28 internal-refs": ("06-backend", "07-frontend"),
    "G29 screen-ids": ("04-docs", "05-prototype", "07-frontend"),
    "G30 defect-register": ("12-governance",),
    "G31 declared-classes": ("07-frontend",),
    "G134 route-b-utilities-compile": ("07-frontend",),
    "G32 refusal-keys": ("06-backend", "07-frontend"),
    "G33 refusal-copy": ("07-frontend",),
    "G129 premises/units copy caps": ("07-frontend",),
    "G130 newworld-card-fields": ("06-backend",),
    "G132 beat-entries-installed": ("06-backend",),
    # The deploy surface: both container scripts, the guard, the Makefile that
    # runs the release step locally, and the runbook that names the recovery.
    "G136 release-step-not-skippable": ("06-backend", "09-infra", "10-scripts",
                                        SURFACE_ROOT),
    "G34 type-scale-escape": ("07-frontend",),
    "G35 version-lockstep": ("06-backend", "07-frontend", SURFACE_ROOT),
    "G36 breakpoint-direction": ("07-frontend",),
    "G37 row-actions": ("07-frontend",),
    "G38 stated-absences": ("07-frontend",),
    # Every tracked file in the repo, so every surface there is.
    "G39 conflict-markers": ("04-docs", "05-prototype", "06-backend", "07-frontend",
                             "08-qa", "09-infra", "10-scripts", "12-governance",
                             SURFACE_ROOT),
    "G40 unmounted-components": ("07-frontend",),
    "G41 tenant-guc-form": ("06-backend",),
    "G42 gate-entrypoints": ("10-scripts",),
    "G43 list-toolbar-contract": ("07-frontend",),
    "G44 display-truth": ("07-frontend",),
    "G45 declared-filters-rendered": ("07-frontend",),
    "G46 register-vocabularies": ("12-governance",),
    "G47 service-catalog-parity": ("06-backend", "07-frontend"),
    "G48 import-money-posts": ("06-backend",),
    "G49 identifier-series-contract": ("06-backend", "07-frontend"),
    "G50 filed-claims-resolve": ("12-governance",),
    "G51 closed-claims-match-register": ("06-backend", "07-frontend", "10-scripts",
                                         "12-governance"),
    "G52 role-gated-doors": ("06-backend",),
    "G53 guard-list-coverage": ("06-backend", "12-governance"),
    "G54 image-build": ("06-backend", "07-frontend", SURFACE_ROOT),
    "G55 fix-claims": ("12-governance",),
    "G56 rls-runtime-guard": ("06-backend", "10-scripts", SURFACE_ROOT),
    "G57 tenant-guc-not-faked": ("06-backend",),
    "G58 streamed-tenant-context": ("06-backend",),
    "G59 billing-queue-split": ("06-backend",),
    "G60 no-address-from-a-vendor-return": ("04-docs", "06-backend"),
    "G61 frozen-figures": ("04-docs",),
    "G62 cr-task-blockers": ("12-governance",),
    "G63 guard-claims": ("06-backend", "10-scripts"),
    "G64 golden-engine-coverage": ("04-docs", "06-backend", SURFACE_ROOT),
    "G65 module-ring": ("06-backend",),
    "G66 seeder-savepoints": ("06-backend",),
    "G67 fix-leaves-a-trace": ("12-governance",),
    "G68 plant-on-postgres": ("06-backend",),
    "G69 id-slice-on-screen": ("07-frontend",),
    "G70 charge-code-gl-default": ("06-backend",),
    "G71 audit-payload-prose": ("06-backend",),
    "G72 counted-prose": ("06-backend", "07-frontend"),
    "G73 storm-water-estate": ("06-backend",),
    "G74 unread-tables": ("06-backend",),
    "G75 connection-table-no-secret": ("06-backend",),
    "G76 operation-modes": ("06-backend",),
    "G77 provider-key-branches": ("06-backend",),
    "G81 portal-write-points": ("06-backend",),
    "G82 cwp-screen-register": ("07-frontend", "12-governance"),
    "G83 measured-not-asserted": ("10-scripts",),
    "G88 published-gate-in-the-query": ("06-backend",),
    "G85 one-address-home": ("06-backend",),
    "G87 declared-dependencies": ("06-backend",),
    "G86 house-style-controls": ("07-frontend",),
    "G90 dead-custom-properties": ("07-frontend",),
    "G91 portal-staff-separation": ("06-backend",),
    "G92 guest-leaks-nothing": ("06-backend",),
    "G93 one-build-destination": ("07-frontend",),
    "G94 credential-three-exits": ("06-backend",),
    "G95 trace-tests-exist": ("06-backend", "07-frontend", "10-scripts"),
    "G96 portal-reads-name-the-tenant": ("06-backend",),
    "G97 routed-views-are-decorated": ("06-backend",),
    "G98 lint-clean": ("07-frontend",),
    "G99 portal-admission": ("06-backend",),
    "G84 module-write-tables": ("06-backend",),
    "G78 work-writes-nothing-foreign": ("06-backend",),
    "G100 every-screen-has-a-door": ("06-backend", "07-frontend"),
    "G101 seeded-starters-have-a-reader": ("06-backend", "07-frontend"),
    "G102 flows-raise-without-blocking": ("06-backend",),
    "G103 holds-cannot-rot": ("06-backend", "07-frontend"),
    "G104 one-declaration-per-component": ("07-frontend",),
    "G105 screen-matches-its-drawing": ("04-docs", "07-frontend"),
    "G79 no-send-route": ("06-backend",),
    "G80 integrations-queue-split": ("06-backend",),
    "G89 provider-error-seam": ("06-backend",),
    "G106 cited-ids-exist": ("06-backend", "07-frontend", "12-governance"),
    "G107 one-responsive-direction": ("07-frontend",),
    "G108 provider-calls-are-guarded": ("06-backend",),
    "G109 work-queue-split": ("06-backend",),
    "G110 safety-gate-server-side": ("06-backend",),
    "G111 no-tax-no-finance-arrow-on-work": ("06-backend", "07-frontend"),
    "G113 closure-drift": ("12-governance",),
    "G114 list-envelope": ("07-frontend",),
    "G112 computed-key-families": ("07-frontend", "12-governance"),
    "G115 runbooks-import-census": ("04-docs", "06-backend"),
    "G116 cited-tests-exist": ("06-backend", "07-frontend", "10-scripts"),
    "G117 runbooks-queue-split": ("06-backend",),
    "G118 client-calls-have-a-caller": ("07-frontend",),
    "G119 shadowed-definitions": ("06-backend",),
    "G120 the-application-starts": ("06-backend",),
    "G121 plans-name-their-late-fee-code": ("06-backend",),
    "G122 reads-that-failed-are-visible": ("07-frontend",),
}


# ── plumbing shared by both changes ────────────────────────────────────────


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:  # pragma: no cover - only if the file moves out of the repo
        return str(path)


def _clip(text: str, width: int = 96) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _wrap_names(names, indent: str = "    ", width: int = 96) -> list[str]:
    """One or more indented lines listing every name — never a truncated list.

    A count with no names tells a reader a number; the names tell them whether
    the number is the one they expected. Both are printed, always.
    """
    lines: list[str] = []
    current = ""
    for i, name in enumerate(names):
        piece = name + ("," if i < len(names) - 1 else "")
        if not current:
            current = indent + piece
        elif len(current) + 1 + len(piece) <= width:
            current = f"{current} {piece}"
        else:
            lines.append(current)
            current = indent + piece
    if current:
        lines.append(current)
    return lines


def _git(*args: str, timeout: int = 60) -> tuple[bool, str]:
    """(ok, output). Never raises: a missing or unhappy git makes a selective run
    fall back to running EVERYTHING, which is the safe direction."""
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, repr(exc)
    if done.returncode != 0:
        return False, (done.stderr or done.stdout).strip() or f"git {' '.join(args)} exited {done.returncode}"
    return True, done.stdout


def _now_utc() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _head_state() -> dict[str, object]:
    ok, out = _git("rev-parse", "HEAD")
    commit = out.strip()[:12] if ok else None
    ok_dirty, dirty_out = _git("status", "--porcelain")
    return {
        "commit": commit,
        # `None` where git could not answer — an unknown is written as unknown
        # rather than as `false`, which would read as "the tree was clean".
        "dirty": bool(dirty_out.strip()) if ok_dirty else None,
    }


# ── CHANGE 1: the record, and the comparison ───────────────────────────────


def _load_record() -> tuple[dict | None, str | None]:
    """(record, why_there_is_none). Exactly one of the two is None.

    Every failure to read is REPORTED, never swallowed. A record silently
    treated as empty prints "0 newly failing" over a comparison that did not
    happen — the false-pass shape this repo names most often.
    """
    if not RECORD_PATH.exists():
        return None, f"{_rel(RECORD_PATH)} does not exist"
    try:
        raw = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{_rel(RECORD_PATH)} could not be read ({exc!r})"
    if not isinstance(raw, dict) or not isinstance(raw.get("gates"), dict):
        return None, f"{_rel(RECORD_PATH)} is not a run record this runner understands"
    if raw.get("schema") != RECORD_SCHEMA:
        return None, (
            f"{_rel(RECORD_PATH)} was written under schema {raw.get('schema')!r} and this "
            f"runner reads schema {RECORD_SCHEMA} — half-reading it would compare some gates "
            "and silently skip the rest"
        )
    return raw, None


def _save_record(previous: dict | None, rows: list[tuple[str, str, str]], mode: str) -> str | None:
    """Merge this run's rows into the record. Returns an error sentence, or None.

    ⚠ MERGE, NOT REPLACE. A selective run updates only the gates it ran and
    leaves every other gate's entry — and its own timestamp — exactly as it
    was, so the next full run still compares each gate against the last time
    THAT GATE actually ran. Replacing would make a `--tier1` run erase 105
    gates' history and the next full run would report them all as new.
    """
    stamp = _now_utc()
    head = _head_state()
    gates = dict(previous.get("gates", {})) if previous else {}
    for name, status, detail in rows:
        gates[name] = {
            "status": status,
            "detail": detail,
            "at": stamp,
            "mode": mode,
            "commit": head["commit"],
        }
    payload = {
        "schema": RECORD_SCHEMA,
        "written_at_utc": stamp,
        "last_mode": mode,
        "head": head,
        "gates": gates,
    }
    tmp = RECORD_PATH.with_suffix(".json.tmp")
    try:
        # Build it whole, then replace — never truncate the destination before
        # the bytes exist (hard-won law 11, the repair that emptied CLAUDE.md).
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(RECORD_PATH)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return f"could not write {_rel(RECORD_PATH)} ({exc!r})"
    return None


def _compare(previous: dict, rows: list[tuple[str, str, str]]) -> dict[str, list]:
    """Bucket the gates that RAN against what the record says they did last time.

    Buckets are exhaustive and disjoint, and the caller prints the arithmetic —
    a category list whose numbers do not add up to the gates that ran is a
    category list hiding something.
    """
    prev = previous.get("gates", {})
    out: dict[str, list] = {
        "newly_failing": [],
        "newly_fixed": [],
        "detail_changed": [],
        "stopped_checking": [],
        "other_change": [],
        "not_recorded": [],
        "unchanged": [],
    }
    for name, status, detail in rows:
        was = prev.get(name)
        if not isinstance(was, dict) or "status" not in was:
            out["not_recorded"].append((name, status, detail))
            continue
        old_status, old_detail = was.get("status"), was.get("detail", "")
        if old_status != "FAIL" and status == "FAIL":
            out["newly_failing"].append((name, old_status, detail))
        elif old_status == "FAIL" and status == "PASS":
            out["newly_fixed"].append((name, old_detail, detail))
        elif old_status == "FAIL" and status == "SKIP":
            # NOT a fix. A gate that stopped checking looks like a gate that
            # started passing to anything counting green lines.
            out["stopped_checking"].append((name, old_detail, detail))
        elif old_status == "FAIL" and status == "FAIL" and old_detail != detail:
            out["detail_changed"].append((name, old_detail, detail))
        elif old_status != status:
            out["other_change"].append((name, old_status, status))
        else:
            out["unchanged"].append((name, status, detail))
    return out


def _render_change_block(
    previous: dict | None, why_none: str | None, rows: list[tuple[str, str, str]], ran_of_total: str
) -> tuple[list[str], str]:
    bar = "─" * 74
    lines = [f"── since the last recorded run {bar[:44]}"]
    if previous is None:
        lines += [
            f"NO PREVIOUS RUN IS RECORDED — {why_none}.",
            "",
            "Nothing is being compared. This is NOT '0 newly failing': it is 'there is no",
            "basis for that number'. Reporting zero here when there is nothing to compare",
            "against is the false pass this repo names most often, so it is not reported.",
            "This run writes the record; the next run on this machine will compare against it.",
            "",
        ]
        return lines, (
            "since the last recorded run: NOTHING TO COMPARE — no record existed before this "
            "run, so no count of newly-failing gates is printed."
        )

    buckets = _compare(previous, rows)
    n = {k: len(v) for k, v in buckets.items()}
    stamp = previous.get("written_at_utc", "unknown time")
    head = previous.get("head") or {}
    commit = head.get("commit") or "unknown commit"
    dirty = head.get("dirty")
    dirty_txt = "dirty tree" if dirty else ("clean tree" if dirty is False else "tree state unknown")
    lines.append(
        f"record: {_rel(RECORD_PATH)}, written {stamp} (mode={previous.get('last_mode', '?')}, "
        f"at {commit}, {dirty_txt}, {len(previous.get('gates', {}))} gate(s) held)"
    )
    lines.append(f"compared: {ran_of_total}")
    lines.append("")

    def block(label: str, key: str, describe=None) -> None:
        items = buckets[key]
        lines.append(f"  {len(items):>3} {label}")
        if not items:
            return
        for name, a, b in items:
            lines.append(f"      {name}")
            if describe:
                lines.extend(f"        {ln}" for ln in describe(a, b))

    block("NEWLY FAILING", "newly_failing", lambda old, new: [f"was {old}, now FAIL: {_clip(new)}"])
    block("NEWLY FIXED", "newly_fixed", lambda old, new: [f"was FAIL: {_clip(old)}"])
    def _detail_pair(old: str, new: str) -> list[str]:
        # ⚠ THE COMPARISON IS ON THE FULL STRINGS; ONLY THE EXCERPT IS CLIPPED.
        # Two excerpts that read identically over a line saying the detail
        # CHANGED is a check whose output cannot distinguish pass from fail to
        # a reader (DEF-182), so when the clip hides the difference the runner
        # says where the difference actually is.
        was, now = _clip(old), _clip(new)
        pair = [f"was: {was}", f"now: {now}"]
        if was == now:
            pair.append(
                f"⚠ the two excerpts above are identical — the difference is PAST the "
                f"{len(was)}-character excerpt (full detail was {len(old)} chars, now "
                f"{len(new)}). The comparison itself is on the full detail."
            )
        return pair

    block(
        "FAILURE DETAIL CHANGED (red before and now — the findings moved)",
        "detail_changed",
        _detail_pair,
    )
    block(
        "STOPPED BEING CHECKED (FAIL -> SKIP — not a fix)",
        "stopped_checking",
        lambda old, new: [f"was FAIL: {_clip(old)}", f"now SKIP: {_clip(new)}"],
    )
    block("OTHER STATUS CHANGE", "other_change", lambda old, new: [f"{old} -> {new}"])
    block(
        "NOT PREVIOUSLY RECORDED (new gate, renamed label, or first run of this gate)",
        "not_recorded",
        lambda status, detail: [f"{status}: {_clip(detail)}"],
    )
    lines.append(f"  {n['unchanged']:>3} unchanged")
    total = sum(n.values())
    lines.append(
        f"      {n['newly_failing']} + {n['newly_fixed']} + {n['detail_changed']} + "
        f"{n['stopped_checking']} + {n['other_change']} + {n['not_recorded']} + "
        f"{n['unchanged']} = {total} gate(s) run this run"
    )
    lines.append("")
    tail = ""
    if n["not_recorded"]:
        tail = f", {n['not_recorded']} not previously recorded"
    recap = (
        f"since the last recorded run ({stamp}, repeated from the top of this output): "
        f"{n['newly_failing']} newly failing, {n['newly_fixed']} newly fixed, "
        f"{n['detail_changed']} still red with different findings, "
        f"{n['unchanged']} unchanged" + tail
    )
    return lines, recap


# ── CHANGE 2: which gates run ──────────────────────────────────────────────


def _default_base() -> tuple[str | None, str]:
    """The ref a `--changed` diff is taken against when none is given."""
    ok, out = _git("rev-parse", "--abbrev-ref", "HEAD")
    branch = out.strip() if ok else ""
    candidates = [f"origin/{branch}"] if branch and branch != "HEAD" else []
    candidates += ["origin/HEAD", "origin/main"]
    for cand in candidates:
        ok_ref, _ = _git("rev-parse", "--verify", "--quiet", cand)
        if ok_ref:
            return cand, f"default base {cand}"
    return None, (
        "no default base could be resolved (tried "
        + ", ".join(candidates)
        + ") — git knows of no upstream for this branch"
    )


def _changed_paths(base: str) -> tuple[set[str] | None, str]:
    """Every repo-relative path that differs from `base`, INCLUDING uncommitted
    and untracked work.

    ⚠ `git diff --name-only <base>` compares the WORKING TREE to base, so in
    this shared tree it also picks up other lanes' in-flight edits. That is
    deliberate: over-inclusive selects too many gates (seconds), under-inclusive
    skips a gate that would have failed (a shipped defect).
    """
    ok, out = _git("diff", "--name-only", base, "--")
    if not ok:
        return None, f"`git diff --name-only {base}` failed: {_clip(out)}"
    paths = {line.strip() for line in out.splitlines() if line.strip()}
    ok_new, out_new = _git("ls-files", "--others", "--exclude-standard")
    if not ok_new:
        return None, f"`git ls-files --others` failed: {_clip(out_new)}"
    paths |= {line.strip() for line in out_new.splitlines() if line.strip()}
    return paths, f"{len(paths)} changed path(s) against {base}"


def _surface_touched(surface: str, paths: set[str]) -> bool:
    if surface == SURFACE_ROOT:
        return any("/" not in p for p in paths)
    prefix = surface.rstrip("/") + "/"
    return any(p == surface or p.startswith(prefix) for p in paths)


def _select(mode: str, base: str | None) -> tuple[set[str], list[str]]:
    """(labels to run, banner lines saying exactly why).

    Every path out of here that cannot answer the question with confidence
    returns EVERY gate and says so. Hard-won law 3: the unsafe option must be
    the one you type.
    """
    every = {name for name, _ in GATES}
    tier1 = set(TIER_1)
    undeclared = sorted(every - set(SURFACES))
    if mode == "full":
        return every, [f"mode: full (tier 3) — all {len(every)} gate(s), the merge verdict"]

    if mode == "tier1":
        banner = [
            f"mode: --tier1 — the {len(tier1)} always-run gate(s): cheap, and the damage they "
            "catch is irreversible or invisible later",
        ]
        return tier1, banner

    # mode == "changed"
    banner = []
    if base is None:
        base, why = _default_base()
        banner.append(f"mode: --changed — {why}")
        if base is None:
            banner.append(
                "  ⚠ NO DIFF COULD BE TAKEN, so NOTHING is being skipped: running all "
                f"{len(every)} gate(s). A selective run that cannot see the diff must not "
                "select."
            )
            return every, banner
    else:
        banner.append(f"mode: --changed — base {base} (given)")

    paths, why = _changed_paths(base)
    if paths is None:
        banner.append(
            f"  ⚠ {why} — so NOTHING is being skipped: running all {len(every)} gate(s)."
        )
        return every, banner
    banner.append(f"  {why} (working tree vs base, untracked files included)")

    suite_touched = sorted(p for p in paths if p.startswith(GATE_SUITE_DIR + "/"))
    if suite_touched:
        banner.append(
            f"  ⚠ the diff touches the gate suite itself ({len(suite_touched)} file(s), e.g. "
            f"{suite_touched[0]}) — a gate's code or its baseline decides what that gate "
            f"accepts, so ALL {len(every)} gate(s) run. Nothing is skipped."
        )
        return every, banner

    if not paths:
        banner.append(
            f"  the diff is EMPTY — no gate is selected by surface, so tier 1 ({len(tier1)}) "
            "runs anyway. A run that runs nothing is not a green run."
        )
        return tier1, banner

    touched = sorted({p.split("/")[0] if "/" in p else SURFACE_ROOT for p in paths})
    by_surface = {
        name
        for name, _ in GATES
        if any(_surface_touched(s, paths) for s in SURFACES.get(name, ()))
    }
    selected = tier1 | by_surface | set(undeclared)
    banner.append(f"  surface(s) touched: {', '.join(touched)}")
    # ⚠ A TOUCHED SURFACE NO GATE CLAIMS SELECTS NOTHING, AND THE READER MUST BE
    # TOLD WHICH — a count of gates not run says how much was skipped, and this
    # says which part of THEIR OWN DIFF nothing in the suite is looking at. A
    # declared blind spot with no name attached is indistinguishable from an
    # empty one (law 7, `G32` reporting a truthful 0 over 21 live refusals).
    unclaimed = []
    for surface in touched:
        here = {p for p in paths if (p.split("/")[0] if "/" in p else SURFACE_ROOT) == surface}
        if not any(_surface_touched(s, here) for names in SURFACES.values() for s in names):
            unclaimed.append(surface)
    if unclaimed:
        banner.append(
            f"  ⚠ {len(unclaimed)} touched surface(s) are declared by NO gate, so nothing was "
            f"selected for them BY SURFACE: {', '.join(unclaimed)}. Tier 1 ran as always — and a "
            "tier-1 gate that scans the whole tree still sees them — but no gate in this run is "
            "AIMED at those paths."
        )
    banner.append(
        f"  selected {len(selected)} of {len(every)}: {len(tier1)} tier-1 (always) + "
        f"{len(by_surface)} by surface (overlap {len(tier1 & by_surface)})"
        + (
            f" + {len(undeclared)} that declare NO surface and therefore always run "
            f"({', '.join(undeclared)})"
            if undeclared
            else " + 0 undeclared"
        )
    )
    return selected, banner


def _parse_args(argv: list[str]) -> tuple[str, str | None, bool, str | None]:
    """(mode, base, wave_close, error). Unknown flags are REFUSED.

    A mistyped `--chnaged` that is silently ignored runs the full suite, which
    is safe — but a mistyped `--tier1` would too, and a reader who believes the
    flag took effect learns nothing true from the output. Refusing is one line
    and removes the guessing.
    """
    mode, base, wave_close = "full", None, False
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--wave-close":
            wave_close = True
        elif arg == "--tier1":
            if mode != "full":
                return mode, base, wave_close, "run_gates: --tier1 and --changed are two modes; pick one."
            mode = "tier1"
        elif arg == "--changed" or arg.startswith("--changed="):
            if mode != "full":
                return mode, base, wave_close, "run_gates: --tier1 and --changed are two modes; pick one."
            mode = "changed"
            if arg.startswith("--changed="):
                base = arg.split("=", 1)[1] or None
            elif rest and not rest[0].startswith("-"):
                base = rest.pop(0)
        elif arg in ("-h", "--help"):
            return mode, base, wave_close, __doc__
        else:
            return mode, base, wave_close, (
                f"run_gates: unknown argument {arg!r}. Usage: run_gates.py "
                "[--wave-close] [--tier1 | --changed [<base>]]"
            )
    return mode, base, wave_close, None


def _assert_registry_sane() -> None:
    """Refuse to run at all if the registry above is inconsistent with itself or
    with the directory it lives in.

    FIVE FAILURES, ALL OF WHICH HAVE ALREADY HAPPENED HERE:

    1. **A gate module exists and no row runs it.** `g27_translation_keys.py`
       and `g26_defect_register.py` were each written, proved RED, committed,
       and left out of GATES — one of them by the lane fixing a law-2 defect.
       Nothing anywhere said so: the suite printed a healthy PASS count over a
       check that was not in it. Counting files against rows is the only thing
       that can see this, which is why it is done here and not in prose.
    2. **Two rows share a label.** The label is what a reader of the results
       table matches a failure to; two `G27` rows are two lines a human cannot
       tell apart. ⚠ **THE SECOND HALF OF THIS CLAUSE — *duplicate FILE
       numbers are deliberately tolerated* — IS SUPERSEDED (2026-09-04,
       `DEF-GOV-3654` / `DEF-CWP-3734`); see check 5.** It rested on readers
       disambiguating by LABEL, and measurement showed they disambiguate by
       NUMBER. What survives of it is that no FILE is renamed to satisfy a
       check — only the number a row claims.
    3. **A row names a module twice**, which silently runs one check as two and
       inflates the PASS count.
    5. **Two rows claim the same G-NUMBER** (`DEF-GOV-3654` /
       `DEF-CWP-3734`, 2026-09-04). Three lanes took `G84` in one afternoon.
       The number — not the label — is how this repo cites a gate, and **9 of
       the 39 bare `G84` citations already pointed at the WRONG GATE**. See
       `NUMBER_COLLISION_FROZEN` above and check 5 below.
    4. **A registered module has no callable `run`** (`DEF-GOV-3733`,
       2026-09-04). `G85` and `G87` both exposed only `main()` and `__main__`,
       so `python3 g85_one_address_home.py` printed PASS while the suite
       reported `gate crashed: AttributeError: module has no attribute 'run'`
       — twice, among 28 other failures, where a new one is easy to miss. Both
       gates were ANNOUNCED GREEN on a proof that exercised the path a person
       uses by hand and never the path the suite uses. Hard-won law 7 says
       prove a guard RED before trusting it green; this is its other half —
       **prove it in the harness that will run it** — and this check is that
       half made mechanical, one `callable()` per row, before anything runs.


    Deliberate exclusions belong in `GATE_NOT_A_GATE` with a reason, so that an
    excluded file is a decision someone wrote down rather than an omission
    nobody noticed.
    """
    labels = [name for name, _ in GATES]
    dupes = sorted({n for n in labels if labels.count(n) > 1})
    if dupes:
        raise SystemExit(
            f"run_gates registry: duplicate gate label(s) {dupes} — the label is how a reader "
            "matches a failure to a gate, so it must be unique. Rename one. (The NUMBER must "
            "be unique too, and is checked separately below.)"
        )
    # `DEF-GOV-3654` / `DEF-CWP-3734` — two rows may not claim the same
    # G-NUMBER. Checked here with the other four, before anything runs.
    #
    # ⚠ THIS DELIBERATELY RETIRES THE TOLERANCE CHECK 2 ABOVE DESCRIBES, and
    # the reasoning is in `12-governance/02-decision-log.md` (2026-09-04) so a
    # later lane does not read it as an oversight. The tolerance was not a
    # shrug: a gate FILE NAME is a cited identifier — the `G27` pair is cited
    # from `DEF-307` and `CR-016`, `g26_defect_register` from `DEF-300` — so
    # renaming one rewrites history, and the LABEL was held to be what a reader
    # disambiguates by. The first half of that is still true and is still
    # honoured: no file is renamed to satisfy this check.
    #
    # The second half was MEASURED on 2026-09-04 and did not hold. This repo
    # cites a gate by its BARE NUMBER almost exclusively — `CLAUDE.md` carries
    # eight bare-number gate citations and none by label; `G84` appeared 39
    # times across 18 files and `G27` 259 times across 66. **Nine of those 39
    # already pointed at the WRONG GATE** (`BR-CWP-094` and `Chip.tsx` among
    # them) because `G84` resolved to two real gates and nothing could tell
    # them apart — the `OQ-119` failure one register over, where a citation
    # does not dangle but silently resolves to a different, real thing.
    #
    # `NUMBER_COLLISION_FROZEN` is a RATCHET, not an allow-list: a new
    # collision fails the suite and cannot be waved through by appending, and
    # the second clause below deletes an entry the moment it stops colliding,
    # so the freeze can only ever shrink.
    numbers: dict[str, list[str]] = {}
    for name, _ in GATES:
        numbers.setdefault(name.split()[0], []).append(name)
    collided = sorted(
        num
        for num, rows in numbers.items()
        if len(rows) > 1 and num not in NUMBER_COLLISION_FROZEN
    )
    if collided:
        detail = "; ".join(f"{n} = {numbers[n]}" for n in collided)
        raise SystemExit(
            f"run_gates registry: gate number(s) {collided} claimed by more than one row "
            f"({detail}). The NUMBER is how this repo cites a gate — CLAUDE.md, the business "
            "rules and the defect register all write `G84`, never `G84 provider-error-seam` — "
            "so two gates sharing one is a citation that resolves to the wrong gate without "
            "ever dangling. The gate that landed LATER renumbers (file, label and every "
            "citation); see 12-governance/02-decision-log.md, 2026-09-04."
        )
    stale_freeze = sorted(
        num for num in NUMBER_COLLISION_FROZEN if len(numbers.get(num, ())) < 2
    )
    if stale_freeze:
        raise SystemExit(
            f"run_gates registry: {stale_freeze} is frozen in NUMBER_COLLISION_FROZEN and no "
            "longer collides — the exception has outlived the reason it was granted. Delete "
            "it, so the freeze can only ever shrink."
        )
    mods = [m.__name__ for _, m in GATES]
    dupe_mods = sorted({m for m in mods if mods.count(m) > 1})
    if dupe_mods:
        raise SystemExit(
            f"run_gates registry: module(s) {dupe_mods} registered more than once — one check "
            "would be counted as two, inflating the PASS count."
        )
    here = Path(__file__).resolve().parent
    on_disk = {
        p.stem
        for p in here.glob("g*.py")
        if p.stem not in GATE_NOT_A_GATE and p.name != Path(__file__).name
    }
    unwired = sorted(on_disk - set(mods))
    if unwired:
        raise SystemExit(
            "run_gates registry: gate module(s) "
            f"{unwired} exist on disk and NO row runs them — hard-won law 2, 'built is not "
            "wired'. A gate nobody runs is a comment claiming a guarantee. Add a row to GATES, "
            "or add the name to GATE_NOT_A_GATE with a written reason."
        )
    # `DEF-GOV-3733` — a registered module the runner cannot call. Checked here,
    # BEFORE any gate runs, so it reads as a registry error rather than as one
    # more red gate in a list of them.
    entryless = sorted(
        name for name, mod in GATES if not callable(getattr(mod, "run", None))
    )
    if entryless:
        raise SystemExit(
            f"run_gates registry: {entryless} expose no callable `run()` — this runner calls "
            "`module.run()` and gets AttributeError, which is reported as a crashed gate rather "
            "than as the wiring mistake it is. Every gate needs `def run() -> tuple[str, str]`; "
            "`main()` and `__main__` are the by-hand path and prove nothing about this one."
        )
    # ── the two tier tables name gates that exist (2026-09-10).
    #
    # ⚠ THIS CHECKS ONE DIRECTION ONLY, ON PURPOSE. A label in `TIER_1` or
    # `SURFACES` that is NOT a registered gate is a rename or a typo QUIETLY
    # REMOVING A GATE FROM A TIER — an under-run, which is the direction that
    # ships a defect, so it stops the suite. The opposite — a registered gate
    # named in neither table — does NOT stop the suite: it runs in every mode
    # and the selection banner prints how many did so (law 3, the unsafe
    # option must be the one you type). Refusing that direction too would halt
    # every lane's suite over a missing one-line declaration, for a case whose
    # fallback already over-runs rather than under-runs.
    known = {name for name, _ in GATES}
    phantom_tier1 = sorted(set(TIER_1) - known)
    phantom_surface = sorted(set(SURFACES) - known)
    if phantom_tier1 or phantom_surface:
        raise SystemExit(
            f"run_gates registry: TIER_1 names {phantom_tier1} and SURFACES names "
            f"{phantom_surface}, which are not registered gate labels. A tier table that names "
            "a gate nobody runs is a gate silently dropped from that tier — the label was most "
            "likely renamed in GATES and not here. Fix the label in both places."
        )
    dupe_tier1 = sorted({n for n in TIER_1 if TIER_1.count(n) > 1})
    if dupe_tier1:
        raise SystemExit(
            f"run_gates registry: TIER_1 lists {dupe_tier1} more than once — the tier-1 count "
            "printed beside every selective run would be wrong."
        )



def main() -> int:
    _assert_registry_sane()
    mode, base, wave_close, err = _parse_args(sys.argv[1:])
    if err is not None:
        print(err)
        return 0 if err is __doc__ else 2
    if wave_close:
        # Was: "journey automation is not built yet — G12 still SKIPs." Both
        # halves stopped being true on 2026-08-11 — a browser suite runs against
        # a live stack, and G12 no longer SKIPs anything (hard-won law 1: a
        # comment claiming a state is not the state).
        print("wave-close mode: G12 additionally requires the last Playwright run receipt.")

    # ── which gates, and why — printed BEFORE anything runs, so a reader of a
    # half-finished log knows what this run is even attempting.
    selected, banner = _select(mode, base)
    to_run = [(name, module) for name, module in GATES if name in selected]
    not_run = [name for name, _ in GATES if name not in selected]
    for line in banner:
        print(line)
    if not_run:
        print(
            f"  {len(not_run)} of {len(GATES)} gate(s) will NOT run for this selection — every "
            "one is named below the results table."
        )
    print()

    rows = []
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for name, module in to_run:
        try:
            status, detail = module.run()
        except Exception as exc:  # a crashing gate must block, never pass silently
            status, detail = "FAIL", f"gate crashed: {exc!r}"
        if status not in counts:
            status, detail = "FAIL", f"gate returned invalid status {status!r} ({detail})"
        counts[status] += 1
        rows.append((name, status, detail))

    # ── CHANGE 1, at the TOP of the output as the PO asked, before the rows.
    previous, why_none = _load_record()
    change_lines, recap = _render_change_block(
        previous,
        why_none,
        rows,
        f"{len(rows)} gate(s) that ran this run, of {len(GATES)} registered"
        + ("" if not not_run else f" — the other {len(not_run)} keep their recorded result untouched"),
    )
    for line in change_lines:
        print(line)

    print(f"{'gate':<18} {'status':<6} detail")
    print(f"{'-' * 18} {'-' * 6} {'-' * 50}")
    for name, status, detail in rows:
        print(f"{name:<18} {status:<6} {detail}")

    # ⚠ A SELECTIVE RUN SAYS WHAT IT DID NOT RUN, WITH A NUMBER AND WITH NAMES.
    # A selective green that reads like a full green is the most dangerous
    # thing this runner could print.
    if not_run:
        print(f"\nNOT RUN ({len(not_run)} of {len(GATES)} gate(s)) — this run judged none of these:")
        for line in _wrap_names(not_run):
            print(line)

    write_problem = _save_record(previous, rows, mode)
    if write_problem:
        print(
            f"\nrun_gates: WARNING — {write_problem}. This run is unaffected; the NEXT run will "
            "report that it has nothing to compare against, which is the honest fallback."
        )

    print()
    print(recap)
    if not not_run:
        verdict = "MERGE BLOCKED" if counts["FAIL"] else "merge allowed"
        print(
            f"run_gates: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['SKIP']} SKIP — {verdict}"
        )
    else:
        flag = "--tier1" if mode == "tier1" else "--changed"
        print(
            f"run_gates: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['SKIP']} SKIP "
            f"of {len(rows)} gate(s) RUN — {len(not_run)} of {len(GATES)} NOT RUN ({flag})"
        )
        if counts["FAIL"]:
            print(
                f"PARTIAL RUN — MERGE BLOCKED by {counts['FAIL']} gate(s) that ran; "
                f"{len(not_run)} more were never asked."
            )
        else:
            print(
                f"PARTIAL RUN — NOT A MERGE VERDICT. {len(not_run)} of {len(GATES)} gate(s) did "
                "not run, so nothing here says the merge is clean. Run with no mode flag for "
                "that. An exit status of 0 from this run means only that nothing among the "
                f"{len(rows)} gate(s) it DID run failed."
            )
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
