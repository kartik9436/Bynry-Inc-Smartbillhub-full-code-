## CR-071 — What the customer portal must feel like: a response-time specification, and the load it holds at

### CR-071 · 0 · CAPTURE — the Product Owner's words, verbatim

Two messages, 2026-09-03, in the working session.

**The requirement:**

> *"When you design customer portal keep in mind that we might have multiple utilities / multiple
> tenants, their users will login or use it as guest portal there can be 500 users or 100 users from
> various tulities using customer portal in such case our design should allow them to login as per
> response time we agreed and also it should not hamper performance of back office user - ensure you
> handle this part well"*

**And, when told that no agreed response time existed anywhere in the repository:**

> *"If you have to write this in CR please do*
> *If you are consumer for utility A and you want to access your utility billl or make payment or have
> any question using portal what will be your expectations in terms of response time ? Figure that out
> and write it as response time specifications"*

⚠ **THE SECOND MESSAGE IS A DELEGATION, NOT A QUESTION.** The PO was asked for a number and handed the
question back with its terms: work it out from the customer's side and write it down. So the figures in
`04-docs/05-modules/15-portal/11-response-times.md` are **ours**. They are not a PO ruling and must
never be cited as one. If one is wrong, we reasoned badly, and correcting it is a change request.

### CR-071 · 1 · CLASSIFY

**A requirement, not a defect** — it adds an obligation nobody had written down, rather than reporting
that something built is wrong. It is nonetheless **urgent**, because `CR-068`'s first wave was being
built the same hour and two of its consequences are cheap now and expensive to retrofit.

### CR-071 · 2 · WHAT SIGNED STATEMENT IS BEING REVERSED — quoted, never summarised

**B6's planning table**, `04-docs/02-decisions/06-non-functional-requirements.md`:

> | Concurrency | **low (1–2 staff/tenant)**, but do not architect a hard ceiling | — |

That line was written on 2026-08-07, when every user of this product was a member of staff. It is not
wrong; it is **out of scope of what it now has to describe**. The supersession is narrow and stated:

- **It stays true of STAFF.** One or two clerks per tenant remains the staff assumption.
- **It is no longer the platform's concurrency figure.** `NFR-38` sets that at **500 concurrent portal
  users spread across many tenants**, guests and signed-in together, while the back office is working.
- **`NFR-5`'s design rule is untouched** — no hard cap is coded anywhere, for staff or customers.

**Nothing ❄️ FROZEN is touched.** B4 and B5 are money math; this is load and latency.

### CR-071 · 3 · IMPACT

| Surface | What changes |
|---|---|
| **B6** | Four new rules, `NFR-38`–`NFR-41`: the concurrency figure, the three isolations, bounded reads, and the guest surface as the cheapest thing we own |
| **The portal module** | A new file, `11-response-times.md` — ten targets by errand, two rules that outrank the table, five prohibitions, and how each is proved |
| **`CR-068`'s plan** | Wave A gains the portal's own queue, worker, connection budget and per-tenant rate limits. Every later wave's walkthrough **prints its measured time** instead of asserting a target was met |
| **Open questions** | `OQ-CWP-1510` is **CLOSED by this CR** — it asked for the target and the PO delegated it |
| **Existing rules** | None reversed. `BR-CWP-022` (sixty a minute per address) gains a per-tenant dimension; `BR-CWP-047` (no cached balance) is **reaffirmed and made load-bearing** — it is the obvious way to hit these numbers and it is forbidden |
| **The demo fixture** | Unchanged |
| **Code already shipped** | None. `CR-068` has no code yet, which is why this arrived at the right moment |

### CR-071 · 4 · WHAT IS ALREADY BUILT

**The isolation pattern exists and is proven twice.** `celery-billing` and `celery-integrations` are
routed, consumed by their own workers, capped, healthchecked, and enforced by `G59`'s clauses. The
portal's queue is a third instance of a shape this product already runs — not a new idea.

**The throttle exists.** `BR-CWP-022`'s sixty-a-minute anonymous throttle is the one the product
already applies to its three existing public endpoints. What is missing is the per-tenant dimension.

**Nothing about connection budgeting exists.** That is genuinely new work.

### CR-071 · 5 · SIZE

Small, and mostly inside `CR-068` wave A rather than beside it: one compose service and its routing,
one settings change for the connection budget, one throttle dimension, and a measurement line in every
walkthrough. **The expensive half is discipline, not code** — bounded reads and no caching of a
balance, held to on every screen for the life of the module.

### CR-071 · 6 · THE SPECIFICATION

Lives in `04-docs/05-modules/15-portal/11-response-times.md` and is not duplicated here — one source,
derived nowhere (hard-won law 5). In one paragraph for a reader who wants the shape:

**A guest bill lookup answers in 400 ms at the 95th percentile; the "what do I owe" screen in 600 ms;
signing in is allowed 900 ms because a password check must burn real time or it is not a password
check; a payment's own half is 800 ms and the processor's half must never be silent. Something
meaningful appears within one second of every interaction, nothing waits silently past three seconds,
everything resolves by fifteen, and a payment always resolves to a definite state — because the second
press is how people double-pay.** All of it at 500 concurrent users with the back office unaffected.

### CR-071 · 7 · VERSION

No version of its own — it is documentation plus rules that `CR-068`'s waves carry. The wave that first
implements the queue and the budget bumps the version and says so in the changelog.

### CR-071 · 8 · CLOSE, AND THE ROLLBACK

**Rollback:** the targets are documentation and can be amended by a later change request. The one piece
of infrastructure — the portal's own queue and connection budget — rolls back by routing the portal's
jobs onto the default queue again, which is the state the product is in today. Nothing here writes
data, so nothing needs unwinding.

**Status: written, and its rules are in force.** The `CR-068` wave A lane was told the same hour, since
it was laying the foundation as this was ruled.
