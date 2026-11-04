// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 2c — OQ-273 (the four service colours) RULED
//           2026-08-20, decision log commit 4e78da4.
// Rules:    the ruling's own two constraints — every colour clear of the
//           #ec3013 brand accent, and DISTINGUISHABLE AT 8x8px — plus the
//           ratified FILL VARIANT for storm_water, the newcomer to the water
//           family, "because the pair misread at 8px".
// Impacts:  nothing in src/ — this is an instrument, not a screen.
// ───────────────────────────────────────────────────────
//
// WHY A RENDERING INSTRUMENT AND NOT A UNIT TEST
//
// `src/styles/tailwindTheme.test.ts` asserts the ten hexes and that no two are
// equal. That is arithmetic on strings and it CANNOT answer the constraint the
// ruling actually wrote down: *distinguishable at 8x8px*. Two hexes 3 units
// apart are unequal and indistinguishable. Hard-won law 1 — a config claiming a
// guarantee is not the guarantee — and law 6: no gate in this repo reads
// rendered output, so a human looks at the pixels or nobody does.
//
// So this renders all TEN dots through THE APPLICATION'S OWN STYLESHEET (it
// injects into a live app page rather than into a blank fixture, so a rule that
// failed to ship is a rule that fails to draw), at three sizes:
//
//   · 6px — the size `.rating-tag::before` actually draws in the product
//   · 8px — the size the ruling names as the legibility floor
//   · 8px magnified 8x, nearest-neighbour, so a person can SEE what an 8px dot
//     is made of without a loupe
//
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && npx vite build && \
//       E2E_BASE_URL=http://127.0.0.1:8180 \
//       E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//       CR018P2C_OUT=/tmp/cr018p2c/swatches \
//       npx playwright test e2e/CR-018-phase2c-swatches.spec.ts
//
// ⚠ REBUILD FIRST — boot_stack serves `dist/`, so a stale bundle photographs
// yesterday's palette, which is the one thing this file exists to see.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { baseUrl, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const OUT = process.env.CR018P2C_OUT ?? "/tmp/cr018p2c/swatches";

/** BR-RAT-024, in the SEED ORDER of tenancy/migrations/0001_initial.py. The
 *  codes carry underscores and the runtime class is `svc-${code}`, so these are
 *  the literal class suffixes, not the token names. */
const SERVICES = [
  ["electric", "Electric"],
  ["water", "Water"],
  ["gas", "Gas"],
  ["sewer", "Sewer"],
  ["trash", "Trash"],
  ["storm_water", "Storm water"],
  ["solar", "Solar"],
  ["broadband", "Broadband"],
  ["thermal_heat", "Thermal/Heat"],
  ["battery", "Battery"],
] as const;

/** The four OQ-273 minted, and the hex each was ruled to. */
const RULED: Record<string, string> = {
  storm_water: "rgb(47, 74, 122)", // #2f4a7a
  solar: "rgb(122, 154, 42)", // #7a9a2a
  thermal_heat: "rgb(168, 37, 107)", // #a8256b
  battery: "rgb(58, 163, 155)", // #3aa39b
};

test.describe("CR-018 Phase 2c — the ten service dots, rendered", () => {
  test("all ten draw, the four ruled hexes are the ones on screen, and storm water is hollow @app-server", async ({
    page,
  }) => {
    test.setTimeout(600_000);
    await page.setViewportSize({ width: 1280, height: 900 });
    await signIn(page);

    // A real app page, so the real bundled stylesheet is the one under test.
    await page.goto(`${baseUrl()}/${tenant()}/plans-rates`);
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.waitForTimeout(1_500);

    const swatches = await page.evaluate((services) => {
      const host = document.createElement("div");
      host.id = "cr018-swatches";
      host.style.cssText =
        "position:fixed;inset:0;z-index:99999;background:var(--color-bg);padding:28px;overflow:auto;font-family:var(--font-body)";

      const heading = (text: string) => {
        const h = document.createElement("div");
        h.textContent = text;
        h.style.cssText =
          "font-family:var(--font-heading);font-weight:800;font-size:14px;margin:18px 0 8px";
        return h;
      };

      /** One row of `.rating-tag` chips, with the dot forced to `size`. */
      const row = (size: number) => {
        const wrap = document.createElement("div");
        wrap.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;align-items:center";
        for (const [code, label] of services) {
          const tag = document.createElement("span");
          tag.className = `rating-tag svc-${code}`;
          tag.setAttribute("data-svc", code);
          tag.setAttribute("data-dot", String(size));
          tag.textContent = label;
          wrap.appendChild(tag);
        }
        const style = document.createElement("style");
        style.textContent = `#cr018-swatches .rating-tag[data-dot="${size}"]::before{width:${size}px;height:${size}px}`;
        wrap.appendChild(style);
        return wrap;
      };

      /** Bare dots, no chip, at 8px and magnified 8x with no smoothing. */
      const bare = (size: number, scale: number) => {
        const wrap = document.createElement("div");
        wrap.style.cssText = "display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end";
        for (const [code, label] of services) {
          const cell = document.createElement("div");
          cell.style.cssText = "display:flex;flex-direction:column;align-items:center;gap:6px";
          const box = document.createElement("div");
          box.style.cssText = `width:${size * scale}px;height:${size * scale}px;display:flex;align-items:center;justify-content:center`;
          const inner = document.createElement("span");
          inner.className = `rating-tag svc-${code}`;
          inner.setAttribute("data-bare", code);
          inner.style.cssText = `border:0;padding:0;transform:scale(${scale});transform-origin:center;image-rendering:pixelated`;
          box.appendChild(inner);
          const cap = document.createElement("div");
          cap.textContent = label;
          cap.style.cssText = "font-size:10px;color:var(--color-text);max-width:80px;text-align:center";
          cell.appendChild(box);
          cell.appendChild(cap);
          wrap.appendChild(cell);
        }
        const style = document.createElement("style");
        style.textContent = `#cr018-swatches .rating-tag[data-bare]::before{width:${size}px;height:${size}px}`;
        wrap.appendChild(style);
        return wrap;
      };

      host.appendChild(heading("TEN SERVICE DOTS · as the product draws them (6px)"));
      host.appendChild(row(6));
      host.appendChild(heading("THE SAME TEN AT 8px — the size OQ-273 names as the floor"));
      host.appendChild(row(8));
      host.appendChild(heading("8px MAGNIFIED 8x — every pixel an 8px dot is made of"));
      host.appendChild(bare(8, 8));
      document.body.appendChild(host);

      // Measure what actually rendered, from the ::before pseudo-element.
      const out: Record<string, { background: string; border: string; size: string }> = {};
      for (const [code] of services) {
        const el = document.querySelector(`#cr018-swatches .rating-tag[data-dot="8"].svc-${code}`);
        if (el === null) continue;
        const cs = getComputedStyle(el, "::before");
        out[code] = {
          background: cs.backgroundColor,
          border: `${cs.borderTopWidth} ${cs.borderTopStyle} ${cs.borderTopColor}`,
          size: `${cs.width} x ${cs.height}`,
        };
      }
      return out;
    }, SERVICES as unknown as [string, string][]);

    mkdirSync(OUT, { recursive: true });
    writeFileSync(join(OUT, "dots.json"), `${JSON.stringify(swatches, null, 1)}\n`);
    await page.locator("#cr018-swatches").screenshot({ path: join(OUT, "ten-service-dots.png") });

    // ── The assertions, each one a sentence from the ruling ─────────────
    // 1 · ALL TEN DRAW. Before OQ-273 four of them fell through to
    //     --color-neutral-500 and three services shared one grey dot.
    expect(Object.keys(swatches).sort()).toEqual(SERVICES.map(([c]) => c).sort());

    // 2 · THE FOUR RULED HEXES ARE THE ONES ON SCREEN — the fill for three,
    //     and for storm_water the BORDER, because its fill is transparent.
    expect(swatches.solar.background).toBe(RULED.solar);
    expect(swatches.thermal_heat.background).toBe(RULED.thermal_heat);
    expect(swatches.battery.background).toBe(RULED.battery);
    expect(swatches.storm_water.border).toBe(`2px solid ${RULED.storm_water}`);

    // 3 · STORM WATER IS HOLLOW, AND IT IS THE ONLY ONE. The shape variant is
    //     what separates it from water at a size where value separation dies.
    expect(swatches.storm_water.background).toBe("rgba(0, 0, 0, 0)");
    const hollow = Object.entries(swatches).filter(
      ([, v]) => v.background === "rgba(0, 0, 0, 0)",
    );
    expect(hollow.map(([c]) => c)).toEqual(["storm_water"]);

    // 4 · THE HOLLOW DOT DID NOT CHANGE SIZE. `box-sizing: border-box` is
    //     global, so the 2px border eats inward; a regression to content-box
    //     would make this one dot 12px while the other nine stayed 8px.
    for (const [code, v] of Object.entries(swatches)) {
      expect(v.size, `${code} is not the same box as the other nine`).toBe("8px x 8px");
    }

    // 5 · NO SERVICE WEARS THE BRAND ACCENT TWICE. Electric IS #ec3013 by r9's
    //     design; a second one would be unreadable as identity.
    const accent = Object.entries(swatches).filter(([, v]) => v.background === "rgb(236, 48, 19)");
    expect(accent.map(([c]) => c)).toEqual(["electric"]);

    // eslint-disable-next-line no-console
    console.log(`CR-018 Phase 2c swatches → ${OUT}\n${JSON.stringify(swatches, null, 1)}`);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 12-governance/02-decision-log.md 2026-08-20 OQ-273 (commits 918bf6f + 4e78da4) + 12-governance/11-change-requests.md CR-018
// generated: 2026-08-20 by the CR-018 Phase 2c lane
// checklist: A✔ B=n/a(instrument, no screen) C=deferred(no backend half) D=deferred(no API call) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST (hard-won law 7) — assertion 3 was proved by giving `.svc-battery::before` the same `background: transparent; border:` as storm water, which failed naming battery in the hollow list; assertion 4 was proved by setting `box-sizing: content-box` on the storm-water dot, which failed with "storm_water is not the same box as the other nine — 12px x 12px"; assertion 2 was proved by swapping solar to gas's #c47a1d.
// exceptions: it renders an INJECTED fragment, not a product screen — the ten services are a platform seed and no single tenant fixture carries all ten, so the alternative is photographing four grey dots and calling it a palette
// status: VERIFIED-UNRATIFIED
