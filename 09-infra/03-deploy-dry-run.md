# Deploy dry-run — what a clean deploy actually produces

> **Run 2026-08-15 against a live PostgreSQL 16 cluster**, on a database created
> empty for the purpose (`sbh_deploy_dryrun`). Every number below is a
> measurement taken from `pg_class` / `pg_policy` / `pg_inherits` or from a test
> run, not a reading of the code that was supposed to produce it. That
> distinction is the entire point of this document: hard-won law 1 says a
> comment claiming a guarantee is not the guarantee, and the only way to settle
> a claim about a database is to ask the database.

## Why this exists

Nine defects reached a running product on the first live deployment. Three of
them — TLS refused, every request answered 400, the app rendering in the wrong
font — were **defaults that failed open**, and each was invisible to every test
in the repository because no test boots a real image against a real cluster.
This dry-run is the check that would have caught them, run before a deploy
rather than after one.

It also catches the class named while closing the partitioning defect: the
partition-coverage gate reads the **code registry** against the requirements
document and never looks at a database, so it cannot see a table that is
*declared* partitioned and never *migrated*. A dry-run is where declared and
actual are compared.

## How to run it

⚠ **THE THREE COMMANDS BELOW USED TO BE THE WHOLE RECIPE AND THEY DO NOT WORK ON A CLEAN
CLUSTER (DEF-622, 2026-08-24).** `migrate` dies at
`identity.0003_sessions_security_policy_lockout` with
`ProgrammingError: unrecognized configuration parameter "app.tenant_id"` — raised inside
PostgreSQL's own foreign-key validation scan, because `FORCE ROW LEVEL SECURITY` applies
the tenant policy to the table owner and the table owner is whoever runs the migration.
**This dry-run passed on 2026-08-15 only because the cluster it ran on already carried the
setting from an earlier database** — exactly the accident of history the defect describes,
and exactly what a dry-run is supposed to be immune to. Provision the tenant-context
default first (doc 01 §5 step 0):

```bash
export DJANGO_SETTINGS_MODULE=config.settings.local
export DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_deploy_dryrun"
export SBH_DB_PASSWORD=smartbillhub
10-scripts/13-provision-database.sh --all
```

`--migrate` applies the sequence **one migration per process, in dependency order** (PO
ruling 2026-08-24, OQ-354) rather than as a single `migrate`, because `app.tenant_id` is a
session variable and one connection lets a data step poison every later step's foreign-key
validation. **No role is granted `BYPASSRLS` at any point.**

`--verify` is the part worth reading: it prints `rolsuper`/`rolbypassrls` for the app role
(both must be `f`, and the run FAILS if not), the `app.tenant_id` default, the ENABLE+FORCE
and policy counts, and that no tenant carries the nil sentinel as its id. Measured on an
empty PostgreSQL 16.13 database, 2026-08-24: **181 tenant-scoped tables · 180 ENABLE+FORCE ·
180 policies**, with the one exemption being `sessions`, as §2 below explains.

⚠ **A dry-run from truly empty stops at step 12 of 163 today** —
`assets.0003_meter_types_and_read_methods` poisons itself (OQ-354, open half). The remaining
152 steps were measured green under the three-line fix with no bypass and no superuser.

The original recipe, kept because it is what the numbers below were measured with — it
still needs step 0 to have run:

```bash
sudo -u postgres createdb sbh_deploy_dryrun
sudo -u postgres psql -tAc "GRANT ALL ON DATABASE sbh_deploy_dryrun TO smartbillhub"
cd 06-backend
export DJANGO_SETTINGS_MODULE=config.settings.local
export DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_deploy_dryrun"
python3 manage.py migrate
```

Then the five checks below, in order. **A dry-run is not a pass until all five
have been run on the same database in one sitting** — a green check on a
database that was migrated at some other time proves nothing about this one.

---

## 1 · Migrations apply from zero

**Result: PASS.** Every migration in every app applied to an empty database in
one `migrate`, exit 0.

This is not the same as "migrations work", which is what a developer database
proves. A developer database was migrated incrementally over weeks and can hide
an ordering dependency that only bites a first deploy — migration ordering is a
🔒 sensitive path for exactly that reason.

## 2 · Every tenant table is actually isolated

The query that settles it — it finds tables by the presence of a `tenant_id`
column rather than by any list, so a table nobody remembered is still counted:

```sql
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
       (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
                   AND a.attnum > 0 AND NOT a.attisdropped
WHERE n.nspname = 'public' AND c.relkind IN ('r','p')
ORDER BY 1;
```

**Result: 149 tenant-scoped tables · 148 with row-level security ENABLED,
FORCED and carrying at least one policy · 1 exempt.**

### The one exemption, and why it survived scrutiny

`sessions` carries `tenant_id` and has no row-level security at all. That is
**deliberate and documented** in `apps/identity/migrations/0003_…`:

> `sessions` — US-IDN-003 §5 platform table. RLS-EXEMPT per that mapping
> ("platform table"): the row must be readable to ESTABLISH tenant context;
> tenant binding is enforced in the auth layer (BR-IDN-006) and probed by the
> G5 isolation suite.

The reasoning is sound — a session row is what tells the system which tenant
the request is in, so it cannot be read *through* tenant isolation without a
circular dependency. **But that comment makes two claims, and law 1 says a
claimed guarantee is not a guarantee. Both were checked rather than trusted:**

| Claim | Verified how | Result |
|---|---|---|
| Tenant binding is enforced in the auth layer | `apps/identity/auth.py:143` refuses a session presented on another tenant's path, and deliberately raises the **same 404 as a tenant that does not exist** — the two must be indistinguishable, or the refusal itself enumerates tenants | **TRUE** |
| It is probed by the isolation suite | `tests/test_path_tenancy_session_binding.py` carries 4 `isolation` marks; run on this database: **3 passed**, and the file's full 33 cases passed | **TRUE** |

**So the exemption stands.** Recorded at length because the next person to run
this query will find the same single row and needs to know it was interrogated,
not waved through — and because if either claim ever stops being true, this is
the table where that would matter most.

## 3 · Partitioning is real, not just declared

```sql
SELECT c.relname, c.relkind,
       (SELECT count(*) FROM pg_inherits i WHERE i.inhparent = c.oid)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('audit_log','meter_reads','invoice_lines',
                    'journal_lines','outbound_messages');
```

`relkind` is the answer: **`p` is a partitioned table, `r` is an ordinary flat
one.** A declared-but-unmigrated table reports `r` with zero children while
every code-reading gate says it is partitioned.

**Result on a clean deploy:**

| Table | Kind | Partitions |
|---|---|---|
| `audit_log` | `p` | 4 |
| `meter_reads` | `p` | 28 |
| `invoice_lines` | `p` | 2 |
| `journal_lines` | `p` | 2 |
| `outbound_messages` | `r` | 0 — **ratified exemption**, see below |

`outbound_messages` is unpartitioned by PO ruling and does not expire: monthly
range partitioning would force `created_at` into every unique constraint, so a
bill released 30 September and re-run 2 October would land in a different
partition, pass the duplicate check, and **send the customer a second copy**.
The no-duplicate guarantee wins over the partitioning requirement.

## 4 · Defaults fail closed

Hard-won law 3: **the unsafe option must be the one you type.** Each row below
was a live-deploy defect once.

| Setting | Value with nothing configured | Fails |
|---|---|---|
| `sslmode` | `require` (`?sslmode=${DB_SSLMODE:-require}`) | **closed** — an un-encrypted connection must be asked for |
| `ALLOWED_HOSTS` | `[]` in both `base` and `production` | **closed** — with `DEBUG=False`, Django rejects every request until a real hostname is set |
| `DEBUG` | `False` in both `base` and `production` | **closed** |

⚠ **A template change never reaches a host that already has a `.env`** (law 4).
Every row above describes what a *new* deployment gets. A host deployed before
these defaults changed still carries whatever its own `.env` says, and editing
`.env.example` does not touch it. **Check the running host, not the template.**

## 5 · Migrations reverse, and the round trip is lossless

A declared reverse is not a working reverse. Both were checked.

**Static:** 47 `RunPython` / `RunSQL` operations across all apps; **0 without a
reverse**. (Note for whoever automates this: this repo writes raw SQL through
`RunPython(forward, backward)` with named function pairs, *not* through
`RunSQL(..., reverse_sql=...)`. A scan that greps only for `reverse_sql`
reports a clean zero against 47 operations it never looked at — which is what
happened on the first attempt here.)

**Live:** nine migrations unapplied across the three money apps — ledger back
to `0004_posting_guard`, billing back to `0015_rls_correction_cases`, payments
back to `0009_…` — every one exit 0, **including both partition migrations**,
which are the ones most likely to be one-way. Then re-applied forward.

**After the full round trip, re-measured on the same database:** `invoice_lines`
and `journal_lines` are both `p` with 2 partitions, and the count of unguarded
tenant tables is **1** — still just the documented `sessions` exemption.
Nothing was lost going backwards and forwards.

---

## What this dry-run does NOT cover

Stated so nobody reads a green dry-run as more than it is:

* **It does not boot the application image.** Three of the nine first-deploy
  defects were only visible in a running container (a permission-denied log
  line on every boot, a webfont that never loaded, a raw scaffold string on a
  public page). Law 6 — diff the running app against `05-prototype/` — is a
  separate check and no gate performs it.
* **It does not exercise a real TLS-requiring cluster.** `sslmode=require` is
  verified as a *default*, not as a working connection to a server that demands
  it. The original defect was found only by a real RDS instance refusing.
* **It says nothing about data.** An empty database migrates cleanly in ways a
  populated one may not; a migration that back-fills or re-shapes existing rows
  is untested here by construction.
* **It is a snapshot.** The counts above are true of the commit it was run at.
  Re-run it — the whole point is that it is cheap.
