# HUMAN-GUIDE — how people read and update this repository

**Numbering convention:** every *document-world* folder and file carries a numeric prefix showing its logical reading order (04-docs/01-spec → 02-decisions → …; modules numbered 00–13 by their canonical module numbers). The *code world* (06-backend, 07-frontend internals) keeps language-mandated names — Python packages cannot start with a digit — and the module-number ↔ code-name map is the 04-docs/05-modules folder names themselves.

This repo is operated by **both humans and AI agents**. Agents follow `CLAUDE.md`; this file is the human counterpart. It tells you where to read, how to interpret what you see, and the rules for changing things by hand without breaking the machinery that keeps documentation, code, and tests consistent.

---

## 1. Sixty-second orientation

| You want to… | Start here |
|---|---|
| Understand the product | `README.md` → `04-docs/README.md` → `04-docs/01-spec/01-screen-inventory.md` |
| See the app as designed | Open `05-prototype/UtilityBilling.html` in a browser (or the single-file `SMARTBillHub Prototype (standalone).html` — no other files needed) |
| Check what a module does | `04-docs/05-modules/<module>/01-overview.md` |
| Read requirements (epics & stories) | `04-docs/05-modules/<module>/06-epics/EP-*.md` |
| Check a business rule | `04-docs/05-modules/<module>/02-business-rules.md`, then the source it cites (usually `04-docs/02-decisions/04-money-math-rules.md`) |
| See what's still undecided | `04-docs/01-spec/17-open-questions.md` scoreboard → `12-governance/01-open-questions.md` (registry, once landed) |
| Check project status | `12-governance/05-weekly/` (latest WSR), `12-governance/02-decision-log.md`, `12-governance/03-risk-register.md` |
| Understand a database table | `04-docs/02-decisions/02-database-design-brief.md` (B2) — the authoritative DDL |
| Find a test | `06-backend/tests/golden/` (billing math), `06-backend/tests/test_tenant_isolation.py`, per-app `tests.py`, `08-qa/` |

## 2. How to read the ID system

Every artifact has an ID; every reference uses the ID. When you see one, this is where it's defined:

| ID looks like | It is a… | Defined in |
|---|---|---|
| `S31.2` | Screen | `04-docs/01-spec/01-screen-inventory.md` (A1) |
| `EP-MET-05` | Epic | that module's `06-epics/` folder |
| `US-MET-016` | User story | inside its epic file |
| `BR-MET-010` | Business rule | that module's `02-business-rules.md` |
| `OQ-003` | Open question | `12-governance/01-open-questions.md` |
| `GT-9` | Golden test (billing math fixture) | `04-docs/02-decisions/05-golden-tests.md` + `06-backend/tests/golden/` |
| `TC-4` | Test case (scoped: `US-MET-016/TC-4`) | §3 of its story |
| `IS-5` | Interaction standard | `04-docs/02-decisions/09-interaction-standards.md` (B9) |
| `ADR-002` | Architecture decision | `04-docs/04-adr/` |
| `OQ-1190`, `BR-RAT-962` | **The numbers run to five digits** — PO ruling 2026-08-31, *"next question make them 5 digital"*. Read them as whole numbers: `OQ-1190` is not `OQ-119`, and the two are different questions. Nothing was renumbered, so short ids stay short. | `12-governance/02-decision-log.md`, 2026-08-31 |
| `A2`, `B4` | Spec/decision documents | `04-docs/01-spec/` (A = extracted from design), `04-docs/02-decisions/` (B = human judgment) |
| `W3` | Build wave | wave plan in root `README.md` |

**Rule of thumb: A-docs describe what the design shows. B-docs decide how we build. Module docs (stories/rules/field maps) tie them together. When two disagree, the B-doc wins for behavior, A1 wins for screens — and the disagreement itself is a bug: file it.**

## 3. How to read a user story

Stories have YAML frontmatter (for machines) and 8 numbered sections (for everyone):

- **frontmatter** — `status: draft | ready | blocked | deferred | done`; `blocked_by:` lists OQ-IDs; **`depends_on:`** lists upstream stories you must read before coding this one; **`journeys:`** lists the end-to-end chains (J1–J6, in `08-qa/01-e2e/journeys/`) this story belongs to — each journey shows the handoff contract between steps.
- **§1 Details** — who/what/why + screens.
- **§2 Business Rules** — each rule's status matters:
  - `CONFIRMED` — signed by finance/product; safe to build against.
  - `PROPOSED` — derived by the PM from industry standards; sensible but **not ratified**; builds may proceed only where the story isn't gated.
  - `OPEN` — nobody knows yet; never build a guess.
- **§3/§4 Test cases & data** — every TC must be runnable as written.
- **§5 Field mapping** — UI field → database column → origin (`user-input`, `system-derived`, `reference-data`, `integration`, `computed-display`).
- **§6 Acceptance** — what "done" demonstrably looks like.
- **§7 Finance calculation** — the formula with a worked example, or "N/A".
- **§8 Open questions** — OQs this story minted; "None" if clean.

## 4. How to read the code

- `06-backend/apps/<module>/` mirrors the doc modules one-to-one. `models.py` = tables owned (per B2), `services.py` = the only write path, `api.py` = endpoints per A11.
- **A stub that raises `NotImplementedError("OQ-003")` is deliberate** — it marks an unresolved decision, with the OQ-ID to look up. Do not "fix" these by implementing a guess.
- Files marked **HUMAN-OWNED** in their docstring (RLS, rating engine, ledger posting, idempotency, money rounding) may only change with Eng-Lead review — CODEOWNERS enforces this on GitHub.
- Frontend: `07-frontend/src/features/<module>/` — files are named for their screens (`RunBillsWizard.tsx` = S31).

## 5. How to read the tests

- `06-backend/tests/golden/` — GT-1…GT-14, the billing-math contract. Markers mean:
  - `xfail` — rule confirmed, engine not built yet; will flip to must-pass automatically.
  - `skip` — expected values not yet signed by finance; **do not un-skip without sign-off**.
- `test_tenant_isolation.py` — the zero-tolerance suite; a failure here is a release blocker, no exceptions, no overrides.
- Story TCs live in the story (§3); QA automates them in `08-qa/` and per-app `tests.py`, keeping the `US-…/TC-#` reference in the test name so results map back.

## 6. Updating things by hand — the rules

### Safe to edit directly (normal PR)
- `12-governance/` — weekly reports, risk register, decision log.
- `11-change-management/` — CRs, cutover plans, comms.
- Module docs **content additions** (a new story, an extra TC) — follow the template in `04-docs/05-modules/_templates/`, take the next free ID, add the traceability row, run the lint (§8).
- Runbooks, compliance docs, this guide.

### Requires a process (don't shortcut it)
- **Answering an open question:** never edit the answer into a story. Add the answer to `12-governance/01-open-questions.md` (status → `ANSWERED`, then `CLOSED(→BR-ID)`), update the BR's status to `CONFIRMED` citing who/when, then flip the story frontmatter. One commit, all three together.
- **PROPAGATION RULE (added 2026-08-08 after a real failure):** a ruling is NOT "recorded" until the SAME commit updates **every affected artifact** — business-rule file, **epic story text/TCs/field maps**, B2, registry, journeys, roadmap, story frontmatter — or the decision-log row explicitly lists `Pending propagation: <files>` with a deadline. Recording the rule while leaving stale epic text is forbidden; every Q&A round ends with a propagation sweep named in the commit message.
- **Changing a business rule:** only the named owner (finance for money rules) confirms; the PR must update the rule, its stories, and any golden test in the same change.
- **A-docs (`04-docs/01-spec/`):** owned by the design session. Don't hand-edit content — request a design change; corrections land as dated addenda at the bottom (see A17's scoreboard for the pattern).
- **B-docs:** PM/Eng Lead author; finance signs anything marked money.

### Never
- Edit `05-prototype/` — it is a generated export; changes go to the design session.
- Edit an existing migration, an issued-financial code path, or anything CODEOWNERS-flagged without its human owner.
- Resolve a `PROPOSED`/`OPEN` marker by picking a value inline — that's how silent production errors are born. Route it through the OQ registry.

## 7. PR conventions (humans and agents alike)

1. First line of the PR description: the story ID(s) — `US-MET-010` — this feeds the traceability matrix's code-refs column.
2. Complete the checklist in the template (tenant isolation, money immutability, audit, **dependency stories + journeys read**).
3. One module per docs PR; one story (or tight group) per code PR.
4. Commit style: `feat(billing): …`, `docs(metering): …`, `fix(payments): …`.

## 8. Before you push

Run what CI will run:
```bash
make lint          # backend style
make test          # unit + golden + isolation
python 10-scripts/02-trace_lint.py   # ID/traceability integrity (lands with Commit 3)
```
If `trace_lint` complains about a dangling ID, you referenced something that doesn't exist (typo) or deleted something still referenced — fix the reference, don't delete the check.

## 9. Reviewing an agent-authored module pack (the human's real job)

When a StorySmith run delivers a module, review in this order — it's 20 minutes well spent:
1. **§8 + registry:** are the minted OQs real questions (not laziness), routed to the right owner?
2. **§2 statuses:** is anything marked CONFIRMED that you don't recognize as signed? That's the #1 failure mode to catch.
3. **§7 formulas:** re-compute one worked example by hand.
4. **§5 origins:** spot-check three fields against B2.
5. **Capability matrix:** does the screen in `05-prototype/` actually show those columns/filters/actions?
Then approve the PR or annotate. You are the ratifier; agents are the drafters.

## 10. Questions

Open a **spec-open-question** issue (template provided) — it routes to the PM and lands in the OQ registry. If it blocks you today, say so in the issue.
