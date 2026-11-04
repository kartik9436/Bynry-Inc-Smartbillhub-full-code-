"""`P3.3` — raise ONE refund through the product's own service, for the walk.

The Finance blueprint's 2·5d walk needs a refund in `requested` to open, and
`load_sample_data` seeds one that is already `cleared`. This raises a real one
through `refunds.request_refund`, so the walk opens a record the product itself
created: `BR-PAY-014`'s credit test and `OQ-135`'s offset-first refusal both
apply exactly as a clerk's press would, and a refund this refuses is a refund
the screen could not have shown either.

RUN — against a CLONE, never a shared database:

    eval "$(10-scripts/proof-db.sh clone finp3 --export)"
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      python3 ../10-scripts/fin_p3_seed_a_requested_refund.py

⚠ **IT REFUSES RATHER THAN INVENTING CREDIT.** If no account on the clone holds
a credit balance, it says so and exits 1; seeding an overpayment is a different
act and is not done quietly here.
"""
import os, sys
from pathlib import Path
import django

_BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from decimal import Decimal
from django.utils import timezone
from core.tenancy import tenant_context
from apps.tenancy.models import Tenant
from apps.customers.models import Account
from apps.identity.models import User
from apps.payments import refunds, selectors as pay_selectors

t = Tenant.objects.first()
with tenant_context(str(t.id)):
    actor = User.objects.filter(email="dana@brazosbendutilities.com").first()
    picked = None
    for account in Account.objects.all()[:400]:
        position = pay_selectors.account_credit_position(account.id)
        if position > Decimal("0"):
            picked = (account, position)
            break
    if picked is None:
        print("NO ACCOUNT HOLDS CREDIT — nothing to refund"); sys.exit(1)
    account, position = picked
    print("account", account.account_no, "credit", position)
    result = refunds.request_refund(
        actor,
        payment_id=None,
        account_id=str(account.id),
        amount=position,
        method="check",
        requested_at=timezone.now(),
        reason="Overpayment",
        cross_account_check=True,
        idempotency_key="finp3-walk-refund-1",
    )
    print("refund", result.refund_id, "created", result.created)
