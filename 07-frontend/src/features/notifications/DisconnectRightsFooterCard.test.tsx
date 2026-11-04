// ── Trace ──────────────────────────────────────────────
// Story:    CR-007 (the disconnect notices — the platform writes the defaults,
//           PO ruling 2026-08-17)   Screens: S8 (Settings → Notifications)
// Rules:    BR-NOT-015 (a PLATFORM DEFAULT, VISIBLY MARKED as one, overridable
//           by a System Admin) · BR-NOT-014 (it prints on all three tiers) ·
//           BR-SHL-025 (a forbidden control renders DISABLED with its reason)
// ───────────────────────────────────────────────────────
// The assertions worth the file, in the order they would break:
//
//   1. **The "this is a default, not legal advice" notice is ON THE SCREEN.**
//      This is the one thing CR-007 said may not be softened. It is the server's
//      sentence and the card renders it verbatim, above the clauses, not in a
//      tooltip — because it is the reason a System Admin is on this card.
//   2. **Every untouched clause is BADGED as the platform's**, and a replaced
//      one is badged as the utility's. A screen where the two look alike is a
//      screen where a utility signs off wording it thinks its own regulator
//      wrote.
//   3. **A clause that is OFF says so, and its text is not presented as live.**
//      The tick box is the PO's own answer to "a utility in a state with no
//      weather rule"; a switched-off clause that still read as printed would
//      make the box meaningless.
//   4. **"Restore the platform default" appears only where there is something
//      to restore.** A button that does nothing teaches a person to distrust
//      the ones that do.
//
// No DOM library is in package.json, so these assert on react-dom/server static
// markup — real render output, no new dependency (the idiom StateFrame.test.tsx
// established and TemplateCatalog.test.tsx follows).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import type { DisconnectRightsFooter, RightsClause } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { DisconnectRightsFooterCard, clauseSaveBlockedReason } from "./DisconnectRightsFooterCard";

/** The server's own sentence, quoted. If `rights_footer.PLATFORM_DEFAULT_NOTICE`
 *  changes, this string is stale and the backend test that asserts its three
 *  clauses is the one that fires — this file only proves it REACHES the page. */
const PLATFORM_NOTICE =
  "These five clauses are wording SMART360 Next provides as a starting point. They are " +
  "not legal advice and they are not your regulator's words: disconnection rules differ " +
  "by state and by utility. Review each clause against your own commission's " +
  "requirements — and edit or switch off whatever does not match them — before any " +
  'disconnection notice goes out. A clause you have not changed is shown as "platform default".';

const PLATFORM_LABEL = "Platform default — review against your own commission";
const TENANT_LABEL = "Your wording";

const READ_ONLY_REASON =
  "Only a System Admin can change these clauses. They are the text telling a customer " +
  "their legal rights before their service is cut off, so the edit is restricted and " +
  "every change is recorded (BR-NOT-015).";

function aClause(overrides: Partial<RightsClause> = {}): RightsClause {
  return {
    code: "weather_suppression",
    title: "Weather",
    purpose: "States the temperature limits on disconnection.",
    text: "We do not disconnect service on a day when the forecast temperature for your service address is below 32°F or above 100°F.",
    enabled: true,
    is_default: true,
    default_text:
      "We do not disconnect service on a day when the forecast temperature for your service address is below 32°F or above 100°F.",
    source_label: PLATFORM_LABEL,
    ...overrides,
  };
}

function aFooter(overrides: Partial<DisconnectRightsFooter> = {}): DisconnectRightsFooter {
  return {
    clauses: [
      aClause({ code: "dispute_rights", title: "If you think this bill is wrong" }),
      aClause(),
    ],
    platform_default_notice: PLATFORM_NOTICE,
    tenant_wording_notice:
      "This clause has been replaced with your own wording. SMART360 Next's default is " +
      "still available and restoring it is one click.",
    prints_on: [
      { code: "disconnect_notice_10_day", name: "Disconnect notice · 10-day warning" },
      { code: "disconnect_notice_5_day", name: "Disconnect notice · 5-day final reminder" },
      { code: "disconnect_notice_48_hour", name: "Disconnect notice · 48-hour certified" },
    ],
    merge_fields: ["{account_no}", "{support_email}", "{support_phone}"],
    merge_fields_reason: "One footer prints on all three disconnection notices.",
    can_edit: true,
    cannot_edit_reason: null,
    ...overrides,
  };
}

/** A client that answers the ONE read this card makes. Nothing else is stubbed:
 *  a card that quietly called a second endpoint would fail here rather than in
 *  a browser. */
function clientFor(footer: DisconnectRightsFooter): ApiClient {
  return {
    get: async () => ({ data: footer, error: null }),
    patch: async () => ({ data: footer, error: null }),
    post: async () => ({ data: footer, error: null }),
    put: async () => ({ data: footer, error: null }),
    delete: async () => ({ data: footer, error: null }),
  } as unknown as ApiClient;
}

async function markup(footer: DisconnectRightsFooter, readOnly = false): Promise<string> {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // Prime the cache so the static render has data — `renderToStaticMarkup` does
  // not await suspense, and asserting on a loading skeleton would assert
  // nothing.
  await queryClient.prefetchQuery({
    queryKey: ["notifications", "rights-footer"],
    queryFn: () => Promise.resolve(footer),
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <DisconnectRightsFooterCard
          client={clientFor(footer)}
          readOnly={readOnly}
          // A stub that keeps the INTERPOLATED VALUES rather than dropping
          // them: half of what this card says comes from the server and arrives
          // through `t(key, {…})`, so a stub returning the bare key would hide
          // exactly the content worth asserting.
          t={
            ((key: string, vars?: Record<string, unknown>) =>
              vars === undefined ? key : `${key} ${Object.values(vars).join(" ")}`) as never
          }
          onRefusal={() => undefined}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-007 · the rights footer never lets a default pass for a regulator's words", () => {
  it("prints the platform-default notice on the card, in the server's own words", async () => {
    const html = await markup(aFooter());
    expect(html).toContain("not legal advice");
    expect(html).toContain("starting point");
    expect(html).toContain("before any disconnection notice goes out");
  });

  it("badges an untouched clause as the platform's and a replaced one as the utility's", async () => {
    const html = await markup(
      aFooter({
        clauses: [
          aClause(),
          aClause({
            code: "dispute_rights",
            title: "If you think this bill is wrong",
            text: "Call us within ten days.",
            is_default: false,
            source_label: TENANT_LABEL,
          }),
        ],
      }),
    );
    expect(html).toContain(PLATFORM_LABEL);
    expect(html).toContain(TENANT_LABEL);
  });

  it("names the three letters the clauses print on", async () => {
    const html = await markup(aFooter());
    expect(html).toContain("10-day warning");
    expect(html).toContain("5-day final reminder");
    expect(html).toContain("48-hour certified");
  });

  it("says a switched-off clause is not printed, rather than leaving it looking live", async () => {
    const html = await markup(
      aFooter({ clauses: [aClause({ enabled: false })] }),
    );
    expect(html).toContain("rights-off-weather_suppression");
    expect(html).toContain("notifications.rights.switchedOff");
  });

  it("offers Restore only where there is something to restore", async () => {
    const platform = await markup(aFooter({ clauses: [aClause()] }));
    expect(platform).not.toContain("rights-restore-weather_suppression");

    const overridden = await markup(
      aFooter({
        clauses: [aClause({ is_default: false, source_label: TENANT_LABEL, text: "Ours." })],
      }),
    );
    expect(overridden).toContain("rights-restore-weather_suppression");
  });

  it("renders every control DISABLED with its reason for a clerk, never hidden", async () => {
    // BR-SHL-025. A Billing Clerk must still be able to READ what their
    // utility's customers are told before their service is cut off.
    const html = await markup(
      aFooter({ can_edit: false, cannot_edit_reason: READ_ONLY_REASON }),
    );
    expect(html).toContain("Only a System Admin can change these clauses");
    expect(html).toContain("rights-edit-weather_suppression");
    expect(html).toContain("disabled");
    // …and the wording itself is on the page for them to read.
    expect(html).toContain("32°F");
  });
});

describe("CR-007 · when the Save control may fire, and why not when it may not", () => {
  const footer = aFooter();

  it("refuses a save for a role that may not edit, with the server's reason", () => {
    const denied = aFooter({ can_edit: false, cannot_edit_reason: READ_ONLY_REASON });
    expect(clauseSaveBlockedReason(denied, "anything", "before")).toBe(READ_ONLY_REASON);
  });

  it("refuses a blank clause — OFF is what the tick box is for", () => {
    expect(clauseSaveBlockedReason(footer, "   ", "before")).toBe("TICK_BOX_NOT_BLANK");
  });

  it("refuses a save that changes nothing", () => {
    expect(clauseSaveBlockedReason(footer, "same", "same")).toBe("NO_CHANGE");
  });

  it("allows a real change", () => {
    expect(clauseSaveBlockedReason(footer, "our own wording", "theirs")).toBeNull();
  });
});
