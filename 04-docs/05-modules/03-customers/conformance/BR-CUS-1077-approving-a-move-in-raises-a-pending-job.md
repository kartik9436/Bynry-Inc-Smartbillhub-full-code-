# BR-CUS-1077 — approving a move-in raises a pending job

**PO ruling 2026-09-16, verbatim: *"it should do B"***, choosing from three
options put to them with each cost named. The decision log row of that date
carries the ruling; the row beside it carries what this build decided and why.

**What was wrong.** The end-to-end clerk walk found that approving a move-in
did not complete at all. `SR-26-0024` on the demo tenant sat at `Under review`
with `outcome=move_in` already saved: the clerk pressed Approve, the outcome was
written, the approval was refused, and the request looked decided while being
nothing of the kind (`DEF-CUS-5398`).

---

## 1 · Where the pending row lives, and the three places it does not

| Candidate | Verdict |
|---|---|
| a draft **account** | ⛔ the Approve drawing forbids opening one, on all five outcomes: *"Not now — No account opens. Nothing is energised."* |
| **`move_records`** | ⛔ the record of a move that HAS happened. `BR-CUS-152` — nothing ever updates a row of it — and `account_id` is NOT NULL, which is the very account the job exists to create. |
| the **`service_requests`** row itself | ⛔ no schema at all, and the blueprint already draws `— draft` rows here. Refused for two reasons: an application's life ends at `approved` and a job's begins there, so one row would carry two lifecycles; and it fixes the queue to requests, so a move-in raised by any other door could never join it. |
| **a row of its own** | ✅ `move_in_jobs` — the shape the product already uses one outcome over. A new connection raises a **draft** `connections` row that appears on its tab at once, carries `request_id`, and whose own wizard asks for the rest. |

**It copies nothing.** The table holds the link to the request (NOT NULL, unique
per tenant), two states, who raised it and when. The applicant, the address, the
requested start, the services, the outstanding money and the unchecked documents
are read back through the link. The address is **walked** to the premises (hard
rule 8) and there is no address column.

**`outcome_ref` is deliberately not taken.** For a move-in that column already
means *the account this application produced*, and the Move-ins tab's `request #`
search leg reads it that way. Idempotency comes from
`uq_move_in_jobs_tenant_request` instead, which is a database guarantee rather
than a text convention.

**B18 §5.5.2's footnote is superseded for the move-in and the supersession is
stated** (B14 rule 41). *"A move-in is short enough that the wizard is the
record"* never weighed where an APPROVED move-in waits before any wizard opens,
and *"the queue stays empty until somebody finishes the wizard"* was the PO's own
reason for rejecting option C. **The footnote still holds for the step**: this
row carries none, so `move_reads.STEP_HAS_NO_STORE` is served on every row.

---

## 2 · What a clerk sees, and how they tell the two kinds of row apart

Read out of the rendered table by the walkthrough, on the demo tenant:

```
SR-26-0005 | — draft | Reyes, Antonio | 500 Main St · Unit 200 | No start date | … | Not started
SR-26-0024 | — draft | Dates, Proof   | 103 Willow Bend Dr     | No start date | … | Not started
MVI-26-0001| A-12048 | Kwan, Michael  | 88 Pine Vista · Unit 2 | 09/01/2026    | … | Due
```

Four differences, and every one of them is the server's rather than the screen's
inference: `row_kind` on the row · the drawn italic **`— draft`** where the
account number goes, with *"no account opens at approval"* in the tooltip rather
than a bare dash · the **request number** in the reference cell, as a link back
to the application · and **`Not started`** in the state cell, a minted code
declared UNDRAWN because B18's four segments are all facts about a move-in that
HAS an account.

---

## 3 · The proof

**Backend — 12 cases, `06-backend/tests/test_br_cus_1077_move_in_job.py`.** TEN
of them were proved RED first, in `pytest`, against `JOB_SHAPES["move_in"]
["raises"] = None` — the product exactly as it stood — and the failures are
quoted in that file. The eleventh passed in the red run and is named there
rather than counted as proof. The twelfth was a **strict `xfail`** holding the
other half of the ruling open; it went XPASS about an hour later when the lane
that owns the approval conditions landed it, and the marker is gone.

**Real PostgreSQL (hard-won law 14).** The double-press path was run against the
live cluster rather than the sqlite suite: the second press is refused by name
(`move_in_job_already_raised`), a forced race is refused by the database
(`duplicate key value violates unique constraint "uq_move_in_jobs_tenant_request"`),
and the connection is usable afterwards — which is the question law 14 actually
asks.

**The migration, on the live cluster.** `move_in_jobs` exists with
`relrowsecurity = t` **and** `relforcerowsecurity = t`, and the policy
`move_in_jobs_tenant_isolation` is on it.

**Frontend — 4 new cases in `MoveInsTab.test.tsx`**, each proved red first. Two
of them caught the ASSERTION being wrong rather than the screen, and both are
written up in the file: the rule id reaches the DOM and the code does not (B14
rule 32), and `Waiting` is also the filter's own option, so a whole-page
`not.toContain` was red over a correct screen.

**The browser walk — `10-scripts/br_cus_1077_move_in_job_walkthrough.mjs`, 22
checks, all passing.** It signs in as the demo owner, opens a request that is
still under review, presses **Approve**, picks the move-in radio, reads the
consequence table *before* pressing (*"Not now — No account opens"*), presses
**Approve and raise the build**, and then finds the job on the Move-ins tab —
rendered, not merely served. It counts the tenant's accounts on both sides
(**72 → 72**) and it follows the reference link back to the application,
asserting the whole address including the tenant segment, because `toContain`
cannot tell `/requests/x` from `/brazosbend/requests/x`.

⚠ **It also proves an ABSENCE on purpose:** no row control starts the move-in
wizard. That is `DEF-CUS-5434`, filed at the moment the row was built rather
than discovered later.

---

## 4 · What is left, named and routed

* **`DEF-CUS-5434` — the pending job has no door into the wizard.** A clerk sees
  the row and walks back to the application to act on it. It also means a
  move-in run any other way passes no `service_request_id`, closes no job, and
  leaves it on the tab beside the account it produced. The list states that on
  every response (`pending_job_closes_on_the_recorded_move`) rather than letting
  a clerk find out.
* **The MOVE-OUT is untouched.** The ruling names the move-in; widening it would
  be a lane widening a ruling. `DEF-CUS-5398` is `partially-fixed` for exactly
  that reason.
* **No back-fill.** Requests approved before today raised no job and get none —
  a row written now would claim a clerk approved a job that did not exist when
  they pressed.
