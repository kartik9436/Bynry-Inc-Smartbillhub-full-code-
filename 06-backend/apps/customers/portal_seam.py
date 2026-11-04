# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-4625 — S21's *Portal access* panel announced *"The customer
#          portal is out of scope for this version, and the paperless, SMS and
#          portal flags are columns that were never built. No login date is
#          shown because none exists."* over an account that HAS a portal
#          login. Reported by the PO from the live product: *"I have login
#          portal for this account - portal access says…"*.
# Rules:   PO 2026-09-07 (decision log, *"A TEMPLATE'S 'IS THIS IN USE'
#          SENTENCE BECOMES DERIVED FROM ACTUAL USAGE"*): *"it should be
#          dynamic and based on actual usage"* — DERIVE the state, keep the
#          SPECIFICITY, and where a derivation cannot see something, print
#          what it skipped beside what it checked · PO 2026-09-07 (*"A MESSAGE
#          THAT WILL NOT BE SENT MUST SAY SO ON SCREEN"*) — a channel that is
#          off is a decision the product made and the reader is entitled to
#          know it · BR-CUS-028 (the delivery election) · BR-CWP-004 (a staff
#          user and a customer login are two populations and two tables) ·
#          BR-CUS-054 (`customer_accounts` is the N:M link) · CLAUDE.md hard
#          rule 1 (tenant scoping) · B2 §2 (cross-module WRITES are forbidden;
#          this file only reads)
# Tests:   06-backend/tests/test_def_cus_4625_portal_access.py
# Impacts: apps/customers/selectors.account_detail (its one caller) ·
#          07-frontend/src/features/customers/AccountDetailPage.tsx
# ───────────────────────────────────────────────────────
"""customers → portal SEAM: whether this account can sign in, and when it last did.

WHY THIS FILE EXISTS AT ALL
---------------------------
`CR-068` built the customer portal and `CR-082` seeded it, and the account
detail screen went on saying the portal was *"out of scope for this version"*
because a sentence written in August was still true when it was written. That
is hard-won law 2's mirror — a refusal that rotted the day the thing it refused
arrived — and the Product Owner found it by opening the screen, which is the
fourth time that has happened on this one screen today.

**The fix is not a better sentence. A hand-written replacement would rot the
same way the first one did.** The Product Owner ruled on exactly this shape
earlier the same evening, about a different screen: *"it should be dynamic and
based on actual usage"*, and chose derivation over a drift test with the
stronger reasoning — a check tells the next engineer the string is wrong, while
derivation means the string cannot be wrong. So the screen now states what this
function reads, and there is no sentence left to go stale.

WHAT IT READS, AND THE PATH IT WALKS
------------------------------------
An account does not hold a login. A **customer** does (`portal_credential.
customer_id`, `BR-CWP-029`: enrolment attaches a password to a person already
on file), and a customer reaches an account through `customer_accounts`
(`BR-CUS-054`, an N:M link — a jointly-held account can have two logins). So:

    account → customer_accounts → customer → portal_credential → portal_session

⚠ **IT NEVER TOUCHES `identity.User`** (`BR-CWP-004`, in capitals in the field
map): a staff account and a customer login are two populations with two
permission catalogues, and one table with a flag on it is how a customer
becomes a System Admin by a single wrong boolean. A clerk's own last sign-in is
not a portal fact and is not read here.

⚠ **READ-ONLY BY CONSTRUCTION.** Cross-module writes are forbidden (B2 §2);
nothing in this file creates, updates or deletes anything, in either module.
⊕ 2026-10-22 — `move_portal_sign_in` CALLS the portal's own function for the
clerk's sign-in tick box; the portal writes its row, this file writes none.

⚠ **THE LAST SIGN-IN IS `portal_session`, AND IT IS A REAL DATE RATHER THAN A
PLACEHOLDER.** `PortalSession` carries `issued_at` (when the customer signed
in) and `last_seen_at` (when the session was last used). The later of the two
is the honest answer to *when did this customer last use the portal*, and a
REVOKED session still answers it — signing out does not un-happen a sign-in.

⚠ **AND WHERE IT CANNOT SEE, IT SAYS SO WITH A NUMBER** — the Product Owner's
blind-spot clause, which CLAUDE.md records `G32` failing: it reported **0
unresolved** truthfully, of everything it could see, over 21 live refusals it
could not. `unreadable` names any part of this answer that could not be read,
so the screen prints what was skipped beside what was checked instead of
implying an empty set.
"""

from __future__ import annotations

from typing import Any

#: Every fact this seam can fail to read, named rather than counted, so the
#: screen can say WHICH half is missing instead of falling silent.
UNREADABLE_LOGINS = "logins"
UNREADABLE_LAST_SIGN_IN = "last_sign_in"


def portal_access_for_account(account: Any) -> dict[str, Any]:
    """What the account detail screen can truthfully say about portal access.

    Returns, and every field is DERIVED:

      * ``logins`` — how many customers on this account hold a portal
        credential that is not disabled. `0` is a real answer and means *this
        account has nobody signed up*, which is different from *the portal
        does not exist*.
      * ``locked`` — how many of those are locked out right now
        (`BR-CWP-033`'s failed-attempt lockout). A clerk taking the call
        *"it won't let me in"* is the reason this is on the screen.
      * ``last_sign_in`` — ISO date of the most recent session across those
        credentials, or ``None`` when nobody has ever signed in. ⚠ `None` here
        means *never*, and the screen must say *never* — not *"no date is
        recorded"*, which is what the sentence this replaced said and which is
        now false.
      * ``unreadable`` — the names of any facts above that could not be read.
        Empty is the normal case and an empty list is a CLAIM, so it is only
        ever empty when both reads actually succeeded.
    """
    from apps.customers import models as customers_models

    tenant_id = getattr(account, "tenant_id", None)
    account_id = getattr(account, "pk", None)
    unreadable: list[str] = []

    try:
        customer_ids = list(
            customers_models.CustomerAccount.objects.filter(
                tenant_id=tenant_id, account_id=account_id
            ).values_list("customer_id", flat=True)
        )
    except Exception:  # pragma: no cover — a read that cannot run is REPORTED
        # ⚠ Law 14: this never runs inside another statement's transaction —
        # `account_detail` is a pure read — so a failure here costs the panel
        # and nothing else. It is still reported rather than swallowed, which
        # is the whole point of `unreadable`.
        return {
            "logins": None,
            "locked": None,
            "last_sign_in": None,
            "unreadable": [UNREADABLE_LOGINS, UNREADABLE_LAST_SIGN_IN],
        }

    if not customer_ids:
        return {"logins": 0, "locked": 0, "last_sign_in": None, "unreadable": []}

    # ⚠ Imported HERE rather than at module scope: `apps.customers` must not
    # take a hard import-time dependency on `apps.portal`, which is a younger
    # module and whose app registry is not loaded when this one is imported.
    from apps.portal import models as portal_models

    try:
        credentials = list(
            portal_models.PortalCredential.objects.filter(
                tenant_id=tenant_id, customer_id__in=customer_ids
            ).exclude(status=portal_models.CREDENTIAL_DISABLED)
        )
    except Exception:  # pragma: no cover
        unreadable.append(UNREADABLE_LOGINS)
        credentials = []

    now = _now()
    locked = sum(
        1
        for row in credentials
        if row.locked_until is not None and now is not None and row.locked_until > now
    )

    last_sign_in = None
    if credentials:
        try:
            rows = portal_models.PortalSession.objects.filter(
                tenant_id=tenant_id,
                portal_credential_id__in=[row.id for row in credentials],
            ).values_list("issued_at", "last_seen_at")
            stamps = [stamp for pair in rows for stamp in pair if stamp is not None]
            last_sign_in = max(stamps).date().isoformat() if stamps else None
        except Exception:  # pragma: no cover
            unreadable.append(UNREADABLE_LAST_SIGN_IN)

    return {
        "logins": None if UNREADABLE_LOGINS in unreadable else len(credentials),
        "locked": None if UNREADABLE_LOGINS in unreadable else locked,
        "last_sign_in": last_sign_in,
        "unreadable": unreadable,
    }


def customers_with_portal_login(tenant_id: Any, customer_ids: list[Any]) -> set[str]:
    """Which of these customers hold a portal login that can sign in — ONE query
    for a whole page of the customers list (`has_portal_login` on the row, which
    decides whether *Edit customer* offers the sign-in tick box; PO 2026-10-22).
    The same *not disabled* test `portal_access_for_account` counts. READ ONLY.
    """
    ids = [one for one in customer_ids if one is not None]
    if not ids:
        return set()
    from apps.portal import models as portal_models

    return {
        str(one)
        for one in portal_models.PortalCredential.objects.filter(
            tenant_id=tenant_id, customer_id__in=ids
        )
        .exclude(status=portal_models.CREDENTIAL_DISABLED)
        .values_list("customer_id", flat=True)
    }


def login_customers_for_account(account: Any) -> list[str]:
    """The customers holding THIS account now who have a portal login.

    The account's *Customer* pencil offers the sign-in tick box only when this
    is exactly one person (decision log 2026-10-22, lane SIGNIN-EMAIL item 2):
    with two, nothing says whose login the primary contact is. READ ONLY.
    """
    from apps.customers import models as customers_models

    holders = list(
        customers_models.CustomerAccount.live(
            tenant_id=account.tenant_id, account_id=account.pk
        ).values_list("customer_id", flat=True)
    )
    found = customers_with_portal_login(account.tenant_id, holders)
    return [str(one) for one in holders if str(one) in found]


def move_portal_sign_in(
    tenant_id: Any, *, customer_id: Any, email: Any, actor_user_id: Any
) -> dict[str, Any]:
    """⚠ **THE ONE CALL IN THIS FILE THAT CHANGES ANYTHING, AND IT IS NOT A
    CUSTOMERS WRITE.** A clerk ticked *"Also use this as the portal sign-in
    email"* (PO 2026-10-22, closes `OQ-CUS-12350`). The login is the PORTAL's
    own table, so the portal's own function moves it
    (`apps.portal.email_update.staff_move_sign_in`, declared in its
    `write_points.STAFF_WRITE_MODULES`) and this module writes none of its rows
    (B2 §2). Returns `{"result": "moved" | "unchanged" | "no_login" |
    "email_required" | "email_invalid" | "taken", ...}` and the caller turns a
    refusal into the clerk's field error.
    """
    from apps.portal import email_update

    return email_update.staff_move_sign_in(
        tenant_id, customer_id=customer_id, email=email, actor_user_id=actor_user_id
    )


def agreement_link_valid_days(tenant_id: Any) -> int:
    """`CR-190-BRC10` — how many days an emailed agreement link stays valid:
    the utility's `portal_settings.agreement_link_valid_days` (Settings →
    Customer portal, seeded 7). READ ONLY. A utility with no settings row yet
    reads the column's own seeded default, which is the same 7 — the value is
    the model's, never typed here (PO 2026-10-22, *"don't do any hardcoding"*).
    """
    from apps.portal import models as portal_models

    value = (
        portal_models.PortalSettings.objects.filter(tenant_id=tenant_id)
        .values_list("agreement_link_valid_days", flat=True)
        .first()
    )
    if value is None:
        value = portal_models.PortalSettings._meta.get_field("agreement_link_valid_days").default
    return int(value)


def application_tax_id(request: Any) -> str | None:
    """**The Tax ID a BUSINESS typed on its portal application, or `None`.**

    `DEF-CWP-9045`, under `OQ-CWP-1560` — CLOSED 2026-09-04 with option (b),
    PO verbatim: *"stores a government identifier once instead of twice"*. The
    number stays on `portal_application_drafts` and is READ from there: by the
    request page (last four, `service_request_reads`) and by the doors that
    open the request's account, which carry it into the NEW company customer's
    identity (`services._carry_request_decisions`) so `BR-CUS-1024` is met
    without a clerk ringing the applicant for a number they already typed.

    ⚠ **READ-ONLY, AND ONLY FOR THE REQUEST THE DRAFT RAISED.** The draft is
    found by `service_request_id`, which only the portal's own submit writes,
    and the request must be a business's portal application; anything else
    answers `None`. Nothing here writes, in either module (B2 §2).
    """
    if request is None or getattr(request, "channel", None) != "customer_portal":
        return None
    if getattr(request, "applicant_kind", None) not in ("business", "company"):
        return None
    from apps.portal import models as portal_models

    number = (
        portal_models.PortalApplicationDraft.objects.filter(
            tenant_id=request.tenant_id, service_request_id=request.pk
        )
        .values_list("tax_id", flat=True)
        .first()
    )
    number = str(number or "").strip()
    return number or None


def application_mailing_address(request: Any) -> dict[str, Any] | None:
    """**Where the applicant asked for the bill to go, as typed on the portal's
    start-service form — or `None`** (`DEF-CWP-9163`, PO 2026-10-02: *"Mailing
    Address is not captured as part of the applicant/customer information"*).

    Read from the draft, where it is stored ONCE, exactly as
    `application_tax_id` is: by the request page (the clerk sees it) and by the
    doors that open the request's account, which turn it into the account's
    ONE `customers.addresses` `kind='mailing'` row
    (`services._carry_request_decisions`) — hard rule 8's first named
    exception, *where the BILL goes*. Never a premises address.

    `None` when the request did not come from the portal, when the applicant
    left *Same as the service address* ticked, or when nothing was typed.
    READ-ONLY, in both modules (B2 §2).
    """
    if request is None or getattr(request, "channel", None) != "customer_portal":
        return None
    from apps.portal import models as portal_models

    row = (
        portal_models.PortalApplicationDraft.objects.filter(
            tenant_id=request.tenant_id, service_request_id=request.pk
        )
        .values(
            "mailing_same_as_service",
            "mailing_line1",
            "mailing_line2",
            "mailing_city",
            "mailing_state",
            "mailing_postal_code",
        )
        .first()
    )
    if not row or row["mailing_same_as_service"] or not (row["mailing_line1"] or "").strip():
        return None
    return {
        "line1": row["mailing_line1"],
        "line2": row["mailing_line2"],
        "city": row["mailing_city"],
        "state": row["mailing_state"],
        "postal_code": row["mailing_postal_code"],
    }


def _now():
    from django.utils import timezone

    return timezone.now()


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-4625 (the S21 portal panel, derived rather than declared)
# generated: 2026-09-07 by the account-Usage-tab lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_def_cus_4625_portal_access.py
# exceptions: E3 `apps.portal` is imported inside the function rather than at
#   module scope — `apps.customers` loads first and a top-level import would
#   make a younger module's app registry a hard dependency of an older one's
#   import. The call is still resolved BY NAME through this one seam file, and
#   nothing here writes (B2 §2) · E3 the `except Exception` arms are
#   deliberately broad and each REPORTS through `unreadable` rather than
#   swallowing: an absent number and a number that could not be read are
#   different claims, and the screen says which
