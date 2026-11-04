"""`DEF-MET-9614` — committing the same FILE twice is refused by name, not a 500.

Hard rule 6 scopes the import's idempotency to the COMMIT: the same bytes may
be uploaded and rehearsed as often as anyone likes (TC-21), and a second commit
of the same RUN returns its receipt (`test_cr023_load_stage`). What was never
asked is the third case: a SECOND RUN carrying the SAME FILE to the same
target. `uq_import_runs_idempotency` (scoped to `status='loaded'`) refused it at
the run's final save, after every row had been written, as an unhandled
`IntegrityError` — HTTP 500, and on PostgreSQL every row of that transaction
rolled back with it.

The refusal now comes BEFORE any row is written and names the earlier run, so
a clerk reads which import already carried this file. Asserted on whichever
database the suite runs on; the PostgreSQL case is the one that reproduced the
500 (lane PARTS, sbh_wparts) and is re-run there by
`config.settings.pgtest`.
"""

import pytest

from apps.metering import import_runs, models
from core import errors

from tests.test_cr023_load_stage import _counts, _file, _validated
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_a_second_run_of_the_same_file_is_refused_by_name_before_a_row_is_written(brazos, marcus):
    content = _file(3)
    with tenant_ctx(brazos):
        first_id = _validated(marcus, content=content)
        first = import_runs.load(marcus, first_id, {"write_mode": "insert"})
        after_one = _counts()

        second_id = _validated(marcus, content=content)
        with pytest.raises(errors.BizError) as refused:
            import_runs.load(marcus, second_id, {"write_mode": "insert"})

        assert refused.value.message_key == "metering.import.file_already_loaded"
        assert refused.value.params["run_no"] == first["receipt"]["run_no"]
        assert _counts() == after_one, "the refused run wrote rows"
        # The run is left where it was — validated, so the clerk can see it —
        # and the earlier run is still the one that is loaded.
        assert models.ImportRun.objects.get(pk=second_id).status == "validated"
        assert models.ImportRun.objects.get(pk=first_id).status == "loaded"

