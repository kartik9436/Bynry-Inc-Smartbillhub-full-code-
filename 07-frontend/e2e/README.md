# e2e — Playwright journey suite (FI-06)

The UI half of the 300-journey E2E catalog (`08-qa/01-e2e/`) runs here in
Playwright, driving the real screens. Engine journeys run at API level in
`06-backend`. Both halves assert against the same expectation dataset
(`08-qa/01-e2e/expected/`), so docs and tests physically cannot drift.

## Running

```bash
./08-qa/01-e2e/stack/boot_stack.sh   # Postgres + Django + the BUILT SPA, seeded
cd 07-frontend
npx playwright install chromium      # first run only: browser binaries
E2E_BASE_URL=http://127.0.0.1:8080 npm run e2e
```

- **Target app:** `E2E_BASE_URL` (default `http://localhost:5173`, the Vite dev
  server). Point it at any deployed frontend — `boot_stack.sh`'s stack, the
  compose-stack demo, a preview deploy. Anything that reads a tenant's DATA
  needs the API on the SAME ORIGIN (the session cookie is httpOnly), which is
  what `boot_stack.sh` and the compose stack both give you and what a bare
  `vite dev` does not.
- **Target tenant:** `E2E_TENANT` (default `brazosbend`). Tenancy is PATH-based
  (PO 2026-08-10), so every authenticated URL a journey visits is
  `/{tenant}/…` — `bootApp` goes to `/{E2E_TENANT}/dashboard`.
- **No server up?** Specs guarded by `skipUnlessAppServer` SKIP with an honest
  reason instead of erroring — **but the RUN now fails**, because a suite that
  executed zero browser assertions proved nothing (DEF-057, below). To accept
  that locally, type `E2E_ALLOW_NO_APP_SERVER=1`.
- **No browser binaries?** `npx playwright install chromium` is the normal path.
  Where the CDN is unreachable (403 *"host not permitted"* from the agent proxy),
  point `E2E_CHROMIUM_EXECUTABLE` at a Chromium already on the box. **On the
  agent sandboxes this repo is worked in, one is pre-provisioned and four
  separate lanes each rediscovered it the hard way — so it is written down here
  once (2026-08-15):**

  ```bash
  export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
  # If the pinned Playwright build matches what is installed, that alone is enough.
  # If it does not (Playwright wants chromium-<other build>), name the binary:
  export E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
  # …or the stable symlink, where the box provides one:
  export E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium
  ```

  **Do NOT run `npx playwright install` there** — it fails on the proxy, slowly,
  and leaves a half-populated cache. CI is different and keeps the normal path:
  `.github/workflows/qa.yml` runs `npx playwright install --with-deps chromium`
  on a runner that can reach the CDN.
- **One journey / one tier:** `npx playwright test --grep @J1`,
  `--grep "@T3M-"`; every browser test also carries `@app-server`.

## The assertion census — why a skipped suite now fails (DEF-057)

`.github/workflows/qa.yml` printed *"Passing by design"* on every pull request
for weeks, because it looked for specs at a path that does not exist. **A job
whose only possible outcomes are "passed" and "passed" is not a check.** The PO
ruled on it, verbatim: *"we ahve to prove against human clicking"*.

So every run ends with a census (`support/census.ts`, registered as a reporter)
that prints how many assertions **actually executed**, split two ways:

```
── E2E ASSERTION CENSUS ──────────────────────────────────
  app-server      22 assertions · 6 ran · 0 skipped (of 6 selected)
  server-free      8 assertions · 4 ran · 0 skipped (of 4 selected)
  TOTAL           30 assertions executed
──────────────────────────────────────────────────────────
```

The split is the point. The server-free half (the CSV and B5 loaders) always
runs, so a total-only count would report a healthy number while every browser
assertion silently skipped — the same trap wearing a different hat. **A run with
zero `app-server` assertions FAILS**, naming why. Both failure modes were proved
red before the guard was trusted (law 7): a selection containing no tagged test,
and the exact DEF-057 scenario of a suite skipping because nothing answers.

Tag any new browser test's `describe` with `APP_SERVER_TAG` so it is counted.

## Support kit (`e2e/support/`)

| Module | What it gives a journey spec |
|---|---|
| `app.ts` | `bootApp(page)` (loads the shell at `/{tenant}/dashboard`, waits for the BR-SHL-001 sidebar) · **`signIn(page)`** (types into the real S3 form and clicks — never forges a cookie) · `skipUnlessAppServer(test)` · `baseUrl()` / `E2E_BASE_URL` · `tenant()` / `E2E_TENANT` |
| `expected.ts` | `moneyTriple(shape, billType, payment)` → the frozen row from `08-qa/01-e2e/expected/money-triples.csv` (245 machine-computed rows) · **`goldenCalc(id)`** → a GT-1..GT-16 fixture parsed out of `04-docs/02-decisions/05-golden-tests.md` (❄️ FROZEN), the same file the golden harness Part 2 reads. Money figures are EXACT DECIMAL STRINGS (CLAUDE.md rule 2) — assert `total === "97.41"`, never parseFloat |
| `census.ts` | `APP_SERVER_TAG` + the reporter that counts executed assertions and fails a run that executed no browser assertion (DEF-057) |
| `journey.ts` | `journey(id, title, body)` — wraps `test.describe` with the `@<journey-id>` tag |

**Which expectation source?** `moneyTriple` for anything the 245-row dataset
carries — those are machine-derived from the frozen B4 RULES. `goldenCalc` for
the GT-1..GT-16 prose fixtures, which a human at a finance sitting signed one at
a time and which no generator produces. Never retype a figure from either: a
second copy of a signed number is exactly the drift that produced DEF-028.

Until the real language-switcher UI lands (FI-03 switcher, S48 packet), specs
flip languages through the `window.__SMARTBILLHUB_I18N__` handle exposed by
`src/i18n/index.ts` — retire that handle (and the smoke's use of it) when the
switcher ships.

## Journey activation (B12 r3 §5)

The 303 journeys (`08-qa/01-e2e/journeys/`) automate **incrementally**:

1. The generated wiring index knows which stories each journey needs, in two
   views from one generator (`10-scripts/07-e2e-wiring-index.py`):
   `01-journey-story-index.md` for humans and **`01-journey-story-index.json`
   for machines**. **A journey ACTIVATES the moment its last story is built —
   the wiring index decides activation, not this directory.**
2. Activating a journey = authoring `<Journey-ID>.spec.ts` here (`J1.spec.ts`,
   `J07.spec.ts`, `T3M-001.spec.ts`, …), wrapping its steps in
   `journey("J1", …)` from the support kit, asserting every money figure via
   `moneyTriple(...)`, and walking the journey file's step table — including
   its per-step handoff contract and downstream assertions.
3. A wave cannot close with an activated journey red (gate G12,
   `run_gates.py --wave-close`). By W5 close, all 303 run nightly.

**Gate G12 is real since 2026-08-11** — it was a hardcoded `return "SKIP"`. Per
merge it fails when the index is stale, when a file named `<ID>.spec.ts` does not
call `journey("<ID>", …)`, when a spec claims a journey from a file not named for
it, when a spec claims an id the catalog does not define, and **when a spec
claims a journey whose stories the index says are not all built**, and **when a
journey file's own `id:`/`stories:` frontmatter cannot be parsed** (added
2026-08-15 — until then a malformed journey file was invisible: a missing id fell
back to a filename guess and an unreadable `stories:` line indexed as "declares
none", which is neither ready nor unready and appears in no count). With
`--wave-close` it additionally requires a durable run receipt to record every
activated journey as passed with a non-zero assertion count.

**Where the receipt lives, and why it moved (DEF-113, 2026-08-15).** It used to
be `07-frontend/test-results/journey-run.json` — inside Playwright's `outputDir`,
**which Playwright purges at the start of every run**. With several journey lanes
in one working tree a genuine receipt vanished within nine seconds of the run
that produced it, twice, and two wave-close runs reported "no run receipt" while
a real one had existed minutes earlier. Evidence now lives in
`07-frontend/journey-evidence/`: one immutable shard per run under `runs/`, plus
a merged view folded from them, **newest record per journey winning**. So a
narrow run (`--grep J23`) refreshes its own journeys and leaves every other
journey's record standing, and two runs finishing at once cannot delete each
other's evidence. Each record carries its own `recorded_at`, and G12 ages each
journey separately against the spec that claims it. The old path is still written
as a copy and still read last — a journey vouched for only from there FAILS the
wave, because the next run of anything deletes it.

Every failure mode above is proved RED by an executable file, not by this
sentence: `python3 10-scripts/gates/g12_selftest.py` breaks each check on purpose
and asserts G12 says so (law 7 · run in `.github/workflows/gates.yml`).

### Activated today: NONE — and that is measured, not assumed

`ready_by_stories` in the JSON lists the journeys whose every declared story is
cited in a code Trace header — two dozen and rising as lanes land (the number is
deliberately not repeated here; read the JSON, it is regenerated on every merge).
**`activated` says zero**, and only `activated` claims anything executes. The two
are kept apart on purpose:

- a Trace citation proves a code file claims a story, not that a human can click
  the flow (**OQ-172** asks the PO to ratify or replace that definition);
- **207 of the 303 journey files declare no stories at all** — every generated
  T3M money-triple and every T3P pairwise file — so "its last story is built" is
  undefined for them, not true (**OQ-173**);
- and the journeys examined in detail this session could each be executed only in
  part. J12 (NSF) and J13 (payment plan) need `/payments/{id}/nsf`, `/reverse`
  and the plan endpoints, none of which is mounted in `config/urls.py` and none
  of which has a screen. J09 (budget billing year) has no enrollment or level
  surface. T5-03 (currency lock) fails its own step 1 for a real product reason
  (DEF-064, below). Nearly every journey ends in a RECOVERY step — corrections,
  reversals, refunds — whose paths do not exist, and its downstream column asks
  for ledger, report and audit assertions that no endpoint serves.

**A journey you can only half-execute is not activated.** `W3-money-render` and
`W4-payment-write` both refuse to claim an id for exactly that reason, and G12
now enforces the refusal instead of relying on authors to keep it.

## The standing rule this directory proposes (PROPOSED — not ruled)

> **The lane that finishes a story writes the journey spec that exercises it.**
> Not a catch-up sweep later: when a story lands and the wiring index shows it
> was the last one a journey needed, that journey's `<ID>.spec.ts` is part of the
> same packet as the code — the lane that knows the screen, the fixture and the
> figures is the one that can write it in minutes, and it is the only moment when
> the flow is fully in someone's head.

Why it is proposed rather than assumed: 304 journey documents and two executing
specs is what the alternative produced. Recorded as PROPOSED in
`12-governance/02-decision-log.md` (2026-08-11) for the PO batch; until it is
ruled, this README is the only place it lives.

`W0-smoke.spec.ts` is **not** a journey — it is the W0 harness proof (shell
boots, the sidebar's 11 modules render, the language switch works, the
expectation CSV loads) and predates all activations.

`W4-payment-write.spec.ts` is **not** a journey either, and is the first spec
that makes the product CHANGE something: it types into the real S33/S22 Record
form — account, GT-1's frozen total, both BR-PAY-021 dates, method — clicks
Record payment, and asserts the rendered result, the S33 row (driving the IS-5
column chooser to reach the clearing date, which ships `defaultVisible: false`),
and that the ISSUED bill is not restated afterwards (hard rule 4). It performs
step 2 of the T3M rides and step 3 of J07 and claims NEITHER id.

`W3-money-render.spec.ts` is **not** a journey either, and is the first spec
that drives a browser all the way to the database: sign in on S3 → click Billing
in the sidebar → the S30 list → the bill detail's Charges tab, asserting that
every rendered figure equals GT-1 as `04-docs/02-decisions/05-golden-tests.md`
states it. It deliberately claims no catalog journey ID — J07 and T3M-001 both
need reads, payments and deposit rules that do not exist yet, and activating an
ID whose steps are not executed would be the same false comfort as DEF-057. Its
fixture is `08-qa/01-e2e/stack/seed_e2e_fixture.py`.

> **A NOTE THIS DIRECTORY PAID FOR.** `W0-smoke.spec.ts` asserted the pre-2026-08-10
> sidebar order — Settings second — for a day and a half after the PO amended
> BR-SHL-001 to put Settings last. Nobody noticed, because the spec had **never
> once executed**: it skipped on every run, since nothing started an app server.
> The first run against a live stack failed it in seconds (DEF-059). A spec that
> cannot run cannot be wrong, and cannot be right either.
