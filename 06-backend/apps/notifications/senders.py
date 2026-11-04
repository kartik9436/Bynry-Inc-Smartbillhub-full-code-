"""SUPERSEDED SCAFFOLDING — the provider seam is `provider_seam.py`.

This file was created with the module skeleton and its docstring described the
seam it would one day hold: *"Provider seams for SMS (Twilio), print/mail (Lob),
e-signature (DocuSign) — B7. Interface-first; provider behind per-tenant config;
never hardcoded in business logic."* All of that is now TRUE and none of it is
here — it is `apps/notifications/provider_seam.py`, which US-NOT-003 landed on
2026-08-15 as TD-8's ONE seam.

The old text is corrected rather than left to rot (hard-won law 1: a comment
claiming a guarantee is not the guarantee). Two files each describing themselves
as the provider seam is how the next reader adds an adapter to the one nothing
calls.

STILL TRUE AND STILL UNBUILT: `apps/integrations` holds three docstrings and no
code, so no adapter exists for ANY channel — print included — and this
deployment dispatches nothing. That gap is parked in
`10-scripts/gates/seam_known_gaps.txt` with a live guard and reported on every
dispatch cycle.

DocuSign is the one thing named above that provider_seam.py does NOT cover: the
e-signature envelope belongs to contract generation (US-NOT-012, EP-NOT-03) and
is a different seam with a different shape — an envelope and a signature event,
not a batch of messages. It is unbuilt and unclaimed.
"""
