// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  2026-10-22 — Settings → Notifications moved to Settings → Configure
//          → Notifications, next to Templates. PO, verbatim: *"Settings →
//          Configure → Notifications, sitting next to Templates - this is
//          correct understanding"*; and of the bell, *"B. Setup stays in one
//          place, and clerks can still reach failed messages in one click from
//          the bell."* (decision log 2026-10-22, three entries)
// Rules:   BR-SHL-011 (every stateful surface has a URL) · hard-won law 2 (a
//          moved screen and the door that points at it are two acts)
// ───────────────────────────────────────────────────────
// ⚠ ONE ROUTED TEST PER OLD ADDRESS. Each case (1) finds the route in the REAL
// route table (`APP_ROUTES`), so a lane that drops the redirect goes red here,
// and (2) mounts that route's own element under the real path pattern and
// reads where the browser ends up — the address, not a string that looks like
// one.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import { BELL_MESSAGES_PATH } from "@/components/AppShell";

import {
  CONFIGURE_SUB_TABS,
  CONFIGURE_TAB,
  LEGACY_SETTINGS_TAB_PATHS,
  LegacyNotificationsRedirect,
  LegacySettingsTabRedirect,
  MESSAGES_NEEDING_ATTENTION_PATH,
  SETTINGS_TABS,
} from "./SettingsPage";

const TENANT = "springfield";

afterEach(() => {
  cleanup();
});

function flatten(
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
      out.push(...flatten(route.children, here));
    }
  }
  return out;
}

function routeAt(pattern: string): RouteObject {
  const found = flatten(APP_ROUTES).find((one) => one.path === pattern);
  expect(found, `no route ${pattern} in App.tsx`).toBeDefined();
  return found!.route;
}

function Where() {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
}

/** Mount the REAL route's element under its real pattern and report the landing. */
function landing(pattern: string, address: string): string {
  const route = routeAt(pattern);
  render(
    <MemoryRouter initialEntries={[`/${TENANT}${address}`]}>
      <Routes>
        <Route path={pattern} element={route.element} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
  return screen.getByTestId("where").textContent ?? "";
}

describe("Settings' rows: Notifications sits in Configure, next to Templates", () => {
  it("the top row has no Notifications tab", () => {
    expect(SETTINGS_TABS.map((tab) => tab.id)).not.toContain("notifications");
  });

  it("Configure reads Reference data · Routes & Cycles · Numbering · Templates · Notifications · Customer portal", () => {
    expect(CONFIGURE_SUB_TABS.map((sub) => sub.id)).toEqual([
      "reference-data",
      "routes-cycles",
      "number-series",
      "templates",
      "notifications",
      "customer-portal",
    ]);
  });

  it("Configure → Notifications' own segment is a routed SettingsPage", () => {
    const route = routeAt("/:tenant/settings/reference-data/notifications/:segment");
    expect((route.element as { props: { configureSub?: string } }).props.configureSub).toBe(
      "notifications",
    );
  });
});

describe("every old /settings/notifications address lands on its new home", () => {
  it("/settings/notifications → Configure → Notifications", () => {
    const route = routeAt("/:tenant/settings/notifications");
    expect((route.element as { type: unknown }).type).toBe(LegacySettingsTabRedirect);
    expect(LEGACY_SETTINGS_TAB_PATHS.notifications).toBe(
      `/settings/${CONFIGURE_TAB}/notifications`,
    );
    expect(landing("/:tenant/settings/notifications", "/settings/notifications")).toBe(
      `/${TENANT}/settings/reference-data/notifications`,
    );
  });

  it("/settings/notifications/messages → Messages needing attention", () => {
    const route = routeAt("/:tenant/settings/notifications/:sub");
    expect((route.element as { type: unknown }).type).toBe(LegacyNotificationsRedirect);
    expect(
      landing("/:tenant/settings/notifications/:sub", "/settings/notifications/messages"),
    ).toBe(`/${TENANT}/settings/reference-data/notifications/messages`);
  });

  it("/settings/notifications/blocked → Blocked addresses", () => {
    expect(landing("/:tenant/settings/notifications/:sub", "/settings/notifications/blocked")).toBe(
      `/${TENANT}/settings/reference-data/notifications/blocked`,
    );
  });

  it("/settings/notifications/<event key> → that rule page, one level down", () => {
    expect(
      landing("/:tenant/settings/notifications/:sub", "/settings/notifications/bill_ready"),
    ).toBe(`/${TENANT}/settings/reference-data/notifications/bill_ready`);
  });

  it("/settings/notifications/rights → the 10-day disconnection notice on Templates", () => {
    expect(landing("/:tenant/settings/notifications/:sub", "/settings/notifications/rights")).toBe(
      `/${TENANT}/settings/reference-data/templates?template=disconnect_notice_10_day`,
    );
  });

  it("/settings/notifications/sender → Connectors' Custom SMTP page", () => {
    expect(landing("/:tenant/settings/notifications/:sub", "/settings/notifications/sender")).toBe(
      `/${TENANT}/settings/integrations/email_smtp`,
    );
  });
});

describe("the bell opens Messages needing attention in one click", () => {
  it("its link is the Messages tab's own address, and that address is routed", () => {
    expect(BELL_MESSAGES_PATH).toBe(MESSAGES_NEEDING_ATTENTION_PATH);
    expect(BELL_MESSAGES_PATH).toBe("/settings/reference-data/notifications/messages");
    routeAt("/:tenant/settings/reference-data/notifications/:segment");
  });
});
