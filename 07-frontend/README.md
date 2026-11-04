# 07-frontend — SMARTBillHub web app (W0 scaffold)

React 18 + TypeScript + Vite. This is the HOUSE the components live in — the
components themselves (FE-01..21) arrive story-by-story through their packets.

## The three laws that bind this app

1. **LAW 0 — Simplicity** (`04-docs/02-decisions/08-coding-conventions.md`):
   boring, explicit code for the human reader first; no premature abstraction
   (third use earns one); the shared registry components are the approved reuse —
   everything else stays plain.
2. **i18n keys only** (B8 + TD-16): every user-visible string is a catalog key,
   no concatenated sentences. UI strings live client-side in
   `src/i18n/locales/`; customer documents are rendered server-side.
3. **One client, no hand-written fetch** (B8 + FI-01/TD-19,
   `04-docs/02-decisions/13-component-registry.md` §2): every request goes
   through `src/api/client.ts`. `src/api/schema.json` is the GENERATED artifact
   (drf-spectacular export); the typed wrappers over it are hand-written until a
   codegen step exists, because the export carries no body shapes yet — see
   `src/api/README.md` for why and for the re-export command.

## URLs — tenancy is PATH-based (PO ruling 2026-08-10)

One origin serves the marketing surface, every tenant and the API:

| Surface | Shape | Examples |
| --- | --- | --- |
| SPA, per tenant | `/{tenant}/…` | `/brazosbend/dashboard` · `/brazosbend/settings/company` |
| SPA, public | root | `/` · `/pricing` · `/signup` · `/signin-help` |
| Sign-in | per tenant | `/brazosbend/signin` → `POST /api/brazosbend/auth/session` |
| API, per tenant | `/api/{tenant}/…` | `/api/brazosbend/settings/company` |
| API, no tenant | `/api/…` | `/api/public/…` · `POST /api/tenants` · `/api/jobs/{id}` · `/api/exports` |

Two files own that shape and nothing else may re-derive it:

- **`src/routing/tenantPath.ts`** — `tenantPath(segment)` (the hook form) turns a
  tenant-RELATIVE route (`/settings/company`, as every route constant in the app
  is written) into the real URL. Every nav item, breadcrumb, link and redirect
  goes through it, so the tenant segment survives navigation by construction.
- **`src/api/client.ts` §API URL shape** — `apiPath()` prefixes `/api` and, for
  tenant-scoped calls, the tenant read from the browser's own URL. Endpoint
  wrappers keep naming the contract path (`/settings/company`); nothing is
  written twice, and a tenant-scoped call with no tenant in scope throws rather
  than posting to a URL that means something else.

**Because one origin now serves every tenant, the browser no longer isolates
them.** The server binds each session to its tenant and answers **404** on a
foreign tenant's path; the UI renders that as its ordinary not-found/failed
state and must never offer to "switch tenant" or redirect to the session's own.

## Deployment configuration

⚠ **THIS SECTION READ *"None right now"* UNTIL 2026-09-28.** It stopped being
true when the product moved to static files on S3 behind a CDN: there is **no
Node server in production**, so the browser calls a **separate API host**, and
the address of that host is now a fact of the BUILD.

The PO's reason for two hosts rather than routing `/api/*` through the CDN,
verbatim: *"I dont want to get locked in with the cdn from an cloud provider
later if I move out from this cloud I dont want this to be a blocker."* So there
is **nothing CDN-specific anywhere in this code**.

### The three builds

| Command | Mode / env file | Frontend served from | API baked in |
|---|---|---|---|
| `npm run build:dev` | `dev` → `.env.dev` | `https://app-dev.bynry.com` | `https://api-smart360-dev.bynry.com` |
| `npm run build:sandbox` | `sandbox` → `.env.sandbox` | `https://app-sand.bynry.com` | `https://api-smart360-sandbox.bynry.com` |
| `npm run build:prod` | `production` → `.env.production` | `https://app.bynry.com` | `https://api-smart360.bynry.com` |

Each runs `tsc --noEmit` first and writes to **`dist/`**. The pipeline copies
`dist/` to that environment's bucket.

### ⚠ THE VALUES ARE BAKED IN AT BUILD TIME

**Editing an env file changes nothing that is already on S3.** Vite INLINES
every `VITE_*` read into the JavaScript, so the API host is a string inside a
hashed `.js` file — not something the running page looks up. Changing where an
environment points needs **a rebuild and a fresh upload**, every time.

That is hard-won law 4 in its front-end shape (*"a template change never reaches
a host that already has a `.env`"*), and it is written here rather than left to
be discovered, because the failure is silent: the file on disk says one thing
and the bundle in the browser does another, for as long as nobody rebuilds.

### What each env file holds

All three carry the same three variables. **None of them is a secret** — every
`VITE_*` value is public the moment the bundle is on S3 — which is why the three
files are committed: they are deployment configuration a reader must be able to
check, not a credential store. **Never put a key, a token or a password in one.**

| Variable | What it is |
|---|---|
| `VITE_API_BASE_URL` | The API **origin**: scheme and host, no trailing slash, no path. `src/api/client.ts` appends its own `/api/{tenant}/…`. Empty means same-origin, which is correct only for `npm run dev` and the local docker stack |
| `VITE_APP_ENV` | `dev` · `sandbox` · `production`. Display and diagnostics only — **nothing may branch on it**, because a bundle that behaves differently by name is a bundle nobody can test |
| `VITE_SCREEN_ID_TAG` | `off` in all three. See below |

⚠ **`.env.example` IS A DIFFERENT FILE AND IS NOT ONE OF THESE.** It holds
`server.mjs`'s **runtime** values (`PORT`, `API_PROXY_TARGET`) for local docker
compose, which reads no `VITE_*` variable at all. Do not merge them.

### ⚠ The build FAILS when `VITE_API_BASE_URL` is missing

For `dev`, `sandbox` and `production` — not a warning, a refusal, with a
sentence naming the file to fix:

```
Error: VITE_API_BASE_URL is empty or missing for mode "production".
A deployed bundle is served from a static host that answers no API, so a
relative base URL makes every screen in the product fail at once and nothing
in CI goes red. Set it in 07-frontend/.env.production — for example
  VITE_API_BASE_URL=https://api-smart360.bynry.com
```

Hard-won law 3: **the unsafe option must be the one you type**, and here there
is no way to type it. A silent fallback to a relative URL would produce a bundle
that calls its **own static host**, so every screen in the product fails at
once, in production, with nothing red anywhere in CI.

A trailing slash and a path are refused for the same reason rather than trimmed.

### Verifying a build before it ships

```bash
npm run build:prod
node scripts/checkBundleHost.mjs production dist
```

It reads the BUILT files and asserts the bundle contains **this** environment's
API host and **no other environment's** — the one fault no other layer can see,
because a production deploy built from the sandbox env file is a perfectly
healthy-looking bundle that sends production data to the sandbox API. It fails
on an empty `dist` rather than reporting a clean zero over nothing.

### The screen-id tag

`VITE_SCREEN_ID_TAG` draws a **screen id** (`S49`, `CWP-052`) in the bottom-right
corner — a development aid for pointing at a screen in conversation. It names
the SCREEN, never the environment.

**PO 2026-09-28, verbatim: *"NO tags for no env to be put on screens as of now"*
— so it is `off` in all three files.**

⚠ **Two things follow, and both are about what NOT to do.** *"As of now"* is
part of the ruling, so **the capability stays**: the variable, its type in
`src/vite-env.d.ts` and the two components that read it are all kept, and
turning it back on for one environment is one word in one file rather than a
code change. And **this product has never had an environment banner** reading
DEV or SANDBOX — so the word *env* in the ruling implies no work, and there is
nothing of that kind to go and remove.

### The page-security policy travels in the document now

`server.mjs` was the **only** thing setting `Content-Security-Policy` on
`index.html`, and there is no server on S3. So `vite.config.ts` bakes the policy
into `index.html` as a `<meta http-equiv>` tag, per build, with that build's API
origin added to `connect-src`, `img-src`, `frame-src` and `object-src`.

The last two are not decoration: `BillDetailPage` and `BillLayoutTab` frame
`/api/{tenant}/…/document.pdf` and the portal shows a kept document in an
`<object>`. Those were `'self'` because the API was the same origin; the day it
is not, leaving them out reproduces `DEF-INT-4410` exactly — an empty grey box
saying the content is blocked, on the bill screen.

The base policy is **read out of `server.mjs`**, not copied. It already lives
twice (`server.mjs` and `06-backend/apps/integrations/page_policy.py`, kept
byte-identical by `server.test.mjs`); a third literal would be the same drift
one file further along.

⚠ **`Strict-Transport-Security` CANNOT go in a meta tag** — a browser ignores it
outside a real response header. The static host sends it. See below.

⚠ **AND ONE THING A META TAG CANNOT DO, STATED RATHER THAN DISCOVERED.**
`server.mjs` asked the API for a **per-tenant** policy and widened `img-src`
with that tenant's registered basemap tile host. A document baked once and
served to every tenant cannot, and a meta policy **intersects** with any header
the static host later adds rather than being replaced by it. So the asset map's
tiles are refused on a static host until that host is given a tile origin of its
own. Filed as a defect rather than quietly accepted.

⚠ **PARTLY FIXED IN 2.495.1 (`DEF-INT-7430`, option (a)).** The baked tag now
names the **default** Esri tile origin, `https://server.arcgisonline.com`, on
`img-src` and nowhere else (`scripts/deployConfig.mjs`'s `DEFAULT_TILE_ORIGIN`,
checked against the server's `ESRI_TILE_HOST` by `src/api/pagePolicyTiles.test.ts`),
so both maps draw on the shipped default. A utility that points its basemap at
its **own** tile server is still refused on a static host; the later fix is
option (b) — the static host sends the per-tenant policy as a header and the
meta tag goes. ⚠ **A host already running keeps its old policy until it is
redeployed** — the policy is baked into `index.html` at build time.

### User-activity tracking (PostHog) — `CR-169-BRC10`

**Off unless the pipeline supplies a key.** One PostHog project per environment,
PostHog US cloud (PO 2026-10-04). Everything lives in `src/analytics/`; a screen
calls `track(event, props)` from `@/analytics`, and `src/analytics/importGate.test.ts`
fails any other file importing `posthog-js`.

| Variable | Where it comes from | What it is |
|---|---|---|
| `VITE_POSTHOG_KEY` | **pipeline, per environment — never committed** | That environment's own PostHog project key. Empty = analytics OFF |
| `VITE_POSTHOG_PROD_KEY_FINGERPRINT` | pipeline (may be committed — it is not the key) | First 16 hex of `sha256(<production key>)` |
| `VITE_POSTHOG_HOST` | `.env.<mode>` | `https://us.i.posthog.com`, and nothing else is accepted |
| `VITE_POSTHOG_EXPECTED_HOSTS` | `.env.<mode>` | The web host(s) this bundle may send from, comma-separated |

**The four locks:** (1) no key, no tracking; (2) `vite.config.ts` **refuses** a
dev or sandbox build whose key is the production key, and a production build
whose key is not (by fingerprint — `scripts/deployConfig.mjs`
`resolvePosthogConfig`); (3) at run time a bundle sends only when the page's
host is in `VITE_POSTHOG_EXPECTED_HOSTS` (`src/analytics/config.ts`); (4) every
event carries `environment`.

**After every deploy, run the check** — before upload against `dist`, after
upload against the live site:

```bash
VITE_POSTHOG_PROD_KEY_FINGERPRINT=<16 hex> node scripts/checkAnalytics.mjs production --dist dist
VITE_POSTHOG_PROD_KEY_FINGERPRINT=<16 hex> node scripts/checkAnalytics.mjs production --url https://app.bynry.com
```

It reads the page policy (PostHog's two hosts on `connect-src`, `script-src`
still `'self'`) and every `phc_…` key in the JavaScript, and fails a dev or
sandbox bundle carrying the production key or a production bundle carrying any
other. A key-less bundle prints `analytics OFF`, never a pass on keys.

**posthog-js and its recorder are bundled** (`posthog-js/dist/module.full.no-external`,
in its own chunk, fetched only when analytics is on), so nothing loads from
PostHog's CDN and `script-src` stays `'self'`. The page policy gains exactly
`https://us.i.posthog.com` and `https://us-assets.i.posthog.com` on
`connect-src`, in `server.mjs` and `page_policy.py` (kept identical by
`server.test.mjs`) and therefore in the baked `<meta>` tag.

⚠ **The static host sets NO policy header of its own** (see below): the policy
a browser enforces on S3 is the baked meta tag, which this repository writes. If
the CDN is ever given a `Content-Security-Policy` response header, it must carry
the same two PostHog hosts — a meta policy and a header **intersect**, so a
header without them silently stops all tracking.

## Deploying to S3 behind a CDN — infrastructure notes

⚠ **NONE OF THIS IS CODE AND NONE OF IT CAN BE BUILT FROM THIS REPOSITORY.** It
is written down so the person configuring the bucket and the distribution has
the list, and so nobody later goes looking for the commit that did it.

| | What it must do | Why |
|---|---|---|
| **Unknown paths** | Serve `index.html` with a **200** | The app owns its own routes: `/brazosbend/payments` is not a file. A 404 or a 403 here is a blank page on every deep link and every refresh |
| **`index.html`** | **Do not cache it** (`no-cache`, or a very short max-age) | It names the hashed bundle. A cached copy points at the previous release's files, so a deploy reaches nobody — or half-reaches them |
| **`assets/*`** | Long cache, immutable | Every filename already carries a content hash, so a changed file is a different name and a stale copy is impossible |
| **HTTP** | Redirect to HTTPS | |
| **HSTS** | `Strict-Transport-Security` on every response | ⚠ It **cannot** be a meta tag — a browser ignores it outside a real header, so this is the static host's job and there is nothing to build |
| **`Content-Security-Policy` header** | **None — do not add one without copying the baked policy** | The policy is the `<meta>` tag `vite.config.ts` writes into `index.html`. A header would INTERSECT with it, so a header missing a host the page needs (PostHog's two, the API origin, the map tiles) breaks that feature silently (`CR-169-BRC10`) |

⚠ **`server.mjs` AND `Dockerfile` ARE KEPT AND ARE NOT USED ON S3.** They are
the **local docker-compose** stack: `server.mjs` serves the bundle and proxies
`/api` to the backend container so that stack stays same-origin, which is why
`.env.example` and `API_PROXY_TARGET` still exist and still mean what they say.
Nothing on S3 runs either of them. Do not delete them as dead code, and do not
read them as a description of production.

## Structure

```
07-frontend/
├── index.html              Vite entry
├── package.json            scripts: dev · build · preview · test · lint · format · e2e
├── tsconfig.json           strict; `@/` → `src/`
├── vite.config.ts
├── vitest.config.ts        unit tests: src/**/*.test.{ts,tsx}
├── playwright.config.ts    E2E runner (FI-06)
├── e2e/                    journey specs — activate per wiring index (B12 r3 §5)
└── src/
    ├── vite-env.d.ts       typed `import.meta.env` (no variables at present)
    ├── main.tsx            React root; loads i18n + global.css
    ├── App.tsx             APP_ROUTES (public + `/:tenant/…`) + QueryClientProvider
    ├── api/                FI-01 client + FI-02 query setup; schema.json is generated
    ├── components/         FE-01..21 registry components — one implementation each
    ├── features/           13 module dirs mirroring 04-docs/05-modules/
    ├── routing/            tenantPath — the ONE builder of `/{tenant}/…` URLs
    ├── i18n/               FI-03: LOCALE_REGISTRY (BR-SHL-041's eleven) + 11 catalogs
    └── styles/
        ├── tokens.css      design tokens PORTED from 05-prototype (FI-05)
        └── global.css      minimal reset importing tokens
```

## Doc pointers

- Conventions: `04-docs/02-decisions/08-coding-conventions.md` (B8, TS/React section)
- Component registry + build checkpoint: `04-docs/02-decisions/13-component-registry.md` (B13) and `13a-screen-component-map.md`
- Interaction standards: `04-docs/02-decisions/09-interaction-standards.md`
- Contracts (API A11, enums A5, glossary A16): `04-docs/03-contracts/`
- Prototype reference (tokens/copy/layout ONLY — runtime is never ported):
  `05-prototype/UtilityBilling.html` + `05-prototype/styles.css`

No `npm install` has been run — no lockfile is committed by the scaffold.
