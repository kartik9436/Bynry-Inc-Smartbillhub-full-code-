// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-010 (EP-IDN-04 §Stories)  Screens: S8 (Settings → Security)
// Rules:    BR-IDN-019 (one tenant record; System Admin edits, Executive views) ·
//           BR-IDN-020 (IPv4 CIDR allowlist; self-lockout guard is the SERVER's) ·
//           BR-IDN-025/BR-IDN-026 (seed defaults) · BR-IDN-028 (NO 2FA section on the v1 tab)
// ───────────────────────────────────────────────────────
// §4 test data: Silver Creek's seed policy — min 8 · upper/lower/number on ·
// symbol off · expiry Never · timeout 60 min · allowlist empty. IPs from
// TEST-NET: admin 203.0.113.7 · outside 192.0.2.44.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { SecurityPolicy } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { RefusalNotice, refusalOf } from "@/features/tenancy/settingsShared";

import {
  SecurityTab,
  draftFromPolicy,
  durationLabel,
  invalidCidrs,
  parseAllowlist,
  securityChanges,
  securityIsDirty,
} from "./SettingsSecurityTab";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// BR-IDN-025/026 seed defaults, exactly as the server returns them when no row
// exists yet — this screen holds no second copy of them.
const SEED: SecurityPolicy = {
  pw_min_length: 8,
  pw_require_mixed: true,
  pw_require_symbol: false,
  pw_expiry_days: null,
  session_timeout_minutes: 60,
  ip_allowlist: [],
  // CR-145-BRC08 — every default equals what the product did when these were
  // platform constants, which is the ruling's own promise: nothing a person
  // reads on this tab moves on the day it ships.
  absolute_session_hours: 12,
  keep_signed_in_offered: true,
  keep_signed_in_days: 30,
  lockout_max_failed: 5,
  lockout_minutes: 15,
  field_capture_hours: 168, // PO 2026-10-21 — the field app's capture life, hours
  password_link_valid_days: 7, // CR-188-BRC10 — an emailed sign-in link's life, days
  // The server's own `SETTING_LIMITS`, field for field — EIGHT entries since
  // `DEF-IDN-7501` closed, the two password rows included.
  limits: {
    // Published, not changed: the values the server always enforced.
    pw_min_length: { choices: [8, 10, 12], default: 8 },
    pw_expiry_days: { choices: [null, 90, 180], default: null },
    // ⚠ 240 AND 480 ARE GONE AND 15 AND 45 ARE NEW (PO 2026-09-28).
    session_timeout_minutes: { choices: [15, 30, 45, 60], default: 60 },
    absolute_session_hours: { min: 4, max: 12, default: 12 },
    keep_signed_in_offered: { boolean: true, default: true },
    keep_signed_in_days: { min: 1, max: 30, default: 30 },
    lockout_max_failed: { min: 3, max: 10, default: 5 },
    lockout_minutes: { min: 5, max: 60, default: 15 },
    field_capture_hours: { choices: [1, 12, 24, 36, 48, 72, 168, 336, 720], default: 168 },
    password_link_valid_days: { choices: [1, 2, 3, 7, 14], default: 7 },
  },
};

/** The utility this screen belongs to — S8 lives at `/{tenant}/settings/security`. */
const TENANT = "silvercreek";

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, AND THAT IS NOT DECORATION.** This
 * fixture used a bare `MemoryRouter` with no `/:tenant` route, so
 * `useParams().tenant` was `undefined` and every address this screen builds
 * came out `//settings/…` — a protocol-relative URL to another host, which
 * reads as a perfectly good string to `toContain`. That is the exact fixture
 * that hid the customer portal's dead front page (CLAUDE.md hard-won law 2):
 * a mount that cannot tell a working link from a broken one makes the one
 * assertion that would catch it impossible to write. Nothing in this file
 * asserts an address today; the point is that the day something does, the
 * fixture will not be lying underneath it.
 */
function renderTab(policy: SecurityPolicy, readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.securityPolicy, policy);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/settings/security`]}>
          <Routes>
            <Route
              path="/:tenant/settings/security"
              // CR-155-BRC09: the Audit log card renders an instant through
              // `DateCell`, which REQUIRES a zone and a format (BR-SHL-034).
              // Named here rather than left to the seed fallback, so this
              // fixture says which tenant it is testing.
              element={<SecurityTab readOnly={readOnly} timeZone="UTC" dateFormat="DD-MMM-YY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-IDN-010 — configure tenant security policy", () => {
  it("US-IDN-010 TC-2: a fresh tenant renders the seed defaults, and NO 2FA section exists (BR-IDN-028)", () => {
    const html = renderTab(SEED);
    expect(html).toContain("Minimum length");
    expect(html).toContain('value="8"');
    expect(html).toContain("Require upper, lower &amp; number");
    expect(html).toContain("Never");
    expect(html).toContain("1 hour");
    // BR-IDN-028: not disabled, not hidden — absent.
    expect(html).not.toContain("2FA");
    expect(html).not.toContain("two-factor");
    expect(html).not.toContain("Two-factor");
    // CR-145-BRC08 TC-2 as amended: five more controls, every one of them at
    // the value this case already asserted when they were platform constants.
    expect(html).toContain("Hard limit");
    expect(html).toContain('value="12"');
    expect(html).toContain("Stay signed in");
    // CR-155-BRC09: the tick box is named for the words a clerk sees on the
    // sign-in screen. "Offer on sign-in" was three words that did not say
    // WHAT is offered, and its neighbour "Days" said even less.
    expect(html).toContain("Offer “Stay signed in”");
    expect(html).toContain("Stay signed in for");
    expect(html).toContain('value="30"');
    expect(html).toContain("Wrong passwords");
    expect(html).toContain('value="5"');
    expect(html).toContain("Lockout length");
    expect(html).toContain('value="15"');
    // The ranges are the SERVER's numbers, stated as facts beside the controls.
    expect(html).toContain("Between 4 and 12 hours.");
    expect(html).toContain("Between 1 and 30 days.");
    expect(html).toContain("Between 3 and 10 tries.");
    expect(html).toContain("Between 5 and 60 minutes.");
  });

  // ── F2: the screen holds no hand-typed list any more ─────────────────────
  //
  // ⚠ **THIS IS THE ONE CASE THAT WOULD HAVE CAUGHT THE DEFECT `CR-145` EXISTS
  // TO REMOVE, AND ASSERTING THE CHOICES ONCE CANNOT.** A tab with
  // `SESSION_TIMEOUT_OPTIONS = [30, 60, 240, 480]` typed into it passes any
  // test that renders one fixture and finds "30 minutes" — the old suite did
  // exactly that, and was green over a screen that could never offer 15. The
  // only proof a list is DERIVED is that the screen FOLLOWS A DIFFERENT ONE, so
  // this renders a second server whose limits are deliberately unlike the
  // first's and requires the offered values to move with them.
  it("CR-145-BRC08 F2: every dropdown follows the server's limits, and the tab holds no copy", () => {
    const seeded = renderTab(SEED);
    expect(seeded).toContain("15 minutes");
    expect(seeded).toContain("45 minutes");
    expect(seeded).toContain("1 hour");
    // The two the PO withdrew are not offered any more.
    expect(seeded).not.toContain("4 hours");
    expect(seeded).not.toContain("8 hours");

    const elsewhere = renderTab({
      ...SEED,
      session_timeout_minutes: 20,
      limits: {
        ...SEED.limits,
        session_timeout_minutes: { choices: [20, 120], default: 20 },
        lockout_minutes: { min: 2, max: 9, default: 5 },
      },
    });
    // Values this file has never heard of, offered because the server said so.
    expect(elsewhere).toContain("20 minutes");
    expect(elsewhere).toContain("2 hours");
    expect(elsewhere).toContain("Between 2 and 9 minutes.");
    // And the seeded set is genuinely absent, so the two fixtures cannot both
    // be passing because the screen prints everything it has ever been given.
    expect(elsewhere).not.toContain("15 minutes");
    expect(elsewhere).not.toContain("45 minutes");
    expect(elsewhere).not.toContain("Between 5 and 60 minutes.");
  });

  // ⚠ THE TWO PASSWORD DROPDOWNS, NOW SERVER-DRIVEN LIKE EVERY OTHER ONE
  // (`DEF-IDN-7501` CLOSED). This case used to assert the OPPOSITE — that the
  // tab kept its own `[8, 10, 12]` and `[null, 90, 180]` — and it was written
  // as the row that says what to delete the day `SETTING_LIMITS` grew the two
  // entries. It has grown them, so this is that day.
  //
  // ⚠ **THE SECOND SERVER IS THE WHOLE POINT, FOR THE REASON THE F2 CASE ABOVE
  // GIVES.** Asserting `8` and `Every 90 days` against the seeded fixture
  // passes just as happily with the literals restored, because the literals
  // held exactly those values. Only a server offering something this file has
  // never contained can tell a derived list from a copied one.
  it("CR-145-BRC08 / DEF-IDN-7501: the password dropdowns follow the server too", () => {
    // Every entry the server publishes, and the two password rows are in it.
    expect(Object.keys(SEED.limits).sort()).toEqual([
      "absolute_session_hours",
      "field_capture_hours",
      "keep_signed_in_days",
      "keep_signed_in_offered",
      "lockout_max_failed",
      "lockout_minutes",
      "password_link_valid_days", // CR-188-BRC10 (2026-10-22)
      "pw_expiry_days",
      "pw_min_length",
      "session_timeout_minutes",
    ]);

    const seeded = renderTab(SEED);
    expect(seeded).toContain('value="8"');
    expect(seeded).toContain("Every 90 days");
    expect(seeded).toContain("Every 180 days");

    // A utility whose server allows a 14-character minimum and a one-year
    // expiry. Neither number has ever been written in the tab, so a restored
    // literal cannot produce them.
    const elsewhere = renderTab({
      ...SEED,
      pw_min_length: 14,
      pw_expiry_days: 365,
      limits: {
        ...SEED.limits,
        pw_min_length: { choices: [14, 16], default: 14 },
        pw_expiry_days: { choices: [null, 365], default: null },
      },
    });
    expect(elsewhere).toContain('value="14"');
    expect(elsewhere).toContain('value="16"');
    expect(elsewhere).toContain("Every 365 days");
    // And the seeded set is genuinely gone, so the two fixtures cannot both be
    // passing because the screen prints everything it was ever given.
    expect(elsewhere).not.toContain('value="10"');
    expect(elsewhere).not.toContain("Every 90 days");
    expect(elsewhere).not.toContain("Every 180 days");
  });

  // PO 2026-10-21, *"this should come from settings"* — the field app's capture
  // life is the utility's own, on this tab, from the server's list (hours on
  // the wire, named in days where whole). A second server proves it is derived.
  it("CR-187-BRC10: the field app's capture life is a dropdown the server publishes", () => {
    const seeded = renderTab(SEED);
    expect(seeded).toContain("Field app sign-in");
    expect(seeded).toContain('id="field_capture_hours"');
    expect(seeded).toContain("7 days");
    expect(seeded).toContain("36 hours");
    expect(seeded).toContain("30 days");

    const elsewhere = renderTab({
      ...SEED,
      field_capture_hours: 6,
      limits: { ...SEED.limits, field_capture_hours: { choices: [6, 240], default: 6 } },
    });
    expect(elsewhere).toContain("6 hours");
    expect(elsewhere).toContain("10 days");
    expect(elsewhere).not.toContain("36 hours");

    const original = draftFromPolicy(SEED);
    expect(original.field_capture_hours).toBe("168");
    expect(securityChanges({ ...original, field_capture_hours: "36" }, original)).toEqual({
      field_capture_hours: 36,
    });
  });

  it("CR-145-BRC08 F2: a duration is named from the number, not from a key per value", () => {
    // Reproduces every string the four retired `settings.security.timeout.*`
    // keys used to hold — that equivalence is why they could be deleted.
    expect(durationLabel(30, t)).toBe("30 minutes");
    expect(durationLabel(60, t)).toBe("1 hour");
    expect(durationLabel(240, t)).toBe("4 hours");
    expect(durationLabel(480, t)).toBe("8 hours");
    // And the two the old keys could not have named at all.
    expect(durationLabel(15, t)).toBe("15 minutes");
    expect(durationLabel(45, t)).toBe("45 minutes");
  });

  it("CR-145-BRC08 F1: the five new settings are diffed and sent, and a cleared box sends nothing", () => {
    const original = draftFromPolicy(SEED);
    expect(securityChanges(original, original)).toEqual({});
    expect(securityChanges({ ...original, lockout_max_failed: "3" }, original)).toEqual({
      lockout_max_failed: 3,
    });
    expect(securityChanges({ ...original, absolute_session_hours: "4" }, original)).toEqual({
      absolute_session_hours: 4,
    });
    expect(securityChanges({ ...original, keep_signed_in_days: "1" }, original)).toEqual({
      keep_signed_in_days: 1,
    });
    expect(securityChanges({ ...original, keep_signed_in_offered: false }, original)).toEqual({
      keep_signed_in_offered: false,
    });
    // ⚠ An empty box is NOT a zero. `Number("")` is 0, which is inside no range
    // and would be refused with a sentence about a number nobody typed.
    expect(securityChanges({ ...original, lockout_minutes: "" }, original)).toEqual({});
    expect(securityIsDirty({ ...original, lockout_minutes: "60" }, original)).toBe(true);
  });

  it("US-IDN-010 TC-1: only the changed fields are sent, with Never mapped to null", () => {
    const original = draftFromPolicy(SEED);
    expect(securityIsDirty(original, original)).toBe(false);
    expect(securityChanges(original, original)).toEqual({});
    expect(securityChanges({ ...original, pw_min_length: "10" }, original)).toEqual({
      pw_min_length: 10,
    });
    expect(securityChanges({ ...original, pw_require_symbol: true }, original)).toEqual({
      pw_require_symbol: true,
    });
    expect(securityChanges({ ...original, pw_expiry_days: "90" }, original)).toEqual({
      pw_expiry_days: 90,
    });
    const with90 = draftFromPolicy({ ...SEED, pw_expiry_days: 90 });
    expect(securityChanges({ ...with90, pw_expiry_days: "" }, with90)).toEqual({
      pw_expiry_days: null,
    });
  });

  it("US-IDN-010 TC-4 (neg): a malformed CIDR is refused inline and nothing is posted", () => {
    expect(invalidCidrs("")).toEqual([]);
    expect(invalidCidrs("203.0.113.0/24")).toEqual([]);
    expect(invalidCidrs("203.0.113.0/24, 198.51.100.0/24")).toEqual([]);
    // The story's own bad input.
    expect(invalidCidrs("203.0.113.0/33, banana")).toEqual(["203.0.113.0/33", "banana"]);
    expect(invalidCidrs("999.0.113.0/24")).toEqual(["999.0.113.0/24"]);
    // Empty means UNRESTRICTED — not "no addresses allowed".
    expect(parseAllowlist("")).toEqual([]);
    expect(parseAllowlist(" 203.0.113.0/24 ,, 198.51.100.0/24 ")).toEqual([
      "203.0.113.0/24",
      "198.51.100.0/24",
    ]);
    expect(t("settings.security.badCidr", { value: "banana" })).toContain("Nothing was saved.");
  });

  it("US-IDN-010 TC-5 (neg): the self-lockout guard is the SERVER's verdict, rendered with the IP it saw", () => {
    const locked = new ApiError(409, {
      code: "BIZ-STATE",
      message_key: "errors.identity.allowlist_self_lockout",
      params: { ip: "203.0.113.7" },
      br_ref: "BR-IDN-020",
    });
    const refusal = refusalOf(locked, t);
    expect(refusal.message).toBe(
      // Shortened to the 12-word rule, PO 2026-08-19 (decision log `6baa846`).
      "Your address 203.0.113.7 is outside those ranges, so nothing was saved.",
    );
    expect(refusal.brRef).toBe("BR-IDN-020");
    const html = renderToStaticMarkup(<RefusalNotice refusal={refusal} />);
    expect(html).toContain("203.0.113.7");
    expect(html).toContain("nothing was saved.");
    // The screen warns before the attempt, because it cannot know its own IP.
    // ⚠ **AND THE STANDING WARNING IS GONE FROM THE SCREEN — CR-155-BRC09.**
    // This asserted that *"The save is refused if your own address is not
    // inside the ranges you enter."* was rendered BEFORE any attempt. Fifteen
    // words explaining why the product may refuse is RATIONALE, which B14
    // rule 33 puts at zero words on screen, and the PO-approved 2026-09-29
    // drawing does not draw it. The guarantee did not move an inch: the
    // refusal above still renders, with the IP the server saw, at the moment
    // it happens. Asserted as an ABSENCE so a lane cannot put it back by
    // accident and call that a fix.
    expect(renderTab(SEED)).not.toContain("if your own address is not inside the ranges you enter");
  });

  it("US-IDN-010 TC-7 (neg): an Executive gets the whole tab read-only, with the reason named", () => {
    const html = renderTab(SEED, true);
    expect(html).toContain(
      "Executives can view security settings; only a System Admin can change them.",
    );
    expect(html).toContain("disabled");
  });

  it("US-IDN-010 TC-10 / OQ-029 CLOSED: the audit panel routes to the tenant-scoped viewer", () => {
    const html = renderTab(SEED);
    // CR-155-BRC09: the card replaced the button, and `View all →` is the
    // door. Asserted as the WHOLE tenant-scoped address — which only the real
    // route pattern in `renderTab` makes possible, and which is the first
    // assertion in this file to use it. A bare `MemoryRouter` produced
    // `href="/audit-log"` with no tenant in it and `toContain` was happy.
    expect(html).toContain("View all →");
    expect(html).toContain(`href="/${TENANT}/audit-log"`);
    // The old panel's sentence explained what an audit log IS. The card shows
    // one instead (B14 rule 33: rationale is removed, never shortened).
    expect(html).not.toContain("actor, timestamp and before/after");
    expect(html).toContain("The last five changes on this tab.");
  });

  // ⚠ RENAMED AND REWRITTEN BY `CR-145-BRC08`. Its old name — *"the
  // platform-fixed values are STATED, so their absence is not read as an
  // omission"* — is the part that went stale hardest, because THREE OF THE FOUR
  // STOPPED BEING PLATFORM-FIXED and the case would have gone on defending the
  // sentence that said they were. The two that really are still fixed keep
  // their half of it, and that is why the sentence is rewritten and not
  // deleted: it is the only place a clerk is told those two are not settings.
  it("CR-145-BRC08: the card states the TWO facts that are still fixed, and none of the three that moved", () => {
    const html = renderTab(SEED);
    // Still true, still the only statement of it on any screen.
    expect(html).toContain("The last 5 passwords are blocked.");
    expect(html).toContain("A temporary password lasts 7 days.");
    // ⚠ The three that became settings, each asserted ABSENT by the sentence
    // that used to carry it — a control on this very screen now decides them.
    expect(html).not.toContain("5 failed sign-ins lock the account for 15 minutes");
    expect(html).not.toContain("every session ends after 12 hours");
    // ⚠ And the framing that made it actively misleading: an admin reading
    // "Fixed for every utility" does not go looking for a control that is now
    // on the same screen. It is rationale as well, which B14 rule 33 puts at
    // zero words on screen.
    expect(html).not.toContain("Fixed for every utility");
  });

  it.todo(
    "US-IDN-010 TC-3/TC-6: the new timeout governs the next request and the allowlist gates sign-in — session/identity server scope",
  );
  it.todo("US-IDN-010 TC-8 (neg): a Billing Clerk gets A18 §6 — route/tab RBAC exercised in the frame suite");
  it.todo("US-IDN-010 TC-9 (isolation): per-tenant policy rows — server/RLS scope (G5)");
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-IDN-010@493ea2f (story+rules snapshot hash — EP-IDN-04)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
