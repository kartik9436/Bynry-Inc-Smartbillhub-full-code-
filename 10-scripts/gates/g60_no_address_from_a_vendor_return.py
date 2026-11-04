#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-674 (PO ruling 2026-08-31, closing OQ-1171), verbatim:
#           *"(a) Ignore it — mailing only, our record unchanged - we cannot
#           make chnges until account confirm it"* · BR-NOT-029 clause (d) ·
#           BR-CUS-070 (the address as given, never overwritten)
# Rules:    CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee) · law 7 (prove a guard RED first) · DEF-182 (a check
#           whose output cannot distinguish pass from fail is worse than none)
# ───────────────────────────────────────────────────────
"""G60 — NOTHING WRITES A CUSTOMER'S ADDRESS FROM A VENDOR'S ANSWER.

WHY THIS GATE EXISTS, AND WHY IT GUARDS AN ABSENCE
--------------------------------------------------
NCOA processing is a licensed mover lookup a mail house runs over the file we
hand it, and it does not only clean an address: **it finds people who have moved
and returns the new one.** So the moment a print hand-over exists, a return file
arrives holding a fact we do not have, and the tempting thing to do with it is
obvious and wrong.

The Product Owner ruled on 2026-08-31, closing `OQ-1171`, verbatim:

    "(a) Ignore it — mailing only, our record unchanged - we cannot make
     chnges until account confirm it"

**The second clause is the rule.** Three options were put — ignore, write it,
or record it as a staff suggestion — and the SUGGESTION was recommended. The PO
chose ignore and gave a reason that disposes of the suggestion too: a queue that
proposes an address change on a third party's say-so is still us proposing it.
`BR-CUS-674` states the general form: **an address changes when the account
holder tells us, and by no other route.**

**Today that rule is satisfied by an ABSENCE**, and an absence is exactly the
kind of guarantee that stops being true without anybody editing the sentence
that claims it (hard-won law 1). Measured on the day the rule was written:

  * there is no inbound vendor path at all — `apps/notifications/provider_seam.py`
    has no vendor, no credentials and no connection to make;
  * the only "return" the product has is `delivery_ops.mark_returned`, a CLERK
    marking a paper letter come-back, whose `update_fields` is
    `returned_at, returned_by, updated_at`;
  * and the one third-party lookup that DOES answer about an address —
    `apps/metering/geocode.geocode_missing` — saves
    `update_fields=["lat", "lng", "updated_at"]` and no address column.

WHAT IT ASSERTS, AND WHY EACH ONE CAN ACTUALLY FAIL
---------------------------------------------------
This is deliberately NOT a "if it's missing, pass" check — this repo recorded
six checks that could not fail in one day, and two of them were written exactly
that way. Every assertion below names a file that must EXIST and a fact that
must be true OF it, so a deleted file is a failure and not a pass:

  1. `delivery_ops.mark_returned` exists, and no `save(update_fields=…)` inside
     `apps/notifications/` names an address column.
  2. `geocode.geocode_missing` exists and its `update_fields` is exactly
     lat/lng/updated_at — the precedent that proves the instinct is already
     honoured where a third party answers about an address.
  3. No module under `apps/notifications/` assigns to an address attribute of a
     premises, account or service-request row.
  4. `BR-CUS-674` and `BR-NOT-029` clause (d) are both in the registers, so the
     code guard and the written rule cannot drift apart.

HOW TO PROVE IT RED (law 7 — and it was, before it was trusted green)
----------------------------------------------------------------------
Add `row.address_line = returned["new_address"]` anywhere under
`apps/notifications/`, or change geocode's `update_fields` to include
`address_line`, and re-run: the gate names the file, the line and the rule.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "06-backend"
NOTIFICATIONS = BACKEND / "apps" / "notifications"
GEOCODE = BACKEND / "apps" / "metering" / "geocode.py"
DELIVERY_OPS = NOTIFICATIONS / "delivery_ops.py"
CUSTOMER_RULES = ROOT / "04-docs" / "05-modules" / "03-customers" / "02-business-rules.md"
NOTIFY_RULES = ROOT / "04-docs" / "05-modules" / "10-notifications" / "02-business-rules.md"

#: The address-bearing columns of every table that says where a customer is.
#: `recipient_address` is deliberately NOT here: it is the address a queued
#: message was ADDRESSED TO — a fact about the message, resolved at queue time
#: from the account — and never the account's own record.
ADDRESS_COLUMNS = (
    "address_line",
    "address_as_given",
    "address_unit_as_given",
    "billing_address_as_given",
    "mailing_address",
    "city",
    "state",
    "postal_code",
)

#: `update_fields=[…]` on a `.save()`, with the list captured.
UPDATE_FIELDS = re.compile(r"update_fields\s*=\s*\[([^\]]*)\]", re.S)

#: An assignment onto an attribute of something — `row.address_line = …`. The
#: `==` guard keeps a COMPARISON from reading as a write.
ASSIGNMENT = re.compile(
    r"^\s*[A-Za-z_][\w.]*\.(" + "|".join(ADDRESS_COLUMNS) + r")\s*=(?!=)", re.M
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def findings() -> list[str]:
    """Return a list of failure sentences. Empty means PASS."""
    failures: list[str] = []

    # ── 1 · THE FILES THIS RULE IS ABOUT MUST EXIST ───────────────────────
    # A missing file is a FAILURE, never a silent pass: "the code that could
    # break the rule is gone" and "I could not find it" look identical to a
    # check that skips, and only one of them is good news.
    for path, marker in (
        (DELIVERY_OPS, "def mark_returned("),
        (GEOCODE, "def geocode_missing("),
    ):
        if not path.exists():
            failures.append(
                f"{path.relative_to(ROOT)} does not exist. BR-CUS-674 is guarded by what "
                f"these files do NOT do, so this gate cannot report on a rule whose "
                f"subject has moved. Point the gate at the new home."
            )
            continue
        if marker not in _read(path):
            failures.append(
                f"{path.relative_to(ROOT)} no longer defines {marker.strip()!r}. "
                f"See BR-CUS-674 — re-point this gate rather than deleting it."
            )

    # ── 2 · NO ADDRESS COLUMN IN ANY NOTIFICATIONS `update_fields` ────────
    if NOTIFICATIONS.exists():
        for path in sorted(NOTIFICATIONS.rglob("*.py")):
            body = _read(path)
            for match in UPDATE_FIELDS.finditer(body):
                named = {token.strip().strip("\"'") for token in match.group(1).split(",")}
                offending = sorted(named & set(ADDRESS_COLUMNS))
                if offending:
                    line = body[: match.start()].count("\n") + 1
                    failures.append(
                        f"{path.relative_to(ROOT)}:{line} saves {', '.join(offending)}. "
                        f"BR-CUS-674 (PO 2026-08-31): an address changes when the ACCOUNT "
                        f"HOLDER tells us, and by no other route — not from a mail vendor's "
                        f"mover lookup and not from a queue that proposes one."
                    )

        # ── 3 · AND NO BARE ASSIGNMENT EITHER ─────────────────────────────
        # `update_fields` is the disciplined way to write one column; the
        # undisciplined way is a plain assignment followed by `.save()`, and a
        # check that only read `update_fields` would pass over it.
        for path in sorted(NOTIFICATIONS.rglob("*.py")):
            body = _read(path)
            for match in ASSIGNMENT.finditer(body):
                line = body[: match.start()].count("\n") + 1
                failures.append(
                    f"{path.relative_to(ROOT)}:{line} assigns {match.group(1)}. "
                    f"BR-NOT-029 clause (d): the print hand-over runs ONE direction — "
                    f"nothing a mailer says about where a customer now lives reaches our "
                    f"record."
                )

    # ── 4 · THE GEOCODER'S PRECEDENT STAYS INTACT ─────────────────────────
    if GEOCODE.exists():
        body = _read(GEOCODE)
        saved = {
            token.strip().strip("\"'")
            for match in UPDATE_FIELDS.finditer(body)
            for token in match.group(1).split(",")
        }
        if not saved:
            failures.append(
                "apps/metering/geocode.py names no update_fields at all. It is the ONE "
                "third-party lookup in this product that answers about an address, and "
                "BR-CUS-674 cites its narrow write (lat/lng only) as the precedent. An "
                "unscoped save there could carry an address column silently."
            )
        offending = sorted(saved & set(ADDRESS_COLUMNS))
        if offending:
            failures.append(
                f"apps/metering/geocode.py saves {', '.join(offending)}. The geocoder is a "
                f"THIRD PARTY answering about an address; BR-CUS-674 says its answer never "
                f"becomes our record. It may write coordinates and nothing else."
            )

    # ── 5 · THE WRITTEN RULE AND THE GUARD MUST NOT DRIFT APART ───────────
    for path, needle, what in (
        (CUSTOMER_RULES, "BR-CUS-674", "BR-CUS-674 in the customers register"),
        (NOTIFY_RULES, "**(d) THE VENDOR'S MOVER RESULT IS NOT A SOURCE WE WRITE FROM",
         "BR-NOT-029 clause (d)"),
    ):
        if not path.exists() or needle not in _read(path):
            failures.append(
                f"{what} is missing from {path.relative_to(ROOT)}. A guard whose rule is not "
                f"written down is a rule the next lane will delete in good faith."
            )

    return failures


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py` — the SHAPE the runner unpacks.

    ⚠ DEF-2849. This function used to BE `findings()` and returned a list.
    Run directly the gate printed `PASS`; run inside the suite the runner did
    `status, detail = module.run()` on an empty list and reported
    `gate crashed: ValueError('not enough values to unpack (expected 2, got 0)')`
    — so the guard on the PO's own address ruling reported nothing but a crash
    from the hour it was written, and `G42` passed it because G42 checks that
    `run()` EXISTS, not what it returns. Two failures of the same family came
    before it (DEF-672, DEF-674) and both were about presence; this one is
    about shape. `main()` delegates here so the two entry points cannot
    disagree — the `g59` convention.
    """
    failures = findings()
    if failures:
        return "FAIL", f"{len(failures)} violation(s): " + " · ".join(failures)
    return (
        "PASS",
        "a vendor's return address is recorded as a claim and never written to "
        "the account (BR-CUS-674, BR-NOT-029 clause (d)); the geocoder writes "
        "coordinates only",
    )


def main() -> int:
    status, detail = run()
    print(f"G60 no-address-from-a-vendor-return: {status} — {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
