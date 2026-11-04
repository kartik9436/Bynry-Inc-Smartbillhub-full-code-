// ── Trace ──────────────────────────────────────────────
// Change:  CR-039 wave C task 13 — *"migrate the free-text names"*. PO ruling
//          2026-08-27, whose second unsettled caveat is this file's entire
//          reason to exist, verbatim: *"What happens to the twelve existing
//          free-text names on migration. They are real data on a live tenant.
//          A flagged migration that offers each name for matching is the
//          shape; silently guessing which string is which party is not."*
// Rules:   BR-MET-151 (matching, never guessing) · BR-MET-150 (the record) ·
//          BR-TEN-150 (the vocabulary the category comes from) · B14 rule 21
//          (Tailwind utilities only — this file adds NO class to a stylesheet)
// Screens: PRM-04 — rendered on the S14 Premises tab, above the table
// Question: OQ-500 (the free text stays; the money path is untouched)
// ───────────────────────────────────────────────────────
// ⚠ **THIS PANEL IS THE "FLAGGED MIGRATION". `metering 0040` WRITES NOTHING.**
// A backfill would have been one line and would have looked like progress; it
// would also have put a permanent claim about a real party into a real
// customer's database on the strength of a legal suffix. So the migration adds
// the table and stops, and the names arrive HERE, where a person decides.
//
// ⚠ **IT DISAPPEARS WHEN THERE IS NOTHING TO DO, AND THAT IS DELIBERATE.** A
// zero-state panel saying *"nothing to match"* is a permanent piece of
// furniture describing an empty set; the work is finite and the surface should
// end with it.
//
// ⚠ **GROUPED BY NAME, NEVER BY ADDRESS.** Twelve addresses sharing one
// landlord are ONE decision. A list of twelve identical rows invites twelve
// separate parties — exactly what `uq_premises_owners_tenant_name_ci` refuses
// and exactly the opposite of the ruling's *"one party rather than twelve
// unrelated strings"*.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";
import type { LookupEntry, UnmatchedOwnerRow } from "@/api/endpoints";
import { getLookupEntries, getUnmatchedOwners, matchPremisesOwner } from "@/api/endpoints";

export const unmatchedOwnersQueryKey = ["metering", "premises-owners", "unmatched"] as const;
const ownerCategoriesQueryKey = ["lookups", "owner_categories"] as const;

/**
 * One name, and the decision a person makes about it.
 *
 * The category select carries NO pre-selection — not the commonest kind, not
 * the first row, not a guess from the string. BR-MET-151 clause 3 is the whole
 * of this component's discipline, and a defaulted select is how that rule gets
 * broken by a UI convenience rather than by a decision.
 */
function UnmatchedRow(props: {
  row: UnmatchedOwnerRow;
  categories: LookupEntry[];
  onMatch: (payload: { premisesIds: string[]; body: Record<string, unknown> }) => void;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const { row } = props;
  const [category, setCategory] = useState("");
  const suggested = row.suggested_owner_ids[0];
  const premisesIds = row.premises.map((premises) => premises.id);

  return (
    <li className="border-t border-divider py-3 first:border-t-0">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="font-medium">{row.owner_manager}</span>
        <span className="text-sm text-neutral-600">
          {t("metering.premises.owner.match.addressCount", {
            count: row.premises_count,
            defaultValue: "{{count}} address(es)",
          })}
        </span>
      </div>
      <p className="mt-1 text-sm text-neutral-600">
        {row.premises.map((premises) => premises.address_line).join(" · ")}
      </p>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        {suggested !== undefined && (
          /* An EXACT name match already exists as a typed party. Offered as a
             one-click link and never applied automatically — the server would
             accept it, and the person is the one the ruling puts in charge. */
          <button
            type="button"
            className="rounded-md border border-divider px-3 py-1.5 text-sm hover:bg-bg disabled:opacity-50"
            disabled={props.busy}
            onClick={() => props.onMatch({ premisesIds, body: { owner_id: suggested } })}
          >
            {t("metering.premises.owner.match.link", {
              defaultValue: "Link to the existing owner",
            })}
          </button>
        )}
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-neutral-700">
            {t("metering.premises.owner.match.category", { defaultValue: "Owner type" })}
          </span>
          <select
            className="rounded-md border border-field-border bg-surface px-2 py-1.5"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            {/* NO pre-selection — see the component docstring. */}
            <option value="">
              {t("metering.premises.owner.match.choose", { defaultValue: "Choose a type…" })}
            </option>
            {props.categories
              .filter((entry) => entry.active)
              .map((entry) => (
                <option key={entry.code} value={entry.code}>
                  {entry.name}
                </option>
              ))}
          </select>
        </label>
        <button
          type="button"
          className="rounded-md bg-accent-700 px-3 py-1.5 text-sm text-surface hover:bg-accent-800 disabled:opacity-50"
          disabled={props.busy || category === ""}
          onClick={() =>
            props.onMatch({ premisesIds, body: { category, name: row.owner_manager } })
          }
        >
          {t("metering.premises.owner.match.create", {
            defaultValue: "Create this owner and link",
          })}
        </button>
      </div>
    </li>
  );
}

export function OwnerMatchingPanel(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();

  const unmatchedQuery = useQuery({
    queryKey: unmatchedOwnersQueryKey,
    queryFn: () => getUnmatchedOwners(client),
    retry: false,
  });
  const categoriesQuery = useQuery({
    queryKey: ownerCategoriesQueryKey,
    queryFn: () => getLookupEntries("owner_categories", { per: 200 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const match = useMutation({
    mutationFn: async (input: { premisesIds: string[]; body: Record<string, unknown> }) => {
      // ⚠ **THE FIRST ADDRESS CREATES THE PARTY; THE REST LINK TO IT.** All the
      // addresses under one name are one decision (see the file header), and
      // sending `{category, name}` for each of them would hit
      // `uq_premises_owners_tenant_name_ci` on the second and refuse — which is
      // the constraint doing its job and would look like a bug from here.
      const [first, ...rest] = input.premisesIds;
      const created = await matchPremisesOwner(first, input.body, client);
      for (const premisesId of rest) {
        await matchPremisesOwner(premisesId, { owner_id: created.owner.id }, client);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: unmatchedOwnersQueryKey });
      void queryClient.invalidateQueries({ queryKey: ["metering", "premises"] });
    },
  });

  const rows = unmatchedQuery.data?.results ?? [];
  if (rows.length === 0) {
    // Nothing to match — the panel is not here. See the file header.
    return null;
  }

  return (
    <section className="mb-4 rounded-lg border border-warning-500 bg-warning-100 p-4">
      <h2 className="text-base font-semibold">
        {t("metering.premises.owner.match.title", { defaultValue: "Owner names to match" })}
      </h2>
      {/* B14 rule 18 (CR-041 task 5) — the panel's description, on the
          `--desc-measure` token rather than `max-w-prose`'s 65ch (DEF-900). */}
      <p className="mt-1 max-w-measure text-sm text-neutral-700">
        {t("metering.premises.owner.match.intro", {
          count: unmatchedQuery.data?.premises ?? 0,
          defaultValue:
            "These addresses name an owner as free text and no owner record. Choose what kind of party each one is — nothing here is guessed for you.",
        })}
      </p>
      <ul className="mt-3">
        {rows.map((row) => (
          <UnmatchedRow
            key={row.owner_manager}
            row={row}
            categories={categoriesQuery.data?.results ?? []}
            busy={match.isPending}
            onMatch={(payload) => match.mutate(payload)}
          />
        ))}
      </ul>
    </section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-039 wave C tasks 12-14 — 12-governance/11-change-requests.md
// generated: 2026-08-27 by the CR-039 wave C tasks 12-14 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// exceptions:
//   E3 r10 draws NO owner-matching surface — it predates the typed record — so
//      this panel has no prototype to conform to. It is placed on the S14
//      Premises tab because that is where the addresses it is about live, and
//      it removes itself when the backlog is empty.
//   E3 the panel offers no "not an owner / skip" action. Leaving a name
//      unmatched IS the skip, and it costs nothing; an explicit dismissal would
//      need a stored flag, which is the second copy of a fact BR-MET-151 clause
//      2 exists to avoid.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
