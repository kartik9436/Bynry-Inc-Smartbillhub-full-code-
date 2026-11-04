# E2E stack — the running product, for a browser to click

> **Why this folder exists.** PO ruling, 2026-08-11, verbatim: **"we ahve to
> prove against human clicking"** (`12-governance/02-decision-log.md`). The
> state it answered, measured rather than estimated: 1,651 backend tests drive
> the real cross-module chain against a real database; 875 frontend tests run
> against **mocked** responses; and **nothing exercised a browser against a live
> server**. 304 journey documents described flows no code executed, and
> `.github/workflows/qa.yml` printed *"Passing by design"* on every pull request
> (DEF-057). This folder is what a browser now points at.

## Run it

```bash
./08-qa/01-e2e/stack/boot_stack.sh          # bring it up (idempotent)
cd 07-frontend && E2E_BASE_URL=http://127.0.0.1:8080 npx playwright test
./08-qa/01-e2e/stack/boot_stack.sh --stop   # take it down
```

`boot_stack.sh` prints the base URL, the sign-in URL and the fixture
credentials, and exits non-zero the moment any step fails. A half-booted stack
that reported success is the thing this whole lane exists to stop.

## What it boots, and how it relates to `docker-compose.yml`

`docker-compose.yml` at the repo root is the application's real shape — two
containers, ONE published port, an EXTERNAL Postgres — and it stays the
reference. `boot_stack.sh` is **the same shape without Docker**, because that is
what a CI runner and a sandbox can actually execute.

| | compose | `boot_stack.sh` |
|---|---|---|
| Postgres | external, yours | external, yours (`DATABASE_URL`) |
| Django | gunicorn in a container | `manage.py runserver --noreload` |
| SPA | built, behind `server.mjs` in a container | built, behind **the same `server.mjs`** |
| `/api/*` | frontend proxies to `backend:8000` | frontend proxies to `127.0.0.1:8000` |
| origin | one | one |

**The one property that must never differ is SAME ORIGIN.** The session cookie
is httpOnly and host-scoped, so the SPA and `/api/*` must answer on one address
or nothing can sign in. Both routes achieve it through the same file.

**The one property that DOES differ is the server:** gunicorn there, Django's
dev server here. That affects the worker model and static handling; no assertion
in `07-frontend/e2e` touches either. Stated rather than hidden.

## The fixture: one tenant, one account, one bill

| Step | What runs | What it leaves |
|---|---|---|
| 1 | `manage.py migrate` | the schema, RLS policies and immutability triggers |
| 2 | `manage.py seed_demo` | Brazos Bend Utilities: services, plans, rate schedules, taxes, 6 premises, 10 units, 8 meters, the owner user |
| 3 | `seed_e2e_fixture.py` | account `E2E-10001` and **one ISSUED bill, priced by the real engine** |

`seed_demo` deliberately creates no reads, accounts, bills or payments — its own
summary says so. Step 3 adds exactly one of each thing the money journey needs
and no more.

### The bill is GT-1, and nothing about it is typed

`seed_e2e_fixture.py` drives the real chain — stage 1 (resolve subscription) →
stage 2 (measure consumption) → rating's priced pass → stage 6 (assemble) →
`issue.issue_invoice` — with GT-1's frozen inputs, **imported** from
`06-backend/tests/test_us_bil_029_assemble.py` rather than copied:

```
B5 GT-1 (❄️ FROZEN, finance-signed 2026-08-08):
  Electric flat $0.12/kWh, base $18.50, usage 684 kWh, tax 8.25% on (usage+base)
  684×0.12 = 82.08; +18.50 = 100.58; tax 8.2979 → 8.30; **total 108.88**
```

The tax is the fixture utility's OWN ratified pair — Texas State 6.25 % + Local
2.00 %, both seeded by `seed_demo` from `[F] lookup_defaults.json` — and under
B4.4's per-line half-up rounding it lands on GT-1's signed $8.30 to the cent
(6.29 + 2.01). So the browser reads a bill taxed by a real tenant's real
configuration, and the number finance signed is the number that lands.

**No total is written into any file here.** If the engine mis-prices GT-1 the
seeder refuses to report success, and the browser assertion fails quoting both
strings. That was proved, deliberately, before this was trusted (law 7): a bill
priced at 683 kWh instead of 684 produced

```
Expected: "$108.88"
Received: "$108.75"
```

### The fixture contract the specs depend on

| Name | Value | Override |
|---|---|---|
| tenant slug | `brazosbend` | `E2E_TENANT` |
| sign-in | `dana@brazosbendutilities.com` / `S3cure!passw0rd` | `E2E_EMAIL` / `E2E_PASSWORD` |
| account | `E2E-10001` | `E2E_ACCOUNT_NO` |
| bill total | GT-1, read from `04-docs/02-decisions/05-golden-tests.md` | — never |

The bill NUMBER is deliberately not part of the contract: the tenant's own
series allocates it, so it differs between a fresh database and a re-seeded one.
The specs find the row by ACCOUNT number.

## Two things this fixture does by hand, and why neither is a money figure

1. **The account is created with the customers MODEL, not the activation
   service.** Activation needs plan deposit rules that no ratified figure exists
   for (`seed_demo`'s own omissions list). The account row carries no money.
   When EP-CUS-07's onboarding lands, this should call it.
2. **A 2200-series liability account per tax authority.** BR-BIL-069 (PO ruling
   2026-08-11) makes every tax line resolve its account through
   `taxes.liability_gl_account_id`, `seed_demo` leaves it NULL, and
   `apps/ledger/chart.py` carries no 2200 row **by design** — seeding one would
   invent a tax authority no tenant created (BR-TEN-037). So the fixture takes
   the three steps a tenant's accountant takes on S13, exactly as
   `tests/test_br_bil_069_tax_authority_gl.py` does. The suffix scheme is typed
   because this fixture predates the allocator (OQ-147 CLOSED 2026-08-12 — the
   product now generates 2200-nn; the fixture's hand-typed codes can go, and this fixture does not
   answer it).

## Databases: one per lane, always

`DATABASE_URL` defaults to `…/sbh_e2e`, not the shared `smartbillhub`. DEF-054
measured what a shared database costs: two concurrent pytest runs drop each
other's `test_smartbillhub`, and every test in whichever file is running errors
in fixture setup with `assert not self._finalizers` — a failure that looks
exactly like a defect in code that is fine.

⚠ **THIS SECTION USED TO END "point `DATABASE_URL` wherever you like; do not
point two runs at one database", AND THAT SENTENCE IS WHY IT HAPPENED AGAIN
(2026-08-30).** It asks a person to remember an environment variable, so the
SHARED name was what you got by typing nothing — hard-won law 3 exactly. Two
lanes ran the backend suite against one PostgreSQL for **fifty minutes and wrote
no result**, against eleven files that take 2m56s alone.

**It is now the default and needs nothing typed.** `config/settings/base.py`
derives `DATABASES['default']['TEST']['NAME']` from the checkout's own path, so
every worktree gets its own test database and `--reuse-db` still reuses. Read the
block beside `DATABASES` there for the whole of it. Set
`SBH_TEST_DB_NAME=test_smartbillhub` to go back to a shared database on purpose.

**A `git worktree` isolates the FILES and shares the REFS, and it shares the
DATABASE with the whole machine** — which is one level worse than the refs
problem `10-scripts/check_head_current.sh` records in its own header.
