# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) — the guard in front of the guest surface.
# Rules:    BR-CWP-001 (the portal may write rows of exactly SIX kinds: a
#           payment, a service request, a meter reading, a preference on the
#           account, a contact detail, an account link — every other portal
#           operation is a read; it said FOUR until 2026-09-04) · BR-CWP-002 (a
#           write outside those six is refused at the edge) · BR-CWP-003 (the
#           six are declared AS DATA so a gate can read them; a seventh write
#           point in code without a row here fails the build) · BR-CWP-103
#           (where the portal's security lives: at the door) · CR-068 R12
# Tests:    10-scripts/gates/g78_portal_write_points.py (reads this file with
#           `ast`; selftest replays a fifth function and a write in the edge) ·
#           10-scripts/gates/g84_module_write_tables.py (reads MODULE_WRITE_TABLES
#           and refuses a model a file's allowance does not name)
# Impacts:  apps/portal/services.py (every public function there is one of
#           these) · apps/portal/guest_api.py · api.py · selectors.py · seams/
#           (none may write)
# ───────────────────────────────────────────────────────
"""The six write points, declared as data (BR-CWP-003 · CR-068 R12).

⚠ **IT WAS FOUR UNTIL 2026-09-04 AND THE TWO NEW ROWS ARRIVED BY DIFFERENT
ROUTES.** `contact_detail` is a Product Owner ruling (`OQ-CWP-1562`);
`account_link` is a defect in our own extraction (`DEF-CWP-3768`) — the
blueprint specified it in `BR-CWP-009` and drew the screen, and `BR-CWP-001`
failed to count it. Each row below says which it is, in its own comment.

**Read by G81, never imported by the product.** The gate parses this file with
`ast` and asserts three things: exactly these six kinds are declared; every
public function in `apps/portal/services.py` is the `function` of one of
them; and no other file under `apps/portal/` performs an ORM write — except
`settings_service.py`, which is the BACK OFFICE's write to the portal's own
settings row, performed by a signed-in System Admin and not by the portal
surface (see `STAFF_WRITE_MODULES`).

`function` is `None` until the wave that builds that write lands; the row is
here from day one so the boundary is a machine check and not a sentence in a
design document. **Nobody ever decides to allow one more; a lane just needs one
more field** — which is why adding a row here is a ruling and not an edit, and
why the two added on 2026-09-04 each carry the ruling or the defect that put
them there.

⚠ **THE FIRST WAVE TO BUILD ONE MET THE EDGE OF THE RULE ON ITS FIRST DAY
(2026-09-04, CR-068 wave B) — AND THE PRODUCT OWNER RULED THAT SHAPE OUT THE
SAME DAY (`CR-072`). BOTH HALVES ARE KEPT HERE, BECAUSE THE LESSON IS IN THE
PAIR AND NOT IN EITHER ONE.**

A report of a burst main used to create TWO rows: the service request a clerk
works, and an `interruptions` row it was about — a record `BR-CWP-001` predates,
because the blueprint drew it and nothing had built it. The rule names four
KINDS and that was a fifth kind of row, so it was declared as a `companions`
entry on the service-request row rather than as a fifth `kind`, with three
conditions written out:

  1. the companion has **no independent door** — nothing in the portal can
     create one except by making the declared write;
  2. it is written by the **owning module's own service**, in the same
     transaction, never by `apps/portal` touching its table;
  3. it **creates**, and changes nothing that existed — `BR-CWP-026`.

**ALL THREE HELD, THE GATE WAS GREEN, AND THE SHAPE WAS STILL WRONG.** The
Product Owner looked at the live portal and said *"all the request coming from
portal should go in Service request"*. The question this field asks — *can this
second row be reached another way?* — is about ACCESS. What was wrong was the
DESTINATION: a clerk had two rows, and the person who reported the burst main
was holding the number of the one that was not their request.

**So `companions` is EMPTY, and it stays declared.** The report IS the service
request; the confirmed interruption is opened later by a CLERK from the staff
app, which is not a portal write at all. The field is left in place — with this
note — because the next lane that wants a second row will reach for it, and it
should find the three conditions **and** the reason they were not enough.

Adding a `kind` for it would also have failed G81, which requires exactly the
kinds declared here; that is the gate doing its job, not an obstacle to route
around. **Moving that list is a ruling with a row in the decision log, which is
what 2026-09-04 was** — not a lane that needed one more field.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.portal.seams.customers_seam import CHANNEL_CUSTOMER_PORTAL


@dataclass(frozen=True)
class WritePoint:
    kind: str
    lands_in: str
    owner: str
    function: str | None
    built_in: str
    rule: str
    #: ⚠ **A COMPANION IS A ROW THIS WRITE POINT CREATES IN THE SAME ACT AND IN
    #: THE SAME TRANSACTION, THROUGH THE OWNING MODULE'S OWN SERVICE.** It is
    #: DATA, added 2026-09-04 with the first companion this product has, so the
    #: fact is readable rather than buried in a docstring.
    #:
    #: **IT IS NOT A LOOPHOLE AND THE TEST IS ONE SENTENCE: a companion has no
    #: independent door.** Nothing in the portal can create one on its own; it
    #: exists only because the declared write happened. `report_a_problem`
    #: cannot raise an interruption without raising the request, and there is no
    #: second function that could.
    #:
    #: **WHAT WOULD MAKE THIS WRONG, stated so a reviewer can check it:** a
    #: companion that a future wave gives its own entry point, or a companion
    #: on a row a customer's action changes rather than creates. Either is a
    #: FIFTH WRITE POINT and needs `BR-CWP-001` reopened — not another line here.
    companions: tuple[str, ...] = ()


WRITE_POINTS: tuple[WritePoint, ...] = (
    WritePoint(
        kind="payment",
        lands_in="payments (one row, allocated by the tenant's rule)",
        owner="apps.payments.services",
        function=None,
        built_in="wave P — US-CWP-045 · US-CWP-046 (rails)",
        rule="BR-CWP-058",
    ),
    WritePoint(
        kind="service_request",
        lands_in=f"service_requests with channel {CHANNEL_CUSTOMER_PORTAL!r}",
        owner="apps.customers.service_request_service",
        function="raise_service_request",
        # ⚠ ONE FUNCTION, THREE SHAPES, TWO WAVES — and it has to be one,
        # because G81 allows exactly one per kind and a second public `def`
        # in services.py fails the build by name. Wave B built it as
        # `report_a_problem`; wave C made the report one `shape` of
        # `raise_service_request` and added the application (CWP-009) and
        # the quick asks (CWP-010) beside it. The bodies are unchanged.
        built_in="wave B, 2026-09-04 — US-CWP-007 · US-CWP-009 (the first rows in this product ever to carry the channel); wave C, 2026-09-04 — US-CWP-014 · US-CWP-015",
        rule="BR-CWP-076",
        # ⚠ EMPTIED BY CR-072 ON 2026-09-04 — see the module docstring. The
        # report no longer writes an interruption; a clerk opens one from the
        # staff app when the reports are real. **This write point now writes
        # exactly one row.**
        companions=(),
    ),
    WritePoint(
        kind="meter_reading",
        # ⚠ **AMENDED 2026-10-17 WHEN IT WAS BUILT (`DEF-CWP-10175`).** It read
        # *"meter_reads with source 'portal' and review_state"*, `function=None`
        # and *"blocked on OQ-1393 for straight-through"*. `OQ-1393` closed on
        # 2026-09-04 (`BR-CWP-074`): the reading is ACCEPTED, validated, and
        # flagged — there is no review state, and the source is `customer`, the
        # fourth value, never `portal` and never `manual`.
        lands_in=(
            "meter_reads with source 'customer' (BR-CWP-074's provenance flag), "
            "through Meter Reads' own stage → validate → commit "
            "(apps.metering.customer_reads)"
        ),
        owner="apps.metering",
        function="submit_meter_reading",
        built_in="2026-10-17 — US-CWP-042 · DEF-CWP-10175 (gap E of the PO's meter-reading ruling)",
        rule="BR-CWP-074",
    ),
    WritePoint(
        kind="preference",
        lands_in=(
            "portal_consent — the recorded paperless consent, carrying the version of the\n"
            "words the person saw (BR-CWP-087), and its withdrawal stamp; and the THREE\n"
            "columns on customers.accounts that hold a customer's own choice —\n"
            "paperless (adds email), sms_reminders (adds text) and preferred_language.\n"
            "⚠ THERE IS NO PER-EVENT CUSTOMER PREFERENCE IN THIS PRODUCT (OQ-CWP-1660):\n"
            "notification_rules is the TENANT's row, one per event per tenant."
        ),
        owner="apps.portal · apps.customers",
        # ⚠ **ONE FUNCTION, THREE SHAPES — the same move `raise_service_request`
        # made above, and for the identical reason: G81 allows exactly one
        # public function per kind and a second `def` fails the build by name.
        # Wave C built it as `record_paperless_consent`; wave G renamed it and
        # added `withdraw_paperless` and `delivery_preferences` beside the
        # consent. The consent's BODY is unchanged.
        function="record_preference",
        # ⚠ WHY A CONSENT ROW IS THE `preference` KIND AND NOT A FIFTH ONE.
        # BR-CWP-001 names *"a preference on the account"*, and BR-CWP-087 is
        # that paperless — how a person wants their bills sent — is RECORDED AS
        # A CONSENT rather than as a toggle: *"a timestamp, the wording version,
        # and a way to withdraw — not a toggle."* The row IS the preference;
        # the rule changed its SHAPE, not its kind. It hangs off the service
        # request in release 1 because the one screen that takes it belongs to
        # somebody with no account yet.
        # ⚠ **THIS ROW NAMED `US-CWP-030` FOR THE CONTACT-PREFERENCES HALF AND
        # THAT WAS WRONG (`DEF-CWP-3861`).** `US-CWP-030` is *accept an
        # invitation* (`CWP-021`, `EP-CWP-06`) and is `status: deferred` —
        # `OQ-1396` ruled delegate access out. The preferences grid is
        # `US-CWP-028`'s `CWP-025`, which is what the decision log of
        # 2026-09-04 says in as many words when it separates a contact
        # PREFERENCE from a contact DETAIL.
        built_in="wave C, 2026-09-04 — US-CWP-014 (paperless); wave G, 2026-09-05 — US-CWP-028 (CWP-025: the channel election, the language, and the withdrawal)",
        rule="BR-CWP-087",
    ),
    # ══ THE FIFTH AND SIXTH KINDS, 2026-09-04 — AND THEY ARRIVED BY TWO
    # DIFFERENT ROUTES, WHICH IS WHY BOTH ARE WRITTEN OUT ═══════════════════
    #
    # ⚠ **THE FIFTH IS A PRODUCT OWNER RULING** (`OQ-CWP-1562`), verbatim:
    # *"maria can change her phone number and email ID and it will udpaet our
    # master records also … once you login we ahve to allow them to change the
    # details, otherwise it will not help"*. It is the first thing the portal
    # may CHANGE in the utility's own books — every kind above CREATES.
    #
    # ⚠ **THE SIXTH IS A DEFECT IN OUR OWN EXTRACTION** (`DEF-CWP-3768`), and
    # naming it a change would have converted our mistake into the customer's
    # new requirement (13-change-process step 1). `BR-CWP-009` — *"the set
    # grows only from a customer-to-account link or a delegate grant"* — has
    # been CONFIRMED since the blueprint, and the same blueprint drew
    # `CWP-020`, the add-an-account screen. So the blueprint always specified
    # this write; `BR-CWP-001`'s *"four"* simply failed to count it, and
    # `US-CWP-027` sat blocked on a question that was already answered.
    WritePoint(
        kind="contact_detail",
        lands_in=(
            "customer_contact — the customer's own email, mobile and postal address,\n"
            "on every account this login holds (US-CWP-028 TC-10: one save, four accounts)"
        ),
        owner="apps.customers.portal_self_service",
        function="update_own_contact_details",
        built_in="wave G, 2026-09-04 — US-CWP-028 (my details)",
        rule="BR-CWP-001 (amended) · BR-CWP-103",
        # ⚠ **WHAT IS NOT IN THIS ROW IS THE POINT OF IT.** The legal name and
        # the account holder are NOT contact details (`BR-CWP-026`): they are
        # encrypted identity fields that a deposit carry-forward and a duplicate
        # check are decided on, and a portal that rewrote them would put a money
        # decision behind an unverified form. They are refused with a route into
        # a service request — which is the `service_request` kind above, not
        # this one.
    ),
    WritePoint(
        kind="account_link",
        lands_in=(
            "customer_accounts — one link joining this login's customer to an account\n"
            "whose OWN contact has just answered a one-time code (BR-CWP-033)"
        ),
        owner="apps.customers.portal_self_service",
        function="add_account_to_login",
        built_in="wave G, 2026-09-04 — US-CWP-027 (add another account)",
        rule="BR-CWP-009 · BR-CWP-033",
        # ⚠ **THE CODE GOES TO THE ACCOUNT BEING ADDED, NEVER TO THE PERSON
        # ADDING IT** (`BR-CWP-033`, `US-CWP-027` TC-3). Otherwise anyone
        # holding one account and a stolen bill number collects a second, and
        # this row would be the widest hole in the portal rather than its
        # narrowest write.
        #
        # ⚠ **AND THE LINK IS THE ONLY THING WRITTEN — NOTHING IS COMBINED**
        # (`BR-CWP-015`). Bills, balances and payments stay separate; the set
        # is FLAT (`BR-CWP-013`) and `session.account_set` re-derives it on
        # every request, so this write widens what one person may see and
        # changes not one figure in the books.
    ),
    WritePoint(
        kind="stored_instrument",
        lands_in=(
            "stored_payment_instruments — one saved card or bank mandate per CUSTOMER,\n"
            "a gateway TOKEN with a brand and a last four, never a card number (BR-CWP-057)"
        ),
        owner="apps.payments.instruments",
        #: ⚠ `None`, AND THE REASON IS THE INTERESTING PART. Every other row
        #: here names a function in `apps/portal` or a module that module
        #: publishes. This one lands in `apps.payments`, because a saved card is
        #: payments' row and a portal that wrote it directly would be the
        #: cross-module write B2 §2 forbids. `save_instrument` and
        #: `remove_instrument` live there.
        function=None,
        built_in="phase 5, 2026-09-05 — US-CWP-046 · US-CWP-022 (CWP-039)",
        rule="BR-CWP-057 · BR-CWP-040",
        # ⚠ **THE SEVENTH KIND, AND IT IS NEITHER OF THE TWO IT LOOKS LIKE.**
        # It is not `payment`: that row is money MOVING, and a customer saves a
        # card without paying anything. It is not a companion of `payment`
        # either — this file's own test says a companion has no independent
        # door, and `CWP-039` is a door somebody walks through on its own to
        # add a card, look at one, or take one away.
        #
        # ⚠ **AND G81 WAS GREEN OVER THIS BEFORE THE ROW EXISTED, BY THE
        # GATE'S LETTER.** It refuses ORM writes inside `apps/portal/` and
        # imports of another module's `…services`; the owning module is called
        # `instruments`, so neither rule bit. The lane that built it said so in
        # its own docstrings rather than banking the green — which is the only
        # reason this row is here at all, and is worth more than the row.
    ),
)

KINDS: frozenset[str] = frozenset(point.kind for point in WRITE_POINTS)

#: Files under apps/portal/ that MAY write, besides services.py, and what each
#: may write.
#:
#: ⚠ **THE NAME SAYS `STAFF` AND THE DICT NEVER MEANT ONLY STAFF** — `G81`
#: reads it by that identifier, so it keeps the name and this note corrects the
#: reading (2026-09-04, CR-068 wave C). `sample_data.py` was in it from wave A
#: and is a fixture seeder, not a person; what the dict actually holds is *every
#: file with a declared, narrow write allowance and exactly what each may
#: write*. Three now:
#:
#:   * `settings_service.py` — the BACK OFFICE, a signed-in System Admin on the
#:     utility's own settings row (CR-068 §0 row 18);
#:   * `sample_data.py` — the demo fixture, through the owning modules' services;
#:   * `applications.py` — the applicant's UNSENT DRAFT, which is not one of
#:     BR-CWP-001's four kinds because it is not a record: it holds nothing the
#:     utility has agreed to, carries no reference and changes no account.
#:
#: ⚠ **AND AN ALLOWANCE IN PROSE IS NOT AN ALLOWANCE A GATE CAN READ.** Adding a
#: file here would otherwise let it write ANY model at all, which is the erosion
#: CR-068 §13 describes: *"Nobody ever decides to allow a fifth; a lane just
#: needs one more field."* `MODULE_WRITE_TABLES` below is the machine-readable
#: half, and `G84` refuses a model a file's own row does not name.
STAFF_WRITE_MODULES: dict[str, str] = {
    "settings_service.py": "PortalSettings — the utility's own switches and branding, by a System Admin",
    "sample_data.py": "the demo fixture, through the owning modules' services (never a raw write)",
    "applications.py": "PortalApplicationDraft — the applicant's unsent form, saved from the first keystroke, including the mailing address if different (DEF-CWP-9163: the applicant's own words, held on the draft and turned into an account's kind=mailing row only by the customers module's account-opening door, never written to an account from here); and PortalApplicationDocument — the files attached to it before it is sent, each saying which required document it is (CR-158-BRC10; DEF-CWP-9167)",
    # ── CR-068 wave E, 2026-09-04 · `BR-CWP-102` — A THIRD CLASS OF WRITE ─────
    # ⚠ **THIS IS THE RULE, NOT A CONVENIENCE, AND IT IS WRITTEN DOWN IN
    # `02-business-rules.md` AS `BR-CWP-102` BEFORE IT WAS BUILT ON.**
    #
    # `BR-CWP-001`'s four kinds are about the UTILITY'S RECORDS — a payment, a
    # service request, a meter reading, a preference on an account — and not one
    # of them describes *who is allowed to look*. A credential and a session are
    # the portal's own authentication material: they change no balance, no bill,
    # no reading and no preference, and deleting every row in these tables would
    # cost nothing but a round of password resets.
    #
    # **THE TEST A FUTURE LANE APPLIES: a file here writes a row the PORTAL
    # ITSELF OWNS, and never a row in the utility's book.** The day that fails —
    # a file here writing an `Account`, an `Invoice`, a `Payment` or a
    # `MeterRead` — it is a fifth write point wearing a different coat, and that
    # is a ruling and not an edit. `MODULE_WRITE_TABLES` below is what makes
    # that visible rather than arguable: each file names the models it may
    # write, and only those.
    #
    # ⚠ **THE DICT'S NAME IS NOW WRONG AND IS NOT RENAMED.** Two of its five
    # entries are not staff writes (`applications.py` has not been one since
    # wave C). The string is read by G81 and by G84; renaming it is a mass
    # shared-file edit for no behaviour (law 11), so the MEANING is written here.
    #
    # ⚠ **AND THESE TWO LINES WERE REVERTED ONCE ALREADY** — landed at
    # `5cb4d970`, removed by a whole-file pathspec commit at `5bfc2492` from a
    # base that predated them, which took `G81` red for the whole branch
    # (`DEF-CWP-3754`). Law 11's mechanism two, and the reason this file is
    # re-derived from the tip rather than copied.
    "credentials.py": "PortalCredential + PortalOneTimeCode — 🔒 the customer's own password and the one-time code that proves it is them (BR-CWP-029/033/102)",
    "session.py": "PortalSession — 🔒 who is signed in, and the flat account set every query is filtered on (BR-CWP-008/009/013/102)",
    # CR-189-BRC10 (PO 2026-10-22) — the locked-out customer's email change.
    # The same two portal-owned 🔒 rows `credentials.py` writes: a code row's
    # hash bound to the new address, and the login's `email` once a code to
    # that address is confirmed. The customer's CONTACT row moves through the
    # `contact_detail` write point (`services.update_own_contact_details`).
    "email_update.py": "PortalCredential + PortalOneTimeCode — 🔒 the login's email after both codes are proved, and the code row bound to the new address (BR-CWP-102, CR-189-BRC10)",
    # ── 2026-10-02 · PO RULING (option A) — A DELETE, AND ONLY A DELETE ──────
    # PO, verbatim: *"A · Delete it 30 days after her last visit. Her draft and
    # the photo are deleted on 31 October, and the deletion is logged. If she
    # returns on 20 October, the 30 days start again."* This file is the
    # nightly job that does it. It writes the SAME two portal-owned rows
    # `applications.py` writes — the applicant's unsent form and the files on
    # it — and it only ever DELETES them: an unsent draft (`submitted_at` IS
    # NULL) last visited 30+ days ago, with its held files, one audit row each.
    # It never touches a sent application, never the document store, and never
    # a row in the utility's book — the test above for this dict, passed.
    "draft_cleanup.py": "PortalApplicationDraft + PortalApplicationDocument — DELETE only: an unsent application and its held files, 30 days after the applicant's last visit (PO ruling 2026-10-02)",
}

#: file under apps/portal/ → the model class names it may write, and NO OTHER.
#: Read by `10-scripts/gates/g84_module_write_tables.py` with `ast`; never
#: imported by the product.
#:
#: `services.py` is here too, and deliberately: it is the file G81 lets write
#: freely, so it is the file where a stray `SomethingElse.objects.create(...)`
#: would be least visible. Its allowance is the portal-owned row the four write
#: points land in — everything else it writes goes through the owning module's
#: own named door (`create_from_portal`), which is a call and not an ORM write.
#: ⚠ `create_interruption` was named here too until CR-072; the portal does not
#: call it any more, and it is now role-gated so it could not.
MODULE_WRITE_TABLES: dict[str, tuple[str, ...]] = {
    "services.py": ("PortalConsent",),
    "settings_service.py": ("PortalSettings",),
    # ⚠ **`PortalApplicationDocument` JOINED THIS ROW ON 2026-10-01, AND IT IS
    # A RULING, NOT A LANE NEEDING ONE MORE FIELD** — PO, verbatim: *"you need
    # to allow customer to upload documents and save those document to server
    # for that Utility"* (`CR-158-BRC10`; `DF-4` superseded for the new-service
    # request ONLY). It is the SAME kind of row the draft is — the applicant's
    # own unsent form, holding nothing the utility has agreed to, readable only
    # through the draft's token — so it is the same file's allowance and NOT a
    # new write point: `BR-CWP-001`'s kinds do not move. The file becomes a
    # service request's document only at submit, through
    # `customers.service_request_documents.attach_from_portal` (a call, never an
    # ORM write from here), and the held copy is deleted in the same transaction.
    "applications.py": ("PortalApplicationDraft", "PortalApplicationDocument"),
    # PO ruling 2026-10-02 — the nightly clean-up. DELETE only, of exactly the
    # two models above, and only an UNSENT draft 30+ days past its last visit;
    # `STAFF_WRITE_MODULES["draft_cleanup.py"]` carries the ruling verbatim.
    # ⚠ G84 matches `<Model>.objects.<write>(…)` and this file deletes through
    # `.objects.filter(…).delete()`, which G84 does not see — G81 does (it
    # flags any `.delete()` outside a listed file), so the row is here for G84's
    # clause 1 (every listed writer is bounded) and as the record of what it may
    # touch, not because G84 could catch a stray write in it.
    "draft_cleanup.py": ("PortalApplicationDraft", "PortalApplicationDocument"),
    # The fixture seeder writes through other modules' services by rule
    # (BR-TEN-013 / the prime directive: no raw INSERT, no RLS bypass), so it
    # writes no model of its own and this empty tuple says so rather than
    # leaving the file unlisted, which would read as "not checked".
    "sample_data.py": (),
    # CR-068 wave E — 🔒, and `BR-CWP-102` is the rule. Each names exactly what
    # it may write and nothing else, so a stray `Account.objects.create(...)` in
    # the file that holds the portal's authentication is a red gate rather than
    # a code review.
    "credentials.py": ("PortalCredential", "PortalOneTimeCode"),
    "session.py": ("PortalSession",),
    "email_update.py": ("PortalCredential", "PortalOneTimeCode"),  # CR-189-BRC10
}
