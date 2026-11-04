# ── Trace ──────────────────────────────────────────────
# Defects: DEF-LED-6665 — Taxes & Remittance printed "The books will not state
#          this. The reason has no wording yet." THREE TIMES · DEF-LED-6643 —
#          the General ledger printed it TWICE, on the Journal and on the Trial
#          balance.
# Rules:   B14 rule 33 (rationale is zero words on screen) · rule 32 (a screen
#          has a description budget; no internal code in clerk-facing copy).
# Tests:   this file
# ───────────────────────────────────────────────────────
"""EVERY GAP CODE THE LEDGER RAISES HAS WORDS IN THE CATALOGUE.

**THE HOLE THIS CLOSES.** `financeShared.gapSentence` looks up
`finance.gap.<code>` with `defaultValue: ""` and, finding nothing, returns
`finance.gap.unknown`. That fallback is deliberate — a missing key must degrade
rather than crash — and it is exactly why **nothing anywhere goes red when the
server adds a code**. `tsc` is green, every test is green, no gate fires, and a
finance officer reads a placeholder sentence about our own unfinished work.
`DEF-LED-6665`'s own prevention column asks for this check by name:

    "A gate that collects every gap code raised in the backend and fails when
     one has no finance.gap.* key in en.json."

⚠ **WHAT THIS COVERS AND WHAT IT DOES NOT — hard-won law 7's fifth shape, a
check reporting zero over a scope it silently excludes.** It reads
`06-backend/apps/ledger/*.py` and nothing else, and inside those it matches the
GAP SHAPE this module uses everywhere: a dict literal carrying both a `"code"`
and a `"detail"`. `test_the_scan_covers_what_it_claims_to` prints the number of
codes it found, so a pattern that quietly stops matching cannot look like a
clean sweep. **It does not see a code built by string concatenation, nor one
raised from another module** — `apps/tenancy` and `apps/reports` also feed
finance surfaces and are out of scope here, deliberately, because guessing at
their shape would give a number nobody could trust.

⚠ **THE BASELINE MAY ONLY SHRINK, AND IT IS A BACKLOG WITH THE LIGHTS ON.**
Twenty codes in `apps/ledger` had no key on 2026-09-25 besides the two this
lane wrote words for. Failing on all twenty would be *"a backlog wearing a
gate's clothes"*, which the Product Owner has already forbidden once in those
terms — so they are listed, and **every NEW code goes red on its first commit**,
which is the whole point. A baselined code that has since GAINED a key fails
too, so the list cannot quietly stop matching the catalogue. They are filed as
`DEF-LED-6676`.

**Proved RED before it was trusted green.** With
`finance.gap.per_authority_remitting_basis_is_not_stored` removed from
`en.json`:

    AssertionError: a gap code with no words reaches a clerk as
    'The books will not state this.':
      per_authority_remitting_basis_is_not_stored (reporting.py)
"""

import ast
import json
import pathlib

LEDGER = pathlib.Path(__file__).resolve().parents[1] / "apps" / "ledger"
EN = (
    pathlib.Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "i18n"
    / "locales"
    / "en.json"
)

#: Codes in `apps/ledger` with no `finance.gap.*` key on 2026-09-25.
#: **IT MAY ONLY SHRINK.** `DEF-LED-6676` is the row that owns them.
BASELINE = {
    "accounts_balance_is_not_written",
    "accrual_posting_role_gate_is_a_reading_not_a_ruling",
    "authority_identity_is_the_gl_account_not_the_jurisdiction_row",
    "collected_tax_omits_allocations_with_no_class_breakdown",
    "deposit_interest_is_read_never_computed",
    "depreciation_before_the_first_posted_period_is_not_in_the_books",
    "export_batch_number_series_is_not_seeded",
    "filing_history_has_no_home",
    "finance_owner_role_gate_is_not_enforced_here",
    "footing_is_not_a_verdict_on_a_trial_balance_narrowed_to_one_premises",
    "migrated_deposit_interest_is_not_posted",
    "no_final_settlements_table_records_the_path",
    "no_importer_calls_this_yet",
    "period_closed_auto_forwarded",
    "the_contra_leg_is_this_lane_s_judgment",
    "the_four_ageing_buckets_are_not_carried",
    "the_over_credit_case_is_refused_not_chosen",
    "the_settled_register_and_the_cost_books_disagree",
    "unbilled_accrual_excludes_the_unread_tail",
    "unpaid_cost_accrual_covers_only_captured_invoices",
}


def _gap_codes() -> dict[str, set[str]]:
    """Every `{"code": "...", "detail": ...}` literal in `apps/ledger`."""
    found: dict[str, set[str]] = {}
    for path in sorted(LEDGER.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            names = {
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            if not {"code", "detail"} <= names:
                continue
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "code"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    found.setdefault(value.value, set()).add(path.name)
    return found


def _catalogue() -> dict[str, str]:
    return json.loads(EN.read_text(encoding="utf-8"))


def test_the_scan_covers_what_it_claims_to():
    # Law 7 — print what was checked, so a detector that stops matching cannot
    # read as a clean sweep. 41 gap-shaped dicts on 2026-09-25.
    found = _gap_codes()
    assert len(found) >= 40, f"the gap shape stopped matching: only {len(found)} found"
    assert "per_authority_remitting_basis_is_not_stored" in found
    assert "posted_entries_without_a_je_number" in found


def test_every_gap_code_has_words_a_clerk_can_read():
    catalogue = _catalogue()
    findings = [
        f"{code} ({', '.join(sorted(files))})"
        for code, files in sorted(_gap_codes().items())
        if code not in BASELINE and f"finance.gap.{code}" not in catalogue
    ]
    assert findings == [], (
        "a gap code with no words reaches a clerk as "
        f"{catalogue['finance.gap.unknown']!r}:\n  " + "\n  ".join(findings)
    )


def test_the_baseline_may_only_shrink():
    # A baselined code that has since gained a key, or left the codebase, is a
    # licence for nothing — and a list that stops matching the catalogue is how
    # a baseline quietly forgives strings nobody looked at.
    catalogue = _catalogue()
    found = _gap_codes()
    stale = sorted(
        code
        for code in BASELINE
        if f"finance.gap.{code}" in catalogue or code not in found
    )
    assert stale == [], f"these no longer need a licence — take them out: {stale}"


def test_the_two_codes_this_lane_fixed_have_words():
    catalogue = _catalogue()
    for code in (
        "per_authority_remitting_basis_is_not_stored",
        "posted_entries_without_a_je_number",
    ):
        assert f"finance.gap.{code}" in catalogue


def test_the_placeholder_no_longer_confesses_to_a_clerk():
    # ⚠ `finance.gap.unknown` READ *"The books will not state this. The reason
    # has no wording yet."* UNTIL 2026-09-25. The second sentence is our own
    # unfinished work told to a utility user, and B14 rule 33 puts rationale at
    # ZERO words on screen. It is REMOVED, not reworded. The first sentence is
    # a FACT at five words and stands.
    unknown = _catalogue()["finance.gap.unknown"]
    assert unknown == "The books will not state this."
