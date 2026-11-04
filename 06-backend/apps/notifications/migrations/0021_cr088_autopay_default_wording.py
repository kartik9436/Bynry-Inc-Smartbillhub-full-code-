# ── Trace ──────────────────────────────────────────────
# Change:   CR-088 R.2 item 1 — PO ruling 2026-10-02 ("SEVEN PO ANSWERS IN ONE
#           MESSAGE" (1)), verbatim: *"update it"*.
# Rules:    BR-NOT-004 type ④ (the ACH authorization placeholder) · BR-BIL-026
#           (every edit is a NEW append-only version) · A19 rule 6 (every
#           template version is audit-logged) · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard-won law 14 (a per-tenant savepoint, proved on
#           PostgreSQL)
# Tests:    tests/test_cr088_autopay_default_wording_migration.py
# ───────────────────────────────────────────────────────
"""notifications 0021 — existing utilities' saved auto-pay wording says SMART360 Next.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-02 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

WHAT IT DOES, IN ONE SENTENCE
────────────────────────────────────────────────────────────────────────────
For every utility, where the LATEST saved version of an automatic-payment (ACH)
authorization template is still byte-for-byte the wording the platform offered
before `2.445.0` — the one that says *"SMARTBillHub gives you default wording
for every other document in this product."* — it saves ONE new draft version
whose only difference is that sentence reading *"SMART360 Next gives you …"*.

WHY ONLY A BYTE-IDENTICAL COPY
────────────────────────────────────────────────────────────────────────────
The PO chose option A as recommended: rewrite where staff never edited it; an
edited copy is left alone. There is no "touched" column on a template version,
so the CONTENT is the only evidence there is — the test `assets/0011` already
uses for a seeded name. A version that differs by a single byte is somebody's
own wording and is not ours to change, even where it still says SMARTBillHub;
the migration LOGS each such variant (tenant, class, category, language,
version) so the edited copies are listed rather than silently skipped.

The default compared against is `2.445.0`'s seed with that one sentence put
back. Every other input to the body — the placeholder marker and the eight items
the utility must get from its bank (`catalogs.CONTRACT_INPUT_REQUIREMENTS`) — has
not moved since 2026-08-29 (`git log -L` on both, checked rather than assumed),
and history before that date is not in this clone. A copy saved from an older
wording is therefore not byte-identical and is left alone, which is the safe
direction for a miss.

WHY A NEW VERSION AND NOT AN UPDATE IN PLACE
────────────────────────────────────────────────────────────────────────────
BR-BIL-026: an edit creates a new row. `template_service.save_draft` never
updates a body, and `0006`'s trigger refuses an UPDATE of a published or
archived body outright. An in-place UPDATE would work on a draft and fail on a
published copy, and on a draft it would rewrite the history the version chain
exists to keep. So this does exactly what a clerk pressing Save would do: the
next version number, status `draft`, the same subject, preheader and effective
date, `created_by` NULL (no person wrote it — `templates_api._author_label`
reads that as *platform seed*), and one `template.saved` audit row naming the
changed field and the version it changed from (A19 rule 6, hard rule 7's shape).
A PUBLISHED placeholder stays published — publishing needs a date only a person
chooses (BR-NOT-002) — and the new draft sits above it until somebody publishes.
Nothing can be sent from either: the renderer refuses the placeholder marker.

IDEMPOTENT
────────────────────────────────────────────────────────────────────────────
After one pass the latest version reads the new wording, so it no longer
matches and a second pass writes nothing.

ROLLBACK (`migrate notifications 0020`)
────────────────────────────────────────────────────────────────────────────
Deletes exactly the drafts this migration wrote: latest in its chain, status
`draft`, `created_by` NULL, body the new wording, and the version below it the
old wording. An unpinned draft deletes (`0006`/`0017`); a pinned one cannot, and
nothing can pin a placeholder because nothing can render one. Each delete writes
a `template.draft_deleted` audit row. The forward audit rows stay — `audit_log`
is append-only — and the old wording was never removed, so the chain reads as it
did. A draft somebody saved ON TOP of ours is left alone, because ours is then
no longer the latest.

RLS AND FAILURE
────────────────────────────────────────────────────────────────────────────
`tenants` is a platform table and is listed first; every other read and write
happens with `app.tenant_id` set to that tenant (hard rule 1). Each tenant is
its own SAVEPOINT (hard-won law 14): on PostgreSQL one refused statement aborts
the whole transaction, so without it one bad tenant would roll back every other
tenant's change, and the sqlite suite cannot show that.
"""

import logging

from django.db import migrations, transaction

logger = logging.getLogger("smartbillhub.notifications")

CODE = "contract_autopay_authorization"
OLD_NAME_SENTENCE = (
    "SMARTBillHub gives you default wording for every other document in this product."
)
NEW_NAME_SENTENCE = (
    "SMART360 Next gives you default wording for every other document in this product."
)
JOB = "notifications 0021 · CR-088 R.2 item 1 · PO 2026-10-02 'update it'"
AUDIT_ENTITY = "notification_template_version"
AUDIT_SAVED = "template.saved"
AUDIT_DELETED = "template.draft_deleted"

#: The nil sentinel, never `''` (assets/0003, OQ-354).
NO_TENANT = "00000000-0000-0000-0000-000000000000"

#: `2.445.0`'s seeded body, FROZEN here rather than imported, for `assets/0011`'s
#: reason: a migration must keep doing what it did when the seed later moves. A
#: test pins it to `seed_templates.CONTRACT_AUTOPAY_PLACEHOLDER_BODY` today.
NEW_BODY = """\
[[PLACEHOLDER — NOT VALID UNTIL YOUR UTILITY REPLACES THIS TEXT]]

{utility_name}
{utility_address}
{support_phone} · {support_email}

AUTOMATIC PAYMENT (ACH) AUTHORIZATION — PLACEHOLDER. DO NOT SEND THIS TO A
CUSTOMER AND DO NOT ASK ANYONE TO SIGN IT.

SMART360 Next gives you default wording for every other document in this product.
It does not give you wording for this one, and that is deliberate. What an
authorization for recurring ACH debits has to say is prescribed by the NACHA
Operating Rules, which this platform does not hold. Wording we wrote by
inference would look official and could be wrong, and this is the document where
that costs you rather than us.

While this text is still here the product REFUSES to render this document, so it
cannot reach a customer by accident.

WHAT TO TAKE TO YOUR BANK. Ask your bank (your ODFI) and your own counsel for
wording that settles each of these, then replace everything on this page with it:

1. Your utility's legal name exactly as it will appear on the customer's bank statement, and the company identification number your bank issued you for collecting payments.

2. The sentence that says the customer authorises you to take recurring electronic (ACH) debits from the bank account they name, and that the amount VARIES because a utility bill varies — including how you tell them each amount before you take it, and how long before.

3. When the debit is taken: the day of the month, or the number of days after the bill date, and what you do when that day falls on a weekend or a bank holiday.

4. How the customer cancels: what they have to send you, where they send it, and how far ahead of a debit it has to reach you for that debit to stop.

5. What happens when a debit is returned unpaid: whether you charge for it (that amount is your own charge code, not ours) and whether you try again.

6. The customer's rights if a debit was not authorised, in the wording your bank or your counsel gives you.

7. That the customer gets a copy of what they signed, and how long you keep the signed authorisation after it ends — your bank will tell you the period they require.

8. The signature block: the customer's name, their signature, the date, the bank account type (checking or savings), and the account and routing numbers they write in themselves. Never merge a bank number from this platform.

WHEN YOU HAVE THE WORDING: paste it here, delete the marker line at the top of
this page, choose the date it takes effect, and publish. The tokens available to
you are {customer_name}, {account_no}, {service_address},
{payment_method}, {today}, {customer_signature} and {date}, plus your own
utility details. Bank routing and account numbers are written in by the customer
on the form and are never merged from this platform.

Customer: {customer_name} · account {account_no}
Signature: {customer_signature}          Date: {date}"""
OLD_BODY = NEW_BODY.replace(NEW_NAME_SENTENCE, OLD_NAME_SENTENCE)


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    """Hard rule 1. On sqlite there is no RLS and no `set_config`; the same ORM
    path runs without it."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _audit(apps, tenant_id, action, version_row, after):
    apps.get_model("audit", "AuditLog").objects.create(
        tenant_id=tenant_id,
        actor_user_id=None,  # an unnamed system job, named in `after` (BR-AUD-003)
        action=action,
        entity_type=AUDIT_ENTITY,
        entity_id=version_row.pk,
        before=None,
        after=after,
    )


def _latest_two(Version, tenant_id, template):
    return list(
        Version.objects.filter(tenant_id=tenant_id, template=template).order_by("-version")[:2]
    )


def _variant(template):
    return f"{template.code}/{template.category}/{template.language}"


def rewrite_unedited(apps, schema_editor):
    Template = apps.get_model("notifications", "NotificationTemplate")
    Version = apps.get_model("notifications", "NotificationTemplateVersion")
    connection = schema_editor.connection
    rewritten = left = 0
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        try:
            # ⚠ THE SAVEPOINT IS THE ONLY OPTION, NOT THE TIDY ONE (law 14).
            with transaction.atomic():
                for template in Template.objects.filter(tenant_id=tenant_id, code=CODE):
                    chain = _latest_two(Version, tenant_id, template)
                    if not chain:
                        continue
                    latest = chain[0]
                    if latest.body != OLD_BODY:
                        if "SMARTBillHub" in latest.body:
                            left += 1
                            logger.info(
                                "notifications 0021: tenant %s %s v%s still names SMARTBillHub "
                                "and was EDITED by the utility, so it is left exactly alone",
                                tenant_id,
                                _variant(template),
                                latest.version,
                            )
                        continue
                    row = Version.objects.create(
                        tenant_id=tenant_id,
                        template=template,
                        version=latest.version + 1,
                        status="draft",
                        subject=latest.subject,
                        preheader=latest.preheader,
                        body=NEW_BODY,
                        effective_from=latest.effective_from,
                        created_by=None,
                    )
                    _audit(
                        apps,
                        tenant_id,
                        AUDIT_SAVED,
                        row,
                        {
                            "code": template.code,
                            "category": template.category,
                            "language": template.language,
                            "version": row.version,
                            "status": "draft",
                            "effective_from": (
                                latest.effective_from.isoformat() if latest.effective_from else None
                            ),
                            "changed_fields": ["body"],
                            "changed_from_version": latest.version,
                            "source": JOB,
                        },
                    )
                    rewritten += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0021: tenant %s could not be updated; every other tenant is "
                "unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info(
        "notifications 0021: %d auto-pay template(s) given the SMART360 Next wording; "
        "%d edited copy(ies) still naming SMARTBillHub left alone",
        rewritten,
        left,
    )


def remove_rewrites(apps, schema_editor):
    Template = apps.get_model("notifications", "NotificationTemplate")
    Version = apps.get_model("notifications", "NotificationTemplateVersion")
    connection = schema_editor.connection
    removed = 0
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                for template in Template.objects.filter(tenant_id=tenant_id, code=CODE):
                    chain = _latest_two(Version, tenant_id, template)
                    if len(chain) < 2:
                        continue
                    ours, below = chain
                    if not (
                        ours.status == "draft"
                        and ours.created_by is None
                        and ours.body == NEW_BODY
                        and below.body == OLD_BODY
                    ):
                        continue
                    _audit(
                        apps,
                        tenant_id,
                        AUDIT_DELETED,
                        ours,
                        {
                            "code": template.code,
                            "category": template.category,
                            "language": template.language,
                            "version": ours.version,
                            "source": JOB + " — reversed",
                        },
                    )
                    ours.delete()
                    removed += 1
        except Exception:  # pragma: no cover — logged, and the other tenants go on
            logger.exception(
                "notifications 0021 reverse: tenant %s could not be reverted; every other "
                "tenant is unaffected (per-tenant savepoint)",
                tenant_id,
            )
    _set_tenant(connection, NO_TENANT)
    logger.info("notifications 0021 reverse: %d draft(s) removed", removed)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0020_rls_def_not_5632_suppressed_addresses"),
        ("audit", "0007_us_aud_010_audit_actor"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rewrite_unedited, remove_rewrites),
    ]
