"""BYO email (A15/B7 addendum, CONFIRMED): tenants connect their own mailbox
(Google OAuth / M365 OAuth / SMTP). All customer email sends from the tenant's
address. No shared sending engine exists by design.

⚠ NOTHING IS IMPLEMENTED HERE AND NOTHING SHOULD BE. The paragraph above is a
RULE, and the rule is now enforced somewhere a gate can see it: the connection
itself belongs to `apps/integrations` (per-tenant provider config, secrets
encrypted per B7), and the send goes through the ONE adapter seam in
`apps/notifications/provider_seam.py`. A second mailbox client living here would
be the shared sending engine A15's addendum exists to forbid.

WHERE THE RULE BITES TODAY, so the absence is findable rather than assumed
handled: `provider_seam.channel_route` refuses to dispatch a channel with no
provider and its refusal text says *"NO fallback shared sender: every customer
email goes from the utility's own address or it does not go"*. A test asserts
it. Email dispatch is deferred to W6 either way (OQ-073 CLOSED), so on this
deployment the rows are written and rest `queued`.
"""
