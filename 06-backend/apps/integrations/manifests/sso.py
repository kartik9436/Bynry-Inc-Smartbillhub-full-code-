"""Single sign-on (Okta / Azure AD) — staff sign in with the identity provider they already have (Identity · COMING SOON v2).

BR-INT-013: SSO is v2; per-tenant identity with no cross-tenant SSO in v1,
sequenced with 2FA-v2. The card says *Coming soon · v2* and the server refuses
a connect. Declared as a redirect (the identity provider sends the person back
to us) with a self-declared conformance to OpenID Connect — the WORDS a screen
may use about that claim are `OQ-INT-1483` and are not decided here.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.sso.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Conformance,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
)

MANIFEST = Manifest(
    key="sso",
    category="identity",
    display_name="Single sign-on",
    summary="Staff sign in with the identity provider you already have.",
    disposition=Disposition(kind="coming_soon", wave="v2"),
    auth=Auth(mode="token_exchange", placement="redirect"),
    fields=(
        Field(name="metadata_url", label="Identity provider address", kind="url"),
        Field(name="sign_in", label="Sign in with your identity provider", kind="redirect"),
    ),
    conformance=Conformance(
        standard="OpenID Connect",
        claim="self_declared",
        evidence="Authorization code flow against the provider's published metadata.",
    ),
    operations=(
        Operation(
            name="sign_in",
            # INWARD, and the tightest ceiling on any connector: thirty a
            # minute. This product is run by 10-20 staff, so thirty sign-ins a
            # minute is far above real use, and the number a brute-forcer gets
            # is the number that matters here.
            rate_limit_per_minute=30,
            label="Sign in",
            description="The identity provider sends a signed-in person back to us.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="inline",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            respond_after="authenticate",
            envelope_status={"ok": 200, "refused": 401},
        ),
    ),
)
