# 18 · Field app — technology

**Source:** the design canvas's *Technology stack* page (version `2.587.0`), in full, with `AD-01`–`AD-24` from its
*Architecture decisions* page where they decide a layer, and the PO's rulings in `12-governance/02-decision-log.md`
(2026-10-21). **Keep** is already in the product · **New** is added for the native app · **Retired** leaves with the
web field app.

The scaffold already on the branch (`field-app/`, decision log 2026-10-21 *"The native field app's folder is
`field-app/`"*): **Expo SDK 53, React 19.0.0, React Native 0.79, TypeScript 5.8 strict**, Jest (jest-expo) with
`@testing-library/react-native`, `better-sqlite3` as a dev dependency (it has FTS5) for testing SQL in Node. Its own
`package.json` and lockfile (conflict 1: `07-frontend` is React 18.3.1); it stays out of the Docker build and builds
with Expo/EAS (conflict 12).

---

## 1 · The handset

| Layer | Choice | Standing |
|---|---|---|
| Framework | **React Native** — one codebase for iOS and Android, shipped through both app stores (`AD-01`: *"Not a PWA and not a WebView shell"* — iPhone web push has no custom sound and Safari implements no vibration API, so emergency alerting would be silent on half the fleet) | New |
| Navigation | Native stack and drawer. Pushed screens with native back (`AD-13`); a permanent sidebar on tablet | New |
| Styling | A shared token module — a plain TypeScript object of colours, spacing and type, imported by both web and native. NativeWind optional on top, but **never with its default theme**, which its own docs say is not designed for native devices | New |
| Local store | SQLite for the job and capture queue; MMKV for small key state. Carries forward the existing schema and its per-technician partitioning (`AD-05`, `AD-17`; `03-field-map.md`) | New driver |
| Camera | Native camera for photos and for 1D barcode / 2D QR scanning | New |
| Location | Native geolocation with the existing best-fix-wins rule — lat and lng to 6 decimals, accuracy to 1 | New driver |
| Images | Native image manipulation, carrying the existing rule: 1,600 px long edge, quality stepped down until the bytes fit, never silently giving up. ⚠ **The bytes the rule fits to are `BR-WRK-047`'s 70–100 KB** (PO-ruled), not the ~300 KB the design's Data page assumes (`03-field-map.md` §12) | New driver |
| Push | APNs and FCM with notification channels. Custom sound per alert kind; **Critical Alerts entitlement needed on iOS to break silent mode** (`AD-07`; T-01, applied 2026-10-21, not yet granted) | New |
| Voice | On-device speech-to-text for notes and debriefs | New |
| Font | **Archivo, bundled into the app.** Open licence, so embedding is permitted (`AD-10`; `OQ-272` (a) ratified — *"our style's font"*) | New |

Installed on the scaffold today: `expo-sqlite`, `expo-secure-store`, `expo-crypto`, `expo-file-system`,
`expo-localization`, `expo-font`, `@expo-google-fonts/archivo`, `react-native-mmkv` 3, `@react-navigation/{native,
native-stack, drawer, bottom-tabs}`, `react-native-screens`, `safe-area-context`, `gesture-handler`, `reanimated`,
`@react-native-community/netinfo`, `i18next`, `react-i18next`, `posthog-react-native`. **Not yet installed, and each
layer above needs one:** a camera/scanner module, image manipulation, location, notifications, speech-to-text,
SQLCipher (`12-security.md` §2), and the crash reporter (§5). Adding them is the coordinator's call (it owns the
lockfile).

---

## 2 · Design tokens

**One source, imported by both the web app and the native app. Nothing in a screen names a colour or a number
directly.** (`shared/tokens.ts`; until the web reads it, a test fails when its values drift from `tokens.css` —
decision log conflict 2.)

### The orange, and the one adjustment (`R100`)

The website's orange is `#ec3013` and it stays the brand colour. But white text on it measures **4.20:1**, and the
standard for body text is **4.5:1** — so a primary button filled with it would fail. **Button fill is `#e12e13` —
4.56:1, and 5% off the brand.** Side by side you cannot tell them apart; a contrast checker can. Marks, active
indicators and section labels keep the true brand orange, because large bold text only needs 3:1 and `#ec3013`
passes that at 4.20:1.

| Token | Value | Where it is used |
|---|---|---|
| `brand` | `#ec3013` | The mark, the active nav indicator, section labels. **Never a button fill with white text** |
| `brand-action` | `#e12e13` | Every primary button. 4.56:1 with white |
| `text` | `#201e1d` | All body text and icon strokes |
| `text-muted` | `#605d5d` | Secondary lines, labels, counts |
| `page` / `surface` | `#f3f2f2` / `#eae9e9` | Page behind, and a recessed strip |
| `card` / `border` | `#ffffff` / `#d7d3d3` | Every card. White on `#f3f2f2` — surface on page is too close to read as stacked |
| `success` | `#0f6e3a` / `#e6f4ec` | Done, read, in step, cleared |
| `warning` | `#e08a1e` / `#fdf0d8` | Flagged, stale, could not be read |
| `danger` | `#e0341a` / `#fde4df` | Emergency, refused, required, accept-anyway |
| `info` | `#1d4ea8` / `#e6eefb` | Added in the field, explanations, needs a signal |

### Spacing — a 4px scale, and only these seven

| Token | Value | What it is for |
|---|---|---|
| `space-1` | 4px | Inside a chip or badge; a label and the line under it |
| `space-2` | 8px | Clearance between two touch targets. Also the gap between cards in a list |
| `space-3` | 12px | Phone screen gutter; footer padding; icon-to-text gap in a row |
| `space-4` | 16px | Padding inside a card; the sidebar's gutter |
| `space-5` | 20px | Tablet screen gutter; padding inside a wide pane |
| `space-6` | 24px | Between sections of one screen |
| `space-8` | 32px | Above a page head; around a centred sign-in card |

**6, 10, 14, 18 and 22 do not exist.** A value off the scale is how a product drifts — the finance sweep of the web
app measured 65 off-scale values in 11 files, 25 of them in the app frame, and that is what put this rule in the UI
standard (B14 rule 44).

### Touch, type and radius (`AD-08`, `AD-11`, `R39`; B14 rule 45)

| | Value | |
|---|---|---|
| Primary action | 56pt | The one thing the screen is for |
| Any control, floor | 48pt | Nothing smaller ships. Swept 2026-10-20: 104 raised, 0 left |
| Most-tapped control | 56pt | A quantity stepper hit a hundred times with gloves on |
| Clearance | 8pt | Between any two targets |
| Native type | 22 / 17 / 15 / 13 / 12 | Title, section, body, label, micro. The web page-head is 32px; a phone title is 22px, deliberately |
| Radius | 4 / 6 / 8 / 22 | Chip, button, card, pill |
| Tablet frame | 220 / 340 / rest | Sidebar, list pane, detail pane, inside 1024 |

**Three themes from one token set** (`AD-09`): Light (default) · Dark (basements and night) · Sunlight (maximum
contrast: pure white, black text, 2–3px borders, one size up). *"Dark and sunlight are not inverses of each other.
Dark lowers light output; sunlight raises contrast."*

---

## 3 · The server — unchanged (`AD-02`)

| Layer | What it is | Standing |
|---|---|---|
| Application | Django / Python · PostgreSQL 16 · row-level security forced, every tenant table scoped | Keep |
| Work module | `06-backend/apps/work/` — 40+ modules, 9 migrations, its own Celery queue | Keep |
| The day read | `mobile.py` — the day, the job bundle and the device register. The whole job in one response, so the phone has nothing to go back for | Keep |
| The sync | `sync.py` — a day's captured work applied once. Per-item results, never a boolean: accepted / duplicate / refused. **A SAVEPOINT per item**, because a failed statement poisons a PostgreSQL transaction and the test suite's SQLite cannot see it | Keep |
| Push | `push.py` on its own named queue. A dead provider retries with jitter; the assignment stands and nothing is lost | Keep |
| Evidence | `evidence.py`, `work_documents.py` — photos, signatures, byte checks | Keep |
| Safety | The gate is re-derived server-side. A completion carrying an unticked mandatory row is refused, naming the row | Keep |
| Audit | Every money action writes `audit_log`. Issued financial rows are never updated — corrections are new rows | Keep |

The server additions the app needs are `07-endpoints.md` §2–§6.

---

## 4 · Integrations

| | | Standing |
|---|---|---|
| Mapping | Esri street tiles through the tenant's integration policy — no key to start, no new environment variable. A paid key or the utility's own tile server is a change to that one connection, never to a screen (`AD-06`, ruled 2026-10-04 *"do not ask about this again"*). **Tiles need a signal; the job does not** (`R31`) | Keep |
| Navigation | Hand-off to Google Maps or Apple Maps by deep link | New |
| Payments | **None on the handset.** The field app reads money and never writes it (`R16`) | Out of scope |

---

## 5 · Telemetry and diagnostics

⚠ **RULED 2026-10-21 — THE CRASH REPORTER IS CRASHLYTICS** (decision log 2026-10-21, *"Field app: crash reporter,
technician identity…"*). The design's `AD-18` and this page chose **Sentry** — *"Chosen over Crashlytics because our
faults will be in JavaScript far more often than in native code, and because it can be self-hosted if the utility
requires it"*; `AD-18`: *"Crashlytics is native-crash-first and its JavaScript story is weaker"*. **That choice is
SUPERSEDED for crash reporting by the PO's ruling; PostHog is unchanged.** The design's reasoning is kept here so the
trade the ruling made is visible, not so it can be re-argued (law 13).

| Layer | Choice | Standing |
|---|---|---|
| Crash reporting | **Crashlytics** (ruled 2026-10-21). JavaScript errors and native crashes, with source maps for the bundled JavaScript and breadcrumbs leading up to the fault. *Was: Sentry (`AD-18`), superseded* | New |
| Product analytics | **PostHog** — events, funnels and retention, so we can see which screens are actually used, where a technician abandons a flow, and how long a job really takes. Self-hostable, which is why it is preferred to a hosted-only product in a multi-tenant utility | New |
| Feature flags | **PostHog flags.** The reason this matters more on a phone than on the web: an app-store review takes days, so without flags a held feature cannot be released without shipping a build. A flag read always has a cached default, so an offline handset behaves deterministically (`R71`) | New |
| Both queue offline | A whole shift can pass with no signal, so crash reports and analytics events queue locally and send later — **a third queue beside the outbox and the photo queue. It always yields to both.** A day of readings matters more than our telemetry (`R67`) | New |
| Performance | The paths that actually hurt — app start, the day pull, a batch send, a photo upload. *"Measuring the sync is how we find out that a flag was silently ignored, which this project has already paid for once."* ⚠ **The design gave this to Sentry's performance tracing; with Sentry superseded, no tool is named for it.** Not decided here — recorded for the coordinator | New — tool unnamed |
| Session replay | **Off. Not configured carefully — off.** A replay of a technician's screen records customer names, addresses, balances and signatures (`R68`) | Refused |

**What telemetry must never do** (`AD-19`, `R66`–`R72`):

1. **It never carries customer data.** No name, no address, no account number, no balance, no reading, no
   photograph, no signature — and never an outbox payload. Every event and every breadcrumb goes through a scrubber
   before it leaves the handset, **with an allow list of fields rather than a block list** of the ones we thought of.
   (The same scrubber sits in front of Crashlytics — T-74, proved by T-76.)
2. **It is never the audit trail.** `audit_log` on the server is the record, and a third-party analytics product is
   not a record of anything. Nobody may later reach for PostHog to answer a question about what happened to a
   payment.
3. **Identity — RULED 2026-10-21: analytics MAY name the individual technician.** The design recommended *"tenant,
   role and an anonymous device id — enough to learn that disconnect orders take nine minutes longer than
   scheduled, not enough to tell you which person is slowest"*, and said *"Whether individual technicians may be
   identified is a workforce question the utility owns … it needs your nod either way."* The PO gave that nod: the
   technician may be identified. **Customer facts still never leave the handset** (rule 1 is untouched), and FF-63's
   *"no reads-per-hour, no average job time, no ranking"* (`R120`) is a rule about the technician's own SCREEN and is
   not changed by this.
4. **It never blocks or slows the work.** A dead telemetry endpoint, a full queue or a failed flag read must be
   invisible to the technician.
5. **It is visible in Settings.** One line on FF-51 saying diagnostics are on, and what they do not include — three
   words, not a policy (T-75).

---

## 6 · How the code is laid out

The handset mirrors the server's module boundaries, so a write that crosses one is as visible here as `G78` makes it
there.

```
field-app/
  src/
    screens/          one folder per flow stage, matching the FF and RW ids
      getting-in/     FF-01..09, FF-56..57
      the-day/        FF-10..14, FF-63 Home
      the-job/        FF-15..24, FF-58, FF-59, FF-60
      customer-money/ FF-25..31, FF-61
      closing/        FF-32..36
      assets-alerts/  FF-37..43, FF-62
      technician/     FF-44..55
      reads/          RW-01..29 — its own mode, same app
    components/       the kit. A screen imports; it never defines a control inline
    tokens/           colour, spacing, type — the SAME object the web app imports
    db/
      schema.ts       the 19 tables
      scoped.ts       the ONLY way to read a scoped table
      migrations/     numbered, forward-only, like the server's
      queries/        one file per table; nothing writes SQL in a screen
    sync/
      outbox.ts       capture, keys, batches of fifty
      photos.ts       the second phase
      delta.ts        watermarks, tombstones
      receipts.ts     accepted / duplicate / refused
    seams/            one READ-ONLY file per server module — mirrors apps/work/seams/
                      metering.ts assets.ts customers.ts billing.ts
    scan/             barcode and QR, below
    security/         the two credentials, the keystore, auto-lock
    i18n/             the eleven catalogues, shared with the web app
    telemetry/        the crash reporter, PostHog, and the scrubber
  tests/
    screens/          mounted at their real route, never bare
    sync/             the thousand-reading run, the handover, the tombstone
    doors.test.ts     every screen has something that opens it
    scoping.test.ts   no query reaches a scoped table unfiltered
```

The brief that started Phase 1 adds `theme/`, `session/`, `navigation/` beside these, and puts the token module at
`shared/tokens.ts` at the repo root (decision log 2026-10-21). `schema.ts` says *"the 19 tables"*; with
`work_order_templates` it holds twenty (`03-field-map.md` §2).

| Rule of the layout | Why |
|---|---|
| Screens by flow, not by type | Six screens of one journey sit together. A `containers/` and `views/` split would scatter them and nobody would find the journey again |
| No SQL in a screen | Every query lives in `db/queries/`, one file per table. That is what makes the screen-to-table map on the Mobile data tab checkable rather than aspirational (`R119`) |
| Seams are read-only, by file | The same shape as `apps/work/seams/`. A lane that wants to write another module's table has to add a function to a file whose name says it cannot |
| One tokens module, two renderers | `tokens/` is a plain TypeScript object imported by the web app and the native app. A colour changes in one place |
| `scoping.test.ts` exists on purpose | A handset is shared, so ten tables carry `technician_id` and every read must filter on it. The test walks the query layer and fails any statement that touches a scoped table without going through `scoped.ts`. The column only has to be forgotten once — and the screen then renders perfectly with the wrong person's data in it, which no other check would catch (`R133`) |
| `doors.test.ts` exists on purpose | It asserts every screen has an inbound route. **Fourteen screens had no door on 2026-10-20, found by sweeping rather than by any check.** This is that sweep, made permanent (`R99`) |

---

## 7 · Barcode and QR

**Scanning is the first-class way to identify a meter. Typing is the fallback, not the other way round** (`R83`).

| Part | What it does |
|---|---|
| Formats read | **1D:** Code 128, Code 39, ITF, UPC-A, EAN-13 — what a utility's own asset labels use. **2D:** QR and Data Matrix. Data Matrix matters: it is what actually fits on a meter plate the size of a coin |
| What is encoded | Usually the badge number, sometimes the serial, occasionally a URL with the serial in it. The app does not care — it takes the payload, strips a URL prefix if there is one, and resolves it |
| How it resolves | **Serial, then badge, then device ID** — one order, everywhere, so the same sticker always finds the same asset. Against the local store first; the server only when asked (`R43`). ⚠ the server has no `badge` or `device id` column yet (`03-field-map.md` §2.1) |
| Torch | On the scan screen, one tap. Meters live in pits and basements — a scanner without a torch is a scanner that works in a showroom |
| Continuous mode | On a route the camera stays open: scan, read, scan, read. 151 meters is 151 camera launches otherwise, and each one is a second and a half |
| Duplicate guard | The same code twice within a few seconds is one scan, not two. Without it a steady hand reads one label eight times |
| When it will not read | Dirty, bent or painted-over labels are normal. After a few seconds the screen offers *type it instead* rather than sitting there. The reading is never lost to a bad label |
| When it reads the wrong thing | A code that resolves to a meter not on this job or route opens FF-18 Different meter or RW-19 Not on the route. **It is never silently accepted** — a guessed meter puts a year of the wrong consumption on somebody's bill. (*FF-18 is "Add step" in the screen list; the design's sentence means RW-18 Different meter for a route — recorded, not corrected in the design*) |
| Permission | The camera permission, asked once at FF-07, shared with photographs |
| Implementation | The platform scanners through the native camera module — Apple's Vision and Android's ML Kit. Both read Data Matrix, both are on-device, neither needs a signal |

**Scanning is offline work.** The payload is matched against the route or job already on the handset, so it is as
fast in a basement as at the depot. Only an off-route code that the handset has never heard of needs the server — and
even then the reading can be taken and sorted out later.

---

## 8 · Leaving with the web field app

| | | Standing |
|---|---|---|
| `work-mobile-sw.js` | Service worker, 5,817 bytes — no equivalent in a native app | Retired |
| `work-mobile.webmanifest` | Install manifest and its icon | Retired |
| `offlineStore.ts` | IndexedDB store — its schema and model carry over, the implementation does not (`AD-03`, `AD-05`) | Re-derived |
| `FieldAppNotice` button | Points at a web address. Must be repointed at the app store when the native app ships — with a test that fires on the day (`AD-16`, T-55) | Repoint |

⚠ **"Retired" is the design's word; it has not happened and is not scheduled.** The PO DEFERRED the decision (T-72,
2026-10-21: *"once native app is build after that we will decide"*), and until then the web field app
(`07-frontend/src/features/work/mobile/`, its service worker and `FieldAppNotice`) **stays untouched** (decision log
conflict 9).

---

## 9 · Scale this is built for

North American utilities of **up to 40,000 accounts, run by 10 to 20 staff** — tiers T7 (up to 3,000), T6 (3–10K) and
T5 (10–40K), all in scope. **Eleven services:** electric, water, gas, sewer, trash, storm water, solar, broadband,
thermal, battery, fire. **No hard caps anywhere, server pagination everywhere, and nothing built that would have to be
removed when the next tier arrives** (`NFR-3`, `NFR-5`; the same doctrine as `AD-15` for asset types and `R87` for one
reader per route).

---

## 10 · What has to be true before code starts

1. The Apple Critical Alerts entitlement applied for — days to weeks, and it cannot be compressed. **Applied
   2026-10-21 (T-01).**
2. BR-WRK-045 recorded as superseded, with a change request, because it reverses a confirmed rule. **Done —
   `CR-187-BRC10`.**
3. OQ-272 closed — Archivo ratified. **Half: (a) ruled; (b) web self-hosting open.**
4. The native type ramp written into the UI standard beside the web one. **Done — B14 rule 45.**
5. Every ruling from this conversation written into the decision log. **Done — T-05.**
6. A ruling on whether analytics may identify an individual technician — the build assumes not until told otherwise.
   **Ruled 2026-10-21: it may** (§5 item 3).
