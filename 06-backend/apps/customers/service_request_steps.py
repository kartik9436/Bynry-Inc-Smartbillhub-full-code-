# ── Trace ──────────────────────────────────────────────
# Change:  REQ-03 redrawn — SIX capture steps become FOUR, approved by the PO
#          2026-09-29. The drawings are
#          `05-prototype/new-request-four-steps-2026-09-29/*.png` and they are
#          the specification (B14 rule 42); the README beside them is an index.
# Rules:   PO ruling 2026-09-21, verbatim: *"you ahve to show the error at step
#          you mentioned"* (`DEF-MET-6110` / `DEF-MET-6111`) · `BR-SHL-020` r2
#          (nothing English crosses the wire — a step id is a stable code) ·
#          CLAUDE.md hard rule 1 (this module touches no table at all)
# Tests:   06-backend/tests/test_req03_four_steps_server.py
# ───────────────────────────────────────────────────────
"""Which of REQ-03's FOUR steps a refusal belongs to, decided at the CALL SITE.

════════════════════════════════════════════════════════════════════════════
WHAT THIS IS FOR
════════════════════════════════════════════════════════════════════════════
A capture wizard routes a refusal to the step that owns the field, and it
routes on `params["step"]` **and nothing else**. A refusal with no step lands
on whatever card the clerk is looking at; a refusal with the WRONG step is
worse, because it sends the clerk to a screen the named field is not on.

REQ-03 was six steps — `customer · connection · addresses · documents · fees ·
check` — and is now four:

    1 · applicant   the 11 applicant fields, category and sub-category, the
                    co-applicant, and DOCUMENTS (which was step 4)
    2 · property    the address search and the mailing address (was step 3)
    3 · service     the services table, the fees table and the payment
                    (services was step 2; fees and payment were step 5)
    4 · review      read-only (was step 6, `check`)

════════════════════════════════════════════════════════════════════════════
⚠ THE STEP IS THE CALL SITE'S, NEVER A GUESS FROM A FIELD NAME
════════════════════════════════════════════════════════════════════════════
`DEF-MET-7690` (2026-09-28, `262a700fc`) settled the shape on the New Connect
wizard and the reasoning transfers exactly: wrapping the CALL says *this step*
about exactly the set of fields that door accepts, while a list of field names
to match against would be **a second copy of the mapping** that drifts the day
a field is added — and it would drift silently, because a wrong step still
produces a plausible-looking screen.

So there is no field table in this file and there must never be one. Each
endpoint in `service_request_api` wraps its own write in `on_step(...)`, and
the step it names is a property of the door, not of the payload.

⚠ **AN INNER STAMP WINS.** `on_step` leaves a refusal that already carries a
step exactly as it is. Two nested doors then cannot argue, and the one closest
to the field is the one that answers — which is also what makes a blanket
outer wrapper harmless rather than a way of relabelling somebody else's
refusal.

⚠ **THE ENVELOPE IS OTHERWISE UNTOUCHED.** Same code, same `message_key`, same
`field_errors`, same `br_ref`, same HTTP status; `step` is added to `params`
and that is all. `BR-SHL-020` r2 holds — a step id is a stable code and the
sentence is still composed in the eleven catalogues.

⚠ **NOT A CATCH-ALL, AND IT ISSUES NO QUERY.** Only `ValidationError` and
`BizError` — the two catalogue refusals a capture door raises — are caught. An
`AuthError`, a `SysError`, an `IntegrityError` or a genuine crash passes to the
handlers that already own it. Nothing here runs after the catch: the refusal is
re-raised at once, so an enclosing `atomic()` unwinds exactly as before and
CLAUDE.md hard-won law 14's aborted-transaction trap is not reachable from
here.

⚠ **ONE CAPTURE DOOR IS DELIBERATELY UNSTAMPED: `PATCH /service-requests/{id}`
(`update_request`).** It is the one MIXED door — its payload carries applicant
fields (step 1) and `address_as_given` (step 2) in the same call — so no single
step is true of it. Naming one would be the wrong-step failure this file exists
to prevent, and partitioning the payload would be the second copy of the
mapping the paragraph above forbids. It carries NO step, which the wizard
already handles by leaving the clerk where they are. `DEF-CUS-7841` holds it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from core import errors

#: The four steps, in the drawings' order. These are CODES and never words a
#: clerk reads (`BR-SHL-020` r2); the catalogues carry the labels.
STEP_APPLICANT = "applicant"
STEP_PROPERTY = "property"
STEP_SERVICE = "service"
STEP_REVIEW = "review"

#: ⚠ **THE ORDER IS THE DRAWINGS' AND IS PART OF THE CONTRACT.** A screen that
#: numbered them itself would be a second opinion about a picture.
CAPTURE_STEPS: tuple[str, ...] = (
    STEP_APPLICANT,
    STEP_PROPERTY,
    STEP_SERVICE,
    STEP_REVIEW,
)

#: `?step=` is 1-based on every wizard in this product (`EP-SHL-03`, A9's
#: routing model). Published so a caller never counts the tuple itself.
STEP_NUMBER: dict[str, int] = {code: n for n, code in enumerate(CAPTURE_STEPS, start=1)}

#: What the six steps became, kept as DATA because it is the thing a reader of
#: a defect, a test or a register row wants to check, and because leaving it in
#: prose is how a mapping rots. Nothing reads it at runtime — the doors name
#: their own step — so it cannot become the second copy warned about above.
SIX_BECAME_FOUR: dict[str, str] = {
    "customer": STEP_APPLICANT,
    "connection": STEP_SERVICE,
    "addresses": STEP_PROPERTY,
    "documents": STEP_APPLICANT,
    "fees": STEP_SERVICE,
    "check": STEP_REVIEW,
}


def _restamped(refusal: Any, step: str) -> Any:
    """The same refusal with `params["step"]` added. Nothing else moves."""
    kwargs: dict[str, Any] = {
        "message_key": refusal.message_key,
        "params": {**refusal.params, "step": step},
        "field_errors": refusal.field_errors,
        "br_ref": refusal.br_ref,
    }
    return type(refusal)(refusal.code, **kwargs)


@contextmanager
def on_step(step: str) -> Iterator[None]:
    """Name `step` on any catalogue refusal raised inside, and re-raise it.

    Used as `with on_step(STEP_SERVICE): writes.set_services(...)` at the door
    that owns that step. See the module docstring for why the step comes from
    the door and never from the field.
    """
    if step not in STEP_NUMBER:  # pragma: no cover - a typo, caught at import
        raise ValueError(f"{step!r} is not one of REQ-03's four steps")
    try:
        yield
    except (errors.ValidationError, errors.BizError) as refusal:
        # An inner door already answered; the closer one wins.
        if refusal.params.get("step"):
            raise
        raise _restamped(refusal, step) from refusal


# ── Lifecycle ─────────────────────────────────────────────
# packet: the approved REQ-03 redraw (05-prototype/new-request-four-steps-2026-09-29/, five PNGs read AS IMAGES per B14 rule 42) · PO ruling 2026-09-21 "you ahve to show the error at step you mentioned" (DEF-MET-6110 / DEF-MET-6111) · DEF-MET-7690 and its commit 262a700fc, which is the shape this file copies · BR-SHL-020 r2 · CLAUDE.md hard-won laws 7 and 14
# generated: 2026-09-29 by lane REQ03-SERVER
# checklist: A✔ B=deferred(no-frontend-half — the wizard's own CAPTURE_STEPS constant and the panels that render a stamped refusal are SCREEN-A/SCREEN-B's, and this lane was dispatched not to touch a frontend file) C✔ D✔ E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST, through pytest — on_step was reduced to a bare re-raise and the ten step cases were watched failing, then restored byte-for-byte; the guard cases (an inner stamp not relabelled, an AuthError and a crash passing straight through) were written before the wrapper was widened and are what refuse a blanket handler.
# exceptions: (1) PATCH /service-requests/{id} carries NO step, deliberately — it is the one mixed door and naming one step would send a clerk to a screen the field is not on (DEF-CUS-7860). (2) SIX_BECAME_FOUR is data nothing reads at runtime, so it cannot become the second copy of the mapping this module exists to prevent. (3) Only ValidationError and BizError are caught; everything else reaches the handler that already owns it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
