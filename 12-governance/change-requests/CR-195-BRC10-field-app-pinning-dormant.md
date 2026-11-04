# CR-195-BRC10 · Field-app certificate pinning dropped as a go-live requirement — kept dormant, hidden from users

**Raised:** 2026-10-28 by the Product Owner, in chat, choosing among options put to them after the 2.603.0 outage (`DEF-FLD-10617`) and the 2026-10-26 beta-only switch.

**Requester's words, verbatim:** *"start A1"*.

**Ruling record:** decision log 2026-10-28, *"Certificate pinning in the field app is DROPPED as a go-live requirement: option A1, the code stays dormant"*, and the same day's *"CORRECTION to the 2026-10-26 entry"*. What was shown: Android's standard certificate check already refuses a fake server on public Wi-Fi; pinning adds protection only against a wrongly issued genuine certificate for our domain or a rooted phone; on 2.603.0 the pins (ISRG/GTS) did not match the server's issuer and every technician was locked out.

## 1 · Classification (step 1 of `13-change-process.md`)
A **change**: it reverses a signed ruling of the PO's own (2026-10-26, *"B. Switch the check off for the beta"*, which kept pinning ON for production and made a production build with it off a build failure). **Fast path (§5):** no business rule, no money and no stored data moves — the pin lists, their endpoint and the phone's settings answer are untouched; only a build default, two screens' visibility and the server-address check change.

## 2 · What signed statement moves, and what stands
**Superseded:** 2026-10-26's *"the production profile keeps it ON and must not ship without a valid issuer list — a release check fails a production build that has pinning off"* and its *"Before go-live … turn pinning on"*; `18-field-app/12-security.md` §4 *Transport*'s *default ON* / *production stays ON* / *Go-live step* (amended in place, dated).
**Corrected (not a ruling, a wrong fact):** 2026-10-26's *"no protection against a fake server on public Wi-Fi"* — appended as a dated correction, the old entry untouched.
**Stands:** `OQ-FLD-12797`'s design (per-utility lists on Settings › Security, platform default, two pins, rotation, adoption only over a pinned connection) — dormant, not deleted. The honest connection errors (*Can't verify the server. Contact the office.*, *The server needs an update.*).

## 3 · Our judgments where the ruling ran out (law 13 — recorded, not re-asked)
1. **Unset means OFF**, in `app.config.ts` and in the phone's `pinningMode`; only the exact word `on` pins. Law 3 is applied, not broken: the safety floor is the OS check, which no config can switch off, and a wrong pin list is what locks the fleet out — so the option you type is now `on`.
2. **`off_for_beta` → `off_by_config`** (internal diagnostics state; never shown).
3. **`https://` only** for the build's server. No profile uses `http` (`development` names no server), so no development exception.
4. **The portal card is hidden by ONE platform setting**, `SBH_FIELD_APP_PINNING_ENABLED` (default false), served as `field_app_pinning_enabled` on the security-policy read AND on the save's answer (the screen replaces its copy with that answer). Added in the view, not in `selectors.security_policy_values`, which is also the sign-in engine's read. A PUT carrying it is ignored.

## 4 · What is built
- **Field app** — `eas.json` (`production` gains `FIELD_APP_PINNING: off`), `app.config.ts` (default off; the production refusal removed), `src/security/pins.ts` (`pinningMode`: only `on`), `src/security/pinning.ts` (dormant; controller default off; state renamed), `src/screens/me/SettingsScreen.tsx` (About line removed), `src/release/serverAddress.ts` (https only). Key `field.ff51.pinningOff` retired from `src/i18n/keys/me.en.json` and from all eleven web catalogues (`10-scripts/i18n_fanin.py` `retire`).
- **Server** — `config/settings/base.py` (`FIELD_APP_PINNING_ENABLED`), `apps/identity/api.py` (`SecurityPolicyView` serves the flag).
- **Web** — `src/api/endpoints.ts` (`field_app_pinning_enabled?`, never on a PUT), `src/features/identity/SettingsSecurityTab.tsx` (the card mounts only when the flag is true).
- **Docs** — `04-docs/05-modules/18-field-app/12-security.md` §4 *Transport*, the sync line, §7 item 2.

## 5 · Tests (red first)
- `field-app/tests/release/pinningSwitch.test.ts` — 4 of 7 RED before the change (production read `on`; `eas.json` production had no `off`; unset read `on`; `''` read `on`), 7/7 after.
- `field-app/tests/security/pinningOff.test.tsx` — 2 of 4 RED (state name; About line present), 4/4 after.
- `field-app/tests/release/serverAddress.test.tsx` — the `http://` case RED, then green.
- `field-app/tests/security/pinning.test.tsx` — the wiring test now asserts both: default config does not initialise the library; `pinning: 'on'` pins.
- `07-frontend/src/features/identity/securityRedesign.dom.test.tsx` — 2 RED (card shown by default; card shown with the flag false), green after; `FieldAppPinsCard.dom.test.tsx` serves the flag on to test the card itself.
- `06-backend/tests/test_cr195_field_app_pinning_dormant.py` — the flag on the read and on the save's answer; not settable; the card's endpoint still answers.

## 6 · Pending verification (not proven by any test here)
1. DevOps to confirm the real issuer of smartbillhub.bynry.com — needed only if pinning is switched back on.
2. One test-phone run with a mitmproxy CA installed on the phone, expecting *"Can't verify the server"*.

## 7 · Version and rollback
**No version bump in this lane** (coordinator's instruction; the release that carries it records the number). **Rollback:** set `FIELD_APP_PINNING=on` on a profile (with a confirmed issuer list) and `SBH_FIELD_APP_PINNING_ENABLED=true` on the server — no code change. Reverting the commits restores the 2026-10-26 behaviour exactly.

**Status:** DONE 2026-10-28.
