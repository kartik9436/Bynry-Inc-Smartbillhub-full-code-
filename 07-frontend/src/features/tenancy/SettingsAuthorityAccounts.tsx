// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 2 task 3 — Settings › Accounting › Authority
//           accounts (CR §7 item 1). No drawing exists for it; it is built to
//           match the neighbouring Settings › Accounting panels (B14 rules 36,
//           43, 44): the same frame title, the same `settings-table`, the same
//           pencil row action and the same `FormModal`.
// Rules:    B14 rule 31 (no id on screen) · rule 33 (copy caps) · rule 21
//           (no new stylesheet class — only classes the neighbours already use)
//           · NFR-3 (the list pages on the server, `ListPager`)
// ───────────────────────────────────────────────────────
//
// THE NUMBER EACH TAX AUTHORITY KNOWS THE UTILITY BY, TYPED ONCE.
//
// PO 2026-10-02 (decision log *"GO ON THE TAXES & FEES REDESIGN"*): *"Due and
// Your account - It should be drop down - Your account can come from settings
// we ahve configure accounts sections"*. Before this list the number was
// re-typed on every tax, and a typo on one of three State taxes filed one
// return under the wrong account with nothing flagging it. Every tax's
// *Account with the authority* now picks from here.
//
// Retiring an account (`Offer on taxes` off) keeps it on every tax that files
// under it and stops offering it to new ones — nothing is ever deleted.
//
// DEF-RAT-10027 — PO RULING 2026-10-09, OPTION (a), verbatim: *"so this is not
// bank account . user is worng. this is the tax code that tax autheirty will
// recognise any tax paying entity. for example in india there is gsT number ;
// simialr tot hat us or canada will ahve some number"*. So this list is the
// utility's TAX REGISTRATION NUMBER with each authority (a state sales-tax
// permit, an EIN, a Canadian BN `123456789 RT0001`), headed *Tax filing
// accounts* — not *GL code mapping*, because nothing here is a ledger account —
// and the authority is PICKED from the same authorities a tax uses, so a tax
// can offer only the numbers held with its own authority.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import {
  createAuthorityAccount,
  getAuthorityAccountsPage,
  updateAuthorityAccount,
} from "@/api/authorityAccountEndpoints";
import type { AuthorityAccount } from "@/api/authorityAccountEndpoints";
import { Button } from "@/components/Button";
import { getTaxJurisdictions } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { CheckboxField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PencilIcon } from "@/components/icons";
import { ListPager } from "@/components/ListPager";
import { RowAction, RowActions } from "@/components/RowActions";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";

import { apiErrorText } from "./settingsShared";

/** The query key every reader of this list shares, so a save refreshes all. */
export const AUTHORITY_ACCOUNTS_QUERY_KEY = ["settings", "authority-accounts"] as const;

/** The add/edit form's values — strings and a flag, never a number.
 *
 *  DEF-RAT-10027 (PO 2026-10-09, option (a)): the authority is PICKED from the
 *  tax authorities (`jurisdiction_id`), so a tax can be offered only the
 *  numbers held with its own authority. `authority_name` stays: it is the
 *  name a row typed before the picker carries, kept until somebody links it. */
export interface AuthorityAccountDraft {
  jurisdiction_id: string;
  authority_name: string;
  account_number: string;
  active: boolean;
}

export function draftOf(row: AuthorityAccount | null): AuthorityAccountDraft {
  return {
    jurisdiction_id: row?.jurisdiction_id ?? "",
    authority_name: row?.authority_name ?? "",
    account_number: row?.account_number ?? "",
    active: row?.active ?? true,
  };
}

/**
 * What a save sends. A picked authority sends its id AND its name (the server
 * writes the jurisdiction's own name either way, so a picked row never carries
 * a name that disagrees with it); an unlinked row keeps its typed name.
 */
export function authorityAccountPayload(
  draft: AuthorityAccountDraft,
  authorities: readonly { id: string; name: string }[] = [],
) {
  const picked = authorities.find((row) => row.id === draft.jurisdiction_id);
  if (draft.jurisdiction_id !== "") {
    return {
      jurisdiction_id: draft.jurisdiction_id,
      authority_name: (picked?.name ?? draft.authority_name).trim(),
      account_number: draft.account_number.trim(),
      active: draft.active,
    };
  }
  return {
    authority_name: draft.authority_name.trim(),
    account_number: draft.account_number.trim(),
    active: draft.active,
  };
}

export function AuthorityAccountsPanel(props: { readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  // `undefined` = no form open; `null` = adding; a row = editing that row.
  const [editing, setEditing] = useState<AuthorityAccount | null | undefined>(undefined);

  const listQuery = useQuery({
    queryKey: [...AUTHORITY_ACCOUNTS_QUERY_KEY, page, per],
    queryFn: () => getAuthorityAccountsPage({ page, per }, props.client),
  });
  const rows = listQuery.data?.rows ?? [];
  const total = listQuery.data?.total ?? 0;

  return (
    <>
      <h3 className="settings-frame-title">{t("settings.accounting.authorities.title")}</h3>
      <Note>{t("settings.accounting.authorities.hint")}</Note>
      <div className="settings-frame-toolbar">
        <Button
          variant="secondary"
          disabled={props.readOnly}
          title={props.readOnly ? t("settings.readOnlyReason") : undefined}
          onClick={() => setEditing(null)}
        >
          {t("settings.accounting.authorities.add")}
        </Button>
      </div>

      {listQuery.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : listQuery.isError ? (
        <p className="settings-warning" role="status">
          {apiErrorText(listQuery.error, t)}
        </p>
      ) : rows.length === 0 && total === 0 ? (
        <Note>{t("settings.accounting.authorities.empty")}</Note>
      ) : (
        <>
          <table className="settings-table">
            <thead>
              <tr>
                <th>{t("settings.accounting.authorities.col.authority")}</th>
                <th>{t("settings.accounting.authorities.col.number")}</th>
                <th>{t("settings.accounting.authorities.col.status")}</th>
                <th>{t("settings.accounting.col.action")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.authority_name}</td>
                  <td>{row.account_number}</td>
                  <td>
                    <StatusPill tone={row.active ? "success" : "muted"}>
                      {row.active
                        ? t("settings.accounting.authorities.active")
                        : t("settings.accounting.authorities.retired")}
                    </StatusPill>
                  </td>
                  <td>
                    <RowActions>
                      <RowAction
                        label={t("settings.accounting.authorities.edit")}
                        icon={<PencilIcon />}
                        reason={props.readOnly ? t("settings.readOnlyReason") : null}
                        onClick={() => setEditing(row)}
                      />
                    </RowActions>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <ListPager
            total={total}
            page={page}
            per={per}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1);
            }}
          />
        </>
      )}

      {editing !== undefined && (
        <AuthorityAccountModal
          row={editing}
          client={props.client}
          onClose={() => setEditing(undefined)}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: AUTHORITY_ACCOUNTS_QUERY_KEY });
            fireToast(t("settings.accounting.authorities.saved"));
          }}
        />
      )}
    </>
  );
}

function AuthorityAccountModal(props: {
  row: AuthorityAccount | null;
  client: ApiClient;
  onClose: () => void;
  onSaved: (saved: AuthorityAccount) => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<AuthorityAccountDraft>(() => draftOf(props.row));
  const set = (patch: Partial<AuthorityAccountDraft>) => setDraft((was) => ({ ...was, ...patch }));
  // DEF-RAT-10027 — the SAME authorities list a tax picks from (every page).
  const authoritiesQuery = useQuery({
    queryKey: queryKeys.taxJurisdictions,
    queryFn: () => getTaxJurisdictions(props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const authorities = authoritiesQuery.data ?? [];
  // A row typed before the picker has a name and no link: its name stands in
  // the box until an authority is picked, and saving it unpicked keeps it.
  const typedOnly = props.row !== null && props.row.jurisdiction_id === null && draft.jurisdiction_id === "";

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const payload = authorityAccountPayload(draft, authorities);
      const saved =
        props.row === null
          ? await createAuthorityAccount(payload, props.client)
          : await updateAuthorityAccount(props.row.id, payload, props.client);
      props.onSaved(saved);
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
      title={
        props.row === null
          ? t("settings.accounting.authorities.addTitle")
          : t("settings.accounting.authorities.editTitle")
      }
      kicker={t("settings.accounting.authorities.title")}
      schema={z.object({
        // An authority is picked — or, on a row typed before the picker, its
        // typed name is kept.
        authority_jurisdiction: typedOnly
          ? z.string()
          : z.string().min(1, t("rating.required")),
        account_number: z.string().trim().min(1, t("rating.required")),
      })}
      values={{ authority_jurisdiction: draft.jurisdiction_id, account_number: draft.account_number }}
      submitLabel={t("settings.accounting.authorities.save")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <SelectField
        id="authority_jurisdiction"
        label={t("settings.accounting.authorities.col.authority")}
        value={draft.jurisdiction_id}
        placeholder={typedOnly ? draft.authority_name : t("settings.accounting.authorities.chooseAuthority")}
        options={authorities.map((row) => ({ value: row.id, label: row.name }))}
        help={
          authoritiesQuery.isSuccess && authorities.length === 0
            ? t("settings.accounting.authorities.noAuthorities")
            : undefined
        }
        onChange={(value) => {
          const picked = authorities.find((row) => row.id === value);
          set({ jurisdiction_id: value, authority_name: picked?.name ?? props.row?.authority_name ?? "" });
        }}
        required
      />
      <TextField
        id="account_number"
        label={t("settings.accounting.authorities.col.number")}
        value={draft.account_number}
        onChange={(value) => set({ account_number: value })}
        required
      />
      <CheckboxField
        id="active"
        label={t("settings.accounting.authorities.field.offered")}
        checked={draft.active}
        onChange={(checked) => set({ active: checked })}
      />
    </FormModal>
  );
}
