from .base import *  # noqa

DEBUG = False
# Fill from environment at deploy time. No secrets in this file, ever.

# Deployment blocker closed 2026-08-10 (09-infra/02 runbook finding): base.py
# leaves ALLOWED_HOSTS empty, and with DEBUG=False Django rejects EVERY request
# — so a deploy that forgot this would 400 on every request, including the load
# balancer's health check.
#
# AMENDED 2026-08-10 (PO ruling: tenancy moved from subdomain to PATH). Every
# tenant is served from the SAME host now — `smartbillhub.bynry.com/{tenant}/…`
# — so this is ONE name, with NO leading-dot wildcard. Dropping the wildcard is
# a real narrowing, not cosmetics: `.smartbillhub.bynry.com` accepted any label
# anyone could point at the load balancer, and Host is what Django trusts for
# absolute URLs and CSRF origin checks. The wildcard TLS certificate the
# subdomain design needed is likewise no longer required (09-infra runbook —
# not this lane's territory, flagged there).
#   DJANGO_ALLOWED_HOSTS=smartbillhub.bynry.com
# The ALB health check reaches the task by its private IP; add that one address
# (or the ALB's own name) beside the host — never a wildcard.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])  # noqa: F405

# BE-07: production runs job bodies on a Celery worker (TD-17), never inside
# the web request — a bill run or a 50k-row export must not hold a request
# open. Deploying with this True (or without a broker) is a misconfiguration.
JOBS_EAGER = env.bool("JOBS_EAGER", default=False)  # noqa: F405

# DEF-BIL-8510 — the walk's outage switches never exist in production, whatever
# the environment says (`core/walk_switches.py`).
WALK_SWITCHES_DIR = ""
WALK_SWITCHES_FORBIDDEN = True

from django.core.exceptions import ImproperlyConfigured  # noqa: E402

# BR-CUS-092 / OQ-016 — app-layer field encryption. REFUSES TO BOOT WITHOUT A KEY.
#
# Same posture as DJANGO_ALLOWED_HOSTS above and for the same reason: the failure
# is certain either way, and the only question is whether it arrives with a name.
# Without a key the tenancy EIN backfill migration stops `migrate` a few seconds
# later, and any SSN written under BR-CUS-092 would refuse at the moment a
# customer submits a form. Raising here turns both into one boot-time sentence.
#
# ⚠ LAW 4 — THIS DOES NOT REACH A HOST THAT ALREADY HAS A `.env`. Every existing
# deployment must add SBH_FIELD_ENCRYPTION_KEYS to its OWN .env by hand before
# the next deploy, or this container will not start. Generate a key with:
#   python -c "import base64,os;print('k1:'+base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('='))"
# Rotation is additive: put the new key FIRST and leave the old one behind it.
if not FIELD_ENCRYPTION_KEYS:  # noqa: F405
    raise ImproperlyConfigured(
        "SBH_FIELD_ENCRYPTION_KEYS is not set. High-sensitivity columns "
        "(tenants.ein today, the BR-CUS-092 identifiers next) are app-layer "
        "encrypted and this process would be unable to read or write any of them. "
        "It is NOT started with encryption disabled — OQ-016 is closed law and "
        "hard-won law 3 says the unsafe option must be the one you type. "
        "Generate a key: python -c \"import base64,os;print('k1:'+"
        "base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('='))\" — and "
        "note that editing .env.example changes nothing on a host that already "
        "has a .env (hard-won law 4)."
    )


# ═══════════════════════════════════════════════════════════════════════════
# CR-144-BRC07 — ECS Fargate behind an Application Load Balancer.
# THIS FILE HAD NONE OF THE FOLLOWING before 2026-09-28.
# ═══════════════════════════════════════════════════════════════════════════

# ── The proxy tells us the scheme ──────────────────────────────────────────
# The ALB terminates TLS and speaks PLAIN HTTP to the task on port 8000. So
# `request.is_secure()` is False for every request unless Django is told where
# the real scheme is recorded, and without this:
#   * `SECURE_SSL_REDIRECT` below would redirect EVERY request forever — the
#     task never sees an https request, so the redirect never satisfies itself;
#   * every absolute URL the product builds (a reset link, a `Location`, a
#     portal QR code) would be written `http://` and handed to a customer.
#
# ⚠ **IT IS ONLY SAFE BECAUSE NOTHING BUT THE ALB CAN REACH THIS PORT.**
# `X-Forwarded-Proto` is a header any client can set. The ALB OVERWRITES it, so
# a client cannot forge it through the load balancer — but a task reachable
# directly (a security group that allows 8000 from anywhere) would let a caller
# claim https and be believed. The security-group rule is part of this setting,
# not separate from it: see 09-infra/02-aws-runbook.md.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── The HTTPS redirect ─────────────────────────────────────────────────────
# ⚠ **DEFAULT OFF, AND THAT IS DELIBERATE RATHER THAN LAX.** The ALB's own HTTP
# listener redirects to HTTPS before a request ever reaches this process, which
# is one hop cheaper and cannot loop. Turning it on here as well is belt and
# braces for an environment whose listener is not configured that way; turning
# it on with `SECURE_PROXY_SSL_HEADER` missing or a listener that strips
# `X-Forwarded-Proto` is an infinite redirect on every page.
#
# ⚠ **THE HEALTH PROBE IS UNAFFECTED EITHER WAY** — `core.health` answers ahead
# of `SecurityMiddleware` in the chain, which is the whole reason it is first,
# and `tests/test_health.py::test_health_answers_through_the_https_redirect`
# holds that shut with this setting switched on.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)  # noqa: F405

# ── HSTS ───────────────────────────────────────────────────────────────────
# ⚠ **HSTS IS THE ONE HEADER YOU CANNOT TAKE BACK.** A browser that has seen it
# refuses plain HTTP to this host for the whole `max-age`, whatever the server
# later says. So it is env-driven and defaults to ZERO (= not sent), and an
# environment ramps it: 300 for a day, 86400 for a week, then 31536000.
# `includeSubDomains` and `preload` are separately switchable for the same
# reason — `includeSubDomains` on `bynry.com` would commit every sibling host,
# and `preload` is a submission to a list that is slow to leave.
#
# ⚠ AND IT IS ONLY EVER SENT ON AN https REQUEST, which is why
# `SECURE_PROXY_SSL_HEADER` above has to be right first. Set it without that and
# this header is silently never sent — a check that cannot fail (hard-won law 7).
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(  # noqa: F405
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)  # noqa: F405

# ── Django's own cookies ───────────────────────────────────────────────────
# The product's sign-in cookies are set by hand in apps/identity, apps/tenancy
# and apps/portal and read `AUTH_COOKIE_SECURE` (base.py). These two cover
# Django's framework cookies, which the admin and any future CSRF use.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ── CORS ───────────────────────────────────────────────────────────────────
# ⚠ **THE VALUE IS PER ENVIRONMENT AND THERE IS EXACTLY ONE OF THEM**, because
# the browser loads the app from a DIFFERENT HOST to this API (decision log
# 2026-09-28 ruling 1). It is inherited from base.py, which reads
# `CORS_ALLOWED_ORIGINS` and defaults to EMPTY — a deployment that forgets it
# grants nothing and says so loudly in the browser console, rather than
# granting everything quietly (hard-won law 3).
#
#   dev       CORS_ALLOWED_ORIGINS=https://app-dev.bynry.com
#   sandbox   CORS_ALLOWED_ORIGINS=https://app-sand.bynry.com
#   production CORS_ALLOWED_ORIGINS=https://app.bynry.com
#
# ⚠ **NEVER `*`.** Not as a matter of taste: `Access-Control-Allow-Origin: *`
# and `Access-Control-Allow-Credentials: true` are mutually exclusive by
# specification, and the session cookie IS the credential — so a wildcard would
# simply not work, and would present as "signed in, and every call is 401".
#
# ⚠ **CSRF_TRUSTED_ORIGINS IS THE SAME LIST AND A DIFFERENT MECHANISM.** Django
# checks it on any view that runs CSRF protection (the admin, and anything
# added later). It is set from the same variable so the two cannot drift.
CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)  # noqa: F405
