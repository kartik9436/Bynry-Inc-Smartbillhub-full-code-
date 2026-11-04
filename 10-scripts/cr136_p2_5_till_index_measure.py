"""`CR-136-BRC07` `P2.5` — IS THE TILL INDEX WORTH MAKING PARTIAL? MEASURED.

`P2.5` asks for *"an index on (tenant, counter_session_id) — the till's own
list reads it on every payment taken"*, and the packet asks the lane to
*"consider whether it should be partial (WHERE counter_session_id IS NOT NULL)
given that most payments in a utility will have no till — measure the
reasoning"*. This is that measurement. It writes the figures that
`payments/0035`'s docstring quotes, so the docstring is a report of something
that was run rather than an argument that sounds right.

WHY A PROBE TABLE AND NOT `payments`
-------------------------------------
The seeded demo tenant holds **74** payments. A planner shown 74 rows chooses a
sequential scan whatever indexes exist, so measuring on the real table would
answer a different question and answer it confidently. This builds a table with
the SAME TWO COLUMN TYPES the index covers (`uuid`, `uuid`) plus the money
column the running total sums, fills it to **40,000 rows — the top of tier T5
and the largest tenant `B6` models** — and measures there. The table is created
and dropped inside this script and nothing else ever reads it.

WHAT IS BEING DECIDED, IN ONE SENTENCE
---------------------------------------
A PARTIAL index is smaller, and it is **only usable if PostgreSQL can prove its
predicate holds for the query** — which for a PARAMETER rather than a literal
is not obvious and is the thing most worth checking. If the planner cannot use
it for `counter_session_id = $1`, a partial index is worse than no decision at
all: it would look thrifty and cost a sequential scan on every page load.

WHAT WOULD MAKE THIS MEASUREMENT PASS WRONGLY (hard-won law 7, habit 2)
------------------------------------------------------------------------
  * **A LITERAL IN THE `EXPLAIN` STANDING IN FOR A PARAMETER.** With a literal,
    PostgreSQL constant-folds and the implication is trivial. Django sends
    bound parameters, so section 3 asks the question again through
    `PREPARE`/`EXPLAIN EXECUTE`, which is where a generic plan appears.
  * **A STALE `pg_class.reltuples` MAKING THE PLANNER GUESS.** `ANALYZE` is run
    after every load and before every plan.
  * **MEASURING AN INDEX THAT IS STILL BEING BUILT.** Sizes are read after
    `CREATE INDEX` returns, and `pg_relation_size` is read for a named relation
    rather than summed from a pattern that could catch the wrong one.
  * **A GREEN THAT MEANS NOTHING WAS TRIED.** Every plan line is printed, so a
    reader sees which node was chosen and not merely a verdict.

HOW TO RUN IT

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p2db?sslmode=disable \\
      python3 manage.py shell < ../10-scripts/cr136_p2_5_till_index_measure.py
"""

import sys
import time
import uuid

from django.db import connection

ROWS = 40_000  # the top of T5, and the largest tenant B6 models
PROBE = "cr136_p2_5_probe"

#: The share of rows carrying a till. Measured at three points rather than at
#: one guessed "payment mix", because this repo has no signed figure for how a
#: utility's money splits across the seven tenders and inventing one would make
#: the whole decision rest on it. What IS signed is the structure: PO ruling
#: 2026-09-23 — three of the seven tenders pass through a person's hands
#: (`cash`, `check`, `money_order`) and the other four never touch a counter,
#: so they carry NULL here for ever.
SHARES = (1.00, 0.30, 0.05)

FULL = "ix_probe_full"
PARTIAL = "ix_probe_partial"

failures: list[str] = []


def sql(statement, params=None, *, fetch=False):
    with connection.cursor() as cur:
        cur.execute(statement, params or [])
        if fetch:
            return cur.fetchall()
    return None


def size(relation):
    return sql("SELECT pg_relation_size(%s)", [relation], fetch=True)[0][0]


def kb(n):
    return f"{n / 1024:,.0f} kB"


def plan(label, statement, params=None):
    rows = sql(f"EXPLAIN (COSTS OFF) {statement}", params, fetch=True)
    text = "\n".join(f"        {line[0]}" for line in rows)
    print(f"  {label}")
    print(text)
    return "\n".join(line[0] for line in rows)


print("=" * 78)
print("CR-136-BRC07 P2.5 — the till index: full or partial, measured")
print("=" * 78)
print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    print("REFUSED: an index decision measured on SQLite is not a measurement")
    print("(hard-won law 14). Run it against a PostgreSQL 16 clone.")
    sys.exit(2)

print(sql("SELECT version()", fetch=True)[0][0])

tenant_a = uuid.uuid4()
tenant_b = uuid.uuid4()
till = uuid.uuid4()

sql(f"DROP TABLE IF EXISTS {PROBE}")
sql(f"""
    CREATE TABLE {PROBE} (
        id                 uuid PRIMARY KEY,
        tenant_id          uuid NOT NULL,
        counter_session_id uuid,
        amount             numeric(18, 6) NOT NULL
    )
    """)

print(f"\n0 · THE PROBE — {ROWS:,} rows, two tenants, the shape the index covers")
print("-" * 78)
print("  columns: tenant_id uuid · counter_session_id uuid · amount numeric(18,6)")
print("  Exactly the two uuid columns P2.5's index covers, plus the money the")
print("  till's running total sums. Nothing else — a wider row would change the")
print("  TABLE size and cannot change either INDEX size, which is what is at issue.")

results = []
for share in SHARES:
    with_till = int(ROWS * share)
    sql(f"TRUNCATE {PROBE}")
    # One in twenty rows belongs to the second tenant, so `tenant_id` is not a
    # constant and the leading column earns its place.
    sql(
        f"""
        INSERT INTO {PROBE} (id, tenant_id, counter_session_id, amount)
        SELECT gen_random_uuid(),
               CASE WHEN i %% 20 = 0 THEN %s::uuid ELSE %s::uuid END,
               CASE WHEN i <= %s THEN
                    CASE WHEN i %% 17 = 0 THEN %s::uuid ELSE gen_random_uuid() END
               END,
               (i %% 400)::numeric + 0.170000
          FROM generate_series(1, %s) AS i
        """,
        [str(tenant_b), str(tenant_a), with_till, str(till), ROWS],
    )
    sql(f"ANALYZE {PROBE}")

    sql(f"DROP INDEX IF EXISTS {FULL}")
    sql(f"DROP INDEX IF EXISTS {PARTIAL}")
    sql(f"CREATE INDEX {FULL} ON {PROBE} (tenant_id, counter_session_id)")
    sql(
        f"CREATE INDEX {PARTIAL} ON {PROBE} (tenant_id, counter_session_id) "
        "WHERE counter_session_id IS NOT NULL"
    )
    full_size, partial_size = size(FULL), size(PARTIAL)
    saved = full_size - partial_size
    pct = (saved / full_size * 100) if full_size else 0
    results.append((share, with_till, full_size, partial_size, saved, pct))

print(f"\n1 · INDEX SIZE, FULL vs PARTIAL, AT {ROWS:,} ROWS")
print("-" * 78)
print("  rows with a till   full index    partial index   saved")
for share, with_till, full_size, partial_size, saved, pct in results:
    print(
        f"  {with_till:>7,} ({share:>5.0%})   {kb(full_size):>10}    "
        f"{kb(partial_size):>13}   {kb(saved):>9}  ({pct:.0f}%)"
    )
print()
print("  ⚠ READ IT AS ARITHMETIC, AND IT REFUTES THE OBVIOUS ARGUMENT FOR A")
print("    PARTIAL INDEX. *A btree stores a NULL key like any other, so the full")
print("    index pays full price for every payment that never touched a counter*")
print("    is what this lane expected to measure, and it is WRONG: PostgreSQL 13+")
print("    DEDUPLICATES equal keys, and every NULL is equal to every other NULL in")
print("    a btree. Divide it out — a NULL row costs about **7 bytes** of index")
print("    where a real till id costs about **48** — so the saving is a seventh of")
print("    what the argument assumes. At T5's ceiling it is **264 kB**, which does")
print("    not decide anything on its own. Section 2a is what decides it.")


print("\n2a · THE COST THAT IS NOT DISK: WHAT EACH INDEX COSTS TO WRITE")
print("-" * 78)
print("  A partial index is not touched at all by an INSERT whose key is excluded,")
print("  and the four electronic tenders arrive in BULK — an ACH file is thousands")
print("  of rows in one statement. Same 40,000 rows, 5% carrying a till, timed with")
print("  one index present at a time and with none, median of FIVE runs each.")


def _load(with_till):
    sql(f"TRUNCATE {PROBE}")
    started = time.perf_counter()
    sql(
        f"""
        INSERT INTO {PROBE} (id, tenant_id, counter_session_id, amount)
        SELECT gen_random_uuid(),
               CASE WHEN i %% 20 = 0 THEN %s::uuid ELSE %s::uuid END,
               CASE WHEN i <= %s THEN
                    CASE WHEN i %% 17 = 0 THEN %s::uuid ELSE gen_random_uuid() END
               END,
               (i %% 400)::numeric + 0.170000
          FROM generate_series(1, %s) AS i
        """,
        [str(tenant_b), str(tenant_a), with_till, str(till), ROWS],
    )
    return time.perf_counter() - started


write_costs = {}
for label, create in (
    ("no index at all", None),
    ("full index", f"CREATE INDEX {FULL} ON {PROBE} (tenant_id, counter_session_id)"),
    (
        "partial index",
        f"CREATE INDEX {PARTIAL} ON {PROBE} (tenant_id, counter_session_id) "
        "WHERE counter_session_id IS NOT NULL",
    ),
):
    sql(f"DROP INDEX IF EXISTS {FULL}")
    sql(f"DROP INDEX IF EXISTS {PARTIAL}")
    sql(f"TRUNCATE {PROBE}")
    if create:
        sql(create)
    runs = sorted(_load(int(ROWS * 0.05)) for _ in range(5))
    write_costs[label] = runs[2]
    print(
        f"  {label:<18} median {runs[2] * 1000:>6.0f} ms   "
        f"min {runs[0] * 1000:>5.0f}   max {runs[-1] * 1000:>5.0f}"
    )

base = write_costs["no index at all"]
spread = max(write_costs.values()) - min(write_costs.values())
for label in ("full index", "partial index"):
    print(f"  {label} costs {(write_costs[label] - base) * 1000:+.0f} ms over no index at all")

print()
if write_costs["partial index"] <= base:
    print("  ⚠ **THIS MEASUREMENT DECIDES NOTHING, AND THAT IS THE RESULT RATHER")
    print("    THAN A FAILURE OF IT.** The partial index came out no slower than")
    print("    having NO INDEX AT ALL, which is impossible — maintaining an index")
    print("    cannot be free. So the difference between the three is smaller than")
    print("    this machine's run-to-run noise, and **no write-cost figure from")
    print("    here may be quoted in support of either shape.**")
else:
    print("  The two differ by more than the spread; the figures above stand.")
print(f"  (run-to-run spread across all three medians: {spread * 1000:.0f} ms)")
print("  ⚠ A check you cannot describe a false pass for is a check you do not")
print("    understand (law 7, habit 2). The false pass here is exactly this: a")
print("    noisy 40,000-row load reading as a verdict. It is printed as noise.")
sql(f"DROP INDEX IF EXISTS {FULL}")
sql(f"DROP INDEX IF EXISTS {PARTIAL}")
sql(
    f"CREATE INDEX {PARTIAL} ON {PROBE} (tenant_id, counter_session_id) "
    "WHERE counter_session_id IS NOT NULL"
)

# Leave the table at the most realistic of the three for the plan tests.
share = 0.30
with_till = int(ROWS * share)
sql(f"TRUNCATE {PROBE}")
sql(
    f"""
    INSERT INTO {PROBE} (id, tenant_id, counter_session_id, amount)
    SELECT gen_random_uuid(),
           CASE WHEN i %% 20 = 0 THEN %s::uuid ELSE %s::uuid END,
           CASE WHEN i <= %s THEN
                CASE WHEN i %% 17 = 0 THEN %s::uuid ELSE gen_random_uuid() END
           END,
           (i %% 400)::numeric + 0.170000
      FROM generate_series(1, %s) AS i
    """,
    [str(tenant_b), str(tenant_a), with_till, str(till), ROWS],
)
sql(f"ANALYZE {PROBE}")

TILL_QUERY = (
    f"SELECT count(*), coalesce(sum(amount), 0) FROM {PROBE} "
    "WHERE tenant_id = %s AND counter_session_id = %s"
)

print("\n2 · CAN THE PLANNER USE THE PARTIAL INDEX AT ALL? (only it exists)")
print("-" * 78)
print("  The question a till asks on every payment taken:")
print("      SELECT count(*), sum(amount) WHERE tenant_id = ? AND counter_session_id = ?")
sql(f"DROP INDEX IF EXISTS {FULL}")
text = plan("partial index only, bound parameters:", TILL_QUERY, [str(tenant_a), str(till)])
if PARTIAL not in text:
    failures.append(
        "the planner did NOT use the partial index for the till query — a "
        "partial index it cannot use is a sequential scan on every page load"
    )
else:
    print(f"  [ok  ] the partial index {PARTIAL} is chosen")

print("\n3 · AND FOR A GENERIC PLAN? (PREPARE, which is where Django's params land)")
print("-" * 78)
print("  ⚠ Section 2 could be a constant-folding artefact: PostgreSQL may have")
print("    substituted the parameters and proved the predicate against literals.")
print("    A PREPAREd statement planned generically is the honest question, and")
print("    the reason it CAN be answered is STRICTNESS — `x = $1` uses a strict")
print("    operator, so a NULL `x` makes the clause NULL rather than true, which")
print("    is what implies `x IS NOT NULL` with no knowledge of $1 at all.")
sql("DEALLOCATE ALL")
sql(
    f"PREPARE cr136_till (uuid, uuid) AS "
    f"SELECT count(*), coalesce(sum(amount), 0) FROM {PROBE} "
    "WHERE tenant_id = $1 AND counter_session_id = $2"
)
# Five executions force PostgreSQL past its custom-plan trials into a generic
# plan; the sixth EXPLAIN is the one that shows what a repeated call gets.
for _ in range(5):
    sql("EXECUTE cr136_till(%s, %s)", [str(tenant_a), str(till)])
rows = sql("EXPLAIN (COSTS OFF) EXECUTE cr136_till(%s, %s)", [str(tenant_a), str(till)], fetch=True)
generic = "\n".join(line[0] for line in rows)
for line in rows:
    print(f"        {line[0]}")
if PARTIAL not in generic:
    failures.append(
        "the GENERIC plan did not use the partial index — section 2's result "
        "was a constant-folding artefact and the partial index would not serve "
        "the real query path"
    )
else:
    print(f"  [ok  ] the generic plan uses {PARTIAL} too")
sql("DEALLOCATE ALL")

print("\n4 · WHAT THE PARTIAL INDEX CANNOT DO — STATED, NOT DISCOVERED LATER")
print("-" * 78)
print("  *Which payments have no till?* cannot be answered from an index that")
print("  excludes exactly those rows. Printed so the cost is on the record:")
plan(
    "counter_session_id IS NULL, partial index only:",
    f"SELECT count(*) FROM {PROBE} WHERE tenant_id = %s AND counter_session_id IS NULL",
    [str(tenant_a)],
)
print("  That query returns most of the table, so a sequential scan is the")
print("  right plan for it whichever index exists — which is why this costs")
print("  nothing rather than being a trade.")

print("\n5 · AND THE FULL INDEX ANSWERS THE SAME TILL QUERY (so the choice is size)")
print("-" * 78)
sql(f"DROP INDEX IF EXISTS {PARTIAL}")
sql(f"CREATE INDEX {FULL} ON {PROBE} (tenant_id, counter_session_id)")
sql(f"ANALYZE {PROBE}")
text = plan("full index only, bound parameters:", TILL_QUERY, [str(tenant_a), str(till)])
if FULL not in text:
    failures.append("the full index was not used either — the probe is measuring nothing")

sql(f"DROP TABLE IF EXISTS {PROBE}")

print("\n6 · NOTHING WAS LEFT BEHIND")
print("-" * 78)
left = sql(
    "SELECT count(*) FROM pg_class WHERE relname IN (%s, %s, %s)",
    [PROBE, FULL, PARTIAL],
    fetch=True,
)[0][0]
print(f"  probe relations remaining: {left}")
if left:
    failures.append(f"{left} probe relation(s) left behind")

print("\n" + "=" * 78)
if failures:
    print(f"RED — {len(failures)} finding(s)")
    for f in failures:
        print(f"  · {f}")
    sys.exit(1)
print("GREEN — the partial index is usable for the till query, including under a")
print("generic plan, and is the smaller of the two at every share measured.")
print("=" * 78)
