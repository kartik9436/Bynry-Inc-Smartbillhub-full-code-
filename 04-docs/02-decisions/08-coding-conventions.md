# B8 — Coding Conventions (Eng-Lead authored, 2026-08-08 — replaces the placeholder house style)

> Enforced by CI (lint gates below). Applies to humans AND coding agents equally. Companion: B12 engineering plan (error catalog, generation process, traceability standard).

## LAW 0 — THE SIMPLICITY LAW (PO-directed 2026-08-09: "human will also look at this code — do not over-complicate it")
Code is written for the human reader FIRST. Concretely: boring, explicit code beats clever code — no metaprogramming, no deep inheritance, no premature abstraction (a pattern earns an abstraction on its THIRD use, not its first); one service function reads top-to-bottom as the story's §1 flow, in the story's vocabulary (glossary A16 terms as names); small functions with names that say what they do; no framework magic where a plain function works. A junior developer must be able to follow any service end-to-end without a tour guide. The shared components (ONE DataTable etc.) are the approved reuse — everything else stays plain. Reviewer test at ratification: "could the PO's future hire read this cold?" If simplicity and DRY conflict, simplicity wins.

## Python / Django (06-backend)
- **Formatting/lint:** ruff + black, line 100; import order stdlib/django/third-party/local. **Types:** hints mandatory; mypy `--strict` on `services.py`/engines; `Decimal` ONLY for money (float in a money path fails CI by grep-gate).
- **Layering per app (one app = one module):** `api.py` (thin: parse → call service → serialize; NO business logic) → `services.py` (the ONLY write path; one service function = one transaction boundary) → `selectors.py` (read path; no writes) → `models.py` (tables owned per B2; no cross-module model imports — cross-module data flows through the owning module's service/selector or the reviewed FK set).
- **🔒 sensitive files** carry `HUMAN-OWNED` in the module docstring (RLS, rating engine, posting service, idempotency keys, rounding, migration ordering). **As amended by PO 2026-08-09 ("AI will do it; we will review it later as human"):** AI authors them implementing the SIGNED rules (B4 ❄/B2) only; each implemented file adds `HUMAN-REVIEW-PENDING` + a row in the human-review ledger (12-governance/09, G7-enforced) and never reaches RATIFIED without a recorded human sign-off.
- **Transactions & locking:** `transaction.atomic` at the service boundary; `select_for_update` on run/batch heads; idempotency check INSIDE the transaction; partition-aware filters (tenant_id + period) on the big five tables always.
- **Errors:** raise only catalog exceptions (B12 §3) — never bare ValueError into an API; every BIZ refusal carries its BR-ID.
- **Errors ACROSS a seam — added 2026-08-11 (DEF-047), and it is the other half of the layering rule above.** A seam adapts BOTH directions: if it maps the owner's RESULT onto the caller's contract, it must map the owner's REFUSAL too, in the same file. Each module owns its own exception hierarchy (`apps.rating.pricing.errors.RatingError`, and the same shape elsewhere) precisely so it need not know its callers — which means an untranslated refusal crosses a module boundary as a type the caller has no reason to catch, and lands wherever the stack unwinds to. Billing's run loop catches per account so one bad account never stops the other 499; rating raised neither type it caught, so ONE unpriceable account killed a 1,124-account run while every test stayed green (the tests all used billing's own exception types). The rules: (1) translate at the seam, never at the call site — one translation per module pair, not one per caller; (2) resolve the owner's error base class BY NAME, the same late binding the seam already uses for its callables, so neither module imports the other; (3) catch the owner's BASE class only — an `AttributeError` inside the owner is a bug in the owner and must never be reported to a user as a business refusal; (4) chain with `raise … from`, so the owner's own words and the rule that fired survive the translation.
- **Tests:** pytest; colocated `tests/` per app; every story TC = one test named `test_us_<mod>_<nnn>_tc<k>__<slug>`; golden tests under `tests/golden/` (xfail→must-pass discipline per HUMAN-GUIDE §5); the isolation suite runs on every PR — red = merge-blocked, no override.

## TypeScript / React (07-frontend)
- **Formatting/lint:** eslint (strict) + prettier; `strict: true`, `noImplicitAny`; no `any` (CI-gated), no inline styles — Modernist tokens only; files named for screens (`RunBillsWizard.tsx` = S31).
- **Structure:** `src/features/<module>/` mirrors doc modules; shared `src/components/` for the IS-standard primitives — ONE `DataTable` implements the IS-5 capability row (search/filters/dynamic columns/server pagination) config-driven; ONE `ConfirmDialog` implements IS-6 consequence messaging; state pattern per IS-7/A18 (skeletons, empty, error, denied).
- **Server state:** TanStack Query + a generated OpenAPI client (from A11 spec) — no hand-written fetch paths; mutations invalidate by entity key; optimistic updates NEVER on money actions.
- **i18n:** every user-visible string is a catalog key (TD-16); server error `message_key` + params rendered client-side; NO concatenated sentences (translation-hostile).
- **Forms:** schema-validated (zod) mirroring server VAL codes; server is authoritative — client validation is UX only.

## Both sides — the TRACEABILITY STANDARD (PO-directed: humans must be able to read it)
Every code file that implements a story carries a header block; every rule-enforcing line carries an inline BR tag; tests embed TC IDs. Format (machine-parseable, CI-validated by the code-trace linter):
```
# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (EP-BIL-01 §Issue)  Screens: S31
# Rules:    BR-BIL-011 (anatomy) · BR-BIL-022 (numbering) · BR-BIL-024 (due date) · BR-BIL-026 (template pin)
# Tests:    US-BIL-005/TC-1..8 · GT-17 · Journeys: J2-step8, J19, T5-05
# Impacts:  ledger posting (US-LED-001) · delivery queue (US-NOT-002) · S30 list
# ───────────────────────────────────────────────────────
```
Inline: `# BR-BIL-026: pin template+version+language at issue — reprints render this forever.`
Comments explain WHY-per-the-rule, never what the next line does. The header is the door back to the requirement; the PR description's first line remains the US-ID (HUMAN-GUIDE §7).

## CI gates (all merge-blocking)
ruff/black/mypy · eslint/tsc · pytest incl. golden + isolation (zero-tolerance) · trace_lint (docs) · **code-trace lint** (headers present, IDs resolve, no orphan code) · float-in-money grep-gate · migration-guard (ordering + no edits) · security-scan · coverage ≥85% services, ≥70% overall (ratchet-up only).

## NO HARD-CODED VALUES — universal, every surface (PO ruling 2026-08-20)

**PO verbatim:** *"please write an universal rule that do not use hard coded items
- in frontend, backdn, fiture if possible and any other places"*.

Ruled after an audit of one day's own work found **three** in code written by the
lane that was asserting it was clean. That is the point of writing it down: a
literal never looks wrong at the moment you type it, because it is correct then.

### The rule

> **A value that another part of the system also knows is DECLARED ONCE and
> referenced. If two places must agree on it, neither of them may spell it out.**

It binds **backend, frontend, fixtures, seed data, tests, migrations, styles and
catalogs** — every surface, because the failure is identical everywhere: two
copies of one fact, each individually well-formed, drifting apart with nothing
able to see it.

### Where each kind of value lives

| Kind | Home | Never |
|---|---|---|
| Money figures in fixtures / seed | `core/sample_fixture.py`, **cited or derived** | a literal in `sample_data.py` |
| A rule's figure | the `BR-` row that ratified it, quoted | re-typed at the call site |
| Sizes, spacing, colour, type | the `@theme` block in `tailwind.css` | `min-w-[260px]`, `#eae9e9`, `13px` |
| Any user-visible string | the i18n catalog | a string literal in a component |
| Service / status / type vocabularies | the module's enum or lookup list | a code compared to `"BASE-W"` |
| A column's precision | B4 / the model, once | repeated in a serializer |

### DERIVE IT WHEN YOU CAN, AND THE REASON IS NOT TIDINESS

The water fixture's version history was three prices — `4.24 / 6.89 / 8.48`. They
were correct. Replacing them with *"`WATER_TIERS` × a stated uplift of 1.06"*
**immediately exposed a wrong digit in the next row**: the 2027 filing's middle
tier is `7.31`, and `7.30` had been typed. Three literals are each well-formed,
and nothing in the product could have told them from three right ones.

**So: state the INPUT and compute the rest.** A derived value cannot drift from
its source, because it has no separate existence to drift with.

### What is legitimately a literal — the rule is unusable without this

* **A fact with no second home.** The fixture's `WATER_V2_FROM = "2026-08-01"` is
  a date chosen so a version lands *after* the billed June period (BR-RAT-007).
  Deriving it would hide the choice; naming it states it.
* **Geometry that means nothing.** An icon's `viewBox="0 0 24 24"`.
* **Protocol constants** — HTTP statuses, a `CHAR(3)` currency width.
* **A test's own expected value.** A test that computes its expectation the way
  the code does asserts nothing. Test fixtures *should* carry literals.

### The test to apply

**"If this number changed, how many places would have to change with it?"**
More than one, and it belongs somewhere else. **"Could this be wrong right now
without anything failing?"** Yes, and it must be derived or cited.

### What this does NOT yet have, stated honestly

**No gate enforces it.** A checker that flagged every literal would drown in the
legitimate ones above, and a rule enforced badly is switched off. It is a review
obligation today — the same standing as most of B14 — and the honest first step
toward a gate is narrow: fail a money literal in `apps/*/sample_data.py`, where
the convention already says every figure is cited, and where the violation found
on the day this was ruled actually lived.
