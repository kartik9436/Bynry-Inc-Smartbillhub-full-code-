// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-040 (EP-INT-11) — S144, the keys we issue. Frame 50.1 (a
//           key we issue: the key in mono, Copy, *Copy it now. This is the
//           only time it is shown.*) and 46.1 (the card afterwards, masked).
// Rules:    BR-INT-053 (shown once, only replaced; revocation refuses the very
//           next call) · BR-INT-003 (never rendered back — the hint only) ·
//           B14 rule 6 (danger tier on the destructive commit — Revoke) ·
//           rule 15 (the row action is an ICON with an accessible name) ·
//           rule 20 (one table type) · rule 21 (Tailwind utilities only; this
//           file is on route-b-migrated.txt, in the commit that creates it) ·
//           rule 31 (NO database id is ever the visible value of a field — the
//           key's id is not its display; the HINT is) · rule 32 (one sentence
//           per section) · rule 33 (a refusal is five or six words)
// Tests:    src/features/integrations/MachineKeysPage.test.tsx ·
//           10-scripts/render-checks/cr069-r-issued-key.mjs (rendered output)
// Impacts:  src/App.tsx (the INT-04 route) · src/routing/screenIds.ts (S144) ·
//           src/api/integrationsEndpoints.ts (`issuePartnerKey` ·
//           `revokePartnerKey`) · src/styles/route-b-migrated.txt ·
//           the eleven locale catalogues (`integrations.keys.*`)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **THE KEY LIVES IN COMPONENT STATE AND IN NOTHING ELSE, AND EVERY OTHER
// CHOICE ON THIS SCREEN FOLLOWS FROM THAT.** The mint response is the only
// place the key will ever appear; it is deliberately NOT put through
// `queryClient`, because a cached secret sits in browser memory for the life
// of the tab and can be re-read by anything that can reach the cache. It is
// held in `justIssued`, rendered once, and dropped when the panel closes.
// Refreshing the page does not bring it back and is not meant to.
//
// ⚠ **THE TABLE'S IDENTITY COLUMN IS THE HINT, NOT THE VERSION AND NOT THE
// ROW ID.** B14 rule 31 forbids a database id as the visible value of a field,
// and there is a second reason here: `••••7Q2F` is the string a partner reads
// back down the phone and the string the access log will print as *who*, so it
// is also the useful one. The version number rides along as a small grey
// suffix because *which of the three* is a real question after two replaces.
//
// ⚠ **B9 DEVIATION, STATED RATHER THAN QUIETLY DROPPED.** `EP-INT-11`'s
// capability matrix gives S144 a search on *partner*. This screen is scoped to
// ONE connection by its route (`…/integrations/:key/access`), so every row on
// it has the same partner and a search box would be a control that can only
// ever return everything or nothing — hard-won law 2's shape. The STATE filter
// (active · revoked) is real and is built. When wave S adds the access log
// beside this table, a partner search belongs to THAT table.

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getIntegrationsGrid, issuePartnerKey, revokePartnerKey } from "@/api/integrationsEndpoints";
import type { IntegrationsGrid, IssuedKey, ProviderCard } from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useTenantPath } from "@/routing/tenantPath";
import { useRegional } from "@/features/metering/meteringShared";

const INTEGRATIONS_ROUTE = "/settings/integrations";

type Translate = (key: string, options?: Record<string, unknown>) => string;

/**
 * The one panel that renders a key — frame 50.1's dashed box.
 *
 * It takes the key as a prop and has no other way to obtain one: there is no
 * fetch in here, no fallback to a stored value, and no `hint` branch that
 * could accidentally print a whole key. When the parent has nothing to show,
 * this component is not rendered at all rather than rendered empty.
 */
export function IssuedKeyPanel(props: { value: string; onDone: () => void }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  async function copy(): Promise<void> {
    // `navigator.clipboard` is absent in a non-secure context and in jsdom.
    // A Copy that silently does nothing is worse than one that is honest, so
    // the button reports only what actually happened.
    try {
      await navigator.clipboard.writeText(props.value);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div
      className="border border-dashed border-divider bg-surface p-4"
      data-issued-key-panel="shown"
    >
      <p className="font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
        {t("integrations.modal.issuedKey.caption")}
      </p>
      <p
        className="mt-2 select-all break-all border border-divider px-3 py-2 font-mono text-base"
        data-issued-key-value=""
      >
        {props.value}
      </p>
      <div className="mt-3 flex items-center gap-3">
        <Button variant="primary" size="sm" type="button" onClick={() => void copy()}>
          {copied ? t("integrations.keys.copied") : t("integrations.keys.copy")}
        </Button>
        <Note as="span">{t("integrations.keys.onlyTime")}</Note>
        <Button variant="ghost" size="sm" type="button" onClick={props.onDone}>
          {t("integrations.keys.done")}
        </Button>
      </div>
    </div>
  );
}

function keysTableConfig(
  t: Translate,
  cells: Record<string, (row: IssuedKey) => React.ReactNode>,
): TableConfig<IssuedKey> {
  return {
    screenId: "S144",
    // The identity column is the HINT (see the header note) — never the
    // version number and never a row id (B14 rule 31).
    getRowId: (row) => String(row.version),
    columns: [
      {
        key: "hint",
        label: t("integrations.keys.column.key"),
        identity: true,
        cell: cells.hint,
      },
      { key: "scope", label: t("integrations.keys.column.scope"), cell: cells.scope },
      { key: "issued", label: t("integrations.keys.column.issued"), cell: cells.issued },
      { key: "lastUsed", label: t("integrations.keys.column.lastUsed"), cell: cells.lastUsed },
      { key: "state", label: t("integrations.keys.column.state"), cell: cells.state },
    ],
    filters: [
      {
        name: "state",
        label: t("integrations.keys.column.state"),
        options: [
          { value: "active", label: t("integrations.keys.state.active") },
          { value: "revoked", label: t("integrations.keys.state.revoked") },
        ],
      },
    ],
    defaultSort: { sort: "issued", dir: "desc" },
  };
}

export interface MachineKeysPageProps {
  client?: ApiClient;
}

export function MachineKeysPage(props: MachineKeysPageProps = {}) {
  const { t } = useTranslation();
  const params = useParams<{ key: string }>();
  const providerKey = params.key ?? "";
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { timeZone, dateFormat } = useRegional({});

  /** The one copy of the key, for as long as the panel is open. Never cached. */
  const [justIssued, setJustIssued] = useState<string | null>(null);
  const [confirmingRevoke, setConfirmingRevoke] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [state, setState] = useState<TableRequestState>(() =>
    defaultRequestState(keysTableConfig((key) => key, {})),
  );

  const gridQuery = useQuery<IntegrationsGrid>({
    queryKey: queryKeys.integrations,
    queryFn: () => getIntegrationsGrid(client),
  });

  const issue = useMutation({
    // ⚠ **THE SCOPE IS NOW REQUIRED AT THE DOOR AND THIS CALLER POSTED NOTHING
    // (`DEF-INT-5535`).** `machine_auth._validated_scope` refuses an empty
    // list, so this button could not succeed either. S144 offers no per-API
    // control — the SET-UP screen is where a clerk switches each API on or off
    // (`CR-110-BRC04` phase 2) — so a key issued from here carries **every
    // operation this connector declares**, which is what one key on this
    // connector has always meant in practice. It is NOT an empty list, which
    // the door refuses, and it is NOT a list typed here: it is read off the
    // manifest the card serves, so a connector that grows a fourth API needs
    // no edit to this line.
    //
    // ⚠ That a clerk cannot NARROW a key from this screen is a real gap and is
    // filed rather than left in this comment — `DEF-INT-5539`.
    mutationFn: () =>
      issuePartnerKey(
        client,
        providerKey,
        (gridQuery.data?.providers.find((one) => one.key === providerKey)?.operations ?? []).map(
          (one) => one.name,
        ),
      ),
    onSuccess: (result) => {
      setRefusal(null);
      setJustIssued(result.key); // the only copy — component state, never cache
      void queryClient.invalidateQueries({ queryKey: queryKeys.integrations });
      toast(t("integrations.keys.issued"));
    },
    onError: (error) => setRefusal(refusalText(t, error)),
  });

  const revoke = useMutation({
    mutationFn: () => revokePartnerKey(client, providerKey),
    onSuccess: () => {
      setRefusal(null);
      setConfirmingRevoke(false);
      setJustIssued(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.integrations });
      toast(t("integrations.keys.revoked"));
    },
    onError: (error) => {
      setConfirmingRevoke(false);
      setRefusal(refusalText(t, error));
    },
  });

  if (gridQuery.isPending) return <LoadingSkeleton variant="table" />;

  const card: ProviderCard | undefined = gridQuery.data?.providers.find(
    (one) => one.key === providerKey,
  );
  if (card === undefined) {
    return (
      <FailedWithRetry
        title={t("integrations.keys.failedTitle")}
        reason={refusalText(t, gridQuery.error)}
        onRetry={() => void gridQuery.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  const providerName = t(`integrations.provider.${card.key}.name`, {
    defaultValue: card.display_name,
  });
  const rows = card.issued_keys.filter(
    (one) => state.filters.state === undefined || one.state === state.filters.state,
  );
  const active = card.issued_keys.find((one) => one.state === "active") ?? null;

  const config = keysTableConfig(t as Translate, {
    hint: (row) => (
      <span data-key-row={row.hint} data-key-state={row.state}>
        <span className="font-mono">{row.hint}</span>
        <span className="ml-2 text-xs text-neutral-600">
          {t("integrations.keys.versionSuffix", { version: row.version })}
        </span>
      </span>
    ),
    // *scope (tenant)* — one utility, in words. The tenant's id is not on this
    // screen and never will be (B14 rule 31).
    scope: () => <span>{t("integrations.keys.scopeThisUtility")}</span>,
    issued: (row) => (
      <DateCell value={row.issued_at} timeZone={timeZone} dateFormat={dateFormat} withTime />
    ),
    lastUsed: (row) =>
      row.last_used_at === null ? (
        // ⚠ A DASH WOULD READ AS *WE DID NOT LOOK*. *Never used* is a fact we
        // hold and it is the one somebody checks after issuing a key.
        <span data-never-used="">{t("integrations.keys.neverUsed")}</span>
      ) : (
        <DateCell value={row.last_used_at} timeZone={timeZone} dateFormat={dateFormat} withTime />
      ),
    state: (row) => (
      <span className={row.state === "active" ? "text-success-700" : "text-neutral-600"}>
        {t(`integrations.keys.state.${row.state}`)}
      </span>
    ),
  });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("integrations.keys.title")}
        kicker={providerName}
        backTo={{
          to: tenantPath(`${INTEGRATIONS_ROUTE}/${providerKey}`),
          label: t("integrations.keys.back"),
        }}
        secondaryActions={
          active === null ? null : (
            <Button
              variant="danger"
              type="button"
              data-revoke-key=""
              onClick={() => setConfirmingRevoke(true)}
            >
              {t("integrations.keys.revoke")}
            </Button>
          )
        }
        primaryAction={
          <Button
            variant="primary"
            type="button"
            data-issue-key=""
            disabled={issue.isPending}
            onClick={() => issue.mutate()}
          >
            {active === null ? t("integrations.keys.issue") : t("integrations.keys.replace")}
          </Button>
        }
      />

      {/* Template I6's NoteBox — one sentence (B14 rule 32). */}
      <Note>{t("integrations.keys.note")}</Note>

      {refusal !== null && (
        <p className="text-sm text-danger-700" data-key-refusal="" role="alert">
          {refusal}
        </p>
      )}

      {justIssued !== null && (
        <IssuedKeyPanel value={justIssued} onDone={() => setJustIssued(null)} />
      )}

      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={rows.length}
        loading={gridQuery.isFetching}
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        empty={{
          title: t("integrations.keys.empty.title"),
          helper: t("integrations.keys.empty.helper"),
          ctaLabel: t("integrations.keys.issue"),
          onCta: () => issue.mutate(),
        }}
      />

      {confirmingRevoke && (
        <ConfirmDialog
          title={t("integrations.keys.revokeConfirm.title")}
          consequence={t("integrations.keys.revokeConfirm.consequence")}
          confirmLabel={t("integrations.keys.revoke")}
          confirmVariant="danger" // B14 rule 6 — this one really does break something
          working={revoke.isPending}
          onConfirm={() => revoke.mutate()}
          onCancel={() => setConfirmingRevoke(false)}
        />
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-INT-040@93a5e80 (EP-INT-11) + frames 50.1 / 46.1 + 08-screen-layouts.md S144
// generated: 2026-09-06 by the CR-069 wave R build lane
// checklist: A✔ B✔ C✔ D✔(POST/DELETE /integrations/{key}/key) E✔(routed at /:tenant/settings/integrations/:key/access, INT-04) F✔ G✔ H=n/a
// gates: tsc · vitest MachineKeysPage.test.tsx · G31 (every utility here is emitted — this file is on route-b-migrated.txt) · G15 (integrations.keys.* in all eleven catalogues)
// exceptions: B9's *partner* search is deliberately not built on a screen scoped to one connection, and the reason is in the header note; the ACCESS LOG half of S144 is wave S (US-INT-041)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
