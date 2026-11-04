# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-616 (2026-08-24) — the shipped premises sample CSV stopped
#           round-tripping through its own import. `premises.lat`/`.lng` landed
#           on the model (CR-028 AST-W5, migration 0018), the offered column set
#           is DERIVED from the model (BR-MET-088) and `sample_csv` is derived
#           from the offered set — so both columns reached the downloadable
#           sample the same day, while `PREMISES_ALIASES`, which is hand-kept,
#           did not move. Stage 1 then could not recognise two headers on the
#           product's own sample file.
#           DEF-619 (2026-08-24) — `service` is a required KIND_LOOKUP column on
#           both measuring-asset targets and the DEF-618 guard reported no rule
#           speaking for it.
# Rules:    BR-MET-088 (the MODEL decides which columns are offered) · CR-025
#           (the sample is header + one worked row, and it maps itself) ·
#           BR-AST-009 + BR-MET-003 (a measuring asset declares a service, and
#           only one this utility sells)
# Tests:    this file IS the prevention both rows ask for.
# Impacts:  apps/metering/import_runs.py (ALIASES_BY_TARGET, sample_csv) ·
#           apps/metering/import_rules.py (ASSETS_METERS_RULES /
#           ASSETS_SUBMETERS_RULES) · tests/test_cr030_w1_accounts_import.py
#           (the DEF-618 register this file's DEF-619 case retires an entry from)
# ───────────────────────────────────────────────────────
"""Two guards over the import surface, each one level above the defect it closes.

**DEF-616's guard is not "the premises sample has lat and lng".** That check
would pass tomorrow and fail again the day after, when the NEXT column is added
to a model. The property that actually holds is: **every header the product
generates for a target is a header the product can detect** — so
`test_def616__every_shipped_sample_maps_itself` walks every target, generates
its sample, and asserts stage 1 recognises the lot. A column added to a model
now shows up here the moment it reaches the sample, whichever target it lands on.

**DEF-619's case is the opposite finding: the rule was already there.** The
DEF-618 guard matches a lookup column to a rule by the naming convention
`<column>_in_lookup`, and the rule that speaks for `service` on both measuring
targets is `AST.SERVICE_ENABLED` (`rule_kind="asset_service_enabled"`,
TIER_STRUCTURAL, ERROR, reject_row) — which is exactly what DEF-619's own
prevention text asks somebody to declare. So this file does not add a rule; it
PROVES the existing one fires, on the case DEF-619 names (a file saying `ELEC`
where the tenant sells `electric`), and the register entry moves from "no rule"
to "covered, by a rule whose name does not follow the convention" — the same
annotation `assets_devices.type` already carries beside it.
"""

from __future__ import annotations

import pytest

from apps.metering import import_rules, import_runs, models as metering_models

from tests.test_cr028_seed import seeded, silvercreek  # noqa: F401 — fixture chain
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# DEF-616 · the shipped sample must map itself, on EVERY target
# ══════════════════════════════════════════════════════════════════════════


def _sample_headers(target: str) -> list[str]:
    _, body = import_runs.sample_csv(target)
    return body.splitlines()[0].split(",")


@pytest.mark.parametrize("target", sorted(import_runs.TARGETS))
def test_def616__every_shipped_sample_maps_itself(seeded, target):  # noqa: F811
    """Stage 1 detects every header the sample ships — for all six targets.

    ⚠ **THIS IS THE PROPERTY, NOT THE SYMPTOM.** DEF-616 was `lat`/`lng` on
    premises; the mechanism is that the offered set is derived from the MODEL
    and the alias table is hand-kept, so any model column added anywhere breaks
    this the moment it reaches the sample. Asserting it per target means the
    next one is caught wherever it lands.

    An operator who downloads the sample and uploads it unedited must reach
    stage 2 with nothing to map. A header that arrives unmapped is not an error
    the product raises — it is silently offered as unmapped, which is why this
    escaped: nothing anywhere failed.
    """
    tenant, actor = seeded
    with tenant_ctx(tenant):
        headers = _sample_headers(target)
        run = import_runs.extract(
            actor,
            {
                "target": target,
                "source_kind": "file",
                "file_name": f"{target}_sample.csv",
                "content": import_runs.sample_csv(target)[1],
                "session_ref": "sess_def616",
                "ip": "71.42.108.14",
            },
        )
    undetected = [h for h in headers if h not in run["detected_mapping"]]
    assert undetected == [], (
        f"the shipped `{target}` sample ships {len(headers)} column(s) and stage 1 cannot "
        f"recognise {undetected} — so the one file a first-time operator is told to start "
        "from arrives needing hand-mapping (DEF-616). A model column reached the offered "
        "set (BR-MET-088 derives it) and the hand-kept alias table did not move with it."
    )


def test_def616__the_premises_sample_still_carries_lat_and_lng(seeded):  # noqa: F811
    """The specific pair, kept beside the general rule.

    The general test above would also pass if `lat`/`lng` were REMOVED from the
    offered set, which would be a different regression — a map coordinate the
    schema holds and the import cannot fill. Both columns are on
    `metering.Premises` (migration 0018, CR-028 AST-W5 §10-D6), so both belong
    on the sample.
    """
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        headers = _sample_headers("premises")
        fields = [str(c["target"]) for c in import_runs.sample_columns("premises")]
    # ⚠ **THE COLUMNS ARE ASSERTED BY FIELD AND THE HEADERS BY LABEL SINCE
    # 2026-08-28 (`DEF-1077`).** The sample's header row is what an operator
    # reads — `Lat`, `Lng` — while the regression this test exists for is about
    # the OFFERED SET, which is field names. Asserting the header row against
    # field names would have made this test a statement about our vocabulary
    # rather than about the schema.
    assert "lat" in fields and "lng" in fields, fields
    assert "Lat" in headers and "Lng" in headers, headers
    aliases = import_runs.ALIASES_BY_TARGET["premises"]
    assert "lat" in aliases["lat"] and "lng" in aliases["lng"], aliases


# ══════════════════════════════════════════════════════════════════════════
# DEF-619 · `service` IS spoken for — by `AST.SERVICE_ENABLED`
# ══════════════════════════════════════════════════════════════════════════

# ⚠ The sub-meters target REQUIRES `parent_asset_no` mapped (BR-AST-003), so
# the two targets do not share one header line: an unmapped required column is
# refused at stage 2 (`metering.import.required_column_unmapped`) and the run
# never reaches the stage-3 rule this file is about. The parent named here does
# not exist on the tenant either — which is deliberate: that produces its OWN
# stage-3 reject on a DIFFERENT rule, and the assertions below look for the
# service sentence specifically rather than "some row was rejected".
_HEADER_BY_TARGET = {
    "assets_meters": "METER_NO,SERVICE,METER_TYPE,READ_METHOD,UNIT_REF",
    "assets_submeters": "METER_NO,SERVICE,METER_TYPE,READ_METHOD,UNIT_REF,PARENT_MTR",
}
_MAPPING_BY_TARGET = {
    "assets_meters": {
        "METER_NO": "asset_no",
        "SERVICE": "service",
        "METER_TYPE": "meter_type",
        "READ_METHOD": "read_method",
        "UNIT_REF": "unit_ref",
    },
    "assets_submeters": {
        "METER_NO": "asset_no",
        "SERVICE": "service",
        "METER_TYPE": "meter_type",
        "READ_METHOD": "read_method",
        "UNIT_REF": "unit_ref",
        "PARENT_MTR": "parent_asset_no",
    },
}
_ROW_TAIL = {"assets_meters": "", "assets_submeters": ",W-5011"}


def _validate_one(actor, target: str, body: str) -> dict[int, tuple[str, str | None]]:
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": "def619.csv",
            "content": body,
            "session_ref": "sess_def619",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(
        actor,
        run["id"],
        {
            "mapping": _MAPPING_BY_TARGET[target],
            "row_handling": {
                "drop_exact_duplicates": False,
                "keep_latest_on_key": False,
                "skip_rows_missing_required": False,
            },
        },
    )
    import_runs.validate(actor, run["id"])
    stored = metering_models.ImportRun.objects.get(pk=run["id"])
    return {row["row_no"]: (row["problem"], row["fix_hint"]) for row in import_runs.rejects(stored)}


@pytest.mark.parametrize("target", ["assets_meters", "assets_submeters"])
def test_def619__a_service_this_tenant_does_not_sell_is_REFUSED_AT_STAGE_3(
    seeded, target
):  # noqa: F811
    """DEF-619's own worked case: `ELEC` where the tenant's list says `electric`.

    The row DEF-619 describes is *"resolved to None at stage 2, unremarked at
    stage 3, and refused inside stage 4 — the one stage that writes"*. This
    asserts the opposite, because `AST.SERVICE_ENABLED` already covers it: the
    row is named at STAGE 3, with the operator's own token quoted back and a fix
    hint that names both places it can be fixed.

    Nothing writes: stage 3 is a read.
    """
    tenant, actor = seeded
    with tenant_ctx(tenant):
        rejects = _validate_one(
            actor,
            target,
            f"{_HEADER_BY_TARGET[target]}\n"
            f"DEF619-1,ELEC,positive_displacement,manual,{_ROW_TAIL[target]}\n",
        )
    assert 1 in rejects, (
        "a meter file naming a service this tenant does not have reached stage 4 unremarked "
        f"— DEF-619. Stage-3 rejects were: {rejects}"
    )
    problem, fix_hint = rejects[1]
    assert "ELEC" in problem, problem
    assert fix_hint, "a refused row must say where it can be fixed"


@pytest.mark.parametrize("target", ["assets_meters", "assets_submeters"])
def test_def619__a_BLANK_service_is_refused_at_stage_3_too(seeded, target):  # noqa: F811
    """`service` is `required=True`, and the blank case gets its own sentence."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        rejects = _validate_one(
            actor,
            target,
            f"{_HEADER_BY_TARGET[target]}\n"
            f"DEF619-2,,positive_displacement,manual,{_ROW_TAIL[target]}\n",
        )
    assert 1 in rejects, rejects
    assert "no service" in rejects[1][0].lower(), rejects[1]


@pytest.mark.parametrize("target", ["assets_meters", "assets_submeters"])
def test_def619__the_rule_is_DECLARED_error_and_reject_row(target):
    """The catalogue half — what DEF-619's prevention text asks to be declared.

    It is declared, under the name `AST.SERVICE_ENABLED` rather than
    `AST.SERVICE_IN_LOOKUP`, at TIER_STRUCTURAL rather than TIER_PLATFORM —
    which is stricter, not weaker: a structural rule may not be switched off by
    a tenant at all (BR-MET-090), because a row it flags is a row the database
    or a hard rule would refuse anyway.
    """
    catalogue = {rule.code: rule for rule in import_rules.PLATFORM_CATALOG[target]}
    rule = catalogue.get("AST.SERVICE_ENABLED")
    assert rule is not None, sorted(catalogue)
    assert rule.rule_kind == "asset_service_enabled"
    assert rule.severity == import_rules.ERROR
    assert rule.action == import_rules.REJECT_ROW
    assert rule.tier == import_rules.TIER_STRUCTURAL
    assert rule.rule_kind in import_rules.EVALUATORS, (
        "a declared rule with no evaluator is a sentence on a screen and nothing else "
        "(hard-won law 1)"
    )
