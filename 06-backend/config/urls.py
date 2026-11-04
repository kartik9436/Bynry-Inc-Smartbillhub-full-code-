"""Root URLconf — the two-part route map the PO's 2026-08-10 path-tenancy
ruling fixes (12-governance/02-decision-log.md, Eng-Lead contract so FE and BE
cannot diverge):

    /api/{tenant}/…   every tenant-scoped endpoint
    /api/…            the surface that carries NO tenant:
                        public/…                onboarding reads (11b §2.1)
                        tenants                 provisioning (S114)
                        jobs/{id}               BE-07 poll (B12 r1)
                        exports, exports/{id}/file   US-SHL-008 + IS-11

Order matters: the no-tenant routes are registered FIRST so a tenant slug can
never shadow them. Belt and braces, `core.tenancy.NON_TENANT_SEGMENTS` refuses
to read those same first segments as a tenant, and
`apps.tenancy.selectors.RESERVED_SUBDOMAINS` refuses to mint a tenant named
after one (test_be01_tc16 keeps the three in step).

API routes register per-app as modules are built (contract:
04-docs/01-spec/11-api-contracts.md).
"""

from django.urls import include, path, re_path

from apps.tenancy.api import export_file, job_status, list_export
from apps.tenancy.api import public_urlpatterns as tenancy_public_urlpatterns
from apps.integrations.platform_api import hook_urlpatterns as twilio_hook_urlpatterns
from apps.tenancy.published_content_api import (
    guest_urlpatterns as published_content_guest_urlpatterns,
)

# ── /api/{tenant}/… — the tenant-scoped API ────────────────────────────────
tenant_urlpatterns: list = [
    path("", include("apps.identity.urls")),  # EP-IDN-01..04 (2026-08-09)
    path("", include("apps.tenancy.api")),  # EP-TEN-03/05..08 (2026-08-09)
    # US-SHL-013 · DEF-647 (2026-08-24) — GET|PUT /user-preferences/{key}.
    # **THE SEVENTH TIME HARD-WON LAW 2 IS RECORDED IN THIS FILE, and the first
    # time a customer reported it as the symptom rather than an engineer finding
    # it as a gap.** The column chooser on every list in the product — accounts,
    # premises, assets, reads, invoices, payments — reset to defaults the moment
    # the component remounted, because `tenancy.UserPreference`, its migration,
    # its RLS policy, `tableTypes.ts`'s `screenId` field and DataTable's pure
    # `toggleColumnVisible` (which returns "exactly the value the consumer
    # persists") were ALL built, and no route and no caller existed between
    # them. The PO's words: *"it save temaprarily … it reset to deault"*.
    #
    # ORDER IS SAFE and was checked rather than assumed. Django resolves by URL
    # and NOT by method, so a duplicate path SHADOWS rather than merges:
    # `user-preferences/<key>` is claimed by no other include in this list
    # (`grep -rn "user-preferences" apps/` finds only this module), it shares no
    # first segment with tenancy's own `settings/…`/`lookups/…` families above,
    # and it is not a prefix of anything (Django matches whole segments).
    # tests/test_us_shl_013_user_preferences.py resolves both verbs through THIS
    # file and then calls them over the wired stack, so a future lane cannot
    # lose the include silently — which is the failure mode this row IS.
    path("", include("apps.tenancy.preferences_api")),
    # CR-035 (PO 2026-08-26) — POST/GET /wizard-parks, GET/PATCH/DELETE
    # /wizard-parks/{id}: the store behind `Park` on the five wizards that
    # carry the control and have had nowhere to park to (DEF-746).
    # **THE EIGHTH TIME HARD-WON LAW 2 IS RECORDED IN THIS FILE, and this time
    # the two halves were built on two different DAYS by two different lanes.**
    # The park panel, its nine reasons, the note and the reminder date have
    # been wired into every wizard since 2026-08-24 — `wizardParkPort()`
    # returns `null` and its own docstring says *"Returning a port here is the
    # whole switch"* — and the table plus its RLS policy landed this morning as
    # CR-035 part 1. Neither half moves a clerk one inch without this line.
    #
    # ORDER IS SAFE and was checked rather than assumed. Django resolves by URL
    # and NOT by method, so a duplicate path SHADOWS rather than merges.
    # `wizard-parks` is claimed by no other include in this list
    # (`grep -rn "wizard-parks" apps/` finds only tenancy's own module), it
    # shares no first segment with tenancy's `settings/…`, `lookups/…` or
    # `user-preferences/…` families, and Django matches whole segments so it is
    # not a prefix of anything. tests/test_cr035_wizard_parks.py resolves all
    # five verbs through THIS file and then calls them over the wired stack, so
    # a future lane cannot lose the include silently.
    path("", include("apps.tenancy.wizard_parks_api")),
    # US-SHL-003 · DEF-2423 (2026-09-03) — `GET /search?q=`, the ONE endpoint
    # behind the topbar box that is on every authenticated screen. **THE NINTH
    # TIME HARD-WON LAW 2 IS RECORDED IN THIS FILE, and this one was known and
    # deliberate rather than missed**: `core/search.py` (the BE-08 kernel, with
    # 12 passing tests), `AppShell.tsx`'s `onSearch` prop, its debouncer and its
    # ✕ have all existed since the shell was built, and NO ROUTE JOINED THEM.
    # `check_unwired_props.py` exempted the prop by name so G13 would pass on
    # purpose, and the box was made to state its own absence. The PO's words on
    # the running product: *"Can you enable universal search ?"*. This line is
    # the join; the exemption goes with it in the same commit.
    #
    # ORDER IS SAFE and was checked rather than assumed. Django resolves by URL
    # and NOT by method, so a duplicate path SHADOWS rather than merges.
    # `search` is claimed by no other include in this list (`grep -rn
    # '"search"' apps/*/api.py` and the urlpatterns of every module above find
    # nothing), it shares no first segment with tenancy's `settings/…` or
    # `lookups/…` families, and Django matches WHOLE segments so it is not a
    # prefix of anything. tests/test_us_shl_003_search.py resolves the route
    # through THIS file and calls it over the wired stack, so a future lane
    # cannot lose the include silently — which is the failure mode this row IS.
    path("", include("apps.tenancy.search_api")),
    path("", include("apps.rating.api")),  # EP-RAT-01..04 (2026-08-09)
    path("", include("apps.metering.api")),  # EP-MET-01/02 (2026-08-09)
    # CR-070 wave A (2026-09-03) — `GET /work-orders`, the Work shell's Orders
    # tab (US-WRK-004). Two segments exactly; metering's `work-orders/<uuid>/…`
    # routes above are three and cannot swallow it. tests/test_us_wrk_004_
    # orders_list.py resolves the path through THIS file, so a future lane
    # cannot lose the include silently.
    path("", include("apps.work.api")),
    path("", include("apps.assets.api")),  # EP-AST-01..04 (2026-08-09)
    path("", include("apps.audit.api")),  # EP-AUD-02 · 11b §2.13 (2026-08-09)
    path("", include("apps.customers.api")),  # EP-CUS-01/02 · 11b §2.6 (2026-08-10)
    # CR-031 (PO 2026-08-24) — REQ-01 the Requests list, REQ-02 the request
    # detail, REQ-03.1..6 the six-step capture, and the BR-CUS-095 settings
    # checklist. **THE SIXTH TIME HARD-WON LAW 2 IS RECORDED IN THIS FILE.**
    # `apps/customers/service_request*.py` landed the same morning as ~2,700
    # lines over five tables and eleven states — RLS, audit, idempotent
    # numbering, a full read model for three screens — and **no route named any
    # of it**, so a clerk could not raise a service request and the whole W4
    # frontend had nothing to call. Its own lane report said so: *"no endpoints
    # exist yet — config/urls.py and openapi/schema.json were outside the lane's
    # scope"*. Built is not wired.
    #
    # ORDER IS SAFE and was checked rather than assumed. Django resolves by URL
    # and NOT by method, so a duplicate path SHADOWS rather than merges.
    # `service-requests…` and `service-request-settings…` are claimed by nothing
    # else in this list — they are different literals from each other (Django
    # matches whole path SEGMENTS, so neither is a prefix of the other) and
    # customers' own `accounts/…` family above shares no first segment with
    # either. Inside the include, the all-static `service-requests/categories`
    # is declared ABOVE `service-requests/<request_id>` or the word would
    # resolve as a request id.
    #
    # Registered AFTER `apps.customers.api` so the owning module's older routes
    # are always matched first, the same rule payments follows below.
    # tests/test_cr031_service_request_api.py resolves every one of these paths
    # through THIS file and then calls them over the wired stack, so a future
    # lane cannot lose the include silently.
    path("", include("apps.customers.service_request_api")),
    # CR-183-BRC10 (2026-10-14) — the temporary stop's staff doors: approve the
    # portal ask, start / move / end a hold from the account page. Four paths,
    # none shadowing an older one (`…/temporary-stop` is a new last segment).
    path("", include("apps.customers.temporary_stop_api")),
    # CR-190-BRC10 (2026-10-22) — click-to-accept agreements: the staff doors
    # (`accounts/{id}/agreements…`, new last segments) and the link's public
    # edge (`agreements/public/{token}…`, a first segment nothing else claims).
    path("", include("apps.customers.agreements_api")),
    path("", include("apps.customers.agreement_public_api")),
    # DEF-BIL-10531 (2026-10-22) — the bill email's direct PDF link: two POSTs
    # (`bill-links/open`, `bill-links/document`), a first segment nothing else
    # claims; the secret travels in the body, never the address.
    path("", include("apps.billing.bill_link_public_api")),
    # DEF-2030 · DEF-2031 (2026-08-28) — TRF-02's five writes and DSC-02's
    # eleven ladder acts. **THE EIGHTH AND NINTH TIME HARD-WON LAW 2 IS RECORDED
    # IN THIS FILE.** G52 measured it: 1,838 lines of built, tested, role-gated
    # write behind no door, and 18 of the 29 offenders were these two files.
    # `customers/api.py` mounted `path("transfers", …)` and `path("disconnects",
    # …)` — two LISTS — so a clerk could see both queues and act on neither row.
    # Both wizards were already built and already mounted in `App.tsx`, posting
    # to addresses that 404'd.
    # tests/test_def2030_2031_wizard_doors.py resolves every one of these paths
    # through THIS file, so a future lane cannot lose the include silently.
    path("", include("apps.customers.transfer_disconnect_api")),
    # CR-125-BRC07 (2026-09-20) — `GET /disconnects/{ref}`, the DISCONNECT CASE
    # RECORD (blueprint p143, whose own red banner reads *"TODAY: no disconnect
    # case page exists"*). Its own module for the reason the three above give.
    # ⚠ **DECLARED AFTER `transfer_disconnect_api` AND THAT IS LOAD-BEARING:**
    # that module mounts `disconnects/schedule`, and Django resolves the FIRST
    # match and stops — so `disconnects/<str:ref>` above it would swallow the
    # schedule POST and read the word "schedule" as a case number. It is
    # `accounts/master`'s trap and DEF-520's.
    # tests/test_disconnect_record_page.py resolves BOTH paths through THIS
    # file, so a future lane cannot reorder or lose the include silently.
    path("", include("apps.customers.disconnect_record")),
    # `S148` — PUT SERVICE BACK ON (PO drawings 2026-09-25, `DEF-CUS-6743`).
    # Its own module for the reason the four above give, and declared AFTER the
    # record for the same reason the record is declared after
    # `transfer_disconnect_api`: `disconnects/<str:ref>` cannot match a
    # two-segment path, so the order is belt and braces rather than load-bearing
    # here — but a lane reordering these has to think about it either way.
    # `tests/test_reconnect_read.py` resolves both of its paths through THIS
    # file, so the include cannot be lost silently.
    path("", include("apps.customers.reconnect_read")),
    # CR-094-BRC01 wave K (2026-09-12) — `ACC-S16`, the Communication dialog on
    # an account. Its own module for the reason the two above give: `api.py` is
    # the file three lanes hold at once, and a pathspec commit naming it
    # publishes whatever else is sitting in it (law 11, mechanism five).
    # ⚠ There is ONE endpoint here and it is the WRITE. *"What has already gone
    # out"* is `GET /outbound` with `f.account_id` — notifications' own queue
    # list, already paginated, already sorted failed-first — and a second list
    # over that table would be the duplicate the PO's standing instruction
    # forbids.
    # tests/test_cr094_k_account_communication.py resolves this path through
    # THIS file, so a future lane cannot lose the include silently.
    path("", include("apps.customers.communication_api")),
    # CR-171-BRC10 P1.12 / P1.16 (2026-10-05) — the move-in's Fees table and
    # its narrowed *See full rates*: three READS, their own module for the
    # reason above. tests/test_cr171_p1_16_move_in_pricing.py resolves each path.
    path("", include("apps.customers.move_in_money_api")),
    # CR-171-BRC10 P2.25 (lane MVI-WIZ-CUST) — the wizard's documents: stage a
    # file before the account exists, open it, read the move-in checklist.
    # tests/test_cr171_p225_move_in_documents.py calls each view.
    path("", include("apps.customers.move_in_documents_api")),
    # `DEF-CUS-5949`'s sibling gap (2026-09-20) — `GET /transfers/{ref}`, the
    # TRANSFER RECORD (blueprint p133). A clerk could make a property sale and
    # had no way to read it back; the screen has existed for days and drew its
    # NOT-FOUND branch at every address because nothing answered.
    #
    # ⛔ **IT IS REGISTERED LAST OF THE `transfers/…` FAMILY AND THE ORDER IS
    # THE WHOLE REASON IT IS A MODULE OF ITS OWN.** Its one route is
    # `transfers/<str:ref>`, which matches `commit` and `buyer-preview` as
    # happily as it matches `TRF-26-0001` — and Django resolves by PATH and not
    # by method, so a duplicate SHADOWS rather than merges (this file says so
    # forty lines up). Declared inside `apps.customers.api`, which is included
    # ABOVE, it would have swallowed `POST /transfers/commit` and answered 405
    # to every property sale in the product. `transfer_disconnect_api.py`
    # predicted exactly this in a comment above its own list: *"the next lane to
    # add `transfers/<id>` would create that collision silently."*
    #
    # So: after `transfer_disconnect_api`, whose literal segments must match
    # first, and the module holds the argument in full.
    # tests/test_transfer_scenarios.py resolves `transfers/TRF-...` through the
    # real router, so a future lane cannot lose this include silently.
    path("", include("apps.customers.transfer_record_api")),
    # CR-171-BRC10 lane MVI-FLOW — the move-in details view's WRITE doors,
    # `moves/<ref>/cancel`, `/cancel-preview`, `/move-in-date`,
    # `/opening-reads`, `/work-orders`. Two segments under `moves/<ref>`, so
    # they cannot shadow `GET /moves/{ref}` (`apps.customers.api`, above);
    # a module of its own for `communication_api`'s reason (shared `api.py`).
    # tests/test_cr171_mvi_flow_record_doors.py resolves each through here.
    path("", include("apps.customers.move_in_flow_api")),
    # EP-BIL-07 · 11b §2.8 (2026-08-11) — GET /invoices + GET /invoices/{id}.
    # This one line is the whole defect: S30's list, S30's detail and the S21
    # Bills tab shipped calling these paths while `apps/billing/api.py` was a
    # one-line docstring and no include named it, so every one of them rendered
    # a 404 failure state. Built is not wired (hard-won law 2), and
    # tests/test_us_bil_025_026_bills_read.py resolves both paths through THIS
    # file so a future lane cannot lose the include silently.
    # Bulk bill run redesign, plan A2 (2026-09-30) — `billing/runs/scope-preview`.
    # ⚠ BEFORE `apps.billing.api`, AND IT MUST STAY BEFORE IT: that module's
    # `billing/runs/<str:run_id>` would otherwise swallow `scope-preview` as a
    # run id and answer *not found*. Django resolves by URL, first match wins.
    # tests/test_bulk_run_scope.py resolves the path through THIS file.
    path("", include("apps.billing.run_scope_api")),
    path("", include("apps.billing.api")),
    # EP-BIL-04 · EP-BIL-05 · EP-BIL-06 (2026-08-16) — the FOUR unreachable
    # halves of the biggest module in the product. `10-scripts/gates/
    # surface_debt.txt` read `billing 17`: **27,908 lines of engine behind three
    # screens**, the worst ratio anywhere. Each of these includes closes one
    # family that was complete, golden-verified and reachable only from a test:
    #
    #   corrections_api  — 170KB across five modules (corrections ·
    #     bulk_corrections · single_correction · document_correction ·
    #     correction_models), every one carrying `D=deferred(no-API-half — the
    #     S30 correction endpoints are unbuilt)`. A utility that overbilled a
    #     customer $19.92 had, in a product with a complete correction engine,
    #     NO WAY TO FIX IT.
    #   budget_api       — `budget_service.enroll` had no caller outside tests,
    #     so no human could put one customer on budget billing.
    #   documents_api    — `documents.render_invoice` produces the bill as HTML
    #     and as a printable page, `issue.py` calls it on every bill to satisfy
    #     BR-BIL-033 and THROWS THE RESULT AWAY. Its own DOCUMENT_UNAVAILABLE
    #     said `GET /invoices/{id}/document` was unmounted "so no human can open
    #     one either (hard-won law 2)". This is that route.
    #   templates_api    — S8's bill-layout chooser (PO ruling 2026-08-16, which
    #     CUT the S91–S96 designers and replaced them with a library of five).
    #
    # ORDER IS SAFE and was checked rather than assumed. Django resolves by URL
    # and NOT by method, so a duplicate path SHADOWS rather than merges. The two
    # new `invoices/…` patterns are THREE segments deep (`invoices/<id>/document`,
    # `/document.pdf`, `/chain`) and `apps.billing.api` above declares only
    # `invoices` and `invoices/<id>`, so nothing is shadowed in either direction.
    # `corrections…`, `budget-billing…` and `bill-templates…` are claimed by no
    # other module. tests/test_us_bil_surface_apis.py resolves every one of these
    # paths through THIS file and then calls them over the wired stack, so a
    # future lane cannot lose an include silently.
    path("", include("apps.billing.corrections_api")),
    path("", include("apps.billing.budget_api")),
    path("", include("apps.billing.documents_api")),
    path("", include("apps.billing.templates_api")),
    # DEF-BIL-4458 — `bill-templates/layouts/<key>/preview.pdf`, the route that
    # lets a System Admin SEE a layout before choosing it. Four segments deep
    # and PLURAL, so it cannot collide with `templates_api`'s all-static
    # `bill-templates/layout` (the POST that chooses); a `<str:…>` directly
    # under `bill-templates/` would have swallowed that one, which is why the
    # segment is `layouts`. Its own module header records the check.
    path("", include("apps.billing.layout_preview_api")),
    # CR-053 task 13 — `billing/print-sets`, the print hand-over (BR-NOT-029,
    # PO 2026-08-30: *"Im okay with this"*). A separate `urlpatterns` for the
    # same reason the four above are: `apps/billing/api.py` is the busiest file
    # in the module and three lanes have been in it this week. The path segment
    # `print-sets` is claimed by no other module, and it carries no `<id>`, so
    # it cannot shadow or be shadowed by anything already declared.
    #
    # ⚠ **THE ARCHIVE ITSELF IS NOT SERVED FROM HERE.** It is downloaded through
    # the platform's own `GET /api/exports/{job_id}/file`, which streams a
    # FINISHED FILE and touches no database — see `apps/billing/print_set.py` on
    # why that is the answer to DEF-2734 rather than a guarded stream.
    path("", include("apps.billing.print_api")),
    # CR-059 CS-37 / task 27 (2026-09-02) — GET /accounts/{id}/credit-notes.
    # THE DIRECT ANSWER TO A QUESTION THAT HAD NONE: to find every credit note a
    # customer had ever been given, somebody had to open each of their bills one
    # at a time and read the panel on each. There was no list, no filter, no
    # account tab and no report — and `ix_credit_notes_account`, the index built
    # on (tenant, account) for exactly that lookup, had never had a query run
    # against it. A separate `urlpatterns` for the same reason the four billing
    # includes above are separate: `apps/billing/api.py` is the busiest file in
    # the module and several lanes are in it this week (hard-won law 11).
    #
    # ORDER IS SAFE AND WAS CHECKED RATHER THAN ASSUMED. Django resolves by URL
    # and NOT by method, so a duplicate path SHADOWS rather than merges. The
    # pattern is `accounts/<id>/credit-notes`, THREE segments, and
    # `apps.customers.api` above — which owns the `accounts/…` family — declares
    # no three-segment `accounts/<id>/credit-notes` pattern of any kind. This is
    # registered AFTER customers, the same ordering `apps.payments.api`'s
    # `accounts/<id>/payments` already relies on, so the owning module's routes
    # are matched first. `credit-notes` is claimed by no other include in this
    # list. tests/test_cr059_cs37_credit_note_identity.py resolves the path
    # through THIS file and then calls it, so a future lane cannot lose the
    # include silently.
    path("", include("apps.billing.credit_notes_api")),
    # CR-139-BRC07 `P5.8` (2026-09-23) — POST /billing/remittance/parse, the
    # ONE place the Code 39 remittance grammar lives. The Scan paper source on
    # 4·3a sends the characters a wedge scanner typed and gets back the three
    # fields, or a sentence saying which of the four ways the scan failed.
    #
    # A separate `urlpatterns` for the same reason every billing include above
    # is separate: `apps/billing/api.py` is the busiest file in the module and
    # several lanes are in it (hard-won law 11). The pattern is
    # `billing/remittance/parse`, THREE literal segments, claimed by nothing —
    # Django resolves by URL and not by method, so a duplicate would SHADOW
    # rather than merge, and there is none.
    path("", include("apps.billing.remittance_api")),
    # `CR-094-BRC01` wave M — `POST /accounts/{id}/statement`, the ✉ quick
    # action that had refused since the account rail was drawn. **It QUEUES a
    # statement; nothing in this product sends** (BR-NOT-005 / BR-NOT-013).
    #
    # It is BILLING's for the reason `catalogs.py` and `seed_templates.py` both
    # already state: *"Bills and statements are BILLING's registry (B2 r10
    # #4)"*, and `S91`–`S93` are named there as bill residential / bill
    # commercial / statement, owned by billing. The `accounts/` prefix is URL
    # grammar and not an ownership claim — the include directly above relies on
    # exactly that reading.
    #
    # ORDER CHECKED, NOT ASSUMED, the same way the row above checks it. The
    # pattern is `accounts/<id>/statement`, THREE segments; `apps.customers.api`
    # — which owns the `accounts/…` family — declares no three-segment
    # `accounts/<id>/statement` of any kind, and `statement` is claimed by no
    # other include in this list (`finance/deposits/statement` and
    # `reports/customer-statement` are different paths in different families).
    # Registered AFTER customers, so the owning module's routes match first.
    # tests/test_cr094_m_send_statement.py resolves the path through THIS file
    # and then calls it, so a future lane cannot lose the include silently.
    path("", include("apps.billing.statement_api")),
    # EP-PAY-01 · 11b §1 (S22 payload regenerated) + §2.9 (2026-08-11) —
    # POST /accounts/{id}/payments + GET /payments. The same one-line defect as
    # the row above, one module along: the payments WRITE PATH landed complete
    # and tested on 2026-08-11 — a payment could be recorded, allocated across
    # open bills and posted to the books — while `apps/payments/api.py` was a
    # one-line docstring and no include named it, so no human being could
    # record a payment at all. Built is not wired (hard-won law 2), and
    # tests/test_us_pay_004_payments_api.py resolves BOTH paths through THIS
    # file and then calls them over real HTTP, so a future lane cannot lose the
    # include silently.
    #
    # ORDER MATTERS HERE in a way it did not for billing: this include also
    # registers `accounts/<str:account_id>/payments`, and `apps.customers.api`
    # above owns the `accounts/…` family. The two never collide (customers
    # declares no three-segment `accounts/<id>/payments` pattern), and payments
    # is registered AFTER customers so the owning module's routes are always
    # matched first.
    path("", include("apps.payments.api")),
    # DEF-2032 (2026-08-28) — money going OUT had no door. `approve_refund` and
    # `void_refund` are Admin-gated under BR-PAY-014 and the only refund route
    # in the tree was `accounts/{id}/refund` in customers, which reaches
    # neither. `GET /refunds` comes with them because no route in this product
    # listed a refund id, so the two writes were unreachable by construction —
    # DEF-100's mechanism one table over.
    path("", include("apps.payments.refunds_api")),
    # CR-059 CS-5 / task 15 (2026-09-01) — POST /payments/{id}/reverse. THE SAME
    # ONE-LINE DEFECT AS THE ROW ABOVE, on the highest-value gap in the module:
    # `apps/payments/reversal.py` has been complete and tested since 2026-08-11
    # — it writes the reversing row, reverses every allocation so the bills
    # re-open AT THEIR ORIGINAL DUE DATES, hands the ledger its mirror, counts
    # the NSF, releases the deposit register and queues the customer's letter —
    # and **twenty-one live payment endpoints reached none of it.** A returned
    # cheque, which is a routine weekly event, was a support call and a
    # hand-written journal entry. Built is not wired (hard-won law 2).
    #
    # ORDER IS SAFE AND WAS CHECKED RATHER THAN ASSUMED: the pattern is
    # `payments/<id>/reverse`, three segments, and `apps.payments.api` above
    # declares only `payments` and `payments/summary`. No pattern in this list
    # is a prefix of it. tests/test_cr059_cs5_reverse_door.py resolves the path
    # through THIS file and then calls it, so a future lane cannot lose the
    # include silently.
    path("", include("apps.payments.reversal_api")),
    # CR-059 CS-34 / task 41 (2026-09-02) — POST /payments/{id}/correct-reference.
    # A NAMED verb and DELIBERATELY NOT A PATCH, in the CR's own words: *"The
    # rule that there is no edit verb on a payment path is load-bearing and
    # should stay absolute — a route that accepts a partial body invites the next
    # field to be added to it."* So this adds no PATCH, PUT or DELETE anywhere on
    # `payments`, and what may be corrected is visible in the route name.
    #
    # ⚠ ITS WRITE IS STUBBED ON AN OPEN QUESTION and its refusals are not: a body
    # carrying an amount, an account or a date is refused with that field named,
    # and the tender is refused once the payment has been banked. See
    # `apps/payments/amendments.py` for why the write waits — "the reference and
    # memo may be amended" collides with hard rule 4, which CR-059 §2 does not
    # list among the statements this CR reverses.
    #
    # ORDER IS SAFE AND WAS CHECKED RATHER THAN ASSUMED: the pattern is
    # `payments/<id>/correct-reference`, three segments; `apps.payments.api`
    # declares only `payments` and `payments/summary`, and `reversal_api` above
    # declares `payments/<id>/reverse`, a different whole pattern. Django matches
    # whole patterns, not prefixes, so nothing shadows anything in either
    # direction. tests/test_cr059_cs34_amend_reference.py resolves the path
    # through THIS file and then calls it, so a future lane cannot lose the
    # include silently.
    path("", include("apps.payments.amendments_api")),
    # CR-059 CS-25 / task 62 + CS-26 / task 64 (2026-09-01) —
    # POST /write-offs/{id}/reject · POST /write-offs/{id}/reverse ·
    # GET /bad-debt · GET /bad-debt/accounts. An approver could only approve a
    # write-off or ignore it, so the Finance queue filled with requests nobody
    # would ever action; and once approved, receivables were permanently reduced
    # with **no path back at all** — while the append-only rule beside it says in
    # terms that an erroneous write-off is corrected by a NEW ROW. The bad-debt
    # report is the third verb `BR-PAY-020` has always named (*"payments owns the
    # transaction record, ledger posts, FINANCE REPORTS"*) and nothing assembled
    # it.
    #
    # ORDER IS SAFE AND WAS CHECKED RATHER THAN ASSUMED: the write-off patterns
    # are `write-offs/<id>/reject` and `…/reverse`, three segments, and
    # `apps.payments.api` above declares only `write-offs` and
    # `write-offs/<id>/approve`. `bad-debt` and `bad-debt/accounts` are claimed
    # by no include in this list, and the STATIC `accounts` segment is declared
    # first inside the module so it is matched before anything else.
    # tests/test_cr059_cs25_write_off_states.py resolves all four paths through
    # THIS file and then calls them, so a future lane cannot lose the include
    # silently.
    path("", include("apps.payments.writeoffs_api")),
    # CR-138-BRC07 · P4.13 (2026-09-23) — POST /collections/notices. THE SAME
    # `G25` SHAPE AS THE FOUR ABOVE: `notices.send_reminders`,
    # `send_disconnect_notices` and `ladder.step_one` have been complete,
    # tested and 🔒 HUMAN-REVIEW-PENDING since 2026-08-11 and 2026-09-07, and
    # **no route named any of them** — so S34's *Send a reminder* and *Send a
    # disconnection notice* have rendered DISABLED since the screen shipped,
    # naming this address in their own refusal.
    #
    # ORDER IS SAFE AND WAS CHECKED RATHER THAN ASSUMED. Line 544 below already
    # records the ownership — *"payments owns `collections/notices`"* — written
    # when `apps.notifications.api` was mounted and deliberately did NOT mint
    # this door, because deciding where an account stands on a ladder it does
    # not own is the prime directive's exact prohibition. `apps.payments.api`
    # declares `collections/run` and `collections/ladder`; this is a third
    # literal two-segment path and can shadow neither.
    path("", include("apps.payments.notices_api")),
    # CR-138-BRC07 · P4.3 (2026-09-23) — GET /debtors/{account_id}, the
    # drill-down 7·1 has never had. ⚠ ITS CONSUMER IS `P4.8`, WHICH IS HELD TO
    # WAVE 2 — said here as well as in the module, because a read nothing calls
    # is hard-won law 2's dead UI facing backwards. `debtors` is a literal
    # claimed by nothing else in this file and no `<str:…>` catch-all sits above
    # it that could read the word as somebody's id.
    path("", include("apps.payments.debtor_api")),
    # DEF-PAY-6342 (2026-09-23) — GET /returned-mail + POST /returned-mail/clear:
    # BR-PAY-018's needs-attention list and the clear step, which were built
    # functions with no route. `returned-mail` is a literal claimed by nothing
    # else in this file and no `<str:…>` catch-all above it can read it as an id.
    path("", include("apps.payments.returned_mail_api")),
    # CR-059 CS-12 / task 49 + CS-27 / task 51 (2026-09-03) — ONE CHEQUE THAT
    # PAYS SEVERAL ACCOUNTS. GET /customers/{id}/open-bills ·
    # POST /customers/{id}/payments · GET /accounts/{id}/premises-position ·
    # POST /accounts/{id}/premises-payments.
    #
    # A customer with three properties hands over one cheque and today the clerk
    # records three payments, splits the money on paper and gets THREE RECEIPTS
    # FOR ONE CHEQUE, with nothing checking the split adds up. The premises pair
    # is the sub-metering case CS-27 calls this product's core market: a landlord
    # paying a block, which was four hand-typed payments on four strangers'
    # accounts with a landlord's overpayment landing as a TENANT's credit.
    #
    # ORDER IS SAFE AND WAS CHECKED RATHER THAN ASSUMED, in both directions:
    # `customers/<id>/open-bills` and `customers/<id>/payments` are THREE
    # segments and `apps.customers.api` (registered above) declares `customers`
    # and `customers/<str:customer_id>` — one and two. Django matches whole
    # patterns, not prefixes, so the two-segment pattern cannot swallow a
    # three-segment one however this list is ordered; it is the same argument
    # `accounts/<id>/payments` has relied on since 2026-08-11, one noun along.
    # The two `accounts/<id>/premises-…` paths are a FIFTH and SIXTH literal last
    # segment beside `payments`, `collections` and `open-bills`, all declared in
    # `apps.payments.api`; none can shadow another and no `accounts/<id>/<catch
    # all>` may ever be added above them.
    # tests/test_cr059_cs12_multi_account_tender.py and
    # tests/test_cr059_cs27_master_pays_units.py resolve all four paths through
    # THIS file and then call them, so a future lane cannot lose the include
    # silently (DEF-524: a check pointed at a path that no longer exists reports
    # PASS through every defect underneath it).
    path("", include("apps.payments.tenders_api")),
    # EP-LED-03/04/05 · 11b §2.10 (2026-08-11) — GET /finance/revenue-ar,
    # GET /finance/taxes, GET /ledger/trial-balance, GET /ledger/journal-entries.
    # THE SAME ONE-LINE DEFECT AS THE TWO ROWS ABOVE, one module further along
    # and at its largest scale yet: `apps/ledger/reporting.py` landed on
    # 2026-08-11 as 1,500 lines of read model — every figure a Σ over POSTED
    # journal lines, five test files, a G7 human-owned guard and a row in the
    # human-review ledger — behind FIVE finance screens (S36, S41, S56, S59,
    # S60). `apps/ledger/api.py` was a one-line docstring and no include named
    # it, so the trial balance, the one report an auditor asks for first,
    # answered 404, and so did every other finance number in the product.
    # Built is not wired (hard-won law 2), and
    # tests/test_us_led_ledger_api.py resolves all six paths through THIS file
    # and then calls them over real HTTP, so a future lane cannot lose either
    # include silently.
    #
    # ORDER IS SAFE HERE and was checked rather than assumed: `finance/…` is
    # claimed by nothing else (payments' S37–S40 deposit and bank-import family
    # is unbuilt), `ledger/…` by nothing else, and `reports/<key>` below by
    # nothing else. No pattern in this list is a prefix of another.
    path("", include("apps.ledger.api")),
    # EP-LED-05 · 11b §2.10 (2026-08-15) — the WRITE half of the same module:
    # the close checklist, close/reopen, the export preview, the recorded
    # batch, its history, the drill-back and the dimension extracts, plus the
    # remittance record. **DEF-112**, and it is the third time this exact defect
    # has been written up in this file: `apps/ledger/close.py` and
    # `apps/ledger/exports.py` shipped complete, unit-tested and G7-guarded on
    # 2026-08-15 with `D=deferred(the S42 close endpoints are the API half —
    # not built by this lane)` in their own trailers, and the J19 month-end
    # journey booted a real browser and went red at STEP 1 — not on a wrong
    # figure, on the absence of anything to click. Every lane was honest and
    # nothing added the honest notes up; 10-scripts/gates/g22_surface_deferrals.py
    # is the check that now does.
    #
    # ORDER IS SAFE and was checked rather than assumed: every path in this
    # include begins `finance/` and none collides with the four `apps.ledger.api`
    # GETs above (`finance/revenue-ar`, `finance/taxes`) — `finance/taxes/
    # remittances` is a LONGER path and Django matches the full pattern, not a
    # prefix. tests/test_us_led_016_finance_api.py resolves all nine paths
    # through THIS file and then calls them over real HTTP.
    path("", include("apps.ledger.finance_api")),
    # EP-LED-02 + EP-LED-04 (2026-08-16) — the LAST two unreachable halves of
    # this module: the chart of accounts with its GL map, and the manual journal
    # entry with its accrual sweep.
    #
    # The chart is **tenant-customizable by design** (US-LED-005 §1: *"add
    # accounts, edit names"*) and no human could add, rename, re-point or retire
    # one line of it — `apps/ledger/services.py`'s own docstring said so
    # (*"WHAT IS NOT: the S56 chart CRUD"*) and `apps/ledger/api.py` listed
    # `GET /ledger/accounts` and the two gl-mapping routes under NOT SERVED.
    # `apps/ledger/manual_je.py` shipped on 2026-08-15 complete, LE-4-verified
    # and G7-guarded with `D=deferred(the S57 endpoints are the API half)`, so
    # the ONE way a finance officer corrects the books by hand existed and could
    # not be reached. Hard-won law 2, twice, in the module the register already
    # names three times above.
    #
    # ORDER IS SAFE and was checked rather than assumed. Django resolves by URL
    # and NOT by method, so a duplicate path SHADOWS rather than merges: no path
    # in either include is registered above. `ledger/accounts…` and
    # `ledger/gl-mappings` are new; `ledger/journal-entries/**` is one segment
    # deeper than the GET-only `ledger/journal-entries` in `apps.ledger.api`,
    # which is what preserves that file's stated guarantee that a forged write
    # verb on it is a router 405 before any view runs. `ledger/accounts` does
    # not collide with customers' `accounts/…` — the prefix differs and Django
    # matches whole patterns, not prefixes. tests/test_us_led_005_chart_api.py
    # and tests/test_us_led_011_journal_api.py resolve every path through THIS
    # file and then call it over real HTTP, so neither include can be lost
    # silently.
    path("", include("apps.ledger.chart_api")),
    # CR-197-BRC10 — the ONE GL mapping list (rows, add/edit, disable/enable).
    path("", include("apps.ledger.gl_mapping_api")),
    path("", include("apps.ledger.journal_api")),
    # EP-LED-06 (2026-08-16) — the PAYABLE side: S73 the captured-cost register
    # and its Capture/Edit/Void, S74 the bought-vs-billed reconciliation, and
    # the export-drift warning the OQ-203 ruling made a CONDITION.
    #
    # `apps/ledger/cost_capture.py` (1,187 lines) and `cost_reconciliation.py`
    # (500) shipped on 2026-08-15 complete, LE-11/LE-12/LE-13-verified and
    # G7-guarded, each carrying `D=deferred(no-API-half — S73's endpoints wait
    # on OQ-204)`. So a utility could capture nothing, see no register, and
    # never learn what fraction of the water it bought it failed to bill — the
    # one figure the Product Owner said the accounting package cannot produce
    # and this product can. **The fifth time this exact defect is recorded in
    # this file**, and the deferral had also gone stale: OQ-204 is scoped by its
    # own registry row to "navigation and the download contract only", so it
    # never blocked the capture, the register, the correction or the
    # computation. What it does block is served as blocked — the S74 download
    # raises NotImplementedError("OQ-204") and the screen disables its control
    # with that reason.
    #
    # ORDER IS SAFE and was checked rather than assumed. Django resolves by URL
    # and NOT by method, so a duplicate path SHADOWS rather than merges: no path
    # in this include is registered above. `finance/cost-of-service…` is claimed
    # by nothing else, and `finance/export/drift` is one segment deeper than
    # `finance/export/preview` and `finance/export/batches` in
    # `apps.ledger.finance_api` — a different whole pattern, not a prefix.
    # Inside the include, the all-static `reconciliation` segment is declared
    # ABOVE `<str:invoice_id>` or the word would resolve as an invoice id.
    # tests/test_us_led_018_cost_api.py resolves every path through THIS file
    # and then calls them over real HTTP, so the include cannot be lost silently.
    path("", include("apps.ledger.cost_api")),
    # CR-060 C2 / task T7 — GET /finance/accruals/unbilled (the preview) and
    # POST /finance/accruals/unbilled/post (the accrual itself).
    #
    # ORDER IS SAFE and was checked rather than assumed, the same way the
    # includes above were. Django resolves by URL and NOT by method, so a
    # duplicate path SHADOWS rather than merges: `finance/accruals/…` is claimed
    # by nothing else in this file — `apps.ledger.journal_api` owns
    # `ledger/accruals` and `ledger/accruals/auto-reverse`, which are a
    # different first segment entirely, and `apps.ledger.finance_api` owns
    # `finance/close-checklist`, `finance/periods…` and `finance/export…`, none
    # of which is a prefix of these. tests/test_cr060_t7_unbilled_accrual.py
    # resolves both paths through THIS file and then calls them over real HTTP,
    # so the include cannot be lost silently (DEF-128's lesson).
    path("", include("apps.ledger.accruals_api")),
    # 11b §2.13 + §2.9 (2026-08-16) — GET /outbound, GET /outbound/summary,
    # POST /outbound/{id}/requeue, POST /outbound/requeue,
    # POST /outbound/{id}/resend, POST /deliveries/returned, GET /notices.
    # **DEF-128, AND IT IS THE FOURTH TIME THIS EXACT DEFECT IS RECORDED IN THIS
    # FILE.** `apps/notifications` measured 7,084 lines — dispatcher 877,
    # services 897, template_service 796, notices 701, delivery_ops 635,
    # rendering 568 and more, every one of them tested — behind an `api.py` of
    # **72 BYTES**: one docstring line, no urlpatterns, and no include here.
    # So NOTHING A CUSTOMER WAS EVER SENT could be triggered, listed or audited
    # through the product: no queue to look at, no failed letter to re-queue, no
    # returned envelope to mark, no second copy to send, and no way to open the
    # record of the disconnect notices this utility had served.
    #
    # The durable half of the fix is 10-scripts/gates/g25_engine_surface.py,
    # which counts a module's ENGINE lines against its MOUNTED routes and fails
    # at ZERO — the number the three earlier occurrences and this one all had.
    # It was red-proved against this module before the first route was written.
    #
    # ORDER IS SAFE and was checked rather than assumed: `outbound/…`,
    # `deliveries/…` and `notices` are claimed by nothing else in this list —
    # customers owns `accounts/{id}/notices` (a THREE-segment path under
    # `accounts/`, which never collides with the bare `notices` here) and
    # payments owns `collections/notices`. tests/test_def_128_notifications_api.py
    # resolves all seven paths through THIS file and then calls them over real
    # HTTP, so a future lane cannot lose the include silently.
    path("", include("apps.notifications.api")),
    # 11b §2.13 + A15 (2026-08-16) — the CONFIG half of the same module:
    # GET|PATCH /notification-settings, GET /notification-templates,
    # GET /notice-tones. The delivery half above answers *what happened to a
    # message*; these answer *what the next one will look like*, and until today
    # nothing did. `apps/notifications/dispatch_config.py` shipped complete,
    # role-gated and audited on 2026-08-15 and no route named it, so the four
    # values the dispatcher obeys — batch size, the two quiet-hours boundaries
    # and the two channel flags — could not be seen or changed by anybody; the
    # S8 tab's own header said so. `notices.TONE_TO_STEP` is BR-PAY-035's whole
    # tone→tier mapping and no surface showed a clerk that picking "Firm" sends
    # the REGULATED 10-day disconnect notice rather than a firmer reminder
    # (BR-NOT-008), or that "Final" sends the 48-hour CERTIFIED letter at real
    # postage. And the template read is the first thing anywhere that reports
    # DEF-163: no tenant has ever had a notification template, because nothing
    # creates one, so every disconnect notice and every dunning letter is
    # refused rather than queued.
    #
    # ORDER IS SAFE and was checked rather than assumed: `notification-settings`,
    # `notification-templates` and `notice-tones` are claimed by nothing else in
    # this list — the bare `notices` above is a different literal, customers owns
    # `accounts/{id}/notices` and billing owns `bill-templates`. No pattern here
    # is a prefix of another. tests/test_us_not_004_settings_api.py resolves all
    # three paths through THIS file and then calls them over real HTTP.
    path("", include("apps.notifications.settings_api")),
    # CR-007 (PO 2026-08-16) — SET-09 the template catalog and SET-10 the
    # template detail/preview/editor. `GET /notification-templates` above is a
    # READ over the same registry and stays exactly as it is (the S8 card calls
    # it); these eight paths are the CATALOG surface and the WRITES, which is
    # what the CR asked for: `template_service` has held a complete
    # draft→publish→archive lifecycle since 2026-08-15 with nothing mounted over
    # it, so a System Admin could not change one word of any letter this utility
    # sends. Hard-won law 2 — built is not wired — closed on both sides.
    #
    # ORDER IS SAFE and was checked rather than assumed: every path starts with
    # the literal `template-catalog`, which nothing else in this list claims —
    # billing owns `bill-templates`, notifications' own read is
    # `notification-templates`, and neither is a prefix of the other.
    # tests/test_cr_007_template_catalog.py resolves all eight through THIS file
    # before calling one of them.
    path("", include("apps.notifications.templates_api")),
    # CR-199-BRC10 (TPL-SRV-LANG) — `GET /template-languages`, how many
    # customers prefer each language (PO option B, 2026-10-29). Its own
    # literal prefix, so no `template-catalog/<code>` path can claim it.
    path("", include("apps.notifications.template_languages_api")),
    # CR-009 (PO 2026-08-17) — SET-12 the notification EVENT MATRIX and SET-12D
    # the per-event rule page. The dispatch CONFIG above is the tenant's send
    # WINDOW and batch size; this is which EVENTS notify whom, on what, when.
    # Nothing stored it before: there was no `notification_rules` table, no
    # per-event audience, channel, timing or escalation storage anywhere, so a
    # utility could not decide that a bill-ready email goes out and a hi-usage
    # text does not. Fifteen events land with their rules; the requirement
    # claims sixteen and names fifteen, and that discrepancy is REPORTED rather
    # than filled in (`rule_catalog.py`'s docstring, decision log 2026-08-17).
    #
    # ⚠ NO SEND ROUTE, AND THE FOURTH PATH'S NAME IS THE REASON. The PO ruled
    # *"lets build the infra and capabilities; the moment we take the decison on
    # ESP or SMTP … we just need to plug it"*, and BR-NOT-005 / A11 r2 §4 still
    # forbid a route that transmits inside the request. So "Send test"
    # ENQUEUES: `notification-rules/{event}/queue-test` writes a queue row
    # addressed to the signed-in user and returns the provider seam's own
    # deferred verdict. tests/test_cr_009_notification_rules.py asserts that
    # `…/send` and `…/test-send` both answer Resolver404.
    #
    # ORDER IS SAFE and was checked rather than assumed: every path starts with
    # the literal `notification-rules`, which nothing else in this list claims.
    # `notification-settings` and `notification-templates` are different
    # literals and neither is a prefix of this one (Django matches whole path
    # segments, and `notification-rules` shares no segment with either). The
    # same test resolves all three paths through THIS file before calling one.
    path("", include("apps.notifications.rules_api")),
    # CR-009 (PO 2026-08-17) — the in-app INBOX: the bell's badge, its list and
    # the two read actions. A FIFTH notifications include, and the split is the
    # same one every other one here follows: `api.py` is the delivery ops half,
    # `settings_api.py` the config half, `templates_api.py` the catalog,
    # `rules_api.py` the SET-12 matrix, and this is the RECIPIENT's own view of
    # what was actually delivered to them.
    # ORDER IS SAFE and was checked rather than assumed: every path starts with
    # the literal `in-app-messages`, which nothing else in this list claims, and
    # within the module `read-all` is registered ahead of `<message_id>/read`.
    # ⚠ NO `send` AND NO `test-send` — BR-NOT-005 and A11 r2 §4, asserted by
    # name against this surface because in-app is the first channel where such a
    # route would actually have delivered something.
    path("", include("apps.notifications.in_app_api")),
    # CR-049 task 3 (PO 2026-08-30) — GET /outbound/{id}/document,
    # GET /documents/{id}, GET /documents/register: the routes that SERVE a
    # frozen legal document. `BR-NOT-027` froze the letter at send on 2026-08-30
    # and the task-2 lane closed with the gap in its own words — *"no endpoint
    # serves a frozen document yet, so a screen could still re-render one and
    # nothing I wrote would notice. The guarantee is worth only what the route
    # eventually does with it."* **THE NINTH TIME HARD-WON LAW 2 IS RECORDED IN
    # THIS FILE**, and the first where the missing half was a legal guarantee
    # rather than a feature: a write-once store, a dispatcher that freezes before
    # every hand-off and 145 passing tests amounted to nothing a person could
    # open.
    #
    # ORDER IS SAFE and was checked rather than assumed. `documents/register` is
    # all-literal and is declared INSIDE the module ahead of
    # `documents/<document_id>`, which would otherwise swallow it; `documents` is
    # claimed by no other include (`grep -rn '"documents' apps/*/api*.py` finds
    # only this module); and `outbound/<id>/document` shares its first segment
    # with `apps.notifications.api` above but no whole path with any of its five
    # `outbound` routes — Django matches whole segments, so neither shadows the
    # other. tests/test_cr049_t3_reprint_route.py resolves all three through THIS
    # file and then calls them over the wired stack, so a lost include goes red
    # here rather than in a regulator request.
    path("", include("apps.notifications.reprint_api")),
    # 11b §1 line 32 + 13a rows S59/S60 (2026-08-11) — GET /reports/{key},
    # serving the Account ledger (S59) and By-premises summary (S60) reports.
    # The ROUTE is the reports module's and the NUMBERS are the ledger's:
    # 04-docs/05-modules/12-reports/01-overview.md settles the split —
    # "ledger owns the TB/account-ledger/by-premises/remittance STORIES …
    # reports owns the report CENTER (S44 catalog · S46 viewer · IS-11
    # download pipeline)". `apps/reports/api.py` reads through
    # `apps.ledger.reporting`'s published functions and owns no tables.
    path("", include("apps.reports.api")),
    # CR-069 wave A (2026-09-03): `GET /integrations` — every manifest the
    # registry holds, joined to THIS tenant's connection state (US-INT-001 ·
    # US-INT-013 · US-INT-018). The three write routes of BR-INT-002 land in
    # wave B with the modal that calls them (US-INT-017 · US-INT-019).
    path("", include("apps.integrations.api")),
    # CR-068 wave A (2026-09-03): the customer web portal's edges — separate
    # files, separate includes (BR-CWP-011 — a portal session must not be able
    # to call a staff route and the guest surface must not be able to call the
    # portal edge; keeping them apart starts with never sharing a module).
    #   guest_api      /api/{tenant}/portal/public/…   anonymous, throttled per address AND per tenant
    #   backoffice_api /api/{tenant}/settings/portal…  the STAFF app's Settings → Customer portal
    #   api            /api/{tenant}/portal/…          the SIGNED-IN customer,
    #                                                   `sbh_portal` cookie, its
    #                                                   own authentication class
    # ⊕ **THE THIRD EDGE LANDED 2026-09-04 (wave E)** — with its first thirteen
    # routes rather than as an empty include, because an `api.py` with nothing in
    # it is a promise in a module name (law 1) and G9 reads it as endpoint code.
    # It declares `PortalSessionAuthentication` and NOT the default list, so a
    # stale staff cookie is never read on a portal route: a visitor who was in
    # the back office last week is simply not signed in here, rather than 401'd
    # by somebody else's session (BR-CWP-011).
    # ORDER IS SAFE and was checked rather than assumed: `portal/…` is claimed
    # by no other include in this list (`grep -rn '"portal' apps/` finds only
    # these), `settings/portal` shares its first segment with tenancy's
    # `settings/…` family but Django matches WHOLE segments and tenancy mounts
    # no `settings/portal`, and neither is a prefix of anything.
    # tests/test_us_cwp_001_front.py resolves the guest route through THIS file.
    path("", include("apps.portal.guest_api")),
    path("", include("apps.portal.backoffice_api")),
    path("", include("apps.portal.api")),
    # CR-189-BRC10 — `portal/update-email/…`, anonymous, its own file so the
    # change stays out of `api.py`. `update-email` is claimed by nothing else.
    path("", include("apps.portal.email_update_api")),
    # CR-068 wave D (2026-09-04): help answers, tips and service centres. The
    # TABLES are tenancy's (03-field-map.md §2 — published content is per-tenant
    # reference data), so the routes that write them are tenancy's too: B2 §2
    # forbids a cross-module write and G81 holds that line over the whole
    # portal package. Two lists out of one module:
    #   urlpatterns        /api/{tenant}/settings/portal/help|tips…   STAFF, A4 settings_lookups
    #                      /api/{tenant}/settings/reference-data/service-centres
    #   guest_urlpatterns  /api/{tenant}/portal/public/help/{slug}/feedback
    #                      anonymous, wearing the SAME per-address + per-tenant
    #                      throttles and the same in-flight budget as every
    #                      other guest door (NFR-39).
    # ORDER IS SAFE and was checked rather than assumed: `settings/portal/help`,
    # `settings/portal/tips` and `settings/reference-data/service-centres` are
    # claimed by nothing else (tenancy/api.py mounts `settings/company`,
    # `settings/holidays`, `lookups/…` and no `settings/portal` at all; portal's
    # backoffice_api mounts only `settings/portal`, `…/branding` and
    # `…/qr.svg`), and Django matches WHOLE segments so no one is a prefix of
    # another.
    path("", include("apps.tenancy.published_content_api")),
    path("", include((published_content_guest_urlpatterns, "tenancy"), namespace="cwp-guest")),
    # CR-069 wave D (2026-09-03): `GET` / `PUT /integrations/{key}/mappings` —
    # their words for our things (US-INT-037), in its own URLconf so this
    # wave's commit stays out of wave B's api.py.
    path("", include("apps.integrations.mappings_api")),
    # CR-069 wave C (2026-09-04): `GET /integrations/{key}/runs` and
    # `GET …/runs/{run_id}` — the run record S142 reads (US-INT-020), in its
    # own URLconf for the same reason the line above is. It is included AFTER
    # `api.py`'s `integrations/<str:key>`, and that is safe because Django
    # matches the whole path: `…/email_smtp/runs` never reaches a pattern that
    # ends at the key. tests/test_us_int_020_runs.py resolves both routes
    # through THIS file rather than trusting the reading.
    path("", include("apps.integrations.runs_api")),
    # CR-173-BRC10 (2026-10-07): `…/integrations/{key}/groups/{group}` — a
    # connection's named section (New World's *Send to City folder*): read,
    # save, test, resend. Its own URLconf, so the change stays out of api.py.
    path("", include("apps.integrations.file_drop_api")),
    # CR-069 wave S (2026-09-06): the partner's door and the manager's window
    # onto it (US-INT-041) — `GET v1/payments`, `v1/billing`, `v1/openapi.json`
    # for a machine with a key, and `integrations/{key}/access-log`,
    # `integrations/subprocessors`, `integrations/{key}/grant` for a signed-in
    # System Admin.
    #
    # ⚠ THE THREE `v1/…` ROUTES SIT INSIDE THE TENANT INCLUDE ON PURPOSE, AND
    # THE EXECUTION PLAN SAID THEY WOULD NOT. The plan (S1) writes them as
    # `/api/v1/payments`, with no utility in the path. That address cannot
    # work: BR-TEN-003 says the tenant is read from the PATH and never from a
    # header or a parameter, and CLAUDE.md hard rule 1 has RLS on FORCE — so
    # with no tenant on the session the credential lookup returns zero rows for
    # EVERY key, a valid one included, and the endpoint would be incapable of
    # passing. Mounted here, `TenantContextMiddleware` sets app.tenant_id from
    # `{utility}` before the view runs, and a key issued by one utility is
    # simply invisible under another's context — so US-INT-041's TC-5 and TC-7
    # are enforced by the database rather than by a line somebody could delete.
    # The reasoning is in 12-governance/02-decision-log.md (2026-09-06) and in
    # apps/integrations/runners/serve.py's docstring.
    #
    # ⚠ **THIS COMMENT ASSERTED A COLLISION AWAY AND WAS WRONG ABOUT ONE
    # ROUTE.** It read: *"Django matches whole paths, so
    # `…/integrations/{key}/access-log` never reaches `api.py`'s pattern that
    # ends at the key."* True of every THREE-segment route here, and false of
    # the two-segment `integrations/subprocessors`, which `api.py`'s
    # `integrations/<str:key>` matched first — reading `subprocessors` as a
    # provider key and answering **405 Method Not Allowed**. A comment claiming
    # a guarantee is not the guarantee (hard-won law 1), and it was the browser
    # that found this, not the reasoning.
    #
    # The register is `integrations/register/subprocessors` now — three
    # segments, out of collision range, and it does not depend on the ORDER of
    # the includes in this list. The three-segment routes
    # (`…/{key}/access-log`, `…/{key}/grant`) were always safe for the reason
    # above, and `v1/…` shares a first segment with nothing.
    # tests/test_us_int_041_partner_surface.py resolves every one of the six
    # through THIS file so a future lane cannot lose the include silently.
    path("", include("apps.integrations.partner_api")),
    # CR-069 wave N (2026-09-06): the INBOUND door (US-INT-044) —
    # `POST integrations/inbound/{key}/{operation}`, the address a payment
    # kiosk posts to. 07-endpoints.md row 25.
    #
    # ⚠ IT IS FOUR SEGMENTS AND THE FIRST TWO ARE LITERAL, so unlike
    # `integrations/subprocessors` above it is out of collision range with
    # `api.py`'s `integrations/<str:key>` by CONSTRUCTION rather than by
    # ordering — `integrations/inbound/payments_kiosk/payments` matches
    # nothing else in this list, and `api.py`'s only four-segment patterns
    # (`…/{key}/oauth/start`, `…/{key}/credential/rollback`) need a literal
    # third segment. That is the reading; the assertion is in
    # tests/test_us_int_044_inbound_door.py, which RESOLVES the real path,
    # because the comment two blocks up was wrong about exactly this and a
    # browser found it (hard-won law 1).
    #
    # ⚠ AND IT IS INSIDE THE TENANT INCLUDE FOR A REASON STRONGER THAN
    # wave S's: this door WRITES. A delivery row landing under no tenant, or
    # under the wrong one, is somebody else's money in somebody else's book —
    # so `TenantContextMiddleware` sets app.tenant_id from `{utility}` before
    # the view runs, and hard rule 1 does the rest.
    path("", include("apps.integrations.inbound_api")),
    # CR-198-BRC10 (2026-10-29): text messages provided by the PLATFORM — the
    # Twilio card's read and Test, and Twilio's signed status callback
    # (`integrations/platform/sms_twilio/status`, four segments, the second
    # literal, out of `api.py`'s `integrations/<str:key>` range by construction).
    path("", include("apps.integrations.platform_api")),
    # CR-075 wave D (2026-09-06): the RUNBOOKS module's first door — eight READ
    # routes (US-RBS-003 · US-RBS-018; 07-endpoints.md rows 1, 2, 4, 8, 9, 10,
    # 11 and 14): the catalogue, the shipped template library, the run history,
    # one run, its FROZEN report, its records, and the two result CSVs.
    #
    # ⚠ **THIS LINE IS WHAT TURNS `G27 engine-surface` GREEN FOR `runbooks`.**
    # The module had 4,369 lines of engine and no `api.py`, no `urls.py` and
    # nothing here reaching it, which G27 reported as *"an entire module is
    # invisible — nothing it does can be triggered, listed or audited through
    # the product"*. That red was sanctioned and dated in
    # 12-governance/02-decision-log.md, which REFUSED a fake route to clear it
    # and named this wave as what would; the paragraph holding it is deleted in
    # the same commit as this include, because a hold that outlives its
    # condition is DEF-CWP-3925's mirror defect.
    #
    # ⚠ **ORDER INSIDE `apps.runbooks.api` IS LOAD-BEARING AND ORDER HERE IS
    # NOT.** `runbooks/…` is claimed by no other include in this list
    # (`grep -rn '"runbooks' apps/` finds only that file) and is a prefix of
    # nothing. What DOES collide is inside the module: `runbooks/<str:key>`
    # matches the literal `runbooks/templates` and `runbooks/runs`, so both
    # literals are registered BEFORE the key pattern — the same collision
    # `integrations/subprocessors` shipped with, read as a provider key and
    # answered 405 under a comment asserting it could not happen (hard-won law
    # 1: it was the browser that found that one, not the reasoning).
    # tests/test_us_rbs_003_endpoints.py RESOLVES all eight paths through THIS
    # file, so a lost include or a reordered pattern goes red here rather than
    # in front of a clerk.
    #
    # ⚠ **EVERY ONE OF THE EIGHT IS A `GET`.** `BR-RBS-002` — a Check is
    # CONSTRUCTED with no ports — is the module's whole safety promise, and
    # phase 1's launch sentence is *"nothing can be written: no writer is
    # bound"*. The write routes (add, clone, PUT, run, approve, stop, decide,
    # raise work items) are waves E and L, and they bring `07-endpoints.md`'s
    # six refusal keys with them: a `message_key` is minted in all eleven
    # catalogues in the same commit as its raise site, or it reaches a clerk as
    # silence (PO ruling 2026-08-19).
    path("", include("apps.runbooks.api")),
]

urlpatterns: list = [
    # ── /api/… — public + platform, no tenant segment (PO 2026-08-10) ──────
    path("api/", include(tenancy_public_urlpatterns)),  # public/* + POST /tenants
    # BE-07: the ONE shared async-job poll resource every 202 in this API
    # promises (B12 r1 / 11b §2.17). It is a PLATFORM path, not a tenancy
    # feature path, so it is registered here rather than inside the tenancy
    # include — the view lives with the module that hosts the `jobs` table.
    # It still serves ONE tenant's jobs: with no slug to read, the tenant comes
    # from the session row (core.tenancy.adopt_session_tenant, BR-IDN-006).
    path("api/jobs/<uuid:job_id>", job_status),  # GET /api/jobs/{id} (2026-08-10)
    # US-SHL-008 / 11b §2.11: the table-level export every DataTable's Download
    # posts to. A PLATFORM path for the same reason /jobs is — the nine
    # exportable lists live in four different modules and register themselves
    # with the kernel; the endpoint belongs to none of them.
    path("api/exports", list_export),  # POST /api/exports (2026-08-10)
    # IS-11 / BR-REP-018: the download the 202 → poll → result_link chain ends
    # at. A PLATFORM path for the same reason the two above are — it serves the
    # artifact of ANY export job kind (list_export, audit_export), whichever
    # module produced it.
    path("api/exports/<uuid:job_id>/file", export_file),  # GET (2026-08-10)
    # `CR-142-BRC07` `P4.14` — BI tier 2. The scheduled-delivery link a BI tool
    # is handed, redeemed for ONE report artifact.
    #
    # ⚠ A NO-TENANT PATH, for the reason the three above are and one more of
    # its own: the tenant is INSIDE the signed token, and a utility slug in the
    # URL would be a second, UNSIGNED assertion about who is asking, sitting
    # beside the signed one. `apps/reports/delivery_api.py` lists the four
    # checks it makes and the order they run in.
    path("", include("apps.reports.delivery_api")),
    # CR-110-BRC04 phase 2 (DEF-INT-5546, PO ruling 2026-09-16): THE PARTNER
    # SURFACE — `GET /api/partner/v1/reference · customers · bills · payments ·
    # ledger`. ONE BASE URL for every partner and every utility.
    #
    # ⚠ IT IS A NO-TENANT PATH AND THAT IS THE WHOLE CHANGE. These five were
    # mounted inside the tenant include as `/api/{utility}/partner/v1/…` until
    # this ruling. PO, verbatim: *"we agreed not to use utility names in partner
    # apis that was our rule - so these urls are not corect - we will resolve
    # utility name using keys"*. The utility is opened from the KEY, through
    # `key_directory.open_utility_for` — the same shape as `/api/jobs/{id}` and
    # `/api/exports` three lines up, which open it from the session row. Both
    # read a table B2 §3 declares RLS-exempt precisely so it can be read before
    # a utility is open; neither reads a tenant the CALLER asserts, which is
    # what BR-TEN-003 forbids.
    #
    # ⚠ REGISTERED BEFORE THE TENANT `re_path` BELOW, WHICH MATCHES
    # `^api/[-a-zA-Z0-9_]+/` AND WOULD THEREFORE MATCH `api/partner/` TOO.
    # Django tries these in order, so this line wins; and `core.tenancy.
    # NON_TENANT_SEGMENTS` carries `partner` so the middleware reads no slug
    # from it, while `RESERVED_SUBDOMAINS` carries it so no utility can be named
    # `partner` and be shadowed here. Three things agreeing, and
    # tests/test_cr110_partner_tenant_from_key.py RESOLVES the real path rather
    # than trusting the reading — the comment two blocks down was wrong about
    # exactly this kind of reasoning once, and a browser found it.
    path("api/", include("apps.integrations.partner_urls")),
    # DEF-FLD-10580 (beta MQ-006, PO 2026-10-24: *"the code from the office
    # sets the utility"*) — `POST /api/auth/activation/lookup`, the field app's
    # utility-free first call: a code in, the utility that holds it out. Before
    # the tenant `re_path` for the reason the partner surface is; `auth` is in
    # NON_TENANT_SEGMENTS and RESERVED_SUBDOMAINS. `apps/identity/
    # platform_urls.py` and `native.lookup_activation_code` say the rest.
    path("api/", include("apps.identity.platform_urls")),
    # CR-198-BRC10 — `POST /api/hooks/twilio/reply`, Twilio's incoming-text
    # webhook for a SHARED sender: one address for every utility, so no utility
    # in the path. Before the tenant `re_path` for the partner surface's
    # reason; `hooks` is in NON_TENANT_SEGMENTS and RESERVED_SUBDOMAINS.
    path("api/", include(twilio_hook_urlpatterns)),
    # ── /api/{tenant}/… — everything else ─────────────────────────────────
    # NON-CAPTURING on purpose. `path("api/<slug:tenant>/", …)` would hand a
    # `tenant=` kwarg to all ~60 views downstream, none of which want it: the
    # tenant is resolved ONCE, by the BE-01 middleware, from the raw path, and
    # a second copy arriving as a view argument is exactly the kind of
    # client-shaped tenant input BR-TEN-003 forbids anyone from reading.
    #
    # The character class is the `slug` converter's ([-a-zA-Z0-9_]+), a
    # superset of the BR-TEN-011 grammar — so the route matches every legal
    # slug and the RESOLVER, not the router, decides whether the tenant exists
    # (unknown → 404 through require_tenant, never 403: HR-1).
    re_path(r"^api/[-a-zA-Z0-9_]+/", include(tenant_urlpatterns)),
]
