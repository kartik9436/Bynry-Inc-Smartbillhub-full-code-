// CR-169-BRC10 §2 row 4(a) — the BUILD refuses a dev or sandbox bundle carrying
// the production key, and a production bundle carrying any other. Drives the
// exact function `vite.config.ts` calls. Written before it existed (red first).
import { describe, expect, it } from "vitest";

// @ts-expect-error — plain .mjs shared with vite.config.ts; no .d.ts on purpose.
import { bakedPagePolicy, keyFingerprint, readBasePolicyDirectives, resolvePosthogConfig } from "../../scripts/deployConfig.mjs";

const PROD = "phc_production_key";
const DEV = "phc_dev_key";
const FP = keyFingerprint(PROD) as string;

const env = (extra: Record<string, string>) => ({
  VITE_POSTHOG_HOST: "https://us.i.posthog.com",
  VITE_POSTHOG_EXPECTED_HOSTS: "app-dev.bynry.com",
  VITE_POSTHOG_PROD_KEY_FINGERPRINT: FP,
  ...extra,
});

describe("resolvePosthogConfig (vite.config.ts)", () => {
  it("is off — empty key — when no key is given, in every mode", () => {
    for (const mode of ["dev", "sandbox", "production", "development", "test", "compose"]) {
      expect(resolvePosthogConfig(mode, {}).key).toBe("");
    }
  });

  it("REFUSES a dev or sandbox build carrying the production key", () => {
    expect(() => resolvePosthogConfig("dev", env({ VITE_POSTHOG_KEY: PROD }))).toThrow(/PRODUCTION key/);
    expect(() => resolvePosthogConfig("sandbox", env({ VITE_POSTHOG_KEY: PROD }))).toThrow(/PRODUCTION key/);
    expect(() => resolvePosthogConfig("development", env({ VITE_POSTHOG_KEY: PROD }))).toThrow(/PRODUCTION key/);
  });

  it("REFUSES a production build carrying any key but the production one", () => {
    expect(() => resolvePosthogConfig("production", env({ VITE_POSTHOG_KEY: DEV }))).toThrow(/not the PRODUCTION key/);
  });

  it("accepts the right key for its environment", () => {
    expect(resolvePosthogConfig("dev", env({ VITE_POSTHOG_KEY: DEV })).key).toBe(DEV);
    expect(resolvePosthogConfig("production", env({ VITE_POSTHOG_KEY: PROD })).key).toBe(PROD);
  });

  it("REFUSES a key with no production fingerprint to compare it with", () => {
    expect(() =>
      resolvePosthogConfig("dev", { VITE_POSTHOG_KEY: DEV, VITE_POSTHOG_EXPECTED_HOSTS: "app-dev.bynry.com" }),
    ).toThrow(/VITE_POSTHOG_PROD_KEY_FINGERPRINT/);
  });

  it("REFUSES a key with no expected web host", () => {
    expect(() => resolvePosthogConfig("dev", env({ VITE_POSTHOG_KEY: DEV, VITE_POSTHOG_EXPECTED_HOSTS: "" }))).toThrow(
      /VITE_POSTHOG_EXPECTED_HOSTS/,
    );
  });

  it("REFUSES an ingest host other than PostHog US cloud (PO answer 2)", () => {
    expect(() =>
      resolvePosthogConfig("dev", env({ VITE_POSTHOG_KEY: DEV, VITE_POSTHOG_HOST: "https://eu.i.posthog.com" })),
    ).toThrow(/us\.i\.posthog\.com/);
  });

  it("fingerprints as the first 16 hex of SHA-256, the same as the server", () => {
    // sha256("phc_production_key") — the server's `product_analytics.fingerprint` spells it the same way.
    expect(FP).toMatch(/^[0-9a-f]{16}$/);
  });
});

describe("the page policy lets PostHog US in, and nothing else changes (CR-169-BRC10 step 7)", () => {
  it("connect-src names the ingest host and the recorder-asset host; script-src stays 'self'", async () => {
    const directives = (await readBasePolicyDirectives()) as string[];
    const policy = bakedPagePolicy(directives, "https://api-smart360.bynry.com") as string;
    const clause = (name: string) => policy.split("; ").find((one) => one.startsWith(`${name} `));
    expect(clause("connect-src")).toContain("https://us.i.posthog.com");
    expect(clause("connect-src")).toContain("https://us-assets.i.posthog.com");
    // The recorder is bundled: no PostHog script host, ever.
    expect(clause("script-src")).toBe("script-src 'self'");
    expect(policy).not.toContain("*");
  });
});
