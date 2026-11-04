# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-3951 — the receipt address a guest types is accepted,
#           validated and DROPPED. Nothing sends to it and nothing checks that
#           an accepted input is ever used.
# Rules:    BR-NOT-013 (nothing dispatches in this release) · US-CWP-004 §4 (a
#           guest may be a NEIGHBOUR, so the address may not be the customer's)
#           · BR-CWP-021 (a stranger holding the paper is told nothing about
#           the person) · hard-won law 1 (a comment claiming a guarantee is not
#           the guarantee — and neither is a line of customer copy) · law 2's
#           mirror, DEF-CWP-3925 (a hold needs a test that fires when it
#           expires)
# ───────────────────────────────────────────────────────
"""**THE EXPIRY TEST FOR THE HELD RECEIPT-ADDRESS FIELD.**

⚠ **THE FIX WAS TO STOP ASKING, AND THE REASON IS THAT THE ALTERNATIVE NEEDS A
RULING.** Writing an unverified address supplied by an ANONYMOUS caller into a
notification row against somebody else's account is a disclosure decision and a
spam-relay surface — `US-CWP-004` §4 is explicit that a guest may be a
neighbour — so it is not a plumbing job a lane takes on its own. Until it is
ruled, the honest thing is not to collect it. What the form said underneath the
box was *"Optional. We use it only for this receipt."*, which is a guarantee
this product does not provide, written in a customer's own language.

⚠ **AND A HOLD WITH NO EXPIRY TEST IS A PROMISE NOBODY IS KEEPING.** On
2026-09-05 the portal's front page had two working doors out of eight because
five controls went on refusing over screens that had already shipped: landing a
capability and releasing the thing that pointed at it are two acts and only the
first feels like the work. So the hold on the guest form is tied HERE to the
fact it depends on — `charge_guest_bill` reporting `receipt_sent: False`
because nothing can dispatch. **The day that stops being hardcoded, this case
goes red and names the block to remove.**
"""

from __future__ import annotations

import inspect
import pathlib

from apps.payments import gateway


def test_nothing_dispatches_so_the_guest_receipt_reports_it_as_UNSENT():
    """⚠ **READ AS AN EXPIRY ALARM, NOT AS AN APPROVAL OF THE HARDCODING.**

    `charge_guest_bill` sets `receipt_sent` to a literal `False` with its own
    comment saying why — *"nothing dispatches in this release, so this is FALSE
    rather than 'an address was typed'"*. That is the correct answer today and
    it is exactly what the guest form's held sentence stands on.

    WHEN THIS GOES RED, do these three things and not only the first:
      1. `07-frontend/src/portal/guest/QuickPayCheck.tsx` — the
         `data-receipt-email-held` sentence comes out;
      2. the receipt-address field goes back, **once somebody has ruled where an
         anonymous caller's address may be written** (the open half of
         `DEF-CWP-3951`);
      3. `QuickPayCheck.dom.test.tsx`'s two `DEF-CWP-3951` cases are rewritten
         to assert the field is present and posted.
    """
    source = inspect.getsource(gateway.charge_guest_bill)
    assert '"receipt_sent": False' in source, (
        "`charge_guest_bill` no longer hardcodes `receipt_sent: False`, which means this "
        "product may now be able to send a guest receipt. The guest pay form is HOLDING its "
        "receipt-address field on exactly that fact — see this module's docstring for the "
        "three things to do about it."
    )


def test_the_edge_no_longer_forwards_an_address_it_cannot_honour():
    """The other half: the EDGE stopped passing one through.

    ⚠ **THE POINT IS NOT THAT THE PARAMETER IS GONE** — `charge_guest_bill`
    still declares `receipt_email`, and it should, because the day dispatch
    arrives it is the parameter that carries the address. The point is that
    `bill_pay` no longer reads one off a public request body, because there was
    nowhere for it to go.
    """
    # ⚠ **THE FILE, NOT THE FUNCTION.** `guest_api.bill_pay` is wrapped by
    # DRF's `@api_view`, so `inspect.getsource` on the name returns the
    # DECORATOR's inner `view(request, *args, **kwargs)` — six lines of
    # framework that contain neither string, so BOTH assertions below would
    # have passed over any behaviour at all. Found by watching this case fail
    # on the wrong text, which is the only reason it is not a check that
    # cannot fail.
    from apps.portal import guest_api

    whole = pathlib.Path(inspect.getfile(guest_api)).read_text(encoding="utf-8")
    start = whole.index("def bill_pay(")
    after = whole.find("\ndef ", start + 1)
    source = whole[start:] if after == -1 else whole[start:after]
    assert 'body.get("receipt_email")' not in source, (
        "the guest pay edge is reading a receipt address off the request body again. "
        "Nothing sends to it (BR-NOT-013) and writing an anonymous caller's address "
        "against somebody else's account is a disclosure ruling nobody has made."
    )
    assert "receipt_email=None" in source, (
        "the rails are being handed something other than `None` for the receipt address"
    )
