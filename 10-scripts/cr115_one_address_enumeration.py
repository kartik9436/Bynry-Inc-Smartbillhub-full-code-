#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 §6 lane 1 — *"ONE PATH DECIDES AN API'S URL"*.
# Defects:  DEF-INT-5502 (the endpoint column blank on every connector) ·
#           DEF-INT-4259 (the wrong host of two reached a browser page policy) ·
#           DEF-INT-5488 (a `host_field` naming a field nobody declares) ·
#           DEF-INT-5612 (the screen and the call read different code) ·
#           DEF-INT-5613 (the set-up screen re-derives the address in TypeScript
#           and answers differently from the connection view).
# Rules:    CR-115-BRC05 §3 risk 2 (a fourth URL source is how the column went
#           blank before) · BR-INT-037 (data, never a provider branch) ·
#           hard-won law 7 (a check's output must distinguish pass from fail to
#           a READER, and say what it could not see).
# Tests:    this file IS the proof; `06-backend/tests/test_cr115_one_address.py`
#           asserts the same equivalences inside pytest.
# Impacts:  apps/integrations/addressing.py · selectors.py · page_policy.py ·
#           live_calls.py · 10-scripts/gates/g128_one_address_resolver.py
# ───────────────────────────────────────────────────────
"""EVERY CONNECTOR × EVERY OPERATION × EVERY CONFIG SHAPE, RESOLVED AND PRINTED.

WHY THIS EXISTS
---------------
`CR-115-BRC05` §6 asks lane 1 for a refactor with **no behaviour change**, and
says what proof it will accept: *"enumerating every connector and every
operation, printing the resolved address before and after, and diffing. An
empty diff IS the deliverable."*

So this script prints ONE LINE per (connector, operation, config shape) holding
the address the product resolves. Run it on the tip, run it again after the
refactor, `diff` the two files. **A moved row is either a bug you found or one
you introduced, and the diff cannot tell you which — a person has to say.**

WHAT IT DRIVES, AND WHY THOSE TWO
---------------------------------
Two consumers place a value where a human or a browser can act on it, and they
are the two `CR-115` §3 risk 2 names:

  * **`selectors._operation_row(...)["endpoint"]`** — the ENDPOINT column under
    each operation's name on the connection view (S142). Driven THROUGH THE
    REAL FUNCTION with a real (unsaved) `IntegrationConnection`, never through
    a copy of its expression: a copy would prove this script agrees with
    itself.
  * **`page_policy.granted(...)`** — the origins the browser is permitted to
    fetch from. `granted` reads the ORM, so the rows are injected through a
    stand-in for `page_policy.models`; everything else about the function is
    the real thing.

THE CONFIG SHAPES, AND WHY EACH ONE
-----------------------------------
Per manifest: **empty** (nothing typed — the state every connector ships in) ·
**one per declared address field** (a connector holding two addresses with only
one filled in, which is `DEF-INT-4259`'s whole shape) · **all** (both filled) ·
**stray** (a key the manifest does not declare, so `settings_for`'s drop is
exercised). A manifest with two address fields therefore contributes four
shapes and `host_fallback_field` answers `None` on every one of them, which is
the deliberate behaviour this refactor must not "tidy".

WHAT WOULD MAKE THIS SCRIPT PASS WRONGLY — SAY IT OUT LOUD (law 7 habit 2)
--------------------------------------------------------------------------
  1. **Both runs printing `None` everywhere.** A resolver that answered `None`
     for all 91 operations would diff empty and be catastrophically wrong. The
     footer therefore prints HOW MANY rows carry a real address; a run whose
     `resolved` count is not the same as the previous run's is not an empty
     diff whatever `diff` says, and the count is IN the file so `diff` sees it.
  2. **The columns being computed by this file rather than by the product.**
     Both columns call the shipped function. There is no local re-implement-
     ation of the resolution order anywhere below — grep for `host_field` in
     this file: it appears in prose and in the SHAPE-BUILDER only.
  3. **Silently skipping a manifest.** The footer prints the manifest and
     operation counts; `29 connectors / 91 operations` is the tip's number.
  4. **The provenance column masking a moved address.** Provenance is written
     to a SEPARATE file, so the diff that matters is over the columns that
     exist in both runs.

WHAT IT DOES NOT COVER, WITH A NUMBER BESIDE IT (law 7, `G32`'s shape)
---------------------------------------------------------------------
It resolves what a SCREEN and a POLICY show. **It does not follow the call.**
Eight adapters are registered and five of them read an address field by a
LITERAL NAME of their own or ignore the configured address entirely; that
divergence is `DEF-INT-5612` and is a finding, not something this refactor
changes. `--adapters` prints that table beside this one so the blind spot
carries a number.

Python 3.12+; needs Django only to import the registry. No database.
"""

from __future__ import annotations

import argparse
import os
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "06-backend"

def _typed(field) -> str:
    """The value a shape types into one field — keyed by the field's NAME so a
    row that moves says which field it came from, and shaped by its KIND.

    ⚠ **A `host` GETS A BARE NAME AND A `url` GETS A WHOLE ADDRESS, BECAUSE
    THAT IS THE DIFFERENCE THE TWO KINDS EXIST FOR** (`DEF-INT-5589`). SMTP
    dials a host and a port and concatenates them into a connection string; a
    scheme typed into `email_smtp.host` is refused by `adapters/base.py`, so a
    fixture that put one there would be proving the product does something it
    refuses to do. `CR-115-BRC05` §6 names this case for the browser check in
    as many words: *a `host` that is NOT a URL and must stay that way*.
    """
    stem = field.name.replace("_", "-")
    if field.kind == "host":
        return f"{stem}.example.invalid"
    return f"https://{stem}.example.invalid/svc"


def _boot() -> None:
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    import django

    django.setup()


def _shapes(manifest) -> list[tuple[str, dict]]:
    """`(shape name, config)` for one manifest — see the docstring."""
    from apps.integrations.registry import ADDRESS_FIELD_KINDS

    address = [one for one in manifest.fields if one.kind in ADDRESS_FIELD_KINDS]
    out: list[tuple[str, dict]] = [("empty", {})]
    for one in address:
        out.append((f"only:{one.name}", {one.name: _typed(one)}))
    if len(address) > 1:
        out.append(("all", {one.name: _typed(one) for one in address}))
    out.append(("stray", {"not_a_declared_field": "stray.example.invalid"}))
    return out


def _endpoint_rows(registry) -> list[str]:
    """The ENDPOINT column, through `selectors._operation_row` itself.

    ⚠ **ONE NAMED STUB, AND IT IS NOT ON THE PATH BEING MEASURED.** The same
    row also carries `rate_limit_per_minute`, which reads
    `integration_rate_limit` — a table, and this script has no database. So
    `serve.rate_limit_for` is stood in for, BY NAME, for the length of this
    function. The endpoint expression does not call it, does not call anything
    else that reads a table, and the connection handed in below is a real
    unsaved model so that a refactor which STARTED reading the connection would
    still be measured rather than skipped.
    """
    from apps.integrations import models, selectors
    from apps.integrations.runners import serve

    real_rate_limit = serve.rate_limit_for
    serve.rate_limit_for = lambda connection, name: None  # noqa: ARG005 — a stand-in, named above
    rows: list[str] = []
    for manifest in registry.all():
        for shape, config in _shapes(manifest):
            connection = models.IntegrationConnection(
                tenant_id=None,
                provider_key=manifest.key,
                config=dict(config),
                enabled=True,
                status=models.STATUS_WORKING,
            )
            settings = selectors.settings_for(manifest, connection)
            for op in manifest.operations:
                # ⚠ **THE FIFTH ARGUMENT IS THE MANIFEST AFTER `CR-115-BRC05`
                # AND WAS A PRE-COMPUTED FALLBACK FIELD BEFORE IT.** Both
                # spellings are tried so the SAME script produces the BEFORE and
                # the AFTER table; a script that only ran against one of them
                # could not diff anything.
                try:
                    row = selectors._operation_row(op, connection, None, settings, manifest)
                except (TypeError, AttributeError):  # pragma: no cover — the pre-refactor shape
                    row = selectors._operation_row(
                        op, connection, None, settings, selectors.host_fallback_field(manifest)
                    )
                rows.append(
                    f"endpoint\t{manifest.key}\t{op.name}\t{shape}\t{row['endpoint']!r}"
                )
    serve.rate_limit_for = real_rate_limit
    return rows


class _Rows:
    """The smallest stand-in for `IntegrationConnection.objects` that `granted`
    uses: one `.filter(tenant_id=…, provider_key__in=…)` returning rows."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *, tenant_id, provider_key__in):  # noqa: ARG002 — signature is the contract
        return [one for one in self._rows if one.provider_key in set(provider_key__in)]


def _policy_rows(registry) -> list[str]:
    """The browser origins, through `page_policy.granted` itself.

    ⚠ `page_policy` reads the ORM, so the rows are injected. Everything the
    gate cares about — which field is read, whether an absent value contributes
    nothing, whether a held row suppresses the shipped default — is the real
    function's.
    """
    from apps.integrations import models, page_policy

    real = page_policy.models
    rows: list[str] = []
    try:
        for manifest in registry.all():
            for shape, config in _shapes(manifest):
                connection = models.IntegrationConnection(
                    tenant_id=None,
                    provider_key=manifest.key,
                    config=dict(config),
                    enabled=True,
                    status=models.STATUS_WORKING,
                )
                page_policy.models = types.SimpleNamespace(
                    IntegrationConnection=types.SimpleNamespace(objects=_Rows([connection])),
                    STATUS_OFF=models.STATUS_OFF,
                )
                for entry in page_policy.granted(tenant_id=None, registry=registry):
                    if entry["provider_key"] != manifest.key:
                        continue
                    rows.append(
                        f"policy\t{manifest.key}\t{entry['operation']}\t{shape}\t"
                        f"{entry['host']!r}\t{entry['source']!r}"
                    )
    finally:
        page_policy.models = real
    return rows


def _provenance_rows(registry) -> list[str]:
    """The NEW column — absent before the refactor, and that is why it is in its
    own file. `[]` when `apps.integrations.addressing` does not exist yet."""
    try:
        from apps.integrations import addressing
    except ImportError:
        return []
    from apps.integrations import models, selectors

    rows: list[str] = []
    for manifest in registry.all():
        for shape, config in _shapes(manifest):
            connection = models.IntegrationConnection(
                tenant_id=None,
                provider_key=manifest.key,
                config=dict(config),
                enabled=True,
                status=models.STATUS_WORKING,
            )
            settings = selectors.settings_for(manifest, connection)
            for op in manifest.operations:
                found = addressing.resolve_address(manifest, op, settings=settings)
                rows.append(
                    f"provenance\t{manifest.key}\t{op.name}\t{shape}\t"
                    f"{found.value!r}\t{found.source}\t{found.field!r}"
                )
    return rows


#: ⚠ **THE BLIND SPOT, WITH ITS NUMBER BESIDE IT.** What each REGISTERED adapter
#: actually reads when it places a call, read out of the adapter by hand on
#: 2026-09-17 and quoted with its line. This table is DATA FOR A READER, not a
#: check — nothing here can go red — and it exists so that nobody mistakes an
#: empty endpoint diff for a statement about where the calls go (`DEF-INT-5612`).
ADAPTER_CALL_SITES: dict[str, str] = {
    "email_microsoft": "class constant `send_url` — the configured address is never read",
    "email_google": "class constant `send_url` — the configured address is never read",
    "email_smtp": "config['host'] (email_smtp.py:271) — agrees with host_field",
    "meters_neptune360": "module constants READINGS_PATH/… (meters_neptune360.py:126-129) — the configured address is never read",
    "payments_sandbox": "no address at all — the sandbox answers in-process",
    "accounting_file": "config['drop_host'] (accounting_file.py:252) — agrees with host_field",
    "bank_lockbox_file": "config['sftp_host'] (bank_lockbox_file.py:214) — agrees with host_field",
    "gis_esri": "config['base_url'] (gis_city.py:170) — agrees for the two server operations; `map_tiles` declares tile_url and no server call reads it",
}


def _adapters(registry) -> list[str]:
    out: list[str] = []
    for manifest in registry.all():
        adapter = registry.adapter_for(manifest.key)
        if adapter is None:
            continue
        note = ADAPTER_CALL_SITES.get(manifest.key, "NOT READ BY HAND — add it here")
        out.append(f"{manifest.key}\t{adapter.__module__}.{adapter.__name__}\t{note}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="-", help="file to write the resolved table to ('-' = stdout)")
    parser.add_argument("--provenance", default=None, help="file to write the provenance table to")
    parser.add_argument("--adapters", action="store_true", help="print what each registered adapter really dials")
    args = parser.parse_args()

    _boot()
    from apps.integrations.registry import REGISTRY

    manifests = REGISTRY.all()
    operations = sum(len(one.operations) for one in manifests)

    if args.adapters:
        print("# what each REGISTERED adapter dials — the blind spot, named (DEF-INT-5612)")
        for line in _adapters(REGISTRY):
            print(line)
        print(f"# {len(_adapters(REGISTRY))} registered adapter(s) of {len(manifests)} connector(s)")
        return 0

    rows = _endpoint_rows(REGISTRY) + _policy_rows(REGISTRY)
    resolved = sum(1 for one in rows if not one.endswith("None") and "\tNone\t" not in one)
    footer = [
        f"# {len(manifests)} connector(s), {operations} operation(s), {len(rows)} row(s)",
        f"# {resolved} row(s) carry a real address — ⚠ A RUN WHERE THIS NUMBER FELL IS NOT",
        "#   AN EMPTY DIFF, WHATEVER `diff` SAYS: a resolver answering None everywhere",
        "#   would diff clean against itself and be wrong on all 91 operations.",
    ]
    text = "\n".join(rows + footer) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {len(rows)} row(s) to {args.out}")

    if args.provenance:
        prov = _provenance_rows(REGISTRY)
        if not prov:
            print(
                "apps/integrations/addressing.py is not present — no provenance table written. "
                "That is the expected state BEFORE the refactor."
            )
        else:
            Path(args.provenance).write_text("\n".join(prov) + "\n", encoding="utf-8")
            print(f"wrote {len(prov)} provenance row(s) to {args.provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
