# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-020 (deposit batches — the tables the S37 list reads)
#           Screens: S37 · S38 · S39 · S40
# Rules:    BR-PAY-025 (deposit batches group day × method) · CLAUDE.md rule 1
#           (every table below is tenant-scoped and RLS-forced by
#           migrations/0005)
# Tests:    06-backend/tests/test_us_pay_020_023_bank_rec.py
# Impacts:  apps/payments/bankrec_models.py (the six EP-PAY-06 model classes
#           this makes visible to the app registry) · apps/payments/migrations
#           (which cannot see a model the registry has not loaded)
# ───────────────────────────────────────────────────────
"""payments AppConfig — model registration only, no logic.

It exists for one reason, stated plainly because a reader will otherwise wonder
why payments suddenly needs an AppConfig when it never did: Django imports
`apps.payments.models` and nothing else, and **the six EP-PAY-06 tables are not
in that file**. They are in `bankrec_models.py`, because another lane held
`models.py` while this one was written (the NSF/refund path) and two lanes in one
models module is how a migration graph forks.

`ready()` imports the module, so the model classes register themselves exactly as
they would have from `models.py`. Folding them back in later is a move, not a
redesign — and until then this import is what makes `makemigrations` see them at
all. REPORTED in the lane report rather than left as a surprise.

Payments registers exactly ONE reference-data handler, `bank_accounts`
(`apps/payments/lookups.py`, added 2026-08-28 for DEF-203): the table is
payments' own, so payments validates and writes it while tenancy renders the
card (BR-TEN-031). Its `payment_methods` list is different and unchanged — that
one is hosted AND handled by tenancy (see `apps/tenancy/models.PaymentMethod`).
No exporter and no signal belong here.
"""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = "apps.payments"
    label = "payments"  # unchanged from Django's default, so no migration moves
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Imported for its side effect: defining a model registers it.
        from apps.payments import bankrec_models  # noqa: F401

        # Same reason, second lane (2026-08-11): EP-PAY-04's collections
        # tables and EP-PAY-05's plan tables are in `collections_models.py`
        # because `models.py` was held elsewhere. `payment_plans` is what
        # the S24 wizard has been refusing to save into since the customers
        # lane shipped its arithmetic — hard-won law 2, closed by this
        # import plus the service the seam resolves.
        from apps.payments import collections_models  # noqa: F401

        # Same reason, third lane (CR-059 CS-12/CS-27, 2026-09-03): the
        # `payment_tenders` class is in `tender_models.py` because `models.py`
        # was held by another lane, and a model the registry has not loaded is
        # a table `makemigrations` cannot see.
        from apps.payments import tender_models  # noqa: F401

        # Same reason, fourth lane (CR-094-BRC01 lane H, 2026-09-15): the
        # `counter_receipts` class is in `counter_receipt_models.py` because
        # five lanes are live in this wave and two of them hold `models.py`.
        # A model the registry has not loaded is a table `makemigrations`
        # cannot see — and this one holds money taken at a counter.
        from apps.payments import counter_receipt_models  # noqa: F401

        # Same reason, fifth lane (CR-135-BRC07, the payments blueprint's
        # phase 0, 2026-09-22): `counter_sessions` is in
        # `counter_session_models.py` for the same reason the four above are in
        # theirs — a model the registry has not loaded is a table
        # `makemigrations` cannot see, and `models.py` is held by other lanes.
        # ⚠ Six phase 2 screens wait on this ONE table, so an import that
        # silently went missing would look exactly like the table never having
        # been built.
        from apps.payments import counter_session_models  # noqa: F401

        # Same reason, sixth lane (CR-139-BRC07, the payments blueprint's
        # phase 5, 2026-09-23): `settlements` and `settlement_members` are in
        # `settlement_models.py` because `models.py` is held by phase 3's lane
        # and two lanes in one models module is how a migration graph forks.
        # ⚠ Both tables carry MONEY, so a registry that silently did not see
        # them would look exactly like a schema that was never written — and
        # `makemigrations --check` is the thing that proves it did.
        from apps.payments import settlement_models  # noqa: F401

        # Same reason, seventh (CR-171-BRC10 lane RULINGS, 2026-10-05,
        # `OQ-CUS-12790` (a)): `deposit_releases` — a held deposit handed back
        # to the customer's credit — is in `deposit_release_models.py`.
        from apps.payments import deposit_release_models  # noqa: F401

        # DEF-203 (2026-08-28) — payments' ONE reference-data handler. The
        # trailer below said "Payments registers no reference-data handler"
        # and that sentence is now amended rather than deleted: it was true
        # of `payment_methods`, which tenancy hosts and handles, and it is
        # NOT true of `bank_accounts`, which is payments' own table
        # (BR-TEN-031 — the OWNING module validates and writes).
        from apps.payments import lookups

        lookups.register()

        # CR-059 CS-10 (2026-09-02) — `ready()` NOW DOES ONE THING BESIDES
        # REGISTRATION: it installs the collections-ladder beat entry, which is
        # what makes BR-PAY-017's *"evaluated on a schedule"* true of a running
        # deployment rather than of a docstring. Same shape and same reason as
        # `apps/notifications/apps.py`, which did this for the dispatcher on
        # 2026-08-29.
        #
        # `install()` never raises: a deployment without celery logs
        # `installed: False` and the application starts, because a Django app
        # that refused to boot without a scheduler would be a worse product than
        # one whose reminders go out when the worker comes back.
        from apps.payments import collections_schedule

        collections_schedule.install()

        # P4.6 (Finance blueprint p017) — the deposit slip. `DepositsPage` has
        # carried a DISABLED download since the screen shipped, saying so with
        # `payments.deposits.slipUnavailable`, and the reason it gave was true:
        # no deposits export resource was registered anywhere. BR-TEN-031 puts
        # the registration in the module that OWNS the list, which is this one.
        from apps.payments import exports as payment_exports

        payment_exports.register()

        # CR-136-BRC07 `P2.11` (2026-09-23) — THE SECOND BEAT ENTRY, and this
        # ONE LINE is the whole of what `DEF-PAY-6268` was. The sweep that tells
        # a supervisor about a counter nobody closed
        # (`apps/payments/counter_watch.py`) and the command that runs it landed
        # complete and correct, and **nothing called either of them**: the PO
        # accepted, in §3.1, that a clerk cannot take money until a System Admin
        # seals yesterday's till, and the notice that bounds that cost fired
        # never.
        #
        # ⚠ `beat_schedule()` being CORRECT and the entry being INSTALLED are
        # two different claims (hard-won law 2), which is why the case that
        # proves it reads `config.celery.app.conf.beat_schedule` rather than the
        # function. `G132` refuses a module that declares an entry this line
        # does not install.
        #
        # ⚠ IT TELLS AND IT NEVER CLOSES — no scheduled job may seal a till.
        from apps.payments import counter_watch_schedule

        counter_watch_schedule.install()

        # US-SHL-003 — the `payments` group of universal search. The module that
        # owns the table owns its query (core/search.py's BE-08 contract).
        # ⚠ An unregistered group does not error, it is simply ABSENT from the
        # popover — hard-won law 2 wearing a search box.
        from apps.payments import search_sources

        search_sources.register()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-020@b6e4c19 (the five EP-PAY-06 sources — B2 §2 + r12/r14/r16 · EP-PAY-06-deposits-bank-rec.md · 08-payments/02-business-rules.md · 08-payments/03-field-map.md §6 · 08-payments/07-pre-session-model.md §7)
# generated: 2026-08-11 by Eng-Lead (W5 deposit-batch + bank-reconciliation lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — registration only) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · makemigrations --check clean (which is what proves the registry sees the models) · pytest tests/test_us_pay_020_023_bank_rec.py
# exceptions: this AppConfig exists ONLY because the EP-PAY-06 models could not
#         be written into apps/payments/models.py while another lane held it —
#         REPORTED, and the fold-back is a move rather than a redesign
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
