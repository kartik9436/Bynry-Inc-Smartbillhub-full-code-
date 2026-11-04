#!/usr/bin/env python3
"""Prove each CR-067 B1/B2/B3 guard RED before trusting it green (law 7).

Applies ONE sabotage, runs the suite that should bite, prints the failure, then
puts the original bytes back — read into memory first, written back in a
`finally`, and never through git (law 11 bans any command that makes the shared
tree momentarily not-what-it-was; this touches one file in this lane's own
worktree and restores it whatever happens).

    python3 scripts/cr067_red_proof.py <sabotage-name>
    python3 scripts/cr067_red_proof.py --list

⚠ **IT NOW COVERS BOTH HALVES, AND THE `be-` NAMES RUN PYTEST RATHER THAN
VITEST.** The B2/B3 lane added the endpoint `DEF-3321` was filed for and the
filter `DEF-3322` was filed for, and both live in `06-backend` — so a proof
script that could only sabotage a `.tsx` file could not have shown either of
them red. The two halves are one script on purpose: they are one change, and a
lane re-proving one should see the other in the same `--list`.

⚠ **THE BACKEND RUNS ARE SLOW UNLESS YOU REUSE THE DATABASE.** Set the four
environment variables below (they match the ones the lane report quotes) and the
first run pays for the schema; every sabotage after it takes seconds:

    export DJANGO_SETTINGS_MODULE=config.settings.local
    export DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub"
    export SBH_TEST_DB_NAME=test_sbh_cr067b JOBS_EAGER=false

The interpreter is the repo's own virtualenv; `SBH_PYTHON` overrides it. A bare
`python3` has no pytest, which is a five-minute detour the next lane need not
take twice.

Without them the backend sabotages still run, on the default in-memory SQLite
tier, and take about three minutes each.

Throwaway; it is here so the next lane can re-run a proof instead of trusting a
quoted string.
"""

import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parents[1]
BACKEND = HERE.parent / "06-backend"
PAGE = HERE / "src" / "features" / "audit" / "AuditLogPage.tsx"
ENDPOINTS = HERE / "src" / "api" / "endpoints.ts"
LOCALES = HERE / "src" / "i18n" / "locales"
API = BACKEND / "apps" / "audit" / "api.py"
SELECTORS = BACKEND / "apps" / "audit" / "selectors.py"
STORE = BACKEND / "apps" / "audit" / "diagnostics.py"
# ⚠ THE WHOLE AUDIT FOLDER, NOT THE ONE FILE. `toggle-inside-the-grid` is the
# reason: the check that catches it needs a DOM (`closest()`), so it lives in
# `AuditToolbarAlignment.dom.test.tsx` — and a proof script pointed at one file
# reported that sabotage GREEN, which is a proof that proves nothing.
TEST = "src/features/audit/"
BACKEND_TEST = "tests/test_cr067_diagnostic_read.py"

#: name -> (file, find, replace). One edit each; a sabotage that needs two is a
#: sabotage that is testing two things.
SABOTAGES: dict[str, tuple[pathlib.Path, str, str]] = {
    # The natural mistake, not an invented one: reading "is the key present"
    # instead of "is there a code". `sample.block_retried` writes
    # `error_code: null` on a retry that SUCCEEDED.
    "panel-on-success": (
        PAGE,
        '  const errorCode = payloadText(after, "error_code");\n  if (errorCode === null) {\n    return null;\n  }',
        '  const errorCode = payloadText(after, "error_code") ?? String(after?.error_code);\n  if (after === null) {\n    return null;\n  }',
    ),
    "no-meaning": (
        PAGE,
        'meaning: payloadText(after, "meaning"),',
        "meaning: null,",
    ),
    "no-copy-control": (
        PAGE,
        '        data-audit="copy-reference"\n',
        '        data-audit="no-copy-here"\n',
    ),
    "database-id-in-panel": (
        PAGE,
        "        <dt>{t(\"audit.diagnostic.result\")}</dt>",
        "        <dt>{t(\"audit.diagnostic.result\")}</dt>\n        <dd>01a062a7-9f7d-73e6-96e4-700cba033c73</dd>",
    ),
    "gate-always-open": (
        PAGE,
        "      {props.isSystemAdmin && (",
        "      {(props.isSystemAdmin || true) && (",
    ),
    "event-row-shows-the-code": (
        PAGE,
        '            <dt>{t("audit.diagnostic.techEvent")}</dt>\n            <dd>\n              <code className="font-mono text-sm">{props.action}</code>',
        '            <dt>{t("audit.diagnostic.techEvent")}</dt>\n            <dd>\n              <code className="font-mono text-sm">{failure.errorCode}</code>',
    ),
    # ⚠ REPOINTED 2026-09-02 BY THE B2/B3 LANE — the markup this named moved
    # into `DiagnosticAbsence` when the endpoint landed, and a sabotage whose
    # anchor is gone is a proof that silently stops proving anything (the script
    # REFUSES rather than passing, which is why it was caught).
    "absence-as-a-paragraph": (
        PAGE,
        '    <details\n      className="my-3 border border-dashed border-[color-mix(in_srgb,var(--color-text)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-text)_3%,transparent)] p-3"\n      data-audit="diagnostic-gap"\n      data-diagnostic-absence={props.reason}\n    >\n      <summary className="m-0 cursor-pointer font-heading text-md">{copy.title}</summary>',
        '    <div\n      className="my-3 border border-dashed border-[color-mix(in_srgb,var(--color-text)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-text)_3%,transparent)] p-3"\n      data-audit="diagnostic-gap"\n      data-diagnostic-absence={props.reason}\n    >\n      <h6 className="m-0 font-heading text-md">{copy.title}</h6>',
    ),
    # ⚠ THE OLD `absence-with-no-id` RAN THE OTHER WAY and cannot any more: it
    # deleted `data-tracks="DEF-3321"` to show G38's rule biting. That defect is
    # CLOSED and the attribute is gone, so the guard that replaced it asserts the
    # note did not survive its reason (DEF-445). The sabotage puts it back.
    "absence-note-outlives-its-defect": (
        PAGE,
        '      data-diagnostic-absence={props.reason}\n',
        '      data-diagnostic-absence={props.reason}\n      data-tracks="DEF-3321"\n',
    ),
    "english-only": (
        LOCALES / "de.json",
        '  "audit.diagnostic.advice": "Was zu tun ist",\n',
        "",
    ),
    # G15's other half: the key is THERE and the value is the English string.
    "english-pasted-in": (
        LOCALES / "it-IT.json",
        '  "audit.diagnostic.techWhere": "Dove",\n',
        '  "audit.diagnostic.techWhere": "Where",\n',
    ),
    # ── CR-067 B2/B3 lane, 2026-09-02 ──────────────────────────────────────
    # The state DEF-3321 recorded, put back: the panel draws the four summary
    # rows out of the shared payload and nothing from the diagnostic read.
    "record-not-drawn": (
        PAGE,
        "          {props.diagnostic?.record != null && (",
        "          {false && props.diagnostic?.record != null && (",
    ),
    # The call path as a visible list — DEF-2375's shape, on the one panel where
    # it is most tempting because a stack looks like something to show.
    "stack-open": (
        PAGE,
        '        <details className="mt-2" data-audit="diagnostic-stack">',
        '        <details open className="mt-2" data-audit="diagnostic-stack">',
    ),
    # ⚠ THE ONE THAT MATTERS MOST, AND IT LOOKS LIKE BOOKKEEPING. The control
    # stays, the server clause stays, and the filter simply never reaches the
    # URL: `parseTableParams`/`serializeTableParams` walk `TableConfig.filters`.
    # The list comes back whole and reads as a product with no errors in it.
    "filter-not-declared": (
        PAGE,
        '      { name: "outcome", label: t("audit.filter.outcome"), options: [] },\n',
        "",
    ),
    "no-errors-only": (
        PAGE,
        '          id="f.outcome"\n',
        '          id="f.no-such-control"\n',
    ),
    # The same drop one layer on: declared on the screen, absent from the typed
    # client's own vocabulary, so `auditQuery` never puts it in the query string.
    "filter-not-in-the-client": (
        ENDPOINTS,
        '  "to",\n  "outcome",\n] as const;',
        '  "to",\n] as const;',
    ),
    # One absence sentence for two different facts — the tidier-looking version,
    # and it tells a person a record expired when none ever existed.
    "absence-one-sentence": (
        PAGE,
        "  if (reason === DIAGNOSTIC_NO_REFERENCE) {",
        "  if (false && reason === DIAGNOSTIC_NO_REFERENCE) {",
    ),
    # B14 rule 31: the job's uuid IS served (an engineer may need it to find the
    # run) and must not be drawn. Adding the row is the obvious "while I'm here".
    "draw-the-job-id": (
        PAGE,
        '            <dd>\n              <code className="font-mono text-sm">{record.job.kind}</code>\n            </dd>',
        '            <dd>\n              <code className="font-mono text-sm">{record.job.kind} {record.job.id}</code>\n            </dd>',
    ),
    # Hard-won law 2 pointed at the moment BEFORE the answer arrives: an absence
    # drawn optimistically states something the screen does not yet know.
    "absence-while-pending": (
        PAGE,
        "          {props.diagnostic === null && !props.diagnosticPending && (",
        "          {props.diagnostic === null && (",
    ),
    # The toggle back inside the six-filter grid, which is DEF-2376's own fault
    # on DEF-2376's own screen.
    #
    # ⚠ **THE FIRST DRAFT OF THIS SABOTAGE DID NOT REPRODUCE ANYTHING**: it gave
    # the toggle's own row `className="contents"`, which is a CSS display value
    # and moves NO DOM node — the checkbox stayed a child of the flex column and
    # `closest()` was right to say so. A sabotage that does not do the thing it
    # names makes a check look proved when nothing was proved (law 7, and DEF-182
    # one level up). This one MOVES the element, which is the only version that
    # can be wrong.
    "toggle-inside-the-grid": (
        PAGE,
        "          dateFormat={props.dateFormat}\n        />\n      </div>\n      {/* ── CR-067 B3",
        "          dateFormat={props.dateFormat}\n        />\n"
        "        <CheckboxField\n"
        '          id="f.outcome"\n'
        '          label={t("audit.filter.errorsOnly")}\n'
        "          checked={state.filters.outcome === AUDIT_OUTCOME_ERROR}\n"
        '          onChange={(checked) => set("outcome", checked ? AUDIT_OUTCOME_ERROR : "")}\n'
        "        />\n      </div>\n      {/* ── CR-067 B3",
    ),
    # ── the backend half ───────────────────────────────────────────────────
    # DEF-3321 exactly: the table is written, expires and is swept, and no route
    # serves it.
    "be-no-endpoint": (
        API,
        '    path("audit-log/<uuid:entry_id>/diagnostic", AuditEntryDiagnosticView.as_view()),\n',
        "",
    ),
    # The copy-paste a lane makes: every other route in this module carries
    # `AdminOrExecutive`, and BR-AUD-009 names both roles for the TRAIL.
    "be-gate-is-admin-or-executive": (
        API,
        "    permission_classes = [SystemAdminOnly]\n\n    def get(self, request, entry_id):\n"
        "        tenant_id = tenancy.require_tenant(request)\n"
        "        row = selectors.audit_entry(tenant_id, entry_id)\n"
        "        if row is None:\n"
        "            # Absent OR another tenant's row — ONE body for both (HR-1/G4), the",
        "    permission_classes = [AdminOrExecutive]\n\n    def get(self, request, entry_id):\n"
        "        tenant_id = tenancy.require_tenant(request)\n"
        "        row = selectors.audit_entry(tenant_id, entry_id)\n"
        "        if row is None:\n"
        "            # Absent OR another tenant's row — ONE body for both (HR-1/G4), the",
    ),
    # ⚠ **THE LEAK, AND THE FIRST DRAFT OF THIS SABOTAGE DID NOT REPRODUCE IT —
    # WHICH IS ITSELF THE FINDING (law 7's whole point).** That draft answered a
    # friendlier 404 body, and the suite stayed GREEN and was right to: the
    # friendlier body is served for an ABSENT id and a FOREIGN one alike, so
    # nothing is disclosed. `errors.NotFoundError` takes no message parameter at
    # all (`core/errors.py` — *"keeping cross-tenant and plain-absent bodies
    # byte-identical (no leak)"*), so the kernel had already made that mistake
    # unwritable.
    #
    # The leak is telling the two APART, and the natural way to write it is to
    # be helpful about a row that exists: *"it is there, you just cannot see
    # it."* That is what this does, and it is what HR-1/G4 forbid.
    "be-foreign-row-is-a-403": (
        API,
        "            raise errors.NotFoundError()\n        # A row whose detail has expired",
        "            if selectors.AuditLog.objects.filter(id=entry_id).exists():\n"
        "                raise errors.AuthError(errors.AUTH_PERMISSION_DENIED)\n"
        "            raise errors.NotFoundError()\n        # A row whose detail has expired",
    ),
    # The obvious reading of "there is no record" — and it makes an expired
    # diagnostic indistinguishable from another tenant's.
    "be-expired-is-a-404": (
        API,
        "        return Response(selectors.audit_diagnostic(row))",
        "        answer = selectors.audit_diagnostic(row)\n"
        "        if not answer['held']:\n"
        "            raise errors.NotFoundError()\n"
        "        return Response(answer)",
    ),
    # The tidier-looking version: one absence code instead of two.
    "be-one-absence-code": (
        STORE,
        '        return {"held": False, "reason": REASON_NO_REFERENCE, "reference": None, "record": None}',
        '        return {"held": False, "reason": REASON_NOT_HELD, "reference": None, "record": None}',
    ),
    # ⚠ **THE ONE THAT CANNOT BE DONE IN `payload()` AT ALL, WHICH IS THE POINT.**
    # `str(exc)` is stored by no column (task A2), so there is no message in the
    # record for a serializer to leak — the writer's SIGNATURE is the guarantee,
    # not the read. The only way to put a customer's account number on this wire
    # is to put it in the record first, so the sabotage goes where the mistake
    # would really be made: the "helpful" exception label in the kernel, which is
    # the exact slip `test_cr067_diagnostics.py` already records one layer down.
    "be-serve-the-message": (
        BACKEND / "core" / "diagnostics.py",
        '        "exception_type": type(exception).__name__,',
        '        "exception_type": f"{type(exception).__name__}: {exception}",',
    ),
    # B14 rule 31 — the row id served, and therefore renderable.
    "be-serve-the-row-id": (
        STORE,
        '        "reference": record.reference,\n        # The full 32 hex',
        '        "id": str(record.id),\n'
        '        "reference": record.reference,\n        # The full 32 hex',
    ),
    # The clause is written and the vocabulary is not: `parse_list_params` DROPS
    # an undeclared `f.<name>` (BR-SHL-011), so the whole list comes back 200.
    "be-filter-not-declared": (
        SELECTORS,
        '    "to",\n    "outcome",\n)',
        '    "to",\n)',
    ),
}

# `absence-as-a-paragraph` also has to close the element it opened.
TAIL_FIX = {
    "absence-as-a-paragraph": ("    </details>\n  );\n}", "    </div>\n  );\n}"),
    # …and `toggle-inside-the-grid` has to rename the one it left behind, or the
    # page carries the id twice and the test passes on whichever came first.
    "toggle-inside-the-grid": (
        '      <div className="flex flex-wrap items-center gap-3">\n        <CheckboxField\n          id="f.outcome"',
        '      <div className="flex flex-wrap items-center gap-3">\n        <CheckboxField\n          id="f.outcome-left-behind"',
    ),
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] == "--list":
        for name in SABOTAGES:
            print(name)
        return 0
    name = sys.argv[1]
    if name not in SABOTAGES:
        print(f"unknown sabotage {name!r}")
        return 2
    path, find, replace = SABOTAGES[name]
    original = path.read_text(encoding="utf-8")
    if find not in original:
        print(f"REFUSED: the anchor for {name!r} is not in {path.name} — the code moved")
        return 2
    broken = original.replace(find, replace, 1)
    if name in TAIL_FIX:
        tail_find, tail_replace = TAIL_FIX[name]
        broken = broken.replace(tail_find, tail_replace, 1)
    assert broken != original
    try:
        path.write_text(broken, encoding="utf-8")
        print(f"── sabotage: {name} ──────────────────────────────")
        if name.startswith("be-"):
            # The backend half. `-p no:randomly` is not needed and `-x` is not
            # wanted: the point is to see EVERY case the sabotage bites, so a
            # reader can tell a guard that caught it from one that happened to.
            subprocess.run(
                [
                    os.environ.get("SBH_PYTHON", "/home/user/SMARTBillHub/.venv/bin/python"),
                    "-m",
                    "pytest",
                    BACKEND_TEST,
                    "-q",
                    "--no-header",
                    "--reuse-db" if os.environ.get("DATABASE_URL") else "-p=no:cacheprovider",
                ],
                cwd=BACKEND,
                check=False,
            )
        else:
            subprocess.run(
                ["npx", "vitest", "run", TEST, "--reporter=basic"],
                cwd=HERE,
                check=False,
            )
    finally:
        path.write_text(original, encoding="utf-8")
        assert path.read_text(encoding="utf-8") == original
        print(f"── restored {path.name} ──")
    return 0


if __name__ == "__main__":
    sys.exit(main())
