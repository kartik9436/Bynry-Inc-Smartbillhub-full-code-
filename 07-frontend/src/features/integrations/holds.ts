// ── Trace ──────────────────────────────────────────────
// Defects: DEF-INT-4224 (half the live cards offered *Connect* over a provider
//          that cannot be connected, and said so only at the last step of a
//          filled form) · DEF-INT-4235 (sign-in refuses on every deployment and
//          the card cannot see it) · DEF-GOV-4232 (G103 reads only the portal,
//          so none of these rows is covered by a merge gate)
// Rules:   CLAUDE.md hard-won law 2, mirror clause (*"when you write a hold,
//          write the test that fires when the hold expires, in the same
//          commit"*) · B14 rule 33 (a refusal is five or six words) ·
//          BR-INT-037 (no provider is named in front-end code) · BR-INT-001
// Tests:   src/features/integrations/holds.test.ts (the expiry conditions) ·
//          src/features/integrations/IntegrationsTab.test.tsx (the drawing)
// Impacts: IntegrationsTab.tsx (the card's action button) · ConnectModal.tsx
// ───────────────────────────────────────────────────────
//
// EVERY HOLD THE INTEGRATIONS SCREENS DRAW, AND WHAT WOULD RELEASE IT.
//
// This is `07-frontend/src/portal/routing/holds.ts` applied one module over,
// for the reason that file gives: a hold is a rule with a CLOCK in it, correct
// the day it is written and silently false the day the thing it waits for
// arrives. The portal learned that four times in a week. Integrations drew its
// first holds today and starts with the register rather than without it.
//
// ⚠ **G103 CANNOT SEE THIS FILE, AND THAT IS FILED RATHER THAN ASSUMED
// (`DEF-GOV-4232`).** The gate scans paths beginning `portal/` and hold keys
// matching `(?:portal|settings)\.`, so every row below is outside its reach and
// it reports a clean pass over them. Widening it was deliberately NOT done here
// — it is a merge gate for four live CR-069 lanes and broadening its scan
// mid-flight fails their merges on holds they did not write. What covers these
// rows instead is `holds.test.ts`, which runs in the ordinary suite every lane
// runs, and which asserts each expiry condition directly.
//
// ⚠ **THE STRONGEST ROW HERE IS THE ONE THAT CANNOT ROT AT ALL**, and it is
// worth naming because it is the shape to reach for. `notConnectable` is
// answered by the SERVER on every draw, from `adapter_registered` — so the day
// an adapter is registered the card goes live with no edit anywhere, and there
// is no second act to forget. A hold that releases itself is better than a hold
// with a good test, and both are better than a hold with a date in a plan.

/** What would make a hold false — the portal register's vocabulary, unchanged. */
export type HoldExpiry =
  /**
   * The SERVER re-decides this on every draw, so it CANNOT rot. The strongest
   * kind: no lane has to remember anything for the hold to lift.
   */
  | { readonly kind: "server"; readonly note: string }
  /** A ruling says this does not open here. Only a CR reverses it. */
  | { readonly kind: "policy"; readonly note: string }
  /**
   * A deferral nothing mechanical can see. **THE WEAKER KIND** — counted and
   * printed rather than implied, so the number of promises nobody is keeping
   * is visible instead of being discovered by a customer.
   */
  | { readonly kind: "unwatched"; readonly note: string };

export const INTEGRATIONS_HOLDS: Readonly<Record<string, HoldExpiry>> = {
  // ── The server re-answers it every draw — cannot rot ────────────────────
  "integrations.hold.notConnectable": {
    kind: "server",
    note:
      "DEF-INT-4224. The card's *Connect* is held when this product has nothing " +
      "that can talk to the provider — `adapter_registered` false, and not one of " +
      "the connectors we never dial. Seven of the fourteen live cards were in that " +
      "state on 2026-09-06 (accounting_file, email_bulk, geocoder_census, gis_city, " +
      "map_tiles_public, meters_neptune360, print_vendor) and every one of them " +
      // ⚠ THOSE ARE THE KEYS AS THEY WERE ON THAT DATE AND THEY ARE LEFT
      // ALONE ON PURPOSE: a record of what was true at a moment is evidence,
      // and editing it to match a later rename stops it being evidence. Two
      // have since moved — `email_bulk` is now `sendgrid` (CR-115-BRC05) and
      // `gis_city` is now `gis_esri` (CR-110-BRC04) — so a grep for either
      // finds this line and not a live connector.

      "offered a form that refused at its last step. Released by the SERVER: the day " +
      "an adapter is registered, `adapter_registered` comes back true and the button " +
      "is live with no edit in this repo. Nothing to remember, nothing to expire.",
  },

  // ── Nothing mechanical can see it — the weaker kind, stated as such ─────
  "integrations.hold.signInNotSetUp": {
    kind: "unwatched",
    note:
      "DEF-INT-4235. Sign-in refuses on every deployment because our OAuth app " +
      "registration lives in `settings.INTEGRATION_OAUTH_CLIENTS`, which is set in NO " +
      "settings file and read with a getattr default of {}. It is DEPLOYMENT state, " +
      "so it differs per host and cannot be a fact about the build — which is exactly " +
      "why no row here can watch it and why this is `unwatched` rather than dressed up " +
      "as a check. ⚠ THE CARD IS DELIBERATELY NOT HELD ON IT: holding a control on " +
      "state the front end cannot see would break a correctly-configured production " +
      "host, which is a worse defect than the one being fixed. What the screens do " +
      "instead is spend nothing before the refusal — the sign-in press is the FIRST " +
      "act on a redirect provider, not the last — so a person meets the truth after " +
      "one click rather than after a filled form. Released when the wire carries a " +
      "readiness fact for sign-in the way `adapter_registered` already does for " +
      "dialling; the named seam is a `sign_in_ready` boolean beside it in " +
      "`selectors.provider_card`. Out of this lane's reach — wave H owns that file.",
  },

  // ── A ruling puts this elsewhere ────────────────────────────────────────
  "integrations.hold.scheduleIsRunbooks": {
    kind: "policy",
    note:
      "DEF-INT-4231. *How often — Nightly · Hourly · Manual* is a SCHEDULE, and " +
      "`BR-INT-054` as amended 2026-09-06 gives scheduling to Runbooks and gives " +
      "integrations exactly three things: building a connection, holding keys and " +
      "secrets, the lifecycle of a connection. ⚠ NO CONTROL IS ACTUALLY HELD BY THIS " +
      "ROW — the cadence segments are LIVE and stay live, because Runbooks does not " +
      "exist yet (`BR-INT-054`: *NOTHING IS TO BE BUILT AGAINST THIS*) and removing " +
      "the control would take away working behaviour and leave a clerk no way to say " +
      "when a nightly collection runs. The row exists so the next lane to read this " +
      "screen finds a recorded reason instead of an oversight, and so the control " +
      "moves as a unit when Runbooks is commissioned.",
  },
};
