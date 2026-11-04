# VAPT remediation — October 2026

**Scope:** five findings from the VAPT retest of SMART360 Next.
**Hosts:** web `https://app.bynry.com` (S3 + CloudFront) · API `https://api-smart360.bynry.com` (ECS behind an ALB with AWS WAF).
**Status of rulings:** all approved by the Product Owner on 2026-10-27 (decision log, *"VAPT round: five findings ruled"*).
**Who does what:** **Code** = the development team (shipped in a release). **AWS** = DevOps, following the steps below.

| # | Finding | Fix | Code | AWS |
|---|---|---|---|---|
| 1 | Stored XSS (SVG logo) | Logos PNG or JPG only; SVG refused with a clear message; firewall blocks show a clear message | ✅ | ✅ (WAF rule exception for uploads) |
| 2 | Rate limiting | Limits at the WAF (per address) and in the app (per user, per utility, heavy actions, per phone); lockout message | ✅ | ✅ (3 WAF rate rules) |
| 3 | Arbitrary HTTP methods | Closed — not exploitable; evidence below | Evidence test only | — |
| 4 | CSP header missing on app.bynry.com | CloudFront response-headers policy carrying the policy the build already uses | — (text provided) | ✅ |
| 5 | HSTS missing on the API | `SECURE_HSTS_SECONDS=300` on the backend task definition | — (already supported) | ✅ |

---

## 1 · Stored XSS — SVG logo upload

### What was found
- Uploading an `.svg` logo answered *"We couldn't reach SMART360 Next. Check your connection and try again."*
- The placeholder reads *"Logo — SVG or PNG, max 2 MB"*.

### Why it happened
- Our server accepted SVG logos and **sanitised** them (removed `<script>`, `on…` handlers, links) — rule BR-TEN-019. A malicious SVG was never stored as-is.
- The request never reached our server: the **AWS WAF managed common rule set** in front of the API blocked it. Two of its rules fire on a logo upload:
  - `CrossSiteScripting_BODY` — matches `<script>` inside an SVG.
  - `SizeRestrictions_BODY` — blocks any request body larger than 8 KB, which includes **most real PNG/JPG logos** (up to 2 MB).
- A WAF block is a 403 **without CORS headers**, so the browser hides it from the page and the app can only say "couldn't reach".

### Fix — code (development team)
| # | Change |
|---|---|
| 1 | Logos accepted: **PNG or JPG only** (max 2 MB). SVG is refused **in the browser before upload** and **again by the server**: *"SVG files aren't accepted. Use PNG or JPG."* |
| 2 | Placeholder: *"Logo — PNG or JPG, max 2 MB"* (all 11 languages). |
| 3 | The server checks the file's **contents**, not just its name: a file named `.png` that is really an SVG/HTML is refused (*"File contents don't match its type."*). |
| 4 | Utilities that already have an SVG logo keep the cleaned PNG copy the server made from it — nothing breaks on bills or screens. |
| 5 | When the firewall blocks a request, the web shows *"This request was blocked for security. Contact support."* instead of "couldn't reach" (needs step 1-A below so the browser can read the block). |

### Fix — AWS (DevOps)
**1-A. Let the upload reach the app, which does the real checking.** AWS console → **WAF & Shield** → **Web ACLs** → (region of the ALB) → the API web ACL → **Rules** → `AWS-AWSManagedRulesCommonRuleSet` → **Edit**:
1. Under **Rules**, set **`SizeRestrictions_BODY`** → **Override to Count**. Set **`CrossSiteScripting_BODY`** → **Override to Count**.
2. **Save rule**.
3. **Add rules → Add my own rules → Rule builder**, name `block-body-xss-except-logo`, priority just **after** the common rule set:
   - **If a request** = *matches all the statements (AND)*:
     - Statement 1: **Has a label** → match key `awswaf:managed:aws:core-rule-set:CrossSiteScripting_Body`.
     - Statement 2: **NOT** → **URI path** → **Contains string** → `/settings/company/logo` (text transformation: none).
   - **Action: Block** → **Custom response**: response code **403**, custom response header `Access-Control-Allow-Origin: https://app.bynry.com`, `Access-Control-Allow-Credentials: true`, body (JSON) `{"code":"WAF-BLOCK","message_key":"api.error.blocked"}`.
4. Add a second rule `block-body-size-except-uploads` the same way, label `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body`, NOT URI path **contains** `/upload` **and** NOT URI path **contains** `/logo` **and** NOT URI path **contains** `/photos` **and** NOT URI path **contains** `/documents`, action Block with the same custom response.
5. **Save**.

> The app keeps its own upload checks (type allowlist, content check, 2 MB cap, 415/413 answers), so excluding these paths from two WAF body rules does not open them.

### Test (after the release and 1-A)
| # | Do | Expect |
|---|---|---|
| 1 | Settings › Company › Brand → pick an `.svg` | Refused in the browser: *"SVG files aren't accepted. Use PNG or JPG."*; nothing uploaded |
| 2 | Bypass the browser: `curl -X POST https://api-smart360.bynry.com/api/<tenant>/settings/company/logo -H "Cookie: <session>" -F "file=@evil.svg;type=image/svg+xml"` | **415** with `message_key` for SVG not accepted |
| 3 | Rename `evil.svg` to `evil.png` and upload | **415/422** *"File contents don't match its type."* |
| 4 | Upload a real 500 KB PNG, then a JPG | Accepted; logo shows on the screen and on a bill PDF |
| 5 | Placeholder | *"Logo — PNG or JPG, max 2 MB"* |
| 6 | WAF → web ACL → **Sampled requests** during test 2 | Shows `CrossSiteScripting_BODY` in **Count** on the logo path, not Block |

---

## 2 · Rate limiting

### Where rate limiting is applied today
| Area | Limit today | Counted by |
|---|---|---|
| Web sign-in (wrong passwords) | Locks after **N** wrong passwords for **M** minutes — **N and M come from Settings › Security** (N 3–10, default 5; M 5–60, default 15). Not hardcoded. | Per account |
| Field app sign-in / token refresh | 30 per minute | Per network address |
| Field app activation | 10 per minute | Per network address |
| Activation-code lookup | 10 per 15 minutes | Per address **and** per phone |
| Password set/reset links | 10 per minute | Per network address |
| Public pages (customer portal, agreement links, bill links) | 60 per minute | Per network address and per utility |
| Partner / integration API | Its own limiter | Per partner key |
| **Signed-in staff API** (e.g. `/premises`) | **None in the app** | — |
| AWS WAF | Common rule set + known bad inputs; **no rate rule confirmed** | — |

So 30 calls to `/premises` without a 429 is the current behaviour. 30 calls is also normal use — one screen load makes 10–20 calls.

### The lockout message (code)
The count and the lock period already follow Settings › Security on the web and in the field app. What changes is the **message**: a locked account now reads *"Too many wrong attempts. Try again in **M** minutes."* — M is the utility's own setting — instead of the generic *"Your email or password isn't right."* The same sentence appears on the web sign-in and the field app sign-in.

### Proposed limits
| Layer | Applies to | Counted by | Limit | When exceeded |
|---|---|---|---|---|
| **WAF — W1** | Everything on the API | Network address | **2,000 requests per 5 minutes** | 429 from WAF |
| **WAF — W2** | Sign-in & public doors: paths containing `/auth/`, `/portal/`, `/public/` | Network address | **300 requests per 5 minutes** | 429 from WAF |
| **WAF — W3** | Field-app activation & lookup: paths containing `/auth/activation` | Network address | **50 requests per 5 minutes** | 429 from WAF |
| **App — A1** | Every signed-in call | User | **300 per minute** | 429 + `Retry-After` |
| **App — A2** | Every signed-in call | Utility | **3,000 per minute** | 429 + `Retry-After` |
| **App — A3** | Heavy actions: exports, imports, report runs, bill runs, bulk actions | User | **10 per minute** | 429 + `Retry-After` |
| **App — A4** | Field-app sync | Phone | **120 per minute** (each call carries up to 50 items) | 429; the phone waits and resends — nothing lost |
| Existing doors | As in the table above | — | Unchanged | — |

App limits A1–A4 are read from environment variables (`RATE_USER_PER_MIN`, `RATE_TENANT_PER_MIN`, `RATE_HEAVY_PER_MIN`, `RATE_DEVICE_PER_MIN`) with the values above as defaults, so DevOps can tune them on the task definition without a release. The web shows *"Too many requests. Wait a moment."* and retries after `Retry-After`.

### WAF setup (DevOps) — AWS console
For **each** of W1, W2, W3: **WAF & Shield** → **Web ACLs** → the API web ACL → **Rules** → **Add rules** → **Add my own rules and rule groups** → **Rule builder**:
| Field | W1 | W2 | W3 |
|---|---|---|---|
| Name | `rate-api-per-ip` | `rate-signin-public-per-ip` | `rate-activation-per-ip` |
| Type | **Rate-based rule** | Rate-based rule | Rate-based rule |
| Rate limit | **2000** | **300** | **50** |
| Evaluation window | **5 minutes** | 5 minutes | 5 minutes |
| Request aggregation | **Source IP address** (or **IP address in header** `X-Forwarded-For` if CloudFront sits in front of the ALB) | same | same |
| Scope of inspection | Consider all requests | **Only requests that match a scope-down statement**: URI path *contains* `/auth/` **OR** *contains* `/portal/` **OR** *contains* `/public/` | Scope-down: URI path *contains* `/auth/activation` |
| Action | **Count** (first 7 days) → then **Block** | Count → Block | Count → Block |
| Custom response (on Block) | Code **429**, header `Retry-After: 300`, headers `Access-Control-Allow-Origin: https://app.bynry.com` and `Access-Control-Allow-Credentials: true` | same | same |
| Priority | After the managed rule groups | Before W1 | Before W2 |

**Count first, then Block:** run 7 days in Count. Then **CloudWatch** → **Metrics** → **WAFV2** → the rule's `CountedRequests`. If any real office address was counted, raise that rule's limit before switching to Block.

### Test
| # | Do | Expect |
|---|---|---|
| 1 | Settings › Security: wrong attempts **3**, lock **5 minutes**. Sign in with a wrong password 3 times | 3rd attempt: *"Too many wrong attempts. Try again in 5 minutes."* (web and field app) |
| 2 | Correct password within the 5 minutes | Same lock message |
| 3 | After 5 minutes, correct password | Signed in |
| 4 | Change to 5 / 15 and repeat | Locks on the 5th, message says 15 minutes |
| 5 | Script 400 `GET /premises?per=50` in one minute as one user (`for i in $(seq 400); do curl -s -o /dev/null -w "%{http_code}\n" -H "Cookie: <session>" https://api-smart360.bynry.com/api/<tenant>/premises?per=50; done \| sort \| uniq -c`) | ~300 × `200`, then `429` with a `Retry-After` header |
| 6 | Same for an export 12 times in a minute | 10 × success, then 429 |
| 7 | WAF in Block: 2,100 requests in 5 minutes from one address | WAF 429 after ~2,000; CloudWatch `BlockedRequests` rises for W1 |
| 8 | Normal use: open 20 screens quickly | Never a 429 |

---

## 3 · Arbitrary HTTP methods — closed, not exploitable

### Reasoning for the audit
1. **Methods are enforced per endpoint by the application.** Each API view declares the HTTP methods it implements (Django REST Framework `@api_view([...])` / viewset actions). Any other method is answered **405 Method Not Allowed** with an `Allow` header listing only the implemented methods — before any business logic, authentication-dependent data access or database read runs. The tester's own retest shows this: `PUT`, `PATCH`, `DELETE` → **405**, `Allow: OPTIONS, GET, POST` on `/premises`.
2. **The CORS preflight list is API-wide by design, and is not an execution path.** `Access-Control-Allow-Methods` (from `django-cors-headers`) answers a browser's question *"may a page from an allowed origin ask with this method?"*. It is one list for the whole API because other endpoints legitimately use `PUT`/`PATCH`/`DELETE` (saving settings, removing records). It grants nothing on its own: the endpoint still refuses a method it does not implement (point 1).
3. **Only our own origin is allowed.** `CORS_ALLOWED_ORIGINS` holds exactly one origin per environment (`https://app.bynry.com` in production) and is never `*`; credentials are allowed only for that origin (`CORS_ALLOW_CREDENTIALS=True` with an explicit origin, which browsers require). A page on any other domain gets no CORS permission at all, so it cannot read responses or send credentialed cross-origin `PUT`/`PATCH`/`DELETE`.
4. **CSRF and session protection still apply** to every state-changing method from the browser (origin guard + session cookie rules), independent of CORS.
5. **Narrowing the preflight per endpoint is not supported** by the CORS library and would break legitimate screens; it adds no protection given 1–3.

**Conclusion:** arbitrary method execution is not possible; the advertised preflight methods are not exploitable. **Recommend closing the finding.**

### Evidence pack to attach
| # | Evidence | How it is produced |
|---|---|---|
| E1 | The tester's retest table (405 ×3, `Allow` header) | Already in the report |
| E2 | Per-endpoint method list from our published API description (`06-backend/openapi/schema.json`) — e.g. `/api/{tenant}/premises`: `get`, `post` only | `jq '.paths["/api/{tenant}/premises"] \| keys' 06-backend/openapi/schema.json` |
| E3 | Automated test run: every API path answers **405** to each method it does not declare (development team adds this test; output attached) | `pytest tests/test_vapt_http_methods.py -v` |
| E4 | CORS configuration: one allowed origin, never `*` | `06-backend/config/settings/base.py` (`CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_CREDENTIALS`, `CORS_URLS_REGEX`) + the production value from the task definition |
| E5 | Cross-origin proof: a preflight from a foreign origin gets no permission | `curl -si -X OPTIONS https://api-smart360.bynry.com/api/<tenant>/premises -H "Origin: https://evil.example" -H "Access-Control-Request-Method: DELETE"` → response has **no** `Access-Control-Allow-Origin` |
| E6 | Same-origin method refusal | `for m in PUT PATCH DELETE TRACE; do curl -s -o /dev/null -w "$m %{http_code}\n" -X $m -H "Cookie: <session>" https://api-smart360.bynry.com/api/<tenant>/premises; done` → 405 ×3 and TRACE 405 |

---

## 4 · CSP header on app.bynry.com — one-time setup

### Why the scan saw none
The web build already carries a Content Security Policy, but **inside the page** (`<meta http-equiv="Content-Security-Policy">` in `index.html`) because S3 cannot send headers. Scanners check **headers**, and a meta policy cannot carry `frame-ancestors`. The fix is to send the **same policy as a header** from CloudFront.

### The policy (production — exactly what the build uses today, plus framing protection)
```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: blob: https://api-smart360.bynry.com https://server.arcgisonline.com; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self' https://us.i.posthog.com https://us-assets.i.posthog.com https://api-smart360.bynry.com; frame-src 'self' https://api-smart360.bynry.com; object-src 'self' https://api-smart360.bynry.com; base-uri 'none'; form-action 'self'; frame-ancestors 'self'
```
- It is the policy every production page already obeys (generated by `07-frontend/scripts/deployConfig.mjs` from `server.mjs`), so sending it as a header **adds no new restriction** — nothing can break that is not already broken.
- `'unsafe-inline'` is on `style-src` only (the UI library sets inline styles); scripts are `'self'` only.
- If the build's hosts change (a new analytics or map host), the development team will send DevOps the new line. `node -e 'import("./scripts/deployConfig.mjs").then(async m=>console.log(m.bakedPagePolicy(await m.readBasePolicyDirectives(),"https://api-smart360.bynry.com")))'` in `07-frontend/` prints it.

### Steps (AWS console) — DevOps
1. **CloudFront** → **Policies** → **Response headers** tab.
2. If the distribution already uses a custom response headers policy (it sets X-Frame-Options, HSTS, etc.), **select it → Edit**. If it uses a managed one (e.g. `SecurityHeadersPolicy`), choose **Create response headers policy** and re-tick the same security headers it had.
3. **Name:** `smart360-app-security-headers`.
4. **Security headers** section → tick **Content-Security-Policy** → paste the policy above → **Origin override: ticked**.
5. Keep the existing ones: Strict-Transport-Security, X-Content-Type-Options (`nosniff`), X-Frame-Options (`SAMEORIGIN`), Referrer-Policy.
6. **Create** / **Save changes**.
7. **CloudFront** → **Distributions** → the app.bynry.com distribution → **Behaviors** → select **Default (*)** → **Edit** → **Response headers policy** = `smart360-app-security-headers` → **Save changes**. Repeat for any other behaviour (e.g. `/assets/*`).
8. Wait until the distribution status is **Deployed** (a few minutes). No invalidation is needed: response header policies apply to cached responses too.

**Rollback:** set the behaviour's response headers policy back to the previous one and save.

### Test
| # | Do | Expect |
|---|---|---|
| 1 | `curl -sI https://app.bynry.com/ \| grep -i content-security-policy` | One line with the policy above |
| 2 | `curl -sI https://app.bynry.com/assets/<any js file> \| grep -i content-security` | Present on assets too |
| 3 | Chrome → app.bynry.com → sign in → DevTools **Console** | **No** "Refused to load … Content Security Policy" errors |
| 4 | Walk: dashboard, Assets map (tiles load), Work map, open a bill PDF, upload a logo, analytics events (Network tab shows posthog calls 200) | All work |
| 5 | https://securityheaders.com/?q=app.bynry.com | CSP shown as present |
| 6 | Framing test: an HTML file with `<iframe src="https://app.bynry.com">` opened from your PC | Frame refused |

---

## 5 · HSTS on the API — ECS task definition

### Why it was missing
The backend supports HSTS but it is **off by default** (`SECURE_HSTS_SECONDS=0` in `06-backend/config/settings/production.py`), on purpose — once a browser has seen HSTS it cannot be taken back for that duration. The backend already trusts the ALB's `X-Forwarded-Proto` header (`SECURE_PROXY_SSL_HEADER`), which is what lets it know the request was HTTPS.

### Value (approved: 5 minutes, upgrade later)
| Variable | Value | Meaning |
|---|---|---|
| `SECURE_HSTS_SECONDS` | **`300`** | Browsers use HTTPS only for this host for 5 minutes after each response |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | **`false`** (or leave unset) | Only `api-smart360.bynry.com`, not other bynry.com subdomains |
| `SECURE_HSTS_PRELOAD` | **`false`** (or leave unset) | Not submitted to browser preload lists |

**Impact:** none on the application. The API is already HTTPS-only; HSTS only stops a browser from ever trying plain HTTP to this host. 300 seconds means any mistake clears itself in 5 minutes.

### Steps (AWS console) — DevOps
1. **ECS** → **Task definitions** → the backend task family → select the latest revision → **Create new revision**.
2. **Container** → the backend (Django/gunicorn) container → **Environment variables** → **Add**: `SECURE_HSTS_SECONDS` = `300`.
3. **Create**.
4. **ECS** → **Clusters** → the cluster → **Services** → the backend service → **Update** → **Revision** = the new one → **Force new deployment** → **Update**.
5. Wait until the new tasks are **Running** and the old ones stopped.
6. Confirm the ALB → target group forwards `X-Forwarded-Proto: https` (ALB does this by default for HTTPS listeners).

**Rollback:** previous task definition revision → update service.

### Test
| # | Do | Expect |
|---|---|---|
| 1 | `curl -sI -H "Cookie: <session>" "https://api-smart360.bynry.com/api/<tenant>/premises?per=50" \| grep -i strict-transport` | `Strict-Transport-Security: max-age=300` |
| 2 | Same URL without the session cookie (answers 401) | Header still present — it is added to every HTTPS response |
| 3 | Use the app normally (web + field app) | No change |
| 4 | If the header is missing | Check the ALB passes `X-Forwarded-Proto: https`; Django sends HSTS only on requests it sees as secure |

**Later upgrade:** `86400` (1 day) → then `31536000` (1 year). Add `includeSubDomains` only after every bynry.com subdomain is confirmed HTTPS-only.

---

## Order of work and closing the findings
| Step | Who | What | Closes |
|---|---|---|---|
| 1 | Development | Release: PNG/JPG logos, SVG refusal, blocked-request message, lockout message, app rate limits A1–A4 (env-tunable), 429 handling, HTTP-method evidence test — **SHIPPED in 2.604.0 (2026-10-27)**: `DEF-TEN-10618`, `DEF-SHL-10619`, `DEF-IDN-10620`, `DEF-SHL-10621`, `DEF-SHL-10622`. **For DevOps:** set `CACHE_URL` (Redis) on the backend task, or each worker counts A1–A4 on its own; `APP_RATE_LIMITS_ENABLED=false` switches A1–A4 off without a release. "Heavy actions" (A3) = exports, imports and their commit/load, bulk actions, bill-run start/calculate/issue/release/catch-up, print sets, collections run, report *run now*, runbook runs, integration run/export — reading a report on screen is not one. E3 run: 1,062 API addresses, 997 checked (4,814 calls, all 405), 65 not checkable as a System Admin (customer-portal session addresses, refused before the method check) | 1 (code), 2 (code), 3 (evidence) |
| 2 | DevOps | HSTS env var (section 5) | 5 |
| 3 | DevOps | CloudFront CSP (section 4) | 4 |
| 4 | DevOps | WAF upload exceptions (1-A) | 1 |
| 5 | DevOps | WAF rate rules W1–W3 in **Count** | — |
| 6 | DevOps + Development | After 7 days: review Count metrics, switch W1–W3 to **Block** | 2 |
| 7 | QA / VAPT | Run each section's **Test** table; attach section 3's evidence | All |
