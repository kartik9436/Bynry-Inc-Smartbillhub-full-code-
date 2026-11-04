"""One port owned by `integrations`. **Bound from `CR-173-BRC10` (2026-10-07).**

`send_partner_file` — *a file placed in a partner's folder*. The fifteenth port
and the first owned by `integrations`, added as a REVIEWED interface
(`BR-RBS-022`; `12-the-contract.md` §6: *"a new runbook that needs a new port is
adding a reviewed interface, not a custom write"*), with a decision-log row of
2026-10-07 and a row in the human-review ledger.

⚠ **WHY A PORT AND NOT A SEAM.** A seam READS. Placing the New World receipt
file in the City's SFTP folder changes the world outside this product — a file
New World will import and post — so it is a write, and the one way a runbook
writes is a named port. That is also what puts it under the dry/live mechanism:
a runbook that is not on `engine.acts.LIVE_ENABLED_RUNBOOKS`, or that runs dry,
holds this declaration WITHOUT its writer and records *planned* — the file is
built and counted, and nothing is sent.

Maps to ONE service function in the owning module —
`apps.integrations.runbook_ports.send_receipt_file` — which answers
`done: False` instead of raising, for the reason its own docstring gives.
"""

from apps.integrations import runbook_ports as integrations_writers

from apps.runbooks.boundary import PortDeclaration

SEND_PARTNER_FILE = PortDeclaration(
    name="send_partner_file",
    owning_module="integrations",
    what_it_does="A file placed in a partner's folder",
    binds_in="CR-173-BRC10",
    writer=integrations_writers.send_receipt_file,
)

PORTS = (SEND_PARTNER_FILE,)
