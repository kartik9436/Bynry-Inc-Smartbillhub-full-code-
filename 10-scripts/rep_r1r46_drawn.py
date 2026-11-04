#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 · lane REP-REGISTER — the 46 report drawings on
#           p49-p73 of `05-prototype/09 Reports Build Brief.pdf`, read AS
#           IMAGES per B14 rule 42 at scale 4.
# Rules:    CLAUDE.md hard rules 2, 3, 4, 5, 8 · NFR-3 · BR-REP-021 (five
#           reports on the generic viewer BECAUSE their column sets are
#           unratified) · spec rule 7 (a seeder never chooses)
# Tests:    06-backend/tests/test_rep_r1r46_drawn_columns.py
# Impacts:  04-docs/05-modules/12-reports/02-business-rules.md §R1-R46 is
#           GENERATED from this file's `DRAWN` table.
# ───────────────────────────────────────────────────────
"""THE 46 DRAWINGS, AS DATA — so the PDF stops being the only copy.

⚠ **THIS FILE IS A TRANSCRIPTION, NOT A RATIFICATION.** Every column list
below is what the drawing SHOWS, in the order it draws it, and B14 rule 37
makes a drawn figure an illustration. `BR-REP-021` already puts five reports
on the generic viewer *because their column sets are unratified*, and
`reports/0003_seed_catalogue.py` deliberately seeds NO `columns` on any of the
46 for exactly that reason. **Nothing here is seeded and nothing here should
be.** What it buys is the measurement the seeder's docstring could not make:
how far a drawn column set is from the dataset the definition names.

WHY A SCRIPT AND NOT A PARAGRAPH
────────────────────────────────
CLAUDE.md: *"where a rule restates what a tool does, name the tool and let a
reader run it."* The gap arithmetic below changes the day a dataset gains a
column, so a sentence quoting a number would be wrong by the next commit.
Run `python3 10-scripts/rep_r1r46_drawn.py --report`.

WHAT THE NUMBERS MEAN, AND THE SECOND ONE MATTERS MORE
───────────────────────────────────────────────────────
`drawn` is how many columns the drawing heads. `declared` is how many the
definition's dataset publishes — and an EMPTY `columns` on the definition row
means *"every column the dataset declares"*, so `declared` is what a clerk
would actually see today. `overlap` is how many DRAWN headings correspond to a
declared column at all. ⚠ **`overlap` is routinely ZERO on a report whose rows
are AGGREGATES** — `R28 Read Completeness` heads ROUTE/READER/EXPECTED/ACTUAL
and `meter_reads` publishes one row per READ, so the generic viewer would not
show a wider version of that table, it would show a different table. A count
difference understates the gap; the overlap is the honest figure.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: `(register, page, drawn column headings in the drawn order)`.
#: Page is the rendered page number of the PDF, read as an image at scale 4.
#: A heading spanning two pages is recorded against the page its HEAD is on.
DRAWN: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    # ── Billing — 5 ─────────────────────────────────────────────────────────
    ("R4", 49, ("ACCOUNT", "CUSTOMER", "ROUTE", "CHECK", "DETAIL", "USAGE")),
    ("R5", 50, ("BILL #", "ACCOUNT", "CUSTOMER", "TYPE", "SERVICES", "USAGE", "AMOUNT", "FLAG")),
    ("R6", 50, ("DATE", "BILL #", "ACCOUNT", "REASON", "BY", "APPROVED BY", "AMOUNT")),
    ("R7", 51, ("BATCH", "CYCLE", "BILLS", "PAGES", "BUILT", "STATUS", "FILE")),
    ("R8", 51, ("ACCOUNT", "CUSTOMER", "CHANNEL", "ADDRESS", "SENT", "STATUS", "REASON")),
    # ── Receivables — 9 ─────────────────────────────────────────────────────
    ("R1", 51, ("METHOD", "TELLER", "COUNT", "AMOUNT", "SHARE")),
    ("R2", 52, ("BATCH", "DAY", "TENDER", "ITEMS", "AMOUNT", "STATUS")),
    ("R3", 52, ("DATE", "KIND", "PAYMENT", "ACCOUNT", "BY", "REASON", "AMOUNT")),
    ("R9", 53, ("ACCOUNT", "CUSTOMER", "CLASS", "CURRENT", "31-60", "61-90", "90+", "TOTAL")),
    ("R10", 53, ("ACCOUNT", "CUSTOMER", "SERVICE ADDRESS", "OLDEST BILL", "DAYS", "OWED", "ARRANGEMENT")),
    ("R11", 54, ("ACCOUNT", "CUSTOMER", "SERVICE ADDRESS", "OWED", "DAYS", "ELIGIBLE", "HOLD REASON")),
    ("R12", 54, ("DATE", "ACCOUNT", "KIND", "STAGE", "CHANNEL", "OUTCOME", "AMOUNT")),
    ("R13", 54, ("DATE", "ACCOUNT", "KIND", "REASON", "APPROVED BY", "AMOUNT")),
    ("R14", 55, ("ACCOUNT", "CUSTOMER", "FINAL BILL", "FORWARDING ADDRESS", "OUTCOME", "BALANCE")),
    # ── Finance — 9 ─────────────────────────────────────────────────────────
    ("R15", 55, ("ACCOUNT", "NAME", "OPENING", "DEBITS", "CREDITS", "CLOSING")),
    ("R16", 56, ("BATCH", "PERIOD", "ENTRIES", "LINES", "VALUE", "EXPORTED", "FILE")),
    ("R17", 56, ("SERVICE", "RATE SCHEDULE", "ACCOUNTS", "USAGE", "USAGE REV", "BASE", "TAX", "TOTAL")),
    ("R18", 57, ("AUTHORITY", "TAX", "BASIS", "TAXABLE", "RATE", "COLLECTED", "REMITTED", "DUE")),
    ("R19", 57, ("DATE", "REFERENCE", "DESCRIPTION", "SYSTEM", "BANK", "STATUS")),
    ("R20", 58, ("ACCOUNT", "CUSTOMER", "CLASS", "TAKEN", "AMOUNT", "APPLIED", "HELD")),
    ("R21", 58, ("CHECK", "SOURCE A", "VALUE A", "SOURCE B", "VALUE B", "DIFFERENCE", "RESULT")),
    # ⚠ R42 is NOT drawn — it became Tab 2 by PO ruling. No columns, on purpose.
    ("R42", 58, ()),
    ("R43", 59, ("PERIOD", "REVENUE", "TARGET", "COLLECTED", "RATE", "DSO", "ACCOUNTS", "REBILLS")),
    # ── Customers — 9 ───────────────────────────────────────────────────────
    ("R22", 59, ("ACCOUNT", "CUSTOMER", "PREMISES", "CLASS", "SERVICES", "STATUS", "OPENED", "BALANCE")),
    ("R23", 60, ("DATE", "ACCOUNT", "CUSTOMER", "EVENT", "PREMISES", "BY", "EFFECTIVE")),
    # R24/R25 are ONE definition each drawn at FOUR subjects. Each subject's
    # own heading row is recorded; the definition's `drawn` is the WIDEST.
    ("R24a", 69, ("DATE", "REFERENCE", "DESCRIPTION", "CHARGES", "CREDITS", "BALANCE")),
    ("R24b", 70, ("ACCOUNT", "PREMISES", "SERVICE", "OPENING", "CHARGES", "CREDITS", "CLOSING")),
    ("R24c", 70, ("ACCOUNT", "UNIT", "CUSTOMER", "KIND", "CHARGES", "CREDITS", "CLOSING")),
    ("R24d", 71, ("DATE", "REFERENCE", "OCCUPANT", "DESCRIPTION", "CHARGES", "CREDITS", "BALANCE")),
    ("R25a", 71, ("DATE", "TYPE", "REFERENCE", "DETAIL", "DEBIT", "CREDIT", "BALANCE")),
    ("R25b", 72, ("ACCOUNT", "GL ACCOUNT", "NAME", "DEBIT", "CREDIT", "CLOSING")),
    ("R25c", 72, ("ACCOUNT", "UNIT", "KIND", "DEBIT", "CREDIT", "CLOSING")),
    ("R25d", 73, ("DATE", "TYPE", "REFERENCE", "OCCUPANT", "DEBIT", "CREDIT", "BALANCE")),
    ("R26", 60, ("FINDING", "SEVERITY", "COUNT", "EXAMPLE", "EFFECT", "FIX IN")),
    ("R27", 61, ("PROGRAMME", "ACCOUNT", "CUSTOMER", "SINCE", "TERMS", "INSTALMENT", "REMAINING", "STATUS")),
    # ⚠ R44's sixth cell is an unheaded ACTION column (`↓ PDF` / `View`).
    # Counted as five HEADED columns; the action is furniture, not a column.
    ("R44", 61, ("DATE", "TYPE", "DESCRIPTION", "AMOUNT", "STATUS")),
    ("R45", 62, ("PERIOD", "READ DATE", "READING", "USAGE", "UNIT", "DAYS", "PER DAY", "BASIS")),
    ("R46", 62, ("COMPONENT", "BASIS", "QUANTITY", "UNIT", "RATE", "PROJECTED")),
    # ── Operations — 7 ──────────────────────────────────────────────────────
    ("R28", 63, ("ROUTE", "READER", "EXPECTED", "ACTUAL", "ESTIMATED", "SKIPPED", "MISSING", "COMPLETE")),
    ("R29", 63, ("ACCOUNT", "METER", "RULE", "PRIOR", "THIS READ", "CHANGE", "UNIT", "STATUS")),
    ("R30", 63, ("RANK", "ACCOUNT", "CUSTOMER", "CLASS", "USAGE", "UNIT", "SHARE", "BILLED")),
    ("R31", 64, ("METER", "TYPE", "SIZE", "PREMISES", "INSTALLED", "AGE", "LAST READ", "STATUS")),
    ("R32", 64, ("DATE", "FILE", "SOURCE", "ROWS", "ACCEPTED", "REJECTED", "BY", "DETAIL")),
    ("R33", 65, ("ORDER", "TYPE", "PREMISES", "RAISED", "ASSIGNED", "COMPLETED", "DAYS", "STATUS")),
    ("R34", 65, ("ACCOUNT", "CUSTOMER", "BALANCE", "NOTICE", "DISCONNECTED", "PAID", "RECONNECTED", "STATUS")),
    # ── Compliance — 7 ──────────────────────────────────────────────────────
    ("R35", 66, ("WHEN", "ACTOR", "ACTION", "OBJECT", "BEFORE", "AFTER", "WHERE")),
    ("R36", 66, ("USER", "ROLE", "ADDED", "ADDED BY", "LAST SIGN-IN", "APPROVE MONEY", "STATUS")),
    ("R37", 67, ("EFFECTIVE", "SCHEDULE", "SERVICE", "COMPONENT", "WAS", "NOW", "CHANGE", "BY")),
    ("R38", 67, ("DATE", "REFERENCE", "ACCOUNT", "REASON", "AMOUNT", "RAISED BY", "APPROVED BY", "INVOICE")),
    ("R39", 68, ("SECTION", "LINE", "MEASURE", "VALUE", "UNIT", "SOURCE")),
    ("R40", 68, ("MEASURE", "OURS", "THEIRS", "DIFFERENCE", "IN TRANSIT", "RESULT")),
    ("R41", 69, ("CHECK", "LEGACY", "LOADED", "DIFFERENCE", "TOLERANCE", "RESULT")),
)

#: A drawn HEADING is a clerk's word; a dataset column is a code. These are the
#: pairs where the two are the same fact under two spellings, hand-checked
#: against the drawing and `apps/reports/datasets.py`. ⚠ **A pair is recorded
#: ONLY where the drawn cell holds the dataset's own value** — `R9`'s `TOTAL` is
#: `payments.total` and is listed; `R21`'s `VALUE A` is a tie-out side and is
#: NOT `payments.total`, so it is not.
ALIASES: dict[str, str] = {
    "account": "account_no",
    "bill #": "invoice_no",
    "customer": "customer_name",
    "name": "customer_name",
    "type": "bill_type",
    "services": "services",
    "usage": "usage",
    "amount": "amount",
    "flag": "flag",
    "unit": "usage_unit",
    "method": "method_name",
    "teller": "teller",
    "share": "share_pct",
    "current": "current",
    "31-60": "d31_60",
    "61-90": "d61_90",
    "90+": "d90_plus",
    "total": "total",
    "meter": "meter_no",
    "read date": "read_on",
    "reading": "reading",
    "premises": "premises_no",
    "size": "size",
    "status": "status",
    "actor": "actor",
    "action": "action",
    "role": "actor_role",
    "reason": "reason",
    "channel": "channel",
    "order": "order_no",
    "crew": "crew",
    "days": "duration",
    "debit": "debit",
    "credit": "credit",
    "balance": "balance",
    "gl account": "account_code",
    "reference": "reference",
    "last sign-in": "last_sign_in_at",
    "added by": "added_by",
    "basis": "read_basis",
    "service": "service_code",
    "schedule": "schedule_code",
    "effective": "effective_from",
    "class": "account_class",
    "opened": "opened_on",
    "installed": "installed_on",
    "last read": "last_read_on",
}


def _slug(heading: str) -> str:
    return re.sub(r"[^a-z0-9+#\- ]", "", heading.lower()).strip()


def load_datasets(repo: Path):
    sys.path.insert(0, str(repo / "06-backend"))
    from apps.reports import datasets  # noqa: PLC0415

    return datasets


def definitions(repo: Path) -> dict[str, tuple[str, str, str]]:
    """`{register: (key, name, dataset)}` read from the seed migration itself,
    never re-typed — the seed is the source of truth for what each R-row IS."""
    path = repo / "06-backend/apps/reports/migrations/0003_seed_catalogue.py"
    rows: dict[str, tuple[str, str, str]] = {}
    pattern = re.compile(
        r'\(\s*"(R\d+)",\s*"([a-z0-9_]+)",\s*"([^"]+)",\s*"([a-z_]+)",\s*"([a-z_]+)",\s*"([a-z_]+)"'
    )
    for match in pattern.finditer(path.read_text()):
        register, key, name, group, sub_group, dataset = match.groups()
        rows[register] = (key, name, dataset, group, sub_group)
    return rows


def measure(repo: Path):
    datasets = load_datasets(repo)
    defs = definitions(repo)
    out = []
    for register, page, drawn in DRAWN:
        base = re.sub(r"[a-d]$", "", register)
        meta = defs.get(base)
        if meta is None:
            out.append((register, page, drawn, None, None, None))
            continue
        key, name, code, group, sub = meta
        dataset = datasets.BY_CODE.get(code)
        declared = tuple(column.name for column in dataset.columns) if dataset else ()
        overlap = sum(
            1 for heading in drawn if ALIASES.get(_slug(heading), _slug(heading).replace(" ", "_")) in declared
        )
        out.append((register, page, drawn, (key, name, code, group, sub), declared, overlap))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    repo = Path(args.repo)
    rows = measure(repo)

    datasets = load_datasets(repo)
    codes = {dataset.code for dataset in datasets.DATASETS}

    print(f"{'REG':5s} {'p':>3s} {'drawn':>5s} {'declared':>8s} {'diff':>5s} {'overlap':>7s}  dataset")
    differ = 0
    unresolved = []
    widest = []
    for register, page, drawn, meta, declared, overlap in rows:
        if meta is None:
            unresolved.append((register, "no seeded definition row"))
            continue
        code = meta[2]
        if code not in codes:
            unresolved.append((register, f"dataset {code!r} is not one of the nine"))
        diff = len(declared) - len(drawn)
        if register == "R42":
            print(f"{register:5s} {page:3d} {'-':>5s} {len(declared):8d} {'-':>5s} {'-':>7s}  {code}   (not drawn — Tab 2)")
            continue
        if diff:
            differ += 1
            widest.append((diff, register, len(drawn), len(declared)))
        print(f"{register:5s} {page:3d} {len(drawn):5d} {len(declared):8d} {diff:+5d} {overlap:7d}  {code}")

    widest.sort(reverse=True)
    print()
    print(f"drawn definitions measured     : {len([r for r in rows if r[0] != 'R42'])}")
    print(f"drawn set != declared set      : {differ}")
    print("worst three by size            : " + ", ".join(
        f"{reg} ({drawn}->{decl}, +{diff})" for diff, reg, drawn, decl in widest[:3]
    ))
    zero = [r[0] for r in rows if r[5] == 0 and r[0] != "R42"]
    print(f"drawn headings that match NO declared column: {len(zero)} — {', '.join(zero)}")
    print(f"datasets declared in code      : {len(codes)} — {', '.join(sorted(codes))}")
    print(f"R-rows whose dataset does not resolve: {len(unresolved)}")
    for register, why in unresolved:
        print(f"  {register}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
