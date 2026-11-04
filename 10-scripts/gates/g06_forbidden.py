"""G6 - forbidden-pattern greps (B12 r2 / hard rules HR-2..5 + module boundaries).

Line-by-line scan of 06-backend/apps/**/*.py (comment-only lines skipped):

1. float on money  — `float(` on a line mentioning a money field
   (amount/total/balance/price/rate — simple heuristic, case-insensitive). HR-2.
2. raw SQL UPDATE/DELETE naming an immutable TABLE
   (invoices, invoice_lines, payments, journal_entries, journal_lines). HR-4.
2b. Django ORM `.update(` / `.delete(` on a line naming an immutable MODEL
   (Invoice, InvoiceLine, Payment, JournalEntry, JournalLine). HR-4, and see
   WHY 2b EXISTS below — it is the commonest real-world shape of the violation
   and rule 2 has never been able to see it.
3. wall-clock time (`datetime.now()` / `timezone.now()`) anywhere in the
   rating/billing/ledger/payments apps — event-time law BR-TEN-043.
4. cross-module model imports: `from apps.<X>.models import` inside apps/<Y>/
   where X != Y — cross-module data flows through the owning module's
   service/selector or the reviewed FK set (B2 §2, B8 layering).
5. `.objects.` in api.py — api is thin; data access goes through
   selectors/services (B8 layering).
6. **DB-17** — `custom_data` (tenant-defined data) anywhere under
   `apps/rating/`, and under `apps/billing/`·`apps/ledger/`·`apps/payments/`
   outside the ONE allowlisted module. BR-TEN-048 / B2 r17.3 / B12 r7.1.
   NARROWED 2026-10-02 for `apps/payments/` (CR-161-BRC10 W5): the capture and
   display — `custom_values.py`, the migration adding the column, and the
   named statements in `DB17_STATEMENT_ALLOW` — and nothing else.

Every hit = FAIL with file:line. These are deliberately dumb greps: cheap,
explainable, and hard to sneak past (B12 r2 "who watches the watchers").

WHY 2b EXISTS, AND WHY IT IS A SEPARATE RULE FROM 2 (DEF-030 + DEF-056)
----------------------------------------------------------------------
Rule 2 fires on a line containing the word UPDATE or DELETE **and** an immutable
TABLE name — lowercase, plural, the DB names. Django code does not contain those
strings: it names MODELS. `Invoice.objects.filter(pk=1).update(total=0)`
lowercases to `...invoice.objects...` and the substring `invoices` is not in it.
So for months the single most likely way a developer actually mutates an issued
invoice from Python was invisible to the gate whose whole job is hard rule 4 —
raw SQL was caught, the ORM was not — while this file's own docstring claimed
that `.update(` and `.delete()` "all still fail, and that was PROVED". They were
never covered. That false claim lived INSIDE the guard, which is hard-won law 1
turned on the guards themselves.

Widened 2026-08-15, as its own change with its own red-proof (the precedent
DEF-030 set and DEF-041's prevention column restates). PROVED RED before being
trusted: an ORM `.update()` on an issued invoice was written into
apps/billing/issue.py, G6 was run, and it FAILED naming that line — where the
identical tree without rule 2b passed. The transcript is in this lane's report
and in 12-governance/02-decision-log.md 2026-08-15.

WHAT 2b CANNOT DO, stated so nobody assumes otherwise: no static check can tell
a DRAFT row from an ISSUED one. A draft invoice is legitimately editable and
legitimately deletable (BR-BIL-004: `IF OLD.status = 'draft' THEN RETURN NEW`),
so every legitimate ORM write in the billing write path looks exactly like a
violation to this rule. That is why the exceptions below are per-STATEMENT and
never per-path: a path-wide pass would silently cover every FUTURE ORM write in
billing's write stage, which is the money path this rule most exists to protect.
The database-level guarantee sits underneath either way — the immutability
TRIGGERS refuse an issued-row UPDATE regardless of how it is issued — so 2b's
job is to stop a draft-shaped mistake reaching review unnoticed, not to be the
last line of defence.
"""
import sys
import re

import common

MONEY_WORDS = ("amount", "total", "balance", "price", "rate")
IMMUTABLE_TABLES = ("invoices", "invoice_lines", "payments", "journal_entries", "journal_lines")
#: The MODEL names of the same five tables — rule 2b. Singular, CamelCase, and
#: matched as whole words so `PaymentMethod` / `PaymentAllocation` / `InvoiceRun`
#: do not collide with `Payment` / `Invoice`.
IMMUTABLE_MODELS = ("Invoice", "InvoiceLine", "Payment", "JournalEntry", "JournalLine")
IMMUTABLE_MODEL_RE = re.compile(r"\b(" + "|".join(IMMUTABLE_MODELS) + r")\b")
#: `.update(` / `.delete(` — the queryset write forms. `.save()` is deliberately
#: NOT here: a `.save()` on a model instance is how every draft in the codebase
#: is written and the rule would be 90% false positives, which is how a gate
#: stops being a gate (DEF-041's prevention column). `.update()`/`.delete()` are
#: the SET-shaped writes that skip `save()` hooks entirely, and they are the two
#: DEF-030/DEF-056 measured.
ORM_WRITE_RE = re.compile(r"\.(update|delete)\s*\(")
UPDATE_DELETE_RE = re.compile(r"\b(update|delete)\b", re.IGNORECASE)
#: A trigger's TIMING clause — `BEFORE UPDATE OR DELETE ON invoices` — names an
#: immutable table next to the words UPDATE and DELETE while doing the exact
#: opposite of a violation: it INSTALLS the prohibition this gate exists to
#: enforce. Added 2026-08-11 when apps/billing/migrations/0002 shipped the
#: hard-rule-4 triggers and this gate flagged them.
#:
#: Deliberately narrow. It matches only a line that STARTS with a trigger
#: timing keyword and names its table — `UPDATE invoices SET ...` and
#: `DELETE FROM invoices` still fail, and that was PROVED before this line was
#: trusted (see the gate's own self-check in 12-governance/02-decision-log.md
#: 2026-08-11). Widening this regex is how a real violation would get through,
#: so it should be widened by nobody.
#:
#: ⚠ CORRECTED 2026-08-11 (DEF-056) — this comment used to end that list with
#: "`.update(` and `.delete()` all still fail", AND THAT WAS NEVER TRUE. This
#: rule matches TABLE names (`invoices`, `payments`, lowercase, plural) and
#: Django ORM code names MODELS (`Invoice`, `Payment`), so
#: `Invoice.objects.filter(...).update(...)` has never matched and does not
#: match now. Measured over the whole backend: exactly ONE such line exists
#: today and it is legitimate. The claim is corrected here rather than the hole
#: closed, because widening a gate is its own change with its own red-proof and
#: its own review (the DEF-030 / DEF-041 precedent) — DEF-056 carries the
#: measurement and the proposed fix. A comment claiming a guarantee is not the
#: guarantee, and this one was inside the guard itself.
PROSE_UPDATE_DELETE_RE = re.compile(r"\bUPDATE\s*/\s*DELETE\b", re.IGNORECASE)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
TRIGGER_TIMING_RE = re.compile(
    r"^\s*(BEFORE|AFTER|INSTEAD\s+OF)\s+[\w\s]*\bON\b\s+\w+", re.IGNORECASE
)
CROSS_IMPORT_RE = re.compile(r"from apps\.(\w+)\.models import")
MONEY_PATH_DIRS = ("/rating/", "/billing/", "/ledger/", "/payments/")

# ── rule 2b's allow-list: per STATEMENT, never per path ─────────────────────
#: Keyed on (repo-relative path, the exact statement text with runs of
#: whitespace collapsed). NOT on a line number — line numbers drift with every
#: edit above them and an entry that drifts silently becomes a path-wide pass.
#:
#: An entry EXPIRES BY CONSTRUCTION: change the statement in any way and the
#: key stops matching, the gate fails, and the lane that changed it has to
#: restate why the write is legal. That is the same discipline as
#: partition_exceptions.txt and seam_known_gaps.txt — an exception may not
#: outlive the reason it was granted for.
#:
#: MEASURED over the whole backend on 2026-08-15 before this rule was trusted:
#: rule 2b produces exactly THREE hits and all three are below. (DEF-056's own
#: measurement, four days earlier, found ONE — the tree gained two while the
#: hole stayed open, which is the argument for closing it rather than
#: re-measuring it.) Each entry carries WHY IT IS LEGAL and WHAT WOULD MAKE IT
#: ILLEGAL AGAIN, because an allow-list without those is a silent permanent
#: exemption.
ORM_WRITE_ALLOW = {
    (
        "06-backend/apps/billing/stages/assemble_document.py",
        "models.InvoiceLine.objects.filter(invoice__in=existing).delete()",
    ): (
        "DRAFT lines only. This discards the lines of a draft being re-assembled "
        "before it is issued, which BR-BIL-023 / BR-BIL-004 expressly permit "
        "(`IF OLD.status = 'draft' THEN RETURN NEW` in billing_invoice_immutable). "
        "REVISIT IF: assemble_document ever runs against an invoice that is not a "
        "draft, or the `existing` queryset stops being restricted to drafts — at "
        "that point this deletes issued invoice lines and hard rule 4 is broken."
    ),
    (
        "06-backend/apps/billing/runs.py",
        "models.InvoiceLine.objects.filter(invoice__in=drafts).delete()",
    ): (
        "DRAFT lines only — `runs.discard_run` (DEF-BIL-9255) throws a DRAFT run "
        "away, and `drafts` is `invoices.filter(status=INVOICE_DRAFT)` after the "
        "function has refused any run holding a locked bill. The same BR-BIL-023 "
        "discard `assemble_document` makes; billing_invoice_immutable refuses a "
        "non-draft anyway. "
        "REVISIT IF: `drafts` stops being restricted to drafts, or the locked-bill "
        "refusal above it is removed."
    ),
    (
        "06-backend/apps/billing/corrections.py",
        "models.Invoice.objects.filter(tenant_id=tenant_id, pk=rebill.pk).update(",
    ): (
        "Stamps `corrects_invoice_id` on the REBILL while it is still a draft "
        "(PO 2026-08-12, OQ-120 — 'Nod to add the link on the new bill'). The 0017 "
        "trigger freezes that column at issue, so this write is only legal before "
        "issue and the database enforces that, not this gate. "
        "REVISIT IF: the stamp moves to after `issue_invoice`, or the filter stops "
        "naming the freshly-created rebill."
    ),
    (
        "06-backend/apps/billing/corrections.py",
        "models.Invoice.objects.filter(tenant_id=tenant_id, pk=invoice.pk).update(",
    ): (
        "Moves the ORIGINAL to `corrected`. `status` is the ONE column the "
        "immutability trigger permits to change after issue — its own message says "
        "'only status may change after issue' — so this is the ruled correction "
        "path, not an exception to it. "
        "REVISIT IF: this `.update()` ever carries a second keyword beside "
        "`status=`, which the trigger would refuse and this entry would wrongly "
        "wave past review."
    ),
}


def _normalize(line: str) -> str:
    """Collapse whitespace so re-indentation does not invalidate an allow key."""
    return " ".join(line.split())


def orm_immutability_violation(rel_path: str, line: str) -> str | None:
    """Rule 2b's verdict for ONE line of ONE file, or None.

    A pure function so the rule can be exercised directly by the self-test and
    by a test, rather than only by mutating the real tree — the same shape
    `db17_violation` takes, and for the same reason.
    """
    judged = INLINE_CODE_RE.sub("", line)  # prose quoting the rule is not the rule
    if not ORM_WRITE_RE.search(judged):
        return None
    if not IMMUTABLE_MODEL_RE.search(judged):
        return None
    key = (rel_path.replace("\\", "/"), _normalize(line))
    if key in ORM_WRITE_ALLOW:
        return None
    return (
        "ORM UPDATE/DELETE on an immutable model (HR-4 — corrections are new rows). "
        "A `.update()`/`.delete()` on Invoice/InvoiceLine/Payment/JournalEntry/"
        "JournalLine skips every save() hook and, on an issued row, is the violation "
        "hard rule 4 exists for. If this write is legal it is legal for a stated "
        "reason (a DRAFT, or the one mutable `status` column) — add it to "
        "ORM_WRITE_ALLOW in this gate with that reason AND the condition that would "
        "make it illegal again."
    )

# ── DB-17: tenant-defined data never enters a money path ────────────────────
# B2 addendum r17.3 states the law and B12 r7.1 makes it this gate's job:
# "`custom_data` is a merge-blocking failure under `apps/rating/` absolutely and
# under billing/ledger/payments outside one allowlisted module."
#
# It is a merge-blocking GREP and not a review note because BR-TEN-048 is the
# single constraint that lets tenant-defined fields exist at all without
# reopening the finance-signed B4/B5 math (PO ruling 2026-08-10 — "we may not
# able to use it for calculation"). A rule enforced by attention is a rule that
# holds until the first busy afternoon.
DB17_TOKEN = "custom_data"
#: Absolute ban — no allowlist, no exception. The rating engine is where B4's
#: signed arithmetic lives; a tenant-defined value reaching it is the failure
#: the whole feature was designed around.
DB17_ABSOLUTE_DIRS = ("/rating/",)
#: Banned EXCEPT in the one module US-BIL-028 names. These three are money
#: paths that legitimately need to COPY tenant data once — onto the immutable
#: invoice snapshot — and nowhere else.
DB17_GUARDED_DIRS = ("/billing/", "/ledger/", "/payments/")
#: The allowlist, and it is one entry on purpose (US-BIL-028: "billing gets ONE
#: allowlisted module whose only job is to copy values into the stamp. It
#: returns dict[str, str] and there is no typed accessor anywhere that returns a
#: number from it"). Adding a second entry is a schema-law change, not a
#: convenience — B2 r17.3 names this path in signed text.
DB17_ALLOWLIST = ("06-backend/apps/billing/custom_snapshot.py",)

# ── DB-17 NARROWED FOR PAYMENTS — CR-161-BRC10 W5, PO ruling 2026-10-02 ──────
#: R3, verbatim: *"Payments IN as capture-at-entry only"*; Part 2 row 14:
#: *"Can't be corrected afterwards; never used to apply the payment to bills"*.
#: BR-TEN-048 is UNCHANGED — what moves is HOW it is enforced in
#: `apps/payments/`: the ban opens for the CAPTURE (Record payment, S35) and the
#: DISPLAY (Payment detail, S33) and for nothing else. Allocation, deposit
#: batching, refunds, dunning and the ledger handoff stay banned, and
#: `self_test` pins a read in each of them as a failure on every run.
#:
#: Two whole files, because each exists for this and nothing else: the one
#: module that validates and reads the answers, and the migration that adds the
#: column. 🔒 human review (CR-161 §1, BR-TEN-048 row).
DB17_PAYMENTS_FILES = (
    "06-backend/apps/payments/custom_values.py",
    "06-backend/apps/payments/migrations/0046_cr161_w5_payment_custom_data.py",
)
#: …and, everywhere else in `apps/payments/`, per STATEMENT — the same
#: discipline as `ORM_WRITE_ALLOW`: keyed on the exact statement text (runs of
#: whitespace collapsed), never a line number, so changing a statement in any
#: way expires its entry and the lane that changed it restates why it is legal.
#: Each carries WHY and WHAT WOULD MAKE IT ILLEGAL. `self_test` fails an entry
#: whose statement no longer exists.
DB17_STATEMENT_ALLOW = {
    (
        "06-backend/apps/payments/models.py",
        "custom_data = models.JSONField(default=dict, blank=True)",
    ): "The column declaration. REVISIT IF: it gains a second meaning (a number, a money hint).",
    (
        "06-backend/apps/payments/services.py",
        "custom_data: Any = None,",
    ): "record_payment's parameter — the submitted answers, handed straight to custom_values.capture.",
    (
        "06-backend/apps/payments/services.py",
        "custom_data_screen: str | None = None,",
    ): "record_payment's parameter — the screen the answers were typed on (S35), for required-where-typed.",
    (
        "06-backend/apps/payments/services.py",
        "captured_at_entry = custom_values.capture(custom_data, screen=custom_data_screen)",
    ): "Validation BEFORE the transaction. REVISIT IF: the result is passed anywhere but the INSERT.",
    (
        "06-backend/apps/payments/services.py",
        "custom_data=captured_at_entry,",
    ): (
        "The INSERT's keyword — written at entry and never after (the trigger refuses an UPDATE). "
        "REVISIT IF: this statement moves out of `Payment.objects.create(` into an allocation, "
        "deposit, refund or ledger call."
    ),
    (
        "06-backend/apps/payments/settings_seam.py",
        'validate = _resolve("tenancy", "validate_custom_data_for", "services")',
    ): "The payments→tenancy seam to the ONE value validator; it reads no stored answer.",
    (
        "06-backend/apps/payments/payment_detail.py",
        '"custom_data": custom_values.for_display(payment),',
    ): "The S33 Payment detail payload — display only. REVISIT IF: any money figure is derived from it.",
}


#: A Django migration DEPENDENCY names another migration FILE, and one of those
#: files is `0004_r17_custom_data`. The token appears there as part of a
#: filename — it is not a read of tenant data, and every migration that depends
#: on that one carries it. Added 2026-08-11, when the payments lane's three
#: migrations failed DB-17 for citing a dependency they are REQUIRED to cite.
#:
#: Narrow on purpose: only a quoted string of the shape `"NNNN_..."` is removed,
#: which is Django's migration-name form and nothing else. A line that reads
#: `row["custom_data"]` or `values("custom_data")` is untouched and still fails,
#: and that was proved before this was trusted.
MIGRATION_NAME_RE = re.compile(r"""["']\d{4}_\w*["']""")


def db17_violation(rel_path: str, line: str) -> str | None:
    """The DB-17 verdict for ONE line of ONE file, or None.

    Split out as a pure function so the rule can be exercised directly by a
    test (tests/test_us_bil_028_custom_snapshot.py TC-7/TC-8) instead of only by
    mutating the real tree. The gate below calls exactly this — there is no
    second copy of the rule to drift.
    """
    line = MIGRATION_NAME_RE.sub("", line)
    if DB17_TOKEN not in line:
        return None
    rel = rel_path.replace("\\", "/")
    if rel in DB17_ALLOWLIST or rel in DB17_PAYMENTS_FILES:
        return None
    if (rel, _normalize(line)) in DB17_STATEMENT_ALLOW:
        return None
    slashed = f"/{rel_path}"
    if any(d in slashed for d in DB17_ABSOLUTE_DIRS):
        return (
            "DB-17 / BR-TEN-048 — tenant-defined `custom_data` in the RATING path. "
            "A custom field may never be read by the rating engine, set or adjust an "
            "invoice-line amount, or affect tax determination. There is no allowlist here."
        )
    if "/apps/payments/" in slashed:
        return (
            "DB-17 / BR-TEN-048 — tenant-defined `custom_data` in the payments money path. "
            "A payment's custom answers are captured at entry and shown on Payment detail "
            "ONLY (CR-161-BRC10 W5): read them through apps/payments/custom_values.py, never "
            "in allocation, deposit, refund, dunning or the ledger handoff."
        )
    if any(d in slashed for d in DB17_GUARDED_DIRS):
        return (
            "DB-17 / BR-TEN-048 — tenant-defined `custom_data` in a money path outside "
            f"the one allowlisted module ({DB17_ALLOWLIST[0]}). Copy it into the invoice "
            "snapshot there, as a string, or do not touch it."
        )
    return None


# ── Self-test (law 7): the guard must go RED on a real violation ────────────
#: Every exception this gate carries — the trigger-timing clause, the prose
#: `UPDATE/DELETE` pair, the inline-code strip, the migration-name strip — makes
#: the gate blinder on purpose. Each one was added because the gate fired on
#: text that STATED a rule rather than broke it. That is the right fix and it is
#: also exactly how a guard rots, so the shapes that must STILL bite are pinned
#: here and checked on every run: if an exception is ever widened enough to let
#: one of these through, the gate FAILS ITSELF rather than passing quietly.
#:
#: The ORM forms USED to be absent from this list, correctly, because they were
#: not covered (DEF-056). They are covered now — rule 2b — and they are pinned in
#: ORM_MUST_STILL_BITE below rather than here, because they run through a
#: different judging function.
MUST_STILL_BITE = (
    ("UPDATE invoices SET total = 0", "bare SQL UPDATE on an immutable table"),
    ("DELETE FROM payments WHERE id = 1", "bare SQL DELETE"),
    ('cur.execute("UPDATE journal_lines SET amount=0")', "UPDATE inside a string literal"),
    ("BEFORE UPDATE ON invoices; UPDATE invoices SET total=0", "real statement beside a trigger clause"),
    ("x = 1  # unlike `payments` elsewhere\nDELETE FROM payments", "real statement beside a quoted word"),
)
MUST_NOT_BITE = (
    ("**`payments` accepts no DELETE, in any status.** hard rule 4 names", "prose naming a backticked table"),
    ('(*"no UPDATE/DELETE on issued invoices, invoice lines, payments"*)', "prose quoting hard rule 4"),
)

#: Rule 2b's own law-7 pins. The first entry IS DEF-030's report, verbatim as the
#: defect stated it — "the ORM says Invoice" — and it is the line that passed
#: this gate for months. If a future exception is ever widened enough to let it
#: through again, the gate fails ITSELF rather than passing quietly.
ORM_MUST_STILL_BITE = (
    (
        "06-backend/apps/billing/issue.py",
        "    models.Invoice.objects.filter(pk=invoice_id).update(total=Decimal('0'))",
        "DEF-030's exact shape: a queryset UPDATE on an issued invoice",
    ),
    (
        "06-backend/apps/payments/services.py",
        "    Payment.objects.filter(id=payment_id).delete()",
        "a queryset DELETE of a recorded payment",
    ),
    (
        "06-backend/apps/ledger/posting.py",
        "    JournalLine.objects.filter(entry=entry).delete()",
        "a queryset DELETE of posted journal lines",
    ),
    (
        "06-backend/apps/billing/stages/assemble_document.py",
        "    models.InvoiceLine.objects.filter(invoice=other).delete()",
        "a DIFFERENT delete in an ALLOWLISTED FILE — the allow-list is "
        "per-statement, so the file's one exception must not cover this",
    ),
)
#: …and the shapes rule 2b must NOT bite, so the widening does not become the
#: 40-findings gate DEF-041's prevention column warns about.
ORM_MUST_NOT_BITE = (
    (
        "06-backend/apps/billing/services.py",
        "    # `Invoice.objects.filter(...).update(...)` is refused after issue",
        "a COMMENT quoting the banned shape (comment lines are skipped anyway)",
    ),
    (
        "06-backend/apps/billing/services.py",
        '    """Never `Invoice.objects.filter(pk=x).update(total=0)` — see BR-BIL-004."""',
        "a docstring quoting the banned shape in backticks",
    ),
    (
        "06-backend/apps/payments/services.py",
        "    PaymentMethod.objects.filter(tenant_id=t).delete()",
        "PaymentMethod is a tenancy lookup, not the immutable Payment table",
    ),
    (
        "06-backend/apps/billing/models.py",
        "    BillRun.objects.filter(pk=run_id).update(status='failed')",
        "BillRun is mutable — only the five immutable models are in scope",
    ),
)


#: DB-17's payments narrowing, pinned both ways (law 7). Each "must bite" is a
#: read in a path BR-TEN-048 keeps banned; the last is a different statement in
#: an allowed FILE — the allowance is per statement, so it must not cover it.
DB17_PAYMENTS_MUST_STILL_BITE = (
    (
        "06-backend/apps/payments/allocation.py",
        '    drawer = payment.custom_data.get("drawer")',
        "a read in ALLOCATION",
    ),
    (
        "06-backend/apps/payments/reconciliation.py",
        '    key = (day, method, payment.custom_data["drawer"])',
        "a read in DEPOSIT batching",
    ),
    ("06-backend/apps/payments/refunds.py", "    note = source.custom_data", "a read in REFUNDS"),
    ("06-backend/apps/payments/ladder.py", '    if account_payment.custom_data.get("vip"):', "a read in DUNNING"),
    (
        "06-backend/apps/payments/ledger_seam.py",
        "    memo = payment.custom_data",
        "a read in the LEDGER handoff",
    ),
    (
        "06-backend/apps/payments/services.py",
        "    allocate_payment(payment, custom_data=captured_at_entry)",
        "a DIFFERENT statement in an allowed file handing the answers to allocation",
    ),
)
DB17_PAYMENTS_MUST_NOT_BITE = (
    (
        "06-backend/apps/payments/custom_values.py",
        '    stored = getattr(payment, "custom_data", None)',
        "the capture/display module itself",
    ),
    (
        "06-backend/apps/payments/services.py",
        "                custom_data=captured_at_entry,",
        "the INSERT's keyword, re-indented",
    ),
)


def _judge_update_delete(line: str) -> bool:
    """The UPDATE/DELETE verdict for one line — the gate's own logic, once."""
    judged = TRIGGER_TIMING_RE.sub("", line, count=1)
    judged = PROSE_UPDATE_DELETE_RE.sub("", judged)
    judged = INLINE_CODE_RE.sub("", judged)
    return bool(UPDATE_DELETE_RE.search(judged) and any(t in judged.lower() for t in IMMUTABLE_TABLES))


def self_test() -> list[str]:
    """Blind spots this gate must not have. Empty list = every guard bites."""
    blind = []
    for line, why in MUST_STILL_BITE:
        if not any(_judge_update_delete(part) for part in line.split("\n")):
            blind.append(f"BLIND: {why} — a real violation would pass")
    for line, why in MUST_NOT_BITE:
        if _judge_update_delete(line):
            blind.append(f"FALSE POSITIVE: {why} — the gate fires on text stating the rule")
    for line, why in (
        ('row["custom_data"]["x"]', "DB-17 dict read"),
        ('qs.values("custom_data")', "DB-17 ORM values()"),
        ("amount = account.custom_data.get('x')", "DB-17 attribute read"),
    ):
        if not db17_violation("06-backend/apps/rating/engine.py", line):
            blind.append(f"BLIND: {why} — tenant data would reach the rating engine")
    if db17_violation("06-backend/apps/payments/migrations/0003_x.py", '("customers", "0004_r17_custom_data"),'):
        blind.append("FALSE POSITIVE: a migration dependency name is not a data read")
    # CR-161-BRC10 W5 — the payments narrowing must not reach a money path.
    for rel_path, line, why in DB17_PAYMENTS_MUST_STILL_BITE:
        if not db17_violation(rel_path, line):
            blind.append(f"BLIND (DB-17 payments): {why} — a custom answer would reach money")
    for rel_path, line, why in DB17_PAYMENTS_MUST_NOT_BITE:
        if db17_violation(rel_path, line):
            blind.append(f"FALSE POSITIVE (DB-17 payments): {why}")
    for (rel_path, statement), _reason in DB17_STATEMENT_ALLOW.items():
        path = common.REPO_ROOT / rel_path
        if not path.is_file() or not any(
            _normalize(ln) == statement for ln in common.read_text(path).splitlines()
        ):
            blind.append(
                f"STALE ALLOW (DB-17): {rel_path} no longer contains `{statement}` — "
                "restate why the new statement is legal, or delete the entry."
            )
    for rel_path in DB17_PAYMENTS_FILES:
        if not (common.REPO_ROOT / rel_path).is_file():
            blind.append(f"STALE ALLOW (DB-17): {rel_path} no longer exists")
    for rel_path, line, why in ORM_MUST_STILL_BITE:
        if not orm_immutability_violation(rel_path, line):
            blind.append(f"BLIND (rule 2b): {why} — a real hard-rule-4 violation would pass")
    for rel_path, line, why in ORM_MUST_NOT_BITE:
        if orm_immutability_violation(rel_path, line):
            blind.append(f"FALSE POSITIVE (rule 2b): {why}")
    # Every allow-list entry must still describe a line that EXISTS. A key that
    # matches nothing is an exemption for a statement nobody can find, and it
    # would quietly pre-authorise that exact text reappearing anywhere later.
    for (rel_path, statement), reason in ORM_WRITE_ALLOW.items():
        path = common.REPO_ROOT / rel_path
        if not path.is_file():
            blind.append(f"STALE ALLOW: {rel_path} no longer exists — delete its ORM_WRITE_ALLOW entry")
            continue
        if not any(
            _normalize(ln) == statement for ln in common.read_text(path).splitlines()
        ):
            blind.append(
                f"STALE ALLOW: {rel_path} no longer contains `{statement}` — the write "
                "changed, so its exemption expired. Re-read the new statement, restate "
                "why it is legal, and update the entry."
            )
    return blind


def run() -> tuple[str, str]:
    files = common.backend_code_files()
    if not files:
        return "SKIP", "06-backend/apps has no Python files yet"

    blind = self_test()
    if blind:
        return "FAIL", (
            f"self-test BLIND: {blind[0]}. A guard that cannot be shown to bite is "
            f"not a guard (hard-won law 7) — {len(blind)} shape(s) failed."
        )

    hits = []
    for path in files:
        rel_path = common.rel(path)
        parts = path.relative_to(common.BACKEND_APPS).parts
        own_module = parts[0] if len(parts) > 1 else ""
        in_money_path = any(d in f"/{rel_path}" for d in MONEY_PATH_DIRS)
        for lineno, line in enumerate(common.read_text(path).splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            where = f"{rel_path}:{lineno}"
            low = line.lower()
            if "float(" in low and any(w in low for w in MONEY_WORDS):
                hits.append(f"{where}: float() on a money field (HR-2 — Decimal only)")
            # Strip a trigger's timing clause before judging the line: the
            # clause itself is the prohibition being installed, but ANYTHING
            # ELSE on that line is still a statement and is still judged.
            # Skipping the whole line would let `BEFORE UPDATE ON invoices;
            # UPDATE invoices SET total=0` through — which it did, in the
            # first version of this exception, until the gate's own self-check
            # caught it.
            judged = TRIGGER_TIMING_RE.sub("", line, count=1)
            # `UPDATE/DELETE` — slash-joined — is PROSE. No SQL and no Python
            # spells a statement that way; it is how this repo's docstrings
            # quote hard rule 4's own wording ("no UPDATE/DELETE on issued
            # invoices, invoice lines, payments, journal entries"). Added
            # 2026-08-11, when the payments lane's immutability migration failed
            # this rule for QUOTING the rule it installs — the third time G6 has
            # fired on text describing a law rather than breaking one (DEF-043
            # was the first, on the clock rule, and its fix was applied to that
            # rule alone; this is the same class recurring because the fix was
            # not carried across).
            #
            # Surgical, and safe by construction: only the slash-joined pair is
            # removed. `UPDATE invoices SET`, `DELETE FROM payments`, `.update(`
            # and `.delete()` are all untouched and all still fail — proved
            # before this line was trusted, the same way TRIGGER_TIMING_RE was.
            judged = PROSE_UPDATE_DELETE_RE.sub("", judged)
            # And the SAME inline-code strip the clock rule below has had since
            # DEF-043. It was applied to that rule alone, and this is the cost:
            # a docstring reading "`payments` accepts no DELETE, in any status"
            # names an immutable table beside the word DELETE while stating the
            # prohibition. The fix was always general; only its application was
            # narrow. Carried across now so the next rule added here inherits it
            # rather than rediscovering it.
            judged = INLINE_CODE_RE.sub("", judged)
            if UPDATE_DELETE_RE.search(judged) and any(t in judged.lower() for t in IMMUTABLE_TABLES):
                hits.append(f"{where}: UPDATE/DELETE touching an immutable table (HR-4 — corrections are new rows)")
            # Inline-code spans are stripped before judging, for the same
            # reason and with the same caution as the trigger clause above:
            # this codebase quotes code in backticks, so a docstring EXPLAINING
            # that `timezone.now()` is banned matched the ban. It happened on
            # 2026-08-11 — G6 failed a selector whose docstring said "gate G6
            # bans `timezone.now()` in a money path", i.e. the gate fired on
            # prose describing the gate.
            #
            # WHAT THIS MUST NOT DO, and does not: skip the line. A real call
            # sitting beside a quoted one — `x = timezone.now()  # unlike
            # `timezone.now()` elsewhere` — still hits, because only the
            # backticked spans are removed and the rest of the line is judged.
            # A bare (unquoted) call inside a docstring still hits too, which
            # is deliberately conservative: prose that quotes code uses
            # backticks here, and prose that does not is indistinguishable from
            # code to any checker that is not a parser.
            judged_clock = INLINE_CODE_RE.sub("", line)
            if in_money_path and (
                "datetime.now()" in judged_clock or "timezone.now()" in judged_clock
            ):
                hits.append(f"{where}: wall-clock time in a money path (BR-TEN-043 event-time law)")
            cross = CROSS_IMPORT_RE.search(line)
            if cross and own_module and cross.group(1) != own_module:
                hits.append(f"{where}: imports apps.{cross.group(1)}.models from apps/{own_module}/ (module boundary, B2 §2)")
            if path.name == "api.py" and ".objects." in line:
                hits.append(f"{where}: ORM access in api.py — use selectors/services (B8 layering)")
            db17 = db17_violation(rel_path, line)
            if db17:
                hits.append(f"{where}: {db17}")
            orm = orm_immutability_violation(rel_path, line)
            if orm:
                hits.append(f"{where}: {orm}")
    if hits:
        return "FAIL", common.summarize(hits)
    return "PASS", f"0 forbidden patterns in {len(files)} backend files"


def main() -> int:
    """Run this gate from the command line.

    ⚠ ADDED 2026-08-25 (DEF-672). Sixteen gate modules defined `run()` and NO
    main block, so `python3 10-scripts/gates/<gate>.py` imported the module,
    defined a function and exited **0 with no output** — indistinguishable from
    a gate that ran and passed, to the eye and to `$?`. Two commit messages on
    this branch claim a G7 PASS obtained exactly that way.

    `run_gates.py` was never affected: it imports `run()` directly, which is why
    the real stack stayed honest while every direct invocation lied.
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
