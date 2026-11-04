"""Identity's ONE route with no utility in its path — `DEF-FLD-10580`.

`POST /api/auth/activation/lookup` — the field app's first call on a new
handset: the code from the office names the utility (PO 2026-10-24, *"A. The
code from the office sets the utility"*). Mounted from `config/urls.py` BEFORE
the tenant `re_path`, which would otherwise read `auth` as a utility slug;
`core.tenancy.NON_TENANT_SEGMENTS` carries `auth` so the middleware reads no
slug here, and `apps.tenancy.selectors.RESERVED_SUBDOMAINS` carries it so no
utility can ever be named `auth` (`test_be01_tc16` keeps those two in step).
"""

from django.urls import path

from apps.identity import api

urlpatterns = [
    path("auth/activation/lookup", api.ActivationLookupView.as_view()),
]
