#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-007 (S36 Revenue & AR) · US-LED-014 (S41 remittance) — the
#           reads this sweep protects. No US-ID is CLAIMED as shipped here; this
#           is an operational check, not a story surface.
# Rules:    CLAUDE.md rule 2 (money is NUMERIC(18,6) **and** CHAR(3)) ·
#           BR-TEN-042 (a tenant's currency locks once a financial record
#           exists) · BR-LED-007 (drift is a red flag) · hard rule 1 (no tenant
#           table is read without a tenant scope — see the RLS note below)
# Tests:    06-backend/tests/test_def_081_mixed_currency_book.py (the guard this
#           sweep is the operational half of)
# Impacts:  apps/ledger/reporting.py (which now REFUSES what this finds)
# ───────────────────────────────────────────────────────
"""DEF-081's second half: **which live tenants already hold a mixed book?**

The defect asks for two things and the guard in `apps/ledger/reporting.py` is
only the first. *"Also wanted: a one-off check of live tenants for more than one
distinct currency in `journal_lines`, because DEF-075 was open for as long as
billing had invoices."*

**WHY A SEPARATE SCRIPT AND NOT A TEST.** A test proves the code refuses. It
cannot tell anybody whether a REAL utility's books are already mixed, and that
is the operationally urgent question: from today the affected tenant's finance
screens stop answering, and somebody has to know which tenant that is BEFORE
they phone in. The guard makes a wrong number impossible; this tells you who is
about to see a refusal.

**WHAT IT DOES.** One query per database it is pointed at:

    SELECT tenant_id, COUNT(DISTINCT currency), STRING_AGG(DISTINCT currency)
    FROM journal_entries GROUP BY tenant_id HAVING COUNT(DISTINCT currency) > 1

plus the same over POSTED entries only, because a draft is not in the books
(BR-LED-003) and a mixed draft is a smaller problem than a mixed ledger — it can
still be deleted, and telling an operator they are equally serious would waste
the trip.

**IT READS AND IT NEVER WRITES.** Not one UPDATE, not one INSERT, no `ALTER`.
A mixed book is corrected by REVERSING the foreign entries through the posting
service and reposting them (hard rule 4: the correction is new rows, never an
edit), which is a decision about real money that no script may take.

**ON RLS.** This runs as the connection's own role and deliberately does NOT set
`app.tenant_id`: its whole question is *"across all tenants, who is affected?"*,
which no tenant-scoped session can answer. That is why it is an operator script
run against a database by hand and not an application code path — an app-layer
read that bypassed tenant scope would be exactly what hard rule 1 forbids. The
`smartbillhub` role owns the tables, so `FORCE ROW LEVEL SECURITY` applies to it
too; run it as a superuser or a `BYPASSRLS` role, and it says so and exits
cleanly rather than reporting a comforting empty result if it cannot see rows.

    python3 10-scripts/def081_currency_sweep.py \\
        "postgres://user:pw@host:5432/smartbillhub"

Exit status: **0** nothing mixed · **1** at least one tenant holds a mixed book
(so CI or a deploy check can gate on it) · **2** it could not answer.
"""

from __future__ import annotations

import os
import sys

MIXED_ENTRIES_SQL = """
SELECT
    e.tenant_id::text          AS tenant_id,
    COUNT(DISTINCT e.currency) AS codes,
    STRING_AGG(DISTINCT e.currency, ', ' ORDER BY e.currency) AS currencies,
    COUNT(*)                   AS entries
FROM journal_entries e
GROUP BY e.tenant_id
HAVING COUNT(DISTINCT e.currency) > 1
ORDER BY e.tenant_id;
"""

#: The same question over the BOOKS rather than over the table. A draft is
#: *"worthless until posted"* (BR-LED-003) and can still be deleted, so a mixed
#: DRAFT set is a warning and a mixed POSTED set is the defect.
MIXED_POSTED_SQL = """
SELECT
    e.tenant_id::text          AS tenant_id,
    COUNT(DISTINCT e.currency) AS codes,
    STRING_AGG(DISTINCT e.currency, ', ' ORDER BY e.currency) AS currencies,
    COUNT(*)                   AS entries
FROM journal_entries e
WHERE e.status = 'posted'
GROUP BY e.tenant_id
HAVING COUNT(DISTINCT e.currency) > 1
ORDER BY e.tenant_id;
"""

#: A tenant whose POSTED books disagree with the currency it has DECLARED. Not
#: the same finding and it is the one DEF-075 predicts: the declared code was
#: changed at 200 OK while issued bills existed, so the books are still in the
#: old money and every screen was labelling them with the new.
DECLARED_MISMATCH_SQL = """
SELECT
    t.id::text        AS tenant_id,
    t.subdomain       AS subdomain,
    t.currency        AS declared,
    STRING_AGG(DISTINCT e.currency, ', ' ORDER BY e.currency) AS in_the_books
FROM tenants t
JOIN journal_entries e ON e.tenant_id = t.id AND e.status = 'posted'
GROUP BY t.id, t.subdomain, t.currency
HAVING COUNT(DISTINCT e.currency) = 1
   AND MIN(e.currency) IS DISTINCT FROM t.currency
ORDER BY t.subdomain;
"""

#: Proof the connection can actually SEE journal entries. An RLS-filtered
#: session returns zero rows from every query above and would report "clean"
#: with total confidence — the single most dangerous outcome this script could
#: have, and the reason it refuses to report anything until this is non-zero.
VISIBILITY_SQL = "SELECT COUNT(*) FROM journal_entries;"


def _connect(url: str):
    try:
        import psycopg
    except ImportError:  # pragma: no cover — the backend venv always has it
        print("psycopg is not installed; run this from the 06-backend environment.")
        raise SystemExit(2)
    return psycopg.connect(url)


def _rows(cursor, sql: str) -> list[tuple]:
    cursor.execute(sql)
    return list(cursor.fetchall())


def main(argv: list[str]) -> int:
    url = argv[1] if len(argv) > 1 else os.environ.get("DATABASE_URL", "")
    if not url:
        print(
            "usage: def081_currency_sweep.py <DATABASE_URL>\n"
            "       (or set DATABASE_URL). Point it at each LIVE database in turn — "
            "one tenant's books can only be mixed within the database that holds them."
        )
        return 2

    with _connect(url) as connection, connection.cursor() as cursor:
        try:
            visible = _rows(cursor, VISIBILITY_SQL)[0][0]
        except Exception as problem:  # UndefinedTable, permission denied, …
            # Reported and NOT treated as clean. A database with no ledger
            # tables is a real operator situation (a fresh host, the wrong URL),
            # and "0 findings" is the one answer it must never produce.
            connection.rollback()
            print(f"REFUSING TO REPORT: journal_entries could not be read — {problem}")
            return 2
        if visible == 0:
            print(
                "REFUSING TO REPORT: this connection can see 0 journal entries.\n"
                "That is either a genuinely empty database or — far more likely — an "
                "RLS-filtered session, and the two are indistinguishable from here. A "
                "sweep that answered 'clean' from a filtered session would be the worst "
                "possible result: a confident all-clear that looked at nothing. Re-run as "
                "a superuser or a BYPASSRLS role."
            )
            return 2

        print(f"journal_entries visible to this connection: {visible}\n")

        posted = _rows(cursor, MIXED_POSTED_SQL)
        drafts_too = _rows(cursor, MIXED_ENTRIES_SQL)
        mismatched = _rows(cursor, DECLARED_MISMATCH_SQL)

        if posted:
            print("MIXED POSTED BOOKS — these tenants' finance reports now REFUSE:")
            for tenant_id, codes, currencies, entries in posted:
                print(
                    f"  tenant {tenant_id}: {codes} currencies ({currencies}) over {entries} "
                    "posted entries"
                )
            print(
                "\n  Each one is corrected by REVERSING the foreign entries through the "
                "posting service and reposting them in the tenant's own currency — new "
                "rows, never an edit (hard rule 4). The S56 journal list still works on "
                "these tenants and is where the entries are found.\n"
            )
        else:
            print("MIXED POSTED BOOKS: none. No tenant's ledger reports will refuse.\n")

        draft_only = [row for row in drafts_too if row[0] not in {r[0] for r in posted}]
        if draft_only:
            print("MIXED DRAFTS ONLY (not yet in the books, still deletable):")
            for tenant_id, codes, currencies, entries in draft_only:
                print(
                    f"  tenant {tenant_id}: {codes} currencies ({currencies}) over {entries} "
                    "entries"
                )
            print()

        if mismatched:
            print("BOOKS IN ONE CURRENCY, TENANT DECLARES ANOTHER — the DEF-075 shape:")
            for tenant_id, subdomain, declared, in_the_books in mismatched:
                print(
                    f"  {subdomain} ({tenant_id}): declares {declared}, books hold "
                    f"{in_the_books}"
                )
            print(
                "\n  These reports still ANSWER — the books are internally consistent — but "
                "every figure was being LABELLED with the declared code. Since DEF-081 the "
                "label is derived from the entries, so the screens are now correct and the "
                "declared code is what needs fixing.\n"
            )

    return 1 if posted else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-007@e3b0c44 (sources, in order: 12-governance/10-defect-log.csv DEF-081 "Also wanted: a one-off check of live tenants for more than one distinct currency in journal_lines" + DEF-075 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-003/BR-LED-007 · CLAUDE.md hard rule 2)
# generated: 2026-08-15 by the money-correctness lane (DEF-081)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — an operator script) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: run against the lane's own PostgreSQL database (sbh_money_lane) both
#         ways — with a genuinely mixed book present it exits 1 and NAMES the
#         tenant and the two codes; against the clean seed it exits 0
# exceptions: it deliberately runs with NO `app.tenant_id` set, because its
#         question is cross-tenant by nature and no tenant-scoped session can
#         answer it — which is exactly why it is an operator script and not an
#         application read path (hard rule 1) · it REFUSES to report anything
#         when it can see zero journal entries, because an RLS-filtered session
#         and an empty database are indistinguishable from inside and the
#         comforting answer is the wrong one · READ ONLY: correcting a mixed
#         book is a reversal through the posting service, which is a decision
#         about real money and not a script's to take
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
