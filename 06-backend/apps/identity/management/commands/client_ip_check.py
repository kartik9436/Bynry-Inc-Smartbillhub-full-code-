# ── Trace ──────────────────────────────────────────────
# Ruling:   PO 2026-10-08 — decision log "THE SECURITY TAB'S SETTINGS ARE MADE
#           TRUE", item (4): DevOps confirms `TRUSTED_PROXY_COUNT` on live
#           before any utility uses Allowed addresses.
# Rules:    BR-IDN-020 (allowed addresses, every request) · runbook §10.15 and
#           §11 item 24 · CLAUDE.md hard-won law 4 (a template never reaches a
#           host that already has its settings)
# Tests:    06-backend/tests/test_def_idn_security_settings_true.py
# ───────────────────────────────────────────────────────
"""`manage.py client_ip_check` — what address the server believes a caller has.

READ-ONLY. It changes nothing, and it does not change the allowlist logic: it
runs the SAME `identity.auth.client_ip` every request runs.

WHY IT EXISTS
-------------
Settings → Security → Allowed addresses compares the caller's address with the
utility's list on every request. The address is `client_ip(request)`, which
trusts `X-Forwarded-For` only as many hops deep as `TRUSTED_PROXY_COUNT` says.
Behind a load balancer with the setting at 0, every caller "is" the load
balancer, and a utility that fills in Allowed addresses either locks itself out
or lets everybody in. Nothing on screen can show which; this can.

TWO WAYS TO USE IT
------------------
1. **Read what the server recorded for real sign-ins** (the default): the last
   `--limit` sessions with the address `client_ip` stored for each, beside the
   setting in force. Sign in yourself from a known address, then run this: the
   newest row must show YOUR public address. If it shows a private
   `10.x`/`172.16-31.x`/`192.168.x` address, the server is seeing a proxy and
   `TRUSTED_PROXY_COUNT` is too low.
2. **Try a header** (`--remote-addr` and `--xff`): prints what `client_ip`
   answers for that request under the current setting, so a line copied from
   the load balancer's access log can be checked without a deploy.

It prints no email in full and no session id.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.identity.auth import client_ip
from apps.identity.models import Session


class Command(BaseCommand):
    help = "Show which client address the server sees (read-only; BR-IDN-020)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--remote-addr", default=None)
        parser.add_argument("--xff", default=None, help="an X-Forwarded-For value to try")

    def handle(self, *args, **options):
        trusted = getattr(settings, "TRUSTED_PROXY_COUNT", 0) or 0
        self.stdout.write(f"TRUSTED_PROXY_COUNT = {trusted}")
        if options["remote_addr"] is not None or options["xff"] is not None:
            meta = {"REMOTE_ADDR": options["remote_addr"] or ""}
            if options["xff"]:
                meta["HTTP_X_FORWARDED_FOR"] = options["xff"]
            seen = client_ip(SimpleNamespace(META=meta))
            self.stdout.write(
                f"REMOTE_ADDR={meta['REMOTE_ADDR'] or '-'}  "
                f"X-Forwarded-For={options['xff'] or '-'}  ->  client_ip={seen or '-'}"
            )
            return
        rows = Session.objects.order_by("-created_at").values_list("created_at", "ip")[
            : max(1, options["limit"])
        ]
        self.stdout.write("newest sign-ins, the address the server recorded:")
        for created_at, ip in rows:
            self.stdout.write(f"  {created_at:%Y-%m-%d %H:%M:%S}Z  {ip or '-'}")
