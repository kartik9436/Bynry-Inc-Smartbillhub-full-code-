"""Put the beta back after `po20260920_transfer_walkthrough.mjs` sold a property.

    cd 06-backend && set -a && . ./.env && set +a \
      && .venv/bin/python ../10-scripts/po20260920_transfer_walk_purge.py

⚠ **IT IS THE ONLY WRITE-BACK THE WALK HAS**, because a sale has no undo: it
rewrites `customer_accounts`, **overwrites the account's CONTACT row in place**,
writes a permanent `transfers` row and writes `audit_log`.

⚠⚠ **THE CONTACT IS THE PART A FIRST DRAFT MISSES, AND IT IS THE DESTRUCTIVE
ONE.** `commit_transfer` does not ADD a contact for the buyer — it UPDATEs the
one the account already had, which is the SELLER's. Measured on 2026-09-20:
contact `01a0aff9-…a72c` went from `Luca Lindqvist · lindqvist11@example.invalid
· +1 (402) 555-1011` to the buyer's name, email, phone and date of birth, same
row id. A purge that restores only the `customer_accounts` link leaves the demo
seller's own contact details destroyed, and **every count still matches**, which
is why this file snapshots them and writes them back.

⚠⚠ **IT NEVER DELETES A CUSTOMER IT DID NOT CREATE.** `transfer.customer` is
the **SELLER** on an OPEN transfer and only becomes the buyer once
`reassign_account` runs — `DEF-CUS-5945` is the row where reading it as *the
buyer* deleted a real demo customer's account links. The licence to delete is
the MARKER in `display_name` and nothing else, checked at the delete site.

⚠ **RAW SQL THROUGHOUT, DELIBERATELY.** Several demo rows on this beta were
written under the retired field-encryption key `insecure-dev`, so the ORM's
`from_db_value` raises `FieldDecryptionError` on an ordinary `.filter()` and a
purge written against the ORM dies half-way through — which is exactly how it
failed on its first run, leaving a sale live on a shared beta. A cursor reads
the stored bytes and does not decrypt.

The seller's id is read out of `audit_log`'s `transfer.reassigned` row, which is
where the ruling put it (hard rule 4 — the value a correction replaces lives
only there, and `OQ-1340` is open on whether it is pruned).

Reads `po20260920_transfer_walk_planted.json`, written by the walk. Prints the
same counts the walk prints, so *"the beta is as it was found"* is measured.
"""
import json
import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

MARKER = "WALKTRF-20260920"
STATE = pathlib.Path(__file__).with_name("po20260920_transfer_walk_planted.json")
TENANT = os.environ.get("TW_TENANT", "brazosbend")
TABLES = (
    "accounts", "transfers", "customer_accounts", "customers", "payments",
    "journal_lines", "invoices", "outbound_messages", "wizard_parks",
)


def counts(cur, label):
    out = []
    for table in TABLES:
        cur.execute("select count(*) from " + table)  # noqa: S608 — a fixed list
        out.append(f"{table} {cur.fetchone()[0]}")
    print(f"  {label}: " + " · ".join(out))


def main() -> int:
    with connection.cursor() as cur:
        cur.execute("select id from tenants where subdomain = %s", [TENANT])
        row = cur.fetchone()
        if row is None:
            print(f"no `{TENANT}` tenant on this database — nothing to remove")
            return 0
        tenant_id = str(row[0])
        # RLS FORCE is on: with `app.tenant_id` unset every count comes back
        # zero and this would be a check that cannot fail.
        cur.execute("select set_config('app.tenant_id', %s, false)", [tenant_id])
        counts(cur, "before the purge")

        if not STATE.exists():
            print(f"no {STATE.name} — nothing is recorded as planted, so nothing is removed")
            return 0
        planted = json.loads(STATE.read_text(encoding="utf-8"))

        for one in planted:
            transfer_id = one.get("transfer_id")
            cur.execute("select id, from_account_id, customer_id from transfers where id = %s", [transfer_id])
            found = cur.fetchone()
            if found is None:
                print(f"  ! transfer {transfer_id} is already gone")
            else:
                account_id, buyer_id = str(found[1]), str(found[2])
                # 1 · the seller's link, out of the audit row that holds it
                cur.execute(
                    "select after from audit_log where action = 'transfer.reassigned' and entity_id = %s"
                    " order by created_at desc limit 1", [transfer_id])
                audit = cur.fetchone()
                sellers = []
                if audit is not None:
                    block = (json.loads(audit[0]) if isinstance(audit[0], str) else audit[0]) or {}
                    sellers = ((block.get("reassignment") or {}).get("from_customer_ids")) or []
                for seller_id in sellers:
                    cur.execute(
                        "select count(*) from customer_accounts where account_id = %s and customer_id = %s",
                        [account_id, seller_id])
                    if cur.fetchone()[0] == 0:
                        cur.execute(
                            "insert into customer_accounts (id, tenant_id, account_id, customer_id, created_at)"
                            " values (%s, %s, %s, %s, now())",
                            [str(uuid.uuid4()), tenant_id, account_id, seller_id])
                        print(f"  restored seller {seller_id} on {one.get('account_no')}")
                # 2 · the buyer's link
                cur.execute("delete from customer_accounts where account_id = %s and customer_id = %s",
                            [account_id, buyer_id])
                print(f"  removed the buyer's link ({cur.rowcount} row)")
                # 3 · the contact row the commit OVERWROTE in place
                snap = one.get("contact")
                if snap is not None:
                    cur.execute(
                        "update contacts set full_name = %s, email = %s, phone = %s, dob = %s where id = %s",
                        [snap.get("full_name"), snap.get("email"), snap.get("phone"),
                         snap.get("dob") or None, snap["id"]])
                    print(f"  restored contact {snap['id']} to {snap.get('full_name')!r} ({cur.rowcount} row)")
                else:
                    print("  ! no contact snapshot recorded — the seller's contact row is NOT restored")
                # 4 · the transfer, then the buyer this walk minted
                cur.execute("delete from transfers where id = %s", [transfer_id])
                print(f"  removed transfer {transfer_id}")
                cur.execute("select customer_no, display_name from customers where id = %s", [buyer_id])
                who = cur.fetchone()
                if who is not None and MARKER in (who[1] or ""):
                    cur.execute("delete from portal_credential where customer_id = %s", [buyer_id])
                    cur.execute("delete from customer_accounts where customer_id = %s", [buyer_id])
                    cur.execute("delete from customers where id = %s", [buyer_id])
                    print(f"  removed the walk's buyer {who[0]}")
                elif who is not None:
                    print(f"  LEFT {who[0]} alone — not this walk's row")

        # Anything the walk minted that no transfer points at.
        cur.execute("select id, customer_no from customers where display_name like %s", [f"%{MARKER}%"])
        for stray_id, stray_no in list(cur.fetchall()):
            cur.execute("select count(*) from transfers where customer_id = %s", [str(stray_id)])
            if cur.fetchone()[0] == 0:
                cur.execute("delete from portal_credential where customer_id = %s", [str(stray_id)])
                cur.execute("delete from customer_accounts where customer_id = %s", [str(stray_id)])
                cur.execute("delete from customers where id = %s", [str(stray_id)])
                print(f"  removed stray walk customer {stray_no}")

        # The walk's parked drafts. `Park` writes a `wizard_parks` row (`Save &
        # exit` writes nothing at all), so a walk that exercised parking leaves
        # one behind. Matched on the marker the walk types into the buyer's name.
        cur.execute("delete from wizard_parks where flow = 'transfer' and values::text like %s", [f"%{MARKER}%"])
        if cur.rowcount:
            print(f"  removed {cur.rowcount} parked draft(s)")

        counts(cur, "after the purge")
    STATE.unlink(missing_ok=True)
    print(f"removed {STATE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
