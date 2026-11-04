// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 task 10b — Owner: search the utility's master
//           accounts by name or number, link one, or carry on without one.
// Ruling:   PO 2026-10-09, verbatim: *"in owner - allow to search amster account
//           from master account list. if it is found then shwo the details, if
//           it is not foudn then show this account not available; anyway woner
//           is options - and we shoudl allow to move forward"*, then *"instead
//           of chnge - it should be link or use this. you should nothave these
//           field - Account type … Person or company … Managed by - it will come
//           as part of account seach"*.
// Rules:    BR-MET-1195 (the owner is an existing master account found and
//           linked; this screen opens no account) · B14 rule 31 (the account
//           NUMBER is shown, never the id) · B14 rule 43 (one component: the
//           search → card → use control is the kit's `PickBySearch`, built by
//           the Add units redesign the same day, `CR-176-BRC10`) · IS-3
// Drawing:  05-prototype/add-premise-2026-10-09/images/02, 13, 14
// Reads:    GET /premises/owner-search?q= (`metering.api.premises_owner_search`)
// ───────────────────────────────────────────────────────
import { useRef } from "react";

import type { ApiClient } from "@/api/client";
import { searchPremisesOwners } from "@/api/endpoints";
import type { OwnerSearchRow } from "@/api/endpoints";
import { PickBySearch } from "@/components/PickBySearch";
import type { PickCandidate } from "@/components/PickBySearch";

import type { OwnerState } from "./addPremiseModel";
import { FoldPanel } from "./addPremiseShared";
import type { Translator } from "./addPremiseShared";

/** `Person` / `Company`, or the absence — never a code (B14 rule 31's spirit). */
export function partyKindWord(kind: string | null, t: Translator): string {
  if (kind === "person") return t("customers.customer.kind.person");
  if (kind === "company") return t("customers.customer.kind.company");
  return "—";
}

/** The header's word: the linked account's name, else *Needs an owner*. */
export function ownerStateWord(owner: OwnerState, t: Translator): string {
  return owner.kind === "linked"
    ? (owner.row.name ?? owner.row.account_no ?? t("metering.premises.owner.needs_owner"))
    : t("metering.premises.owner.needs_owner");
}

/** A master account as the kit's search control lists it: the NAME, then
 *  the account number — never the id (B14 rule 31). */
export function ownerCandidate(row: OwnerSearchRow): PickCandidate {
  return { id: row.id, title: row.name ?? row.account_no ?? "—", meta: row.account_no ?? undefined };
}

export function OwnerSection(props: {
  owner: OwnerState;
  onOwner: (next: OwnerState) => void;
  open: boolean;
  onToggle: () => void;
  t: Translator;
  client?: ApiClient;
}) {
  const { t, owner } = props;
  // The rows behind the candidates the control is showing, so the card can
  // draw what the search returned without a second read.
  const seen = useRef(new Map<string, OwnerSearchRow>());
  if (owner.kind === "linked") seen.current.set(owner.row.id, owner.row);

  async function search(q: string): Promise<PickCandidate[]> {
    const page = await searchPremisesOwners(q, props.client);
    for (const row of page.results) seen.current.set(row.id, row);
    return page.results.map(ownerCandidate);
  }

  return (
    <FoldPanel
      id="add-premise-owner"
      title={t("metering.addPremise.owner.title")}
      state={ownerStateWord(owner, t)}
      open={props.open}
      onToggle={props.onToggle}
    >
      <PickBySearch
        id="owner_search"
        label={t("metering.addPremise.owner.field")}
        placeholder={t("metering.addPremise.owner.placeholder")}
        findLabel={t("metering.addPremise.owner.find")}
        noMatchLabel={`${t("metering.addPremise.owner.missingTitle")} ${t("metering.addPremise.owner.missingLine")}`}
        search={search}
        chosen={owner.kind === "linked" ? ownerCandidate(owner.row) : null}
        onUse={(candidate) => {
          const row = seen.current.get(candidate.id);
          if (row !== undefined) props.onOwner({ kind: "linked", row });
        }}
        onChange={() => props.onOwner({ kind: "none" })}
        useLabel={t("metering.addPremise.owner.link")}
        selectedLabel={`✓ ${t("metering.addPremise.owner.linked")}`}
        changeLabel={t("metering.addPremise.owner.unlink")}
        renderCard={(candidate) => {
          const row = seen.current.get(candidate.id);
          if (row === undefined) return null;
          return (
            <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-3" data-owner-card="">
              {[
                ["type", t("metering.addPremise.owner.accountType"), row.account_type_name ?? "—"],
                ["kind", t("metering.addPremise.owner.kind"), partyKindWord(row.party_kind, t)],
                ["managed", t("metering.premises.field.managedBy"), row.managed_by ?? "—"],
                ["status", t("metering.addPremise.owner.status"), row.status_name ?? "—"],
              ].map(([id, label, value]) => (
                <div key={id} data-owner-fact={id}>
                  <dt className="text-sm text-neutral-700">{label}</dt>
                  <dd className="m-0 font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
          );
        }}
      />
      <p className="field-help m-0">{t("metering.addPremise.owner.help")}</p>
    </FoldPanel>
  );
}
