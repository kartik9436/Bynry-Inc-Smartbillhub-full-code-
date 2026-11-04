# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-003 (S31.3 exception step) · US-BIL-029 (stage contracts)
#           Screens: S31.3
# Rules:    BR-BIL-021 (every run threshold is tenant config, seeded, nothing
#           hardcoded) · BR-BIL-015 (an exception resolves by an explicit human
#           choice, never silently) · BR-BIL-037/039 (stage contracts)
# ───────────────────────────────────────────────────────
"""The seven exception cases of the run's step 3, and the error the stages raise.

The cases (BR-BIL-021, all thresholds tenant-configured and seeded — nothing
here is a number): high usage · no usage · estimated · owes a lot · way past
due · late fee due · extra charges. Each carries its own action set, and
BR-BIL-015's law over all of them is that an exception resolves by an explicit
human choice and never by a default.

`BillingRuleError` is what a PURE stage raises when an account cannot be billed
under the rules — no plan, an unknown behaviour class, no currency. It is
deliberately NOT one of the `core.errors` catalog exceptions: those carry an
HTTP status because they answer a request, and a stage does not answer a
request. It runs inside a batch over thousands of accounts, where the right
handling is to record this account as an exception and CARRY ON, not to return
a status code to nobody.

The orchestrator catches it per account. One account that cannot be billed must
never stop the other 499 — which is the PO's ruling of 2026-08-11: *"issue the
clean ones, the problems queue with their reason."*
"""


class BillingRuleError(Exception):
    """This account cannot be billed under the rules, and here is why.

    Raised by the pure stages. Carries a human-readable reason because that
    reason is shown ON SCREEN in the run's exception list — the PO's
    requirement that a break says *why* — so it is written for a billing clerk
    rather than for a log.

    `br_ref` is OPTIONAL and names the rule that refused. Added 2026-08-11 with
    the S31 run API: B8 requires every BIZ refusal to carry its BR-ID, and the
    API layer is not the place to infer one from a sentence — the module that
    knows which rule it is enforcing says so, and `api._as_catalog_refusal`
    carries it into the envelope. Callers that name none get the endpoint's
    default, which is why this stays a keyword with a default rather than
    becoming a required argument on forty raise sites.

    ⚠ **`message_key` AND `params` ARE THE SAME IDEA ONE STEP FURTHER, ADDED
    2026-08-27 FOR `DEF-2720`, AND THEY EXIST BECAUSE THE SENTENCE ABOVE CANNOT
    REACH A CLERK.** The reason above is written here, in English, in Python —
    which is right for a log, an audit row and support, and is by construction
    unreachable by the ten catalogues this product ships beside English
    (`BR-SHL-041`). `api._as_catalog_refusal` therefore maps every refusal onto
    ONE catalogue entry and puts this sentence in `params.detail`, which
    `BR-SHL-020 r2` keeps off the screen deliberately (`DEF-322`).

    That is right for the refusals it was written for and wrong for the few
    whose whole content is a NUMBER a person has to act on. Such a refusal names
    its own key and hands over the figures as params, so the sentence is
    composed where the eleven catalogues are and the numbers are the server's.
    A refusal that names none is unchanged and still gets the generic entry —
    the uniformity `_as_catalog_refusal` argues for is the default, not the
    exception.

    **`params` MUST NOT CARRY PROSE.** It carries figures and stable codes; the
    moment it carries a composed English sentence this is `params.detail` again
    with a new name, and the ten other catalogues are back to showing nothing.
    """

    def __init__(
        self,
        *args: object,
        br_ref: str | None = None,
        message_key: str | None = None,
        params: dict[str, object] | None = None,
    ) -> None:
        self.br_ref = br_ref
        self.message_key = message_key
        self.params = params
        super().__init__(*args)


class BillingConfigError(Exception):
    """A tenant setting the run needs is missing or out of range.

    Distinct from `BillingRuleError` because it is not about ONE account: a
    missing guardrail percentage or grace setting is wrong for the whole run,
    and carrying on per-account would produce a thousand bills under a
    configuration nobody chose. Hard-won law 3 — defaults fail closed.
    """


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-029@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — but `br_ref` now travels INTO one; the translation lives in apps/billing/api._as_catalog_refusal) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · exercised by tests/test_us_bil_029_stages.py
# exceptions: NOT core.errors catalog exceptions, deliberately — a catalog code
#         carries an HTTP status, and a stage running inside a batch over
#         thousands of accounts is not answering a request. G9 guards API files
#         only, so this does not widen the error surface an endpoint can raise
#         · [run-API lane 2026-08-11] `BillingRuleError` gained an OPTIONAL
#         `br_ref`. B8 requires every BIZ refusal to carry its BR-ID, and the
#         API boundary is the wrong place to infer one from a sentence — the
#         module enforcing the rule names it, and `api._as_catalog_refusal`
#         carries it into the envelope. Keyword with a default, so the forty
#         existing raise sites are untouched and inherit the endpoint's default.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
