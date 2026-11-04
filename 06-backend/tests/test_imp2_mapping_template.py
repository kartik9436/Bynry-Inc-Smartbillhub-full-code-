# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10779 (Q7 — Save mapping as template disabled; saved
#           templates not offered)
# Ruling:   decision log 2026-10-30 "Eight open payment questions answered
#           (PO)" — Q7 = A: saved column layout per source; "Save mapping as
#           template" switched on with a name; applied automatically when a
#           file's headers match.
# ───────────────────────────────────────────────────────
"""Q7 — save "Hy-Vee weekly" this week; next week's file maps itself.

The mapping step saves the operator's map AS THEY SEE IT — every header,
including the ones they told us to ignore — so the next file with the same
header row is recognised exactly (BR-AST-048's exact header-set match). A map
saved from the run's confirmed spec alone drops the ignored headers and then
never matches the file it came from.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest

from apps.metering import import_runs
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

HEADERS = ["Store Acct", "Paid", "Txn Date", "Receipt", "Network", "Clerk"]
MAPPING = {
    "Store Acct": "account_ref",
    "Paid": "amount",
    "Txn Date": "paid_on",
    "Receipt": "reference",
    "Network": "network",
    "Clerk": None,  # ignored
}


def _file(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(HEADERS)
    for row in rows:
        writer.writerow(row)
    return out.getvalue()


def _extract(actor, content):
    return import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_PAYMENTS,
            "source_kind": "file",
            "file_name": f"hyvee-{uuid.uuid4().hex[:6]}.csv",
            "content": content,
            "session_ref": "sess_imp2_q7",
        },
    )


def test_hy_vee_weekly_is_saved_and_next_weeks_file_maps_itself(brazos, dana):
    with tenant_ctx(brazos):
        week1 = _extract(dana, _file([["AC-1", "253.00", "2026-10-22", "HV-1", "Hy-Vee", "kim"]]))
        assert week1["recognised_template"] is None
        saved = import_runs.save_mapping_template(
            dana, week1["id"], {"name": "Hy-Vee weekly", "mapping": MAPPING}
        )
        assert saved["name"] == "Hy-Vee weekly"
        assert saved["column_count"] == len(HEADERS)

        week2 = _extract(dana, _file([["AC-2", "60.00", "2026-10-29", "HV-2", "Hy-Vee", "lee"]]))
        assert week2["recognised_template"]["name"] == "Hy-Vee weekly"
        detected = week2["detected_mapping"]
        for source, target in MAPPING.items():
            if target is not None:
                assert detected[source] == target, (source, detected)
        assert detected.get("Clerk") in (None, import_runs.IGNORE)


def test_a_mapping_naming_a_header_the_file_does_not_have_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        run = _extract(dana, _file([["AC-1", "1.00", "2026-10-22", "R", "", ""]]))
        with pytest.raises(errors.ValidationError):
            import_runs.save_mapping_template(
                dana, run["id"], {"name": "x", "mapping": {"Not a header": "amount"}}
            )
