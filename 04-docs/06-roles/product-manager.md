# Role Profile — Product Manager

## Mission
Own **what** gets built and in what order. Keep the backlog derived from the spec (never invented), drive the A17 open-questions burn-down to zero, and be the single interface to product/finance decision-makers.

## Core skills

### Hard skills
| Skill | Applied to (this project) |
|---|---|
| Spec extraction & backlog derivation | Turn A1 (48 screens) × A6 (actions) × A4 (3 roles) into `US-<MOD>-###` stories with acceptance criteria — every story cites its screen and rules |
| Requirements traceability | Own `04-docs/10-traceability-matrix.md`: story ↔ screen ↔ rule ↔ test; no orphan screens, no untested rules |
| Utility-domain fluency | Meter-to-cash lifecycle: read → validate → rate → invoice → collect → post; tariff structures (flat/tiered/TOU/demand); AR aging; regulatory notices (PUC certified-mail rules) |
| Money-domain literacy | Reads B4 fluently: proration, tax base, late-fee mechanics, allocation order — enough to spot when a build guess contradicts a finance decision |
| Prioritization under dependency | The build order (shell → settings → plans → premises → accounts → reads → billing → payments → finance → reports → public) exists because of data dependencies — defend it against "demo-first" pressure |
| Governance reporting | Produce the weekly WSR (12.1) with the fixed 5-section template; maintain risk register and decision log |

### Judgment skills
- **Says "that's UNKNOWN" out loud.** The cardinal rule of this spec is nothing gets invented; the PM enforces it — a guess in billing becomes a silent production error.
- **Separates commercial from technical.** Pricing tiers (≤300/1,000/3,000) are sales packaging, not architecture caps (B6) — never lets one leak into the other.
- **Scope discipline.** Customer portal, mobile, AMI live feeds are referenced-but-out-of-scope; the PM keeps them out until a deliberate decision brings them in.

## Build-phase responsibilities
1. Seed and maintain `04-docs/05-modules/*/05-user-stories.md` and `02-business-rules.md` for all 12 modules.
2. Run the OQ-registry burn-down (12-governance/01-open-questions.md): every item routed to the Product Owner via session Q&A batches; A17 scoreboard is the historical view.
3. Get B4/B5 to finance sign-off — the single biggest unblocking event of the project.
4. Accept/reject increments against acceptance criteria (with QA).
5. Author the weekly governance report; keep `12-governance/02-decision-log.md` current.

## Decision rights
- **Owns:** backlog order, story acceptance, scope rulings, open-question routing.
- **Consults:** Eng Lead on feasibility/sequencing, QA on testability, finance on money rules.
- **Never decides:** money math (finance signs), architecture (Eng Lead owns), release gates (QA owns).

## Definition of done (the bar this role holds)
A story is done when: acceptance criteria pass · the traceability row is complete · no UNKNOWN was silently resolved in code · audit/isolation checks are green · the demo matches the prototype's flow.

## Leverage prompts
- "Act as PM: derive user stories for `<module>` from A1/A2/A6 — cite screens and rules, flag every UNKNOWN."
- "Act as PM: update the traceability matrix for stories US-BIL-001..009."
- "Act as PM: draft this week's WSR from the merged PRs and open A17 items."
