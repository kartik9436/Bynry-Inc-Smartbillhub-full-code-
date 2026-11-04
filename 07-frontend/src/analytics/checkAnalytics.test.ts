// CR-169-BRC10 §2 row 10 — the post-deploy check. Drives its pure verdict.
import { describe, expect, it } from "vitest";

// @ts-expect-error — plain .mjs Node script; no .d.ts on purpose.
import { fingerprint, inspectBundle } from "../../scripts/checkAnalytics.mjs";

const PROD = "phc_PRODUCTIONproductionPRODUCTION01";
const DEV = "phc_DEVELOPMENTdevelopmentDEVELOP01";
const FP = fingerprint(PROD) as string;
const HTML = `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; connect-src 'self' https://us.i.posthog.com https://us-assets.i.posthog.com" />`;

type Verdict = { ok: boolean; lines: string[] };
const run = (mode: string, scripts: string[], html = HTML, prodFingerprint = FP) =>
  inspectBundle({ mode, html, scripts, prodFingerprint }) as Verdict;

describe("checkAnalytics", () => {
  it("passes a dev bundle with the dev key, fails it with the production key", () => {
    expect(run("dev", [`const k="${DEV}"`]).ok).toBe(true);
    expect(run("dev", [`const k="${PROD}"`]).ok).toBe(false);
  });

  it("passes a production bundle only with the production key", () => {
    expect(run("production", [`const k="${PROD}"`]).ok).toBe(true);
    expect(run("production", [`const k="${DEV}"`]).ok).toBe(false);
  });

  it("fails over zero scripts and without a fingerprint (law 7)", () => {
    expect(run("dev", []).ok).toBe(false);
    expect(run("dev", ["x"], HTML, "").ok).toBe(false);
  });

  it("says OFF, not 'keys correct', for a key-less bundle", () => {
    const verdict = run("production", ["const nothing = 1"]);
    expect(verdict.lines.join("\n")).toContain("analytics OFF");
  });

  it("fails when the page policy does not let PostHog in, or widens script-src", () => {
    expect(run("dev", ["x"], `<meta http-equiv="Content-Security-Policy" content="script-src 'self'; connect-src 'self'" />`).ok).toBe(false);
    expect(
      run("dev", ["x"], HTML.replace("script-src 'self'", "script-src 'self' https://us-assets.i.posthog.com")).ok,
    ).toBe(false);
  });
});
