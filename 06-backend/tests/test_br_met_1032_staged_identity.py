# ── Trace ──────────────────────────────────────────────
# Change:  BR-MET-1032 — an uploaded spreadsheet stops keeping Social Security
#          numbers in plain text while it waits to be committed, and the
#          checking screen stops showing them back. BOTH import doors.
# Ruling:  PO 2026-09-01, verbatim: *"in spreadsheet we will porvide entire SSN
#          number if required"* — the FILE half, CONFIRMED and unchanged here.
#          The SCREEN and STORE halves are build judgments recorded in
#          `12-governance/02-decision-log.md` the same day (law 13).
# Rules:   BR-MET-1032 (this rule) · BR-CUS-092 (app-layer encrypted, last four
#          only on every read path) · BR-CUS-1022 (identity is per kind) ·
#          BR-CUS-1024 (an exact agreement on name + one identifier REUSES the
#          number already on file) · BR-MET-1030 (the premises file's owner
#          identity) · BR-CUS-673 (the failures file is the operator's own row,
#          for re-upload) · OQ-016 CLOSED · CLAUDE.md hard-won law 7 (prove the
#          guard RED first) · law 14 (PostgreSQL, not the default suite)
# Screens: WFL-01.premises.3 · WFL-01.accounts.3 (the checking step)
# ───────────────────────────────────────────────────────
"""What a parked upload keeps, and what the checking screen shows back.

WHAT THIS FILE MEASURES, AND WHY EACH HALF NEEDS ITS OWN CASE
--------------------------------------------------------------
Three things were tangled in one question and they pull in opposite directions,
which is exactly why *"we encrypted it"* is not a finding:

    the FILE      carries the whole number      — unchanged, and asserted so
    the SCREEN    serves ••••6789               — asserted on the payload
    the STORE     holds a ciphertext + index    — asserted in the DATABASE
    the MATCHER   still sees the whole number   — asserted by COUNTING customers

**THE FOURTH IS THE ONE THAT MATTERS.** A change that redacted on the way IN
would satisfy the first three completely and break the feature the number is
collected for: a blind index cannot be built from four digits, so every
returning customer would be minted a second Customer #, silently, with every
count on every receipt still reading correctly. `test_..._the_matcher_still_
matches` is the case that can tell the difference, and it counts ROWS rather
than inspecting a value.

WHAT WAS PROVED RED FIRST (r11 step 2d, hard-won law 7)
--------------------------------------------------------
⚠ **RUN ON A CLEAN WORKTREE AT THE BRANCH TIP — the product as it stood before
this lane, with only this file and `import_identity`'s READER half copied in
(the reader alone changes no behaviour, so the suite fails on the DEFECT rather
than on an ImportError, which proves nothing).** The failures below are quoted
from that run, not reconstructed::

      7 failed, 5 passed, 4 warnings in 21.51s

* The staging table held the operator's nine digits, which is the defect::

      E   AssertionError: BR-MET-1032: the staged cell still holds the whole
          number — read straight from PostgreSQL: '123-45-6789'
      E   assert '123-45-6789' == '••••6789'

* The checking screen was served them too::

      E   AssertionError: BR-MET-1032: the checking screen is showing the whole
          Social Security number
      E   assert '123-45-6789' == '••••6789'

* There was no vault to look in at all::

      E   AssertionError: BR-MET-1032: no blind index was written beside the
          staged identifier
      E   assert None is not None
      E   KeyError: '__identity__'

* And the screen was told nothing about what it was drawing::

      E   KeyError: 'masked'

**THE FIVE THAT PASSED ON THE CLEAN TREE ARE THE POINT OF THEM.** The matcher
case, the verdict case, the phone case and the duplicate-drop case all passed
BEFORE this change — they are the REGRESSION half, and a change that hardened
the store by breaking one of them would have shown up here rather than in
production. They are recorded as passing-then and passing-now rather than
quietly counted as successes of this lane.

⚠ **TWO OF THIS SUITE'S OWN FIRST DRAFTS WERE WRONG, AND BOTH ARE RECORDED**,
because a file that lists only the bugs it caught in the product implies it
never had any of its own:

* `_from_the_database` assumed the driver hands a `jsonb` column back as a
  dict. It hands back TEXT on this connection, so every case that read a cell
  died on `TypeError: string indices must be integers, not 'str'` — a failure
  that says nothing at all about the rule under test.
* The failures-file case ran as a BILLING CLERK over a file whose only row
  rejects, and met `BizError: BIZ-APPROVAL (metering.import.approver_role)` —
  a refusal about a ROLE standing in front of an assertion about a FILE.

WHAT IS DELIBERATELY NOT ASSERTED, SAID SO NOBODY READS MORE INTO IT
---------------------------------------------------------------------
* **Nothing is migrated.** A run parked before this rule keeps its plain-text
  cell, and `test_..._a_row_staged_before_the_rule_still_reads` asserts that it
  stays READABLE rather than that it gets fixed. This governs what is written
  from now on, like every rule in its family.
* **A phone is not vaulted and not masked.** `customers.selectors` serves a
  phone in full on every other surface, so masking it here would be this file
  inventing a rule; the case asserting that is a statement of the boundary, not
  an oversight.
"""

import json

import pytest
from django.db import connection

from apps.customers import models as customer_models
from apps.metering import import_identity, import_runs
from core import crypto

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_cr023_import_stages import ALL_ON, _csv, _row
from tests.test_cr058_w3_premises_owner_import import (
    BLANKS,
    OWNER_HEADERS,
    OWNER_MAPPING,
)

pytestmark = pytest.mark.django_db

#: One person, one number, used everywhere below so the blind indexes compared
#: across two tables are comparisons of the SAME identifier and not of two.
SSN = "123-45-6789"
LAST_FOUR = "••••6789"


def _premises_rows(*owners: tuple[str, str]) -> list[dict]:
    """One premises row per `(owner name, ssn)`, every other identity cell blank.

    `PREMISE_ID` and `PROP_TYPE` stay empty for the reasons the W3 suite already
    records: either would reject rows for something that has nothing to do with
    identity, and an unmeasurable count is worse than a failing one."""
    return [
        _row(
            index,
            PREMISE_ID="",
            PROP_TYPE="",
            OWNER=owner,
            **{
                **BLANKS,
                "OWNER_KIND": "person",
                "SSN": ssn,
                "OWNER ACCOUNT TYPE": "residential",
            },
        )
        for index, (owner, ssn) in enumerate(owners, start=1)
    ]


def _stage(actor, rows: list[dict], *, through_transform: bool = True) -> dict:
    """Extract (and usually transform + validate), through the SAME functions a
    screen calls. Never a hand-built `ImportRunRow`: this rule is about what the
    STAGES write, so a test that assembled a row itself would assert nothing."""
    run = import_runs.extract(
        actor,
        {
            "target": "premises",
            "source_kind": "file",
            "file_name": "br_met_1032.csv",
            "content": _csv(rows, OWNER_HEADERS),
            "session_ref": "sess_br_met_1032",
            "ip": "71.42.108.14",
        },
    )
    if through_transform:
        import_runs.transform(
            actor, run["id"], {"mapping": OWNER_MAPPING, "row_handling": ALL_ON}
        )
        import_runs.validate(actor, run["id"])
    return run


def _from_the_database(run_id) -> list[tuple[int, dict, dict]]:
    """`(row_no, raw, mapped)` read with SQL rather than through the ORM.

    ⚠ **THE ORM IS NOT A WITNESS HERE.** Every claim this file makes is about
    what is AT REST, and a model layer is exactly the place a decryption could
    hide. Going through the cursor is what makes *"read the staged row straight
    from the database"* literally true.

    ⚠ The driver hands a `jsonb` column back as TEXT on this connection, so it
    is parsed here rather than assumed to arrive as a dict — assuming cost a
    run of `TypeError: string indices must be integers`."""

    def _json(value):
        if isinstance(value, str):
            return json.loads(value)
        return value or {}

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT row_no, raw::text, mapped::text FROM import_run_rows "
            "WHERE run_id = %s ORDER BY row_no",
            [str(run_id)],
        )
        return [(row[0], _json(row[1]), _json(row[2])) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════════════════════════
# THE STORE — WHAT A PARKED UPLOAD KEEPS
# ═══════════════════════════════════════════════════════════════════════════


def test_br_met_1032__the_staged_row_holds_no_plaintext_identifier(brazos, marcus):
    """`BR-MET-1032` — read straight from PostgreSQL, twice: after stage 1 and
    after stage 2. A run sits at `extracted` until somebody maps it, so both
    moments are moments the number would have been sitting there."""
    with tenant_ctx(brazos):
        run = _stage(marcus, _premises_rows(("Rosa Alvarez", SSN)), through_transform=False)
        (_row_no, raw, _mapped) = _from_the_database(run["id"])[0]
        assert raw["SSN"] == LAST_FOUR, (
            "BR-MET-1032: the staged cell still holds the whole number — read "
            f"straight from PostgreSQL: {raw['SSN']!r}"
        )
        assert SSN not in str(raw), "the nine digits are somewhere in the staged row"

        import_runs.transform(
            marcus, run["id"], {"mapping": OWNER_MAPPING, "row_handling": ALL_ON}
        )
        import_runs.validate(marcus, run["id"])
        (_row_no, raw, mapped) = _from_the_database(run["id"])[0]
        assert raw["SSN"] == LAST_FOUR
        assert mapped["owner_ssn"] == LAST_FOUR
        assert SSN not in str(raw) and SSN not in str(mapped)


def test_br_met_1032__the_blind_index_equals_the_customers_own(brazos, marcus):
    """The index beside the staged value is the token the MATCHER looks up.

    ⚠ **THIS IS THE ASSERTION THE WHOLE FEATURE HANGS ON AND IT IS ONE LINE.**
    A blind index is an HMAC over `INDEX_SCHEME|context|normalised`, so a staged
    token computed under any context but `customers`' own would be a
    well-formed, deterministic, useless string: every lookup would miss, every
    returning customer would get a second number, and nothing would raise."""
    with tenant_ctx(brazos):
        run = _stage(marcus, _premises_rows(("Rosa Alvarez", SSN)))
        (_row_no, raw, mapped) = _from_the_database(run["id"])[0]

        staged = import_identity.blind_index_of(raw, "SSN")
        assert staged is not None, (
            "BR-MET-1032: no blind index was written beside the staged identifier"
        )
        # What `customers` would compute for the SAME number, through its own
        # module rather than through a constant repeated here.
        from apps.customers import identity_match

        expected = crypto.blind_index(SSN, context=identity_match.CRYPTO_CONTEXT["ssn"])
        assert staged == expected, (
            "BR-MET-1032: the staged blind index does not equal the one the "
            "customer record would carry for the same number — the matcher "
            "would look it up and find nothing"
        )
        assert import_identity.blind_index_of(mapped, "owner_ssn") == expected

        # ⚠ **THE HYPHENS ARE NOT PART OF THE IDENTIFIER.** A person types them
        # on Tuesday and omits them on Thursday, and `normalise_identifier`
        # exists so both index the same. Asserted here because the staged half
        # is a new caller of it.
        assert crypto.blind_index(
            "123456789", context=identity_match.CRYPTO_CONTEXT["ssn"]
        ) == expected


def test_br_met_1032__the_ciphertext_is_bound_to_the_staging_column(brazos, marcus):
    """The envelope decrypts under `import_run_rows.ssn` and REFUSES under
    `customers.ssn`.

    Two facts in one case because they are the same fact: the AAD is what stops
    a staged blob being dropped into a customer column without going through the
    door `customers` owns."""
    with tenant_ctx(brazos):
        run = _stage(marcus, _premises_rows(("Rosa Alvarez", SSN)))
        (_row_no, raw, _mapped) = _from_the_database(run["id"])[0]
        envelope = raw[import_identity.VAULT]["SSN"][import_identity.CIPHER]

        assert crypto.decrypt(envelope, context="import_run_rows.ssn") == SSN
        with pytest.raises(crypto.FieldDecryptionError):
            crypto.decrypt(envelope, context="customers.ssn")


# ═══════════════════════════════════════════════════════════════════════════
# THE SCREEN — WHAT AN OPERATOR SEES ON THE CHECKING STEP
# ═══════════════════════════════════════════════════════════════════════════


def test_br_met_1032__the_checking_screen_serves_the_last_four(brazos, marcus):
    """`GET /imports/{id}` — the payload the stage-3 table draws.

    The row is made to REJECT on purpose (a premise number this utility never
    issued), because the reject window is the one surface that carries a row's
    own cells to a screen."""
    rows = _premises_rows(("Rosa Alvarez", SSN))
    rows[0]["PREMISE_ID"] = "P-99999"
    with tenant_ctx(brazos):
        run = _stage(marcus, rows)
        payload = import_runs.read_run(run["id"])
        reject = payload["rejects"][0]

        assert reject["raw"]["SSN"] == LAST_FOUR, (
            "BR-MET-1032: the checking screen is showing the whole Social "
            "Security number"
        )
        assert SSN not in str(payload), (
            "the nine digits are somewhere in the payload the screen is polled with"
        )
        # ⚠ **AND THE ENVELOPE DOES NOT TRAVEL EITHER.** A ciphertext on the
        # wire every two seconds is still the value's shadow, and no screen has
        # any use for one.
        assert import_identity.VAULT not in reject["raw"]
        assert "sbh1:" not in str(payload)
        # The screen is TOLD which cells are masked — the inline editor opens
        # those empty rather than pre-filled, so an appended digit cannot become
        # somebody's identifier.
        assert reject["masked"] == ["SSN"]


def test_br_met_1032__a_phone_is_neither_vaulted_nor_masked(brazos, marcus):
    """The boundary, asserted rather than left as an absence.

    `customers.selectors.customer_detail` serves `phone` IN FULL and serves the
    three government identifiers as `*_last4`. This screen follows that exactly.
    A phone masked here would be a rule this repo has not made."""
    rows = _premises_rows(("Rosa Alvarez", SSN))
    rows[0]["OWNER PHONE"] = "281-555-0134"
    with tenant_ctx(brazos):
        run = _stage(marcus, rows)
        (_row_no, raw, mapped) = _from_the_database(run["id"])[0]
        assert raw["OWNER PHONE"] == "281-555-0134"
        assert mapped["owner_phone"] == "281-555-0134"
        assert "OWNER PHONE" not in (raw.get(import_identity.VAULT) or {})


# ═══════════════════════════════════════════════════════════════════════════
# THE MATCHER — THE CASE THAT CAN TELL A HARDENING FROM A BREAKAGE
# ═══════════════════════════════════════════════════════════════════════════


def test_br_met_1032__the_matcher_still_matches(brazos, marcus):
    """One landlord, two addresses, ONE Customer # — with the value encrypted.

    ⚠ **THIS COUNTS ROWS AND INSPECTS NOTHING, DELIBERATELY.** Every other case
    in this file reads a stored value, and every one of them would pass over a
    change that redacted on the way in. This is the case that would not: two
    rows presenting the same person must join to one customer, and a matcher
    handed four digits would mint two.

    It is `BR-CUS-1024`'s own measured figure — *"a landlord at three buildings
    got `C-00001`, `C-00002` and `C-00003`; after it, ONE"* — re-asserted from
    the other side of an encryption boundary."""
    with tenant_ctx(brazos):
        before = customer_models.Customer.objects.count()
        run = _stage(marcus, _premises_rows(("Rosa Alvarez", SSN), ("Rosa Alvarez", SSN)))
        import_runs.load(marcus, run["id"], {"write_mode": "insert"})
        after = customer_models.Customer.objects.count()

    assert after == before + 1, (
        "BR-MET-1032: two rows presenting ONE person made "
        f"{after - before} customers. A blind index cannot be built from four "
        "digits, so a redaction on the way IN breaks matching while looking "
        "like it hardened the store."
    )


def test_br_met_1032__the_verdict_hands_over_the_whole_number(brazos, marcus):
    """`owner_account_verdict` is what `customers` is handed, and it must carry
    the operator's own nine digits — not the mask beside them."""
    with tenant_ctx(brazos):
        run = _stage(marcus, _premises_rows(("Rosa Alvarez", SSN)))
        (_row_no, _raw, mapped) = _from_the_database(run["id"])[0]
        verdict = import_runs.owner_account_verdict(mapped)
        assert verdict["identifiers"] == {"ssn": SSN}, (
            "BR-MET-1032: the account door was handed "
            f"{verdict['identifiers']!r} — the matcher cannot index that"
        )


# ═══════════════════════════════════════════════════════════════════════════
# THE FILE — UNCHANGED, IN BOTH DIRECTIONS
# ═══════════════════════════════════════════════════════════════════════════


def test_br_met_1032__the_failures_file_hands_the_whole_number_back(brazos, dana):
    """`BR-CUS-673` — the operator's own row, for them to fix and re-upload.

    ⚠ **A MASK HERE WOULD BE REDACTION THAT BREAKS THE FEATURE.** The file's one
    job is *fix two cells in the spreadsheet you already know and upload it
    again*; `normalise_identifier` strips bullets, so a re-uploaded `••••6789`
    would be filed as the identifier `6789`, match nobody, and mint a second
    customer. The PO's ruling puts the whole number in a spreadsheet, and this
    IS one."""
    rows = _premises_rows(("Rosa Alvarez", SSN))
    rows[0]["PREMISE_ID"] = "P-99999"
    with tenant_ctx(brazos):
        run = _stage(dana, rows)
        # ⚠ **DANA AND NOT MARCUS**, the same reason the W7 suite gives: a file
        # whose rows ALL reject is over `BR-MET-098`'s approval bar, and only an
        # owner or an admin may approve past it. A billing clerk would meet
        # `metering.import.approver_role` here — a refusal about a ROLE standing
        # in front of the assertion about a FILE.
        import_runs.load(dana, run["id"], {"write_mode": "insert", "approved": True})
        _name, lines = import_runs.results_csv(run["id"], "failures")
        body = "".join(lines)

    assert SSN in body, (
        "BR-MET-1032: the failures file came back redacted — the operator "
        "cannot fix and re-upload their own file"
    )
    assert import_identity.VAULT not in body, "the vault is not a column of anybody's file"


def test_br_met_1032__the_failures_file_keeps_its_header_row(brazos, dana):
    """`DEF-2991` — the first line of the download is the operator's own headers.

    ⚠ **THIS CASE EXISTS BECAUSE THE CASE ABOVE IT WAS NOT ENOUGH, AND THE GAP
    IS WORTH NAMING.** `..._hands_the_whole_number_back` asserts the Social
    Security number is IN the file — CONTENT — and it passed cleanly over a
    download that had **no header row at all**, because this lane's own block
    replacement dropped the `yield` that writes one. A CSV missing its header
    still parses, still has the right number of data lines, and reads as an
    ordinary file right up until an operator opens it and finds their columns
    unlabelled. **Content assertions cannot see SHAPE**, and the failures file's
    whole job is to be re-uploaded, which needs its headers.

    Proved RED against commit `0179d7a0`::

        E   AssertionError: DEF-2991: the failures file's first line is not its
            header row — got 'P-99999,1 Bluestem Ln,…'
    """
    rows = _premises_rows(("Rosa Alvarez", SSN))
    rows[0]["PREMISE_ID"] = "P-99999"
    with tenant_ctx(brazos):
        run = _stage(dana, rows)
        import_runs.load(dana, run["id"], {"write_mode": "insert", "approved": True})
        _name, lines = import_runs.results_csv(run["id"], "failures")
        body = "".join(lines)

    first = body.splitlines()[0]
    assert first.startswith("PREMISE_ID"), (
        f"DEF-2991: the failures file's first line is not its header row — got {first[:60]!r}"
    )
    # The operator's OWN headers, then the two we append — in that order, because
    # a re-upload maps by header name.
    assert "SSN" in first
    assert first.endswith(
        f"{import_runs.FAILURE_REASON_COLUMN},{import_runs.FAILURE_FIX_COLUMN}"
    ), f"the two appended columns are not the last two — got {first[-60:]!r}"
    # …and the row beneath it is still the operator's own row, whole number and
    # all. Shape and content, together, because either alone missed this.
    assert SSN in body.splitlines()[1]


def test_br_met_1032__an_exact_duplicate_is_still_dropped(brazos, marcus):
    """The nonce trap, and it is the reason this case exists.

    Every AES-GCM envelope carries a fresh random nonce, so two rows that are
    byte-identical in the operator's file hold DIFFERENT ciphertexts. A
    duplicate signature taken over the STORED cells would call them different
    rows, *"drop exact duplicates"* would silently stop dropping anything on any
    file carrying an identifier, and the count on the screen would still look
    right."""
    identical = _premises_rows(("Rosa Alvarez", SSN))
    rows = [identical[0], dict(identical[0])]
    with tenant_ctx(brazos):
        run = _stage(marcus, rows)
        after = import_runs.read_run(run["id"])

    assert after["counts"]["duplicates_dropped"] == 1, (
        "BR-MET-1032: an exact duplicate stopped being recognised — the random "
        "nonce in each envelope made two identical rows look different"
    )


def test_br_met_1032__a_row_staged_before_the_rule_still_reads(brazos, marcus):
    """*"Nothing already staged is invalidated"*, asserted rather than promised.

    The row is written as a pre-rule row would have been — plain text, no vault
    — and every read path must still answer for it. **Nothing migrates it**;
    this rule governs what is WRITTEN from now on, like every rule in its
    family, and a read path that rewrote rows would be a different decision
    nobody made."""
    from apps.metering import models as metering_models

    rows = _premises_rows(("Rosa Alvarez", SSN))
    rows[0]["PREMISE_ID"] = "P-99999"
    with tenant_ctx(brazos):
        run = _stage(marcus, rows)
        # Put the row back the way yesterday's build left it.
        row = metering_models.ImportRunRow.objects.get(run_id=run["id"], row_no=1)
        row.raw = {**{k: v for k, v in row.raw.items() if k != import_identity.VAULT},
                   "SSN": SSN}
        row.mapped = {**{k: v for k, v in row.mapped.items() if k != import_identity.VAULT},
                      "owner_ssn": SSN}
        row.save(update_fields=["raw", "mapped"])

        payload = import_runs.read_run(run["id"])
        reject = payload["rejects"][0]
        assert reject["raw"]["SSN"] == SSN, "an old row must stay READABLE"
        assert reject["masked"] == [], "an old row has no vault, so it masks nothing"

        verdict = import_runs.owner_account_verdict(row.mapped)
        assert verdict["identifiers"] == {"ssn": SSN}, "an old row must stay COMMITTABLE"
        assert import_identity.blind_index_of(row.raw, "SSN") is None, (
            "no index was written for it, and inventing one on read would hide "
            "that the row is old rather than that the value is absent"
        )


# ═══════════════════════════════════════════════════════════════════════════
# THE OTHER DOOR — ONE DECISION FIXED BOTH
# ═══════════════════════════════════════════════════════════════════════════


def test_br_met_1032__the_accounts_door_stages_the_same_way(brazos, dana):
    """The accounts upload, through its own four stages.

    Both doors stage through `import_run_rows`, which is why one decision fixes
    both — and this case is what makes that a measured claim rather than a
    sentence in a docstring."""
    from tests.test_cr058_w7_accounts_identity_import import (
        ALL_OFF,
        HEADERS,
        MAPPING,
        _row as _account_row,
        _units,
    )

    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        line = _account_row(
            units[0]["unit_no"], "", "Rosa Alvarez", kind="person", ssn=SSN
        )
        run = import_runs.extract(
            dana,
            {
                "target": import_runs.TARGET_ACCOUNTS,
                "source_kind": "file",
                "file_name": "br_met_1032_accounts.csv",
                "content": "\n".join([HEADERS, line]) + "\n",
                "session_ref": "sess_br_met_1032_acct",
            },
        )
        import_runs.transform(dana, run["id"], {"mapping": MAPPING, "row_handling": ALL_OFF})
        import_runs.validate(dana, run["id"])
        (_row_no, raw, mapped) = _from_the_database(run["id"])[0]

        assert raw["SSN"] == LAST_FOUR
        assert mapped["customer_ssn"] == LAST_FOUR
        assert SSN not in str(raw) and SSN not in str(mapped)
        # …and the accounts door's own verdict still sees the whole number.
        verdict = import_runs.account_identity_verdict(mapped)
        assert verdict["identifiers"] == {"ssn": SSN}


def test_br_met_1032__an_unrecognised_header_is_protected_at_stage_two(brazos, marcus):
    """A header the alias table never heard of, pointed at `owner_ssn` by hand.

    ⚠ **THIS IS THE CASE THE STAGE-1 HALF CANNOT COVER, AND IT IS WHY
    `transform` PROTECTS `raw` AGAIN.** Stage 1 only knows what its SUGGESTION
    recognised; an operator may map any column they like at stage 2, and a file
    whose Social Security column is headed `TAXPAYER REF` would otherwise keep
    its nine digits for the life of the run."""
    headers = [header for header in OWNER_HEADERS if header != "SSN"] + ["TAXPAYER REF"]
    mapping = {
        key: value for key, value in OWNER_MAPPING.items() if key != "SSN"
    } | {"TAXPAYER REF": "owner_ssn"}
    rows = _premises_rows(("Rosa Alvarez", SSN))
    rows[0]["TAXPAYER REF"] = rows[0].pop("SSN")

    with tenant_ctx(brazos):
        run = import_runs.extract(
            marcus,
            {
                "target": "premises",
                "source_kind": "file",
                "file_name": "br_met_1032_odd_header.csv",
                "content": _csv(rows, headers),
                "session_ref": "sess_br_met_1032_odd",
            },
        )
        # Stage 1 could not know: the header is nobody's alias.
        (_row_no, raw, _mapped) = _from_the_database(run["id"])[0]
        assert raw["TAXPAYER REF"] == SSN

        import_runs.transform(marcus, run["id"], {"mapping": mapping, "row_handling": ALL_ON})
        import_runs.validate(marcus, run["id"])
        (_row_no, raw, mapped) = _from_the_database(run["id"])[0]

    assert raw["TAXPAYER REF"] == LAST_FOUR, (
        "BR-MET-1032: a hand-mapped identity column kept its plaintext"
    )
    assert mapped["owner_ssn"] == LAST_FOUR
    assert SSN not in str(raw) and SSN not in str(mapped)
