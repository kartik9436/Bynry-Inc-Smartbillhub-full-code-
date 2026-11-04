// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CWP-10561 (F-05 language) · DEF-CWP-10562 (F-07 titles) ·
//           DEF-CWP-10563 (F-20 headings) · DEF-CWP-10564 (F-12 unnamed control) ·
//           DEF-CWP-10565 (F-14 loading placeholder) · DEF-CWP-10566 (F-23 link
//           names) · DEF-CWP-10567 (F-24 one door, one name)
// Rules:    decision log 2026-10-23 — "Portal accessibility, Group D …",
//           "Group E …" and "Groups D and E: how it is built".
// Rendered: 10-scripts/a11y/portal_outline_scan.mjs --assert walks every
//           route in a real browser; these cases hold the shared roots in the
//           suite so a regression goes red without a browser.
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import { queryKeys } from "@/api/queryClient";
import { HeadingLevelProvider } from "@/components/HeadingLevel";
import { Panel } from "@/components/Panel";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";

import type { PortalFront } from "../api/guestClient";
import type { PortalHome, PortalRequestHub } from "../api/portalClient";

let readHome: () => Promise<PortalHome> = async () => {
  throw new Error("no behaviour set");
};
let readHub: () => Promise<PortalRequestHub> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getHome: () => readHome(), getRequestHub: () => readHub() };
});

const { HomeView } = await import("../home/Home");
const { RequestsView } = await import("../requests/Requests");
const { FrontPage } = await import("../guest/FrontPage");
const { FrontDoorView } = await import("../signin/FrontDoor");
const { PortalDocumentTitle, portalPageName } = await import("../components/PortalDocumentTitle");
const { ErrandCard, ErrandLink } = await import("../components/primitives");

// Node's own modules, reached the way `pageHeadCensus.test.ts` does: `@types/node`
// is deliberately not installed, so a plain `node:fs` import fails `tsc`.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string): string[];
  statSync(p: string): { isDirectory(): boolean };
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
};
const { readFileSync, readdirSync, statSync } = nodeFs;
const { join } = nodePath;

// Under jsdom `import.meta.url` is an http address, so the source root comes
// from the working directory vitest runs in (07-frontend).
const SRC = join((globalThis as unknown as { process: { cwd(): string } }).process.cwd(), "src");
const LOCALES = join(SRC, "i18n", "locales");

const FRONT: PortalFront = {
  tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: "#EC3013", brand_accent_hex: null },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
  locales: ["en", "es"],
  cards: [
    { key: "pay_bill", available: true, reason_code: null },
    { key: "report_problem", available: true, reason_code: null },
    { key: "start_service", available: true, reason_code: null },
    { key: "help_answers", available: true, reason_code: null },
  ],
  links: { help: true, visit: true },
  switches: undefined,
  services: [{ code: "water", name: "Water", color: null }],
  strapline: "Your account, any time.",
  office_hours_text: "8am to 5pm, Monday to Friday",
  emergency_phone: "(512) 555-0100",
} as unknown as PortalFront;

/** The portal's own outline root, exactly as `PortalApp` declares it. */
function portal(path: string, pattern: string, element: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.portalFront, FRONT);
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={pattern} element={<HeadingLevelProvider level={2}>{element}</HeadingLevelProvider>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** The outline a screen reader is given: `[level, text]` for every heading. */
function outline(root: ParentNode = document.body): [number, string][] {
  return [...root.querySelectorAll("h1,h2,h3,h4,h5,h6,[role=heading]")].map((h) => [
    Number(h.getAttribute("aria-level") ?? h.tagName.slice(1)),
    (h.textContent ?? "").trim(),
  ]);
}

/** Exactly one h1, and no heading more than one level below the one before it (an h2 above the h1 is a frame notice). */
function outlineProblems(heads: [number, string][]): string[] {
  const problems: string[] = [];
  const h1s = heads.filter(([level]) => level === 1).length;
  if (h1s !== 1) problems.push(`${h1s} h1`);
  let previous = 1;
  for (const [level, text] of heads) {
    if (level > previous + 1) problems.push(`h${previous} → h${level} "${text}"`);
    previous = level;
  }
  return problems;
}

/** Two links on one page that read the same and go to different places. */
function sharedLinkNames(root: ParentNode = document.body): string[] {
  const byName = new Map<string, Set<string>>();
  for (const a of root.querySelectorAll("a[href]")) {
    const name = (a.getAttribute("aria-label") ?? a.textContent ?? "").trim();
    const href = a.getAttribute("href") ?? "";
    byName.set(name, (byName.get(name) ?? new Set()).add(href));
  }
  return [...byName].filter(([, hrefs]) => hrefs.size > 1).map(([name]) => name);
}

/** A control a screen reader cannot name. */
function unnamedControls(root: ParentNode = document.body): string[] {
  return [...root.querySelectorAll("select, input:not([type=hidden]), textarea, button")]
    .filter((el) => {
      if (el.getAttribute("aria-label") || el.getAttribute("aria-labelledby")) return false;
      if (el.tagName === "BUTTON") return (el.textContent ?? "").trim() === "";
      if (el.id && root.querySelector(`label[for="${el.id}"]`)) return false;
      return el.closest("label") === null;
    })
    .map((el) => el.outerHTML.slice(0, 80));
}

afterEach(async () => {
  cleanup();
  await act(async () => {
    await i18n.changeLanguage("en");
  });
});

describe("F-05 · <html lang> follows the catalogue (DEF-CWP-10561)", () => {
  it("is the catalogue's code on the first load and after every switch", async () => {
    expect(document.documentElement.lang).toBe("en");
    await act(async () => {
      await i18n.changeLanguage("es");
    });
    expect(document.documentElement.lang).toBe("es");
    await act(async () => {
      await i18n.changeLanguage("es-MX");
    });
    expect(document.documentElement.lang).toBe("es-MX");
    await act(async () => {
      await i18n.changeLanguage("en");
    });
    expect(document.documentElement.lang).toBe("en");
  });

  it("every language name in a portal language picker carries its own lang", () => {
    // The three pickers that list languages by their own names.
    for (const file of ["portal/shell/GuestLanguage.tsx", "portal/details/Preferences.tsx", "portal/guest/ApplicationPreferences.tsx"]) {
      const source = readFileSync(join(SRC, file), "utf8");
      expect(source, file).toMatch(/lang(=\{code\}|: code)/);
    }
  });
});

describe("F-07 · every portal page titles its own tab (DEF-CWP-10562)", () => {
  it("writes '<page h1> · <utility>' and follows the h1 as it changes", async () => {
    const view = portal(
      "/pine-hill/portal/pay",
      "/:tenant/portal/pay",
      <>
        <PortalDocumentTitle />
        <h1 data-testid="head">Find your bill</h1>
      </>,
    );
    await waitFor(() => expect(document.title).toBe("Find your bill · Pine Hill Water & Power"));
    act(() => {
      view.getByTestId("head").textContent = "Let us find that bill again";
    });
    await waitFor(() => expect(document.title).toBe("Let us find that bill again · Pine Hill Water & Power"));
  });

  it("a page whose h1 is the failure card's level-1 line is named by that line", () => {
    document.body.innerHTML = '<div role="alert"><p role="heading" aria-level="1">We could not open this page.</p></div>';
    expect(portalPageName(document.body)).toBe("We could not open this page.");
    document.body.innerHTML = "";
  });

  it("an open dialog's heading wins over the page's", () => {
    document.body.innerHTML =
      '<h1>Your bills</h1><div role="dialog" aria-modal="true"><h2>Remove this card?</h2></div>';
    expect(portalPageName(document.body)).toBe("Remove this card?");
    document.body.innerHTML = "";
  });

  it("is mounted once at the portal's root, so no route is born without one", () => {
    const app = readFileSync(join(SRC, "portal/PortalApp.tsx"), "utf8");
    expect(app).toContain("<PortalDocumentTitle />");
    expect(app).toMatch(/<HeadingLevelProvider level=\{2\}>\{element\}<\/HeadingLevelProvider>/);
  });
});

describe("F-20 · one h1 per page, no skipped levels, sizes unchanged (DEF-CWP-10563)", () => {
  it("a Panel's title is an h3 on a staff screen and the outline's level in the portal", () => {
    render(<Panel title="Staff">x</Panel>);
    expect(screen.getByRole("heading", { name: "Staff" }).tagName).toBe("H3");
    cleanup();
    render(
      <HeadingLevelProvider level={2}>
        <Panel title="Outer">
          <Panel title="Inner">y</Panel>
        </Panel>
      </HeadingLevelProvider>,
    );
    const outer = screen.getByRole("heading", { name: "Outer" });
    expect(outer.tagName).toBe("H2");
    // The size is the panel title's own, carried onto the element.
    expect(outer.className).toContain("text-h5");
    expect(screen.getByRole("heading", { name: "Inner" }).tagName).toBe("H3");
  });

  it("the failure card that replaces a whole portal page is that page's level-1 heading", () => {
    render(
      <HeadingLevelProvider level={2}>
        <FailedWithRetry title="We could not open this page." reason="You're signed out." onRetry={() => undefined} />
      </HeadingLevelProvider>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "We could not open this page." })).toBeInTheDocument();
    cleanup();
    render(<FailedWithRetry title="Import failed." reason="r" onRetry={() => undefined} />);
    expect(screen.queryByRole("heading")).toBeNull();
  });

  it("signed-in Home has one hidden h1, 'Your account home', and no skipped level", async () => {
    readHome = async () => HOME;
    portal("/pine-hill/portal/home", "/:tenant/portal/home", <HomeView today={new Date("2026-09-02T00:00:00Z")} />);
    const h1 = await screen.findByRole("heading", { level: 1, name: "Your account home" }, { timeout: 4000 });
    expect(h1.className).toContain("sr-only");
    await screen.findAllByText("$142.18");
    expect(outlineProblems(outline())).toEqual([]);
  });

  it("the signed-in Requests page is 'Your requests', with a clean outline", async () => {
    readHub = async () => HUB;
    portal("/pine-hill/portal/requests", "/:tenant/portal/requests", <RequestsView />);
    // The head is drawn on the loading branch and again once the hub arrives;
    // wait for the cards so the outline read is the loaded page's.
    await screen.findAllByRole("heading", { level: 2 }, { timeout: 4000 });
    expect(screen.getByRole("heading", { level: 1, name: "Your requests" })).toBeInTheDocument();
    expect(outlineProblems(outline())).toEqual([]);
  });

  it("no two pages share an h1: the front page and Requests differ in all eleven catalogues", () => {
    for (const file of readdirSync(LOCALES).filter((f) => f.endsWith(".json"))) {
      const catalogue = JSON.parse(readFileSync(join(LOCALES, file), "utf8")) as Record<string, string>;
      expect(catalogue["portal.requests.title"], file).not.toBe(catalogue["portal.front.title"]);
      expect(catalogue["portal.home.pageTitle"], file).toBeTruthy();
    }
  });
});

describe("F-12 / F-14 · every control is named, and a placeholder is a status (DEF-CWP-10564, DEF-CWP-10565)", () => {
  it("Home's bill-month chooser is named 'Bill month'", async () => {
    readHome = async () => ({ ...HOME, recent_bills: [BILL("BL-2608-0141", "2026-08-26"), BILL("BL-2607-0120", "2026-07-26")] });
    portal("/pine-hill/portal/home", "/:tenant/portal/home", <HomeView today={new Date("2026-09-02T00:00:00Z")} />);
    expect(await screen.findByRole("combobox", { name: "Bill month" })).toBeInTheDocument();
    expect(unnamedControls()).toEqual([]);
  });

  it("the loading placeholder is role=status, so its name is allowed and heard", () => {
    const { container } = render(<LoadingSkeleton variant="card" />);
    const box = container.firstElementChild as HTMLElement;
    expect(box.getAttribute("role")).toBe("status");
    expect(box.getAttribute("aria-label")).toBeTruthy();
  });
});

describe("F-23 · a link's name says where it goes (DEF-CWP-10566)", () => {
  it("each card's 'Start →' is named for its card, with the visible words unchanged", () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/pine-hill/portal"]}>
          <Routes>
            <Route
              path="/:tenant/portal"
              element={
                <>
                  <ErrandCard cardKey="a" title="Pay a bill" description="d" action={<ErrandLink label="Start →" to="/pay" />} />
                  <ErrandCard cardKey="b" title="Report a problem" description="d" action={<ErrandLink label="Start →" to="/report" />} />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const pay = screen.getByRole("link", { name: "Start: Pay a bill" });
    expect(pay).toHaveTextContent("Start →");
    expect(pay.getAttribute("href")).toBe("/pine-hill/portal/pay");
    expect(screen.getByRole("link", { name: "Start: Report a problem" })).toBeInTheDocument();
    expect(sharedLinkNames()).toEqual([]);
  });

  it("the front page has no two links of one name going to different places", async () => {
    portal("/pine-hill/portal", "/:tenant/portal", <FrontPage />);
    await screen.findByRole("heading", { level: 1 });
    expect(sharedLinkNames()).toEqual([]);
    expect(outlineProblems(outline())).toEqual([]);
  });

  it("the Requests page has no two links of one name going to different places", async () => {
    readHub = async () => HUB;
    portal("/pine-hill/portal/requests", "/:tenant/portal/requests", <RequestsView />);
    await screen.findByRole("heading", { level: 1 });
    expect(sharedLinkNames()).toEqual([]);
  });
});

describe("F-24 · quick pay goes to /pay from every page (DEF-CWP-10567)", () => {
  it("the sign-in page's 'Pay with a bill number →' opens Pay", () => {
    render(
      <MemoryRouter initialEntries={["/pine-hill/portal/sign-in"]}>
        <Routes>
          <Route path="/:tenant/portal/sign-in" element={<FrontDoorView front={FRONT} />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: /bill number/ }).getAttribute("href")).toBe("/pine-hill/portal/pay");
  });

  it("no source file sends the quick-pay words anywhere but /pay", () => {
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.tsx$/.test(name) && !/\.test\.tsx$/.test(name)) {
          const lines = readFileSync(path, "utf8").split("\n");
          lines.forEach((line, i) => {
            if (!line.includes("doorQuickPay")) return;
            // the destination is on the same line (a door object) or within the six lines above it (a <Link>)
            const near = lines.slice(Math.max(0, i - 6), i + 1).join("\n");
            const to = /to[=:]\s*\{?\s*(?:path\()?"([^"]+)"/g;
            const found = [...near.matchAll(to)].map((m) => m[1]);
            if (found.length === 0 || found[found.length - 1] !== "/pay") offenders.push(`${path}:${i + 1} → ${found.join(",") || "?"}`);
          });
        }
      }
    };
    walk(join(SRC, "portal"));
    expect(offenders).toEqual([]);
  });

  it("one name per function, the longer one", () => {
    for (const file of readdirSync(LOCALES).filter((f) => f.endsWith(".json"))) {
      const c = JSON.parse(readFileSync(join(LOCALES, file), "utf8")) as Record<string, string>;
      expect(c["portal.home.askForPlan"], file).toBe(c["portal.overdue.askForAPlan"]);
    }
    const account = readFileSync(join(SRC, "portal/accounts/YourAccount.tsx"), "utf8");
    expect(account).toMatch(/key: "equipment", label: t\("portal\.usage\.seeEquipment"\)/);
  });
});

// ── fixtures ────────────────────────────────────────────────────────────────
function BILL(number: string, issued: string) {
  return {
    number,
    issued_on: issued,
    due_on: "2026-09-14",
    total: "142.1800",
    currency: "USD",
    period_start: "2026-07-27",
    period_end: issued,
    owing: "142.1800",
    state: "due",
    usage: [{ quantity_display: "4820", unit: "gal" }],
  };
}

const HOME = {
  as_of: "2026-09-02",
  balances: {
    as_of: "2026-09-02",
    account_count: 1,
    total_owing: "142.1800",
    currency: "USD",
    problems: [],
    accounts: [
      {
        account_id: "a1",
        owing: "142.1800",
        bills_open: "142.1800",
        credit_held: "0.0000",
        currency: "USD",
        due_on: "2026-09-14",
        open_bill_count: 1,
        problems: [],
      },
    ],
  },
  last_bill: null,
  last_payment: null,
  usage: [],
  usage_series: [],
  recent_bills: [],
  service: {
    address: { value: null, varies: false },
    plan: { value: null, varies: false },
    billed: { value: null, varies: false },
    paperless: { value: null, varies: false },
  },
  identity: {
    name: { value: null, varies: false },
    status: { value: null, varies: false },
    status_class: { value: null, varies: false },
    services: [],
    equipment: [],
    phone: null,
    phone_varies: false,
    email: null,
    email_varies: false,
  },
  attention: [],
  tip: null,
} as unknown as PortalHome;

const HUB = {
  errands: [
    { code: "move_out", label: "portal.errand.move_out.title", hint: "portal.errand.move_out.hint", to: null, held_reason: "not_online_yet" },
    { code: "stop_for_a_while", label: "portal.errand.stop_for_a_while.title", hint: "portal.errand.stop_for_a_while.hint", to: "/stop-or-restart", held_reason: null },
    { code: "report_problem", label: "portal.errand.report_problem.title", hint: "portal.errand.report_problem.hint", to: "/report", held_reason: null },
    { code: "something_else", label: "portal.errand.something_else.title", hint: "portal.errand.something_else.hint", to: "/ask-a-question", held_reason: null },
  ],
  open_requests: [],
  closed_requests: [],
  lists_only_portal_requests: true,
} as unknown as PortalRequestHub;
