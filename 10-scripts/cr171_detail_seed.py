"""CR-171-BRC10 lane MVI-DETAIL — put one move-in in EVERY status on a lane database.

Run inside the backend with the lane's settings, AFTER `seed_demo` and
`load_sample_data --tenant brazosbend`:

    DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
      python manage.py shell < ../10-scripts/cr171_detail_seed.py

The sample tenant already carries a Waiting-on-customer request, a Not started
job, a Draft and a Completed move-in. This adds, through the real services
(never a direct row write):

  * a TO APPROVE request and a DECLINED one (images 03, 07);
  * a committed move-in on SCW-U-042 (water meter + sub-meter, electric meter)
    with the deposit and plan fees paid by check, a co-owner and a field visit,
    whose electric opening read is left unread — WAITING ON A READ (image 13);
  * a committed move-in on a second metered unit, then cancelled (image 17).

Every name, date and figure is an illustration (B14 rule 37). Re-running it
adds another set; it never edits what is there. It prints the references.
"""

import uuid
from types import SimpleNamespace

from core import tenancy as core_tenancy

from apps.customers import models as cmodels
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.identity.models import User
from apps.tenancy.models import Tenant

tenant = Tenant.objects.get(subdomain="brazosbend")
user = User.objects.get(email="dana@brazosbendutilities.com")
actor = SimpleNamespace(id=user.id, role="system_admin", user=user, tenant_id=tenant.id)
DOC = cmodels.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY


def capture(name, unit_no):
    return {
        "channel": "customer_portal",
        "applicant_kind": "person",
        "applicant_name": name,
        "applicant_email": f"{name.split(',')[0].lower()}@example.invalid",
        "applicant_phone": "641-555-0182",
        "address_as_given": unit_no,
        "property_type": "standalone_owner_occupied",
        "what_they_said": "Moving in next week",
        "requested_start": "2026-10-12",
    }


def move_in_request(name, unit_no):
    request = sr.create_request(actor, capture(name, unit_no))
    sr.attach_document(actor, request.id, doc_type=DOC, name="photo-id.pdf", storage_ref="s3://photo-id")
    sr.submit(actor, request.id)
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=None)
    sr.decide_outcome(actor, request.id, outcome="move_in")
    return sr.request_row(request.id)


def person(name):
    return {"kind": "person", "display_name": name, "identity": {"phone": "732-555-0285"}}


def commit(unit_no, name, **extra):
    from apps.metering.models import Unit

    row = Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
    payload = {
        "account_type": "residential",
        "opened_at": "2026-10-03",
        "contact": {"full_name": name, "email": "nilesh@example.invalid", "phone": "732-630-0285"},
        "customer": person(name),
    }
    payload.update(extra)
    return customers_services.move_in_to_unit(actor, row.id, payload)


import os

with core_tenancy.tenant_context(tenant.id):
  if os.environ.get("MDS_SKIP_REQUESTS") != "1":
    to_approve = move_in_request("Verma, Asha", "U-00214-200")
    declined = move_in_request("Ruiz, Paolo", "U-00318-102")
    sr.refuse_request(actor, declined.id, reason="Lease not signed", reason_code="other",
                      message_to_applicant="Lease not signed")
    print("TO APPROVE", to_approve.request_no)
    print("DECLINED", sr.request_row(declined.id).request_no)
  if os.environ.get("MDS_SKIP_COMMITS") != "1":

    waiting = commit(
        "SCW-U-042",
        "G, Nilesh",
        initial_reads=[{"meter_no": "W-5041", "value": "2531"}],
        fees=[
            {"kind": "fee", "source": "charge_code", "code": "CONN", "amount": "45.00"},
            {"kind": "fee", "source": "charge_code", "code": "SAME-DAY", "amount": "50.00"},
        ],
        payment={"mode": "pay_now", "method_code": "check", "amount": "95.00", "confirmation": "1043",
                 "received_on": "2026-10-03", "idempotency_reference": str(uuid.uuid4())},
        co_owners=[{"full_name": "G, Riya", "relationship": "Spouse", "phone": "732-555-0144",
                    "contact_by": "text", "responsible_for_bills": True}],
    )
    print("WAITING ON A READ", waiting.get("move_no"), waiting.get("id"))

    cancelled = commit("U-00101-A", "Lee, Morgan")
    print("TO CANCEL", cancelled.get("move_no"))
