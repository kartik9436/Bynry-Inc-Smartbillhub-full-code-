# `CR-105-BRC03` · The bill template is decided at step 1 Scope

| | |
|---|---|
| Raised | 2026-09-14 |
| Requester | Product Owner, in the working chat session |
| Branch | `claude/eager-johnson-r0k88b` · block `CR-105`–`CR-109`, suffix `BRC03` |
| Module | billing |
| Classification | **CHANGE** — and it is the ONLY change in the bill-run rebuild |
| Version | allocated at build time through `allocate.py version --bump change` |

## 0 · Capture — the requester's words, verbatim

> *"in this step 1 scope - you will ahve to also decide on billing template"*

Said while reviewing the action-by-action table of the four-step bill run, immediately after
confirming that table correct.

## 1 · Classify — why this is a CHANGE and the rest of the rebuild is not

`13-change-process.md` §1: *when it is ambiguous it is a DEFECT, not a change, because filing
our misunderstanding as a "change" quietly converts our error into the customer's new
requirement.*

Everything else in the bill-run rebuild is the product failing to match a drawing the PO already
signed — `DEF-BIL-5247` (four steps, not six), `DEF-BIL-5255`/`5256` (the screen bodies),
`DEF-BIL-5258` (chips counted in the browser), `DEF-BIL-5269` (stage numbers), `DEF-BIL-5270`
(read continuity). **Our miss, routed as defects.**

**This one is different: the blueprint does not draw a template control, and the PO is asking
for one.** That is the agreement moving, so it is a CR.

## 2 · What signed statement is reversed, with its chain

**The blueprint deliberately has no template picker, and it is an INHERITED decision rather than
a finding of the redraw.** `p047`'s `DEFAULTS` group holds four controls — *when there is no
reading · when a bill looks unusually large · unusual days · label this run* — and no template.

`p087` and `p099` both address the absence and **neither re-argues it**. Both record the removal
of an on-screen panel headed *"What this step no longer asks you"*, which existed to explain
*"why a template picker and a typed due date are absent"*:

> **REMOVED. Ruled.** *"It explains why a template picker and a typed due date are absent — a
> note about a design decision taken long ago, printed to a clerk on every run. Its content
> belongs in this document, and it is here. If you want it kept on screen, say so and it
> returns as a closed disclosure."*

⚠ **THERE IS NO DECISION-LOG ROW FOR THE ORIGINAL EXCLUSION.** It predates this repo's record
and the drawing simply carries it forward. **So this CR does not overturn a signed ruling — it
supplies one where none existed**, and that is why the reasoning is written out here rather
than left as a one-line change.

**No ❄️ FROZEN B4/B5 figure is touched.** No money math moves.

## 3 · Impact

| Surface | Effect |
|---|---|
| Screen | Step 1 Scope gains a template control beside the four drawn defaults |
| Screen | The counts card gains a template-resolution line — own · run's pin · **NEITHER** |
| Screen | Step 3 Sign off gains a gate: a run with unresolvable templates does not release |
| Screen | Step 4 Send's specimen renders with the template pinned at step 1 |
| API | The run carries the pin from creation instead of receiving it at issue |
| Data | No new table. `template_pin_explicit` already exists on `issue_run` |
| B14 rule 41 | **A DIVERGENCE FROM THE DRAWING, RECORDED.** A PO ruling outranks a drawing; the drawing is not amended by us |
| Open questions | None opened, none closed |
| Demo fixture | Unaffected |

## 4 · What is already built, and is now in the wrong place

**The mechanism exists and fires too late.** `issue.py` describes it in its own words:

> *"an EXPLICIT pin typed by the clerk deliberately governs the whole pass"* — `template_pin_explicit` on `issue_run`.

The run already carries two counters, `template_resolved_per_account` against
`template_pinned_by_run`, and *"a run where both are non-zero is NORMAL, not an error"*.

⚠ **AND THE ARGUMENT FOR MOVING IT IS A THIRD FIELD THAT ALREADY EXISTS.** `issue.py` tracks
**`template_problems`** — *"distinct reasons a bill could not resolve its own template, with the
number of bills each affected"*. **A bill CAN fail to find a template**, and today that is
discovered AT ISSUE — after Scope, after Check, after the clerk has signed off. **This CR turns
a step-4 surprise into a step-1 count**, which is the same argument `p048` makes for moving
pricing into step 1: *"step 2 opens with money on every row."*

**Lanes building right now:** none. The four journey lanes have landed.

## 5 · Size, in plain English with a figure

**Small, because nothing is invented.** One control on Scope, one line on the counts card, one
gate on Sign off, and the run carrying a value it already accepts at a later moment. The write
path, the per-account fallback, the two counters and `template_problems` are all built. The
estimate is **one wave inside the Scope screen's own build**, not a wave of its own.

## 6 · Execution

Through `r11`, as part of the new Scope screen. **Deciding is not stamping** —
`assemble_document` continues to stamp the template version onto each invoice AT ISSUE and
freeze it, so a template edited between Scope and Send cannot silently change a bill a clerk
already approved. Step 1 records the CHOICE; issue pins the VERSION.

## 7 · Version

**`2.267.0`**, allocated 2026-09-14 through `10-scripts/allocate.py version --bump
change` and verified against the REMOTE at push time. Written into all four
literals (`07-frontend/package.json`, `07-frontend/package-lock.json` ×2,
`06-backend/pyproject.toml`) and carrying a `CHANGELOG.md` entry.

⚠ **THAT ENTRY ALSO CARRIES TWO FIXES THIS CR DID NOT AUTHOR**, and says so in
its own words: `DEF-BIL-5270` (a run checks where each account's money starts)
and `DEF-BIL-5271` (a decision reaches the money) landed earlier on this branch
with no version pointing at them, because at that moment the four version files
held a sibling's unpushed `2.266.0`. Folding them in here costs nothing and
leaves no orphan — the maintenance process requires a close to tell the reporter
WHICH BUILD to look in, and *"none"* is the answer an unversioned fix gives.

## 7b · What was BUILT under this CR, and what is owed

**BUILT (2026-09-14, version `2.267.0`):**

| | |
|---|---|
| `bill_runs.template_id` | migration `billing/0028`, a nullable FK to `bill_templates`, `PROTECT`. **The template and no version number** — the freeze does not move. |
| `runs.validated_template_pin` | the two refusals, at CREATION: a template that is not this tenant's (HR-1, answered as absent) and a template with **no PUBLISHED version** (BR-BIL-026). Neither leaves a row. |
| `runs.create_run(template_id=…)` | writes it, and names it in the `bill_run.created` audit row. |
| `BR-BIL-1041` | written into `04-docs/05-modules/07-billing/02-business-rules.md`, CONFIRMED. |
| tests | `06-backend/tests/test_br_bil_1040_run_case_defaults.py`, proved on **real PostgreSQL 16**. `test_deciding_is_not_stamping__no_version_is_pinned_at_scope` is the one that guards the freeze. |

**OWED, AND FILED AS `DEF-BIL-5302` RATHER THAN LEFT AS A NOTE** (hard-won law 2
— a column nothing reads is a feature that does not exist, and every check stays
green over it). Two call sites, both small, both in files two other billing lanes
were editing at the same time, which is why this lane reported them instead of
reaching in:

1. **`api._template_pin_for` must prefer the RUN's pin over the request body**,
   returning `template_pin_explicit=True` for it — the run's pin *is* a clerk's
   typed statement about this run, which is exactly what that flag means.
2. **The sign-off gate must refuse a run with an unresolvable template**, which
   is the same refusal `validated_template_pin` already makes at creation, made
   again at the last moment before anything is billed.

Until both land, a clerk choosing a template at Scope is choosing something the
issue pass does not yet read.

## 8 · Rollback

Remove the control and the gate; the run stops carrying the pin and `issue_run` resolves
templates exactly as it does today. **No data migration, so rollback is a code revert only** —
runs created with a pin simply have a field nothing reads.
