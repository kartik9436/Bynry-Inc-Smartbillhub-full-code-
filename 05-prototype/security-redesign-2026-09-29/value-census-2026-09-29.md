# What utilities actually hold — the count the dropdowns are drawn from

**Run 2026-09-29 on this container, by `10-scripts/cr145_security_dropdown_value_census.py`
(READ-ONLY).** It answers Q1's precondition in the README beside this file: the PO chose
*"short dropdown, list chosen from real use"*, and a list is only safe once you know what
every utility holds — **every value left off the list is withdrawn from whoever holds it.**
On 2026-09-28 that already cost seven hours of session to the utilities on 480 minutes.

---

## ⚠ EVERY FIGURE BELOW IS DEMO. IT IS NOT AN ANSWER TO "WHAT WILL MOVE".

**This container holds no production data.** Every database on it is a seeded demo estate
or a lane's scratch copy, and the six tenant rows counted are **four distinct tenant ids,
all of them one utility — Brazos Bend Utilities — cloned across databases.** A distribution
measured on copies of one seeded estate is a proof that the counter works, not a population.

**The lists that ship must be drawn from this same count run against the production
database.** One command, and it writes nothing:

```
PGPASSWORD=… /root/.venvs/sbh312/bin/python \
  10-scripts/cr145_security_dropdown_value_census.py \
  --dsn postgres://<user>@<prod-host>:5432/postgres
```

## Scoping and role — say which you are getting

The counting role on this container is `smartbillhub`, and **`rolsuper=true`**
(`rolbypassrls=false`). A superuser bypasses row-level security, so **RLS is not what keeps
these reads apart.** Every read of `security_policies` runs with
`set_config('app.tenant_id', <tenant>, true)` in its own `READ ONLY` transaction, one tenant
at a time — hard rule 1, satisfied explicitly rather than inherited. The script prints both
flags on every run so no reader has to assume.

## Databases counted — 15

`sbh_a106smoke` · `sbh_clone_ncmaint` · `sbh_cr145t10` · `sbh_money7611` · `sbh_tpl_1c4644a4` ·
`smartbillhub` (one tenant each), and nine empty test databases:
`test_sbh_agent_a1bc796e005f67_2da5232b`, `…_a26541a814c05a_69fd322a`,
`…_a84a390545c6c4_a04d75d3`, `…_aba046a6a73952_56f5f7c9`, `…_adfbc69ccb0d09_799b7f40`,
`…_ae42d019823044_8f3eb240`, `…_ae4bbd1b8dd0a5_f6e7e9fe`, `test_sbh_gate_iso_4ae5a143c60a1418`,
`test_sbh_redproof_0d87088f` (0 tenants — migrated schema, no seed).

## Databases skipped — 4, by name, with the reason

| Database | Why |
|---|---|
| `template0` | `datallowconn=false` — the server refuses connections |
| `template1` | no `security_policies` / `tenants` table |
| `postgres` | no `security_policies` / `tenants` table |
| `sbh_gate` | no `security_policies` / `tenants` table |

*(Law 7's fifth shape: a blind spot with no number beside it is indistinguishable from an
empty one. 15 counted + 4 skipped = the 19 databases on the server.)*

## The four frequency tables — DEMO

Six tenant rows, all with a policy row; **zero tenants have no row.**

| Setting | Range today | Values held (DEMO) | Distinct |
|---|---|---|---|
| `absolute_session_hours` | 4–12 | **12** × 6 | 1 |
| `lockout_max_failed` | 3–10 | **5** × 6 | 1 |
| `lockout_minutes` | 5–60 | **15** × 6 | 1 |
| `keep_signed_in_days` | 1–30 | **30** × 6 | 1 |

Every held value is the column default. Nothing on this container has ever been changed from
seed, and **no value is outside today's range.**

## The shortest list that moves nobody — proposed, on demo evidence

| Setting | Proposed list | Contains what is held? |
|---|---|---|
| `absolute_session_hours` | all nine: 4, 5, 6, 7, 8, 9, 10, 11, 12 hours | yes — nine is short enough to offer whole, nothing is withdrawn, confirmed |
| `lockout_max_failed` | all eight: 3, 4, 5, 6, 7, 8, 9, 10 tries | yes — same, confirmed |
| `lockout_minutes` | 5, 10, 15, 30, 45, 60 minutes | yes — 15 is on it |
| `keep_signed_in_days` | 1, 7, 14, 30 days | yes — 30 is on it |

The first two are free: offering the whole range as a list withdraws nothing, so there is no
judgment to make. **The last two are the only real decisions**, and on demo data both round
lists cover every held value — but a demo estate sitting entirely on its seed defaults cannot
tell you whether a real utility sits on 23 minutes or 11 days. **Re-run the count against
production and widen either list by whatever it names.**

## The counter was proved able to find an awkward value

On a throwaway clone (`sbh_plantproof_xgfsgz`, created from `smartbillhub` and **dropped
afterwards** — `select count(*) from pg_database where datname='sbh_plantproof_xgfsgz'` → 0):

* planted `lockout_minutes = 23`, `keep_signed_in_days = 11`, `absolute_session_hours = 7`,
  `lockout_max_failed = 9` → the census reported each one and **named the utility**
  (`sbh_plantproof_xgfsgz/brazosbend (Brazos Bend Utilities)`);
* planted `lockout_minutes = 480` → reported `⚠ OUTSIDE TODAY'S RANGE` and listed it under
  the Product-Owner section with `(allowed 5..60)`;
* deleted the row → `utilities with NO row (run on the default) : 1`, named.

A counter nobody has watched find an awkward value is not evidence that none exists, which is
why this is here rather than assumed.

## The script writes nothing, and the server enforces it

Every read runs inside `begin read only`. Proved rather than asserted: an `UPDATE` issued
inside that transaction on the clone was refused by PostgreSQL —
`ERROR: cannot execute UPDATE in a read-only transaction`.
