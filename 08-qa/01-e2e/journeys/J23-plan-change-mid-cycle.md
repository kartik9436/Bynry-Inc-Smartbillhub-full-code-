# J23 — Plan change mid-cycle (14 days on the old plan, 16 on the new, one bill, and it still reprints in December)

---
id: J23
tier: 2
rules: [BR-CUS-010, BR-CUS-011, BR-CUS-013, BR-CUS-014, BR-MET-007, BR-MET-040, BR-MET-041, BR-MET-042, BR-RAT-030, BR-BIL-004, BR-CUS-040]
stories: [US-MET-003, US-CUS-003, US-CUS-016, US-CUS-017, US-RAT-012, US-BIL-005]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** A customer changes plan in the middle of a billing cycle, and one
bill has to carry both plans. This is the journey that could not have been
written before 2026-08-11, because the system had no way to *say* that a unit
was on one plan for part of a month: `unit_plan_assignments` had existed since
W1 and had never been written, so the only plan a unit knew was today's.

The PO settled the cause that day — a unit holds a **plan** (the bundle across
its services), not one service's rate schedule — and the dated history became
writable. This journey exercises what that buys: **a mid-cycle change is
billable**, the change is attributable, the previous plan's coverage ends
exactly where the new one begins, and a bill reprinted months later still shows
the prices that were actually charged.

**Fixture.** Tenant brazos-bend · Apt 4B, a unit taking **electric + water**
(which is itself the point: one plan covers both — the pre-ruling column could
only have recorded one of them) · account A-10432, Sarah Chen, active ·
Residential Standard **published** · Senior / Low-income **published** · cycle
**Jun 1–30** (30 days) · change effective **Jun 15** · actors Dana Whitfield
(System Admin), Marcus Vega (Billing Clerk).

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · history · audit) | Rule |
|---|---|---|---|---|
| 1 | **Jun 1** — the unit is on Residential Standard, assigned effective Jun 1 | `units.rate_plan_id` = Residential Standard; ONE open `unit_plan_assignments` row {plan, plan_version snapshot, from Jun 1, to NULL, source, actor, reason} | Exactly one open row per unit (partial unique index). `history_recorded` is TRUE — it is no longer a status field that can read false; a missing row now RAISES, because a plan column that moves without its coverage is a hole that surfaces months later inside a bill | BR-CUS-010/011/013 |
| 2 | **Jun 15** — Sarah qualifies for the senior rate; Marcus changes the plan effective Jun 15 | Residential row CLOSED at **Jun 14** — the day before the successor starts, so no day is covered twice and none is uncovered. Senior row opens Jun 15, to NULL, `plan_version` frozen at assignment | The unit's coverage now reads "Residential Jun 1–14, Senior Jun 15–" — the thing a bill run can price. A current-plan column can only ever say "Senior" | **BR-CUS-011** · BR-CUS-014 |
| 3 | **Jun 15** — the ACCOUNT is not written to | No account-side plan row exists and none is created (BR-CUS-029 superseded, PO 2026-08-11) | The account's plan resolves THROUGH the unit, so unit and account cannot disagree — there is only one of them. The account's own attributes are untouched: deposit, credit tier, tax exemption + certificate + expiry, autopay, language, NSF count, bad address | **BR-CUS-014** (as amended) |
| 4 | **Jun 20** — a Billing Clerk tries to change the plan on a **locked** unit | Refused, `BIZ-LOCKED` naming BR-MET-007; the unit comes back still locked and still on its Jun 15 plan; NO history row is appended | The lock gates by permission rather than freezing the unit: the same call by a System Admin succeeds. A refusal that leaves a half-written history would be worse than no lock | **BR-MET-007** |
| 5 | **Jul 1** — the June cycle runs | ONE bill for A-10432 carrying **both** plans: 14 days priced on Residential, 16 on Senior, each period group resolving the plan version recorded in step 1/2 — never today's | Fixed charges prorate by calendar days (B4.3); metered usage with a read is NOT prorated (B4.3 as amended 2026-08-11 — the reading IS the consumption). Balanced JE; delivery queued; audit | BR-CUS-014 · B4.3 |
| 6 | **Dec 3** — Sarah disputes the June bill; it is reprinted | Renders the ISSUED invoice **verbatim** from its own locked-at-issue payload — never recomputed, never re-resolved through today's assignments | Byte-identical document. This is why no account-side plan snapshot is needed: reprint fidelity comes from the bill, not from a live row that could since have moved | **BR-CUS-040** · BR-BIL-004 |
| 7 | **INVARIANCE** — the history is append-only and complete | A plan withdrawn before it ever applied is CLOSED, not deleted (`assigned_to < assigned_from`), so a same-day correction leaves evidence of both the mistake and the fix; readers filter `assigned_to IS NULL OR assigned_to >= assigned_from` for "was ever in force" | No gap and no overlap in coverage between Jun 1 and today; exactly one open row throughout; every change carries who/when/from→to/reason/source | BR-CUS-010/011 · hard rule 4 |

**⚠ What is NOT runnable yet, and must not be read as covered.** Steps 5 and 6
describe billing, and billing has no `invoices` table. Steps 1–4 and 7 are
exercised today by `06-backend/tests/test_us_met_003_plan_history.py` and
`test_us_met_003_plan_lock.py`; steps 5–6 are the CONTRACT the bill run must
satisfy when it lands, written now so the bill run is built against it rather
than discovering it afterwards.

**⚠ One guard this journey assumes and the code does not yet have.** Step 2
backdated behind an **already-issued** bill is not refused. The guard move-out
carries — no date behind the last issued bill — belongs on this path for
exactly the same reason, and cannot be written until there are invoices to ask.
Named here rather than left to look covered.
