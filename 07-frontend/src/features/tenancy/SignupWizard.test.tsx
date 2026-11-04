// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-001 (EP-TEN-03 §Stories) · US-TEN-002 (S111 seed toggle, client half)  Screens: S110–S114
// Rules:    BR-TEN-010 (atomic + idempotent commit) · BR-TEN-011 (slug grammar; live check advisory) ·
//           BR-TEN-012 (seed toggle) · BR-TEN-014 (14-day trial) · BR-TEN-045 OBSOLETE (PO 2026-08-10 —
//           path tenancy: the commit signs the owner in and S114 routes to /{tenant}/checklist) ·
//           BR-SHL-017 (the kit's PasswordField at the owner step) · BR-SHL-018 (rail) · BR-SHL-019 (single-flight commit)
// ───────────────────────────────────────────────────────
// TC tests for the S110–S114 wizard. Markup asserts on react-dom/server static
// output (MemoryRouter + QueryClientProvider + ToastProvider — the wizard
// routes, reads the plan catalog and fires a toast); the laws run through the
// exported pure pieces and through the endpoint wrapper driven by a stub fetch.
// The single-flight commit law itself belongs to FE-06 WizardFrame (proven in
// US-SHL-010 TC-5); it is re-driven here over THIS wizard's real commit
// function, because BR-TEN-010 makes a second POST a provisioning question.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import i18n, { LOCALE_CODES } from "@/i18n";
import { createApiClient } from "@/api/client";
import type { ApiError } from "@/api/client";
import { createTenant } from "@/api/endpoints";
import type { PricingPlan, ProvisionResult, SamplePlant } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { createWizardCommitController } from "@/components/WizardFrame";
import { SIZE_BANDS } from "@/features/public/sizeBands";
import { tenantPathFrom } from "@/routing/tenantPath";

import * as signupModule from "./SignupWizard";
import {
  CHECKLIST_SEGMENT,
  EMPTY_SIGNUP_DRAFT,
  IDLE_SUBDOMAIN,
  PROVISIONING_STEPS,
  ProvisioningPanel,
  SIGNUP_SERVICES,
  SIGNUP_STEP_COUNT,
  SignupWizard,
  US_STATE_OPTIONS,
  commitSignup,
  handoverReady,
  navFromStepParam,
  plantPhase,
  sampleStepState,
  provisioningStepStates,
  signupPayload,
  stepLabelKey,
  stepValid,
  suggestSubdomain,
  tenantAddress,
  restoreSignup,
  storableSignup,
} from "./SignupWizard";
import type { SignupDraft } from "./SignupWizard";

// §4 test data — Brazos Bend Utilities, subdomain `brazosbend`, Texas,
// Electric + Water, Growth plan, owner Dana Whitfield.
const BRAZOS: SignupDraft = {
  ...EMPTY_SIGNUP_DRAFT,
  name: "Brazos Bend Utilities",
  subdomain: "brazosbend",
  state: "TX",
  services: ["electric", "water"],
  currency: "USD",
  taxRegion: "TX",
  loadDefaults: true,
  plan: "growth",
  ownerName: "Dana Whitfield",
  ownerEmail: "dana@brazosbendutilities.com",
  ownerPassword: "Canyon2026rapids",
  ownerPhone: "+1 (281) 555-0164",
  termsAccepted: true,
};

const AVAILABLE = {
  checking: false,
  result: { subdomain: "brazosbend", available: true, problem: null },
};

const PLANS: PricingPlan[] = [
  {
    id: "plan-starter",
    code: "starter",
    name: "Starter",
    price_month: "1000.000000",
    currency: "USD",
    min_accounts: 0,
    max_accounts: 300,
  },
  {
    id: "plan-growth",
    code: "growth",
    name: "Growth",
    price_month: "5000.000000",
    currency: "USD",
    min_accounts: 300,
    max_accounts: 1000,
  },
];

const PROVISIONED: ProvisionResult = {
  id: "0191d3c0-0000-7000-8000-0000000000aa",
  name: "Brazos Bend Utilities",
  subdomain: "brazosbend",
  created: true,
  trial_ends_at: "2026-08-22T19:05:00+00:00",
  owner_user_id: "0191d3c0-0000-7000-8000-0000000000bb",
  reference_seed: { version: "2026.08", seeded: { uoms: 6 }, skipped: [] },
  // CR-017: the sample-data plant's job, as `POST /tenants` now answers.
  sample_plant: {
    job_id: "0191d3c0-0000-7000-8000-0000000000cc",
    status_url: "/api/jobs/0191d3c0-0000-7000-8000-0000000000cc",
    status: "succeeded",
    total: 10,
  },
};

// The deployment the PO chose on 2026-08-10: ONE origin, tenants on a path
// under it. The host below is the app's own — with path tenancy there is no
// second host anywhere in this flow.
const APP_HOST = "smartbillhub.bynry.com";

function renderWizard(props: Partial<signupModule.SignupWizardProps> = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.pricingPlans, PLANS);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/signup"]}>
          <SignupWizard appHost={APP_HOST} {...props} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-TEN-001 — idempotent tenant provisioning at signup commit (S110–S114)", () => {
  it("US-TEN-001 TC-1: the wizard commits Brazos Bend as ONE POST /api/tenants carrying exactly the ratified payload", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    const client = createApiClient({
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({ url: String(input), init: init ?? {} });
        return new Response(JSON.stringify(PROVISIONED), {
          status: 201,
          headers: { "Content-Type": "application/json", Location: "/tenants/x" },
        });
      },
      sleep: () => Promise.resolve(),
    });
    const result = await createTenant(signupPayload(BRAZOS), client);

    expect(calls).toHaveLength(1); // ONE transactional call (BR-SHL-019)
    // Provisioning is the one write that CANNOT be tenant-scoped — there is no
    // tenant yet — so it stays on the un-tenanted platform path (PO 2026-08-10).
    expect(calls[0].url).toBe("/api/tenants");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({
      name: "Brazos Bend Utilities",
      subdomain: "brazosbend",
      state: "TX",
      currency: "USD",
      tax_region: "TX",
      plan: "growth",
      services: ["electric", "water"],
      load_defaults: true, // BR-TEN-012: the S111 toggle drives seeding
      owner: {
        full_name: "Dana Whitfield",
        email: "dana@brazosbendutilities.com",
        password: "Canyon2026rapids",
        phone: "+1 (281) 555-0164",
      },
    });
    expect(result.created).toBe(true);
    expect(result.trial_ends_at).toBe("2026-08-22T19:05:00+00:00"); // BR-TEN-014: +14 days
  });

  it("US-TEN-001 TC-2: a replayed commit answers 200 with the SAME tenant and created:false — a success, not a duplicate", async () => {
    const client = createApiClient({
      fetchImpl: async () =>
        new Response(JSON.stringify({ ...PROVISIONED, created: false, owner_user_id: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      sleep: () => Promise.resolve(),
    });
    const result = await createTenant(signupPayload(BRAZOS), client);
    expect(result.id).toBe(PROVISIONED.id);
    expect(result.created).toBe(false); // BR-TEN-010: nothing written twice
  });

  it("US-TEN-001 TC-3: a subdomain owned by another owner refuses 409 in plain language, keeping the entered values", async () => {
    const client = createApiClient({
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            code: "BIZ-STATE",
            message_key: "signup.subdomain_taken",
            params: { subdomain: "brazosbend" },
            field_errors: [],
            br_ref: "BR-TEN-011",
            trace_id: "abc123",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      sleep: () => Promise.resolve(),
    });
    const error = (await createTenant(signupPayload(BRAZOS), client).catch(
      (caught: unknown) => caught,
    )) as ApiError;
    expect(error.status).toBe(409);
    expect(error.messageKey).toBe("signup.subdomain_taken");
    expect(error.brRef).toBe("BR-TEN-011");
    // The draft is the consumer's state above WizardFrame, so a failed commit
    // loses nothing (BR-SHL-018/019 + A18 §4).
    expect(signupPayload(BRAZOS).subdomain).toBe("brazosbend");
  });

  it("US-TEN-001 TC-4: a bad-charset or reserved web address never reaches the server — Continue stays blocked", () => {
    // The live check is the only client-side knowledge of the BR-TEN-011
    // grammar; the reserved list and the charset rule live server-side.
    const badCharset = {
      checking: false,
      result: { subdomain: "-brazos_bend!", available: false, problem: "charset" },
    };
    const reserved = {
      checking: false,
      result: { subdomain: "api", available: false, problem: "reserved" },
    };
    expect(stepValid(1, { ...BRAZOS, subdomain: "-brazos_bend!" }, badCharset)).toBe(false);
    expect(stepValid(1, { ...BRAZOS, subdomain: "api" }, reserved)).toBe(false);
    // An unanswered check is not an available one.
    expect(stepValid(1, BRAZOS, IDLE_SUBDOMAIN)).toBe(false);
    expect(stepValid(1, BRAZOS, AVAILABLE)).toBe(true);
  });

  it("US-TEN-002 TC-1/TC-2: the S111 toggle is the ONLY thing that asks for seeding, and it defaults ON (BR-TEN-012)", () => {
    expect(EMPTY_SIGNUP_DRAFT.loadDefaults).toBe(true); // "recommended", pre-checked
    expect(signupPayload(BRAZOS).load_defaults).toBe(true);
    // TC-2: toggled off, the commit asks for no seed — reference lists stay
    // empty and no seed audit rows are written (server half, G5/backend suite).
    expect(signupPayload({ ...BRAZOS, loadDefaults: false }).load_defaults).toBe(false);
    // The fixture VERSION and the per-list row counts are the server's answer;
    // nothing here predicts them.
    expect(Object.keys(signupPayload(BRAZOS))).not.toContain("reference_seed");
  });

  it("BR-SHL-018: each step gates Continue on its own required fields", () => {
    expect(stepValid(1, { ...BRAZOS, services: [] }, AVAILABLE)).toBe(false);
    expect(stepValid(1, { ...BRAZOS, name: "" }, AVAILABLE)).toBe(false);
    expect(stepValid(2, BRAZOS, AVAILABLE)).toBe(true);
    expect(stepValid(3, { ...BRAZOS, plan: "" }, AVAILABLE)).toBe(false);
    expect(stepValid(4, EMPTY_SIGNUP_DRAFT, IDLE_SUBDOMAIN)).toBe(true); // review is read-only
    expect(stepValid(5, { ...BRAZOS, termsAccepted: false }, AVAILABLE)).toBe(false);
    expect(stepValid(5, { ...BRAZOS, ownerEmail: "dana@" }, AVAILABLE)).toBe(false);
    expect(stepValid(5, BRAZOS, AVAILABLE)).toBe(true);
  });

  it("DEF-TEN-4222: the size step shows NO money — only how many accounts, mapped to the plan code the server needs", () => {
    // PO 2026-10-02: the prices came off the home page, and this step showed
    // the same three ($1,000 / $5,000 / $8,000 a month) one click later.
    // RED-PROVED against the step as it stood: "$1,000.00" was in the markup.
    const html = renderWizard({ initialNav: { step: 3, reached: 3 } });
    expect(html).toContain("How many accounts?");
    expect(html).not.toMatch(/\$\s?[\d,]+/);
    expect(html).not.toMatch(/month/i);
    for (const band of ["Up to 3,000", "3,000–10,000", "10,000–40,000"]) {
      expect(html, band).toContain(band);
    }
    // Each band carries an EXISTING plan code, smallest band to smallest plan.
    expect(SIZE_BANDS.map((band) => band.plan)).toEqual(["starter", "growth", "scale"]);
    for (const band of SIZE_BANDS) {
      expect(html, band.plan).toContain(`value="${band.plan}"`);
    }
    expect(html.match(/name="signup-plan"/g) ?? []).toHaveLength(3);
    // The review step names the band the prospect picked, never a plan price;
    // its trial line is the one figure that stays.
    const review = renderWizard({ initialNav: { step: 4, reached: 4 } });
    expect(review).toContain("Due today $0.00");
    expect(review.match(/\$[\d,]+\.\d{2}/g)).toEqual(["$0.00"]);
  });

  it("A1 friction control: the web address is suggested from the utility name in BR-TEN-011 grammar", () => {
    expect(suggestSubdomain("Brazos Bend Utilities")).toBe("brazos-bend-utilities");
    expect(suggestSubdomain("Silver Creek Water")).toBe("silver-creek-water");
    expect(suggestSubdomain("  O'Hara & Sons, Inc. ")).toBe("o-hara-sons-inc");
    expect(suggestSubdomain("")).toBe("");
    expect(suggestSubdomain("x".repeat(80))).toHaveLength(63);
  });

  it("BR-SHL-018 / A9: a pasted ?step= clamps to the highest validated step", () => {
    const fresh = { step: 1, reached: 1 };
    expect(navFromStepParam("4", fresh)).toEqual(fresh); // cannot skip ahead
    expect(navFromStepParam(null, fresh)).toEqual(fresh);
    const reachedThree = { step: 3, reached: 3 };
    expect(navFromStepParam("2", reachedThree)).toEqual({ step: 2, reached: 3 });
    expect(navFromStepParam("99", reachedThree)).toEqual(reachedThree);
    expect(SIGNUP_STEP_COUNT).toBe(5);
  });

  it("S110 renders the five-step rail, the utility fields and the searchable 52-entry state list (BR-SHL-033)", () => {
    const html = renderWizard();
    expect(html).toContain('data-wizard="rail"');
    for (const label of [
      "Your utility",
      "How you bill",
      "Utility size", // was "Plan &amp; setup" until DEF-TEN-4222 (2026-10-02)
      "Review",
      "Create login",
    ]) {
      expect(html).toContain(label);
    }
    expect(html).toContain('id="signup-name"');
    expect(html).toContain('id="signup-subdomain"');
    expect(html).toContain('role="combobox"'); // SearchSelectField, not a bare select
    expect(US_STATE_OPTIONS).toHaveLength(52); // 50 states + DC + PR (A1)
    // The commit ✓ belongs to the final step only.
    expect(html).not.toContain("Create utility &amp; go live");
    expect(html).toContain("Continue");
  });

  // ⚠ **THIS ASSERTION READ "the six" UNTIL 2026-08-27 AND WAS GREEN ON A BUG.**
  // CR-039 wave A task 2: the PO ruled all ten on 2026-08-17 and the backend was
  // rewritten to match the next day; `SIGNUP_SERVICES` stayed at six, and this
  // test — asserting a subset with `toContain` — passed the whole time. A
  // subset assertion cannot fail on a missing member, which is why the count is
  // now asserted too and why `signupServices.test.ts` compares the list to the
  // database seed rather than to another list in this repo.
  // ⚠ **AND IT READ "TEN" UNTIL 2026-09-02, WHEN CR-063 ADDED FIRE — THE SAME
  // SHAPE ONE SERVICE ALONG.** A real utility is being onboarded that sells
  // fire protection; the catalogue row, the API and the whole backend suite
  // were green without a chip on this screen, and the tenant would have signed
  // up successfully with `fire` `enabled=False` and no control to change it.
  // **This count is the guard, and it is why CR-063 numbered the front end
  // before the demo data.**
  it("A1 S110 / CR-039 A2 / CR-063: all ELEVEN signup services render as chips", () => {
    const html = renderWizard();
    expect(SIGNUP_SERVICES).toHaveLength(11); // BR-RAT-024, amended 2026-09-02
    for (const service of [
      "Electric",
      "Water",
      "Gas",
      "Sewer",
      "Trash",
      "Storm water",
      "Solar",
      "Broadband",
      "Thermal / Heat",
      "Battery",
      "Fire",
    ]) {
      expect(html).toContain(service);
    }
  });

  it("S110 availability names the PATH address, built by the same helper the router uses — no catalog hardcodes a domain", () => {
    // The line used to read "✓ {{subdomain}}.smartbillhub.app is available" in
    // all five catalogs, then a composed HOST. Path tenancy (PO 2026-08-10)
    // makes the address a path on this origin, so the line takes the whole
    // composed address and S110 cannot promise something the commit will not
    // deliver.
    // The loop reads LOCALE_CODES rather than a written-out list (2026-08-11,
    // eleven-locale lane): a hardcoded five would have kept passing while six
    // new catalogues went unchecked, which is the shape of the defect this
    // assertion exists to prevent.
    for (const language of LOCALE_CODES) {
      const line = i18n.getResource(language, "translation", "tenancy.signup.utility.available");
      expect(String(line)).toContain("{{address}}");
      expect(String(line)).not.toContain("smartbillhub");
    }
    expect(tenantAddress(APP_HOST, "brazosbend")).toBe("smartbillhub.bynry.com/brazosbend");
    expect(
      i18n.t("tenancy.signup.utility.available", {
        address: tenantAddress(APP_HOST, "brazosbend"),
      }),
    ).toBe("✓ smartbillhub.bynry.com/brazosbend is available");
    // …and it is the SAME string the route is built from — one helper, so the
    // promised address and the real one cannot drift.
    expect(tenantAddress(APP_HOST, "brazosbend")).toBe(
      `${APP_HOST}${tenantPathFrom("brazosbend", "")}`,
    );
  });

  it("BR-SHL-017 (E1 closed): the S114 owner step renders the KIT's PasswordField, not a local input", () => {
    // Rendered at step 5 through the nav seam (the rail cannot be jumped
    // forward, BR-SHL-018). Asserted through the control's accessible name and
    // role — the kit's toggle button is what proves the composition.
    const html = renderWizard({ initialNav: { step: 5, reached: 5 } });
    expect(html).toContain('id="signup-owner-password"');
    expect(html).toContain('aria-label="Show password"');
    expect(html).toContain('aria-controls="signup-owner-password"');
    // The toggle must never submit the wizard's owner step.
    // ⚠ CLASS NAME -> `data-variant` (CR-018 Phase 4a, 2026-08-20). Route B
    // deletes the name; `buttonKit` stamps `data-variant`/`data-size` on every
    // kit button precisely so a check has something stable to read.
    expect(html).toMatch(/<button [^>]*data-variant="ghost"[^>]*class="[^"]*password-toggle"/);
    expect(html).toContain('class="password-field"');
  });
});

// ── Post-signup handoff under PATH tenancy (PO 2026-08-10) ─────────────────
// BR-TEN-045 is OBSOLETE. It existed because provisioning could not create a
// session across HOSTS; with one origin the commit signs the owner in, so S114
// routes straight into the new tenant at /{tenant}/checklist (S62) — the
// friction the PO wanted gone, and their deferred "option B" for free. The
// tests below pin that, and pin that the whole host mechanism is gone.

describe("S114 hands the owner into the NEW TENANT's path, with no host anywhere", () => {
  it("the commit routes to /{tenant}/checklist, built from the SERVER's slug", () => {
    // The route the wizard navigates to on a successful commit, composed by the
    // ONE helper. The slug is the server's answer, so a value the server
    // normalised (or an idempotent replay's existing tenant) is what the URL
    // carries — never the string that was typed at S110.
    expect(tenantPathFrom(PROVISIONED.subdomain, CHECKLIST_SEGMENT)).toBe(
      "/brazosbend/checklist",
    );
    expect(CHECKLIST_SEGMENT).toBe("/checklist");
    // A different tenant gets a different path from the same code — there is no
    // per-tenant branch anywhere.
    expect(tenantPathFrom("lonestar", CHECKLIST_SEGMENT)).toBe("/lonestar/checklist");
  });

  it("no surface offers a cross-host link any more — the handoff is same-origin", () => {
    const html = renderWizard();
    // Nothing in the wizard names a scheme+host: with path tenancy the address
    // is a path on the origin the visitor is already on.
    expect(html).not.toContain("https://brazosbend");
    expect(html).not.toContain("smartbillhub.app");
    expect(html).not.toContain(".smartbillhub.bynry.com"); // no HOST form of the address
    // …and the success screen that used to carry that link is gone entirely.
    expect(Object.keys(signupModule)).not.toContain("SignupSuccess");
    for (const key of ["address", "go", "hint", "kicker", "note"]) {
      expect(
        i18n.getResource("en", "translation", `tenancy.signup.success.${key}`),
      ).toBeUndefined();
    }
  });

  it("REGRESSION PIN: the host-suffix mechanism is DELETED, not merely unused", () => {
    // The 2026-08-10 host bug (a three-label app host read as "bynry.com") is
    // unreachable because the code that could make the mistake no longer
    // exists: no env var, no derivation, no composition of a tenant HOST.
    for (const gone of [
      "tenantHost",
      "tenantHostSuffix",
      "derivedTenantHostSuffix",
      "configuredTenantHostSuffix",
      "tenantHomeUrl",
      "TENANT_HOST_SUFFIX_VAR",
      "TENANT_SIGN_IN_PATH",
    ]) {
      expect(Object.keys(signupModule)).not.toContain(gone);
    }
  });

  it("the address the user is shown is the address they will be at", () => {
    // One composition rule for both: the S110 line and the route the commit
    // takes are the same helper, so the promise and the destination agree.
    const address = tenantAddress(APP_HOST, PROVISIONED.subdomain);
    expect(address).toBe("smartbillhub.bynry.com/brazosbend");
    expect(address.endsWith(tenantPathFrom(PROVISIONED.subdomain, ""))).toBe(true);
    // The owner's password help no longer promises "a new web address".
    expect(String(i18n.t("tenancy.signup.login.passwordHelp"))).not.toContain("address");
  });

  it("BR-SHL-019 / BR-TEN-010: the S114 commit stays single-flight — a second click posts nothing", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const calls: string[] = [];
    const client = createApiClient({
      fetchImpl: async (input: RequestInfo | URL) => {
        calls.push(String(input));
        await gate; // hold the first POST open so the second click overlaps it
        return new Response(JSON.stringify(PROVISIONED), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      },
      sleep: () => Promise.resolve(),
    });
    const translate = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);
    // The wizard's REAL commit function, driven through the REAL frame
    // controller it is handed to in the component.
    const controller = createWizardCommitController(i18n.t("wizard.failed.reason"));
    const commit = () => commitSignup(BRAZOS, client, translate).then((r) => r.outcome);

    const first = controller.run(commit);
    const second = await controller.run(commit); // the double click
    expect(second).toBeNull(); // ignored while one commit is in flight
    expect(calls).toHaveLength(1); // …and it never reached the network

    release();
    expect(await first).toEqual({ ok: true });
    expect(calls).toEqual(["/api/tenants"]); // still exactly ONE POST /api/tenants
  });

  it("BR-TEN-010: the route is built from the SERVER's subdomain, and a replay lands on the same checklist", async () => {
    const replay = { ...PROVISIONED, created: false, owner_user_id: null };
    const client = createApiClient({
      fetchImpl: async () =>
        new Response(JSON.stringify(replay), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      sleep: () => Promise.resolve(),
    });
    // The draft's typed value is never what the URL is built from — the
    // server's is.
    const typed: SignupDraft = { ...BRAZOS, subdomain: "brazosbend" };
    const result = await commitSignup(typed, client, (key) => i18n.t(key));
    expect(result.outcome).toEqual({ ok: true });
    expect(result.provisioned?.subdomain).toBe("brazosbend");
    expect(result.provisioned?.created).toBe(false); // a replay is still a success
    expect(tenantPathFrom(result.provisioned?.subdomain ?? "", CHECKLIST_SEGMENT)).toBe(
      "/brazosbend/checklist",
    );
  });

  it("BR-SHL-020: a refused commit yields plain language and NO navigation", async () => {
    const client = createApiClient({
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            code: "BIZ-STATE",
            message_key: "signup.subdomain_taken",
            params: { subdomain: "brazosbend" },
            field_errors: [],
            br_ref: "BR-TEN-011",
            trace_id: "abc123",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      sleep: () => Promise.resolve(),
    });
    const result = await commitSignup(BRAZOS, client, (key, params) => i18n.t(key, params));
    // No tenant, so no tenant path: the wizard has nowhere to navigate and
    // stays on its own failure state rather than guessing a slug.
    expect(result.provisioned).toBeNull();
    expect(result.outcome.ok).toBe(false);
  });

  it.todo(
    "US-TEN-001 TC-5 (isolation): after provisioning, a Lone Star Ridge session sees zero Brazos Bend rows — server/RLS scope (G5)",
  );
  it.todo(
    "browser scope → Playwright journey J1: typing through S110–S114, the debounced availability check firing, the ✓ commit, and the redirect landing signed-in on /{tenant}/checklist",
  );
  it.todo(
    "server scope: the commit's Set-Cookie IS the owner's session (the backend half of the obsolete BR-TEN-045 handoff) — the concurrent backend lane's to prove",
  );
});


// ── CR-017 · the provisioning screen (PO 2026-08-19) ───────────────────────
//
// *"after this step at the time of new tenant creation you need new screen
//  showcaing data migration is going on so that User wil know whats going on in
//  the background"* / *"otherwise they are left hi and dry"*.
//
// The DECISION this screen makes — which of five things it is saying — is
// `plantPhase`, driven here through every state it can be in. The markup is
// asserted through static render, which runs no effects, so the two phases that
// need no effect (the commit still in flight, and a plant still seeding) are
// rendered and the effect-driven ones are proven through the pure function they
// come from. The whole thing clicked in a browser is J1's, and CR-017's own
// journey spec.
describe("CR-017 — the signup wait names the work instead of leaving the user high and dry", () => {
  // Non-null by construction: the fixture above carries one, and a test that
  // silently fell back to null would prove the S111-toggle case twice and the
  // real one never.
  const PLANT: SamplePlant = PROVISIONED.sample_plant ?? (() => {
    throw new Error("the PROVISIONED fixture must carry a sample_plant");
  })();
  const job = (status: string, done: number) => ({
    id: PLANT.job_id,
    kind: "tenancy.sample_data_plant",
    status: status as "queued" | "running" | "succeeded" | "failed",
    progress: { done, total: 10 },
    result_link: null,
    error: null,
  });

  it("nothing is claimed before the commit answers", () => {
    expect(plantPhase({ committed: false, plant: PLANT, job: null, gaveUp: false })).toBe(
      "committing",
    );
    // …and the sample row is WAITING, never "working": no plant exists yet.
    expect(sampleStepState("committing", PLANT)).toBe("queued");
  });

  it("JOBS_EAGER on: the plant already finished inside the commit, so the screen shows it done", () => {
    // This is every deployment today — the record comes back `succeeded`
    // because `dispatch_job` ran it in-process (DEF-320's first shape).
    const phase = plantPhase({
      committed: true,
      plant: PLANT,
      job: job("succeeded", 10),
      gaveUp: false,
    });
    expect(phase).toBe("ready");
    expect(sampleStepState(phase, PLANT)).toBe("done");
  });

  it("a runner behind it: queued and running are both SEEDING, and the screen keeps narrating", () => {
    for (const status of ["queued", "running"]) {
      const phase = plantPhase({
        committed: true,
        plant: PLANT,
        job: job(status, 3),
        gaveUp: false,
      });
      expect(phase, status).toBe("seeding");
      expect(sampleStepState(phase, PLANT)).toBe("working");
    }
  });

  it("DEF-320: a record that never runs stops the screen WAITING, not spinning forever", () => {
    // JOBS_EAGER off with no worker — the deployed shape. The poller gives up,
    // and giving up is its own answer: the tenant is real and usable, and what
    // we cannot say is whether the sample records landed.
    const phase = plantPhase({ committed: true, plant: PLANT, job: job("queued", 0), gaveUp: true });
    expect(phase).toBe("waiting");
    expect(sampleStepState(phase, PLANT)).toBe("queued");
  });

  it("a FAILED plant is never reported as ready — the block that broke is named", () => {
    const phase = plantPhase({
      committed: true,
      plant: PLANT,
      job: job("failed", 6),
      gaveUp: false,
    });
    expect(phase).toBe("partial");
    expect(sampleStepState(phase, PLANT)).toBe("failed");
  });

  it("BR-TEN-012: no plant was ever asked for, so the tenant is READY and nothing is pending", () => {
    // The S111 toggle off means `sample_plant` is null. A screen that waited on
    // it would wait forever for something nobody started.
    const phase = plantPhase({ committed: true, plant: null, job: null, gaveUp: false });
    expect(phase).toBe("ready");
    expect(sampleStepState(phase, null)).toBe("queued");
  });

  it("the screen names the work, and the counts are the SERVER's own", () => {
    const markup = renderToStaticMarkup(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={createApiClient({ fetchImpl: () => Promise.reject(new Error("no fetch in this test")) })}
        onDone={() => undefined}
      />,
    );
    // Named work, not a spinner (the whole point of the CR).
    expect(markup).toContain(i18n.t("tenancy.signup.provisioning.step.reference"));
    expect(markup).toContain(i18n.t("tenancy.signup.provisioning.step.foundations"));
    expect(markup).toContain(i18n.t("tenancy.signup.provisioning.step.sample"));
    // The reference count is DERIVED from `reference_seed`, never typed here:
    // the fixture carries one list of 6 rows and the screen says exactly that.
    expect(markup).toContain(
      i18n.t("tenancy.signup.provisioning.step.referenceDone", { lists: 1, rows: 6 }),
    );
    // The reassurance the PO asked for, in words.
    expect(markup).toContain(i18n.t("tenancy.signup.provisioning.reassure"));
    // And the way out holds its place from the first frame — BR-SHL-025 refuses
    // a control by disabling it, never by hiding it, so the button is PRESENT
    // here even though this frame is `seeding` and cannot serve it.
    //
    // ⚠ THIS LINE USED TO READ "a way out that does not depend on the background
    // work finishing", WHICH WAS DEF-2370 WRITTEN DOWN AS AN INTENTION. Presence
    // is all it ever asked, and presence was never the question; whether the
    // control can be PRESSED is, and that is asserted per phase in
    // `SignupHandover.dom.test.tsx`, which needs a real DOM to reach `ready` and
    // `partial` at all.
    expect(markup).toContain("signup-provisioning-continue");
  });

  it("DEF-2370: the hand-over is REFUSED while the sample-data job is still writing blocks", () => {
    // `renderToStaticMarkup` runs no effects, so `job` stays null and this is
    // the `seeding` frame — the one the PO screenshotted, with the button live.
    const markup = renderToStaticMarkup(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={PROVISIONED}
        client={createApiClient({ fetchImpl: () => Promise.reject(new Error("no fetch in this test")) })}
        onDone={() => undefined}
      />,
    );
    expect(plantPhase({ committed: true, plant: PLANT, job: null, gaveUp: false })).toBe("seeding");
    expect(markup).toContain("signup-provisioning-continue"); // present…

    // …and refused. The whole `<button …>` tag is pulled out and asked, rather
    // than matching `disabled` somewhere after the test id: React writes the
    // spread props in call order, so an assertion that pins the ATTRIBUTE ORDER
    // would go red on a harmless reordering and green on the wrong button.
    const tag = markup.match(/<button[^>]*data-testid="signup-provisioning-continue"[^>]*>/)?.[0];
    expect(tag, "the hand-over button is not in the seeding markup").toBeTypeOf("string");
    expect(tag).toContain("disabled");
    // BR-SHL-025's other half: it says WHY, pointing at the declared line.
    expect(tag).toContain('aria-describedby="signup-provisioning-reassure"');
    expect(markup).toContain('id="signup-provisioning-reassure"');
  });

  // ── CR-064 · THE SEVENTEEN (PO 2026-09-02) ───────────────────────────────
  //
  //   "can you show all 17 step - -list down all 17 steps and show 1 by 1 when
  //    they finish - if step breaks - then show the reason behind it at that
  //    step itself , if you skip the step, then show the reason for that step
  //    also … you ahve to provide specific error on the screen itself"
  //
  // The DECISION is `provisioningStepStates`, driven here through every state a
  // step can be in, plus a static render for what actually reaches the DOM.
  const stepJob = (
    status: "queued" | "running" | "succeeded" | "failed",
    done: number,
    steps?: {
      key: string;
      outcome: "seeded" | "skipped" | "failed" | "not_started";
      detail?: string | null;
    }[],
  ) => ({
    id: PLANT.job_id,
    kind: "tenancy.sample_data_plant",
    status,
    progress: { done, total: 17 },
    checkpoint: null,
    result_link: null,
    error: null,
    steps: (steps ?? []).map((row, index) => ({
      position: PROVISIONING_STEPS.indexOf(row.key) + 1,
      key: row.key,
      module: row.key.split(":")[0],
      block: row.key.split(":")[1],
      label: row.key,
      tables: [],
      outcome: row.outcome,
      count: row.outcome === "seeded" ? 3 : 0,
      reason_code: null,
      error_code: null,
      failure_class: null,
      root_block: null,
      root_label: null,
      detail: row.detail ?? null,
      finished_at: null,
      // `index` is unused; kept out of the object on purpose — a position
      // invented here would disagree with the catalogue's.
      ...(index < 0 ? {} : {}),
    })),
  });

  it("CR-064: all seventeen are on screen from the FIRST frame, numbered and in order", () => {
    // RED-PROVED (law 7) with the list gated on the commit having answered —
    // `(phase === "committing" ? [] : stepRows).map(...)`:
    //
    //     AssertionError: identity:seed_sample_records: expected '<section
    //     class="card border-t-4 borde…' to contain
    //     'data-step="identity:seed_sample_recor…'
    //
    // The frame before the commit answers. `renderToStaticMarkup` runs no
    // effects, so no poll has happened and nothing has been seeded — which is
    // exactly the moment the PO asked to see the list.
    const markup = renderToStaticMarkup(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={null}
        client={createApiClient({ fetchImpl: () => Promise.reject(new Error("no fetch")) })}
        onDone={() => undefined}
      />,
    );
    // ⚠ DERIVED, NOT A LITERAL (DEF-3320). This said `toHaveLength(17)` and
    // the estate grew to eighteen; a literal here is a SECOND place to remember,
    // and the one that decides whether the list agrees with the orchestrator is
    // `provisioningSteps.test.ts`, which parses SAMPLE_MODULES out of Python.
    // What this case is really about is that EVERY step in the constant draws a
    // row, whatever the constant holds.
    expect(PROVISIONING_STEPS.length).toBeGreaterThan(0);
    for (const [index, key] of PROVISIONING_STEPS.entries()) {
      // The step's own row, its number, and its clerk-facing label.
      expect(markup, key).toContain(`data-step="${key}"`);
      expect(markup, key).toContain(`${index + 1}. ${i18n.t(stepLabelKey(key))}`);
    }
    // One row per step, not one fewer and not a summary that states a number.
    expect(markup.match(/data-step="/g) ?? []).toHaveLength(PROVISIONING_STEPS.length);
  });

  it("CR-064 A4: a step with no recorded row reads NOT STARTED — never Done", () => {
    // ⚠ THE ONE CR-064 NAMES AS THE REAL RISK. A run that finished with rows
    // for only the first six must not report the rest as Done, and a
    // `succeeded` job is exactly where that mistake would hide.
    //
    // RED-PROVED (law 7) with an unrecorded step reading `done` on a succeeded
    // run — one word changed in `provisioningStepStates`:
    //
    //     AssertionError: metering:seed_sample_records: expected 'done' to be
    //     'notStarted' // Object.is equality
    //
    // ⚠ AND THIS TEST FOUND A SECOND, DIFFERENT DEFECT BEFORE THE SCREEN
    // SHIPPED, which is the whole argument for writing it first: the original
    // `stepCatalogue` read the POLL BODY as the catalogue, so a body carrying
    // two rows drew a list of two —
    //
    //     AssertionError: expected [ … ] to have a length of 17 but got +2
    //
    // (Seventeen was the length on the day that was measured; the estate holds
    // eighteen now and this case counts `PROVISIONING_STEPS` rather than a
    // literal — DEF-3320.)
    const rows = provisioningStepStates(
      "ready",
      PLANT,
      stepJob("succeeded", 6, [
        { key: "identity:seed_sample_records", outcome: "seeded" },
        { key: "rating:seed_sample_records", outcome: "seeded" },
      ]),
    );
    expect(rows).toHaveLength(PROVISIONING_STEPS.length);
    expect(rows[0].state).toBe("done");
    expect(rows[1].state).toBe("done");
    for (const row of rows.slice(2)) {
      expect(row.state, row.key).toBe("notStarted");
      expect(row.state, row.key).not.toBe("done");
    }
  });

  it("CR-064 B2: a step moves Waiting → Working → Done, and exactly one is Working", () => {
    const rows = provisioningStepStates(
      "seeding",
      PLANT,
      // ⚠ **THE FIVE FINISHED KEYS ARE DERIVED, NOT TYPED (DEF-3320's own
      // lesson, applied to the fixture as well as to the assertion).** They
      // were five literals, and `assets:seed_sample_aged_meters` was inserted
      // at position 5, so the fifth literal (`customers:seed_sample_records`)
      // was really the SIXTH step — already Done — and index 4 had no row at
      // all: zero Working, red, for a change this case is not about.
      stepJob(
        "running",
        5,
        PROVISIONING_STEPS.slice(0, 5).map((key) => ({ key, outcome: "seeded" as const })),
      ),
    );
    expect(rows.filter((row) => row.state === "working")).toHaveLength(1);
    // `progress.done` is blocks FINISHED, so the one in flight is the sixth.
    // ⚠ THE KEY IS DERIVED FROM THE CONSTANT, NOT TYPED (DEF-3320). This read
    // `metering:seed_sample_reads`, which was the sixth step until CR-062's
    // Municipal-discount block was INSERTED at position 6 — an insertion in the
    // middle moves every key after it, and a positional case that names one by
    // hand then fails for a change it is not about. What it is about is that
    // exactly one step is Working and it is the one after the last counted.
    expect(rows[5].state).toBe("working");
    expect(rows[5].key).toBe(PROVISIONING_STEPS[5]);
    expect(rows.slice(0, 5).every((row) => row.state === "done")).toBe(true);
    expect(rows.slice(6).every((row) => row.state === "queued")).toBe(true);
  });

  it("CR-064 B3: the reason is on the step's OWN line, verbatim, for a break AND a skip", () => {
    // *"if step breaks - then show the reason behind it at that step itself ,
    //  if you skip the step, then show the reason for that step also"*.
    //
    // RED-PROVED (law 7) with the reason dropped from the row, which is what a
    // "link to Settings instead" version of this screen would do:
    //
    //     AssertionError: expected null to be 'relation "meter_reads" does not
    //     exist' // Object.is equality
    const broke = 'relation "meter_reads" does not exist';
    const unwired =
      "apps.customers.services.seed_sample_wizard_parks is not published yet";
    const markup = renderToStaticMarkup(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={{
          ...PROVISIONED,
          sample_plant: { ...PLANT, status: "failed" },
        }}
        client={createApiClient({ fetchImpl: () => Promise.reject(new Error("no fetch")) })}
        onDone={() => undefined}
      />,
    );
    // The static render reaches no server, so this proves the DECISION through
    // the pure function and the SHAPE through the markup above.
    const rows = provisioningStepStates(
      "partial",
      PLANT,
      stepJob("failed", 6, [
        { key: "metering:seed_sample_reads", outcome: "failed", detail: broke },
        { key: "customers:seed_sample_wizard_parks", outcome: "skipped", detail: unwired },
      ]),
    );
    const byKey = new Map(rows.map((row) => [row.key, row]));
    expect(byKey.get("metering:seed_sample_reads")?.state).toBe("failed");
    expect(byKey.get("metering:seed_sample_reads")?.reason).toBe(broke);
    // ⚠ A SKIP IS NOT A FAILURE. Nothing broke; a part of the product is not
    // wired, and the two must be distinguishable or the diagnosis is lost.
    expect(byKey.get("customers:seed_sample_wizard_parks")?.state).toBe("skipped");
    expect(byKey.get("customers:seed_sample_wizard_parks")?.reason).toBe(unwired);
    // A step that SEEDED carries no reason line at all — the line is for the
    // ones that did not, which is what makes it worth reading.
    expect(markup).toContain('data-signup="provisioning-steps"');
  });

  it("CR-064: the SERVER's catalogue wins over the typed copy, so an extra step still shows", () => {
    // Hard-won law 2, forwards for once: the day a block this file has never
    // heard of is added in Python, it is on this screen with the server's own
    // English label rather than silently missing until somebody edits the
    // constant. It happened for real on 2026-09-02 (DEF-3320) and this is the
    // behaviour that kept the Municipal-discount step visible meanwhile.
    // ⚠ DERIVED (DEF-3320): "one more than the constant holds", never a
    // literal. This case was written when the constant held seventeen and
    // named the extra one `eighteenth` with `position: 18`; the estate then
    // grew to eighteen and the case asserted 18 against 19. The point it makes
    // is about ONE MORE THAN WE KNOW ABOUT, whatever that number is.
    const extraPosition = PROVISIONING_STEPS.length + 1;
    const eighteenth = {
      position: extraPosition,
      key: "notifications:seed_sample_digests",
      module: "notifications",
      block: "seed_sample_digests",
      label: "Sample notification digests",
      tables: [],
    };
    const plantWithEighteen: SamplePlant = {
      ...PLANT,
      total: extraPosition,
      steps: [
        ...PROVISIONING_STEPS.map((key, index) => ({
          position: index + 1,
          key,
          module: key.split(":")[0],
          block: key.split(":")[1],
          label: key,
          tables: [],
        })),
        eighteenth,
      ],
    };
    const rows = provisioningStepStates("seeding", plantWithEighteen, null);
    expect(rows).toHaveLength(extraPosition);
    expect(rows[extraPosition - 1].key).toBe("notifications:seed_sample_digests");
    // No catalogue key exists for it, so the server's label is what renders.
    expect(rows[extraPosition - 1].fallbackLabel).toBe("Sample notification digests");
  });

  it("DEF-2370: ONE predicate answers `may they leave yet`, and `partial` is a YES", () => {
    // The button and the auto-handover effect disagreed because each answered
    // this separately. They now read the same function — which is the fix, not
    // the disabled attribute.
    expect(handoverReady("committing")).toBe(false);
    expect(handoverReady("seeding")).toBe(false);
    expect(handoverReady("ready")).toBe(true);
    expect(handoverReady("waiting")).toBe(true);
    // ⚠ `partial` NEVER hands over on its own — something did not land and the
    // owner has to see which block before they go — so the button is the ONLY
    // way off that screen. Disabling it would strand them.
    expect(handoverReady("partial")).toBe(true);
  });

  it("DEF-325: during the commit the sample row says PENDING, never \"not requested\"", () => {
    // Found by the first browser walkthrough of this screen and by nothing
    // else: `plant` is null both when no sample set was asked for AND before
    // the commit has answered, so the screen told every signing-up customer
    // "Not requested at signup" about the sample data it was building for them
    // at that moment.
    const markup = renderToStaticMarkup(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={null}
        client={createApiClient({
          fetchImpl: () => Promise.reject(new Error("no fetch in this test")),
        })}
        onDone={() => undefined}
      />,
    );
    expect(markup).toContain(i18n.t("tenancy.signup.provisioning.step.samplePending"));
    expect(markup).not.toContain(i18n.t("tenancy.signup.provisioning.step.sampleSkipped"));
  });

  it("the reassurance is for the WAIT — it is not repeated under a finished list", () => {
    const done = renderToStaticMarkup(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={{ ...PROVISIONED, sample_plant: null }}
        client={createApiClient({
          fetchImpl: () => Promise.reject(new Error("no fetch in this test")),
        })}
        onDone={() => undefined}
      />,
    );
    expect(done).toContain(i18n.t("tenancy.signup.provisioning.ready.lead"));
    expect(done).not.toContain(i18n.t("tenancy.signup.provisioning.reassure"));
  });

  it("while the commit is in flight there is no address to leave to, so no way out is offered", () => {
    const markup = renderToStaticMarkup(
      <ProvisioningPanel
        utilityName="Brazos Bend Utilities"
        result={null}
        client={createApiClient({ fetchImpl: () => Promise.reject(new Error("no fetch in this test")) })}
        onDone={() => undefined}
      />,
    );
    expect(markup).toContain(
      i18n.t("tenancy.signup.provisioning.building", { name: "Brazos Bend Utilities" }),
    );
    expect(markup).not.toContain("signup-provisioning-continue");
  });

  it("every one of the screen's keys exists in ALL ELEVEN catalogues (G15/G27's shape, asserted here too)", () => {
    const keys = [
      "tenancy.signup.provisioning.title",
      "tenancy.signup.provisioning.building",
      "tenancy.signup.provisioning.lead",
      "tenancy.signup.provisioning.reassure",
      "tenancy.signup.provisioning.continue",
      "tenancy.signup.provisioning.ready.title",
      "tenancy.signup.provisioning.waiting.lead",
      "tenancy.signup.provisioning.partial.lead",
      "tenancy.signup.provisioning.state.working",
      "tenancy.signup.provisioning.state.done",
      "tenancy.signup.provisioning.state.queued",
      "tenancy.signup.provisioning.state.failed",
      "tenancy.signup.provisioning.step.sampleProgress",
    ];
    // ⚠ READ THE CATALOGUE, NOT `t()`. i18next falls back to English for a key
    // a locale is missing, so `getFixedT("ko-KR")(key)` returns an English
    // SENTENCE for a Korean key that does not exist — a check that cannot tell
    // present from absent, which is worse than no check at all (CLAUDE.md).
    // Proved by deleting one key from ko-KR.json: through `t()` the assertion
    // stayed green; through the bundle below it goes red naming the locale.
    const bundles = LOCALE_CODES.map(
      (locale) => [locale, i18n.getResourceBundle(locale, "translation")] as const,
    );
    for (const [locale, bundle] of bundles) {
      for (const key of keys) {
        expect(Object.keys(bundle ?? {}), `${locale} is missing ${key}`).toContain(key);
      }
    }
  });

  it.todo(
    "browser scope → CR-017 journey: signing up for a NEW tenant shows the named steps for the whole wait and lands on the checklist",
  );
});

describe("DEF-539 — the draft survives a reload, the password never does", () => {
  const FILLED = {
    ...EMPTY_SIGNUP_DRAFT,
    name: "Brazos Bend Utilities",
    subdomain: "brazosbend",
    state: "TX",
    services: ["water", "electric"],
    taxRegion: "TX",
    plan: "growth",
    ownerName: "Dana Whitfield",
    ownerEmail: "dana@brazosbendutilities.com",
    ownerPassword: "S3cure!passw0rd",
    ownerPhone: "555-0142",
    termsAccepted: true,
  };

  it("the stored string NEVER carries the password", () => {
    // ⚠ THE point of `storableSignup` being its own function: sessionStorage
    // is readable by anything on the origin, and a password at rest there is
    // a defect whatever else this feature does.
    const stored = storableSignup(FILLED, 3);
    expect(stored).not.toContain("S3cure!passw0rd");
    expect(stored).not.toContain("ownerPassword");
  });

  it("round-trips every field EXCEPT the password, and the reached step", () => {
    const back = restoreSignup(storableSignup(FILLED, 3));
    expect(back).not.toBeNull();
    expect(back?.reached).toBe(3);
    expect(back?.draft).toEqual({ ...FILLED, ownerPassword: "" });
  });

  it("restores nothing from garbage, and never a half-broken form", () => {
    expect(restoreSignup(null)).toBeNull();
    expect(restoreSignup("not json {")).toBeNull();
    expect(restoreSignup('{"draft": 7}')).toBeNull();
    // wrong-typed fields are dropped one by one, right-typed ones survive
    const partial = restoreSignup(
      '{"draft": {"name": "Brazos", "services": "water", "loadDefaults": "yes"}, "reached": 99}',
    );
    expect(partial?.draft.name).toBe("Brazos");
    expect(partial?.draft.services).toEqual([]); // a string is not a list
    expect(partial?.draft.loadDefaults).toBe(true); // the default, not "yes"
    expect(partial?.reached).toBe(5); // clamped to the wizard's own count
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-2371 — the page footer told every signing-up utility two untrue things
// ══════════════════════════════════════════════════════════════════════════
//
// `tenancy.signup.foot` renders unconditionally under BOTH the wizard steps and
// the provisioning panel, and it read: *"Account and meter data migration
// happens separately in Settings — this only captures configuration."*
//
//   * **"in Settings" named a screen that does not exist.** The four import
//     screens are `/:tenant/accounts/import` (S68), `/:tenant/assets/import`,
//     `/:tenant/premises/import` and `/:tenant/premises/units/import` — every
//     one of them reached from Accounts, Assets or Premises, none from
//     Settings. A new utility sent to Settings hunts for a screen that is not
//     there.
//   * **"only captures configuration" was false while it was on screen.** The
//     block running underneath that very sentence calls
//     `apps/customers/sample_data.py::seed_sample_records`, which creates ONE
//     ACTIVE ACCOUNT PER SEEDED UNIT — 48 — each through `create_account`, the
//     account wizard's own call, with its contact, its billing address and the
//     service agreements its unit's service points imply.
//
// ⚠ **NOTHING IN THIS REPO CHECKS WHETHER A SENTENCE IS TRUE**, so the fix has
// to be tied to something a future change would break. The catalogue test below
// asserts each locale's footer against THAT LOCALE'S OWN NAV LABELS, read from
// the same catalogue the sidebar reads — so renaming a section without
// revisiting this copy goes red instead of shipping another wrong destination.
// That is G49's question (does a served string name the screen a person would
// actually go to) asked of the four import screens, which G49 does not cover.
describe("DEF-2371 — the signup footer is true, and names screens that exist", () => {
  /** The three sidebar sections the four import screens hang from, verified
   *  against `App.tsx` on 2026-08-28: Accounts → `/:tenant/accounts/import`;
   *  Assets → `/:tenant/assets/import`; Premises → `/:tenant/premises/import`
   *  and `/:tenant/premises/units/import`. */
  const NAV_KEYS = ["shell.nav.accounts", "shell.nav.assets", "shell.nav.premises"] as const;

  it("the footer no longer sends anyone to Settings, and no longer calls signup configuration-only", () => {
    const html = renderWizard();
    expect(html).toContain(i18n.t("tenancy.signup.foot"));
    // The two false halves, gone.
    expect(html).not.toContain("migration happens separately in Settings");
    expect(html).not.toContain("this only captures configuration");
  });

  it("the footer says what is really being created now — sample data, so you can see it working", () => {
    const foot = i18n.t("tenancy.signup.foot");
    expect(foot).toMatch(/sample data/i);
    // …and it does not describe the run as configuration-only, which is the
    // claim `seed_sample_records`' 48 accounts contradict.
    expect(foot).not.toMatch(/only captures configuration/i);
  });

  it("EVERY catalogue's footer names that locale's OWN nav labels for the import screens", () => {
    // ⚠ READ THE CATALOGUE, NOT `t()` — the same trap the eleven-catalogue key
    // check above documents: i18next falls back to English, so `t()` would
    // report an English sentence for a locale whose footer was never rewritten
    // and this assertion could not tell a translation from a fallback.
    const missing: string[] = [];
    for (const locale of LOCALE_CODES) {
      const bundle = i18n.getResourceBundle(locale, "translation") as Record<string, string>;
      const foot = bundle["tenancy.signup.foot"];
      expect(foot, `${locale} has no tenancy.signup.foot`).toBeTypeOf("string");

      // Not a leftover copy of the false English sentence.
      expect(foot, `${locale} still carries the old English footer`).not.toContain(
        "only captures configuration",
      );

      for (const key of NAV_KEYS) {
        const label = bundle[key];
        expect(label, `${locale} has no ${key}`).toBeTypeOf("string");
        if (!foot.includes(label)) {
          missing.push(`${locale}: footer does not name ${key} (${label})`);
        }
      }
    }
    expect(missing, missing.join("\n")).toEqual([]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03; regenerated for the BR-TEN-045 post-signup handoff; fix pass 2026-08-10 for the PO's smartbillhub.bynry.com host choice)
// generated: 2026-08-09 by story-coder v1 · amended 2026-08-10 by story-coder v1 (+3 tests: configured suffix, the PO production pin, the local-dev fallback; +1 test: the S110 availability line no longer hardcodes a domain) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-19 by story-coder (CR-017 lane — 9 tests for the provisioning screen: `plantPhase` driven through all five states, the two render-able phases asserted on rendered text, DEF-325's regression, and an eleven-catalogue key check that reads the BUNDLE rather than `t()` because `t()` falls back to English and cannot tell present from absent)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: 2026-08-10 re-run — trace_lint✔ tsc✔ eslint✔ vitest 509/509✔ (132 todo repo-wide; 3 in this file's suite — browser/journey/v2-deferred scope) · run_gates 11 PASS · 0 FAIL · 1 SKIP (G12 is the wave-close journey gate) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: none — the env-stubbing this suite used to need is gone with the variable it stubbed; the handoff tests now assert on PATHS composed by the ONE helper, which no local configuration can change
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
