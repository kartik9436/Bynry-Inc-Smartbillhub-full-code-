# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-37 · task 27 — "Give credit notes a number and a place
#           to be seen". The CR's own words: *"THE DIRECT ANSWER TO 'where can a
#           user view all the credit notes for an account?' — NOWHERE."*
# Story:    US-BIL-016 (the correction that writes them) · US-CUS-010 (the S21
#           account tabs this feeds)
#           Screens: S21 (the new Credits tab — P13) · S28 (the bill-detail
#           panel, already served by `invoice_detail`) · S31 (the sign-off
#           sentence, fixed in `release.py`, nothing routed here)
# Rules:    B14 rule 31 (RATIFIED 2026-08-31, PO: *"no Databse ID on screen -
#           that is a rule"*) · BR-BIL-074 (a credit note's amount is stored
#           NEGATIVE, by check constraint) · BR-BIL-004 (the original bill is
#           never touched; a credit is a new row beside it) · BR-TEN-003 / HR-1
#           (a cross-tenant id reads as absent, never as somebody else's rows) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · CLAUDE.md hard
#           rule 1 (tenant scoping)
# Ruling:   CR-059 §8 CS-37, 2026-09-01. The goodwill-credit accounting behind
#           these rows was ruled 2026-08-12 (*"a separate write-off account"*).
# Tests:    06-backend/tests/test_cr059_cs37_credit_note_identity.py
# Impacts:  config/urls.py inclusion · apps/billing/selectors.account_credit_notes
# ───────────────────────────────────────────────────────
"""`GET /accounts/{id}/credit-notes` — the one place a person can see them all.

Its own module rather than more lines in `apps/billing/api.py`, on the
`documents_api` / `corrections_api` / `payments/reversal_api` precedent and for
hard-won law 11's reason: a file several lanes edit is where a pathspec commit
eats somebody's work.

THIN by law: the read is `selectors.account_credit_notes`. **No ORM, no figure
and no rounding in this file.**

═══════════════════════════════════════════════════════════════════════════════
WHY THE ROUTE IS ON THE ACCOUNT AND NOT ON A `credit-notes` COLLECTION
═══════════════════════════════════════════════════════════════════════════════
CS-37 asks for **one account-scoped read**, and the shape follows the question
it answers: *"show me every credit note on this account."* An account-scoped
path also means the index that already exists — `ix_credit_notes_account`, on
`(tenant, account)`, which CR-059 §7 records as *"never had a query run against
it"* — is the index the query uses, rather than a tenant-wide scan that would
want a different one.

A tenant-wide credit-note REPORT is a separate thing and is deliberately not
here: CR-059 §7b names it as *"a credit-note report over a date range, by
reason, alongside the write-off report"*, and a report has a date range, an
export and a reason filter that this tab does not.

═══════════════════════════════════════════════════════════════════════════════
`AnyTenantRole`, AND WHY IT IS NOT NARROWER
═══════════════════════════════════════════════════════════════════════════════
This is a READ of a document the customer has already been told about — a
goodwill concession queues a *"credit issued"* email the day it is raised. Every
other read of the same rows is already `AnyTenantRole`: the bill detail
(`GET /invoices/{id}`) lists the credit notes raised against that bill, and the
correction chain lists them again. A narrower gate here would hide from a
Billing Clerk the same rows they can read one click away on the bill, which
`refunds_api` argues against in the other direction — a door must not promise
or deny a reach its siblings do not.

The WRITE half is untouched and stays where it is: only `corrections.py` creates
a credit note, and it does so inside a bill correction.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS DOOR DOES **NOT** DO
═══════════════════════════════════════════════════════════════════════════════
* **No write verb of any kind.** A credit note freezes at issue (billing/0002's
  trigger) and hard rule 4 makes a correction a new row. There is no PATCH, no
  DELETE and no `POST /credit-notes` here — the account-level *Issue credit*
  action CS-38 unblocks is a CORRECTION, and it enters through
  `corrections_api`.
* **No `GET /credit-notes/{id}`.** Nothing a detail view would add is absent
  from the row: the number, the date, the amount, the reason and the bill are
  all on it. The same argument CR-059 §7 records for there being no
  `GET /payments/{id}`.
* **It nets nothing into a balance.** See `selectors.account_credit_notes` —
  giving the account balance a second source of truth in a second module is the
  alternative CS-38 rejects by name.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import selectors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: the same reach the bill detail gives
def account_credit_notes(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/credit-notes` — S21's Credits tab (CS-37 · P13).

    Every credit note on one account, newest first, each carrying its number,
    date, amount, reason and the bill it was raised against.

    **An account with none answers 200 with an empty list, never 404.** "This
    customer has never been given a credit" is a true and useful answer; a 404
    would say the account does not exist, which is a different fact and one the
    screen would have to draw as an error. A cross-tenant or unknown id reaches
    the same empty list under HR-1 — RLS plus the explicit tenant filter mean it
    resolves to no rows rather than to somebody else's (hard rule 1).
    """
    require_tenant(request)
    return Response(selectors.account_credit_notes(account_id))


# ── the route ──────────────────────────────────────────────────────────────
# THREE segments (`accounts/<id>/credit-notes`), and `apps.customers.api` — which
# owns the `accounts/…` family — declares no three-segment `accounts/<id>/credit-
# notes` pattern. Django resolves by URL and not by method, so a duplicate path
# SHADOWS rather than merges; this one is claimed by nothing else in the tree.
# The include is registered AFTER customers in config/urls.py, the same ordering
# `apps.payments.api`'s `accounts/<id>/payments` already relies on, so the owning
# module's routes are always matched first.
urlpatterns = [
    path("accounts/<str:account_id>/credit-notes", account_credit_notes),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 (how credit notes work today) · §7b (current vs proposed) ·
#         §8 CS-37 · §11 task 27 · apps/billing/selectors.py ·
#         apps/billing/models.CreditNote · B14 rule 31 · BR-BIL-074
# generated: 2026-09-02 by the CR-059 W5 credit-note identity lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(CR-059 task 28 owns the S21 Credits tab —
#            P13 — and lands in the same lane, one commit later) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E2 no `GET /credit-notes/{id}` and no tenant-wide list is minted. The
#      report CR-059 §7b names is a separate deliverable with a date range and
#      an export; inventing half of it here would be building that story.
#   E3 an account with no credit notes answers 200 with an empty list rather
#      than 404 — the two are different facts and only one of them is an error.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
