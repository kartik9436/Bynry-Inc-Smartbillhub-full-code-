# CR-169-BRC10 — User-activity tracking in PostHog, one project per environment

**Raised:** 2026-10-04 by the Product Owner, in chat.
**Status:** **BUILT in 2.507.0 (lane POSTHOG, 2026-10-04) — OFF until the pipeline supplies the keys (§6).** Plan shown and four answers given (decision log 2026-10-04, *"POSTHOG USER-ACTIVITY TRACKING"*); §5 ruled the same day: (a), displayed customer details are masked too. What was built and the judgments it took are §8; the S3/CDN policy finding is §9; the post-deploy proof is §10.
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`). `allocate.py cr --verify 169`: free on every branch at allocation.
**Classification (`13-change-process.md` §1):** a CHANGE. It is new capability, not a defect. It touches no money rule, no signed figure and no RLS policy. It adds a third-party data flow, so it does touch privacy.

## 0 · What arrived, in the requester's words (abridged; the headings are theirs)

*"We want to implement user activity tracking using PostHog."*
1. **Environment separation:** a separate PostHog project for Development, Sandbox and Production. *"Data from one environment must NEVER be sent to another environment's PostHog project."* The key is to be injected by environment configuration.
2. **What to track:** sign-in/out, registration, page visits, feature use, useful button actions, operations on important business records, search/filter, report generation/download, workflow/status changes, failed actions.
3. **Identification:** use a stable internal user id plus non-sensitive properties (role, tenant, environment). Never passwords, tokens, credentials, payment information or sensitive PII.
4. **Isolation:** the right configuration is picked automatically per deployed environment. Developers never edit code between environments. Dev/Sandbox can never reach Production.
5. **The plan:** asked for first, *"Before making code changes"*.

## 1 · What the application already is (inspected 2026-10-04, tip `45da0db3c`)

| Fact | File | Consequence |
|---|---|---|
| The bundle is built per environment: `build:dev` / `build:sandbox` / `build:prod` read `.env.dev` / `.env.sandbox` / `.env.production`. | `07-frontend/package.json`, `vite.config.ts` | The key travels as a `VITE_*` build value. It is baked in, so changing it needs a rebuild (law 4). |
| `VITE_APP_ENV` exists, and its docstring says **NOTHING MAY BRANCH ON IT**. | `src/vite-env.d.ts` | The separation comes from a different KEY per build. There is never an `if (env === "production")`. |
| `vite.config.ts` already fails closed on a missing API origin for the three deployed modes. | `vite.config.ts` | The key checks go in the same place. |
| Staff sign-in is `POST /auth/session`. `/me` returns `{id, full_name, email, phone, role, role_name}` for the current tenant. Sign-out runs through `ShellWithSession`. | `src/api/endpoints.ts`, `src/components/ShellWithSession.tsx` | Identify on `id`. Reset on sign-out and on the dead-session boundary (`DEF-SHL-6378`). |
| The customer portal and the technician field app have their own sign-in. | `src/portal/`, `/work/mobile` | Portal: anonymous (ruling 1). Field app: same as staff. |
| Every screen carries a fixed screen id that is the same in all eleven languages. | `src/routing/screenIds.ts` | Page views name the screen id, not translated text or a raw address. |
| The CSP allows `connect-src 'self'` only. It lives in two places kept in step by a test. | `07-frontend/server.mjs`, `06-backend/apps/integrations/page_policy.py` | PostHog's US hosts must be added to both. **Where the S3/CDN deployment sets its header is to be confirmed by the build lane** (`CR-144-BRC07` moved the bundle off `server.mjs`). |
| The error-report cleaner already strips typed values, search text and capability links from an address. | `src/components/errorReport.ts` | It is reused for every `$current_url` sent. One cleaner, not two. |

## 2 · The plan (shown to the PO in chat, 2026-10-04)

| # | Topic | How |
|---|---|---|
| 1 | Where it starts | One module `src/analytics/`, started once at app load. Screens call only `track(event, props)`, never `posthog` directly. A gate forbids importing `posthog-js` anywhere else. |
| 2 | Keys per environment | Three PostHog projects. `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` are supplied by the pipeline per environment. The project key is public by design, but it is still not committed. |
| 3 | Fails closed | No key means analytics is off. Local, compose and test builds send nothing. |
| 4 | Cannot cross | (a) The build refuses when the Dev or Sandbox key equals the Production key (`VITE_POSTHOG_PROD_KEY_FINGERPRINT` compared at build). (b) At run time the bundle sends only when `location.host` matches its build's expected host list. (c) Every event carries `environment`. |
| 5 | Identify staff | `identify(user.id)` after `/me`. Properties: `role`, `tenant`, `environment`, `app` (`staff` / `portal` / `field`), `app_version`, `language`. Never name, email or phone. |
| 6 | Utility as a group | `group("tenant", <tenant slug>)`. This needs PostHog group analytics on the plan. |
| 7 | Sign-out / switch | `posthog.reset()` on sign-out, on an expired session and on switching tenant. |
| 8 | Privacy | Autocapture off. Every event has a typed allow-list of properties, and a test fails on any other key. Addresses are cleaned (§1). No amounts, account numbers, names or search text; counts and yes/no only. |
| 9 | Server events | Business events are sent from the server after commit (`transaction.on_commit`): bill run finalised, payment recorded, work order completed. The server has its own per-environment key in backend env and the same fail-closed rule. It never runs inside a money transaction. |
| 10 | Proving it | A post-deploy smoke per environment. A Production insight on `environment != production` that must stay at 0, with an alert. A test that the three keys differ. |

**Event names:** `object_action`, snake case, past tense. Examples: `user_signed_in`, `user_sign_in_failed` (reason code only), `screen_viewed`, `list_searched` (`has_search`, `result_count`), `list_filtered` (filter name, never its value), `bill_run_finalised`, `payment_recorded`, `work_order_raised`, `work_order_status_changed` (`from`, `to`), `report_downloaded` (report, format), `action_refused` (screen, error code).

## 3 · The PO's answers (2026-10-04, verbatim)

| # | Question | Answer |
|---|---|---|
| 1 | Track customers on the portal? | *"(a) Track portal visits without identifying the customer."* No `identify` on the portal. |
| 2 | Where the data is stored | *"(a) PostHog US cloud."* Hosts: `us.i.posthog.com` (ingest) and `us-assets.i.posthog.com` (the recorder's assets). |
| 3 | Session recording | *"(b) On for staff only, with all typed text hidden."* — widened minutes later: *"for customer portal also - with all typed text hidden."* **Recording on for staff and the portal; every input masked; the portal stays anonymous.** |

## 4 · Not a PO question — ours, recorded

- The field app is treated as staff. Its users are staff logins (ruling 18 of `CR-168-BRC10`).
- `posthog-js` is bundled from npm, never loaded from PostHog's CDN, so `script-src` stays `'self'`.
- The analytics module never blocks or slows a screen. A failed send is dropped silently, and nothing user-facing depends on it.

## 5 · RULED — displayed personal data in recordings (PO 2026-10-04, option (a))

"Typed text hidden" hides what a person TYPES, not what a screen SHOWS. The worked case was put to the PO: a clerk opens Maria Lopez's account, and the recording would show *"Maria Lopez, 412 Oak St, balance $186.40, account AC-2026-00012"* as page text. A customer on the portal would have their own balance and address recorded the same way. **The PO chose (a), verbatim: *"Also hide customer details shown on screen (names, addresses, amounts, account numbers). Menus, buttons and labels stay visible, so you can still see what people clicked and where they got stuck."*** So in BOTH apps the recorder masks every input AND the displayed record data: names, addresses, money amounts, account and reference numbers, emails and phones. Chrome, menus, buttons, column headings and labels stay readable. **The build masks by default and UNMASKS only the chrome**, never the other way round, so a new screen is private until someone decides otherwise (law 3).

## 6 · Needed from outside the repo

The three PostHog project keys (Dev, Sandbox, Production), entered in the deployment pipeline's per-environment settings, plus the expected host of each environment's web app. **PO 2026-10-04, verbatim: *"when you need it - just let me know in the chat in bold"*.** So the build does not wait on them, and the request goes to the PO in bold in chat at the moment a deploy needs them.

## 7 · Version · rollback

**Version 2.507.0** (`allocate.py version --bump change`, verified at push).

**Rollback, in order of size:**
1. **Turn it off without a code change:** rebuild the front end with `VITE_POSTHOG_KEY` empty and restart the API with `POSTHOG_KEY` empty. Nothing is sent and `posthog-js` is never downloaded. (A host already serving a bundle keeps its key until rebuilt — law 4.)
2. **Take the code back:** redeploy 2.506.x (the build before this one). No migration was added, so there is nothing to reverse in the database. The page policy loses the two PostHog hosts with it.

## 8 · What was built (2026-10-04, lane POSTHOG)

| Plan row | Where | What it does |
|---|---|---|
| 1 | `07-frontend/src/analytics/` | The only importer of `posthog-js` (`importGate.test.ts` fails any other, proved red by adding the import to a screen). Started once in `main.tsx`. |
| 2–4 | `scripts/deployConfig.mjs` `resolvePosthogConfig`, `vite.config.ts`, `src/analytics/config.ts`, `src/vite-env.d.ts`, `.env.dev/.sandbox/.production`, README | No key → off. The build **refuses** a dev/sandbox bundle carrying the production key and a production bundle carrying any other (by `VITE_POSTHOG_PROD_KEY_FINGERPRINT`), a key with no expected web host, and any ingest host but `us.i.posthog.com`. At run time the bundle sends only on its own host. `environment` on every event. |
| 5–7 | `client.ts` `identifyStaff`, `ShellWithSession`, `MobileApp`, `SignInPage`, `SessionExpired` | `identify(user.id)` with `role`, `tenant`, `app`, `language`; `group("tenant", slug)`; reset on sign-out, on a dead session and on a tenant switch. The portal never identifies and entering it after a staff session in the same tab resets first. |
| 8 | `events.ts`, `privacy.ts`, `client.ts` | Typed catalogue with a per-event allow-list; a string value that is not a code (a name, an amount, an email, a printed reference like `AC-2026-00012`) is dropped even under an allowed key. Autocapture, automatic page views, rage/dead clicks, heatmaps, surveys, flags all off. Every address on every event — and the recording's own page address — cleaned by `errorReport.ts`'s `redactPath`/`redactSearch`, reused with one new switch (`keepReferences: false`). `$title` dropped. |
| §3 answer 3, §5 | `privacy.ts` `RECORDING_PRIVACY` | Recording on for staff and portal. **Mask by default:** `maskTextSelector: "*"` sends every text through `maskText`, which keeps only the chrome readable (nav, menus, tabs, buttons, labels, column headings, h3–h6) and scrubs digits and emails even there; every input masked; attributes masked except those that draw the page, `href` cleaned. Network requests never recorded. Proved through the REAL recorder (`posthog-js/rrweb`) in `privacy.dom.test.ts`: *Maria Lopez*, *$186.40*, *412 Oak St*, *AC-2026-00012*, an email, a phone and the signed-in clerk's own name are absent from the recording; *Payments*, *Record payment*, *Cheque number*, *Account*, *Balance* are present. Proved red by removing the `*` selector. |
| 9 | `06-backend/config/product_analytics.py`, `config/settings/base.py`, `.env.example`, `pyproject.toml` | `POSTHOG_KEY` / `POSTHOG_HOST` / `POSTHOG_ENVIRONMENT` / `POSTHOG_PROD_KEY_FINGERPRINT` from env; off without a key or an environment; a non-production server handed the production key refuses. Sent through `transaction.on_commit` — a rolled-back payment sends nothing, nothing is sent while a money transaction is open. `bill_run_finalised` (`billing/issue.py` `finish_issue_pass`), `payment_recorded` (`payments/services.py` `record_payment`), `work_order_completed` (`metering/connections.py` `submit_field_result`). |
| 10 | `scripts/checkAnalytics.mjs`, §10 below | The post-deploy check and the insight that must stay at 0. |

**Events wired in this first set:** `user_signed_in`, `user_sign_in_failed` (`unknown_tenant` / `wrong_door` / `refused`), `user_signed_out` (`clicked` / `session_expired`), `screen_viewed` (the screen id, from each app's own register), `list_searched` / `list_filtered` (every `DataTable`; counts and the filter's NAME), `report_downloaded` (every `DownloadButton`; the screen id and the format), `work_order_status_changed` (`OrderDetailPage`; the two status words), `action_refused` (the API client; any non-GET 4xx but 401 and sign-in; the screen id, the refusal code, the status). Server: the three above. **Not yet wired** (named in §0 item 2, left for a later wave): registration (`SignupWizard`), `work_order_raised`, business-record operations beyond the three server events.

**Walked on the real app (2.507.0, brazosbend demo on PostgreSQL, `10-scripts/cr169_posthog_walkthrough.mjs`)** with a fake dev key, the walk's own host as the expected host, and every request to PostHog intercepted after the browser's page policy had let it out. Signing in, opening Dashboard, Accounts, searching the list, opening one account, Payments and signing out sent: `user_signed_in` (`surface: web`), `screen_viewed` ×6 named `ONB-03`, `DSH-01`, `ACC-01`, `ACC-02`, `PAY-summary`, `list_searched` (`list: S17`, `has_search: true`, `result_count: 16`), `user_signed_out` (`clicked`), one `$identify` on Dana's internal user id and one `$groupidentify` for `brazosbend`; after sign-out the next event carried a fresh anonymous id. The account's address left the browser as `/brazosbend/accounts/(withheld)` on every event and in all 116 of the recording's own page addresses. **The recording (1.2 MB once inflated) carried none of the 14 identifying values the list showed** — five account numbers, five names, a premises and three balances, e.g. *Mill Pond Apartments LP*, *AC-2026-00053*, *Iqbal, Nadia*, *$948.20* — nor the clerk's name or email, **and did carry** the chrome words *Accounts*, *Payments*, *Dashboard*. ⚠ **The recorder gzips its own payload**, so a search of the raw request finds nothing whether or not a name was recorded; the walk inflates every compressed field first and reports how many it could not (0). Two faults the walk found in this lane's own unpushed code, fixed before the push: screen ids shaped like `ACC-01` were being dropped as if they were printed references (a `screen` kind now carries them, with a test), and the walk itself had to stop reloading between screens, because PostHog flushes with `sendBeacon` on unload.

**Judgments that were ours (decision log 2026-10-04, *"POSTHOG BUILT"*):**
- **h1 and h2 are masked; h3–h6 are not.** `PageHeader` renders a record's title as h1 (h2 under Settings), and on a record that title is the customer's name. Breadcrumbs and the signed-in person's name in the frame are masked for the same reason.
- **Chrome text still has digits and emails scrubbed** — a button reading *Pay $186.40* records as *Pay $\*\*\*.\*\**.
- **`work_order_completed` is sent from the door (`submit_field_result`), not from `_record_field_result`**, whose other caller writes the demo's seeded history; seeding a utility must not send events.
- **The server module lives in `06-backend/config/`**, not a business module: it owns no table, and billing, payments and metering all call it.
- **A server event's `distinct_id` is the acting user's id** — the same id the browser identifies with — or `server` for a system job.
- **`screen_viewed` fires once per SCREEN**, not per address: opening a second account on the same screen is not a new screen.

## 9 · Where the S3/CDN deployment sets its page-security policy — FOUND

**Inside the repository, and only there.** `CR-144-BRC07` moved the policy into the document: `vite.config.ts` → `scripts/deployConfig.mjs` `pagePolicyPlugin` bakes a `<meta http-equiv="Content-Security-Policy">` into `index.html` at build time, reading `server.mjs`'s `BASE_POLICY` (which `server.test.mjs` keeps identical to `page_policy.BASE_DIRECTIVES`). So adding the two PostHog hosts to those two files reaches S3 with no further edit; the built `dist/index.html` was checked and carries them. **The static host (S3 + CloudFront) sets no `Content-Security-Policy` header**: the README's infrastructure table lists HSTS as the only header it must send, and nothing in `09-infra/` configures a CSP header. ⚠ That bucket/distribution configuration is **outside this repository** (it is the pipeline's and DevOps's), so nothing here can prove no header was added there by hand. If one ever is, it must carry the same hosts — a meta policy and a header intersect, and a header without PostHog's hosts would stop all tracking silently. The README now says so in its S3 table.

## 10 · Proving it after deploy (plan row 10), as instructions

**Every deploy, every environment:**
1. Before upload: `VITE_POSTHOG_PROD_KEY_FINGERPRINT=<16 hex> node scripts/checkAnalytics.mjs <mode> --dist dist` must print `PASS`.
2. After upload: the same with `--url https://<that environment's web host>`.
3. Open the web app, sign in, open two screens. In that environment's PostHog project → **Activity**, the events `user_signed_in` and `screen_viewed` appear within a minute with `environment` = that environment. In the **other two** projects, nothing new appears.

⚠ **Do step 3 in an ordinary browser, not an automated one.** posthog-js drops every event from a bot user agent and from a browser reporting `navigator.webdriver` — which every headless or Playwright browser does — so an automated smoke sees nothing and proves nothing. `10-scripts/cr169_posthog_walkthrough.mjs` shows how a walk gets past both, and it navigates inside the app rather than reloading, because a reload flushes PostHog's queue with `sendBeacon`, which no interception can read.

**When nothing arrives:** in that browser's console run `localStorage.ph_debug = "true"` and reload. PostHog logs its own work, and `src/analytics/` logs its on/off decision (`[analytics] decision: on` or the reason it is off — `no-key`, `wrong-host`, `wrong-ingest-host`), every tracked event, and any error it would otherwise swallow.

**Once, in the PRODUCTION project (the guard that must stay at 0):**
1. **Product analytics → New insight → Trends.** Series: *All events*. Filter: event property `environment` **is not** `production`. Date range: last 24 hours, interval: hour. Name it *Events from another environment (must be 0)* and save it to a dashboard.
2. On the saved insight, **Alerts → New alert**: *when the value is above 0*, check every hour, notify the engineering lead's email.
3. A second insight, same project: event property `environment` **is not set** — also must be 0.

**Once, in EACH project (settings the SDK cannot set):**
- *Project settings → Session replay → Record user sessions*: **on** for Dev, Sandbox and Production. **This one is REQUIRED, not belt and braces:** the SDK asks to start recording on every page, but the recorder starts only when the project's remote config says recording is on — measured in the walk, where a project answering `{}` recorded nothing.
- *Project settings → Session replay → Network capture*: **off**.
- *Project settings → IP data capture → Discard client IP data*: **on** (the PO ruled out sensitive PII; an IP address is not needed for any event here).
- *Project settings → Group analytics*: on, group type **`tenant`** (plan row 6 — needs group analytics on the PostHog plan).
