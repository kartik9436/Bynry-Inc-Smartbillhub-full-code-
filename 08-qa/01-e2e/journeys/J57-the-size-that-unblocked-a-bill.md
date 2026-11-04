# J57 — The size that unblocked a bill ⚠ blocked `OQ-INT-1485` (*size 5/8" for MTR-2210, we hold none* — the difference shown, nothing written, and the ride ending one step early)

---
id: J57
tier: 2
rules: [BR-INT-031, BR-INT-032, BR-INT-049, BR-INT-029, BR-INT-039]
stories: [US-INT-036]
# Wiring: `US-INT-036` cites `J57` in its `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J57.spec.ts`. Wave L task L5 writes it
# with J55 (`cr069-l-backfill-tuesday.mjs`, steps 6–7). Phase 4.
# ⚠ BLOCKED ON OQ-INT-1485 — WHICH SYSTEM IS MASTER OF THE LINK BETWEEN A METER
# AND AN ACCOUNT, THE HEAD-END OR US? Both hold one. Getting it wrong BILLS THE
# WRONG CUSTOMER, which makes it a ruling rather than a mapping. Until ruled the
# sync collects the supplier's records into staging on the run, shows the
# differences on S142, and WRITES NOTHING TO `assets` — `seams/assets.py` raises
# `NotImplementedError("OQ-INT-1485")` at the write. The ride ends one step
# early, as the flow document says it must. Step 6 (TC-2) is WRITTEN NOW AND
# SKIPPED until the ruling closes.
---

**Intent.** *"The most concrete value in the document"*: an account cannot be billed **for
want of a connection size**; a register sync runs; the size arrives **from the system that
installed the meter**; and the run goes from **blocked** to drafted. This journey walks up to
that last step and **stops**, because the head-end holds a meter-to-account link **and so do
we**, and which one is master is the PO's. What it proves now is the **boundary**: the
difference is shown in words, the supplier's vocabulary for routes and types lands as
**rows** (unmapped → `other`, red), a size arriving **without its unit** is refused by name,
and `assets` is **byte-identical** afterwards.

**Upstream leaves (handoff in).** Brazos Bend's `meters_neptune360` connection (J55). *A
meter with no size*: account **`ACC-1048`**, meter **`MTR-2210`**, **no connection size**
on our side; the September bill run **blocked** for it — *needs a connection size* (a J24
phase-3 break, stage by name). The supplier's meter record: **`5/8" · positive displacement ·
route RT-NORTH-07`**. A supplier record reporting size `20` **with no unit**. No mapping
rows yet for `entity_type = route` or `meter_type`. Lone Star Ridge with a meter of the
**same serial** at the same supplier. Actor **Priya Menon**.

**This journey leaves (handoff out).** ONE `register_sync` run row whose **artifact** is the
staging table of supplier records and the classified differences; S142 listing *size 5/8"
for MTR-2210, we hold none · waiting for a decision*; `integration_target_reference` rows
**red/unmapped** for `RT-NORTH-07` (route) and `positive displacement` (meter type);
**`assets` unchanged — read back through its API**; the bill run for `ACC-1048` **still
blocked**. When `OQ-INT-1485` is ruled: the size written through `apps.assets`' service and
the blocked bill drafting on its next attempt.

**Fixture.** Frame `44.1`'s `RunsTable` (*Meter register · 1,240 checked · 18 changed*) for
the shape of the sync row; S143's *Routes* tab for the red rows.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (staging · assets · rows · isolation) | Rule |
|---|---|---|---|---|
| 1 | The September bill run (J24) reaches `ACC-1048` | A **phase-3 break**, failing stage by name: *needs a connection size* for `MTR-2210`. No partial invoice; the other drafts unaffected; the account queued with the reason | The break is billing's; this journey is what would clear it | BR-BIL-053 · BR-BIL-055 |
| 2 | The register sync runs (`meters_neptune360` · `register_sync`) | The supplier's meter records are collected into a **staging table on the run artifact**; the run is `reconcile` mode with its five counts. S142 lists the difference: ***size 5/8" for MTR-2210, we hold none*** · ***waiting for a decision*** — in words, no id | **No `assets` row changes** — assert `assets` byte-identical before and after, **read back through its API**. The write path `seams/assets.py` **raises `NotImplementedError("OQ-INT-1485")`** — asserted | BR-INT-029 · `OQ-INT-1485` · `US-INT-036` TC-1 |
| 3 | **their words as rows** — the supplier names route `RT-NORTH-07` and type `positive displacement` | Neither has a mapping row → each records as **`other`** and appears **red on S143** (*Routes* tab; the meter-type row likewise) — **the sync is not stopped** by a vocabulary | Route and type vocabularies are `integration_target_reference` rows (`entity_type = route | meter_type`), UNIQUE on the external side; a fourth supplier costs rows and no migration | BR-INT-032 · BR-INT-031 · `US-INT-036` TC-3 |
| 4 | **negative · 🔒 the measurement frame** — the record reporting size `20` with **no unit** | **Refused by name** — *size arrived without a unit* — **not written even to staging** | Hard rule 3 one level out: every numeric arriving from outside carries a declared frame; a coordinate in the wrong projection or a `0.8` score against a 0–100 scale is refused the same way (`US-INT-043`) | BR-INT-049 · hard rule 3 |
| 5 | **boundary · the ride ends here** | Priya reads the difference and *waiting for a decision*; the bill for `ACC-1048` **stays blocked**; nothing on `assets` moved | The three options are the PO's — we are master and the head-end's link is shown as a difference · the head-end is master for meters it installed · ours, but the head-end may **fill** an empty link. **A lane may not choose** | `OQ-INT-1485` |
| 6 | **after the ruling · written now, skipped until `OQ-INT-1485` closes** | The size `5/8"` is written **through `apps.assets`' service function** (never by an adapter); the blocked bill run for `ACC-1048` **drafts on its next attempt** — from **blocked** to drafted | The test exists in the suite marked skipped with the OQ id, so the day the ruling lands there is something to un-skip rather than something to write | `US-INT-036` TC-2 |
| 7 | **tenant isolation** | Lone Star Ridge's meter of the **same serial** at the same supplier: staging rows are **tenant-scoped**; the serial is **never cross-linked**; Lone Star Ridge's S142 lists its own differences only | RLS `FORCE` on `integration_run`; the seam scopes every read | hard rule 1 · `US-INT-036` TC-5 |
| 8 | **INVARIANCE** | The sync showed what it would change and **changed nothing**; the unit-less size never reached staging; unknown vocabulary landed red rather than stopping the run; `assets` was unchanged throughout; the bill stayed honestly blocked rather than drafting on a guess | Getting the master wrong bills the wrong customer — which is why the write waits | `OQ-INT-1485` · BR-INT-031 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The size **written** and the bill **drafting** | `OQ-INT-1485` — which system is master. Step 6 is written and skipped |
| b | Hourly interval data on the same connection | `OQ-INT-1484` — not the register sync, not the readings feed |
