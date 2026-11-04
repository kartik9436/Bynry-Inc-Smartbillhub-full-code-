# field-app — SMART360 Next Field (native, React Native)

The field technician and meter-reader app. `CR-187-BRC10`; it supersedes BR-WRK-045 (the phone was a web app).

- **Own `package.json` and lockfile** — React 19 / React Native 0.79 / Expo SDK 53 here, React 18 in `07-frontend`. Never one shared npm install (decision log 2026-10-21, twelve conflicts, #1).
- **Screens are built from images**: `04-docs/05-modules/18-field-app/wireframes/` (B14 rules 42, 44, 45).
- **Tokens** come from `../shared/tokens.ts`, the one source both apps read.
- **The backend is reused**: `06-backend/apps/work` (and `metering`, `identity`, `payments` seams for the new endpoints).
- The design: `04-docs/05-modules/18-field-app/` (plan: `10-execution-plan.md`).

```
npm ci            # in this folder only
npm run typecheck
npm test
npm start         # Expo dev server
```

## Native configuration (the PO supplies; nothing here is in git)

`index.ts` mounts `src/NativeApp.tsx` — `App` with the real handset (`src/device/native/`). Tests mount `App` with fakes.

| What | Where it goes | Without it |
|---|---|---|
| Firebase Android file | `secrets/google-services.json` (added by `app.config.ts` only when BOTH files exist) | the build still works: no Crashlytics (crash reports kept on the handset, unsent) and no Android push |
| Firebase iOS file | `secrets/GoogleService-Info.plist` | as above (iOS push still works through APNs) |
| Android Google Maps SDK key | env `GOOGLE_MAPS_ANDROID_API_KEY` (`app.config.ts`) | the native Android map is never mounted (it would crash the app); FF-13 / FF-14 show *Map not installed*. iOS needs no key |
| Server address | env `EXPO_PUBLIC_API_BASE_URL`, per profile in `eas.json` → `build.<profile>.env` (read at BUILD time) | FF-05 says *No server set* and offers no sign-in; nothing calls a relative `/api/…` |
| Utility (tenant slug) | **nothing to configure — one build serves every utility** (`DEF-FLD-10580`). The office's activation code (Settings › Users › *New app code*) names the utility on FF-56; the handset remembers it. No profile may carry a utility (`tests/release/serverAddress.test.tsx`) | a fresh handset shows *Activate this phone first.* and *First time here? Activate* |
| PostHog project key + host (US/EU) | env `EXPO_PUBLIC_POSTHOG_KEY`, `EXPO_PUBLIC_POSTHOG_HOST` | events wait on the handset, never sent |
| Map tile host (optional) | env `EXPO_PUBLIC_MAP_TILE_HOST` | Esri's public World Street Map host |
| Push: FCM (Android) / APNs key + Critical Alerts entitlement (iOS) | Firebase project; Apple provisioning profile | no pushes; the server sends to no provider yet (`push.py _deliver`) |
| Five push sounds (`new_job.wav` …) | `expo-notifications` plugin `sounds` + `CHANNEL_SOUND` | default sound; ⚠ must land before the first build — Android fixes a channel's sound at creation |
| App name, bundle id / package, store accounts | `app.json` `name`, `ios.bundleIdentifier`, `android.package` — `io.bynry.smart360.field` (PROPOSED; permanent only once uploaded to a store) | no store build |
| EAS project | `app.json` `owner: "bynry"`, `extra.eas.projectId` (`eas init`, 2026-10-22) | — |

`app.config.ts` writes `extra.firebaseConfigured` and `extra.mapsAvailable`; `src/release/nativeConfig.ts` reads them, failing closed. Both change the runtime fingerprint, so an update never crosses between a build with and a build without them.

`firebase.json` keeps Crashlytics' own JavaScript reporting off (generation off, chaining on), so every crash goes through the scrubber; `src/telemetry/firebaseCrashlytics.ts` says why both values.
