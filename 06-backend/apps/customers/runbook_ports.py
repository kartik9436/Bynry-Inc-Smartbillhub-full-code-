# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 · US-RBS-014 (EP-RBS-04) — CR-075 wave L task L2: the
#           two ports customers owns. NEITHER binds a writer today, and this
#           file is where that is said out loud with its reason.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-RBS-040 (a NOTE is an ENGINE act, not a port — so a
#           note is not the answer to `flag_account`) · BR-CUS-045 (every
#           contact column is PII) · CLAUDE.md hard-won law 1 (a comment
#           claiming a guarantee is not the guarantee)
# Tests:    06-backend/tests/test_us_rbs_010_port_writers.py (asserts both are
#           UNBOUND and that `bound_ports()` reports a true number)
# Impacts:  apps/runbooks/ports/customers_ports.py · DEF-RBS-4331
# ───────────────────────────────────────────────────────
"""Customers owns two ports and can honour neither today. Here is exactly why.

⚠ **THIS FILE EXISTS SO THAT AN ABSENCE HAS AN ADDRESS.** `CR-075` wave A
declared thirteen ports from `12-the-contract.md` §8's coverage table, which
names an owning module for each. Wave L is the first attempt to put a writer
behind them, and **customers has no service and no column for either of its
two**. Writing nothing at all would leave the next lane to rediscover that;
binding something that looks close would be worse, because `bound_ports()`
would report a number that is not true and hard-won law 2 is exactly that shape
one layer down. Both are filed as `DEF-RBS-4331`.

**`suppress_channel` — NOT BOUND. There is no column.** The port is *"a contact
channel marked undeliverable, dated"*. `customers.Contact` carries `email` and
`phone` and **nothing that says a channel stopped working, or when**. The
nearest facts in the product belong to other modules and answer other questions:
`payments.DeliveryReturnEvent` records that one letter came back, and
`notifications`' outbound row records that one message had no address. Neither
is a durable statement about the CONTACT, which is what runbook 22
(*Undeliverable contacts*) needs and what this port names. A column plus its
rule is customers' design decision, not a runbook lane's.

**`flag_account` — NOT BOUND, and the obvious substitute is forbidden.** The
port is *"a flag with a reason"*. `Account` carries exactly one flag —
`cash_only` (`BR-PAY-013`) — with a signed rule of its own that **nothing
auto-clears it** (J12 step 6), which is not a general-purpose flag an automation
may set. And **`AccountNote` is not the answer**: `BR-RBS-040` (CONFIRMED, PO
2026-09-06) rules that a note is an **ENGINE act, not a port**, precisely so a
Check can cause one while holding no writer — *"A LANE MAY NOT 'SIMPLIFY' THIS
INTO A PORT. A fourteenth port would make `BR-RBS-002` false, and nothing in
the suite would notice — the note would still be written and every count would
still agree."* Binding `flag_account` to `create_account_note` would be that
mistake with a different name on it.

⚠ **NEITHER IS A `NotImplementedError("OQ-…")` STUB.** The prime directive's
stub is for a story blocked on an open question the Product Owner must answer.
These are ours: a column and a rule, decided by the module that owns the table
and written down when it is. `G8` reads a `NotImplementedError` as a blocked
story and would report two questions that were never asked.

⚠ **WHAT THIS COSTS, STATED WITH ITS FIGURE RATHER THAN LEFT TO BE INFERRED.**
Runbook 22 (*Undeliverable contacts*) and runbook 19 (*Data hygiene*) are the
two in the catalogue of 34 that need these; **neither is in `CR-075`'s phase 2**
and neither is built. Runbook 8, the collections ladder this wave ships, needs
neither: it holds `queue_notice` and `apply_fee`, both of which are bound. So
nothing in wave L waits on this — it is a debt the catalogue collects later, and
it is recorded now because the moment it was discovered is the cheapest moment
to write it down.
"""

from __future__ import annotations

# ⚠ NO IMPORTS FROM THIS MODULE'S SERVICES, ON PURPOSE. There is nothing to
# call. An import kept "ready for when it lands" is an import that makes this
# file look implemented to anything reading it at a glance, and the whole point
# of this file is that it is honest about being empty.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 (EP-RBS-04; CR-075 wave L task L2)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path — this file writes nothing)
# gates: pytest tests/test_us_rbs_010_port_writers.py (asserts both ports are UNBOUND) · G115
# exceptions: BOTH of this module's ports bind no writer — DEF-RBS-4331, with the reason for each above
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
