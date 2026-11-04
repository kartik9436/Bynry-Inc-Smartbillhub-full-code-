# ── Trace ──────────────────────────────────────────────
# Rules:    BR-NOT-006 as amended 2026-10-29 · decision log 2026-10-29 *"A
#           message goes in the customer's preferred language (PO, option B)"*
#           — SUPERSEDES `OQ-CUS-12619` (a) for messages · BR-BIL-025 (the
#           variant ladder) · BR-BIL-026 (a pin is never re-resolved)
# Change:   CR-199-BRC10 lane TPL-SRV-LANG (task S8)
# ───────────────────────────────────────────────────────
"""**WHICH LANGUAGE A MESSAGE TO A CUSTOMER IS ASKED FOR** — one answer, used by
every writer.

PO, verbatim, 2026-10-29: *"Question: which language should messages be sent
in? - B"* — option (B), *messages follow her choice*. The worked case put to
the PO: Rosa Pemberton, at an English-default utility, chose Español. Springfield
has published a Spanish *Bill ready* → her bill email is Spanish. Springfield
has published no Spanish past-due reminder → her reminder is English.

So the ladder, per message CLASS (the answer differs class by class, which is
why it cannot be read once per account):

  1. the customer's stated language, exactly (`es-MX`), where the utility has
     PUBLISHED wording of this class in it;
  2. its base language (`es-MX` → `es`) — the same language, the judgment the
     decision log recorded for New Connection letters on 2026-10-02;
  3. otherwise the UTILITY's default language — `BR-NOT-006`'s existing
     fallback, and what every message went in from 2026-09-23 to 2026-10-29.

The template resolver is then asked for that ONE language and walks its own
`BR-BIL-025` order exactly as before (category → `default`), so this module
never picks a variant and never invents one; it only decides what to ASK FOR.
"Published" is the resolver's own answer, never a guess beside it — a class
counts as published in a language only when `template_service.resolve` itself
lands on a variant in that language, so the language chosen here and the
variant pinned at queue cannot disagree.

⚠ **A PIN IS NEVER RE-ASKED.** Nothing here runs for a row that already holds
a pinned version (`services._pinned` returns those untouched), so a reprint or
a resend renders the language its row was pinned in, whatever the customer has
chosen since (`BR-BIL-026`).

This generalises `apps.metering.connection_messages._letter_language`
(`DEF-CUS-9195`, 2026-10-02), which did exactly this for New Connection letters
alone; that narrowing is now the rule.
"""

from __future__ import annotations

from typing import Any


def _tries(stated: str | None) -> list[str]:
    code = (stated or "").strip()
    if not code or code == "default":
        return []
    out = [code]
    base = code.split("-")[0]
    if base and base != code:
        out.append(base)
    return out


def published_in(
    code: str, *, language: str, category: str | None = None, on_date: Any = None
) -> bool:
    """Does the resolver's OWN answer for `code` land on a variant in `language`?

    A refusal (nothing published at all) is *no*. An account override is not
    consulted here — an override wins outright inside the resolver whatever
    language is asked for, so it cannot change this answer's consequence."""
    from apps.notifications import template_service

    try:
        found = template_service.resolve(
            code=code, category=category, language=language, on_date=on_date
        )
    except template_service.TemplateRefused:
        return False
    return str(getattr(found, "language", "") or "").lower() == language.lower()


def language_for(
    code: str | None,
    *,
    stated: str | None,
    utility: str | None,
    category: str | None = None,
    on_date: Any = None,
) -> str | None:
    """The language to ASK the resolver for, for message class `code`.

    `stated` is the customer's preference (the account's, or an applicant's
    before an account exists); `utility` is the utility's default language —
    the fallback and, when `stated` is blank, the whole answer. `None` back
    means the utility never set one; the resolver then takes the `default`
    variant, exactly as before."""
    if not code:
        return utility
    for one in _tries(stated):
        if utility and one.lower() == utility.lower():
            return utility
        if published_in(code, language=one, category=category, on_date=on_date):
            return one
    return utility


def account_language(account_id: Any) -> str | None:
    """The account's `preferred_language`, read through customers' own selector
    (`customers_seam.account_preferred_language`). `None` for no account, no
    preference, or a customers module that publishes no such read."""
    if account_id in (None, ""):
        return None
    from apps.notifications import customers_seam

    return customers_seam.account_preferred_language(account_id)


def customers_by_language() -> dict[str, Any]:
    """How many of this utility's accounts prefer each language — the figure
    the Templates screen prints beside a variant's language (*"Español · 312
    customers"*, drawing image 16), because since 2026-10-29 that variant is
    what those customers receive.

    One grouped statement over accounts (`customers_seam.
    account_counts_by_language`), so it is an AGGREGATE and pagination does not
    apply (`NFR-3` governs lists; this is a fold, and it stays one statement at
    40,000 accounts — `NFR-5`, nothing here caps a tenant).

    * The rows are the utility's SWITCHED-ON languages, exactly the list the
      *New variant* picker offers (`template_variants.offered_languages`, lane
      TPL-SRV-VAR's derivation of A4 B: the utility's own language, every
      language it writes a variant in, every language a customer chose). Each
      row carries the picker's own `value` (`default` for the utility's
      language), so the screen joins a variant to its count without guessing.
    * Accounts stating NO preference — and accounts whose preference IS the
      utility's language — are counted on the utility's row: they receive
      exactly that. `no_preference` on that row says how many stated nothing.
    * A stored code the picker does not list is still a row, never dropped, so
      the rows always sum to `total` (law 7: a count that silently excludes part
      of its scope reads as complete).
    * Codes are exact: `es-MX` and `es` are separate rows. An `es-MX` account
      receives `es` wording when only `es` is published (`language_for`), so a
      screen summing for a variant adds the base language's regional rows.
    """
    from apps.notifications import customers_seam, template_variants, tenancy_seam
    from apps.notifications import template_models as tm

    default = tenancy_seam.tenant_default_language()
    counts = customers_seam.account_counts_by_language()
    unstated = int(counts.pop(None, 0) or 0)
    own = int(counts.pop(default, 0) or 0) if default else 0
    offered = [
        row for row in template_variants.offered_languages() if row["value"] != tm.VARIANT_DEFAULT
    ]
    listed = {str(row["code"]) for row in offered}
    rows: list[dict[str, Any]] = [
        {
            "value": tm.VARIANT_DEFAULT,
            "language": default,
            "accounts": unstated + own,
            "is_default": True,
            "no_preference": unstated,
        }
    ]
    for row in offered:
        code = str(row["code"])
        rows.append(
            {
                "value": str(row["value"]),
                "language": code,
                "accounts": int(counts.get(code, 0) or 0),
                "is_default": False,
                "no_preference": 0,
            }
        )
    for code in sorted(str(one) for one in counts if str(one) not in listed):
        rows.append(
            {
                "value": code,
                "language": code,
                "accounts": int(counts[code] or 0),
                "is_default": False,
                "no_preference": 0,
            }
        )
    return {
        "default_language": default,
        "languages": rows,
        "total": sum(row["accounts"] for row in rows),
    }
