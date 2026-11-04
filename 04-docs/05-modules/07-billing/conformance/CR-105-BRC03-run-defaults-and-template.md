# The run's standing answers, its name, and its template — the schema half

`DEF-BIL-5255` (defect) + `CR-105-BRC03` (change) · 2026-09-14 · version **`2.267.0`**
Built from `CR-105-BRC03-s03-element-inventory.md` §5.1 (screen **16 Scope**, `p046`–`p048`)
and from the PDF pages it indexes — **never from a prose brief**.

**One migration, `billing/0028`, three nullable columns on `bill_runs`.** A money-path
migration is a 🔒 sensitive path, so it is reviewed ONCE and its ledger row is written.

---

## 1 · The elements this wave answers, and the ones it does not

Screen 16 draws **five groups**. The inventory's §5.1 lists 33 elements across them. This
wave is the SCHEMA half of exactly two of those groups, and nothing else.

| Inventory element (§5.1, `p047`) | Drawn value | This wave |
|---|---|---|
| Group head D · `DEFAULTS` ③ | — | — *(the group head is a screen element)* |
| Default · no reading | dropdown `Estimate from history` | ✅ `case_defaults["missing_read"]` |
| Default · unusually large | dropdown `Hold it for review` | ✅ `case_defaults["high_usage"]` |
| Default · unusual days | dropdown `Pro-rate by days`, helper **`Holds the bill - pricing not built`** | ✅ `case_defaults["days_threshold"]` |
| `Label this run` ④ | text `September, after the water rate change` | ✅ `bill_runs.label` |
| Past-runs columns | `RUN · **LABEL** · STARTED · BY · ACCOUNTS · STATUS · ACTIONS` | ✅ the LABEL column now has something behind it |
| *(not drawn — PO ruling `CR-105-BRC03`)* | the bill template | ✅ `bill_runs.template_id` |

**NOT this wave, and each belongs to somebody:** group B `SCOPE` ① (the account-scope
resolver, `DEF-BIL-4224`) · the checkbox ② `Also include the 21 accounts held from
RUN-0002` (`DEF-2843`) · group C `WHAT THIS COVERS`'s five counts · group E's `Take it
over` ⑤ (`DEF-106`) · the commit ⑥ · **every control on screen** — this wave draws
nothing.

### The tie-out

```
DEFAULTS group, drawn      4 controls  (3 case defaults + 1 label)
                           + 1 group head, which is not a control
columns landed             3           (case_defaults, label, template_id)
                           = 3 case defaults folded into ONE jsonb column
                           + label
                           + template_id, which the drawing does NOT draw   ✅
3 (drawn defaults) -> 1 column + 1 (label) + 1 (template, ruled) = 3        ✅
```

The three case defaults are **one column and not three**, and §3 says why.

---

## 2 · Where this brief disagreed with the inventory, and the inventory won

| Claim | What the inventory / register actually says |
|---|---|
| *"the run-level defaults are DEFECT work under `DEF-BIL-5256`"* | **`DEF-BIL-5256` is step TWO's chip strip** — *"Bill run step 2 draws six sub-tabs where the blueprint draws seven chip rows carrying 26 counted chips"*. The row for this work is **`DEF-BIL-5255`**, *"Bill run step 1 does not draw the blueprint's five groups: SCOPE, WHAT THIS COVERS and DEFAULTS are absent"*, whose own `prevention` column names the deliverable exactly: *"three run-level default columns with their migration"*. Built against **5255**. This is `DEF-2804`'s shape — a real id read for a different real id, on a money path — and it is recorded here so the next reader does not inherit it. |
| *"there is a fourth control, `Label this run` — check whether it is already stored"* | **It is not stored anywhere.** No `label` column on `bill_runs`, no `run_label` in the module, and the past-runs table's drawn `LABEL` column had nothing behind it. The inventory marks it ④ **NEW**. Built. |
| *"the drawing calls this group the single biggest error-reducer"* | Confirmed verbatim at `p047`. |
| *"`issue.py` describes `template_pin_explicit` … the run already tracks two counters"* | Confirmed verbatim, `issue.py:674-689` and `2311`. |

---

## 3 · Two judgments this wave made, with their reasoning

**(a) ONE `jsonb` COLUMN, NOT THREE TYPED ONES WITH A `CHECK` APIECE.** The case vocabulary
is `apps.billing.decisions.CHOICES_BY_CASE` and it has grown **twice this month** — CR-038
W8 added seven cases, and `DEF-BIL-5270` added `billing_continuity` on 2026-09-14, the day
before this wave. A `CHECK` constraint spelling the choices out would be a **second copy of
a vocabulary that already has one home**, which is the exact failure
`apps/tenancy/settings_families.py` records beside `back_bill_cap_months`: two copies of one
default, and the tenant's screen and the engine's guard disagreeing in silence. Validation
is `runs.resolve_case_defaults`, against the one vocabulary, refusing both an unknown case
kind and an unknown choice **by name**.

**(b) THE RESOLVED VALUE IS STORED AT CREATION, NOT RE-READ AT PREPARE TIME.** A tenant who
edits Settings between Scope and Check must not change what a run already in flight decided.
That is the same hazard `BR-BIL-026` freezes the template against, one field along, and it
is a test: `test_a_run_already_created_does_not_move_when_the_setting_moves`.

---

## 4 · ⚠ The collision, stated rather than assumed

**`BR-BIL-015`'s no-pre-committed-default clause was reaffirmed by its author on
2026-08-26**, verbatim:

> *"keep the rule — speed comes from the bulk button, not from decisions nobody made; an
> auditor asking 'who chose to estimate M-4412?' gets a name"*

A run-level default pre-answers a case for hundreds of accounts, which is the thing that
ruling refused. **It is superseded on this point by the LATER 2026-09-11 run-intent ruling**
— *"it kind of allow him to do all decision before hand"* — which is what the blueprint is
drawn to and what B14 rule 41 makes the specification.

**The audit guarantee is KEPT, not traded away.** Nothing in this wave writes a
`bill_run_decisions` row; the per-account trail is as append-only as it was. The name the
2026-08-26 reaffirmation demands is the run's own `run_by` plus its `bill_run.created` audit
row, which now carries the map. So *"who chose to estimate M-4412?"* is answered **by the
run** rather than being unanswerable.

Change process §2 requires the supersession be quoted with its chain, and law 13 requires it
be STATED rather than asked. It is stated here, in the decision log, in `BR-BIL-1040` and in
the review-ledger row, and the review row asks the PO for **one line** confirming it.

---

## 5 · Proof

* **17 cases, `tests/test_br_bil_1040_run_case_defaults.py`, all green on real PostgreSQL 16**
  under `config.settings.local` — never the default suite, which hard-won law 14 says
  hardcodes in-memory SQLite. Two of the cases turn on behaviour SQLite does not have.
* **Two of the seventeen were proved RED FIRST, in the harness that runs them:**
  widening one mirrored choice tuple in `settings_families.py` → the vocabulary test red;
  replacing the tenant read in `runs.resolve_case_defaults` with a hardcoded dict → the
  no-hardcoding test red. **2 failed, 15 passed.** Both files then restored **byte-identical**
  (`cmp`) and the suite re-run **17/17 green**.
* `makemigrations billing --check` — clean.
* **Reds read and DATED that this wave did not cause** (law 7 habit 1): `run_gates --tier1`
  reports *0 newly failing*; `G61 frozen-figures` has been red since **2026-09-08** on the two
  ❄️ FROZEN documents (3 new figures in B4, 8 in B5) and nobody is reading it; `G53` names
  `runs.py` as a 🔒 file no glob covers; three PostgreSQL-only test failures date to the
  **2026-09-02** merge and are filed as `DEF-BIL-5301`.

## 6 · What is owed, filed rather than noted

| | |
|---|---|
| `DEF-BIL-5302` | **`bill_runs.template_id` has no reader.** `api._template_pin_for` still resolves the pin from the request body. Two small call sites, both in files two other billing lanes were editing at the same time, so reported rather than taken. |
| `DEF-BIL-5301` | three tests incapable of passing on PostgreSQL, invisible because the default suite is SQLite. |
| `G53` / `human_owned.txt` | `06-backend/apps/billing/runs.py` invokes the 🔒 protocol, has a review-ledger row, and **no glob matches it**. That is the FOURTH occurrence of the escape `issue.py`, `decisions.py` and `read_analysis.py` each record in the guard list itself. Adding the glob is a **process event and the PO's call, not a lane's** — so it is reported here and G53 counts it. |
