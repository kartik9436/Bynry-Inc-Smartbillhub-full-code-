#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-094-BRC01 step 2 wave A — the four ending-service screens.
#          DEF-CUS-5072 · DEF-CUS-5073 · DEF-CUS-5074 · DEF-CUS-5076.
# Rules:   PO 2026-09-12, verbatim: *"you can do actual figures"* — a lane may
#          seed, and must say what it seeded · BR-TEN-043 (the event date is an
#          ARGUMENT, never a clock — every date below is a parameter)
# ───────────────────────────────────────────────────────
"""Put a seeded tenant into the two states the ending-service screens need.

WHY IT EXISTS, AND WHY THE STATES ARE NOT IN `load_sample_data`
──────────────────────────────────────────────────────────────
Step 1 of this CR measured two gaps in the seeded data, and both of them made a
screen unverifiable rather than merely untested:

  1 · **No account on any seeded tenant is eligible for a CLOSE-OUT.** Getting
      one there needs a cut, and a cut refuses on every tenant in this tree
      because the charge code the module looks up (`CC-RECON`) is spelled
      `RECON` in the seed and carries no amount — `OQ-681`, OPEN. So the
      close-out screen's happy path could not be reached at all, and its
      confirm page and its account-afterwards page have never been opened by
      anybody.
  2 · **No account carries a PROTECTION**, so `GET /accounts/{id}/protections`
      answers `pass` on every row and the `fail` branch of step 2 of the
      disconnect wizard — *"This is in force. It stops the cut."*, the sentence
      that exists to stop a medical household being cut — renders on no fixture
      and on no tenant.

Both are seeded HERE rather than in `load_sample_data` on purpose: a demo
tenant where an account is mid-close-out and a household is under a medical
hold is a demo that opens on two alarming states nobody asked for. This is a
lane's instrument, run deliberately.

⚠ **IT WRITES THROUGH THE PRODUCT'S OWN DOORS AND NOT THROUGH THE ORM.**
`record_protection` is the act `BR-CUS-039` defines, it writes `audit_log`
(CLAUDE.md hard rule 7), and it is the thing a clerk would do. A row inserted
behind it would prove the screen renders a row and would prove nothing about
whether the act works.

WHAT IT DID WHEN THIS LANE RAN IT, stated so it can be reproduced or undone
──────────────────────────────────────────────────────────────────────────
Tenant `brazosbend`, 2026-09-12, against account `A-11340` (status
`marked_disconnect`, balance `$8,240.00`, disconnection case `DSC-26-0001`):

  * ONE `account_protections` row — `medical_certificate`, effective
    `2026-09-01`, expiring `2026-12-01`, `set_by=tenant`. `protection_check`
    then answers `medical_certificate: fail` with that expiry, `payment_plan`
    and `weather_moratorium` `pass`, `dispute` `unavailable`, and `all_clear`
    flips to `False`.

### AND FIVE REAL SALES, WRITTEN BY THE PRODUCT AND NOT BY THIS SCRIPT

Proving `DEF-CUS-5075` meant committing sales, because the whole finding was
that the commit could not succeed. Five landed on `brazosbend` on 2026-09-12 —
`TRF-26-0001` … `TRF-26-0005`, all `state=done`, all with one date `2026-05-09`
in both stored columns and `same_day=true` — reassigning `AC-2026-00018`,
`AC-2026-00019`, `AC-2026-00020`, `AC-2026-00021` and `AC-2026-00022` to new
customers. Two were posted at the server with `curl` and three were walked in a
browser through the redesigned wizard at 1280 and 1440.

⚠ **THEY ARE NOT UNDONE, AND THEY CANNOT BE.** `transfer_cancel` refuses a
COMMITTED transfer by design — the accounts have already moved and hard rule 4's
posture applies, so a correction is a new job rather than an edit of this one.
Said plainly here because the next lane to read this tenant will find five
accounts whose customer is *Vasquez, M.* and one *Probe Only*, and the honest
explanation is that a sale is the one thing this lane could not prove without
performing.

⚠ **A NOTE ON `reference_id`, WHICH COST A 500 AND IS FILED AS `DEF-CUS-5089`.**
It is a `UUIDField`. Passing a certificate reference a human would actually
write — `MED-2026-0042` — raises `ValueError: badly formed hexadecimal UUID
string` and the door answers **500**, not a 422 naming the field. The drawn
step 2 has a `Reference` input on it, so the first screen to offer that field
hands a clerk a server error. It is left OUT of the payload below rather than
worked around silently.

  $ python3 manage.py shell < 10-scripts/cr094_lane4_seed_ending_service.py
  (or import and call `seed(tenant="brazosbend", account_no="A-11340", …)`)
"""

from __future__ import annotations

from datetime import date
from typing import Any


def seed(
    *,
    tenant: str = "brazosbend",
    account_no: str = "A-11340",
    protection_kind: str = "medical_certificate",
    effective_from: date = date(2026, 9, 1),
    expires_on: date = date(2026, 12, 1),
) -> dict[str, Any]:
    """Record ONE protection, through the product's own act. Idempotent-ish:
    `record_protection` refuses a duplicate live hold of the same kind, and that
    refusal is reported rather than swallowed — a seeder that hides a refusal is
    a seeder that lies about the state it left behind."""
    from django.db import connection

    from apps.customers import disconnects, selectors
    from apps.identity.models import User
    from apps.tenancy.models import Tenant

    row = Tenant.objects.filter(subdomain=tenant).first()
    if row is None:
        raise SystemExit(f"no tenant {tenant!r}")
    with connection.cursor() as cur:
        cur.execute("SET app.tenant_id = %s", [str(row.id)])

    account = selectors.accounts_queryset().filter(account_no=account_no).first()
    if account is None:
        raise SystemExit(f"no account {account_no!r} on {tenant!r}")
    actor = User.objects.filter(tenant_id=row.id, role="system_admin").first()
    if actor is None:
        raise SystemExit(f"no system admin on {tenant!r} to act as")

    written = disconnects.record_protection(
        actor,
        account.id,
        kind=protection_kind,
        effective_from=effective_from,
        expires_on=expires_on,
        set_by="tenant",
        reference_id=None,  # DEF-CUS-5089 — a UUIDField, and a certificate
        # reference is not a UUID. Left absent rather than faked.
        note="seeded by cr094_lane4_seed_ending_service.py",
    )
    check = disconnects.protection_check(account.id, as_of=date.today())
    return {
        "tenant": tenant,
        "account_no": account_no,
        "protection": written,
        "outcomes": {c["check"]: c["outcome"] for c in check["checks"]},
        "all_clear": check["all_clear"],
    }


if __name__ == "__main__":
    print(seed())
