# B-CWP-RT — What the customer portal must feel like, in seconds

**Status: RATIFIED by delegation (PO 2026-09-03).** The Product Owner was asked for the target and
answered by handing the question back with its terms: *"If you are consumer for utility A and you want
to access your utility billl or make payment or have any question using portal what will be your
expectations in terms of response time ? Figure that out and write it as response time
specifications"*. So this file is the answer, reasoned from the customer's side and written to be
built against. It closes `OQ-CWP-1510`. **It is ours, not the PO's** — if a figure here is wrong, it is
wrong because we reasoned badly, and changing it is a change request, not an inline edit.

---

## 1 · Who is on the other end, because that is what sets the numbers

A residential customer opening this portal is **not browsing**. Almost every visit is one of four
errands, and each has a mood attached:

| The errand | When it happens | What they are feeling |
|---|---|---|
| *What do I owe?* | a bill arrived, or a notice did | wary — they want the number and they want it to be right |
| *Let me pay it* | often the last day, often late at night | anxious — a late payment has a consequence |
| *Why is it so high?* | after a bill that surprised them | already annoyed before the page loads |
| *Something is wrong* | a burst main, no water, a wrong reading | urgent, sometimes standing in the street |

Three things follow from that, and they matter more than any single number:

**They are on a phone, on mobile data.** Whatever the server takes, the network adds. A 4G round trip
in a US suburb is commonly 80–200 ms and can be 600 ms on a bad cell; on the edge of a rural service
area it is worse, and rural is where a lot of small utilities are. **So the server's budget is not the
customer's experience — it is roughly half of it.**

**They did not choose us.** A customer cannot switch water companies because the portal is slow. That
sounds like it lowers the bar, and it does the opposite: a slow portal does not lose a customer, it
produces a **phone call to the utility's one or two office staff** — which is precisely the cost this
product exists to remove. A portal that is slow enough to abandon converts itself into the workload it
was built to replace.

**Their comparison is not other utility portals.** It is every other page on their phone. They do not
grade us against a peer; they grade us against what a page normally does.

## 2 · The thresholds this is built on

These are not invented for this document. They are the long-standing findings about human response
that interface work has used for decades:

- **Under 0.1 second** — feels instantaneous; the person believes they caused it directly.
- **Under 1 second** — their train of thought survives. They notice the delay and do not mind it, and
  **no progress indicator is needed**.
- **Under 10 seconds** — the outer limit of holding attention on one thing. Past a few seconds they
  need to be told something is happening, or they start pressing buttons again.
- **Past 10 seconds** — they go and do something else, and on a payment they *press pay a second time*.

Mapping our four errands onto that gives the shape of the specification: **the answer to "what do I
owe" belongs in the under-one-second band**, because it is one fact and they came for exactly it.

## 3 · The specification

**Measured at the server**, per endpoint, as the time from request received to response finished —
excluding network and rendering, because those are what we cannot control and must therefore leave
room for. **`p95` is the number that gates a build**: half of all requests being fast is not a service,
and the twentieth-worst request in a hundred is what a customer actually remembers.

**All of it holds at `NFR-38`'s load — 500 concurrent portal users across many tenants — while the back
office is in use.** A figure met on an idle machine is not a specification, it is a demonstration.

| # | What the customer is doing | `p50` | **`p95`** | `p99` | Why this number |
|---|---|---|---|---|---|
| **RT-1** | **Guest bill lookup** — types a bill number and a postcode | 150 ms | **400 ms** | 800 ms | Two indexed reads and no join. It is the front door, it is unauthenticated, and it is what a stranger can aim traffic at — so it is the cheapest thing we own |
| **RT-2** | **Signing in** | 400 ms | **900 ms** | 1.5 s | Deliberately slower than everything else: a password check must burn real time (~200–300 ms of hashing) or it is not a password check. **This is the one place where slower is safer, and the budget says so out loud** |
| **RT-3** | **"What do I owe" — the first screen after signing in** | 250 ms | **600 ms** | 1.2 s | The errand itself. Account, balance, next due date: three indexed reads. With a 200 ms network round trip this lands near one second in the hand, which is the band where thought is not interrupted |
| **RT-4** | **The bill list** | 300 ms | **700 ms** | 1.4 s | One page of rows, server-paginated (`NFR-3`). It must not grow with how long they have been a customer |
| **RT-5** | **Opening a bill document** — time to first byte | 400 ms | **1.0 s** | 2.0 s | A stored file, streamed. First byte is the promise; the rest is size and network |
| **RT-6** | **Submitting a payment — our half** | 300 ms | **800 ms** | 1.5 s | Everything up to handing off to the processor. **Their half is not ours and must never be silent** — see RT-6b |
| **RT-6b** | **Payment — what the person sees** | — | **feedback inside 1 s, always** | — | The processor can take as long as it takes. What is not allowed is a screen that says nothing while somebody's money is in flight. A payment that takes 8 seconds with a clear "we are asking your bank" is fine; a payment that takes 3 seconds in silence is not, because **the second press is how people double-pay** |
| **RT-7** | **Reporting a problem / asking a question** | 300 ms | **800 ms** | 1.5 s | A write and an acknowledgement. The burst-main case is the urgent one: they are outdoors, on a bad signal, and need to see that it was received |
| **RT-8** | **Submitting their own reading** | 300 ms | **800 ms** | 1.5 s | A write plus validation. If the reading is implausible the refusal must arrive in the same budget — a slow refusal reads as a broken form |

### The two rules that matter more than the table

**RT-9 · Something meaningful within one second, on every interaction.** Not a spinner — the shell, the
heading, the part of the answer we already have. A person who sees the page responding waits; a person
looking at a blank rectangle presses again.

**RT-10 · Nothing waits silently past three seconds, and nothing waits forever.** Past three seconds
the screen says what is happening in words a customer understands. At **fifteen seconds** any request
resolves — to an answer or to a sentence they can act on. **A payment resolves to a definite state,
always**: "we took it", "we did not take it", or "we are checking with your bank and will email you" —
never an ambiguity a customer has to resolve with a phone call.

## 4 · What this forbids

Stating a target is only half a specification; here is what it rules out, so a review can catch it:

- **No portal endpoint whose cost grows with the tenant's size.** A customer of a 4,000-connection
  utility must not wait longer than a customer of a 400-connection one. Their own account is the index
  (`NFR-40`).
- **No unbounded list and no page-2-costs-more pagination** on any screen a customer can refresh.
- **No portal request queued behind back-office work.** Its own queue, its own worker, its own
  connection budget (`NFR-39`) — a bill run at 2 a.m. is exactly when somebody pays a bill late.
- **No fixing this with a cached balance.** `BR-CWP-047` says no portal screen caches a balance, and it
  is right: showing a customer a number that was true ten minutes ago, on the screen they use to decide
  what to pay, is worse than being slow. **The budget is met by reading less, not by remembering.**
- **No target met by degrading the back office.** If something has to be slower under load, it is the
  portal, and the office staff must not be able to tell that 500 customers are online.

## 5 · How it is proved, since a target nobody measures is a wish

- Every portal endpoint's walkthrough (`10-scripts/render-checks/cr068-*.mjs`) **records the measured
  time and prints it**, rather than asserting that a target was met. A number a person can read beats a
  claim.
- The load figure is proved at `NFR-38`'s 500 concurrent users with the back office working, not on an
  idle machine, before phase 1 is called done.
- **A failure here is reported, never rounded.** If `p95` for the balance screen is 900 ms, the report
  says 900 ms against a 600 ms target — it does not say "meets target".

### What does the measuring (added 2026-09-04, `CR-071`; no figure above changes)

The three bullets above were an obligation with nothing behind them until this was written. The
instrument is **`10-scripts/render-checks/lib/timings.mjs`**, and a walkthrough calls it in three
lines:

```js
import { attachTimings } from "./lib/timings.mjs";

const timings = attachTimings(context);     // a Playwright Page or BrowserContext
…click the screens…
await timings.report({ targets: [{ id: "RT-3", match: "/portal/me/balance", p95: 600 }] });
```

It catches every `/api/` response the browser made — nothing is hand-listed — groups them by
endpoint (`GET /api/{tenant}/accounts/{id}/bills`, so one account and another are one row and one
budget), and prints count, `p50`, `p95`, `p99` and the slowest, in milliseconds.

**Three things it does that the bullets above ask for and are easy to lose:**

- **It never turns a number into a verdict.** With `targets` it prints the MEASURED figure first and
  the target second — *"p95 MEASURED 894 ms against a 600 ms target · OVER by 294 ms"*. There is
  deliberately no option to fail a run on a latency figure: an instrument that can is the assertion
  the bullets replace. The caller gets the misses back and decides.
- **It says when a `p95` is not a `p95`.** A walkthrough clicks a screen once or twice, and
  `ceil(0.95 × 2) = 2` — the "p95" of two requests IS the slower of the two. Below **n = 20** there is
  no 95th percentile at all and below **n = 100** no 99th, so those cells are marked `!` and named in
  words under the table: *"NOT A p95 — n=2, so this is simply the slowest of 2"*. A comparison against
  such a figure prints *"…so this comparison is not evidence either way"*, in BOTH directions — a
  small sample that lands under a target is not proof the target is met. **To get a `p95` worth
  quoting, ask for the screen twenty-plus times; for a `p99`, a hundred.**
- **It states what it cannot prove.** The figure is wire time as the browser saw it — the server's
  time **plus** both network legs and the SPA's own `/api` pass-through — so it is NOT the
  server-only figure §3 specifies, and it says so on every table it prints. It also excludes the
  browser's own queueing, which is latency a customer feels. **And no run of it proves anything about
  `NFR-38`:** the load figure needs 500 concurrent users with the back office working, which no
  walkthrough does.

**Proved against a running product** — the portal has no screens yet, so
`10-scripts/render-checks/cr071-response-times-instrument.mjs` runs it against the staff app and
prints real numbers (hard-won law 6: a unit test over a fake array proves nothing). The percentile
arithmetic and the small-sample rule are unit-tested in `10-scripts/tests/test_cr071_timings.mjs`.

**`G83` holds the obligation open.** It refuses a `cr068-*` walkthrough that measures nothing, and
refuses any walkthrough that prints *"meets target"* without the figure on the same line. Its three
RED proofs are quoted in its docstring.

## 6 · What is deliberately not specified

- **The customer's total page load.** It depends on their phone and their signal, and a specification
  we cannot measure is one we cannot honour. The server budget above leaves room for roughly a second
  of network and rendering, which is the assumption to revisit if real users are slower than expected.
- **The payment processor's own time** (RT-6b covers what we owe the person meanwhile).
- **Anything about the staff app.** Its targets are its own; this file only forbids the portal from
  spending them.

---

**Traceability.** `NFR-38`–`NFR-41` (B6) · `BR-CWP-022` (throttle) · `BR-CWP-023` (lockout) ·
`BR-CWP-047` (no cached balance) · `NFR-3` (server pagination) · `NFR-30` (index discipline) ·
`OQ-CWP-1510` (CLOSED by this file) · `CR-071`.
