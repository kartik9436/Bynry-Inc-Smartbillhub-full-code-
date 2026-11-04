// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 · US-CUS-005 · US-CUS-013 · US-CUS-014 · US-CUS-015 ·
//           US-CUS-016 · US-CUS-018   Screens: S21
// Change:   CR-094-BRC01 step 2 wave L — `BR-CUS-1051`, the eight quick actions
//           open OVER the account. PO 2026-09-13, verbatim: *"Yes move the
//           eight quick actions over the account"*.
// Rules:    BR-CUS-1051 · BR-SHL-025 · B14 rule 30 (DECLINED — the PO answered
//           this INSTANCE) · B14 rule 32
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE HERE ASSERTS A DOOR BY ITS ADDRESS AND BY WHAT IT OPENS**,
// which is CLAUDE.md hard-won law 2's own prescription. A wave that moves eight
// controls has eight chances to point one at nothing, and `tsc` cannot see any
// of them: a route whose element is the wrong screen, a `mounted` entry naming
// an overlay nobody declares, an overlay nobody reaches, an address that
// changed spelling and broke the OTHER door. Each is checked below, by name.
//
// ⚠ **AND THE SECOND DOOR IS CHECKED AS HARD AS THE FIRST.** Three of the eight
// are also reachable from their own address elsewhere in the product; a wizard
// that worked only inside the dialog would be a regression that no gate here
// reads rendered output to catch.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { isValidElement } from "react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useParams, useSearchParams } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { describe, expect, it } from "vitest";

// ⚠ **NODE'S OWN MODULES, REACHED THE WAY `wizardRailCensus.test.ts` AND
// `styles/routeBUtilities.test.ts` REACH THEM — AND THE REASON IS A BROKEN
// PRODUCTION BUILD, NOT A STYLE PREFERENCE.** This file first imported
// `node:fs` and `node:url` statically. `npm run build` is `tsc --noEmit &&
// vite build` and the Dockerfile runs it *"on purpose: a type error must fail
// the image, not ship in it"* — so with no `@types/node` in this tsconfig, two
// import lines in a TEST file failed the frontend image with
// `TS2307: Cannot find module 'node:fs'`. It was reported by the Product Owner
// from a `docker compose` run, not by any check here, because `vitest` resolves
// these at run time and never asks `tsc` about them.
// The string-split import keeps Vite from pre-bundling them and keeps `tsc`
// quiet without adding a dependency the product does not otherwise need.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import { BillDocumentPage } from "@/features/billing/BillDocumentPage";
import { FixABillTab } from "@/features/billing/FixABillTab";
import { BillsListPage } from "@/features/billing/BillsListPage";
import { ToastProvider } from "@/components/Toast";

import {
  ACCOUNT_ACTION_OVERLAYS,
  AccountActionOverlay,
  accountOverlayAt,
  accountOverlayPath,
} from "./accountActionOverlays";
import { ChangePlanWizard } from "./ChangePlanWizard";
import { CloseOutPage } from "./CloseOutPage";
import { DisconnectWizard } from "./DisconnectWizard";
import { MoveInWizard } from "./MoveInWizard";
import { MoveOutWizard } from "./MoveOutWizard";
import { PaymentPlanWizard } from "./PaymentPlanWizard";
import {
  accountChangePlanPath,
  accountCloseOutPath,
  accountDetailPath,
  accountMoveInPath,
  accountMoveOutPath,
  accountPaymentPlanPath,
} from "./customersShared";

const ACCOUNT = "acc-10432";
const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** Every route in the tree, with its FULL path — the same walk
 *  `routing/screenIds.test.tsx` makes, so the two read the table alike. */
function walk(
  routes: readonly RouteObject[],
  parent = "",
): { path: string; route: RouteObject }[] {
  const out: { path: string; route: RouteObject }[] = [];
  for (const route of routes) {
    let here = parent;
    if (typeof route.path === "string") {
      here = route.path.startsWith("/")
        ? route.path
        : `${parent === "/" ? "" : parent}/${route.path}`;
      out.push({ path: here, route });
    }
    if (route.children) {
      out.push(...walk(route.children, here));
    }
  }
  return out;
}

const ROUTES = walk(APP_ROUTES);

function routeAt(path: string): RouteObject | undefined {
  return ROUTES.find((entry) => entry.path === path)?.route;
}

/** The component a route's `element` renders — `undefined` for a pathless or
 *  elementless route, so a wrong answer never reads as a match. */
function componentOf(route: RouteObject | undefined): unknown {
  const element = route?.element;
  return isValidElement(element) ? (element as ReactElement).type : undefined;
}

describe("BR-CUS-1051 — the eight are CHILD ROUTES of the account", () => {
  const ACCOUNT_ROUTE = "/:tenant/accounts/:accountId";

  it("the account route owns children, and they are exactly the eight overlays", () => {
    const account = routeAt(ACCOUNT_ROUTE);
    expect(account, "the account detail route is declared").toBeDefined();
    expect((account?.children ?? []).map((child) => child.path)).toEqual(
      ACCOUNT_ACTION_OVERLAYS.map((overlay) => overlay.segment),
    );
  });

  it("each child opens the screen the overlay table names, BY COMPONENT", () => {
    // ⚠ **THE CASE THAT MATTERS MOST HERE.** A child route pointing at the
    // wrong screen compiles, renders, and opens a dialog onto something the
    // clerk did not ask for. Comparing ADDRESSES alone cannot see it.
    const expected: Record<string, unknown> = {
      "move-out": MoveOutWizard,
      "move-in": MoveInWizard,
      "close-out": CloseOutPage,
      "bills/:invoiceId/document": BillDocumentPage,
      "issue-credit": FixABillTab,
      "change-plan": ChangePlanWizard,
      disconnect: DisconnectWizard,
      "payment-plan": PaymentPlanWizard,
    };
    for (const overlay of ACCOUNT_ACTION_OVERLAYS) {
      expect(
        componentOf(routeAt(`${ACCOUNT_ROUTE}/${overlay.segment}`)),
        `${overlay.id} opens its own screen`,
      ).toBe(expected[overlay.segment]);
    }
  });

  it("does not re-spell the five addresses the product already had", () => {
    // A nesting, not a re-addressing: a changed string here would break every
    // existing link, every test and every bookmark at once.
    expect(accountOverlayPath("moveOut", ACCOUNT)).toBe(accountMoveOutPath(ACCOUNT));
    expect(accountOverlayPath("moveIn", ACCOUNT)).toBe(accountMoveInPath(ACCOUNT));
    expect(accountOverlayPath("closeOut", ACCOUNT)).toBe(accountCloseOutPath(ACCOUNT));
    expect(accountOverlayPath("changePlan", ACCOUNT)).toBe(accountChangePlanPath(ACCOUNT));
    expect(accountOverlayPath("paymentPlan", ACCOUNT)).toBe(accountPaymentPlanPath(ACCOUNT));
  });
});

describe("BOTH DOORS — the three that were never account-scoped keep their own", () => {
  // A wizard that only worked inside the dialog would be a regression, and the
  // only thing that can see it is an assertion by ADDRESS and by COMPONENT.
  it("the bill document is still at billing's address", () => {
    expect(componentOf(routeAt("/:tenant/billing/bills/:invoiceId/document"))).toBe(
      BillDocumentPage,
    );
  });

  it("the fix-a-bill tab is still reachable through the bills screen", () => {
    expect(componentOf(routeAt("/:tenant/billing/:tab"))).toBe(BillsListPage);
  });

  it("the disconnect wizard is still at /disconnects/new", () => {
    expect(componentOf(routeAt("/:tenant/disconnects/new"))).toBe(DisconnectWizard);
  });

  it("the standalone move-in and move-out doors are untouched", () => {
    expect(componentOf(routeAt("/:tenant/move-ins/new"))).toBe(MoveInWizard);
    expect(componentOf(routeAt("/:tenant/move-outs/new"))).toBe(MoveOutWizard);
  });
});

describe("accountOverlayAt — which overlay the browser is standing on", () => {
  it("resolves every one of the eight from the address it generates", () => {
    for (const overlay of ACCOUNT_ACTION_OVERLAYS) {
      const path = accountOverlayPath(overlay.id, ACCOUNT, { invoiceId: "inv-7" });
      expect(accountOverlayAt(`/${TENANT}${path}`, ACCOUNT)?.id).toBe(overlay.id);
    }
  });

  it("is null on the account itself — the dialog must not open unasked", () => {
    expect(accountOverlayAt(`/${TENANT}${accountDetailPath(ACCOUNT)}`, ACCOUNT)).toBeNull();
    expect(accountOverlayAt(`/${TENANT}${accountDetailPath(ACCOUNT)}/`, ACCOUNT)).toBeNull();
  });

  it("is null for a tab, a stranger's address, and an unknown segment", () => {
    expect(accountOverlayAt(`/${TENANT}/accounts/other/move-out`, ACCOUNT)).toBeNull();
    expect(accountOverlayAt(`/${TENANT}${accountDetailPath(ACCOUNT)}/renumber`, ACCOUNT)).toBeNull();
    expect(accountOverlayAt(`/${TENANT}${accountDetailPath(ACCOUNT)}`, "")).toBeNull();
  });

  it("matches the bill document whatever the bill id is", () => {
    const at = accountOverlayAt(`/${TENANT}/accounts/${ACCOUNT}/bills/anything/document`, ACCOUNT);
    expect(at?.id).toBe("printBill");
  });
});

describe("accountOverlayPath refuses to build a half-resolved link", () => {
  it("throws rather than putting :invoiceId in the URL bar", () => {
    // A link that half-resolves is hard-won law 2's dead control wearing a
    // plausible href — it renders, it is clickable, and it opens nothing.
    expect(() => accountOverlayPath("printBill", ACCOUNT)).toThrow(/invoiceId/);
    expect(() => accountOverlayPath("printBill", ACCOUNT, { invoiceId: "" })).toThrow(/invoiceId/);
  });
});

describe("the dialog head follows the screen, not a preference", () => {
  // ⚠ `ownsItsHeading` is a CLAIM ABOUT ANOTHER FILE, and a claim nothing
  // re-checks is what CLAUDE.md's own lesson is about. So it is re-checked: the
  // source is read and the claim measured against it.
  it("says a screen draws its own PageHeader only where it does", () => {
    const src = nodeUrl.fileURLToPath(new URL(".", import.meta.url)).replace(
      /features\/customers\/$/,
      "",
    );
    for (const overlay of ACCOUNT_ACTION_OVERLAYS) {
      const body = nodeFs.readFileSync(`${src}${overlay.source}`, "utf8");
      expect(body.includes("<PageHeader"), `${overlay.id} · ${overlay.source}`).toBe(
        overlay.ownsItsHeading,
      );
    }
  });
});

/** A stub child: it proves what the CONTAINER hands its screen, which is the
 *  half a wizard's own tests cannot see. */
function Subject() {
  const params = useParams();
  const [search] = useSearchParams();
  return (
    <p>
      subject={params.accountId ?? "none"} step={search.get("step") ?? "none"}
    </p>
  );
}

function renderOverlay(path: string): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${path}`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId"
              element={
                <div>
                  <h1>THE ACCOUNT IS STILL HERE</h1>
                  <AccountActionOverlay accountId={ACCOUNT} kicker="A-10432" t={t} />
                </div>
              }
            >
              {ACCOUNT_ACTION_OVERLAYS.map((overlay) => (
                <Route key={overlay.id} path={overlay.segment} element={<Subject />} />
              ))}
            </Route>
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("the container — a dialog OVER the account, and the account stays", () => {
  it("renders nothing at all on the bare account", () => {
    const html = renderOverlay(accountDetailPath(ACCOUNT));
    expect(html).toContain("THE ACCOUNT IS STILL HERE");
    expect(html).not.toContain('role="dialog"');
  });

  it("opens the dialog with the account still rendered behind it", () => {
    // `ACC-S14`'s acceptance sentence: a clerk acts *"without losing sight of
    // the balance behind it"*. If the host stops rendering, the ruling was not
    // honoured whatever the dialog looks like.
    const html = renderOverlay(accountMoveOutPath(ACCOUNT));
    expect(html).toContain("THE ACCOUNT IS STILL HERE");
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
  });

  it("hands the mounted screen the account from the PATH", () => {
    // The five screens that read `useParams().accountId` needed no prop, and
    // this is why. A container that swallowed the param would have forced eight
    // prop changes and a rewrite of every fixture.
    expect(renderOverlay(accountMoveOutPath(ACCOUNT))).toContain(`subject=${ACCOUNT}`);
  });

  it("PARK AND RESUME SURVIVES — ?step= reaches the wizard unchanged", () => {
    // ⚠ THE CASE THIS WAVE COULD MOST EASILY HAVE BROKEN. Three of the eight
    // keep their step in the query and save a half-finished job against it. A
    // `useState` dialog would have thrown the step away on every refresh and
    // every test would still have passed.
    expect(renderOverlay(`${accountMoveOutPath(ACCOUNT)}?step=4`)).toContain("step=4");
  });

  it("names itself with the action's own label where the screen owns the heading", () => {
    // B14 rule 32: one heading per surface. Seven of the eight draw their own
    // `PageHeader`, so the dialog head carries the ✕ alone — and the dialog is
    // still NAMED, or a screen reader is handed an unlabelled modal.
    const html = renderOverlay(accountMoveOutPath(ACCOUNT));
    expect(html).toContain(`aria-label="${t("customers.account.action.moveOut")}"`);
    expect(html).not.toContain('class="modal-title"');
  });

  it("draws a visible title for the one screen that has no heading of its own", () => {
    // `FixABillTab` is a TAB — `BillsListPage` draws the head at its own
    // address. Here the dialog must, or the surface has no heading at all.
    const html = renderOverlay(accountOverlayPath("issueCredit", ACCOUNT));
    expect(html).toContain('class="modal-title"');
    expect(html).toContain(t("customers.account.action.issueCredit"));
  });

  it("is WIDE — a six-step wizard is not a 560px card", () => {
    expect(renderOverlay(accountMoveOutPath(ACCOUNT))).toContain("w-[min(1120px,100%)]!");
  });
});

describe("DEF-CUS-5151 — a head with nothing in it is not rendered at all", () => {
  // ⚠ **WHAT THESE CASES CAN AND CANNOT PROVE, SAID OUT LOUD.** jsdom computes
  // no layout, so not one line here can say the band was 80px, that the ✕ moved
  // to 16px from the corner, or that the card now ends at the window edge.
  // Those were MEASURED in Chromium at 1280 and 1440 and the numbers are in the
  // lane report. What these cases own is the STRUCTURE the measurement depends
  // on — a `.modal-head` element that exists at all is a band, whatever its
  // height — and structure is the half that silently comes back.

  it("renders NO head band on the six screens that draw their own heading", () => {
    // The defect, exactly: `titleHidden` emptied the head's TEXT and kept the
    // head's BOX, so six of the eight drew two rules' worth of nothing with a
    // lone ✕ in it and began their real heading 181px down the card.
    for (const overlay of ACCOUNT_ACTION_OVERLAYS.filter((one) => one.ownsItsHeading)) {
      const html = renderOverlay(accountOverlayPath(overlay.id, ACCOUNT, { invoiceId: "inv-7" }));
      expect(html, `${overlay.id} draws no empty band`).not.toContain('class="modal-head"');
    }
  });

  it("still closes — the ✕ is present and named, it just costs no height", () => {
    // A frame fix that removed the close button would pass the case above and
    // trap a clerk in a dialog. IS-10 requires ✕, Esc and the backdrop.
    const html = renderOverlay(accountMoveOutPath(ACCOUNT));
    expect(html).toContain("modal-close");
    expect(html).toContain(`aria-label="${t("forms.close")}"`);
    expect(html).toContain("absolute top-4 right-4");
  });

  it("KEEPS the band where there IS something to draw in it", () => {
    // The mirror case, and the one that stops this fix becoming "no dialog in
    // the product ever has a head again". `issueCredit` mounts a TAB with no
    // heading of its own, so the band is the only heading the surface has.
    const html = renderOverlay(accountOverlayPath("issueCredit", ACCOUNT));
    expect(html).toContain('class="modal-head"');
    expect(html).toContain('class="modal-kicker"');
    expect(html).toContain('class="modal-title"');
  });

  it("ends at the window edge and scrolls its own body", () => {
    // Measured before the fix at 1440x900: the mounted screens rendered 876,
    // 894, 907, 939, 1113 and 1585px tall, so `.modal-overlay` scrolled the
    // whole card and took the ✕ off the top of the screen with it. That is what
    // reads as a near-full-screen panel — the height, not the width.
    const html = renderOverlay(accountMoveOutPath(ACCOUNT));
    expect(html).toContain("max-h-[calc(100vh-64px)]");
    // `min-h-0` is load-bearing: without it a flex child refuses to shrink
    // below its content and the cap above changes nothing until the content
    // gets tall — a guard that cannot fail, in CSS.
    expect(html).toContain("min-h-0 flex-1 overflow-y-auto");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 wave L · BR-CUS-1051 · decision log 2026-09-13
// generated: 2026-09-13 by the CR-094 wave L build lane
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest accountActionOverlays.dom.test.tsx
// exceptions: E4 the container cases mount a STUB child rather than the real 1,500-line wizards — what is under test is what the CONTAINER hands its screen (the param, the query, the host still rendering), and each wizard's own suite already owns its behaviour at its own address
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
