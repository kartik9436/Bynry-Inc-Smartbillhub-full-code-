# J-REP-04 — change a report's columns, save it under your own name, share it with a colleague

---
id: JREP04
tier: 1
rules: [BR-REP-019, BR-REP-023, NFR-3, NFR-5]
stories: [US-REP-004]
change: CR-142-BRC07 · Phase 5 · P5.8
screens: ["1·1", "1·2", "2·1", "2·2", "2·4"]
depends_on: [JREP01]
# ⚠ **ACTIVE.** Every step below was impossible on 2026-09-26: there was no
# `report_definitions` write path at all, and `+ Build your own` was a held
# control with an expiry test on it. Steps 1–7 were walked in Chromium on
# 2026-09-27 by `10-scripts/rep_p5_builder_walkthrough.mjs`; step 8 is `P5.9`
# and is proved in pytest rather than in a browser, and this file says which
# is which rather than implying one walk covered both.
---

> **Read the drawings as IMAGES (B14 rule 42), never the text layer:**
> `python3 10-scripts/pdf/pdf_render.py "05-prototype/09 Reports Build Brief.pdf" <outdir> 3 16,17,20,22,23`
> The Phase 5 task table is **p016–p017**, the catalogue with `+ Build your
> own` above the sub-tab strip is **p020**, the Custom sub-tab and its empty
> state are **p022**, and the edit panel's own field table is **p023**.
> ⚠ The text layer of this PDF is measurably lossy — it drops whole task rows.

## WHAT THIS JOURNEY IS FOR

**Phase 5's DONE WHEN, verbatim:** *"A utility saves a report we never wrote,
shares it, and it appears in the catalogue for their colleagues and nobody
else's."*

Three different people have to be true at once for that sentence to hold: the
author, a colleague in the same utility, and a colleague in **another**
utility. A walk that signs in as one person proves the first and can say
nothing about the other two — which is exactly how `DEF-REP-6864` shipped, a
private report served to every colleague, over a green suite in which every
test had one user.

## THE HANDOFF CONTRACT

**What upstream (`J-REP-01`) leaves for this journey:** a report that OPENS —
the viewer at `/{tenant}/reports/{key}` rendering rows for a platform
definition. The builder is an edit panel BESIDE that table (PO ruling
2026-09-26: *"panel"*, not a wizard), so a report that cannot be opened cannot
be edited.

**What this journey leaves for downstream:** one `report_definitions` row owned
by this tenant, and one `audit_log` row per save. **No ledger, no bill, no
payment, no account.** A definition is data about a QUESTION, never about
money; nothing in this walk moves a figure.

## THE WALK

| # | Step | What must be true | Proved by |
|---|---|---|---|
| 1 | Sign in, open **Reports** | `+ Build your own` is drawn, and it is **above** the Standard · Custom strip rather than inside Custom (p20 callout ②) | `10-scripts/rep_p5_builder_walkthrough.mjs` |
| 2 | Read the **Custom** sub-tab | It reads **0** before anything is saved. ⚠ The count is the whole point of the sub-tab — *"an empty sub-tab reading 0 is how a clerk learns the feature exists"* | idem |
| 3 | Open a standard report, open the **edit panel** | The panel opens BESIDE the table, not over it, and the table is still readable | idem |
| 4 | **Untick a column, then tick it back** | The rows underneath change **both times, with no save in between** — `P5.3`'s outcome word for word. The walk prints the header row before and after, so a reader sees the difference rather than being told about it | idem |
| 5 | **Save as** a name of your own | The address becomes the new report's, **Custom** goes 0 → 1, and the report is listed by NAME and not by an id (B14 rule 31) | idem |
| 6 | Name one **`History`** | Refused, by that literal word, and the **History tab still opens afterwards** | idem |
| 7 | A **colleague in the same utility** looks | They do **not** see it while it is private; once it is shared they see it **and it opens** — a dimmed card would be the same defect one layer down | idem |
| 8 | A **Billing Clerk** opens the catalogue | The **access-review** report is not on it, and its address refuses with **403** | `tests/test_rep_p5_9_role_gate.py` |
| 9 | A colleague in **another utility** looks | They see nothing of it — not the row, not the key, not the name | `10-scripts/rep_p5_isolation_and_savepoint_proof.py`, on real PostgreSQL |

### ⚠ STEP 4 IS THE ONE A SINGLE SCREENSHOT CANNOT PROVE

A photograph of an open panel proves the panel RENDERS. `P5.3`'s outcome is
*"Adding a column shows it in the rows below without a save"* — a statement
about two states of one screen — so the step is walked as a **pair** and the
two header rows are printed beside each other. The tick-back half is there for
the same reason in reverse: a panel that only ever ADDS columns would pass a
one-way check and would have lost the clerk their original report.

### ⚠ STEP 8 IS NOT WALKED IN A BROWSER, AND THAT IS STATED RATHER THAN HIDDEN

`P5.9`'s outcome is *"A Billing Clerk cannot run the access-review report"*,
and the seeded demo tenant has one signed-in staff member. Walking it needs a
second account holding a different role, which the fixture does not create —
so it is proved in `tests/test_rep_p5_9_role_gate.py` against the same
functions the screen calls, and the gap is named here. **A step silently
dropped is hard-won law 7's fifth shape**: a check reporting zero over a scope
it excludes.

### ⚠ STEP 9 CANNOT BE PROVED BY THE DEFAULT SUITE AT ALL

`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`, and **SQLite has no row-level security** — a probe there proves
nothing and passes (hard-won law 14, and `P5.6`'s own ⚠ *"Postgres only"*).
The proof is the PostgreSQL script named above, run under a NOLOGIN
NOSUPERUSER NOBYPASSRLS role, because PostgreSQL exempts a superuser from RLS
unconditionally, `FORCE` included.

## WHAT THE SEEDED TENANT CANNOT SHOW

* **A second role.** See step 8.
* **A report built FROM SCRATCH.** 1·2B draws one whose *Based on* reads *from
  scratch*; there is no read path for a definition that has never been saved,
  so `+ Build your own` opens the **Custom** list and its empty state carries
  p22's own instruction — *"Open a standard report. Change it. Save it here."*
  That is not a gap in this journey; it is the shape the product has, and
  callout ② calls it *"the usual way a custom report gets made"*.
* **A colleague, unless `COLLEAGUE` is set.** The walkthrough announces
  `CANNOT` and counts it rather than passing quietly.
