"""Test payments (sandbox) — the whole payment journey, with nobody's money (Payments · LIVE, phase 5).

⚠ **THIS IS A REAL PROVIDER, NOT A MOCK, AND THAT IS THE POINT.** PO ruling
2026-09-05, verbatim: *"we will have multiple payment providers integrated using
integration module. For given utility we will activate 1 or 2. That work we can
do when integration is ready. Now from beta product point of you can't you
release payment functionality so that we can test it. We can enable payment
provider flow later"*.

So the seven payment stories are built against THIS provider, registered exactly
as `payments_card` and `payments_kiosk` are — its own manifest, its own adapter,
the same `charge` / `card_page` / `refund` operations a real processor declares.
When a vendor is chosen it is another manifest and another adapter, activated
per tenant (`BR-INT-037`: adding a provider adds a manifest and no migration),
and **not one screen changes**.

**What it does:** answers a tokenisation with a token that is a token and
nothing else (`tok_test_…`, brand `Visa`, last four `4242`), and posts its
settlement through the SAME door a real processor uses — the signed inbound
webhook, whose composed idempotency key is what stops a replayed settlement
becoming a second payment (`BR-INT-020` D, hard rule 6). Everything after the
charge is the product's own: the payment row, oldest-bill-first allocation, the
receipt, the balanced ledger pair, the audit row, the refund.

**What it deliberately cannot do**, said out loud so a green beta run is not
read as more than it is: a real authorisation, a real decline, a chargeback, and
the card network's own *confirm it is you* step. Those arrive with a vendor.

⚠ **IT IS REFUSED IN PRODUCTION BY NAME.** `environment` on the connection is
the closed vocabulary that carries it (`BR-INT-026`: sandbox and production are
two rows), and the refusal is a check with a test behind it rather than a
sentence here — a docstring promising a guard is hard-won law 1's oldest shape,
and this one guards real customers' money.

Data, not code (`BR-INT-037`). Read by `apps/integrations/registry.py` at
`AppConfig.ready()` and refused there, by name, if anything below is outside a
closed vocabulary. Display text is the ENGLISH fallback — the catalogue key
`integrations.provider.payments_sandbox.*` wins on screen when present.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
)

MANIFEST = Manifest(
    key="payments_sandbox",
    category="payments",
    display_name="Test payments (sandbox)",
    summary="Take payments end to end with nobody's money, before a provider is chosen.",
    #: LIVE, not `coming_soon`: it is connectable today and a utility can run the
    #: whole journey on it. What is coming soon is a VENDOR, and `payments_card`
    #: already says so for that.
    disposition=Disposition(kind="live", phase=5),
    #: Nothing to hold. The credential exists so the connection has the same
    #: SHAPE as a real one — a lane that special-cases *the sandbox has no
    #: credential* writes a branch the real provider then has to unwrite.
    auth=Auth(mode="none", placement="none"),
    fields=(
        #: The PO's phase-1 dummy API. `required=False`: the sandbox answers
        #: from a fixture and never leaves the process, so a clerk who never
        #: touches this box is right (`DEF-INT-5488`).
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            required=False,
            default="https://sandbox.payments.example",
        ),
        #: ⚠ A CLOSED LIST, NOT FREE TEXT. A tester changes one field and the
        #: screen's refusal path is exercised for real, rather than by a unit
        #: test asserting a branch nobody has ever seen on screen. `Field` has
        #: no help text and does not need one here: the three words say it.
        Field(
            name="behaviour",
            label="How every charge answers",
            kind="select",
            options=("approve", "decline", "timeout"),
        ),
    ),
    operations=(
        Operation(
            name="charge",
            # Sixty a minute, matching the five real card processors so the
            # sandbox behaves like the thing it stands in for. ⚠ This one's
            # `request_key` duplicate guard is SHIPPED and is left exactly as
            # it is: the PO moved the guard for the five REAL processors to
            # Runbooks, and stripping a working one here would be obeying a
            # ruling by breaking something it did not name.
            rate_limit_per_minute=60,
            label="Take a payment",
            description="We ask it to charge a stored card and record the answer.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="manual",
            #: The SAME key discipline as `payments_card`. The key is minted
            #: before the request leaves, so a retry after a timeout carries the
            #: key the first attempt used and the debit is never taken twice
            #: (`US-CWP-045` TC-7).
            idempotency=Idempotency(mode="refuse", source="request_key"),
            completion="immediate",
            codec="json",
            test_action="Charge 10 cents and refund it.",
        ),
        Operation(
            name="card_page",
            # 600 — one call per customer starting a payment, while they wait.
            rate_limit_per_minute=600,
            label="Card page",
            description="Where a customer would type the card number. Here it returns a test token.",
            direction="out",
            initiative="us",
            transport="browser",
            trigger="inline",
            idempotency=Idempotency(mode="refuse", source="request_key"),
            completion="immediate",
            executor="browser_credentialed",
        ),
        Operation(
            name="settlement",
            # INWARD. Sixty, matching the kiosk's payment door: it is the same
            # shape of event arriving from the same kind of machine.
            rate_limit_per_minute=60,
            label="Payment confirmed",
            description="It tells us the payment settled, through the signed inbound door.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            #: ⚠ THE REVERSAL MARKER IS PART OF THE KEY, and leaving it out is
            #: not a tidier key — it is a product that refuses every refund as a
            #: duplicate of the payment it reverses (`BR-INT-020` D). The source
            #: is the provider's event id, exactly as `payments_kiosk`'s returns
            #: declare it; `composite` is not one of the seven the registry
            #: allows, and it said so by name at load rather than at run time.
            idempotency=Idempotency(
                mode="refuse", source="provider_event_id", natural_key="event_id+reversal"
            ),
            completion="immediate",
            codec="json",
            respond_after="dedupe",
            envelope_status={"ok": 200, "duplicate": 409, "refused": 401},
        ),
        # ── CR-139-BRC07 `P5.9` · THE SETTLEMENT FEED ──────────────────────
        # *"Providers are integration manifests, so this is an ADAPTER, not a
        # change to payments."* Outcome: *"Adding a provider stays one manifest
        # and one adapter."*
        #
        # ⚠ **IT IS A SECOND, DIFFERENT MESSAGE AND NOT A BIGGER `settlement`,
        # AND THE WORD `settlement` IS WHY THIS NEEDS SAYING.** The operation
        # above means ONE PAYMENT CLEARED. This one means A BANK CREDIT
        # CARRYING MANY OF THEM, net of what the provider kept — the blueprint's
        # worked case is forty-six payments and one fee. Folding the two into
        # one operation would give a door two payload shapes and one key.
        #
        # ⚠ **THE KEY IS THE PAYOUT'S OWN ID, NOT AN EVENT ID, AND IT IS
        # `P5.3`'s KEY.** `(tenant, provider, settlement id)` is the unique
        # index `uq_settlements_provider_code` in `payments/0038`; declaring
        # `provider_event_id` here would key a redelivery on the DELIVERY rather
        # than on the PAYOUT, so a provider re-sending last night's payout under
        # a fresh event id would write it twice — forty-six duplicate
        # memberships and a second bank credit that does not exist.
        #
        # **Adding a real processor adds this same operation to its own
        # manifest and nothing else.** `apps/payments/settlements.py` names no
        # vendor and compares no `provider_key` to a literal (`BR-INT-037`,
        # `G77`), which is what makes that true rather than aspirational.
        Operation(
            name="payout",
            # INWARD, and RARER than a settlement by three orders of magnitude:
            # one or two a day per provider, against thousands of charges. Sixty
            # is the shape the inbound doors share rather than a measurement —
            # a payout arriving at four an hour is already a provider
            # misbehaving, and a limit that never binds is the correct one.
            rate_limit_per_minute=60,
            label="Paid out",
            description="It tells us it paid us one bank credit, and which payments are in it.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            idempotency=Idempotency(
                mode="refuse", source="provider_event_id", natural_key="settlement_id"
            ),
            completion="immediate",
            codec="json",
            respond_after="dedupe",
            envelope_status={"ok": 200, "duplicate": 409, "refused": 401},
        ),
    ),
)
