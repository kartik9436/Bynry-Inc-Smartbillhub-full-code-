// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-004 · US-IDN-005 · US-IDN-006 · US-IDN-007 (EP-IDN-02 §Stories)
//           Screens: S8 (Settings → Users & roles)
// Rules:    BR-IDN-008 (exactly the 3 predefined platform roles; no tenant role CRUD) ·
//           BR-IDN-009 (System Admin only; server-enforced, UI gating is convenience) ·
//           BR-IDN-010/BR-IDN-029 (users are PER-TENANT; the list is this tenant's rows only) ·
//           BR-IDN-011 (`invited` = temp password not yet changed; Name renders "—" until first sign-in) ·
//           BR-IDN-012 (deactivation blocks sign-in and revokes this tenant's sessions; history kept) ·
//           BR-IDN-013 (a tenant always keeps ≥ 1 active System Admin) ·
//           BR-IDN-014 (the roles & permissions matrix is READ-ONLY, rendered from the server catalog) ·
//           BR-IDN-022 (a temporary password is shown ONCE on screen) · BR-IDN-021 SUPERSEDED for
//           invitations and resets (CR-188-BRC10, PO 2026-10-22 — a one-time sign-in link is ALSO
//           emailed, never the password; the panel says whether it was) ·
//           BR-IDN-025 (temp password valid 7 days) · BR-IDN-030 (Remove = permanent deactivation) ·
//           BR-SHL-032 (confirms name the action) · BR-SHL-034 (dates via the shared cell) · IS-2 (paging/sort)
// ───────────────────────────────────────────────────────
// S8 → Users & roles.
//
// The one irreversible thing on this screen is the TEMPORARY PASSWORD. The
// server generates it and returns it exactly once; it is never retrievable
// again (BR-IDN-022). So it is rendered in a panel the admin must dismiss
// deliberately, it is never written into a query cache, never re-fetched, and
// the modal that produced it closes into that panel rather than disappearing
// with the value. Losing it is not a bug the user can recover from — only a
// reset (which VOIDS the previous one) can.
//
// Nothing about role legality is decided here: the role options come from the
// server's own catalog (`GET /roles`), the last-admin guard is the server's
// 409 (BR-IDN-013) rendered verbatim, and "Remove" calls the endpoint whose
// ruled behaviour is permanent deactivation (BR-IDN-030) — the confirm says so
// in those words rather than promising a deletion that will not happen.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  addTenantUser,
  deactivateTenantUser,
  getRolesMatrix,
  getTenantUsers,
  issueActivationCode,
  reactivateTenantUser,
  removeTenantUser,
  resendInvitation,
  resetTempPassword,
  updateTenantUser,
} from "@/api/endpoints";
import type {
  AddUserResult,
  InvitationEmail,
  MembershipStatus,
  RolesMatrix,
  TenantUser,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { KeyIcon, PencilIcon, PhoneIcon, PowerIcon, TrashIcon, EnvelopeIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { Kicker, Note } from "@/components/TextBits";
import { InvitationEmailStatus } from "@/features/identity/InvitationEmailStatus";

import {
  RefusalNotice,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "@/features/tenancy/settingsShared";
import type { Refusal, Translator } from "@/features/tenancy/settingsShared";
import {
  ROLE_FIELD_TECHNICIAN,
  ROLE_SYSTEM_ADMIN,
  useRegional,
  useTenantRole,
} from "@/features/metering/meteringShared";

import { PhoneAppCodePanel } from "./PhoneAppCodePanel";
import type { IssuedActivationCode } from "./PhoneAppCodePanel";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** BR-IDN-011: an invited row has no name yet — the prototype renders "—". */
export function displayName(user: TenantUser, dash: string): string {
  return user.name.trim() === "" ? dash : user.name;
}

export function statusTone(status: MembershipStatus): StatusTone {
  switch (status) {
    case "active":
      return "success";
    case "invited":
      return "warning";
    case "deactivated":
      return "neutral";
  }
}

/**
 * Which row actions a status offers (EP-IDN-02 capability row, IS-6). Nothing
 * here decides whether the action will SUCCEED — the last-admin guard
 * (BR-IDN-013) is the server's and arrives as a 409.
 */
export type UserAction =
  | "edit"
  | "deactivate"
  | "reactivate"
  | "remove"
  | "temp_password"
  | "resend"
  | "activation_code";

export function actionsFor(status: MembershipStatus): readonly UserAction[] {
  switch (status) {
    case "active":
      // DEF-IDN-9706 — the forgot-password reset (BR-IDN-023, CR-170-BRC10):
      // an active member who has forgotten their password is issued a new
      // temporary one here. The server always allowed it (audit
      // `auth.temp_password_issued`); this row never offered it.
      return ["temp_password", "edit", "deactivate", "remove"];
    case "invited":
      // CR-188-BRC10 (PO answer 5): *"'Resend invitation' on the row: a new
      // password and a new email."* Invited rows only — the person has never
      // signed in, so there is an invitation to resend.
      return ["resend", "temp_password", "edit", "remove"];
    case "deactivated":
      return ["reactivate", "remove"];
  }
}

/**
 * The row's actions for THIS viewer (DEF-IDN-10365, CR-187-BRC10 `R105`).
 *
 * `actionsFor` stays a function of the row's status alone; this adds the one
 * action that also depends on WHO the row is and WHO is looking: *New app code*
 * is offered only on a field technician who can still sign in, and only to a
 * System Admin — `POST users/{id}/activation-code` is System-Admin-only and the
 * code is useless to any other role. An unknown viewer role (`null`, the read
 * not back yet) offers nothing: the action voids a live code, so it is held
 * until the screen knows it is allowed. The server is the boundary either way
 * (BR-SHL-025).
 */
export function rowActionsFor(user: TenantUser, viewerRole: string | null): readonly UserAction[] {
  const base = actionsFor(user.status);
  if (
    viewerRole !== ROLE_SYSTEM_ADMIN ||
    user.role !== ROLE_FIELD_TECHNICIAN ||
    user.status === "deactivated"
  ) {
    return base;
  }
  const at = base.indexOf("temp_password") + 1;
  return [...base.slice(0, at), "activation_code", ...base.slice(at)];
}

/**
 * B14 rule 15's glyph for each user action. It is a MAP and not a switch so
 * that adding a `UserAction` without giving it a glyph does not compile — the
 * failure mode this replaces is a row action that renders an empty 32x32 box.
 */
const USER_ACTION_ICON: Record<UserAction, ReactNode> = {
  edit: <PencilIcon />,
  deactivate: <PowerIcon />,
  reactivate: <PowerIcon />,
  remove: <TrashIcon />,
  temp_password: <KeyIcon />,
  resend: <EnvelopeIcon />,
  activation_code: <PhoneIcon />,
};

const EMAIL_SHAPE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function addUserSchema(t: Translator) {
  return z.object({
    full_name: z.string().trim().min(1, t("settings.users.nameRequired")),
    email: z.string().trim().refine((v) => EMAIL_SHAPE.test(v), t("settings.users.emailInvalid")),
    // CR-187-BRC10 — optional. The server is the judge of a number's shape and
    // of its uniqueness at this utility (`phone_invalid`, `phone_in_use`).
    phone: z.string().optional(),
    role: z.string().min(1, t("settings.users.roleRequired")),
  });
}

// CR-011 decision 7 (PO 2026-08-18): *"you decide and later allow user to
// cahnge email as well as Name"*. The NAME half has always been here; the
// EMAIL half is the new requirement, and it uses `addUserSchema`'s own shape
// check rather than a second one — one definition of "is this an email", so a
// string the Add panel accepts cannot be one the Edit panel rejects.
export function editUserSchema(t: Translator) {
  return z.object({
    full_name: z.string(),
    email: z.string().trim().refine((v) => EMAIL_SHAPE.test(v), t("settings.users.emailInvalid")),
    phone: z.string().optional(),
    role: z.string().min(1, t("settings.users.roleRequired")),
  });
}

// ── BR-IDN-022 — the shown-once temporary password ─────────────────────────

export interface IssuedTempPassword {
  email: string;
  password: string;
  expiresAt: string | null;
  /** CR-188-BRC10 — whether the one-time sign-in link was emailed, and which
   *  email it was (`invite` for Create user / Resend, `reset` for a reset). */
  invitation?: InvitationEmail;
  kind?: "invite" | "reset";
  /** DEF-IDN-10365 — a field technician's phone app code, answered with the
   *  password by `POST users` and shown once beside it. */
  activation?: IssuedActivationCode | null;
}

/**
 * The panel that carries a value which cannot be asked for again. It states
 * that plainly, so an admin who navigates away knows what they lost and that
 * "Reset temp password" is the only recovery (BR-IDN-011: a reset VOIDS the
 * previous one).
 */
export function TempPasswordPanel(props: {
  issued: IssuedTempPassword;
  dateFormat: RegionalDateFormat;
  /** Tenant TZ — the phone app code's expiry is an instant (DEF-IDN-10365). */
  timeZone: string;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="settings-temp-password" role="alert">
      <Kicker>{t("settings.users.tempPassword.kicker")}</Kicker>
      <p className="settings-temp-password-for">
        {t("settings.users.tempPassword.for", { email: props.issued.email })}
      </p>
      {props.issued.invitation !== undefined && (
        <InvitationEmailStatus
          invitation={props.issued.invitation}
          kind={props.issued.kind ?? "invite"}
        />
      )}
      <code className="settings-temp-password-value">{props.issued.password}</code>
      <p className="settings-temp-password-note">
        {/* BR-IDN-025: 7-day validity, stated with the date it expires. */}
        {props.issued.expiresAt === null
          ? t("settings.users.tempPassword.onceOnly")
          : t("settings.users.tempPassword.onceOnlyUntil")}
        {props.issued.expiresAt !== null && (
          <>
            {" "}
            <DateCell
              value={props.issued.expiresAt}
              timeZone="UTC"
              dateFormat={props.dateFormat}
            />
          </>
        )}
      </p>
      {props.issued.activation != null && (
        // DEF-IDN-10365: the code that claims the phone app, beside the
        // password and dismissed with it — both are shown exactly once.
        <PhoneAppCodePanel
          issued={props.issued.activation}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      )}
      <Button variant="secondary"  onClick={props.onDismiss}>
        {t("settings.users.tempPassword.dismiss")}
      </Button>
    </div>
  );
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface UsersTabProps {
  readOnly: boolean;
  client?: ApiClient;
  dateFormat?: RegionalDateFormat; // IS-8; supplied by the US-SHL-013 wiring
  timeZone?: string; // tenant TZ for "last active" instants
}

type PendingUserAction = { user: TenantUser; action: UserAction } | null;

export function UsersTab(props: UsersTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  // DEF-SHL-3964 — this used to spell its own copy of the seed default, one
  // layer below the resolver. Same defect, same cure: the tenant's own setting.
  // (The first wording of this comment named a prop in backtick-quoted code and
  // G13's scanner read the COMMENT as a prop reference — ten false positives.
  // A comment that contains code-shaped text is code to anything that greps.)
  const { timeZone, dateFormat } = useRegional(props);
  const fireToast = useToast();
  const queryClient = useQueryClient();

  const [state, setState] = useState<TableRequestState>({
    q: "",
    // EP-IDN-02 capability row: last active DESC.
    sort: "last_active",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  const [issued, setIssued] = useState<IssuedTempPassword | null>(null);
  // DEF-IDN-10365 — a REISSUED phone app code, for whom. Held in state only,
  // never in a query cache, exactly like the temporary password above.
  const [issuedCode, setIssuedCode] = useState<
    { email: string; activation: IssuedActivationCode } | null
  >(null);
  const viewerRole = useTenantRole(client);
  const [inviting, setInviting] = useState(false);
  const [editing, setEditing] = useState<TenantUser | null>(null);
  const [pending, setPending] = useState<PendingUserAction>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  // ⚠ `matrixOpen` IS GONE. The grid was a panel this tab toggled open BELOW
  // its own table; it is now the `roles` sub-tab of Users & roles, with an
  // address of its own. A button that reveals a second surface underneath the
  // first is a second way in to something that already has one — see
  // `UsersSubTabs` in SettingsPage.tsx for the strip that replaced it.

  const usersQuery = useQuery({
    queryKey: queryKeys.tenantUsers(state.page, state.per),
    queryFn: () =>
      getTenantUsers({ page: state.page, per: state.per, sort: state.sort, dir: state.dir }, client),
  });
  const rolesQuery = useQuery({
    queryKey: queryKeys.rolesMatrix,
    queryFn: async () => (await getRolesMatrix(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });

  function refresh(): void {
    void queryClient.invalidateQueries({ queryKey: ["users"] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.checklist });
  }

  const rowAction = useMutation({
    mutationFn: (input: { user: TenantUser; action: UserAction }) => {
      switch (input.action) {
        case "deactivate":
          return deactivateTenantUser(input.user.id, client).then(() => undefined);
        case "reactivate":
          return reactivateTenantUser(input.user.id, client).then(() => undefined);
        case "remove":
          return removeTenantUser(input.user.id, client);
        default:
          return Promise.resolve(undefined);
      }
    },
    onSuccess: (_result, input) => {
      refresh();
      setPending(null);
      setRefusal(null);
      fireToast(t(`settings.users.toast.${input.action}`, { name: displayName(input.user, input.user.email) }));
    },
    onError: (error: unknown) => {
      // BR-IDN-013: "a tenant needs at least one active System Admin" arrives
      // as the server's 409 and is rendered verbatim, with its br_ref.
      setPending(null);
      setRefusal(refusalOf(error, t));
    },
  });

  const resetPassword = useMutation({
    mutationFn: (user: TenantUser) => resetTempPassword(user.id, client),
    onSuccess: (result, user) => {
      refresh();
      setPending(null);
      setRefusal(null);
      // BR-IDN-022: shown once — straight into the panel, never into a cache.
      setIssuedCode(null);
      setIssued({
        email: user.email,
        password: result.temp_password,
        expiresAt: result.expires_at,
        invitation: result.invitation_email,
        kind: "reset",
      });
    },
    onError: (error: unknown) => {
      setPending(null);
      setRefusal(refusalOf(error, t));
    },
  });

  // CR-188-BRC10 (PO answer 5) — a new password on screen AND a new invitation
  // email; every earlier link and password stops working.
  const resend = useMutation({
    mutationFn: (user: TenantUser) => resendInvitation(user.id, client),
    onSuccess: (result, user) => {
      refresh();
      setPending(null);
      setRefusal(null);
      setIssued({
        email: user.email,
        password: result.temp_password,
        expiresAt: result.expires_at,
        invitation: result.invitation_email,
        kind: "invite",
      });
    },
    onError: (error: unknown) => {
      setPending(null);
      setRefusal(refusalOf(error, t));
    },
  });

  // DEF-IDN-10365 — `POST users/{id}/activation-code`: a new phone app code,
  // every older unused one void at once; shown once in its own panel.
  const newAppCode = useMutation({
    mutationFn: (user: TenantUser) => issueActivationCode(user.id, client),
    onSuccess: (result, user) => {
      setPending(null);
      setRefusal(null);
      setIssued(null);
      setIssuedCode({
        email: user.email,
        activation: { code: result.activation_code, expiresAt: result.activation_code_expires_at },
      });
    },
    onError: (error: unknown) => {
      setPending(null);
      setRefusal(refusalOf(error, t));
    },
  });

  if (usersQuery.data === undefined && usersQuery.isError) {
    if (isPermissionDenied(usersQuery.error)) {
      // US-IDN-004 TC-3/TC-4: Clerk and Executive both get A18 §6 here.
      return <SettingsDenied helper={t("settings.users.denied")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.users.failedTitle")}
        reason={apiErrorText(usersQuery.error, t)}
        onRetry={() => void usersQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void usersQuery.refetch()}
      />
    );
  }

  const users = usersQuery.data?.results ?? [];
  const roles = rolesQuery.data?.roles ?? [];
  const dash = t("settings.users.never");

  const config: TableConfig<TenantUser> = {
    screenId: "S8.users",
    getRowId: (row) => row.id,
    defaultSort: { sort: "last_active", dir: "desc" },
    columns: [
      {
        key: "name",
        label: t("settings.users.col.name"),
        sortable: true,
        identity: true,
        cell: (row) => displayName(row, t("settings.users.noName")),
      },
      { key: "email", label: t("settings.users.col.email"), sortable: true },
      {
        key: "role",
        label: t("settings.users.col.role"),
        sortable: true,
        cell: (row) => row.role_name,
      },
      {
        key: "last_active",
        label: t("settings.users.col.lastActive"),
        sortable: true,
        cell: (row) =>
          row.last_active_at === null ? (
            dash
          ) : (
            // BR-SHL-034: an instant renders in the tenant TZ through DateCell.
            <DateCell
              value={row.last_active_at}
              timeZone={timeZone}
              dateFormat={dateFormat}
              withTime
            />
          ),
      },
      {
        key: "status",
        label: t("settings.users.col.status"),
        sortable: true,
        cell: (row) => (
          <StatusPill tone={statusTone(row.status)}>
            {t(`settings.users.status.${row.status}`)}
          </StatusPill>
        ),
      },
      {
        key: "actions",
        label: t("settings.reference.col.actions"),
        cell: (row) => (
          <RowActions>
            {rowActionsFor(row, viewerRole).map((action) => (
              <RowAction
                key={action}
                label={t(`settings.users.action.${action}`)}
                icon={USER_ACTION_ICON[action]}
                danger={action === "remove"}
                reason={props.readOnly ? t("settings.readOnlyReason") : null}
                onClick={() => {
                  if (action === "edit") {
                    setEditing(row);
                    return;
                  }
                  setPending({ user: row, action });
                }}
              />
            ))}
          </RowActions>
        ),
      },
    ],
  };

  return (
    <div className="settings-tab">
      <div className="settings-frame-head">
        <div>
          <Kicker>{t("settings.users.kicker")}</Kicker>
          {/* BR-IDN-008, in the user's words — the reason there is no "+ Role". */}
          <p className="settings-lede">{t("settings.users.lede")}</p>
        </div>
        <div className="settings-frame-actions">
          <Button
            variant="primary"
            disabled={props.readOnly}
            title={props.readOnly ? t("settings.readOnlyReason") : undefined}
            onClick={() => setInviting(true)}
          >
            {t("settings.users.add")}
          </Button>
        </div>
      </div>

      {issued !== null && (
        <TempPasswordPanel
          issued={issued}
          dateFormat={dateFormat}
          timeZone={timeZone}
          onDismiss={() => setIssued(null)}
        />
      )}

      {issuedCode !== null && (
        <PhoneAppCodePanel
          issued={issuedCode.activation}
          forEmail={issuedCode.email}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onDismiss={() => setIssuedCode(null)}
        />
      )}

      <RefusalNotice refusal={refusal} />

      <DataTable<TenantUser>
        config={config}
        state={state}
        onStateChange={setState}
        rows={users}
        totalRows={usersQuery.data?.count ?? null}
        loading={usersQuery.isPending}
        empty={{
          title: t("settings.users.emptyTitle"),
          helper: t("settings.users.emptyHelper"),
          ctaLabel: t("settings.users.add"),
          onCta: () => setInviting(true),
        }}
      />

      {inviting && (
        <AddUserModal
          roles={roles}
          client={client}
          onClose={() => setInviting(false)}
          onCreated={(result) => {
            const user = result.user;
            setInviting(false);
            refresh();
            setIssuedCode(null);
            // CR-188-BRC10: the panel still carries the password, and now says
            // whether the one-time sign-in link was emailed too.
            // DEF-IDN-10365: a field technician's answer also carries the phone
            // app code; it lands in the same panel, in the same tick.
            setIssued({
              email: user.email,
              password: result.temp_password,
              expiresAt: null,
              invitation: result.invitation_email,
              kind: "invite",
              activation:
                result.activation_code !== undefined && result.activation_code_expires_at !== undefined
                  ? { code: result.activation_code, expiresAt: result.activation_code_expires_at }
                  : null,
            });
            fireToast(t("settings.users.toast.created", { email: user.email }));
          }}
        />
      )}

      {editing !== null && (
        <EditUserModal
          user={editing}
          roles={roles}
          client={client}
          onClose={() => setEditing(null)}
          onSaved={(user) => {
            setEditing(null);
            refresh();
            fireToast(t("settings.users.toast.edit", { name: displayName(user, user.email) }));
          }}
        />
      )}

      {pending !== null && (
        // BR-SHL-032: every confirm names its action and its consequence.
        <ConfirmDialog
          // B14 rule 6 (DEF-718): this ONE dialog serves five row actions. `deactivate` and `remove` are
          // rule 6's subject; `reactivate` restores access and `temp_password` issues
          // a credential, so both stay primary — a tier on every dialog says nothing.
          confirmVariant={pending.action === "deactivate" || pending.action === "remove" ? "danger" : "primary"}
          title={t(`settings.users.confirm.${pending.action}.title`, {
            name: displayName(pending.user, pending.user.email),
          })}
          consequence={t(`settings.users.confirm.${pending.action}.body`, {
            name: displayName(pending.user, pending.user.email),
          })}
          confirmLabel={t(`settings.users.confirm.${pending.action}.action`)}
          working={
            rowAction.isPending || resetPassword.isPending || resend.isPending || newAppCode.isPending
          }
          onConfirm={() => {
            setRefusal(null);
            if (pending.action === "temp_password") {
              resetPassword.mutate(pending.user);
              return;
            }
            if (pending.action === "resend") {
              resend.mutate(pending.user);
              return;
            }
            if (pending.action === "activation_code") {
              newAppCode.mutate(pending.user);
              return;
            }
            rowAction.mutate(pending);
          }}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  );
}

// ── BR-IDN-014 — the read-only matrix ──────────────────────────────────────

export function RolesMatrixPanel(props: { matrix: RolesMatrix | null }) {
  const { t } = useTranslation();
  if (props.matrix === null) {
    return <Note>{t("settings.users.matrixUnavailable")}</Note>;
  }
  return (
    <div className="settings-matrix">
      <Kicker>{t("settings.users.matrixTitle")}</Kicker>
      {/* BR-IDN-014: rendered from the server catalog, with NO edit affordance
          anywhere — there is no tenant-facing mutation route for it. */}
      <table className="settings-table">
        <thead>
          <tr>
            <th>{t("settings.users.matrixPermission")}</th>
            {props.matrix.roles.map((role) => (
              <th key={role.code}>{role.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.matrix.permissions.map((permission) => (
            <tr key={permission.code}>
              <td>{permission.label}</td>
              {props.matrix?.roles.map((role) => (
                <td key={role.code}>{permission.cells[role.code] ?? "—"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * BR-IDN-014's grid AS A SUB-TAB — `/{tenant}/settings/users/roles`.
 *
 * It owns its own read rather than taking the matrix as a prop, for the reason
 * hard-won law 2 exists: a panel with an optional `matrix` prop is a component
 * that renders nothing whenever a caller forgets to pass one, and every test
 * still passes. `RolesMatrixPanel` keeps that prop because its REQUIRED-ness is
 * what its own suite pins; this is the one caller, and it always supplies it.
 *
 * The query key is the same `queryKeys.rolesMatrix` the Users sub-tab already
 * reads for the role picker, so switching between the two strips costs no
 * request — the answer is in the cache either way.
 *
 * ⚠ **STILL READ-ONLY, AND NOTHING HERE CHANGED THAT.** BR-IDN-008 gives a
 * tenant exactly three predefined roles and no role CRUD, so there is no
 * mutation route to offer and no control that could call one. Moving a surface
 * does not grant a permission.
 */
export function RolesMatrixTab(props: { client?: ApiClient }) {
  const client = props.client ?? api;
  const rolesQuery = useQuery({
    queryKey: queryKeys.rolesMatrix,
    queryFn: async () => (await getRolesMatrix(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  if (rolesQuery.isPending) {
    return <LoadingSkeleton variant="table" />; // A18 §3
  }
  // `null` is not an error state — BR-IDN-014 makes the grid a System-Admin
  // read, so a non-admin gets the panel's own sentence rather than a failure.
  return <RolesMatrixPanel matrix={rolesQuery.data ?? null} />;
}

// ── Modals ─────────────────────────────────────────────────────────────────

function AddUserModal(props: {
  roles: readonly { code: string; name: string }[];
  client: ApiClient;
  onClose: () => void;
  onCreated: (result: AddUserResult) => void;
}) {
  const { t } = useTranslation();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const result = await addTenantUser(
        { full_name: fullName.trim(), email: email.trim(), role, ...(phone.trim() ? { phone: phone.trim() } : {}) },
        props.client,
      );
      // The password leaves this function and lands in the panel in the same
      // tick — it is never stored anywhere it could be read back.
      props.onCreated(result);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("settings.users.addTitle")}
      kicker={t("settings.users.kicker")}
      schema={addUserSchema(t)}
      values={{ full_name: fullName, email, phone, role }}
      submitLabel={t("settings.users.addSubmit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <TextField
        id="full_name"
        label={t("settings.users.col.name")}
        value={fullName}
        onChange={setFullName}
        required
      />
      <TextField
        id="email"
        label={t("settings.users.col.email")}
        value={email}
        onChange={setEmail}
        required
        // CR-188-BRC10: the sign-in identifier AND where the link is emailed.
        help={t("settings.users.emailHelp")}
      />
      {/* CR-187-BRC10 — a field technician may sign in with this number. */}
      <TextField id="phone" label={t("settings.users.phone")} value={phone} onChange={setPhone} />
      <SelectField
        id="role"
        label={t("settings.users.col.role")}
        value={role}
        onChange={setRole}
        // BR-IDN-008: exactly the server's predefined roles.
        options={props.roles.map((r) => ({ value: r.code, label: r.name }))}
        placeholder={t("settings.regional.choose")}
        required
      />
      {/* BR-IDN-022 said before the click: what happens is a password on screen. */}
      <Note>{t("settings.users.tempPassword.willShow")}</Note>
    </FormModal>
  );
}

function EditUserModal(props: {
  user: TenantUser;
  roles: readonly { code: string; name: string }[];
  client: ApiClient;
  onClose: () => void;
  onSaved: (user: TenantUser) => void;
}) {
  const { t } = useTranslation();
  const [fullName, setFullName] = useState(props.user.name);
  // CR-011 decision 7 — the PO's *"later allow user to cahnge email as well as
  // Name"*, and hard-won law 2 is the whole story of why this line is new.
  // `apps/identity/services.update_user` has accepted an email since the day it
  // was written: it checks BR-IDN-029 per-tenant uniqueness, refuses a clash
  // without revealing a match in another tenant, and writes a masked
  // `user.email_changed` audit row. `updateTenantUser` declared `email?` in its
  // payload type. And this modal drew ONE text field and sent `{full_name,
  // role}` — so the complete, tested, audited path was reachable by nobody.
  const [email, setEmail] = useState(props.user.email);
  const [phone, setPhone] = useState(props.user.phone ?? "");
  const [role, setRole] = useState(props.user.role);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const saved = await updateTenantUser(
        props.user.id,
        // `phone: ""` clears the number; the server refuses one in use here.
        { full_name: fullName.trim(), email: email.trim(), role, phone: phone.trim() },
        props.client,
      );
      props.onSaved(saved);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        // BR-IDN-013's last-admin refusal renders inside the modal too, so a
        // demotion that cannot happen is explained where it was attempted.
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("settings.users.editTitle")}
      kicker={t("settings.users.kicker")}
      schema={editUserSchema(t)}
      values={{ full_name: fullName, email, phone, role }}
      submitLabel={t("settings.users.editSubmit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <TextField
        id="full_name"
        label={t("settings.users.col.name")}
        value={fullName}
        onChange={setFullName}
      />
      <TextField
        id="email"
        label={t("settings.users.col.email")}
        value={email}
        onChange={setEmail}
        required
        // BR-IDN-017/027: no verification message is sent to either address
        // (CR-188-BRC10 changed invitations and resets only, not this). The
        // address is the SIGN-IN IDENTIFIER, so
        // changing it changes what this person types to get in — said here,
        // where the change is made, rather than discovered afterwards.
        help={t("settings.users.emailChangeHelp")}
      />
      <TextField id="phone" label={t("settings.users.phone")} value={phone} onChange={setPhone} />
      <SelectField
        id="role"
        label={t("settings.users.col.role")}
        value={role}
        onChange={setRole}
        options={props.roles.map((r) => ({ value: r.code, label: r.name }))}
        required
        help={t("settings.users.lastAdminHelp")}
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-IDN-004@9d61512 (story+rules snapshot hash — EP-IDN-02; co-stories US-IDN-005/006/007@9d61512)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope)
// exceptions: E2 US-IDN-007 §2/BR-IDN-012 describe Remove as a membership DELETE blocked by an audit-lock, while the shipped endpoint implements BR-IDN-030 (PO 2026-08-09: Remove = permanent deactivation, nothing deleted, email never freed) — the confirm copy states the SHIPPED behaviour and the divergence is reported, not resolved · E4 `POST /users` returns no `expires_at`, so the create panel states the 7-day rule without a date while the RESET panel (which does return one) shows it — reported · E1 the B9 row says "no column chooser in design" but FE-02 renders its ⋮ menu unconditionally; DataTable is still used because the row DOES declare IS-2 paging + sort — the FE-02 gap is reported, not patched from here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
