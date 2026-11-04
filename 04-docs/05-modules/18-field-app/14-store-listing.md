# 18 · Field app — store listings, privacy declarations and screenshots (T-56)

**Change:** `CR-187-BRC10` · **Task:** T-56 (Phase 15, Release) · **Written:** 2026-10-21, lane RELEASE.
**Status:** DRAFT for the PO. Everything a store console asks for is written here, ready to paste, except the
items in §8, which only the PO (or their Apple / Google admins) can supply.

**Sources, all read for this page, not remembered:** `field-app/src/telemetry/` (the allow list, the scrubber, the
Crashlytics and PostHog adapters), `field-app/src/sync/outbox.ts` (what a capture carries off the handset),
`field-app/src/device/ports.ts` (which device abilities exist), `field-app/app.json` (the permissions the build
declares), the FF-07 *Permissions* board (`wireframes/phone/FF-07-permissions.png`), `12-security.md`,
`03-field-map.md`, and the decision log of 2026-10-21 (*"Field app: crash reporter, technician identity…"* —
Crashlytics; usage data may name the technician, *"Yes, by name"*).

> ⚠ **THE LISTING DESCRIBES THE APP AS IT WILL SHIP, AND THE CODE ON THE BRANCH TODAY DOES NOT YET DO ALL OF IT.**
> On 2026-10-21 none of the native device packages is installed (camera, location, barcode reader, signing pad,
> dictation, push — `device/ports.ts`), nor Crashlytics or the PostHog client. **§7 is a pre-flight table: every
> claim on this page is tied to the thing that must be wired before the listing is submitted.** A store listing
> that claims a feature the binary lacks is rejected by Apple (guideline 2.3.1) and is a false statement to a
> customer; a privacy label that omits a data type the binary collects is worse. Re-read §7 against the build
> being submitted, every time.

---

## 1 · Name, subtitle, category

| Field | Apple App Store | Google Play |
|---|---|---|
| App name (≤ 30) | **SMART360 Next Field** | **SMART360 Next Field** |
| Subtitle (Apple, ≤ 30) | **Jobs, meter routes, offline** | — |
| Short description (Google, ≤ 80) | — | **Field jobs and meter reading routes for utility crews. Works with no signal.** |
| Primary category | **Business** | **Business** |
| Secondary category (Apple) | **Productivity** | — |
| Age rating | 4+ (no objectionable content; questionnaire all *None*) | Everyone (IARC questionnaire: utility / business tool, no user interaction between users, no purchases) |
| Price | Free (the utility's subscription pays for the product; nothing is sold in the app) | Free; **no in-app purchases, no ads** |
| Contains ads | No | No |

The name is the one the boards draw (FF-01 Splash: *SMART360 Next* over *Field*). The home-screen label under the
icon shows about 12 characters; iOS and Android shorten it themselves to *SMART360 Ne…* — if the PO wants a shorter
home-screen name, that is `expo.name` in `field-app/app.json` and does not have to match the store name.

## 2 · Descriptions

**Apple promotional text (≤ 170, editable without a new build):**

> Your day's jobs and meter routes on one handset, signal or not. Everything you capture waits safely and sends
> itself when you are back in range.

**Full description (both stores, ≤ 4,000; plain text):**

> SMART360 Next Field is the handset app for the technicians and meter readers of utilities that run SMART360. It is
> for a utility's own staff and contractors: you sign in with the technician ID and password your office gives you.
>
> YOUR DAY
> • Today's work orders in appointment order, with priority shown on each one.
> • Nearby unassigned work you may claim, if your utility allows it.
> • The address of every stop travels with the job, so it is there offline.
>
> ON THE JOB
> • The whole job template: safety checks, tasks, materials, readings and help, each with a count.
> • Photos taken where they prove something — against a task or a reading.
> • Readings outside the expected range are flagged for a second look, never refused.
> • The customer's balance and whether a payment cleared, for staff your utility allows to see it. The app shows
>   money and never takes a payment.
> • A customer signature on the handset when the job asks for one.
>
> METER READING ROUTES
> • Download a route, walk it stop by stop, and read each meter by typing or by scanning its barcode or QR code.
> • A meter that is not on your route is never silently accepted.
> • Turn the route in when you are done; anything unread is shown to you first.
>
> NO SIGNAL? KEEP WORKING
> • Everything you capture is kept on the handset and sent when you are back in range — readings in batches, photos
>   after them, on wi-fi by default.
> • An expired sign-in never throws away captured work.
> • The sync indicator shows how far the handset and the office are apart, as a number.
>
> BUILT FOR THE FIELD
> • Large touch targets for gloved hands.
> • Light, dark and a high-contrast Sunlight theme.
> • Several technicians can share one handset; each person's unsent work stays theirs and is sent under their name.
>
> PRIVACY
> • Your location is read only while the app is open, to stamp readings and photos and to show nearby work.
> • Diagnostics (crash reports and usage events) carry your technician name and ID so your utility can help you,
>   and never include customer names, addresses, account numbers, balances, readings, photos or signatures.
>
> SMART360 Next Field needs an account from a utility that uses SMART360. It does not work on its own.

**What the description deliberately does NOT say**, because the app does not do it: take payments; work without an
account; track your location in the background; chat between crews (dispatch messages only, `R29`); show a map
offline (the map needs a signal, `R31`); dictate notes (the dictation port is unwired until a speech package is
chosen — add the line only when it ships, §7).

**What's new (first release):** *First release of the native field app. It replaces the web field app.*

## 3 · Keywords (Apple, ≤ 100 characters, comma-separated, no spaces)

`utility,meter,reading,work order,field service,technician,route,offline,water,electric,gas`
(90 characters). Google has no keyword field; its search reads the title and descriptions above.

## 4 · Screenshots

Taken from the running app on a **demo tenant with invented customers** — never a real utility's data, because a
screenshot is published to the world (Security §5: no customer data leaves the handset; a store image is the most
public place it could go). All in the **light** theme except the two theme frames, which exist to show the themes.
Each frame is the drawn board named below (`wireframes/`), captured from the built screen, not exported from the
drawing.

**Phone** — Apple 6.9" (1320 × 2868) and Google phone (1080 × 2340 or larger), same eight frames, same order:

| # | Screen | Board | Theme | Caption (≤ 6 words, B14 rule 33) |
|---|---|---|---|---|
| 1 | FF-63 Home | `phone/FF-63-home.png` | light | Your day at a glance |
| 2 | FF-10 Today | `phone/FF-10-today.png` | light | Jobs in appointment order |
| 3 | FF-15 Job | `phone/FF-15-job.png` | light | The whole job, one screen |
| 4 | FF-16 Safety | `phone/FF-16-safety.png` | light | Safety checks before work |
| 5 | RW-05 The walk | `reads/RW-05-the-walk.png` | light | Meter routes, stop by stop |
| 6 | FF-38 Scan | `phone/FF-38-scan.png` | light | Scan the meter's barcode |
| 7 | FF-50 Sync | `phone/FF-50-sync.png` | light | No signal? It waits safely |
| 8 | FF-55 Sunlight theme | `phone/FF-55-sunlight-theme.png` | sunlight | Readable in full sun |

**Tablet** — Apple 13" iPad (2064 × 2752, required because `ios.supportsTablet` is true) and Google 10" tablet
(landscape, 2560 × 1600 or larger); Google 7" optional, same frames:

| # | Screen | Board | Theme | Caption |
|---|---|---|---|---|
| 1 | FF-10 T Today | `tablet/FF-10-T-today.png` | light | List and job side by side |
| 2 | FF-15 T Job | `tablet/FF-15-T-job.png` | light | The whole job, one screen |
| 3 | RW-05 T The walk | `tablet/RW-05-T-the-walk.png` | light | Meter routes, stop by stop |
| 4 | FF-13 T Map | `tablet/FF-13-T-map.png` | light | Today's stops on the map |
| 5 | FF-54 T Dark | `tablet/FF-54-T-dark.png` | dark | A dark theme for night |

**Not used, on purpose:** FF-25 Customer and FF-27 Stale money (a balance and a customer's name, even invented, read
as a privacy promise broken), FF-33 Signature (a signature image), FF-05 Sign in (a store reviewer learns nothing
from it). **Google feature graphic** (1024 × 500): the brand mark on brand orange `#ec3013` with *SMART360 Next
Field* in white Archivo — a design task, not a screenshot. **App icon:** 1024 × 1024 (Apple, no transparency) and
512 × 512 (Google) — not yet in the repository; `app.json` carries no `icon` until the PO approves one.

## 5 · Privacy declarations — from what the code sends, not from what we intend

### 5.1 · What leaves the handset, and where it goes (the facts both forms are filled from)

| Channel | Destination | What it carries | Source in code |
|---|---|---|---|
| **The sync** | the utility's SMART360 server, over TLS | everything captured on the job and the route: readings, ticks, materials, notes, photos, **customer signatures**, close-outs, the **position fix** stamped on each (`lat`, `lng` to 6 dp, `accuracy_m`, `fix_at`), `captured_by` (the technician) | `sync/outbox.ts` (`JOB_SYNC_KINDS`, `CaptureLocation`, `PhotoCapture`) |
| **Sign-in** | the same server | the technician ID and password; a device registration (*Van 14 tablet*) | `security/httpAuthApi.ts`, `security/deviceRegister.ts` |
| **Crash reports** | **Firebase Crashlytics** (Google) | the error's class name and the stack as code coordinates only (no message text), the screen id (`FF-nn`/`RW-nn`), recent allow-listed events as breadcrumbs, tenant, role, an install-random device id, **the technician's id and name** | `telemetry/scrubber.ts`, `crashlyticsReporter.ts` |
| **Usage events** | **PostHog** | the eight allow-listed events (app start, day pull, batch send, photo upload, screen view, flow abandoned, job timed, telemetry dropped) with bounded numeric fields and screen ids; tenant, role, device id, **technician id and name** as super-properties; no person profile, GeoIP off, session replay off, autocapture off | `telemetry/allowList.ts`, `posthog.ts` |
| **Map tiles** | Esri, through the tenant's integration policy | the map area being viewed (tile coordinates), as any map does; no name, no account | Stack *Integrations* |
| **Navigation hand-off** | Apple Maps / Google Maps (the user's own app) | a street address, nothing else | Security §5 |

**What never leaves the handset by telemetry** (enforced by the scrubber's allow list, R66): a customer's name,
address, account number, balance, reading, photograph, signature, or any outbox payload. Customer data leaves only
through the sync, to the utility's own server.

**Is any of it "tracking" (Apple) or "sharing" (Google)?** No. Nothing is combined with other companies' data for
advertising, there is no advertising identifier (the app never asks for IDFA/AAID), and Crashlytics and PostHog act
as **service providers** processing on the publisher's behalf — which Google's form excludes from *sharing* and
Apple's form counts as *collection* (so it is declared below as collected).

### 5.2 · Apple — App Privacy ("nutrition label")

*Does this app collect data?* **Yes.** *Used for tracking?* **No, for every type.**

| Apple data type | Collected | Linked to the user | Purposes |
|---|---|---|---|
| Contact Info → **Name** (the technician's own) | Yes | Yes | App Functionality; Analytics |
| Location → **Precise Location** | Yes | Yes | App Functionality |
| User Content → **Photos or Videos** | Yes | Yes | App Functionality |
| User Content → **Other User Content** (readings, notes, task answers, customer signatures) | Yes | Yes | App Functionality |
| Identifiers → **User ID** (technician id) | Yes | Yes | App Functionality; Analytics |
| Identifiers → **Device ID** (a random id minted per install; not IDFA, not hardware) | Yes | Yes | Analytics; App Functionality |
| Usage Data → **Product Interaction** | Yes | Yes | Analytics |
| Diagnostics → **Crash Data** | Yes | Yes | App Functionality |
| Diagnostics → **Performance Data** (durations of start, sync, upload) | Yes | Yes | Analytics |
| Financial Info, Health, Contacts, Browsing, Search History, Purchases, Sensitive Info, Audio | **No** | — | — |

*Linked* is **Yes** throughout because the PO ruled on 2026-10-21 that usage and crash data carry the technician's
id and name (*"Yes, by name"*). If that ruling is ever reversed (tenant, role and device id only), Name and User ID
leave the Analytics purpose and the label is re-filed **before** the build that changes it ships.

**Privacy policy URL:** required by both stores — §8.

### 5.3 · Google Play — Data safety

*Does your app collect or share any of the required user data types?* **Yes.** *Is all of the user data collected by
your app encrypted in transit?* **Yes** (TLS to the server; Crashlytics and PostHog over HTTPS). *Do you provide a way
for users to request that their data is deleted?* **Yes — through their utility**, which administers the account;
the app has no in-app account creation (an account is made by the utility and only *activated* on the handset), so
Play's in-app account-deletion requirement does not apply. Confirm this reading with the PO's Play admin (§8).

| Google category → type | Collected | Shared | Optional? | Purposes |
|---|---|---|---|---|
| Location → **Precise location** | Yes | No | Optional (a reading without a fix is accepted and warned, R91) | App functionality |
| Personal info → **Name** (technician) | Yes | No | Required | App functionality; Analytics |
| Personal info → **User IDs** (technician id) | Yes | No | Required | App functionality; Analytics; Account management |
| Personal info → **Other info** (customer signatures captured on the job) | Yes | No | Optional (a job may not ask for one) | App functionality |
| Photos and videos → **Photos** | Yes | No | Optional | App functionality |
| App activity → **App interactions** | Yes | No | Required | Analytics |
| App activity → **Other user-generated content** (readings, notes, task answers) | Yes | No | Required | App functionality |
| App info and performance → **Crash logs** | Yes | No | Required | App functionality; Analytics |
| App info and performance → **Diagnostics** | Yes | No | Required | Analytics |
| Device or other IDs → **Device or other IDs** (install-random id) | Yes | No | Required | Analytics |
| Financial info, Health, Messages, Audio, Files and docs, Calendar, Contacts, Web browsing | **No** | — | — | — |

*Data processed only on the handset and never sent* (Google does not ask for it, recorded so nobody adds it later):
the customer names, addresses and balances the app SHOWS were downloaded from the utility's server and are not
collected by the app.

## 6 · Permissions, and why — the text each store shows

The build declares exactly what FF-07 draws: **three permissions, each used for one thing** — location, camera,
notifications — plus biometric unlock, which is offered, never required.

| Permission | iOS (`app.json` → `ios.infoPlist`) | Android (`app.json` → `android.permissions`) | Used for |
|---|---|---|---|
| Location, **foreground only** | `NSLocationWhenInUseUsageDescription` | `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` | stamping a reading or photo with where it was taken; nearby work (FF-11, radius default 2 miles, R34) |
| Background location | **not requested** — no `NSLocationAlways…` key | **`ACCESS_BACKGROUND_LOCATION` in `blockedPermissions`**, so no library can add it at build time | — |
| Camera | `NSCameraUsageDescription` | `CAMERA` | job photos; barcode and QR scanning |
| Notifications | asked at runtime (FF-07); **Critical Alerts** entitlement `com.apple.developer.usernotifications.critical-alerts` | `POST_NOTIFICATIONS` (added by the push package when it is installed) | emergency jobs that must break silent mode (`R28`) |
| Biometrics | `NSFaceIDUsageDescription` | `USE_BIOMETRIC` | returning to your own session after the auto-lock; switching technician always takes a password (Security §3) |

`field-app/tests/release/config.test.ts` fails if a background-location key or permission appears in `app.json`.

### 6.1 · Location-use justification

**Apple — the purpose string the user sees (`NSLocationWhenInUseUsageDescription`, already in `app.json`):**

> Your location is stamped on each reading and photo you take, and shows nearby jobs. It is only read while the app
> is open.

**Apple — App Review notes (App Store Connect → App Review Information → Notes):**

> SMART360 Next Field is used by a utility's field technicians and meter readers. The app requests location only
> while in use (When In Use). It reads one position fix at the moment a technician records a meter reading or takes
> a job photo, and stores it with that record so the utility can show where the work was done; it also uses the
> current position to list unassigned jobs within the technician's chosen radius (default 2 miles). The app never
> requests Always / background location and does not track a technician's movements. A reading taken without a fix
> is still accepted. Demo sign-in for review: [technician ID and password supplied by the PO, §8].

**Google — Play Console → App content → Sensitive permissions:** the app does **not** request
`ACCESS_BACKGROUND_LOCATION`, so Play's background-location declaration and video are **not required**. If the
console still asks (it does when any dependency's manifest merges the permission in), the build is wrong: check the
merged manifest (§7 pre-flight) rather than filling the form. The foreground-location text for the Data safety
form and the in-app prominent disclosure is the same sentence as Apple's purpose string.

**Camera purpose string (`NSCameraUsageDescription`):** *The camera takes job photos and scans meter barcodes and QR
codes.* **Face ID (`NSFaceIDUsageDescription`):** *Face ID unlocks your own session after the app locks.*

These strings are English only today. iOS shows the purpose string in the device's language when the app ships
`InfoPlist.strings` per language; the eleven languages of the catalogues are a follow-up through
`10-scripts/i18n_fanin.py` and Expo's `locales` config, not done in this lane.

## 7 · Pre-flight — every claim, and what must be true in the submitted build

| Claim on this page | Must be wired first | State on 2026-10-21 |
|---|---|---|
| Location stamps readings and photos; nearby jobs | `expo-location` behind `device/ports.ts` `LocationDevice` | **NOT installed** — `NO_LOCATION` answers "no fix" |
| Photos; barcode and QR scanning | `expo-camera` (photo + scanner ports) | **NOT installed** |
| Customer signature | a signing pad behind `device/signature.ts` | **NOT installed** — FF-33 offers the recorded alternative |
| Emergency alerts break silent mode | a push package (APNs / FCM) + Critical Alerts in the provisioning profile | **NOT installed**; entitlement requested in `app.json` |
| Biometric unlock | `expo-local-authentication` behind `security/biometric.ts` | **NOT installed** |
| Crash reports (Crashlytics) | `@react-native-firebase/app` + `/crashlytics`, its own JS handler OFF (`crashlyticsReporter.ts`) | **NOT installed** — reports wait on the handset |
| Usage events (PostHog) | `posthog-react-native` client built with `posthogOptions()`; the sync engine calling `gate.reportWork()` | package installed; **not constructed at the app root** |
| Encrypted local store (SQLCipher) | SQLCipher build of SQLite | **NOT installed** (`12-security.md`) |
| Over-the-air updates | `expo-updates` + `eas update:configure` (writes `updates.url`, `extra.eas.projectId`) | **NOT installed** — config in `app.json`, no URL yet |
| "It replaces the web field app" | T-72 decided; `FieldAppNotice` repointed (T-55 hold) | **open** |

Before each submission also: run `npx expo prebuild --no-install` into a scratch copy and read the generated
`Info.plist` and merged `AndroidManifest.xml` for any permission or purpose string this page does not list — a
config plugin can add one, and `config.test.ts` reads only `app.json`.

## 8 · What only the PO can supply

See `15-release-and-rollback.md` §7 — one list for the whole release, so it is never kept in two places.
