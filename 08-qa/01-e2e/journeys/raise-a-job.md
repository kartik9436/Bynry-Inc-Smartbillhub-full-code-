# raise-a-job — an office clerk raises field work on a building's units, from an account or from a meter, in three steps, and every job lands priced with its promise, its template and its holder

---
id: raise-a-job
tier: 2
change: CR-168-BRC10 P2.7 (written in round 9 by lane FIN-T, `2.520.3`)
rules: [BR-WRK-018, BR-WRK-027, BR-WRK-029, BR-WRK-056, BR-WRK-016]
tasks: [P2.1, P2.2, P2.4, P2.5, P2.6, P2.9, P2.11, P2.12, P2.13, P2.14, P2.15, P2.16, P2.18, P2.19, P2.20]
modules: [work, metering, customers, assets]
spec: 07-frontend/src/features/work/raise/cr168Raise.dom.test.tsx · cr168RaiseAccount.dom.test.tsx ·
      06-backend/tests/test_cr168_srv2_raise.py (SQLite) ·
      06-backend/tests/test_cr168_srv2_bulk_raise_pg.py (PostgreSQL 16 — P2.6, the savepoint per job, red first)
walk: 10-scripts/cr168_raise_after_walk.mjs (browser, 1440)
---

**Intent.** Images 14–20. The beta reported that raising a job meant one form per unit and
that the job came out without a priority, a promise or a checklist. This journey is the
three-step raise — *What · Schedule & crew · Confirm* — through each of its three doors.

**Upstream leaves (preconditions).** A building (premises) with units and its services; the
utility's job types and priorities seeded (`seed_reference_list`, the PO's nine types and
their sub-types, BR-WRK-058); at least one PUBLISHED template of the service (`BR-WRK-016`:
the offer is the utility's own); a technician or crew to give it to (optional).

| # | Who | Does | Sees | Record |
|---|---|---|---|---|
| 1 | Clerk | Work › Orders › *+ New work order* (top right, every state of the list — P2.1) | Step 1 *What*: Premises (type two letters, server-searched, the building's type and unit count beside each), Units, Job type (two levels — a heading and its sub-types), Template, Asset type, Priority, Description | `GET /premises?q=` · `GET /work/templates?f.job_type=&f.raisable=1` |
| 2 | Clerk | Picks *12 Kestrel Park*, ticks three units, *Water › Leak Repairs*, its template | *Raises 3 jobs — one per unit.* The template's own asset type, else *None — the unit itself* | `GET /units?f.premises_id=` (paged, the unit-type chips) |
| 3 | Clerk | Chooses an asset type with two meters on one unit | That unit reads *Choose one*; Continue refuses *Choose an asset for Apt 101.* until one is ticked (ruling 20) | `GET /work/raise/assets` (`shares_unit`) |
| 4 | Clerk | Step 2 *Schedule & crew* | Due date opening on the priority's promise (ruling 23), Visit date + window (*What the customer is told.*), *Assign to* — best fit first, advice beside every name, or *Nobody yet*. **No Area** (ruling 24) | `GET /work/candidates?template_id=&premises_id=&unit_ids=&on=` |
| 5 | Clerk | Step 3 *Confirm* | The summary, *The jobs* table, the EFFECT box; *Back · Raise 3 jobs ✓* | — |
| 6 | Clerk | Presses *Raise 3 jobs ✓* | *3 jobs raised* — each number with *Raised*, or *Not raised* and why; *Raise more* · *Open work orders* | ONE `POST /work-orders/bulk-raise` with an `idempotency_key`; one savepoint per job (law 14) |
| 7 | — | One unit is refused by the database mid-raise | The other two are raised; that row reads *Not raised* with its reason | `[ok, refused, ok]` — proved on PostgreSQL 16 (P2.6) |
| 8 | Clerk | Presses *Raise* again (double click, retry) | The same answer | the repeated key returns the first answer — 3 jobs, never 6 |
| 9 | Clerk | Accounts › an account › Work tab › *⚡ Raise work here* | The same three steps *From the account* — Account, Where, Category, Status, Services, then the account's assets | `/{tenant}/accounts/{id}/work-orders/new` (P2.4) |
| 10 | Clerk | Assets › a meter › *Raise work order* | The same three steps *From the asset* — Asset, Service, Where, On site, Account; only that service's templates | `/{tenant}/assets/{id}/work-orders/new` (P2.19); `apps/assets` writes nothing (`BR-WRK-056`) |

**Rules the journey holds.**
* **Every job is priced with its promise** (`BR-WRK-018`): `due_at` = raise + the type's
  hours, else the priority's, else the utility's default; a chosen due date wins.
* **The template's service must be the job's** (P2.11): a water template on an electric meter
  is refused `work.order.template_wrong_service`; a unit of another building is refused
  `work.order.unit_not_on_premises` (P2.13).
* **The template's scope and service reach the job** (P2.14); a job raised on an asset says
  where it is — premises, unit, service walked (P2.20).
* **One job per unit, or per asset when an asset type is chosen** (ruling 19).
* **A bulk raise without a key is refused** (`work.raise.key_required`).
* **Assigning at the raise commits with the job**, and the phone is told after commit.

**Leaves (for downstream).** Jobs on Work › Orders with priority, `due_at`, template,
scope, service and — when one was chosen — a holder whose phone was told;
`work_bulk_raises` holding the key's answer; `source = dispatcher` (or `assets` from the
asset door). `dispatcher-reassigns` starts from one of them.
