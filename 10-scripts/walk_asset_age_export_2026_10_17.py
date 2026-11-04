"""Build the Meters download's CSV the way the export job does, minus the S3 upload.

DEF-AST-10178 walk. A local machine has no export bucket (`export_storage.backend()`
refuses with "File storage is not set up."), so the browser's Download link cannot
complete here. This runs the kernel's own file-building path — `params_from_payload`
→ `resource.select` → `row_stream` → `write_csv` — for the payload the Meters tab
sends (tab=meters, status=all, sort=age asc) and stops before `finish_artifact`.

Run from 06-backend under the walk copy's settings:
    python manage.py shell < ../10-scripts/walk_asset_age_export_2026_10_17.py
with OUT_CSV set to where the file should land.
"""

import os
from pathlib import Path

from apps.tenancy import exports as kernel
from core import tenancy

tenant_id = tenancy.tenant_id_for_slug(os.environ.get("TENANT", "brazosbend"))
out = Path(os.environ["OUT_CSV"])
with tenancy.tenant_context(tenant_id):
    resource = kernel.export_resource("assets")
    payload = {
        "resource": "assets",
        "filters": {"tab": "meters", "status": "all"},
        "sort": "age",
        "dir": "asc",
    }
    params = kernel.params_from_payload(resource, payload)
    tz = kernel.tenant_timezone(tenant_id)
    chosen = kernel.columns_for(resource, None)
    written = kernel.write_csv(
        out,
        tuple(column.name for column in chosen),
        kernel.row_stream(resource, resource.select(params), tz, columns=chosen),
    )
print(f"wrote {written} row(s) to {out}")
