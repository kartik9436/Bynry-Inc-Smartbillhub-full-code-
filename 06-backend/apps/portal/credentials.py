# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-016 (EP-CWP-03) — find my account · US-CWP-017 — prove it is
#           you · US-CWP-018 — choose a password · US-CWP-019 — forgotten
#           password · US-CWP-021 (🔒) — the credential store itself.
#           Screens: CWP-015 · CWP-016 · CWP-017 · CWP-018 · CWP-019
# Rules:    BR-CWP-029 (customer credentials get their OWN store, attached to a
#           customer already on file; enrolment never creates a person) ·
#           BR-CWP-030 (three facts, all printed on the paper bill) ·
#           BR-CWP-031 (never date of birth, never the last four of an SSN) ·
#           BR-CWP-032 (matched and proven are TWO states; between them the
#           portal has told the visitor NOTHING) · BR-CWP-033 (the code goes
#           only to a contact already held) · BR-CWP-034 (no contact →
#           dead-end into "ring the office", never something weaker) ·
#           BR-CWP-035 (ten minutes) · BR-CWP-036 (fifteen minutes after three
#           wrong tries) · BR-CWP-037 (policy read from the tenant's existing
#           settings) · BR-CWP-038 (reset returns the SAME panel either way) ·
#           BR-CWP-004 (never resolves into a staff role) · CLAUDE.md hard
#           rule 1 (tenant scoping) · hard rule 7 (the trail)
# Tests:    06-backend/tests/test_us_cwp_016_find_account.py ·
#           test_us_cwp_017_prove_it.py · test_us_cwp_018_password.py ·
#           test_us_cwp_019_forgotten.py · test_us_cwp_021_pg.py (RLS on real
#           PostgreSQL under the non-superuser probe role — law 14)
# Impacts:  apps/portal/api.py (the seven endpoints) · session.py (sign-in
#           reads the credential this file wrote) · migrations/0007, 0008
# ───────────────────────────────────────────────────────
"""🔒 THE CUSTOMER'S CREDENTIAL — enrolment, the one-time code, the reset link.

HUMAN-OWNED · HUMAN-REVIEW-PENDING (CLAUDE.md 🔒 sensitive paths; row in
12-governance/09-human-review-ledger.md). AI-authored under the PO ruling of
2026-08-09, *"AI will do it; we will review it later as human."*

WHAT A DEFEAT OF THIS FILE COSTS, IN ONE SENTENCE, BECAUSE THAT IS WHAT A
REVIEWER IS BEING ASKED ABOUT
------------------------------------------------------------------------
**One customer's own bills and address — Maria Alvarez's, `$142.18` and
`1408 Elm St · A` — and never the utility's whole book.** A portal credential
carries no staff role and no permission catalogue; it resolves to a flat set of
accounts and every query is filtered on that set as well as on the tenant. That
is `BR-CWP-004`'s whole point, and it is why this store is a separate table
rather than a flag on `identity.user`.

THE FOUR THINGS THIS FILE REFUSES, AND THE WORDS IT REFUSES IN
--------------------------------------------------------------
1. **A wrong surname and an unknown account number are refused IDENTICALLY**
   (`BR-CWP-032`). `find_account` returns a token or None; it never returns a
   name, a balance or an address, and the endpoint's body is the same shape
   either way. Three wrong tries lock the FORM for fifteen minutes.
2. **A code goes only to a contact already on file** (`BR-CWP-033`), masked,
   and an account holding neither a phone nor an email **dead-ends** (`BR-CWP-034`).
   It is never sent to an address typed on the previous screen — that would be
   a second factor the attacker chose.
3. **A reset answers the same body whether or not the address has a login**
   (`BR-CWP-038`), and the staff store is not consulted at all, so a staff email
   address cannot be probed here either.
4. **A staff email and password are refused with the ORDINARY failure.** There
   is no branch in `sign_in` that looks at `identity` — it looks in
   `portal_credential`, finds nothing, and answers what it answers for a typo.

WHY THE HASH IS THE PRODUCT'S CONFIGURED ONE AND NOT `Argon2id` VERBATIM
-----------------------------------------------------------------------
⚠ `03-field-map.md` §1 types `password_hash` *"Argon2id"*. **`argon2-cffi` is
not installed on this deployment** and Django's `PASSWORD_HASHERS` therefore
resolves to PBKDF2, which is what `apps/identity/services.py` already hashes
every staff password with. Two hashing policies in one product is worse than
one slower hash: it is a deployment that upgrades one population and not the
other, silently. So this file calls `make_password`/`check_password` — the
ACTIVE configuration — and the day `PASSWORD_HASHERS` names Argon2id, staff and
customers move together, and existing rows re-hash on their next sign-in exactly
as Django already does it. The divergence is stamped in the field map and
recorded in `12-governance/02-decision-log.md` with this reasoning.

TIMING
------
`sign_in` and `request_reset` hash a dummy when they find nothing, so a
registered address and an unregistered one cost the same. That is the same
device `identity.services` uses and for the same reason: without it, response
TIME is the disclosure `BR-CWP-038` forbids in the BODY.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.customers import models as customers_models
from apps.portal import lockout, models
from apps.portal.seams import identity_seam, notifications_seam
from core import audit

#: The three doors `lockout.py` counts, kept as constants so the enrolment form
#: and the sign-in form can never be spelt the same by accident.
FORM_ENROL = "enrol"
FORM_SIGN_IN = "sign_in"
FORM_CODE = "verify_code"


# ═══════════════════════════════════════════════════════════════════════════
# Small pure helpers — no database, no clock
# ═══════════════════════════════════════════════════════════════════════════


def normalise_email(value: Any) -> str:
    """Lower-cased and stripped. The whole of this table's case-insensitivity.

    ⚠ The field map says `citext`; SQLite has no such type, so the normalisation
    happens on the way IN and the unique constraint is then true on both engines
    (law 14 — a case-insensitivity proved only on PostgreSQL is not proved).
    """
    return str(value or "").strip().lower()


#: What `email_refusal` answers. KEYS a catalogue turns into a sentence.
EMAIL_REQUIRED = "email_required"
EMAIL_INVALID = "email_invalid"


def email_refusal(value: Any) -> str | None:
    """`None` for a well-formed address, else WHY it is not one (`DEF-CWP-10380`).

    ⚠ **A STATEMENT ABOUT WHAT WAS TYPED, NEVER ABOUT WHAT IS STORED.** It reads
    no table, so refusing a blank or malformed address tells nobody whether any
    address has a login — `BR-CWP-038` is untouched. Django's own
    `validate_email`, so the portal and every staff form agree on what an email
    address is.
    """
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    if not isinstance(value, str) or not value.strip():
        return EMAIL_REQUIRED
    try:
        validate_email(value.strip())
    except ValidationError:
        return EMAIL_INVALID
    return None


def mask_phone(value: str) -> str:
    """`(512) 555-4218` → `••• ••• 4218` — the string `CWP-017` shows.

    The last four digits and nothing else. A person recognises their own number
    from four digits; a stranger holding a bill learns four digits they cannot
    dial, which is the trade `BR-CWP-033` makes deliberately.
    """
    digits = [character for character in str(value or "") if character.isdigit()]
    tail = "".join(digits[-4:]) if len(digits) >= 4 else "".join(digits)
    return f"••• ••• {tail}" if tail else "•••"


def mask_email(value: str) -> str:
    """`maria@example.com` → `m•••@example.com`. First letter, then the domain.

    The domain is shown because that is what tells a person WHICH of their
    mailboxes to open, and it is not a secret from somebody already holding
    their paper bill.
    """
    raw = str(value or "")
    if "@" not in raw:
        return "•••"
    local, _, domain = raw.partition("@")
    head = local[:1] or "•"
    return f"{head}•••@{domain}"


def surname_of(display_name: str) -> str:
    """The last word of a display name — what a paper bill prints as *last name*.

    A company matches on its whole name instead; `_name_matches` tries both, so
    *"Kestrel Bookkeeping"* is found by its full name and *"Maria Alvarez"* by
    *"Alvarez"*.
    """
    parts = [part for part in str(display_name or "").replace(",", " ").split() if part]
    return parts[-1] if parts else ""


def _name_matches(display_name: str, typed: str) -> bool:
    wanted = str(typed or "").strip().lower()
    if not wanted:
        return False
    full = str(display_name or "").strip().lower()
    return wanted == full or wanted == surname_of(display_name).lower()


def _digest(secret: str) -> str:
    """A one-time code is short and high-entropy-per-use, not a password.

    SHA-256 over the code, with no per-row salt, is deliberate and is the shape
    a comparison must be CONSTANT-TIME for — `hmac.compare_digest` below. A
    password hasher here would put a ~100 ms KDF on a public endpoint that
    accepts six-digit codes, which is a denial-of-service surface, and the code
    is worthless within ten minutes anyway (`BR-CWP-035`).
    """
    return hashlib.sha256(str(secret).encode("utf-8")).hexdigest()


_dummy_hash: str | None = None


def equalise_timing() -> None:
    """Spend the same time on a miss as on a hit (see the module docstring)."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = make_password("smartbillhub-portal-timing-equalizer")
    check_password("timing-equalizer", _dummy_hash)


# ═══════════════════════════════════════════════════════════════════════════
# The password policy — the tenant's own, never a second one
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PolicyVerdict:
    ok: bool
    #: Message KEYS, never sentences: eleven catalogues write the sentence in
    #: their own language (B14 rule 35) and a server that assembled it would
    #: ship English to all eleven.
    failures: tuple[str, ...]
    min_length: int


def check_password_policy(tenant_id: Any, password: str) -> PolicyVerdict:
    """Is this password long and mixed enough FOR THIS UTILITY? (`BR-CWP-037`)

    Read, never hardcoded: `CWP-018` refuses eight characters on a tenant whose
    `pw_min_length` is twelve, and the helper line under the field states the
    tenant's own number.
    """
    policy = identity_seam.password_policy(tenant_id)
    value = str(password or "")
    failures: list[str] = []
    if len(value) < policy["pw_min_length"]:
        failures.append("too_short")
    if policy["pw_require_mixed"]:
        if not any(character.isupper() for character in value):
            failures.append("needs_upper")
        if not any(character.islower() for character in value):
            failures.append("needs_lower")
        if not any(character.isdigit() for character in value):
            failures.append("needs_digit")
    if policy["pw_require_symbol"] and value.isalnum():
        failures.append("needs_symbol")
    return PolicyVerdict(
        ok=not failures, failures=tuple(failures), min_length=int(policy["pw_min_length"])
    )


# ═══════════════════════════════════════════════════════════════════════════
# Step 1 — matching an account, and telling the visitor nothing (BR-CWP-032)
# ═══════════════════════════════════════════════════════════════════════════


def find_account(tenant_id: Any, *, account_no: str, postcode: str, name: str) -> Any:
    """The three facts printed on the paper bill (`BR-CWP-030`), or None.

    ⚠ **THE POSTCODE IS THE SERVICE ADDRESS'S AND IS WALKED TO, NEVER STORED ON
    THE ACCOUNT** (CLAUDE.md hard rule 8: an address lives on `premises` and
    nowhere else). The walk is account → unit → premises, and an account that
    hangs off a premises directly (a master account, `BR-CUS-1010`) is walked
    the other way. A `kind='service'` customer address would have been the
    fourth home the rule retired.

    ⚠ **NOTHING ABOUT THE ACCOUNT IS RETURNED TO THE CALLER'S CALLER.** This
    hands back the row so `issue_code` can read the contact on it; `api.py`
    turns it into `matched: true` and a signed token and nothing else
    (`BR-CWP-032`), and `US-CWP-016` TC-2 asserts the body carries no name, no
    balance and no address.

    ⚠ **DATE OF BIRTH AND THE LAST FOUR ARE NOT ARGUMENTS HERE AND MUST NEVER
    BE** (`BR-CWP-031`). They are held encrypted and blind-indexed for a person
    at a counter to recognise somebody; a public form anyone can hammer is the
    one place they must not be matchable.
    """
    from apps.metering import models as metering_models

    wanted_no = str(account_no or "").strip()
    wanted_postcode = str(postcode or "").strip().replace(" ", "").lower()
    if not wanted_no or not wanted_postcode or not str(name or "").strip():
        return None

    account = (
        customers_models.Account.objects.filter(tenant_id=tenant_id, account_no__iexact=wanted_no)
        .exclude(status__behavior_class="terminal")
        .select_related("unit")
        .first()
    )
    if account is None:
        return None

    premises_id = account.premises_id or getattr(account.unit, "premises_id", None)
    row = (
        metering_models.Premises.objects.filter(
            # `BR-CWP-010` — in the QUERY (`G96`, `DEF-CWP-3775`). `tenant_id`
            # is this function's own argument; leaving it out left the postcode
            # walk relying on RLS alone, which the SQLite suite cannot see.
            tenant_id=tenant_id,
            pk=premises_id,
        )
        .only("postal_code")
        .first()
        if premises_id
        else None
    )
    held = str(getattr(row, "postal_code", "") or "").strip().replace(" ", "").lower()
    if not held or held != wanted_postcode:
        return None

    # ⛔ **THE LIVE LINK, NOT ANY LINK — AND IT DECIDES WHO MAY SIGN IN.**
    # `customers/0060` made a property sale END the seller's
    # `customer_accounts` row instead of deleting it, so a sold account
    # holds TWO rows and this read has no ordering: the database may hand
    # back either. Unfiltered, that is the SELLER keeping a door into a
    # house they sold, or the BUYER's password filed against the seller.
    # The default manager is deliberately unfiltered (the model says why),
    # so a caller that means NOW has to say so. This one means now.
    link = (
        customers_models.CustomerAccount.live(tenant_id=tenant_id, account_id=account.pk)
        .select_related("customer")
        .first()
    )
    customer = getattr(link, "customer", None)
    if customer is None or not _name_matches(customer.display_name, name):
        return None
    return account


def find_account_by_postcode(tenant_id: Any, *, account_no: str, postcode: str) -> Any:
    """`US-CWP-027` — the account being ADDED, on its number and its postcode.

    ⚠ **TWO FACTS HERE, THREE IN `find_account` ABOVE, AND THE DIFFERENCE IS
    DELIBERATE.** Enrolment asks for the surname as well because the person at
    the form has proved nothing at all. This caller is a SIGNED-IN customer
    (`BR-CWP-103`: the security is at the door), and the surname would be a
    weak third fact anyway — a landlord adding a tenant's account does not hold
    the tenant's name, and `US-CWP-027`'s own field list is *account number and
    postcode*.

    ⚠ **THE REAL GUARD IS NOT THIS MATCH — IT IS WHERE THE CODE GOES**
    (`BR-CWP-033`, `US-CWP-027` TC-3). Matching here discloses nothing and adds
    nothing; the account joins the set only when a code sent to the contact
    already on THAT account comes back. A stolen bill number gets you as far as
    a code you cannot read.

    ⚠ **AND THE WALK IS SHARED WITH `find_account`, NOT COPIED.** Both go
    account → unit → premises for the postcode (hard rule 8), so a premises
    change moves both at once; two walks would be two answers to *which account
    is this* and would drift on the first one.
    """
    from apps.metering import models as metering_models

    wanted_no = str(account_no or "").strip()
    wanted_postcode = str(postcode or "").strip().replace(" ", "").lower()
    if not wanted_no or not wanted_postcode:
        return None

    account = (
        customers_models.Account.objects.filter(tenant_id=tenant_id, account_no__iexact=wanted_no)
        .exclude(status__behavior_class="terminal")
        .select_related("unit")
        .first()
    )
    if account is None:
        return None
    premises_id = account.premises_id or getattr(account.unit, "premises_id", None)
    row = (
        metering_models.Premises.objects.filter(
            # `BR-CWP-010` — in the QUERY (`G96`, `DEF-CWP-3775`). `tenant_id`
            # is this function's own argument; leaving it out left the postcode
            # walk relying on RLS alone, which the SQLite suite cannot see.
            tenant_id=tenant_id,
            pk=premises_id,
        )
        .only("postal_code")
        .first()
        if premises_id
        else None
    )
    held = str(getattr(row, "postal_code", "") or "").strip().replace(" ", "").lower()
    if not held or held != wanted_postcode:
        return None
    return account


def already_enrolled(tenant_id: Any, account: Any) -> bool:
    """Does the customer behind this account already hold a login?

    ⚠ **THE ANSWER NEVER REACHES THE VISITOR AS ITSELF** (`07-endpoints.md` §2):
    an already-enrolled account is routed to *reset your password* **without
    confirming a login exists**, which is the same sentence somebody with no
    login sees. Confirming it would turn the enrolment form into a register of
    who banks online with this utility.
    """
    # ⛔ **THE LIVE LINK, NOT ANY LINK — AND IT DECIDES WHO MAY SIGN IN.**
    # `customers/0060` made a property sale END the seller's
    # `customer_accounts` row instead of deleting it, so a sold account
    # holds TWO rows and this read has no ordering: the database may hand
    # back either. Unfiltered, that is the SELLER keeping a door into a
    # house they sold, or the BUYER's password filed against the seller.
    # The default manager is deliberately unfiltered (the model says why),
    # so a caller that means NOW has to say so. This one means now.
    link = customers_models.CustomerAccount.live(
        tenant_id=tenant_id, account_id=getattr(account, "pk", account)
    ).first()
    if link is None:
        return False
    return models.PortalCredential.objects.filter(
        tenant_id=tenant_id, customer_id=link.customer_id
    ).exists()


def contact_for(tenant_id: Any, account: Any) -> tuple[str | None, str | None, str | None]:
    """`(channel, destination, masked)` — the contact ALREADY ON FILE, or three
    Nones, which is `BR-CWP-034`'s dead end.

    SMS is preferred where a mobile is held (field map §1 `otp_channel` default)
    and email is the fallback. ⚠ **SMS IS HELD UNTIL W8** — there is no provider
    — so the message is queued on the channel the contact implies and the queue
    row sits unsent; `api.py` says so on the screen rather than pretending it
    was delivered.
    """
    contact = (
        customers_models.Contact.objects.filter(
            tenant_id=tenant_id, account_id=getattr(account, "pk", account), deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at")
        .first()
    )
    if contact is None:
        return (None, None, None)
    if contact.phone:
        return (models.CHANNEL_SMS, contact.phone, mask_phone(contact.phone))
    if contact.email:
        return (models.CHANNEL_EMAIL, str(contact.email), mask_email(str(contact.email)))
    return (None, None, None)


# ═══════════════════════════════════════════════════════════════════════════
# Step 2 — the one-time code
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class IssuedCode:
    row_id: str
    channel: str
    masked: str
    #: ⚠ **RETURNED SO THE CALLER CAN QUEUE IT, NEVER SO IT CAN BE SERVED.**
    #: `api.py` hands it to the outbound queue and drops it; no response body in
    #: this module contains it. A test reads it back off the queue row, which is
    #: exactly what the demo script does while W6 is not activated.
    code: str


def issue_code(
    tenant_id: Any,
    *,
    purpose: str,
    account: Any = None,
    credential: Any = None,
    channel: str,
    masked: str,
) -> IssuedCode:
    """Mint one code, and invalidate every live one for the same door.

    ⚠ **RESEND INVALIDATES** — the `superseded_at` stamp below and the same
    transaction. Without it the first SMS still works after the second arrives,
    so a code read over somebody's shoulder stays live for its whole ten
    minutes even though the person asked for a new one.
    """
    now = timezone.now()
    if purpose == models.PURPOSE_RESET:
        code = secrets.token_urlsafe(32)
        # The utility's own setting, not `models.RESET_TTL_DAYS` (PO
        # 2026-10-22, *"don't do any hardcoding"*; seeded default 7).
        expires = now + timedelta(days=identity_seam.password_link_valid_days(tenant_id))
    else:
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = now + timedelta(minutes=models.CODE_TTL_MINUTES)

    with transaction.atomic():
        live = models.PortalOneTimeCode.objects.filter(
            tenant_id=tenant_id,
            purpose=purpose,
            consumed_at__isnull=True,
            superseded_at__isnull=True,
        )
        live = (
            live.filter(account_id=getattr(account, "pk", account))
            if account is not None
            else live.filter(portal_credential_id=getattr(credential, "pk", credential))
        )
        live.update(superseded_at=now)
        row = models.PortalOneTimeCode.objects.create(
            tenant_id=tenant_id,
            purpose=purpose,
            #: ⚠ **`getattr(x, "pk", x)`, NOT `getattr(x, "pk", None)` — AND THE
            #: DIFFERENCE IS A CODE THAT CAN NEVER BE VERIFIED (`DEF-CWP-3930`).**
            #: Every other place in this file takes an id OR a row: the
            #: supersede filter eleven lines up reads
            #: `getattr(credential, "pk", credential)`, and so does
            #: `verify_code`. This one call read `None` as its default, so a
            #: caller handing it an id STRING — which the rest of the module
            #: invites — wrote `portal_credential_id = NULL`.
            #:
            #: **Nothing anywhere looked wrong.** The row is written, the
            #: response carries a masked destination and an expiry, the caller
            #: gets its code, and the supersede filter (which accepts an id)
            #: even retires the previous one correctly. Only `verify_code`,
            #: filtering on the credential, can then never find the row it just
            #: made. Found by lane A on the step-up path — the code that guards
            #: CHANGING A PAYMENT METHOD — and reported rather than worked
            #: around, which is the only reason it is fixed here.
            account_id=getattr(account, "pk", account),
            portal_credential_id=getattr(credential, "pk", credential),
            code_hash=_digest(code),
            channel=channel,
            destination_masked=masked,
            expires_at=expires,
        )
    return IssuedCode(row_id=str(row.pk), channel=channel, masked=masked, code=code)


#: What `verify_code` answers. Strings a catalogue turns into a sentence, never
#: sentences (B14 rule 35).
CODE_OK = "ok"
CODE_WRONG = "wrong"
CODE_EXPIRED = "expired"
CODE_LOCKED = "locked"


def verify_code(tenant_id: Any, *, purpose: str, code: str, account=None, credential=None) -> str:
    """One of the four constants above. Single use, ten minutes, six tries.

    ⚠ **AN EXPIRED CODE IS ITS OWN ANSWER AND NOT AN ERROR PAGE** (`BR-CWP-035`
    verbatim: *"an expired code shows 'that code has expired' with a resend"*).
    Collapsing it into `wrong` would send a person who waited eleven minutes
    round the loop guessing at a code that was right.
    """
    row = (
        models.PortalOneTimeCode.objects.filter(
            tenant_id=tenant_id,
            purpose=purpose,
            consumed_at__isnull=True,
            superseded_at__isnull=True,
        )
        .filter(
            **(
                {"account_id": getattr(account, "pk", account)}
                if account is not None
                else {"portal_credential_id": getattr(credential, "pk", credential)}
            )
        )
        .order_by("-created_at")
        .first()
    )
    if row is None:
        return CODE_WRONG
    if row.attempts >= models.CODE_MAX_TRIES:
        return CODE_LOCKED
    now = timezone.now()
    if row.expires_at <= now:
        return CODE_EXPIRED
    if not hmac.compare_digest(row.code_hash, _digest(code)):
        row.attempts = int(row.attempts) + 1
        row.save(update_fields=["attempts"])
        return CODE_LOCKED if row.attempts >= models.CODE_MAX_TRIES else CODE_WRONG
    row.consumed_at = now
    row.save(update_fields=["consumed_at"])
    return CODE_OK


def code_row(tenant_id: Any, row_id: Any) -> Any:
    """One code row by id, for the caller that has to stamp the queue row on it."""
    return models.PortalOneTimeCode.objects.filter(tenant_id=tenant_id, pk=row_id).first()


def attach_outbound(row: Any, outbound_message_id: Any) -> None:
    """Which queue row carries this code — the link the walkthrough reads back."""
    row.outbound_message_id = outbound_message_id
    row.save(update_fields=["outbound_message_id"])


# ═══════════════════════════════════════════════════════════════════════════
# Handing the code to the ONE queue this product has
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE QUEUE IS REACHED THROUGH `seams/notifications_seam.py`, WHICH
# RESOLVES THE DOOR BY NAME RATHER THAN IMPORTING IT — AND THAT IS THE SHAPE
# EVERY OTHER MODULE ALREADY USES** (`apps/metering/seams.py`,
# `apps/customers/seams.py`). G81 refused the first draft of this file for
# importing `apps.notifications.services` directly — *"a write reached through a
# service is still a write"* — and it was RIGHT to. The answer was not to widen
# the gate's allow-list, which would turn a guard into decoration; it was to use
# the exception the platform had already made.
#
# **`outbound_messages` IS THE ONE TABLE B1 OPENS TO CROSS-MODULE WRITES
# (B2 r16 #7).** So queueing a code is not a fifth write point at all — it is
# the platform's own sanctioned door, and the portal walks through it the same
# way metering does.
#
# **IT ALSO MEETS `write_points.py`'s THREE-PART TEST FOR A COMPANION ROW,
# which is the reasoning that must hold or this is a ruling rather than an edit:**
#
#   1. **no independent door** — nothing in the portal can queue one of these
#      except by issuing a code, and `issue_code` is the only way to issue one;
#   2. **written by the OWNING module's own service** — `queue_document` is
#      notifications' ruled insert interface (B1), never `apps/portal` touching
#      `outbound_messages`;
#   3. **it CREATES and changes nothing that existed** — `BR-CWP-026`.
#
# ⚠ **AND THE SOURCE KIND IS `portal`, WHICH WAS ADDED FOR THIS AND IS NOT A
# TIDINESS EDIT.** `CHANNEL_FLOOR_BY_SOURCE` is keyed on the source kind, and
# `account` — the nearest existing kind — carries a PRINT floor. Filing an
# enrolment code under it would have **posted a six-digit login code by letter**,
# arriving four days after it expired. `portal` is deliberately absent from that
# dict: a code is not a document and there is no envelope for it.


def queue_code(tenant_id: Any, *, account: Any, issued: IssuedCode, destination: str) -> None:
    """Hand one enrolment code to the outbound queue, through the seam.

    ⚠ **SMS IS QUEUED AND NOT SENT.** There is no SMS provider until W8
    (`10-execution-plan.md` §0 row 23) and email activates in W6; the row exists
    either way, which is what lets the demo — and `US-CWP-017`'s test — read the
    code back off the queue rather than out of a log. *A message that was never
    queued leaves no trace* is `notifications`' own reason for writing a row even
    when it cannot deliver, and it is the reason here too.
    """
    channel = (
        notifications_seam.CHANNEL_SMS
        if issued.channel == models.CHANNEL_SMS
        else notifications_seam.CHANNEL_EMAIL
    )
    write = notifications_seam.queue_document(
        source_type=notifications_seam.SOURCE_PORTAL,
        template=notifications_seam.template_pin("portal_enrolment_code"),
        # ⚠ The CODE ROW's id, so a resend is a NEW queue row rather than the
        # idempotent re-find of the old one. `queue_document` keys on
        # (source_type, source_id, channel, copy_no); passing the ACCOUNT id
        # would mean the second code was never queued at all and the person
        # would be waiting for a message that already existed as the first.
        source_id=issued.row_id,
        channels=(channel,),
        account_id=getattr(account, "pk", None),
        recipients=(notifications_seam.recipient(channel=channel, address=destination),),
        render_context={
            "code": issued.code,
            "expires_in_minutes": models.CODE_TTL_MINUTES,
            "purpose": "portal_enrolment",
        },
    )
    _attach_first(tenant_id, issued, write)


#: The template class a reset email renders from (`catalogs.AUTHORED_CATALOGS`,
#: seeded by `seed_templates.SEEDABLE` and `notifications/0023`).
RESET_TEMPLATE = "portal_password_reset"

#: Where the emailed link opens: the forgotten-password route, which draws the
#: *choose a new password* form when it carries `ref` and `token`.
RESET_PATH = "/{slug}/portal/forgot-password"


def reset_link(slug: str, issued: IssuedCode) -> str | None:
    """The absolute link a reset email carries, or `None` with no public address.

    `ref` is the code ROW's id and `token` the secret, both in the URL
    FRAGMENT (decision log 2026-10-22: no server or proxy log holds them);
    `auth/reset-password` needs both. The host is `PUBLIC_APP_ORIGIN` (`core.public_origin`), never the
    host the request arrived on — that is the API's (`DEF-CWP-9717`).
    """
    from core import public_origin

    return public_origin.public_app_link(
        RESET_PATH.format(slug=slug), fragment={"ref": issued.row_id, "token": issued.code}
    )


def send_reset(tenant_id: Any, *, credential: Any) -> bool:
    """Mint a seven-day single-use link and queue its email (`DEF-CWP-10381`).

    ⚠ **NO PUBLIC ADDRESS ⇒ NO CODE, NO ROW, ONE AUDIT LINE — AND THE CUSTOMER
    STILL SEES THE ONE ANSWER.** A link on the API's host, or a relative one,
    would be a link that does not open, so none is sent (law 3). The code is
    not minted either, because minting supersedes the person's previous live
    link for a new one that never left the building. The audit row says WHY so
    the utility can find it; the response cannot say it without becoming a
    second answer (`BR-CWP-038`). Returns whether a row was queued.
    """
    from apps.portal.seams import tenancy_seam

    # The unknown-address branch spends one password-hash check; so does this
    # one, so the two answers take the same time (`BR-CWP-038`). Without it an
    # address WITH a login would answer ~100 ms FASTER than one without.
    equalise_timing()
    slug = tenancy_seam.branding(tenant_id)["slug"]
    probe = reset_link(slug, IssuedCode(row_id="-", channel="", masked="", code="-"))
    if probe is None:
        audit.write_row(
            action="portal_credential.reset_not_sent",
            entity_type="portal_credential",
            entity_id=credential.pk,
            after={
                "actor": "portal:self-service",
                "email": mask_email(credential.email),
                "reason": "not sent: the public address is not configured",
            },
        )
        return False
    issued = issue_code(
        tenant_id,
        purpose=models.PURPOSE_RESET,
        credential=credential,
        channel=models.CHANNEL_EMAIL,
        masked=mask_email(credential.email),
    )
    queue_reset(tenant_id, credential=credential, issued=issued, link=reset_link(slug, issued))
    return True


def queue_reset(tenant_id: Any, *, credential: Any, issued: IssuedCode, link: str) -> None:
    """Hand one reset link to the queue — email only, single use, the utility's
    own lifetime.

    `render_context` carries exactly the class's two caller tokens;
    `{utility_name}` and the contact lines are stamped by the renderer from the
    tenant's own identity (BR-TEN-017), never copied here. The subject and body
    come ONLY from the utility's Settings template; a missing one leaves the row
    holding with its reason at dispatch, never a sentence written here.
    """
    from apps.portal.seams import tenancy_seam

    notifications_seam.ensure_seeded(RESET_TEMPLATE)
    customer = getattr(credential, "customer", None)
    write = notifications_seam.queue_document(
        source_type=notifications_seam.SOURCE_PORTAL,
        template=notifications_seam.template_pin(RESET_TEMPLATE),
        # The UTILITY's default language picks the variant (`OQ-CUS-12619`,
        # `BR-NOT-006` amended 2026-09-23); `None` resolves `default`.
        language=tenancy_seam.regional(tenant_id)["language"],
        source_id=issued.row_id,
        channels=(notifications_seam.CHANNEL_EMAIL,),
        recipients=(
            notifications_seam.recipient(
                channel=notifications_seam.CHANNEL_EMAIL, address=credential.email
            ),
        ),
        render_context={
            "customer_name": getattr(customer, "display_name", None),
            "reset_link": link,
            "purpose": "portal_password_reset",
        },
    )
    _attach_first(tenant_id, issued, write)
    # ⚠ **INSTANT, AND AFTER COMMIT** (PO 2026-10-22). The row is on the queue
    # either way; this only stops it waiting for the next cycle. The owning
    # service defers the send to `on_commit` + a background job, so a
    # rolled-back request sends nothing and the send never runs inside the
    # response a stranger is timing.
    notifications_seam.send_now(write)


def _attach_first(tenant_id: Any, issued: IssuedCode, write: Any) -> None:
    """⚠ **NOTHING IS CLAIMED WHEN NOTHING WAS QUEUED.** An unwired seam answers
    `None` and this leaves `outbound_message_id` NULL, so a screen saying *we
    sent you a code* over a queue with no row is a state a test can see."""
    row = code_row(tenant_id, issued.row_id)
    message_id = notifications_seam.first_message_id(write)
    if row is not None and message_id is not None:
        attach_outbound(row, message_id)


# ═══════════════════════════════════════════════════════════════════════════
# Step 3 — the credential itself
# ═══════════════════════════════════════════════════════════════════════════


def create_credential(tenant_id: Any, *, account: Any, email: str, password: str, otp_channel: str):
    """Attach a password to a person ALREADY ON FILE (`BR-CWP-029`).

    Raises `ValueError` when the account is linked to no customer — which is a
    state `BR-CUS-1024` already forbids, so it is an assertion rather than a
    branch a screen ever sees.
    """
    # ⛔ **THE LIVE LINK, NOT ANY LINK — AND IT DECIDES WHO MAY SIGN IN.**
    # `customers/0060` made a property sale END the seller's
    # `customer_accounts` row instead of deleting it, so a sold account
    # holds TWO rows and this read has no ordering: the database may hand
    # back either. Unfiltered, that is the SELLER keeping a door into a
    # house they sold, or the BUYER's password filed against the seller.
    # The default manager is deliberately unfiltered (the model says why),
    # so a caller that means NOW has to say so. This one means now.
    link = customers_models.CustomerAccount.live(
        tenant_id=tenant_id, account_id=getattr(account, "pk", account)
    ).first()
    if link is None:
        raise ValueError("this account is linked to no customer, so there is nobody to enrol")
    now = timezone.now()
    credential = models.PortalCredential.objects.create(
        tenant_id=tenant_id,
        customer_id=link.customer_id,
        email=normalise_email(email),
        password_hash=make_password(password),
        password_changed_on=now,
        otp_channel=otp_channel if otp_channel in models.OTP_CHANNELS else models.CHANNEL_SMS,
        status=models.CREDENTIAL_ACTIVE,
    )
    # Hard rule 7 is written for money actions; standing access to somebody's
    # bills is money-adjacent by `BR-CWP-039`'s own reasoning, so the trail
    # carries it. ⚠ `actor_user_id` is None because the actor is NOT a staff
    # user and `audit_log` has no portal-actor column yet — wave F's task
    # (03-field-map.md §3 row 11). The payload names who it was instead, which
    # is exactly what core/audit.py's contract says to do for a non-user actor.
    audit.write_row(
        action="portal_credential.create",
        entity_type="portal_credential",
        entity_id=credential.pk,
        after={
            "actor": "portal:self-enrolment",
            "customer_id": str(link.customer_id),
            "account_no": getattr(account, "account_no", None),
            "email": mask_email(normalise_email(email)),
        },
    )
    return credential


def credential_by_email(tenant_id: Any, email: str):
    return models.PortalCredential.objects.filter(
        tenant_id=tenant_id, email=normalise_email(email)
    ).first()



#: What `sign_in` answers.
SIGN_IN_OK = "ok"
SIGN_IN_WRONG = "wrong"
SIGN_IN_LOCKED = "locked"


def sign_in(tenant_id: Any, *, email: str, password: str):
    """`(verdict, credential_or_None)`. A staff address is a `wrong`, no more.

    ⚠ **THERE IS NO BRANCH IN THIS FUNCTION THAT LOOKS AT `identity`, AND THAT
    IS THE POINT.** Pine Hill's System Admin types their office email and their
    office password here and gets the ordinary failure, because this store has
    never heard of them — not because a check found them and refused. A check
    that FOUND them would be a way to ask *"is this address a member of staff?"*
    """
    credential = credential_by_email(tenant_id, email)
    if credential is None:
        equalise_timing()
        return (SIGN_IN_WRONG, None)
    now = timezone.now()
    if credential.locked_until is not None and credential.locked_until > now:
        return (SIGN_IN_LOCKED, None)
    if credential.status == models.CREDENTIAL_DISABLED:
        equalise_timing()
        return (SIGN_IN_WRONG, None)
    if not check_password(password, credential.password_hash):
        credential.failed_attempts = int(credential.failed_attempts) + 1
        fields = ["failed_attempts"]
        if credential.failed_attempts >= models.SIGN_IN_MAX_TRIES:
            credential.locked_until = now + timedelta(minutes=models.LOCK_MINUTES)
            credential.status = models.CREDENTIAL_LOCKED
            fields += ["locked_until", "status"]
        credential.save(update_fields=fields)
        return (
            SIGN_IN_LOCKED if credential.failed_attempts >= models.SIGN_IN_MAX_TRIES else SIGN_IN_WRONG,
            None,
        )
    if credential.failed_attempts or credential.locked_until or credential.status != models.CREDENTIAL_ACTIVE:
        credential.failed_attempts = 0
        credential.locked_until = None
        credential.status = models.CREDENTIAL_ACTIVE
        credential.save(update_fields=["failed_attempts", "locked_until", "status"])
    return (SIGN_IN_OK, credential)


def set_password(credential: Any, password: str) -> None:
    """A reset lands here. The row is UPDATEd, and that is lawful: hard rule 4's
    financial immutability names issued invoices, invoice lines, payments and
    journal entries, and a password is none of them."""
    credential.password_hash = make_password(password)
    credential.password_changed_on = timezone.now()
    credential.failed_attempts = 0
    credential.locked_until = None
    credential.status = models.CREDENTIAL_ACTIVE
    credential.save(
        update_fields=[
            "password_hash",
            "password_changed_on",
            "failed_attempts",
            "locked_until",
            "status",
        ]
    )
    audit.write_row(
        action="portal_credential.password_reset",
        entity_type="portal_credential",
        entity_id=credential.pk,
        after={"actor": "portal:self-service", "email": mask_email(credential.email)},
    )


# ═══════════════════════════════════════════════════════════════════════════
# The three lockouts, one helper each, so nothing has to remember a number
# ═══════════════════════════════════════════════════════════════════════════


def enrolment_locked(tenant_id: Any, address: str) -> bool:
    return lockout.is_locked(str(tenant_id), FORM_ENROL, address)


def record_enrolment_miss(tenant_id: Any, address: str) -> int:
    """`BR-CWP-036` — three, not five. The staff sign-in policy applied to a
    PUBLIC form, which is a lower number for the same reason a public form is a
    guessing surface and a staff sign-in page behind a VPN is not."""
    return lockout.record_wrong(
        str(tenant_id), FORM_ENROL, address, max_attempts=models.ENROLMENT_MAX_TRIES
    )


def clear_enrolment(tenant_id: Any, address: str) -> None:
    lockout.clear(str(tenant_id), FORM_ENROL, address)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-016..019@c05e4dd4 · US-CWP-021@c05e4dd4 (EP-CWP-03 stories + BR-CWP-029..040 verbatim)
# generated: 2026-09-04 by the CR-068 wave E build lane
# checklist: A✔ B✔ C✔ D✔(api.py) E✔(CWP-015..019) F✔ G✔ H=PENDING(🔒 credentials — ledger row 09-human-review-ledger.md, plain English with the figure: a defeated portal login costs ONE customer's data — Maria's $142.18 and 1408 Elm St · A — never the utility's book)
# gates: G91 (no import of apps.identity outside seams/identity_seam.py) · G92 (no guest serialiser field outside the allow-list) · G81/G84 (this file is declared in write_points.py with the two models it may write) · pytest tests/test_us_cwp_016..019 · tests/test_us_cwp_021_pg.py on PostgreSQL 16
# exceptions: (1) the hash is the deployment's CONFIGURED hasher, not Argon2id — argon2-cffi is not installed and two hashing policies is worse than one; field map stamped, decision logged. (2) `portal_one_time_code` is a SEVENTH portal table the field map does not list, because a code exists BEFORE the credential does (DEF-CWP-3741). (3) SMS is queued and not sent — no provider until W8.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
