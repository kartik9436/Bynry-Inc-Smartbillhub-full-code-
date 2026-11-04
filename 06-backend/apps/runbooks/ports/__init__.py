# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4: the THIRTEEN ports
#           as declarations binding NO writer.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-022 (a
#           runbook reaches another module or a partner ONLY through a named
#           port; work items and audit rows are the ENGINE's) · BR-RBS-018 (a
#           money-bearing action carries a second approval)
# Tests:    06-backend/tests/test_us_rbs_041_module.py (thirteen, none bound,
#           and raise_work_item is NOT among them)
# Impacts:  apps/runbooks/interfaces.py (the registry) ·
#           10-scripts/gates/g115_runbooks_import_census.py
# ───────────────────────────────────────────────────────
"""The thirteen write ports — declarations, and **not one of them is bound**.

⚠ **THIS `__init__.py` IMPORTS NOTHING FROM ANOTHER MODULE, AND WILL NOT.** A
package `__init__` that pulled the port modules in would launder whatever they
import into `apps.runbooks.ports`, so a caller anywhere could reach another
module's service through this name without any file appearing to import it.
`G115` refuses a foreign import in any file under `ports/` that is not itself a
`*_ports.py`, and this file stays clear of them so the rule has nothing to argue
with. The registry that does import them is `apps/runbooks/interfaces.py`.

WHY FIVE FILES AND NOT THIRTEEN
--------------------------------
One file per **owning module**, mirroring the read seams: `notifications` (2),
`payments` (5), `billing` (1), `metering` (3), `customers` (2) — thirteen
declarations in five files. That is the shape wave L wants, because a port maps
to one service function in the owning module and binding is done one module at a
time; thirteen files would scatter one act across five directories' worth of
imports.

THE THIRTEEN, AND WHAT EACH DOES
---------------------------------
| Port | Owner | What it does |
|---|---|---|
| `queue_notice` | notifications | Writes a queue row; the dispatcher sends |
| `queue_receipt` | notifications | A receipt document to the queue |
| `apply_payment` | payments | Applies a landed payment by the allocation order |
| `post_credit` | payments | A credit to an open account |
| `raise_refund` | payments | A refund awaiting its own approval |
| `record_match` | payments | A bank line matched to a deposit batch |
| `schedule_retry` | payments | A retry of a failed debit |
| `apply_fee` | billing | A fee by rule, behind the second approval |
| `write_read` | metering | A validated meter-day as a read, source stamped |
| `apply_premise_change` | metering | One field on one premise, before-and-after kept |
| `flag_meter` | metering | *"Told about a leak on"* a date |
| `suppress_channel` | customers | A contact channel marked undeliverable, dated |
| `flag_account` | customers | A flag with a reason |

⚠ **`raise_work_item` IS NOT ON THAT LIST AND MUST NOT BE ADDED.** The source
specification's architecture section says a runbook writes through *"four named
calls: queue a notice, flag an account, raise a work item, apply a fee"*, and
some form of that sentence appears in **seven places**; the contract, one page
later, lists these thirteen and states in its own heading that **raising work
items and writing audit rows are ENGINE acts**. Thirteen is right — it is the
later and finer statement, it names an owning module for each entry, and it is
the list the twenty-one result wireframes need, since the four-port sentence
cannot draw `record_match`, `write_read`, `apply_premise_change`,
`suppress_channel`, `post_credit`, `raise_refund` or `schedule_retry`.

**And the membership matters more than the count.** A Check is constructed with
NO ports and must still populate the work list; if raising a work item were a
port, every Check would need a writer and `BR-RBS-002` — the whole safety
promise of a Check — would be gone. A lane grepping for *port* finds the wrong
answer seven times out of eight, which is why this is written out here rather
than left to be re-derived.

⚠ **NOTHING IS BOUND, AND THAT IS PHASE 1'S PRODUCT RATHER THAN ITS GAP.** Phase
1's launch sentence is *"a clerk presses one button and sees exactly what is
stopping billing… nothing can be written: no writer is bound."* Wave L binds
them with sending switched **off**, so the risky code runs against real accounts
in production for a full cycle unable to do anything; wave N turns the first one
on. A port called before then raises `PortNotBound` naming the wave — the
shipped behaviour, not a stub awaiting an open question.
"""
