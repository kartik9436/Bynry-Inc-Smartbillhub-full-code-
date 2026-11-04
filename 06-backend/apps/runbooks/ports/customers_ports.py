# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-RBS-002 (a Check holds none — and a Check may NOT
#           write a note to an account, OQ-RBS-1734) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 · apps/runbooks/interfaces.py
# ───────────────────────────────────────────────────────
"""Two ports owned by `customers`. **Neither is bound, and now for a REASON.**

⚠ **UNTIL 2026-09-06 *"neither is bound"* MEANT *"wave L has not happened
yet"*. IT NOW MEANS *"customers has nowhere to write this"*, which is a
different sentence and is `DEF-RBS-4331`.** `apps/customers/runbook_ports.py`
carries the full reason for each; in short: there is no undeliverable-channel
column on `Contact`, and `Account` carries only `cash_only`, whose own rule is
that nothing auto-clears it. **And the obvious substitute is forbidden** —
`BR-RBS-040` (CONFIRMED) rules a NOTE an ENGINE act rather than a port,
precisely so a Check can cause one while holding no writer, so binding
`flag_account` to `create_account_note` would make `BR-RBS-002` false and
nothing in the suite would notice.

**Nothing in wave L waits on either.** Runbook 8 holds `queue_notice` and
`apply_fee`; the two runbooks that need these — 22 (*Undeliverable contacts*)
and 19 (*Data hygiene*) — are not in phase 2 and are not built.

`suppress_channel` marks a contact channel undeliverable **and dates it**, which
is the whole value of it: *this address bounced on the 4th* is actionable, while
*this address is bad* is a dead end a clerk cannot argue with.

`flag_account` writes a flag **with a reason**, in words a clerk can read
(`BR-RBS-010`) and with no rule id in them (B14 rule 32).

⚠ **NEITHER OF THESE IS AVAILABLE TO A CHECK, AND THAT IS THE OPEN QUESTION
WORTH KNOWING ABOUT.** *May a Check ever write a note to an account
automatically* is `OQ-RBS-1734` and is OPEN. **Nothing is blocked and nothing is
stubbed**: what ships is that it does not — a clerk adds the explanation with
one button, performed by the customers module. ⚠ **And a later *yes* is not a
setting.** It would be a FOURTEENTH port and a narrowing of `BR-RBS-002`, the
rule that a Check is constructed with no writer at all — which is the whole
safety promise of a Check. That question is more expensive than it reads, and a
lane that answers it by adding a port here has answered it for the Product
Owner.
"""

from apps.runbooks.boundary import PortDeclaration

#: ⚠ NO `writer=` — `DEF-RBS-4331`. There is no column that says a channel
#: stopped working, or when.
SUPPRESS_CHANNEL = PortDeclaration(
    name="suppress_channel",
    owning_module="customers",
    what_it_does="A contact channel marked undeliverable, dated",
)

#: ⚠ NO `writer=` — `DEF-RBS-4331`. And a note is not the answer: `BR-RBS-040`
#: makes that an ENGINE act, never a fourteenth port.
FLAG_ACCOUNT = PortDeclaration(
    name="flag_account",
    owning_module="customers",
    what_it_does="A flag with a reason",
)

PORTS = (SUPPRESS_CHANNEL, FLAG_ACCOUNT)
