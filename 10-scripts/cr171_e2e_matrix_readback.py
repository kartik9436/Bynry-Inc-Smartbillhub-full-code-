#!/usr/bin/env python3
"""CR-171-BRC10 P4.02 (lane MVI-E2E-SEED) — the DATABASE half of the move-in matrix.

`cr171_e2e_matrix_run.mjs` submits a case through the browser, then calls this
with the case and the MVI- number the screen printed. It reads the database
back and prints ONE JSON object:

    {"checks": [{"module", "name", "pass", "detail"}],   # one per fact
     "facts":  {...}}                                     # what the screen walk looks for

It WRITES NOTHING. The one service call that could (the first-bill preview) runs
inside a transaction that is rolled back.

    cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
        python ../10-scripts/cr171_e2e_matrix_readback.py --case M1 --move MVI-26-0009

WHAT EACH EXPECTATION FOLLOWS (never what the product happened to print):
  * the fees: the plan's deposit rule for the account type + the plan's CONN,
    as `cr171_e2e_matrix_world.py` seeded them — and NONE TAXED at move-in
    (`OQ-BIL-12788` (a), decision log 2026-10-05);
  * a person new to the utility gets a new customer; a match only where our
    Q5 rule matches (decision log 2026-10-05 (1));
  * unit and meter status are DERIVED, never written: the unit has no status
    column to write, and no asset carries an audit row of a status change made
    by the move-in;
  * every money action writes `audit_log` (hard rule 7); every journal entry
    for the account balances (hard rule 5) — and the number of payments not yet
    journaled is PRINTED beside it, because a check over zero entries proves
    nothing (hard-won law 7, the fifth shape);
  * an opening read carries its meter's OWN unit (water kgal, electric kWh,
    gas ccf) — the known trap is a helper that saves kWh when told nothing;
  * labour comes from the technician's arrived/finished times: a visit nobody
    has worked carries no minutes and no cost line.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


#: What each case's clerk typed (the runner's `CASES`) and what follows from it.
#: M2–M7 are the R4 lanes' to add, in this shape.
EXPECT = {
    "M1": {
        "opened_at": "2026-10-10",
        "customer": {"name": "Avery Collins", "kind": "person", "new": True},
        "account_type": "residential", "subtype": "single_family",
        "services": ["electric", "sewer", "trash", "water"],
        "opening_reads": {"E-M1": ("4300", "kWh"), "W-M1": ("315.0", "kgal")},
        # Residential deposit rule on SCW-RES + the plan's CONN (the world's seed).
        "fees": [("deposit", "DEPOSIT", "150.0000"), ("fee", "CONN", "25.0000")],
        "payment": {"method": "check", "confirmation": "2041", "total": "175.00"},
        "work_orders": [{"template": "Opening read", "asset": "W-M1", "window_local": ("08:00", "12:00")}],
        # A later reading for the first-bill preview (typed into the preview, never committed).
        "preview_reads": {"E-M1": "4800", "W-M1": "321.0"},
        # DEF-BIL-9751 FIXED (PO 2026-10-06 (a)): the check is still processing and the deposit counts as paid.
    },
    # ── M2 (lane MVI-E2E-1, R4) ─────────────────────────────────────────
    "M2": {
        "opened_at": "2026-10-10",
        # Found by her SSN (an identifier on file, PO 2026-10-05 (1)) and LINKED: no new
        # customer; her two accounts on file (the world's seed) plus this one.
        "customer": {"name": "Rosa Delgado", "kind": "person", "new": False,
                     "accounts_on_file": ["AC-2026-00054", "AC-2026-00055"]},
        "account_type": "residential", "subtype": "multi_family",
        "services": ["sewer", "water"],
        # The meter and its irrigation sub-meter are read; the backflow device is not a read device.
        "opening_reads": {"W-M2": ("121.5", "kgal"), "SW-M2": ("42.0", "kgal")},
        "devices": {"BF-M2": "W-M2"},  # device → the meter it stands under (BR-AST-003)
        "co_owners": [{"kind": "co_owner", "full_name": "Luis Delgado", "relationship": "spouse",
                       "date_of_birth": "1977-09-03", "responsible_for_bills": True}],
        "fees": [("deposit", "DEPOSIT", "150.0000"), ("fee", "CONN", "25.0000")],
        # Add to bill records NO money (move_fees: "Add to bill records no money").
        "payment": None,
        "work_orders": [],
        "preview_reads": {"W-M2": "126.0", "SW-M2": "44.0"},
        # DEF-MET-9773 (a sub-meter's size unresolving the connection) was this case's one expected
        # FAIL; fixed in 2.549.9, so nothing is labelled. The key stays: P25 spreads it.
        "known_defects": {},
    },
    # ── M3 (lane MVI-E2E-1, R4) ─────────────────────────────────────────
    "M3": {
        "opened_at": "2026-10-10",
        "customer": {"name": "Harold Whitfield", "kind": "person", "new": True},
        "account_type": "residential", "subtype": "senior_low_income",
        "services": ["electric", "gas"],
        "opening_reads": {"E-M3": ("8905", "kWh"), "G-M3": ("1541", "ccf")},
        "fees": [("deposit", "DEPOSIT", "150.0000"), ("fee", "CONN", "25.0000")],
        # $100.00 cash < the $150.00 deposit → ONE prepay payment; the deposit is never taken
        # partly (BR-CUS-025 / BR-PAY-012) and stays on the first bill.
        "payment": {"method": "cash", "confirmation": None, "total": "100.00",
                    "purposes": [("prepay", "100.00")], "part": True},
        # The clerk's claim is ENROLLED at once (PO 2026-10-05 (b)); its evidence is an account document.
        "discounts": ["CAP"],
        # The evidence the clerk uploaded as *Assistance evidence* is filed in the account's KYC
        # folder — every paper a move-in brings is (move_in_documents.FILED_FOLDER, BR-CUS-036).
        "documents": [("kyc", "cap-award-letter.pdf")],
        "work_orders": [],
        "preview_reads": {"E-M3": "9400", "G-M3": "1580"},
    },
}

#: M4 and M5 — lane MVI-E2E-2 (R4). Their own block, merged below, so the M2/M3 lane's
#: hunks and these never touch the same lines. Built on E2E-1's hooks (accounts_on_file,
#: co_owners, documents, known_defects, _case_extras).
EXPECT_M4_M5 = {
    # ── M4 · Commercial · Small commercial · a company found by its Tax ID · card
    "M4": {
        "opened_at": "2026-10-10",
        # Found = identifier on file (PO 2026-10-05 (1)): Northgate's Tax ID 74-3051190 is on
        # file, so the clerk LINKS it — no second customer; its 6 Aspen Row account (the world's
        # seed) plus this one.
        "customer": {"name": "Northgate Provisions LLC", "kind": "company", "new": False,
                     "accounts_on_file": ["AC-2026-00056"]},
        "account_type": "commercial", "subtype": "small_commercial",
        "services": ["electric", "sewer", "storm_water", "trash", "water"],
        "opening_reads": {"E-M4": ("15100", "kWh"), "W-M4": ("642.0", "kgal")},
        # Commercial deposit rule on SCW-COM $300.00 + the plan's CONN $25.00 (the world's seed).
        "fees": [("deposit", "DEPOSIT", "300.0000"), ("fee", "CONN", "25.0000")],
        "payment": {"method": "card", "confirmation": "4417", "total": "325.00"},
        # The company's owners as typed on step 2 (stored as kind 'officer').
        "co_owners": [{"kind": "officer", "full_name": "Hal Brennan", "title": "Managing member",
                       "ownership_pct": "60.000000", "signs_for_company": True},
                      {"kind": "officer", "full_name": "Priya Nandakumar", "title": "Member",
                       "ownership_pct": "40.000000", "signs_for_company": False}],
        "work_orders": [],
        "preview_reads": {"E-M4": "15900", "W-M4": "655.0"},
        # No exemption: every SCW-COM tax reaching a commercial account stays on (the seed:
        # State 6.25% commercial+industrial, County 2.00% every class, City 2.00% commercial+
        # government; the world gives the City tax no place scope, so it reaches 900 Commerce Row).
        "taxes_present": ["TX State Utility Tax", "Local · Bexar County", "City of Cedar Ford utility tax"],
        # A card is recorded with no cleared date exactly as a check is, so the deposit is
        # PROCESSING — and counts as paid (DEF-BIL-9751 FIXED, PO 2026-10-06 (a)), tender-independent.
    },
    # ── M5 · Commercial · Institutional & non-profit · a church, tax exempt with certificate
    "M5": {
        "opened_at": "2026-10-10",
        "customer": {"name": "Grace Fellowship of Cedar Ford", "kind": "company", "new": True},
        "account_type": "commercial", "subtype": "institutional_non_profit",
        "services": ["fire", "sewer", "water"],
        "opening_reads": {"W-M5": ("89.5", "kgal")},
        "fees": [("deposit", "DEPOSIT", "300.0000"), ("fee", "CONN", "25.0000")],
        "payment": {"method": "check", "confirmation": "1187", "total": "325.00"},
        "work_orders": [],
        "preview_reads": {"W-M5": "95.0"},
        # Billing clerks record exemptions themselves (PO 2026-10-05 (2)): the City tax's
        # RELIGIOUS category, its number and dates; the certificate PDF filed on the account.
        # An exemption removes ONLY the tax named on its certificate (ruling (A), 2.546.5): the
        # account's blanket tax_exempt stays false and every OTHER tax still applies.
        "exemption": {"category": "RELIGIOUS", "tax": "City of Cedar Ford utility tax",
                      "certificate_ref": "CF-REL-2026-0412", "issued_on": "2026-01-15",
                      "expires_on": "2028-12-31"},
        # The certificate PDF's file name, filed in the account's KYC folder (move_in_preferences:
        # CERTIFICATE_DOC_TYPE). Its stored key is prefixed with the account number, so it is
        # matched by its END, not through the customer-step `documents` hook's exact leaf.
        "certificate_file": "religious-exemption-certificate.pdf",
        # Fire is trash's arithmetic, ONE line per service (CR-063; decision log "ONE-TIME BILL:
        # SIX ANSWERS" (5), built 2.411.3): one 6" line $60.00 + two 2" lines 2 × $12.00 = $84.00
        # on ONE fire line (fire's six prices are the signup's seed).
        "fire": {"lines": 1, "amount": "84.00"},
        # The certificate names the City's tax only, so ruling (A) leaves the State and County.
        "taxes_absent": ["City of Cedar Ford utility tax"],
        "taxes_present": ["TX State Utility Tax", "Local · Bexar County"],
    },
}
EXPECT.update(EXPECT_M4_M5)

#: M6, M7 and the three after-Complete cases P4.24–P4.26 — lane MVI-E2E-3 (R4). Their own
#: block, merged below, so no other lane's hunks share these lines. Built on E2E-1's and
#: E2E-2's hooks (devices, co_owners, exemption, taxes_present/absent, known_defects).
EXPECT_M6_M7 = {
    # ── M6 · Industrial · Light industrial · a new company · four services, solar behind the meter
    "M6": {
        "opened_at": "2026-10-10",
        "customer": {"name": "Foundry Works Fabrication Inc.", "kind": "company", "new": True},
        "account_type": "industrial", "subtype": "light_industrial",
        "services": ["electric", "gas", "solar", "water"],
        # Three meters are read; the solar inverter PV-M6 stands behind E-M6 and is not a read
        # device (asset category, `assets.selectors.READ_DEVICE_CATEGORIES`).
        "opening_reads": {"E-M6": ("52400", "kWh"), "G-M6": ("7725", "ccf"), "W-M6": ("205.5", "kgal")},
        "devices": {"PV-M6": "E-M6"},
        # Industrial deposit rule on SCW-IND $500.00 + the plan's CONN $25.00 (the world's seed).
        "fees": [("deposit", "DEPOSIT", "500.0000"), ("fee", "CONN", "25.0000")],
        # $525.00 in CASH. The wizard records cash as PROCESSING too (as a check or a card), and a
        # move-in deposit counts as paid whatever the tender (DEF-BIL-9751 FIXED, PO 2026-10-06 (a)).
        "payment": {"method": "cash", "confirmation": None, "total": "525.00"},
        # Two field visits (the PO's matrix): an opening read on the electric meter in the
        # morning and the gas turn-on (Reconnect visit) in the afternoon.
        "work_orders": [{"template": "Opening read", "asset": "E-M6", "window_local": ("08:00", "12:00")},
                        {"template": "Reconnect visit", "asset": "G-M6", "window_local": ("12:00", "17:00")}],
        "preview_reads": {"E-M6": "53900", "G-M6": "7810", "W-M6": "214.0"},
        # The seed: State 6.25% commercial + industrial, County 2.00% every class, City 2.00%
        # commercial + government — so an industrial account carries State and County, not City.
        "taxes_present": ["TX State Utility Tax", "Local · Bexar County"],
        "taxes_absent": ["City of Cedar Ford utility tax"],
        "solar": True,
        # M6 starts water WITHOUT sewer, the first matrix case to: the first bill must carry no sewer.
        "services_absent_from_bill": ["sewer"],
        # DEF-BIL-9793's label left with its fix (2.549.15): sewer follows water only at an
        # address that offers sewer, and 5 Foundry Way does not.
        "known_defects": {"one work order per field-visit row": "DEF-WRK-9784"},
    },
    # ── M7 · Government · Schools · a new public body · government exemption · PO on bills
    "M7": {
        "opened_at": "2026-10-10",
        "customer": {"name": "Cedar Ford Independent School District", "kind": "company", "new": True},
        # Government · Schools, the PO's M7. `government` is seeded legacy (BR-CUS-094); the world
        # offers it again the way a utility does on Settings (OQ-CUS-12407 a, DEF-CUS-9808), and the
        # seeded Schools sub-type hangs under it (lane DEF-9786-9788; was Municipal, no sub-type).
        "account_type": "government", "subtype": "schools",
        "services": ["sewer", "trash", "water"],
        "opening_reads": {"W-M7": ("1462.0", "kgal")},
        # No deposit rule for Government (the world's seed), so the one fee is CONN $25.00.
        "fees": [("fee", "CONN", "25.0000")],
        "payment": None,  # Add to bill: a school district is invoiced, it does not pay at a counter
        "work_orders": [],
        "preview_reads": {"W-M7": "1480.0"},
        "po_number": "PO-2026-118",
        "exemption": {"category": "GOVERNMENT", "tax": "City of Cedar Ford utility tax",
                      "certificate_ref": "CF-GOV-2026-0077", "issued_on": "2026-07-01",
                      "expires_on": "2027-06-30"},
        "certificate_file": "government-exemption-letter.pdf",
        # Three 96-gallon carts, trash's arithmetic (count × the size's price, M4 read $15.00 each).
        "trash": {"count": 3, "amount": "45.00"},
        # The certificate removes the City tax; the State tax never reaches municipal (class);
        # the County tax reaches every class and STAYS (ruling (A): only the named tax goes).
        "taxes_absent": ["City of Cedar Ford utility tax", "TX State Utility Tax"],
        "taxes_present": ["Local · Bexar County"],
    },
}
# P4.24 / P4.25: a COPY of M1 / M2 (the same input on a freshly restored world), then the act.
EXPECT_M6_M7["P24"] = {**EXPECT["M1"], "world_case": "M1", "after": "cancel",
                       # W-M1 is left unread so the move-in is Scheduled / Waiting on a read — the status
                       # the PO's actions table offers Cancel on (a Completed move-in offers none).
                       "opening_reads": {"E-M1": ("4300", "kWh")},
                       # J6's worked figure on M1's money: $150.00 deposit + $25.00 = ONE $175.00 refund.
                       # DEF-CUS-9789 FIXED (2.549.16): the check is still PROCESSING, so both payments are
                       # CALLED OFF (cancelled + a −amount reversing row each), nothing is refunded or
                       # released. Cleared money stays ONE refund (the PO's signed $175.00).
                       "cancel": {"refund": None, "deposit_released": None, "method": "check",
                                  "called_off": ["150.0000", "25.0000"]},
                       "known_defects": {**EXPECT["M1"].get("known_defects", {})}}
EXPECT_M6_M7["P25"] = {**EXPECT["M2"], "world_case": "M2", "after": "date",
                       "opening_reads": {"W-M2": ("121.5", "kgal")},  # SW-M2 left unread (Waiting on a read)
                       "work_orders": [{"template": "Opening read", "asset": "W-M2", "window_local": ("08:00", "12:00")}],
                       "change_date": {"to": "2026-10-15"}}
EXPECT_M6_M7["P25B"] = {**EXPECT["M1"], "world_case": "M1", "after": "date",
                        "opening_reads": {"E-M1": ("4300", "kWh")},  # W-M1 left for its booked visit
                        "change_date": {"to": "2026-10-15"}}
# P25's DEF-MET-9773 labels left with its fix (2.549.9): M2's first bill prices again.
EXPECT.update(EXPECT_M6_M7)

SERVICE_NAMES = {"electric": "Electric", "water": "Water", "gas": "Gas", "sewer": "Sewer", "trash": "Trash",
                 "storm_water": "Storm water", "solar": "Solar", "fire": "Fire"}


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, module, name, passed, detail=""):
        self.rows.append({"module": module, "name": name, "pass": bool(passed), "detail": str(detail)})

    def eq(self, module, name, actual, expected):
        self.add(module, name, actual == expected, f"expected {expected!r}, read {actual!r}")


def money(value) -> str:
    return f"{Decimal(value):.2f}"


def sql(query, params=()):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


def readback(world, case: str, move_no: str) -> dict:
    from zoneinfo import ZoneInfo

    from apps.tenancy.models import Tenant
    from core import tenancy as core_tenancy

    expect = EXPECT[case]
    seeded = world.CASES[expect.get("world_case", case)]  # P24/P25 are copies of M1/M2 (lane MVI-E2E-3)
    tenant = Tenant.objects.get(subdomain=world.SUBDOMAIN)
    c = Checks()
    facts: dict = {}
    with core_tenancy.tenant_context(tenant.id):
        T = str(tenant.id)
        move = sql("select id, account_id, kind, effective_on, reads_committed, performed_at from move_records "
                   "where tenant_id=%s and move_no=%s", (T, move_no))
        c.add("Accounts", f"one move record {move_no} exists", len(move) == 1, f"{len(move)} found")
        if not move:
            return {"checks": c.rows, "facts": facts}
        move = move[0]
        c.eq("Accounts", "the move record is a move-in", move["kind"], "move_in")
        c.eq("Accounts", "the move-in is dated as typed", str(move["effective_on"]), expect["opened_at"])
        A = str(move["account_id"])

        # ── Accounts ────────────────────────────────────────────────────
        acct = sql("""select a.account_no, s.code status, a.opened_at, a.closed_at, at.code type, at.name type_name,
                             st.code subtype, a.unit_id, u.unit_no
                        from accounts a left join account_statuses s on s.id=a.status_id
                        left join account_types at on at.id=a.account_type_id
                        left join account_subtypes st on st.id=a.account_subtype_id
                        left join units u on u.id=a.unit_id where a.id=%s""", (A,))[0]
        c.eq("Accounts", "the account is active", acct["status"], "active")
        c.eq("Accounts", "the account opens on the move-in date", str(acct["opened_at"]), expect["opened_at"])
        c.eq("Accounts", "the account type is the one the clerk picked", acct["type"], expect["account_type"])
        c.eq("Accounts", "the sub-type is the one the clerk picked", acct["subtype"], expect["subtype"])
        c.eq("Accounts", "the account is on the case's unit", acct["unit_no"], _unit_no(T, seeded))
        cust = sql("""select cu.customer_no, cu.display_name, cu.kind,
                             (select count(*) from customer_accounts x where x.customer_id=cu.id) accounts
                        from customer_accounts ca join customers cu on cu.id=ca.customer_id
                       where ca.account_id=%s""", (A,))
        c.add("Accounts", "exactly one customer holds the account", len(cust) == 1, f"{len(cust)} found")
        if cust:
            cu = cust[0]
            c.eq("Accounts", "the customer's name is as typed", cu["display_name"], expect["customer"]["name"])
            c.eq("Accounts", "the customer is a person/company as picked", cu["kind"], expect["customer"]["kind"])
            if expect["customer"].get("new"):
                c.eq("Accounts", "a NEW customer holds this one account only (nothing was linked)",
                     cu["accounts"], 1)
            on_file = expect["customer"].get("accounts_on_file")
            if on_file:
                held = sorted(r["account_no"] for r in sql(
                    """select a.account_no from customer_accounts ca join accounts a on a.id=ca.account_id
                        join customers cu on cu.id=ca.customer_id where cu.customer_no=%s""", (cu["customer_no"],)))
                c.eq("Accounts", "LINKED: the returning customer holds her accounts on file AND this one",
                     held, sorted(on_file + [acct["account_no"]]))
                same_name = sql("select count(*) n from customers where tenant_id=%s and display_name=%s",
                                (T, expect["customer"]["name"]))[0]["n"]
                c.eq("Accounts", "LINKED: no second customer of that name was written", same_name, 1)
        agreements = sql("""select s.code, sa.started_on from service_agreements sa
                              join service_points sp on sp.id=sa.service_point_id
                              join services s on s.id=sp.service_id where sa.account_id=%s""", (A,))
        c.eq("Accounts", "one agreement per started service", sorted(r["code"] for r in agreements),
             sorted(expect["services"]))
        c.add("Accounts", "every agreement starts on the move-in date",
              agreements and all(str(r["started_on"]) == expect["opened_at"] for r in agreements),
              [str(r["started_on"]) for r in agreements])

        # ── Units (occupancy derived, never written) ────────────────────
        cols = {r["column_name"] for r in sql(
            "select column_name from information_schema.columns where table_name='units'")}
        stored = sorted(cols & {"status", "occupancy", "status_id", "occupied"})
        c.add("Units", "the unit stores no status or occupancy (it is derived)", not stored, stored)
        open_accounts = sql("select count(*) n from accounts where unit_id=%s and closed_at is null "
                            "and tenant_id=%s", (str(acct["unit_id"]), T))[0]["n"]
        c.eq("Units", "the unit now has exactly one open account (reads Occupied)", open_accounts, 1)

        # ── Assets: opening reads in each meter's own unit; status untouched ─
        reads = sql("""select a.id asset_id, a.asset_no, r.current_value, r.unit, r.read_at, r.lifecycle
                         from meter_reads r join assets a on a.id=r.asset_id
                        where r.account_id=%s order by a.asset_no""", (A,))
        by_meter = {r["asset_no"]: r for r in reads}
        c.eq("Assets", "an opening read for each meter the clerk read, and none other",
             sorted(by_meter), sorted(expect["opening_reads"]))
        opening = []
        for meter, (value, unit) in expect["opening_reads"].items():
            r = by_meter.get(meter)
            if r is None:
                continue
            c.eq("Assets", f"{meter}'s opening read is {value} as typed", Decimal(r["current_value"]), Decimal(value))
            c.eq("Assets", f"{meter}'s opening read is in {unit}, the meter's own unit", r["unit"], unit)
            c.eq("Assets", f"{meter}'s opening read is dated the move-in date", str(r["read_at"].date()),
                 expect["opened_at"])
            c.eq("Assets", f"{meter}'s opening read is committed", r["lifecycle"], "committed")
            opening.append({"asset_no": meter, "asset_id": str(r["asset_id"]), "unit": unit,
                            "value_display": _display(value),
                            "value_raw": f"{Decimal(value):f}".rstrip("0").rstrip(".") if "." in value else value})
        seeded_assets = [row[0] for row in seeded["equipment"]]
        status_writes = sql("""select al.action, a.asset_no from audit_log al
                                 join assets a on a.id::text = al.entity_id::text
                                where al.tenant_id=%s and al.entity_type='asset' and a.asset_no = any(%s)
                                  and al.created_at >= %s and al.action ilike '%%status%%'""",
                            (T, seeded_assets, move["performed_at"]))
        asset_rows = sql("""select count(*) n from audit_log al join assets a on a.id::text = al.entity_id::text
                             where al.tenant_id=%s and a.asset_no = any(%s) and al.created_at >= %s""",
                         (T, seeded_assets, move["performed_at"]))[0]["n"]
        c.add("Assets", f"the move-in wrote no asset status (meter status is derived) — {asset_rows} asset audit "
              f"rows read since the move", not status_writes, status_writes)

        # ── Payments: fees, payments, audit, ledger ─────────────────────
        lines = sql("select seq, kind, source, code, amount from move_fee_lines where move_record_id=%s order by seq",
                    (str(move["id"]),))
        c.eq("Payments", "the fee lines are the plan's deposit and connection charge",
             [(r["kind"], r["code"], f"{Decimal(r['amount']):.4f}") for r in lines], expect["fees"])
        fees_total = sum((Decimal(r["amount"]) for r in lines), Decimal("0"))
        fee_tax = sql("select count(*) n from journal_lines where account_id=%s and tax_authority_id is not null",
                      (A,))[0]["n"]
        c.eq("Payments", "no tax was charged on any move-in fee (OQ-BIL-12788 (a))", fee_tax, 0)
        pays = sql("""select p.id, p.payment_no, p.amount, p.purpose, p.status, p.confirmation, p.journal_entry_id,
                             m.code method from payments p left join payment_methods m on m.id=p.method_id
                       where p.account_id=%s order by p.payment_no""", (A,))
        total_paid = sum((Decimal(p["amount"]) for p in pays), Decimal("0"))
        pay = expect["payment"]
        deposit_paid = sum((Decimal(p["amount"]) for p in pays if p["purpose"] == "deposit"), Decimal("0"))
        deposit_fee = sum((Decimal(r["amount"]) for r in lines if r["kind"] == "deposit"), Decimal("0"))
        if pay is None:
            # Add to bill: no money is recorded at move-in; every fee is on the first bill.
            c.eq("Payments", "Add to bill: no payment was recorded", len(pays), 0)
        else:
            c.eq("Payments", f"the payments total ${pay['total']}", money(total_paid), pay["total"])
            if not pay.get("part"):
                c.eq("Payments", "the payments total the fees (paid in full)", money(total_paid), money(fees_total))
            if pay.get("confirmation"):
                c.add("Payments", f"every payment carries "
                      f"{'check number' if pay['method'] == 'check' else 'reference'} {pay['confirmation']}",
                      bool(pays) and all(p["confirmation"] == pay["confirmation"] for p in pays),
                      [p["confirmation"] for p in pays])
            c.add("Payments", f"every payment's tender is {pay['method']}",
                  bool(pays) and all(pay["method"] in (p["method"] or "").lower() for p in pays),
                  [p["method"] for p in pays])
            if pay.get("purposes"):
                c.eq("Payments", "the payments' purposes are as the rule splits them",
                     sorted((p["purpose"], money(p["amount"])) for p in pays), sorted(pay["purposes"]))
            if pay.get("part"):
                c.eq("Payments", "a part payment below the deposit takes NO deposit (never taken partly)",
                     money(deposit_paid), "0.00")
            else:
                c.eq("Payments", "the deposit is paid as a deposit-purpose payment", money(deposit_paid),
                     money(deposit_fee))
        # The account and its payments are new with this move-in, so every row
        # naming them is the move-in's — no clock filter (performed_at is
        # stamped AFTER the account's own audit row inside the same commit).
        audits = sql("""select action, entity_id::text entity from audit_log where tenant_id=%s
                         and (entity_id::text = %s or entity_id::text = any(%s))""",
                     (T, A, [str(p["id"]) for p in pays]))
        actions = sorted({a["action"] for a in audits})
        c.add("Payments", "every payment wrote audit_log (hard rule 7)",
              (bool(pays) or pay is None) and all(any(a["entity"] == str(p["id"]) for a in audits) for p in pays), actions)
        c.add("Accounts", "the move-in wrote audit_log account.moved_in", "account.moved_in" in actions, actions)
        entries = sql("""select je.number,
                                sum(case when jl.side='debit' then jl.amount else 0 end) dr,
                                sum(case when jl.side='credit' then jl.amount else 0 end) cr
                           from journal_entries je join journal_lines jl on jl.journal_entry_id=je.id
                          where je.id in (select journal_entry_id from journal_lines where account_id=%s)
                          group by je.id, je.number""", (A,))
        unposted = [p["payment_no"] for p in pays if p["journal_entry_id"] is None]
        c.add("Payments",
              f"every journal entry for the account balances DR = CR (hard rule 5) — {len(entries)} entries read, "
              f"{len(unposted)} payment(s) not journaled yet ({', '.join(unposted) or 'none'}; a check journals when it clears)",
              all(Decimal(e["dr"]) == Decimal(e["cr"]) for e in entries),
              [(e["number"], str(e["dr"]), str(e["cr"])) for e in entries])

        # ── Billing: the first-bill preview (rolled back) ───────────────
        facts["first_bill"] = _first_bill(c, A, expect, lines, deposit_paid)
        facts.update(_case_extras(c, T, A, move, expect, seeded))

        # ── Route & Cycle ───────────────────────────────────────────────
        points = sql("""select s.code service, r.code route, cy.code cycle, cy.bill_day from service_points sp
                          join services s on s.id=sp.service_id left join routes r on r.id=sp.route_id
                          left join cycles cy on cy.id=sp.cycle_id where sp.unit_id=%s""", (str(acct["unit_id"]),))
        route_codes = {p["route"] for p in points}
        cycle_codes = {p["cycle"] for p in points}
        c.add("Route", f"every service point of the unit is on a route ({len(points)} points)",
              bool(points) and None not in route_codes, sorted(map(str, route_codes)))
        c.add("Route", f"every service point of the unit is on a billing cycle ({len(points)} points)",
              bool(points) and None not in cycle_codes, sorted(map(str, cycle_codes)))
        member = sql("""select r.id, r.code, r.name, m.walk_order from route_memberships m
                          join routes r on r.id=m.route_id where m.unit_id=%s""", (str(acct["unit_id"]),))
        c.add("Route", "the unit holds a place in its route's walk order", bool(member),
              [(m["code"], m["walk_order"]) for m in member])
        bill_day = next((p["bill_day"] for p in points if p["bill_day"]), None)
        first_bill_on = _next_bill_day(date.fromisoformat(expect["opened_at"]), bill_day) if bill_day else None
        facts.update({"route_id": str(member[0]["id"]) if member else None,
                      "route_code": member[0]["code"] if member else None,
                      "route_name": member[0]["name"] if member else None,
                      "cycle_code": next(iter(cycle_codes - {None}), None),
                      "first_bill_on": first_bill_on.isoformat() if first_bill_on else None})

        # ── Work ────────────────────────────────────────────────────────
        orders = sql("""select w.id, w.order_no, t.name template, ty.name type_name, w.state, w.source, a.asset_no, w.due_at,
                               w.window_start, w.window_end, w.assignee_technician_id, w.minutes_on_site,
                               (select count(*) from work_order_cost_lines cl where cl.work_order_id=w.id) cost_lines
                          from work_orders w left join work_order_templates t on t.id=w.template_id
                          left join work_order_types ty on ty.id=t.type_id
                          left join assets a on a.id=w.asset_id where w.account_id=%s order by w.order_no""", (A,))
        c.eq("Work", "one work order per field-visit row", len(orders), len(expect["work_orders"]))
        tz = ZoneInfo(_tenant_tz(tenant))
        for order, want in zip(orders, expect["work_orders"]):
            n = order["order_no"]
            c.eq("Work", f"{n} is raised from the move-in", order["source"], "move_in")
            c.eq("Work", f"{n} carries the template {want['template']}", order["template"], want["template"])
            c.eq("Work", f"{n} is for meter {want['asset']}", order["asset_no"], want["asset"])
            c.eq("Work", f"{n} is due on the move-in date",
                 str(order["due_at"].astimezone(tz).date()) if order["due_at"] else None, expect["opened_at"])
            window = (order["window_start"].astimezone(tz).strftime("%H:%M"),
                      order["window_end"].astimezone(tz).strftime("%H:%M")) if order["window_start"] else None
            c.eq("Work", f"{n}'s window is the one picked (utility time)", window, want["window_local"])
            c.add("Work", f"{n} is assigned to a technician", order["assignee_technician_id"] is not None)
            c.add("Work", f"{n} carries no labour yet (labour comes from arrived/finished times)",
                  order["minutes_on_site"] in (None, 0) and order["cost_lines"] == 0,
                  (order["minutes_on_site"], order["cost_lines"]))

        # ── Messages ────────────────────────────────────────────────────
        msgs = sql("""select channel, template_code, status, source_type, unavailable_reason, sent_at
                        from outbound_messages where account_id=%s order by created_at""", (A,))
        welcome = [m for m in msgs if m["source_type"] == "move"]
        c.add("Messages", f"the move-in's welcome is queued ({len(welcome)} rows)",
              bool(welcome) and all(m["status"] == "queued" for m in welcome),
              [(m["channel"], m["template_code"], m["status"]) for m in welcome])
        receipts = [m for m in msgs if m["source_type"] == "payment"]
        c.add("Messages", f"a receipt is queued for each payment ({len(receipts)} rows for {len(pays)} payments)",
              len(receipts) >= len(pays) > 0 if expect["payment"] is not None else not receipts,
              [(m["channel"], m["template_code"]) for m in receipts])
        c.add("Messages", "no message is marked sent (BR-NOT-013: queued is never sent)",
              all(m["sent_at"] is None and m["status"] != "sent" for m in msgs), sorted({m["status"] for m in msgs}))

        facts.update({
            "move_no": move_no, "account_id": A, "account_no": acct["account_no"],
            "unit_id": str(acct["unit_id"]), "unit_no": acct["unit_no"],
            "customer_name": expect["customer"]["name"],
            "account_type_name": acct["type_name"],
            "services_display": [SERVICE_NAMES[s] for s in sorted(expect["services"])],
            "opening_reads": opening,
            "payments": [{"payment_no": p["payment_no"], "amount_display": money(p["amount"])} for p in pays],
            "deposit_display": f"${money(deposit_paid)}" if deposit_paid else None,
            "fee_codes": [r["code"] for r in lines],
            "confirmation": (pay or {}).get("confirmation"),
            "payment_method": (pay or {}).get("method"),
            "exemption_ref": (expect.get("exemption") or {}).get("certificate_ref"),
            "paid_in_full": money(total_paid) == money(fees_total),
            "fees_total": f"{fees_total:,.2f}",
            "work_orders": [{"order_no": o["order_no"], "id": str(o["id"]), "template": o["template"],
                             "type": o["type_name"], "asset_no": o["asset_no"],
                             "day_display": o["due_at"].astimezone(tz).strftime("%m/%d/%Y") if o["due_at"] else None}
                            for o in orders],
            "messages": [{"channel": m["channel"], "template": m["template_code"]} for m in msgs],
        })
    for row in c.rows:
        known = expect.get("known_defects", {}).get(row["name"])
        if known and not row["pass"]:
            row["detail"] = f"[{known}] {row['detail']}"
    return {"checks": c.rows, "facts": facts}


def _display(value: str) -> str:
    """A reading as a screen prints it: thousands grouped, no trailing zeros."""
    number = Decimal(value)
    text = f"{number:,.6f}".rstrip("0").rstrip(".")
    return text


def _first_bill(c: Checks, account_id: str, expect: dict, fee_lines: list,
                deposit_paid: Decimal = Decimal("0")) -> dict:
    """The first-bill preview the One-time tab draws, priced from typed readings and rolled back."""
    from django.db import transaction

    from apps.assets.models import Asset
    from apps.billing import one_time

    start = date.fromisoformat(expect["opened_at"])
    readings = tuple({"asset_id": str(Asset.objects.get(asset_no=no).id), "value": v}
                     for no, v in expect["preview_reads"].items())
    request = one_time.OneTimeRequest(account_id=account_id, kind="first", period_start=start,
                                      period_end=start + timedelta(days=30), readings=readings)
    try:
        with transaction.atomic():
            body = one_time.preview(request)
            transaction.set_rollback(True)
    except Exception as refusal:  # noqa: BLE001 — a refusal is a finding, printed
        c.add("Billing", "the first-bill preview answers", False, refusal)
        return {}
    c.add("Billing", "the first-bill preview prices (every started service has what it needs)",
          body.get("priced") is True, body.get("priced_unavailable"))
    if not body.get("priced") and "sewer" in expect["services"]:
        # DEF-BIL-9750: a sewer point with no meter holds the whole preview. Price
        # the rest WITHOUT sewer so the fee, tax and deposit facts are still read —
        # labelled, so this is never mistaken for the whole bill.
        scoped = one_time.OneTimeRequest(account_id=account_id, kind="first", period_start=start,
                                         period_end=start + timedelta(days=30), readings=readings,
                                         scope_services=tuple(s for s in expect["services"] if s != "sewer"))
        with transaction.atomic():
            body = one_time.preview(scoped)
            transaction.set_rollback(True)
        c.add("Billing", "the first-bill preview WITHOUT sewer prices (DEF-BIL-9750 isolates sewer)",
              body.get("priced") is True, body.get("priced_unavailable"))
    lines = body.get("lines") or []
    if body.get("priced"):
        fees = [(l.get("kind"), l.get("description"), l.get("amount")) for l in lines
                if l.get("kind") in ("fee", "deposit")]
        taxed = [l.get("description") for l in lines if l.get("kind") in ("fee", "deposit") and l.get("taxable")]
        c.add("Billing", "the first bill carries the move-in's fee lines", any(k == "fee" for k, _d, _a in fees), fees)
        c.add("Billing", "no fee or deposit line on the first bill is taxable", not taxed, taxed)
        deposit_fee = sum((Decimal(r["amount"]) for r in fee_lines if r["kind"] == "deposit"), Decimal("0"))
        deposits = [(l.get("description"), l.get("amount")) for l in lines if l.get("kind") == "deposit"]
        if deposit_fee and deposit_paid:
            c.add("Billing", "a deposit paid at move-in is not billed again on the first bill", not deposits, deposits)
        elif deposit_fee:
            # Not paid at move-in (Add to bill, or a part payment below it): the first bill carries
            # the plan's deposit, plan − paid (P1.14, BR-PAY-012).
            billed = sum((Decimal(str(a)) for _d, a in deposits if a is not None), Decimal("0"))
            c.eq("Billing", f"the deposit NOT taken at move-in is on the first bill (${money(deposit_fee)})",
                 money(billed), money(deposit_fee))
        fee_billed = sorted((d or "", money(a)) for k, d, a in fees if k == "fee" and a is not None)
        c.add("Billing", "the first bill carries each move-in fee line at its recorded amount",
              all(any(money(r["amount"]) == amt for _d, amt in fee_billed) for r in fee_lines if r["kind"] == "fee"),
              fee_billed)
        _first_bill_extras(c, expect, lines)  # fire and taxes (M4/M5, lane MVI-E2E-2)
        _first_bill_m6_m7(c, expect, body)  # solar, trash count, the PO on the bill (lane MVI-E2E-3)
    return {"priced": body.get("priced"),
            "lines": [(l.get("kind"), l.get("description"), l.get("amount")) for l in lines]}


def _case_extras(c: Checks, T: str, A: str, move: dict, expect: dict, seeded: dict) -> dict:
    """The facts only some cases carry (lane MVI-E2E-1: M2's co-owner and device, M3's
    discount and evidence). A case without the key checks nothing here."""
    facts: dict = {}
    for want in expect.get("co_owners", []):
        rows = sql("""select kind, full_name, relationship, date_of_birth, responsible_for_bills
                        from account_co_owners where account_id=%s and full_name=%s""", (A, want["full_name"]))
        c.add("Accounts", f"co-owner {want['full_name']} is written on the account", len(rows) == 1, f"{len(rows)} rows")
        if rows and want["kind"] == "officer":  # a company's owner (M4, lane MVI-E2E-2)
            o = sql("""select kind, title, ownership_pct, signs_for_company from account_co_owners
                        where account_id=%s and full_name=%s""", (A, want["full_name"]))[0]
            c.eq("Accounts", f"{want['full_name']} is an owner/officer, {want['title']}, "
                 f"{Decimal(want['ownership_pct']).normalize():f}%, signs {'yes' if want['signs_for_company'] else 'no'}",
                 (o["kind"], o["title"], f"{Decimal(o['ownership_pct']):.6f}" if o["ownership_pct"] is not None
                  else None, o["signs_for_company"]),
                 ("officer", want["title"], want["ownership_pct"], want["signs_for_company"]))
        elif rows:
            r = rows[0]
            c.eq("Accounts", f"{want['full_name']} is a {want['kind']}", r["kind"], want["kind"])
            c.eq("Accounts", f"{want['full_name']}'s relationship is {want['relationship']}", r["relationship"],
                 want["relationship"])
            c.eq("Accounts", f"{want['full_name']}'s date of birth is as typed", str(r["date_of_birth"]),
                 want["date_of_birth"])
            c.eq("Accounts", f"{want['full_name']} is responsible for bills as ticked", r["responsible_for_bills"],
                 want["responsible_for_bills"])
    devices = []
    for device, parent in expect.get("devices", {}).items():
        rows = sql("""select a.id, p.asset_no parent_no from assets a left join assets p on p.id=a.parent_asset_id
                       where a.asset_no=%s and a.tenant_id=%s""", (device, T))
        c.add("Assets", f"{device} still stands under {parent} (the move-in moved no equipment)",
              bool(rows) and rows[0]["parent_no"] == parent, rows and rows[0]["parent_no"])
        reads = sql("select count(*) n from meter_reads r join assets a on a.id=r.asset_id where a.asset_no=%s "
                    "and r.account_id=%s", (device, A))[0]["n"]
        c.eq("Assets", f"{device} (not a read device) carries no opening read", reads, 0)
        if rows:
            devices.append({"asset_no": device, "asset_id": str(rows[0]["id"]), "parent_no": parent})
    facts["devices"] = devices
    for code in expect.get("discounts", []):
        rows = sql("""select d.id discount_id, d.code, d.name, e.verification_status, e.enrolled_on, e.enrolled_by_user_id
                        from discount_enrolments e join discounts d on d.id=e.discount_id
                       where e.account_id=%s and d.code=%s and e.ended_on is null""", (A, code))
        c.add("Payments", f"the clerk's {code} claim is ENROLLED at Complete (PO 2026-10-05 (b))", len(rows) == 1,
              f"{len(rows)} enrolments")
        if rows:
            r = rows[0]
            facts["discount_name"] = r["name"]
            facts["discount_id"] = str(r["discount_id"])
            # Claimed at move-in, so it covers the first bill from its first day.
            c.add("Payments", f"{code} is enrolled on or before the move-in date (covers the first bill's first day)",
                  str(r["enrolled_on"]) <= expect["opened_at"], f"enrolled {r['enrolled_on']}, moved in {expect['opened_at']}")
            clerk = sql("""select ro.code role from tenant_memberships m join roles ro on ro.id=m.role_id
                            where m.user_id=%s and m.tenant_id=%s""", (str(r["enrolled_by_user_id"]), T))
            c.add("Payments", f"{code} was enrolled by the Billing Clerk herself (no System Admin)",
                  bool(clerk) and clerk[0]["role"] == "billing_clerk", clerk)
            proof = sql("""select v.proof_required, v.verification_method from discount_versions v
                             join discounts d on d.id=v.discount_id where d.code=%s and d.tenant_id=%s
                            order by v.effective_from desc limit 1""", (code, T))
            needs = bool(proof) and (proof[0]["proof_required"] or proof[0]["verification_method"] != "automatic")
            c.eq("Payments", f"{code}'s enrolment waits for verification exactly when the programme asks proof",
                 r["verification_status"], "pending" if needs else "not_required")
    for folder, leaf in expect.get("documents", []):
        rows = sql("""select d.doc_type, s.display_name name from account_documents d
                        left join stored_documents s on s.id=d.document_id
                       where d.account_id=%s and d.withdrawn_at is null""", (A,))
        typed = [r for r in rows if r["doc_type"] == folder and (r["name"] or "").rsplit("/", 1)[-1] == leaf]
        c.add("Accounts", f"the uploaded {leaf} is on the account, in its {folder.upper()} folder (BR-CUS-073/036)",
              len(typed) == 1, [(r["doc_type"], r["name"]) for r in rows])
        if typed:
            facts["evidence_name"] = leaf
    _exemption_extras(c, A, expect)  # M5 (lane MVI-E2E-2)
    if expect.get("po_number"):  # M7 (lane MVI-E2E-3): the PO the clerk typed, on the ACCOUNT (§9.1)
        po = sql("select po_number from accounts where id=%s", (A,))[0]["po_number"]
        c.eq("Billing", f"the account carries PO {expect['po_number']} as typed (accounts.po_number)", po,
             expect["po_number"])
        facts["po_number"] = expect["po_number"]
    return facts


# ── M4/M5 checks (lane MVI-E2E-2). Each runs only when its EXPECT key is present. ──


def _exemption_extras(c: Checks, account_id: str, expect: dict) -> None:
    ex = expect.get("exemption")
    if not ex:
        return
    certs = sql("""select k.code, t.name tax, x.certificate_ref, x.issued_on, x.expires_on
                     from tax_exemption_certificates x join tax_exemption_categories k on k.id=x.category_id
                     join taxes t on t.id=k.tax_id where x.account_id=%s and x.revoked_at is null""", (account_id,))
    c.eq("Billing", "one exemption certificate is recorded on the account (by the billing clerk)", len(certs), 1)
    if certs:
        x = certs[0]
        c.eq("Billing", f"the certificate is {ex['category']} for the {ex['tax']}", (x["code"], x["tax"]),
             (ex["category"], ex["tax"]))
        c.eq("Billing", "the certificate number, issued and expiry dates are as typed",
             (x["certificate_ref"], str(x["issued_on"]), str(x["expires_on"])),
             (ex["certificate_ref"], ex["issued_on"], ex["expires_on"]))
    blanket = sql("select tax_exempt from accounts where id=%s", (account_id,))[0]["tax_exempt"]
    c.add("Billing", "the account's blanket tax-exempt flag is NOT set (ruling (A): only the named tax)",
          not blanket, blanket)
    leaf = expect.get("certificate_file")
    if leaf:
        docs = sql("""select d.doc_type, s.display_name name from account_documents d
                        left join stored_documents s on s.id=d.document_id
                       where d.account_id=%s and d.withdrawn_at is null""", (account_id,))
        c.add("Billing", f"the certificate {leaf} is filed on the account, in its KYC folder",
              [d["doc_type"] for d in docs if (d["name"] or "").endswith(leaf)] == ["kyc"],
              [(d["doc_type"], d["name"]) for d in docs])


def _first_bill_extras(c: Checks, expect: dict, lines: list) -> None:
    fire = expect.get("fire")
    if fire:
        mine = [l for l in lines if l.get("service") == "fire" and l.get("kind") != "tax"]
        c.eq("Billing", "fire is ONE bill line (one line per service, PO 'per service')", len(mine), fire["lines"])
        c.eq("Billing", f"the fire line is ${fire['amount']} ($60.00 + 2 × $12.00)",
             [money(l.get("amount")) for l in mine], [fire["amount"]] * fire["lines"])
    if not (expect.get("taxes_absent") or expect.get("taxes_present")):
        return
    # A tax line is labelled by its JURISDICTION ("Tax City"), never the tax's name, so a
    # name match would pass an ABSENCE check whatever the bill held (law 7). Match by tax_id.
    ids = [str(l.get("tax_id")) for l in lines if l.get("kind") == "tax" and l.get("tax_id")]
    named = {r["id"]: r["name"] for r in sql("select id::text id, name from taxes where id::text = any(%s)", (ids,))}
    taxes = sorted(named.get(i, f"?{i}") for i in ids)
    c.add("Billing", f"every tax line on the first bill names a tax ({len(ids)} tax lines read)",
          len(ids) == len([l for l in lines if l.get("kind") == "tax"]) and "?" not in "".join(taxes), taxes)
    for name in expect.get("taxes_absent", ()):
        # The reason is printed truthfully: a certificate (M5, M7) or the tax's classes (M6, lane MVI-E2E-3).
        why = "its certificate removes it" if expect.get("exemption") and name == expect["exemption"].get("tax") \
            else "not this account's class"
        c.add("Billing", f"the first bill carries NO {name} ({why})", name not in taxes, taxes)
    for name in expect.get("taxes_present", ()):
        why = " STILL carries {} (an exemption removes only its own tax)" if expect.get("exemption") else " carries {}"
        c.add("Billing", "the first bill" + why.format(name), name in taxes, taxes)


# ── M6/M7 and P4.24–P4.26 checks (lane MVI-E2E-3). Each runs only when its key is present. ──


def _first_bill_m6_m7(c: Checks, expect: dict, body: dict) -> None:
    lines = body.get("lines") or []
    if expect.get("solar"):
        # Solar is started with an inverter behind the meter and no meter of its own: the plan's
        # solar base charge is what the first bill can price (SCW-IND's BASE-SOL).
        solar = [(l.get("description"), l.get("amount")) for l in lines
                 if l.get("service") == "solar" and l.get("kind") != "tax"]
        c.add("Billing", "the first bill carries the solar service (the plan's solar charge)", bool(solar), solar)
    trash = expect.get("trash")
    if trash:
        mine = [l for l in lines if l.get("service") == "trash" and l.get("kind") != "tax"]
        c.eq("Billing", f"trash is priced for {trash['count']} carts, ${trash['amount']} (count × size price)",
             money(sum((Decimal(str(l.get("amount") or 0)) for l in mine), Decimal("0"))), trash["amount"])
    for service in expect.get("services_absent_from_bill", ()):
        stray = [(l.get("description"), l.get("amount")) for l in lines if l.get("service") == service
                 or str(l.get("description") or "").lower().startswith(service)]
        c.add("Billing", f"the first bill carries no line for {service}, a service the account did not start",
              not stray, stray)
    po = expect.get("po_number")
    if po:
        # *"PO or reference on bills — printed on every bill of THIS account"* (accounts.po_number,
        # CR-171 P1.11: a billing READ). The first bill is the one bill a move-in can show.
        printed = po in json.dumps(body, default=str)
        c.add("Billing", f"the first bill carries the account's PO {po}", printed,
              "the PO appears nowhere in the first-bill preview" if not printed else "")


def after_cancel(world, case: str, move_no: str) -> dict:
    """P4.24 — J6's four reversals read back after *Cancel move-in* on a committed move-in.

    J6 (CR-171 §6.2): the account CLOSED before any bill (closed_at = the day BEFORE the move-in
    date, so it reads Cancelled — `move_in_cancel.is_cancelled`); the agreements ENDED that day;
    money taken REFUNDED as ONE request (`OQ-CUS-12790` (a): the held deposit released to credit
    and refunded with the rest); open work orders CANCELLED; opening reads KEPT; the unit reads
    Vacant because occupancy is derived (BR-MET-036). Every reversal is a NEW row (hard rule 4).
    """
    from apps.tenancy.models import Tenant
    from core import tenancy as core_tenancy

    expect = EXPECT[case]
    want = expect["cancel"]
    tenant = Tenant.objects.get(subdomain=world.SUBDOMAIN)
    c = Checks()
    with core_tenancy.tenant_context(tenant.id):
        T = str(tenant.id)
        move = sql("select account_id, effective_on from move_records where tenant_id=%s and move_no=%s",
                   (T, move_no))[0]
        A = str(move["account_id"])
        acct = sql("""select a.opened_at, a.closed_at, a.close_reason, s.code status, a.unit_id
                        from accounts a left join account_statuses s on s.id=a.status_id where a.id=%s""", (A,))[0]
        opened = acct["opened_at"]
        day_before = opened - timedelta(days=1)
        c.eq("Accounts", "CANCEL (1/4): the account is closed (terminal status)", acct["status"], "closed")
        c.eq("Accounts", "CANCEL: the account closes the day BEFORE it opened (reads Cancelled)",
             str(acct["closed_at"]), str(day_before))
        agreements = sql("select ended_on from service_agreements where account_id=%s", (A,))
        c.add("Accounts", f"CANCEL: every agreement ends on {day_before} ({len(agreements)} agreements)",
              bool(agreements) and all(str(r["ended_on"]) == str(day_before) for r in agreements),
              [str(r["ended_on"]) for r in agreements])
        refunds = sql("select amount, status, method, journal_entry_id from refunds where account_id=%s", (A,))
        c.eq("Payments", "CANCEL (2/4): ONE refund request for the CLEARED money taken (deposit released + the rest)",
             [(f"{Decimal(r['amount']):.4f}", r["status"]) for r in refunds],
             [(want["refund"], "requested")] if want["refund"] else [])
        if refunds:
            c.eq("Payments", f"CANCEL: the refund goes by {want['method']}", refunds[0]["method"], want["method"])
        releases = sql("select amount from deposit_releases where account_id=%s", (A,))
        c.eq("Payments", "CANCEL: a CLEARED deposit is RELEASED to credit as a new row (deposit_releases)",
             [f"{Decimal(r['amount']):.4f}" for r in releases],
             [want["deposit_released"]] if want["deposit_released"] else [])
        if want.get("called_off"):
            # DEF-CUS-9789: each uncleared payment CALLED OFF through payments' own Cancel — the
            # original `cancelled`, plus a −amount `cancelled` reversing row; nothing posted.
            originals = sql("select amount, status, journal_entry_id from payments where account_id=%s "
                            "and reverses_payment_id is null order by amount desc", (A,))
            c.eq("Payments", "CANCEL: every uncleared payment is CALLED OFF (status cancelled)",
                 [(f"{Decimal(r['amount']):.4f}", r["status"]) for r in originals],
                 [(a, "cancelled") for a in want["called_off"]])
            backs = sql("select amount, status from payments where account_id=%s "
                        "and reverses_payment_id is not null order by amount", (A,))
            c.eq("Payments", "CANCEL: each call-off is a NEW −amount row (hard rule 4)",
                 [(f"{Decimal(r['amount']):.4f}", r["status"]) for r in backs],
                 [(f"-{a}", "cancelled") for a in want["called_off"]])
            c.add("Payments", "CANCEL: nothing called off had posted (no journal entry)",
                  all(r["journal_entry_id"] is None for r in originals), [str(r["journal_entry_id"]) for r in originals])
        pays = sql("select payment_no, status from payments where account_id=%s order by payment_no", (A,))
        c.add("Payments", "CANCEL: the payments themselves are untouched (hard rule 4: corrections are new rows)",
              bool(pays), [(p["payment_no"], p["status"]) for p in pays])
        orders = sql("select order_no, state, dispatch_state from work_orders where account_id=%s", (A,))
        c.add("Work", f"CANCEL (3/4): every open work order is cancelled ({len(orders)} orders)",
              all("cancelled" in (o["state"], o["dispatch_state"]) for o in orders),
              [(o["order_no"], o["state"], o["dispatch_state"]) for o in orders])
        reads = sql("select a.asset_no from meter_reads r join assets a on a.id=r.asset_id where r.account_id=%s",
                    (A,))
        c.eq("Assets", "CANCEL (4/4): the opening reads are KEPT (true readings, append-only)",
             sorted(r["asset_no"] for r in reads), sorted(expect["opening_reads"]))
        open_accounts = sql("select count(*) n from accounts a left join account_statuses s on s.id=a.status_id "
                            "where a.unit_id=%s and a.closed_at is null", (str(acct["unit_id"]),))[0]["n"]
        c.eq("Units", "CANCEL: the unit holds no open account (reads Vacant, derived)", open_accounts, 0)
        audits = sorted({r["action"] for r in sql(
            "select action from audit_log where tenant_id=%s and entity_id::text=%s", (T, A))})
        c.add("Accounts", "CANCEL: the cancel wrote audit_log on the account",
              any("cancel" in a for a in audits), audits)
        entries = sql("""select je.number,
                                sum(case when jl.side='debit' then jl.amount else 0 end) dr,
                                sum(case when jl.side='credit' then jl.amount else 0 end) cr
                           from journal_entries je join journal_lines jl on jl.journal_entry_id=je.id
                          where je.id in (select journal_entry_id from journal_lines where account_id=%s)
                          group by je.id, je.number""", (A,))
        c.add("Payments", f"CANCEL: every journal entry for the account balances ({len(entries)} entries read)",
              all(Decimal(e["dr"]) == Decimal(e["cr"]) for e in entries),
              [(e["number"], str(e["dr"]), str(e["cr"])) for e in entries])
    for row in c.rows:
        known = expect.get("known_defects", {}).get(row["name"])
        if known and not row["pass"]:
            row["detail"] = f"[{known}] {row['detail']}"
    return {"checks": c.rows, "facts": {"closed_on": str(day_before), "refund": want["refund"]}}


def after_date(world, case: str, move_no: str, was: str = "") -> dict:
    """P4.25 — *Change move-in date* (J7) read back: the account's start, its agreements and the
    first bill's proration move; the move record does not (BR-CUS-152, never updated)."""
    from apps.tenancy.models import Tenant
    from core import tenancy as core_tenancy

    expect = EXPECT[case]
    new = expect["change_date"]["to"]
    tenant = Tenant.objects.get(subdomain=world.SUBDOMAIN)
    c = Checks()
    facts: dict = {}
    with core_tenancy.tenant_context(tenant.id):
        T = str(tenant.id)
        move = sql("select account_id, effective_on from move_records where tenant_id=%s and move_no=%s",
                   (T, move_no))[0]
        A = str(move["account_id"])
        opened = sql("select opened_at from accounts where id=%s", (A,))[0]["opened_at"]
        c.eq("Accounts", f"DATE: the account now opens on {new}", str(opened), new)
        agreements = sql("select started_on from service_agreements where account_id=%s", (A,))
        c.add("Accounts", f"DATE: every agreement now starts on {new} ({len(agreements)} agreements)",
              bool(agreements) and all(str(r["started_on"]) == new for r in agreements),
              [str(r["started_on"]) for r in agreements])
        c.eq("Accounts", "DATE: the move record keeps the date it was made with (never updated)",
             str(move["effective_on"]), expect["opened_at"])
        audits = sorted({r["action"] for r in sql(
            "select action from audit_log where tenant_id=%s and entity_id::text=%s", (T, A))})
        c.add("Accounts", "DATE: the change wrote audit_log on the account",
              any("date" in a or "opened" in a or "start" in a for a in audits), audits)
        # The first bill is prorated from the move-in day (BR-BIL-012, B4.3): the base charges it
        # carried BEFORE the change (`was`, read by the main readback's preview from the completed
        # date) and the ones it carries from the new date must DIFFER. A preview "from the old day"
        # taken AFTER the change prices from the account's new start and would compare a figure with
        # itself (lane MVI-E2E-3 saw exactly that: $40.26 → $40.26), so `was` comes from before.
        was = was or None
        now = _base_lines(c, A, expect, new)
        if was is None:
            c.add("Billing", "DATE: the first bill priced BEFORE the change (the proration's 'was')", False,
                  "the readback's first-bill preview did not price, so there is nothing to compare")
        facts.update({"base_was": was, "base_now": now})
        if was is not None and now is not None:
            c.add("Billing", f"DATE: the first bill's prorated base charges move with the date "
                  f"(from {expect['opened_at']}: ${was}; from {new}: ${now})",
                  Decimal(now) < Decimal(was), f"${was} → ${now}")
    for row in c.rows:
        known = expect.get("known_defects", {}).get(row["name"])
        if known and not row["pass"]:
            row["detail"] = f"[{known}] {row['detail']}"
    return {"checks": c.rows, "facts": facts}


def _base_lines(c: Checks, account_id: str, expect: dict, start_iso: str):
    from django.db import transaction

    from apps.assets.models import Asset
    from apps.billing import one_time

    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(expect["opened_at"]) + timedelta(days=30)
    readings = tuple({"asset_id": str(Asset.objects.get(asset_no=no).id), "value": v}
                     for no, v in expect["preview_reads"].items())
    request = one_time.OneTimeRequest(account_id=account_id, kind="first", period_start=start,
                                      period_end=end, readings=readings)
    try:
        with transaction.atomic():
            body = one_time.preview(request)
            transaction.set_rollback(True)
    except Exception as refusal:  # noqa: BLE001 — a refusal is a finding, printed
        c.add("Billing", f"the first-bill preview answers from {start_iso}", False, refusal)
        return None
    if not body.get("priced"):
        c.add("Billing", f"the first-bill preview prices from {start_iso}", False, body.get("priced_unavailable"))
        return None
    base = [l for l in body.get("lines") or [] if l.get("kind") in ("base", "fixed", "recurring", "charge")
            and l.get("amount") is not None]
    return money(sum((Decimal(str(l["amount"])) for l in base), Decimal("0")))


def requests_readback(world) -> dict:
    """P4.26 — the two requests after the clerk's path on the details view.

    R1: To approve → Ask for more (more_info, the ask queued to the applicant) → Approve (the
    pending move-in job, no account — BR-CUS-1077) → Start → Complete (the job done, the account
    opened from the request's start). R2: To approve → Decline (refused, reason kept, the
    refusal letter queued; no job, no account)."""
    from apps.tenancy.models import Tenant
    from core import tenancy as core_tenancy

    tenant = Tenant.objects.get(subdomain=world.SUBDOMAIN)
    c = Checks()
    facts: dict = {}
    with core_tenancy.tenant_context(tenant.id):
        T = str(tenant.id)
        for key, spec in world.REQUESTS.items():
            row = sql("select id, request_no, state, decision_reason from service_requests "
                      "where tenant_id=%s and applicant_name=%s", (T, spec["applicant"]))[0]
            R = str(row["id"])
            events = [(e["from_state"], e["to_state"]) for e in sql(
                "select from_state, to_state from service_request_events where request_id=%s "
                "and to_state is not null order by at, created_at", (R,))]
            jobs = sql("""select j.state, j.move_no, m.account_id from move_in_jobs j
                            left join move_records m on m.move_no=j.move_no and m.tenant_id=j.tenant_id
                           where j.request_id=%s""", (R,))
            letters = sql("select template_code, status, channel from outbound_messages where source_id::text in "
                          "(select id::text from service_request_events where request_id=%s) "
                          "or source_id::text=%s", (R, R))
            facts[key] = {"request_no": row["request_no"], "state": row["state"],
                          "move_no": jobs[0]["move_no"] if jobs else None}
            n = row["request_no"]
            if key == "R1":
                c.add("Accounts", f"{n} went To approve → Waiting on customer → Approved (its timeline)",
                      ("submitted", "more_info") in events and any(t == "approved" for _f, t in events), events)
                c.add("Messages", f"{n}: the ask for more is queued to the applicant, never sent",
                      any(l["status"] == "queued" for l in letters), letters)
                c.eq("Accounts", f"{n}: ONE move-in job, done by Complete", [j["state"] for j in jobs], ["done"])
                acct = sql("""select a.account_no, a.opened_at, u.unit_no from accounts a join units u on u.id=a.unit_id
                               where a.id=%s""", (str(jobs[0]["account_id"]),)) if jobs and jobs[0]["account_id"] else []
                c.add("Accounts", f"{n}: Complete opened the account on the request's unit {spec['unit']}",
                      bool(acct) and acct[0]["unit_no"] == world_unit_no(T, spec), acct)
                c.add("Accounts", f"{n}: the account opens on the request's start {world.REQUEST_START}",
                      bool(acct) and str(acct[0]["opened_at"]) == world.REQUEST_START, acct)
                if acct:
                    facts[key]["account_no"] = acct[0]["account_no"]
            else:
                c.eq("Accounts", f"{n} is Declined (refused)", row["state"], "refused")
                c.add("Accounts", f"{n}: the decline keeps its reason", bool(row["decision_reason"]),
                      row["decision_reason"])
                c.add("Messages", f"{n}: the refusal letter is queued to the applicant",
                      any(l["status"] == "queued" for l in letters), letters)
                c.eq("Accounts", f"{n}: no move-in job and no account", len(jobs), 0)
    return {"checks": c.rows, "facts": facts}


def world_unit_no(tenant_id, spec) -> str | None:
    rows = sql("select u.unit_no from units u join premises p on p.id=u.premises_id where u.tenant_id=%s "
               "and p.address_line=%s and u.label=%s", (tenant_id, spec["address"], spec["unit"]))
    return rows[0]["unit_no"] if rows else None


def _next_bill_day(after: date, bill_day: int) -> date:
    day = min(bill_day, 28)
    candidate = after.replace(day=day)
    if candidate <= after:
        candidate = date(after.year + (after.month == 12), after.month % 12 + 1, day)
    return candidate


def _tenant_tz(tenant) -> str:
    for attr in ("time_zone", "timezone", "tz"):
        value = getattr(tenant, attr, None)
        if value:
            return str(value)
    return "America/Chicago"


def _unit_no(tenant_id, seeded) -> str | None:
    rows = sql("select u.unit_no from units u join premises p on p.id=u.premises_id where u.tenant_id=%s "
               "and p.address_line=%s and u.label=%s", (tenant_id, seeded["address"], seeded["unit"]))
    return rows[0]["unit_no"] if rows else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--move", default="")
    # lane MVI-E2E-3: `--after cancel|date` reads P4.24/P4.25's act back; `--case P26 --after
    # requests` reads P4.26's two requests.
    parser.add_argument("--after", default="")
    parser.add_argument("--was", default="")  # P4.25: the first bill's base total before the change
    args = parser.parse_args()
    sjf = _load("seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py")
    sjf.django_setup()
    world = _load("cr171_e2e_matrix_world", REPO / "10-scripts/cr171_e2e_matrix_world.py")
    if args.after:
        if args.after == "requests":
            out = requests_readback(world)
        elif args.after == "date":
            out = after_date(world, args.case, args.move, args.was)
        else:
            out = after_cancel(world, args.case, args.move)
        print(json.dumps(out, default=str))
        return 0
    if args.case not in EXPECT:
        print(json.dumps({"checks": [{"module": "Runner", "name": f"{args.case} has expectations in the readback",
                                      "pass": False, "detail": "R4 lanes: add this case to EXPECT"}], "facts": {}}))
        return 0
    print(json.dumps(readback(world, args.case, args.move), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
