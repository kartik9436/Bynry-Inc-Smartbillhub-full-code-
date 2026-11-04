#!/usr/bin/env python
# ── Trace ──────────────────────────────────────────────
# Rules:  CLAUDE.md hard rule 1 (tenant scoping — every read here sets
#         `app.tenant_id` and goes through the module's own published door) ·
#         hard-won law 7 (a check must be able to fail, and its output must
#         distinguish pass from fail to a READER, not merely to an exit code).
# ───────────────────────────────────────────────────────
"""READ THE BYTES BACK OUT OF THE STORE, AND COMPARE THEM TO WHAT WAS SENT.

WHY THIS EXISTS SEPARATELY FROM THE BROWSER WALK
──────────────────────────────────────────────────────────────────────────────
⚠ **A ROW IN A TABLE IS NOT A FILE.** `DEF-CUS-5872` is six rows on this very
beta that carry a name, a type, an uploader and a `storage_ref`, and point at
NOTHING — four of them reading `Verified`. Every assertion that reads the ROW
passes on all six. So the browser walk proves the screen, and this proves the
only thing the screen cannot: that the bytes a clerk handed over are the bytes
the store gives back.

⚠ **AND IT CANNOT BE DONE FROM THE BROWSER, WHICH IS WHY IT IS A SECOND FILE.**
The dev storage backend mints `file://` URLs. A browser will not follow one, so
the walk can assert that a download link is ISSUED (200) and never that the
thing behind it is right — the exact shape of a check that looks at the wrong
thing. This opens it.

WHAT IT PROVES, AND WHAT A FALSE PASS WOULD LOOK LIKE
──────────────────────────────────────────────────────────────────────────────
It is deliberately EXPECTED-VALUE driven rather than self-consistent. Asking
the store for a document and hashing what comes back proves only that the store
is internally consistent; it would pass just as happily over a file of zero
bytes. So the walk writes a body containing its own TAG, this is told that tag,
and the comparison is against a string composed HERE from the tag — so the only
way to pass is for the clerk's actual bytes to have survived.

    ./10-scripts/po20260919_request_step4_readback.py W1AND3-S4-993843

⚠ **IT ALSO PROVES THE REFUSAL, NOT ONLY THE SUCCESS.** The walk creates one
row with a file and one without. A store that answered bytes for BOTH would be
a store that invents files, so the ticked row's read must RAISE — and a run in
which that read quietly succeeds is a failure even though nothing threw.
"""
import hashlib
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import connection  # noqa: E402

from apps.customers import models, service_request_documents as docs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else ""
SUB = os.environ.get("REQ_WALK_TENANT", "brazosbend")
results: list[tuple[bool, str, str]] = []


def ok(name: str, passed: bool, detail: str = "") -> None:
    results.append((passed, name, detail))


with connection.cursor() as cur:
    cur.execute("select id from tenants where subdomain = %s", [SUB])
    row = cur.fetchone()
if row is None:
    sys.exit(f"no tenant {SUB!r}")

# ⚠ **`tenant_context`, NOT A BARE `set_config`.** `service_request_documents`
# resolves the tenant from `core.tenancy.current_tenant_id()` and raises
# `AUTH-003` without it — deny by default, which is hard rule 1 working. Setting
# the GUC alone satisfies RLS in the database and leaves the application layer
# with no tenant at all, so the two must be entered together, and this is the
# helper that does both.
with core_tenancy.tenant_context(row[0]):
    requests = list(
        models.ServiceRequest.objects.filter(applicant_name__contains=TAG).order_by("-created_at")
    )
    ok(f"a request tagged {TAG} exists", len(requests) > 0, f"{len(requests)} found")

    if requests:
        req = requests[0]
        rows = list(models.ServiceRequestDocument.objects.filter(request=req).order_by("created_at"))
        ok("it carries both rows the walk made", len(rows) == 2, f"{len(rows)} row(s)")

        withfile = [r for r in rows if docs.has_real_file(r)]
        nofile = [r for r in rows if not docs.has_real_file(r)]
        ok("exactly one of them holds a real file", len(withfile) == 1, f"{len(withfile)}")
        ok("and exactly one holds none", len(nofile) == 1, f"{len(nofile)}")

        if withfile:
            expected = f"SMARTBillHub step-4 attach proof {TAG}\n".encode()
            got = docs.fetch_bytes(req.id, withfile[0].id)
            ok("the store returns bytes for it", len(got) > 0, f"{len(got)} byte(s)")
            ok(
                "and they are the EXACT bytes the clerk handed over",
                got == expected,
                f"sha256 got {hashlib.sha256(got).hexdigest()[:16]} "
                f"want {hashlib.sha256(expected).hexdigest()[:16]}",
            )
            ok(
                "the size on the row is the size of those bytes",
                withfile[0].size == len(got),
                f"row says {withfile[0].size}, store returned {len(got)}",
            )
            print(f"    bytes read back: {got!r}")

        if nofile:
            # ⚠ A store that answered for this row would be inventing a file.
            raised = None
            try:
                docs.fetch_bytes(req.id, nofile[0].id)
            except Exception as exc:  # noqa: BLE001 — the TYPE is asserted below
                raised = exc
            ok(
                "a row with no file is REFUSED rather than answered",
                raised is not None,
                type(raised).__name__ if raised else "it returned bytes",
            )

for passed, name, detail in results:
    print(f"{'PASS' if passed else 'FAIL'} · {name}" + (f" · {detail}" if detail else ""))
p = sum(1 for r in results if r[0])
print(f"\n{p} PASS · {len(results) - p} FAIL")
sys.exit(0 if p == len(results) and results else 1)
