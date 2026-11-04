# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-028 (EP-INT-07) — token exchange and the fetch plan, a
#           ten-minute token across a two-hour walk. US-INT-031 (EP-INT-08) —
#           submit–poll–collect, a link or a handle. US-INT-035 (EP-INT-09) 🔒
#           — safety parameters explicit, and a fetch that changes their world.
#           Screens: S141 (the connect modal, Neptune variant) · S142
# Rules:    BR-INT-047 (token exchange never writes the credential table) ·
#           BR-INT-046 (completion and result delivery are declared) ·
#           BR-INT-050 (no vendor default on a money path) · BR-INT-019
#           (`test()` is the smallest REAL instance) · BR-INT-003 (the
#           plaintext lives for one call and never reaches a sentence, a log
#           or `describe()`) · BR-INT-038 (an adapter TRANSLATES: no retry, no
#           scheduling, no persistence) · BR-INT-054 as amended 2026-09-06
#           (this adapter talks to a head-end; what the rows MEAN is Runbooks')
# Tests:    06-backend/tests/test_us_int_028_token_walk.py ·
#           06-backend/tests/test_us_int_031_submit_poll_collect.py ·
#           06-backend/tests/test_us_int_035_safety_parameters.py
# Impacts:  apps/integrations/adapters/__init__.py (the one binding line) ·
#           apps/integrations/manifests/meters_neptune360.py (the fetch plans,
#           the poll schedules, the four safety parameters — all data) ·
#           apps/integrations/runners/fetch.py (the walk that drives this)
# ───────────────────────────────────────────────────────
"""The water meter cloud — a token, a window, a page, and a file they build for us.

WHAT THIS ADAPTER IS FOR
------------------------
Neptune 360 is the largest single vendor in the design: sixteen operations on
one credential. This file is the anti-corruption layer for three of their
shapes and nothing else — how they mint a token, how they page a window, and
how they answer *is the export ready yet*. **Every number is on the manifest**
(`window_days`, `page_size`, `poll`, `result_delivery`, `safety_parameters`);
nothing in this file decides how long to wait, how many to ask for or when to
give up. That is `BR-INT-037` and it is the whole of `C10`/`C12`.

⚠ **THE TOKEN IS MINTED THROUGH A PRIVATE METHOD, AND THAT IS DELIBERATE.**
The adapter protocol is four PUBLIC methods and the conformance kit refuses a
fifth. Minting is provider knowledge — the URL is data on the manifest, the
RESPONSE SHAPE is not — so it lands on `_mint_token`, which the kit's `dir()`
scan skips and which `adapters.base.token_minter()` resolves by name for a
runner that has no idea which provider it is driving. The token itself is held
by `runtime.TokenCache` in memory for the length of the walk and **never
written to `integration_credential`** (`BR-INT-047`): a ten-minute token across
a two-hour walk is about twelve mints, and a version row per mint would be
roughly 144 rows a day on one connection.

⚠ **`test()` READS ONE METER'S LAST READING** (`BR-INT-019`, and the manifest's
own `test_action` says so in words). It mints a real token and asks a real
question with a page size of one. It is NOT *does the API key parse* — the
design calls that the commonest mistake in this space, and a test that cannot
fail the way production fails is worse than no test because somebody trusted it.

⚠ **THERE IS NO HTTP CLIENT BOUND ON THIS DEPLOYMENT, AND THIS FILE SAYS SO
RATHER THAN PRETENDING.** `HEAD_END_CLIENT` is the seam; when nothing is bound,
`test()` answers `ok=False` with a plain sentence and `execute()` fails every
item — it never returns a green result it has not earned. The recorded client
in `apps/integrations/neptune_fixtures.py` is what the suite binds.

WHAT IS NOT HERE, AND WHOSE IT IS (BR-INT-054, CR-069 §20.4)
-------------------------------------------------------------
**What a collected reading MEANS.** `CR-069` §20.4 keeps token exchange, the
fetch plan, paging, submit–poll–collect and the safety parameters with
integrations, and moves *"the readings projection — turning what was collected
into our measurement frame"* to Runbooks in as many words. So this adapter
counts records and reports outcomes; it maps no meter to an account, writes no
read, and imports nothing that could. `apps/integrations/seams/runbooks.py` is
the door the pages leave through, and it returns nothing today.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_SUCCEEDED,
    MINTED_TOKEN_KEY,
    Adapter,
    ConnectionView,
    FieldError,
    FieldErrors,
    ItemResult,
    RunResult,
    TestResult,
)
from apps.integrations.scrubbing import scrub


class HeadEndClient:
    """What this adapter needs of an HTTP client, and the whole of it.

    ONE method. A real client (`requests`, `httpx`) is adapted to this shape in
    one place; nothing else in the product learns which library exists.
    `timeout_s` is passed in from `runtime.Limits` rather than chosen here —
    a timeout hard-coded in an adapter is the same rule in a second place, and
    the second place is the one that goes stale.
    """

    def call(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
        timeout_s: int = 30,
    ) -> Mapping[str, Any]:
        raise NotImplementedError


#: The seam. `None` on this deployment — no HTTP client is bound. A test binds
#: `neptune_fixtures.RecordedHeadEnd`; production binds a real one. A module
#: attribute rather than a constructor argument because `services` builds every
#: adapter with no arguments.
HEAD_END_CLIENT: HeadEndClient | None = None

#: ≤ 6 words each (B14 rule 33); no rule id and no status code (rule 32).
NO_CLIENT_SENTENCE = "No connection to the meter cloud."
REFUSED_SENTENCE = "The meter cloud refused the key."
UNREACHABLE_SENTENCE = "The meter cloud did not answer."
OK_SENTENCE = "Read one meter's last reading."

#: Their paths, relative to the site's API root. The token URL is on the
#: MANIFEST (`Auth.token.token_url`) because it is a fact about the
#: relationship; these are facts about their API and belong with the shapes.
READINGS_PATH = "https://api.neptune360.example/v1/sites/{site_id}/readings"
INVENTORY_PATH = "https://api.neptune360.example/v1/sites/{site_id}/meters"
ROUTES_PATH = "https://api.neptune360.example/v1/sites/{site_id}/routes"
EXPORTS_PATH = "https://api.neptune360.example/v1/sites/{site_id}/exports"

#: Which of their paths each operation asks. An operation absent from here is
#: one no runner drives yet — `collect_interval_data` is the case, and it is
#: absent on purpose: `OQ-INT-1484` was closed on 2026-09-04 with *"we will not
#: bring hourly internal data in this product"*, for no tenant, so nothing here
#: knows how to ask for it.
OPERATION_PATHS: dict[str, str] = {
    "collect_readings": READINGS_PATH,
    "collect_readings_by_route": READINGS_PATH,
    "collect_meter_inventory": INVENTORY_PATH,
    "collect_routes": ROUTES_PATH,
    "collect_billing_export": EXPORTS_PATH,
    "request_billing_export": EXPORTS_PATH,
}


def _api_error(answer: Mapping[str, Any]) -> str | None:
    """Their refusal, in their words, or `None` when they answered happily.

    ⚠ It carries `parameter` when they name one, because `US-INT-028` TC-4 is
    exactly *the provider refuses; the run records the refusal NAMING THE
    PARAMETER; no silent narrowing*.
    """
    error = answer.get("error")
    if not error:
        return None
    parameter = answer.get("parameter")
    return f"{error} ({parameter})" if parameter else str(error)


class MetersNeptune360Adapter(Adapter):
    """Four public methods, one private minter, and no policy of its own."""

    key = "meters_neptune360"

    # ── validate ───────────────────────────────────────────────────────────
    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """Provider knowledge about the NON-SECRET fields. No network.

        The manifest's shape check (`validate_fields`) has already run, so the
        only thing left is what Neptune itself knows: a site id is their own
        identifier and is never an email address or a URL typed into the wrong
        box, which is the mistake this catches before we dial with it.
        """
        problems: FieldErrors = []
        site_id = str(config.get("site_id") or "").strip()
        if site_id and ("@" in site_id or "/" in site_id or " " in site_id):
            problems.append(
                FieldError(
                    field="site_id",
                    # ⚠ THE KEY EXISTS IN ALL ELEVEN CATALOGUES, AND IT DID
                    # NOT ON ITS FIRST DRAFT. A `message_key` nothing resolves
                    # reaches a clerk as SILENCE — the field goes red and says
                    # nothing — and neither `tsc`, the suite nor `G32` would
                    # have seen it, because G32 resolves a key only where the
                    # raising helper is defined in the same file. The name also
                    # follows this family's own spelling (`bank_format`,
                    # `drop_required`), which camelCase would have broken.
                    message_key="integrations.field.site_id",
                    params={"field": "site_id"},
                )
            )
        return problems

    # ── test ───────────────────────────────────────────────────────────────
    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """Mint a token, read ONE meter's last reading, say so in one sentence."""
        client = HEAD_END_CLIENT
        if client is None:
            return TestResult(ok=False, sentence=NO_CLIENT_SENTENCE)
        try:
            token = self._mint_token(conn, secrets)
            answer = client.call(
                method="GET",
                url=READINGS_PATH.format(site_id=conn.config.get("site_id")),
                headers={"Authorization": f"Bearer {token}"},
                payload={"page": 1, "pageSize": 1},
            )
        except Exception as exc:  # noqa: BLE001 — a test's failure is its outcome
            return TestResult(
                ok=False, sentence=UNREACHABLE_SENTENCE, provider_text=scrub(str(exc))
            )
        problem = _api_error(answer)
        if problem is not None:
            return TestResult(ok=False, sentence=REFUSED_SENTENCE, provider_text=scrub(problem))
        readings = answer.get("readings") or []
        if not readings:
            # They answered and had nothing to give. That is not a failure of
            # the CONNECTION, and saying otherwise would send a clerk to look
            # for a password problem that is not there.
            return TestResult(ok=True, sentence="Connected. No readings yet.")
        return TestResult(ok=True, sentence=OK_SENTENCE)

    # ── execute ────────────────────────────────────────────────────────────
    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One attempt at a batch of REQUESTS. Per-item outcomes, never a bool.

        Each item of `work` is one request the runner has already decided to
        make — a window and a page of a walk, a submit, a poll, a collect. This
        method makes it and translates the answer; it does not decide whether
        to make another one, how long to wait, or what the rows mean.

        ⚠ **THE ITEM'S `ref` IS THE WINDOW AND THE PAGE, WHICH IS WHAT A CLERK
        WOULD SEARCH FOR** (B14 rule 31 — never a database id). *2024-09-01 ·
        page 2* is a thing a person can find in a support call; a uuid is not.
        """
        client = HEAD_END_CLIENT
        items: list[ItemResult] = []
        if client is None:
            return RunResult(
                items=tuple(
                    ItemResult(
                        ref=str(one.get("ref") or "?"),
                        outcome=ITEM_FAILED,
                        detail=NO_CLIENT_SENTENCE,
                    )
                    for one in work
                ),
                confirmed=False,
                provider_text=None,
            )
        # ⚠ THE RUNNER'S CACHED TOKEN WINS, AND THAT IS THE WHOLE OF
        # `US-INT-028` TC-1. Minting here per call would exchange once per
        # PAGE — 105 times on a two-year walk instead of the twelve a
        # ten-minute token needs — and `runtime.TokenCache` would be a cache
        # nothing ever read. Absent (a `test()` press, one call), we mint.
        token = str(secrets.get(MINTED_TOKEN_KEY) or "")
        if not token and work:
            token = self._mint_token(conn, secrets)
        site_id = conn.config.get("site_id")
        for one in work:
            ref = str(one.get("ref") or "?")
            operation = str(one.get("operation") or "")
            url = one.get("url") or OPERATION_PATHS.get(operation)
            if not url:
                items.append(
                    ItemResult(
                        ref=ref,
                        outcome=ITEM_FAILED,
                        detail=f"{operation} is not one this connector asks for",
                    )
                )
                continue
            answer = client.call(
                method=str(one.get("method") or "GET"),
                url=str(url).format(site_id=site_id),
                headers={"Authorization": f"Bearer {token}"},
                payload=dict(one.get("payload") or {}),
                timeout_s=int(one.get("timeout_s") or 30),
            )
            problem = _api_error(answer)
            if problem is not None:
                items.append(
                    ItemResult(ref=ref, outcome=ITEM_FAILED, provider_text=scrub(problem))
                )
                continue
            items.append(
                ItemResult(
                    ref=ref,
                    outcome=ITEM_SUCCEEDED,
                    detail=self._what_came_back(answer),
                    # ⚠ THE ONE CONTROL SIGNAL THIS ADAPTER OWES THE RUNNER, and
                    # it is a WORD rather than a number on purpose: the runner
                    # must not parse *4,912 records* to decide whether to ask
                    # for another page, and it must not infer *a short page
                    # means done* — a provider whose last page is exactly full
                    # is ordinary, and that inference silently drops the tail of
                    # every window that divides evenly. `hasMore` is THEIRS and
                    # this is the translation of it.
                    provider_text="more" if answer.get("hasMore") else None,
                )
            )
        return RunResult(items=tuple(items), confirmed=True)

    # ── describe ───────────────────────────────────────────────────────────
    def describe(self, conn: ConnectionView) -> str:
        """The masked line on the card — *Site BRAZOS-01 · Water meter cloud*.

        ⚠ NO SECRET, EVER (`BR-INT-003`'s third exit). The site id is not one:
        it is the non-secret half of the connection, the thing a utility reads
        off its own contract, and it is what makes two Neptune connections
        distinguishable on one screen.
        """
        site_id = str(conn.config.get("site_id") or "").strip()
        return f"Site {site_id} · Water meter cloud" if site_id else "Water meter cloud"

    # ── the private minter (adapters.base.TOKEN_MINT_METHOD) ───────────────
    def _mint_token(self, conn: ConnectionView, secrets: Mapping[str, str]) -> str:
        """Exchange the stored pair for a short-lived bearer token.

        ⚠ **NOTHING HERE WRITES ANYTHING** (`BR-INT-047`). It makes one call and
        returns a string. `runtime.TokenCache` decides whether to call it again;
        `services.record_credential` is never reached from this path, and a
        version row per mint would be ~144 a day on one connection.

        ⚠ **AND IT IS PRIVATE ON PURPOSE** — the protocol is four PUBLIC methods
        and the conformance kit refuses a fifth. `adapters.base.token_minter()`
        resolves this by name for a runner that knows nothing about Neptune.

        The URL comes from the MANIFEST (`Auth.token.token_url`) and is passed
        in by the runner where one is driving; `test()` reads it from the same
        place through `_token_url()` so the two cannot diverge.
        """
        client = HEAD_END_CLIENT
        if client is None:
            raise RuntimeError(NO_CLIENT_SENTENCE)
        answer = client.call(
            method="POST",
            url=self._token_url(),
            payload={
                "siteId": conn.config.get("site_id"),
                "apiKey": secrets.get("api_key", ""),
                "grantType": "client_credentials",
            },
        )
        problem = _api_error(answer)
        if problem is not None:
            raise RuntimeError(scrub(problem) or REFUSED_SENTENCE)
        token = str(answer.get("access_token") or "")
        if not token:
            # ⚠ A 200 with no token is not a token. Returning "" here would put
            # `Bearer ` on every request of a two-hour walk and fail 105 times
            # with an authentication error nobody could explain.
            raise RuntimeError("the meter cloud answered with no token")
        return token

    @staticmethod
    def _token_url() -> str:
        """The manifest's token endpoint — read at call time, never copied.

        Reaching into the registry here keeps ONE statement of where Neptune
        mints. A constant in this file would be the same fact in two places,
        and the second place is the one that goes stale (hard-won law 1).
        """
        from apps.integrations.registry import REGISTRY

        manifest = REGISTRY.require(MetersNeptune360Adapter.key)
        token = manifest.auth.token
        if token is None:  # pragma: no cover — the registry refuses this at load
            raise RuntimeError("this connector declares no token endpoint")
        return token.token_url

    @staticmethod
    def _what_came_back(answer: Mapping[str, Any]) -> str:
        """One short clause for the run row — a count, a status, or the file.

        ⚠ It deliberately does not describe the readings. What a reading MEANS
        is Runbooks' (`BR-INT-054`), and a sentence here that started
        interpreting them would be the boundary moving by accident.

        ⚠ **A URL WINS OVER THE STATUS WORD, AND THAT IS WHAT MAKES `C20` ONE
        CODE PATH.** Their v1 answers *ready* AND hands back a download link in
        the same body; their v2 answers *ready* and holds an identifier back for
        a second call. Reporting the link when there is one means the runner
        reads `link` delivery straight off the poll and asks again only for a
        `handle` — same function, two declared values, no branch on the
        provider (`US-INT-031` TC-2).
        """
        if "readings" in answer:
            return f"{len(answer.get('readings') or [])} records"
        url = answer.get("artifactUrl") or answer.get("downloadUrl")
        if url:
            return str(url)
        status = answer.get("status")
        if status:
            return str(status)
        if "records" in answer:
            return f"{answer.get('records')} records"
        return "answered"


__all__ = [
    "EXPORTS_PATH",
    "HEAD_END_CLIENT",
    "HeadEndClient",
    "INVENTORY_PATH",
    "MetersNeptune360Adapter",
    "NO_CLIENT_SENTENCE",
    "OPERATION_PATHS",
    "READINGS_PATH",
    "REFUSED_SENTENCE",
    "ROUTES_PATH",
    "UNREACHABLE_SENTENCE",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-028 · US-INT-031 · US-INT-035 (EP-INT-07/08/09) + BR-INT-046/047/050 verbatim
# generated: 2026-09-06 by the CR-069 wave K build lane
# checklist: A✔ B✔ C✔ D✔(bound in adapters/__init__.py, so the Neptune card is connectable) E✔(S141's Neptune variant draws the manifest's two fields) F✔ G✔ H=pending(🔒 HUMAN-REVIEW-PENDING — idempotency keys on a partner-state write; row in 09-human-review-ledger.md)
# gates: pytest tests/test_us_int_028_token_walk.py tests/test_us_int_031_submit_poll_collect.py tests/test_us_int_035_safety_parameters.py · the conformance kit (37 cases, unchanged) · G77
# exceptions: no HTTP client is bound on this deployment — `test()` answers ok=False rather than a green result it has not earned; `collect_interval_data` is absent from OPERATION_PATHS because OQ-INT-1484 closed it out of scope for every tenant
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
