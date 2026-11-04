// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-004 · US-IDN-005 · US-IDN-006 · US-IDN-007 (EP-IDN-02 §Stories)
//           Screens: S8 (Settings → Users & roles)
// Rules:    BR-IDN-008 (3 predefined roles) · BR-IDN-011 (invited = temp password not yet changed) ·
//           BR-IDN-012 (deactivate keeps history) · BR-IDN-013 (last active System Admin is protected) ·
//           BR-IDN-014 (read-only A4 matrix) · BR-IDN-021/BR-IDN-022 (no invite email; password shown ONCE) ·
//           BR-IDN-025 (7-day temp password) · BR-IDN-030 (Remove = permanent deactivation)
// ───────────────────────────────────────────────────────
// §4 test data: Silver Creek — Alex Reed (System Admin, active), Priya Menon
// (Billing Clerk, active), Diana Chen (Executive, active), Marcus (invited,
// no name yet), Carla Ortiz (deactivated).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { Paginated, RolesMatrix, TenantUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { collectFormErrors } from "@/components/FormModal";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import { RefusalNotice, refusalOf } from "@/features/tenancy/settingsShared";

import {
  RolesMatrixPanel,
  TempPasswordPanel,
  UsersTab,
  actionsFor,
  addUserSchema,
  displayName,
  editUserSchema,
  statusTone,
} from "./SettingsUsersTab";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const USERS: TenantUser[] = [
  {
    id: "u-alex",
    name: "Alex Reed",
    email: "alex@silvercreek.example",
    role: "system_admin",
    role_name: "System Admin",
    last_active_at: "2026-08-09T14:02:00Z",
    status: "active",
  },
  {
    id: "u-priya",
    name: "Priya Menon",
    email: "priya@silvercreek.example",
    role: "billing_clerk",
    role_name: "Billing Clerk",
    last_active_at: "2026-08-09T12:00:00Z",
    status: "active",
  },
  {
    id: "u-marcus",
    name: "",
    email: "marcus@silvercreek.example",
    role: "billing_clerk",
    role_name: "Billing Clerk",
    last_active_at: null,
    status: "invited",
  },
  {
    id: "u-carla",
    name: "Carla Ortiz",
    email: "carla@silvercreek.example",
    role: "billing_clerk",
    role_name: "Billing Clerk",
    last_active_at: "2026-07-10T09:00:00Z",
    status: "deactivated",
  },
];

const MATRIX: RolesMatrix = {
  roles: [
    { code: "system_admin", name: "System Admin" },
    { code: "billing_clerk", name: "Billing Clerk" },
    { code: "executive", name: "Executive" },
  ],
  permissions: [
    {
      code: "settings_lookups",
      label: "Settings & lookup tables",
      cells: { system_admin: "Full", executive: "View" },
    },
    { code: "user_management", label: "User management", cells: { system_admin: "Full" } },
    {
      code: "adjustment_approval",
      label: "Adjustment / write-off approval",
      cells: { system_admin: "Approve", billing_clerk: "Request", executive: "Approve" },
    },
  ],
};

function pageOf(rows: TenantUser[]): Paginated<TenantUser> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function renderTab(rows: TenantUser[], readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // DEF-SHL-3964 — this mounts the REAL shell, and the shell now renders no
  // routed screen until it knows the tenant's date format and time zone. A
  // test that mounts the product says which tenant it is testing.
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  queryClient.setQueryData(queryKeys.tenantUsers(1, DEFAULT_PAGE_SIZE), pageOf(rows));
  queryClient.setQueryData(queryKeys.rolesMatrix, MATRIX);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <UsersTab readOnly={readOnly} timeZone="America/Chicago" />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-IDN-004 — tenant user list", () => {
  it("US-IDN-004 TC-1: every membership of THIS tenant renders; an invited row shows '—' and 'Never'", () => {
    const html = renderTab(USERS);
    expect(html).toContain("Alex Reed");
    expect(html).toContain("marcus@silvercreek.example");
    expect(html).toContain(">Never<");
    expect(html).toContain(">Invited<");
    expect(html).toContain(">Deactivated<");
    // BR-IDN-011: an invited user has no name yet.
    expect(displayName(USERS[2], "—")).toBe("—");
    expect(displayName(USERS[0], "—")).toBe("Alex Reed");
  });

  it("US-IDN-004 TC-2: the list uses the shared framework's server paging and sort, last-active desc", () => {
    const html = renderTab(USERS);
    expect(html).toContain("data-table");
    expect(html).toContain("table-pager");
    // BR-SHL-034: an instant renders in the tenant TZ (14:02Z → 09:02 CT).
    expect(html).toContain("08/09/2026 09:02");
  });

  it("row actions follow the membership status (IS-6), and no action is invented", () => {
    // DEF-IDN-9706 — an ACTIVE user who has forgotten their password is reset
    // from this row (BR-IDN-023, US-IDN-002 TC-2 on active Priya). This line
    // pinned the list WITHOUT the action, so it asserted the defect.
    expect(actionsFor("active")).toEqual(["temp_password", "edit", "deactivate", "remove"]);
    // CR-188-BRC10 (PO answer 5): an INVITED row also offers Resend invitation.
    expect(actionsFor("invited")).toEqual(["resend", "temp_password", "edit", "remove"]);
    expect(actionsFor("deactivated")).toEqual(["reactivate", "remove"]);
    expect(statusTone("active")).toBe("success");
    expect(statusTone("invited")).toBe("warning");
    expect(statusTone("deactivated")).toBe("neutral");
    // ⚠ WAS `>Reactivate<` — the row action's text content — until 2026-08-20.
    // DEF-337 is what these words looked like on a real deployment: "Edit /
    // Deactivate / Remove / Reset temp password sit as four red words in one
    // cell". They are glyphs now (PO ruling, B14 rule 15) and the words are the
    // accessible names, which is where a test should read them anyway.
    const html = renderTab(USERS);
    expect(html).toContain('aria-label="Reset temp password"');
    expect(html).toContain('aria-label="Reactivate"');
    // ...and every one of them IS named. An icon with no accessible name is
    // the failure rule 15 exists to prevent, and it passes a text check.
    for (const tag of html.match(/<button[^>]*data-size="row"[^>]*>/g) ?? []) {
      expect(tag, `row action without an accessible name: ${tag}`).toMatch(/aria-label="[^"]+"/);
    }
  });

  it("US-IDN-004 TC-3/TC-4 (neg): a role the server refuses gets the A18 §6 block, not an empty table", () => {
    expect(t("settings.users.denied")).toBe("User management is for System Admins only.");
  });

  it.todo("US-IDN-004 TC-5/TC-6 (isolation): only this tenant's memberships are listed — G5 scope");
});

describe("US-IDN-005 — add a user (admin-set temporary password, no-email v1)", () => {
  it("US-IDN-005 TC-1: the temporary password is shown ONCE, with no email and no way back to it", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TempPasswordPanel
          issued={{ email: "tom@silvercreek.example", password: "Tq4v-Xm92-Lpr7", expiresAt: null }}
          dateFormat="MM/DD/YYYY"
          timeZone="America/Chicago"
          onDismiss={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(html).toContain("Tq4v-Xm92-Lpr7");
    expect(html).toContain("For tom@silvercreek.example");
    // BR-IDN-022, said plainly where the value is. ⚠ AMENDED 2026-10-22
    // (CR-188-BRC10): this asserted *"no email is sent"* — BR-IDN-021, which
    // the PO superseded for invitations ("email a one-time sign-in link
    // instead, no password"). The panel no longer claims no email; whether one
    // was sent is the status line's job (cases below).
    expect(html).toContain("Shown once. Copy it now.");
    expect(html).toContain("It works for 7 days.");
    expect(html).not.toContain("no email is sent");
    expect(html).toContain('role="alert"');
    expect(html).toContain("I&#x27;ve copied it");
  });

  it("US-IDN-005 TC-5 / BR-IDN-025: a RESET shows the new value once and dates its expiry", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TempPasswordPanel
          issued={{
            email: "marcus@silvercreek.example",
            password: "Zn6h-Wc31-Qkd8",
            expiresAt: "2026-08-16",
          }}
          dateFormat="MM/DD/YYYY"
          timeZone="America/Chicago"
          onDismiss={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(html).toContain("Zn6h-Wc31-Qkd8");
    expect(html).toContain("It expires");
    expect(html).toContain("08/16/2026");
    // The confirm says the previous value dies immediately.
    expect(t("settings.users.confirm.temp_password.body")).toContain(
      "previous one stops working immediately",
    );
  });

  it("the shown-once value never enters a cache — the panel is the only place it exists", () => {
    // Proven structurally: the panel takes the value as a PROP, and no query
    // key in the app names a temp password.
    expect(Object.keys(queryKeys)).not.toContain("tempPassword");
    expect(JSON.stringify(queryKeys)).not.toContain("temp");
  });

  it("US-IDN-005 TC-3/TC-4 (neg): the add form validates shape, and duplicates are the server's refusal", () => {
    const schema = addUserSchema(t);
    expect(
      collectFormErrors(schema, {
        full_name: "Tom Nguyen",
        email: "tom@silvercreek.example",
        role: "billing_clerk",
      }).count,
    ).toBe(0);
    expect(
      collectFormErrors(schema, { full_name: "Tom", email: "not-an-email", role: "billing_clerk" })
        .errors.email,
    ).toBe("Enter a valid email address.");
    expect(
      collectFormErrors(schema, { full_name: "", email: "tom@x.com", role: "" }).count,
    ).toBe(2);

    const already = new ApiError(409, {
      code: "BIZ-STATE",
      message_key: "errors.identity.already_a_member",
      br_ref: "BR-IDN-010",
    });
    expect(refusalOf(already, t).message).toBe(
      "That email already belongs to someone at this utility.",
    );
  });

  // ⚠ AMENDED 2026-10-22 (CR-188-BRC10). This case was *"BR-IDN-021: the
  // modal states up front that a password appears on screen and no mail is
  // sent"* and asserted `"No email is sent."` in both strings. The PO ruled the
  // opposite (*"email a one-time sign-in link instead, no password"*), so the
  // copy now says a link is emailed — and still that a password appears once.
  it("CR-188-BRC10: the modal says a password appears once AND a sign-in link is emailed", () => {
    expect(t("settings.users.tempPassword.willShow")).toBe(
      "A temporary password appears once. We also email a sign-in link.",
    );
    expect(t("settings.users.emailHelp")).toBe("They sign in with this. We email them a link.");
    for (const key of ["settings.users.tempPassword.willShow", "settings.users.emailHelp"]) {
      expect(t(key)).not.toContain("No email is sent");
    }
  });

  it("CR-188-BRC10: an emailed invitation says where it went, beside the password", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TempPasswordPanel
          issued={{
            email: "sam@silvercreek.example",
            password: "Tq4v-Xm92-Lpr7",
            expiresAt: null,
            invitation: { status: "queued", reason_code: null, email: "sam@silvercreek.example" },
            kind: "invite",
          }}
          dateFormat="MM/DD/YYYY"
          timeZone="America/Chicago"
          onDismiss={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(html).toContain("Invitation emailed to sam@silvercreek.example.");
    expect(html).toContain("Tq4v-Xm92-Lpr7"); // the on-screen password is unchanged
  });

  it("CR-188-BRC10: with no provider the admin is told so and told to share the password", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <TempPasswordPanel
          issued={{
            email: "sam@silvercreek.example",
            password: "Tq4v-Xm92-Lpr7",
            expiresAt: null,
            invitation: {
              status: "not_sent",
              reason_code: "provider_not_connected",
              email: "sam@silvercreek.example",
            },
            kind: "invite",
          }}
          dateFormat="MM/DD/YYYY"
          timeZone="America/Chicago"
          onDismiss={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(html).toContain(
      "Invitation not emailed. No email provider is connected. Share the password below.",
    );
  });

  it("CR-188-BRC10: every reason the server can send has its own sentence in every catalogue", () => {
    const reasons = [
      "no_email_address",
      "public_address_not_configured",
      "email_sending_off",
      "provider_not_connected",
      "provider_status_unknown",
      "switched_off_in_settings",
      "template_missing",
      "queue_refused",
      "email_unavailable",
    ];
    for (const reason of reasons) {
      const key = `settings.users.invite.reason.${reason}`;
      expect(i18n.exists(key)).toBe(true);
      expect(t(key)).not.toBe(key);
    }
    expect(t("settings.users.action.resend")).toBe("Resend invitation");
    expect(t("settings.users.confirm.resend.body")).toContain("The old ones stop working.");
  });

  it.todo(
    "US-IDN-005 TC-2/TC-6/TC-7/TC-9/TC-10: cross-tenant adds, first sign-in activation, expiry and lockout — server/identity scope (G5)",
  );
});

describe("US-IDN-006 — edit role · deactivate · reactivate", () => {
  it("US-IDN-006 TC-4/TC-5 (neg): the last active System Admin refusal is the server's, rendered verbatim", () => {
    for (const action of ["demote", "deactivate", "remove"]) {
      const refused = new ApiError(409, {
        code: "BIZ-STATE",
        message_key: "errors.identity.last_system_admin",
        params: { action },
        br_ref: "BR-IDN-013",
      });
      const refusal = refusalOf(refused, t);
      expect(refusal.message).toBe(
        // Shortened to the 12-word rule, PO 2026-08-19 (decision log `6baa846`).
        `A utility needs one active System Admin. You can't ${action} this one.`,
      );
      expect(refusal.brRef).toBe("BR-IDN-013");
    }
    const html = renderToStaticMarkup(
      <RefusalNotice
        refusal={refusalOf(
          new ApiError(409, {
            code: "BIZ-STATE",
            message_key: "errors.identity.last_system_admin",
            params: { action: "deactivate" },
            br_ref: "BR-IDN-013",
          }),
          t,
        )}
      />,
    );
    expect(html).toContain("one active System Admin");
    expect(html).toContain("BR-IDN-013");
    // The guard is stated in the edit modal before anyone tries it.
    expect(t("settings.users.lastAdminHelp")).toContain("at least one active System Admin");
  });

  it("US-IDN-006 TC-2/TC-3 / BR-SHL-032: the confirms name their action and their consequence", () => {
    expect(t("settings.users.confirm.deactivate.action")).toBe("Deactivate user");
    expect(t("settings.users.confirm.deactivate.body")).toContain("Their history stays.");
    expect(t("settings.users.confirm.reactivate.body")).toContain("existing password");
    for (const key of ["deactivate", "reactivate", "remove", "temp_password"]) {
      expect(t(`settings.users.confirm.${key}.action`)).not.toBe("OK");
    }
  });

  // CR-011 decision 7 (PO 2026-08-18): *"you decide and later allow user to
  // cahnge email as well as Name"*.
  //
  // ⚠ THIS TEST IS WHAT THE OLD SHAPE COULD NOT FAIL ON, which is why it is
  // written against the SCHEMA rather than against a click. `update_user` had
  // validated and audited an email change since the day it was written and
  // `updateTenantUser` declared `email?` in its payload — so every backend
  // test, every type check and every existing case here passed over a modal
  // that drew one text field and sent `{full_name, role}`. Nobody could change
  // an email, and nothing was red. Hard-won law 2.
  it("CR-011 decision 7: the EDIT form accepts an email and validates it the same way ADD does", () => {
    const schema = editUserSchema(t);
    expect(
      collectFormErrors(schema, {
        full_name: "Avery Cole",
        email: "avery.cole@sample.test",
        role: "executive",
      }).count,
    ).toBe(0);
    // One definition of "is this an email": a string Add accepts, Edit accepts,
    // and the message is the same sentence in both places.
    expect(
      collectFormErrors(schema, {
        full_name: "Avery Cole",
        email: "not-an-email",
        role: "executive",
      }).errors.email,
    ).toBe(t("settings.users.emailInvalid"));
    // BR-IDN-021 on the EDIT path: the address is the sign-in identifier and
    // no verification message goes anywhere, because nothing here sends mail.
    expect(t("settings.users.emailChangeHelp")).toContain("how they sign in");
    expect(t("settings.users.emailChangeHelp")).toContain("No verification email is sent");
  });

  // CR-187-BRC10 — a phone number is a field-app sign-in name (PO 2026-10-21:
  // work email OR phone). Optional on both forms; its shape and its uniqueness
  // at this utility are the server's to judge, and its refusal is one sentence.
  it("CR-187-BRC10: both forms carry an optional phone, and a number in use is refused in words", () => {
    for (const schema of [addUserSchema(t), editUserSchema(t)]) {
      expect(
        collectFormErrors(schema, {
          full_name: "Dana Ortiz",
          email: "dana@silvercreek.example",
          phone: "(512) 555-0104",
          role: "billing_clerk",
        }).count,
      ).toBe(0);
    }
    expect(t("settings.users.phone")).toBe("Phone");
    expect(t("errors.identity.phone_in_use")).toBe("This phone number is already in use");
  });

  it.todo("US-IDN-006 TC-1/TC-6/TC-7/TC-8 (isolation + server enforcement): identity scope (G5)");
});

describe("US-IDN-007 — remove a user · read-only roles & permissions matrix", () => {
  it("US-IDN-007 TC-3 / BR-IDN-014: the matrix renders the SERVER's grid with no edit affordance", () => {
    const html = renderToStaticMarkup(<RolesMatrixPanel matrix={MATRIX} />);
    expect(html).toContain("Roles &amp; permissions (predefined · read-only)");
    expect(html).toContain("User management");
    expect(html).toContain("Adjustment / write-off approval");
    // Spot-check the ratified cells: user management = Full / — / —.
    expect(html).toContain("<td>Full</td><td>—</td><td>—</td>");
    // …and approval = Approve / Request / Approve.
    expect(html).toContain("<td>Approve</td><td>Request</td><td>Approve</td>");
    // No control of any kind exists in the panel.
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<input");
    expect(html).not.toContain("<select");
  });

  it("a role the grid does not mention renders '—' rather than an assumed permission", () => {
    const html = renderToStaticMarkup(<RolesMatrixPanel matrix={MATRIX} />);
    expect(html).toContain("—");
    const unavailable = renderToStaticMarkup(<RolesMatrixPanel matrix={null} />);
    expect(unavailable).toContain("only readable by a System Admin");
  });

  it("US-IDN-007 TC-1 / BR-IDN-030: Remove is described as PERMANENT DEACTIVATION, not a delete", () => {
    const body = t("settings.users.confirm.remove.body");
    expect(body).toContain("deactivates them permanently");
    expect(body).toContain("history stay for the audit trail");
    expect(body).toContain("email can't be reused");
    expect(body).toContain("Reactivate");
    // The copy never promises a deletion the endpoint does not perform.
    expect(body.toLowerCase()).not.toContain("deleted");
  });

  it.todo(
    "US-IDN-007 TC-2/TC-5/TC-6: the reference-count audit-lock, self-removal and cross-tenant removal — server scope; E2 with BR-IDN-030 reported",
  );
  it.todo("US-IDN-007 TC-4 (neg): the roles catalog has no tenant mutation route — server 403/405");
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-IDN-004@9d61512 (story+rules snapshot hash — EP-IDN-02; co-stories US-IDN-005/006/007@9d61512)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
