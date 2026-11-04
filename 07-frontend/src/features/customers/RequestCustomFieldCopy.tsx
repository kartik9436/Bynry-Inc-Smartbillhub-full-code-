// ── Trace ──────────────────────────────────────────────
// Change:   CR-161-BRC10 wave W6 — the Approve window's *Your own fields*
//           block: what approving does with every answer typed on Staff New
//           Request, and R5's side-by-side pick.
// Rulings:  PO 2026-10-02, gap 3 (RULED C), verbatim from the agreed design:
//           *"review shows Existing: Metal · Requested: Tile side by side; the
//           EXISTING value is pre-selected; the clerk picks; the choice is
//           audited; a key with no existing value is copied"*.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — `ApproveChecksModal`
//           only mounts it) · rule 36 (the kit's `SegmentedControl`, purpose
//           `choice`) · rule 31 (a record is named by its NUMBER) · rule 33
//           (labels ≤ 3 words, facts ≤ 6, no rationale on screen) · rule 21
//           (Tailwind utilities; on route-b-migrated.txt) · BR-TEN-048 (a
//           value is shown as typed — never money-formatted)
// Tests:    src/features/customers/requestCustomFieldsW6.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE SERVER DECIDES EVERY ROW'S STATE AND THIS FILE DECIDES NONE.**
// `copy_preview` reads the target record and says `copy` / `conflict` / `same`
// / `no_target`; this component draws it. The ONE thing a clerk changes is the
// pick on a conflict, and it opens on the server's own `default_pick`
// (`existing`), so a clerk who touches nothing sends nothing and the server's
// default keeps every existing value too — two halves of one rule, not two
// rules.
//
// ⚠ **A UTILITY WITH NO FIELDS, OR A REQUEST WITH NO ANSWERS, DRAWS NOTHING** —
// no heading, no empty section (US-SHL-015 TC-4's posture).
import { useTranslation } from "react-i18next";

import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { displayValue } from "@/components/CustomFields";
import { SegmentedControl } from "@/components/SegmentedControl";

import type {
  RequestCustomEntity,
  RequestCustomFieldCopyBlock,
  RequestCustomFieldCopyRow,
  RequestCustomFieldPicks,
} from "./serviceRequestEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

const NS = "customers.serviceRequest.customFields";

/** A row's value as the clerk reads it, through the kit's one formatter. */
function shown(row: RequestCustomFieldCopyRow, value: unknown, t: Translate): string {
  const field = {
    id: row.key,
    key: row.key,
    label: row.label,
    help_text: "",
    data_type: row.data_type,
    options: [],
    is_required: false,
    display_order: 0,
    placement: {},
  } as CustomFieldRegistryEntry;
  return displayValue(field, { [row.key]: value }, (iso) => iso, t);
}

/** The pick a row is showing: the clerk's, else the server's pre-selection. */
export function pickOf(
  picks: RequestCustomFieldPicks,
  entity: RequestCustomEntity,
  row: RequestCustomFieldCopyRow,
): "existing" | "requested" {
  return picks[entity]?.[row.key] ?? row.default_pick ?? "existing";
}

export function RequestCustomFieldCopy(props: {
  blocks: readonly RequestCustomFieldCopyBlock[];
  picks: RequestCustomFieldPicks;
  onPick: (entity: RequestCustomEntity, key: string, pick: "existing" | "requested") => void;
}) {
  const { t } = useTranslation();
  if (props.blocks.length === 0) return null;
  return (
    <section data-request-custom-copy="" className="mt-3">
      <h4 className="m-0 mb-1 text-xs font-semibold tracking-wide text-accent uppercase">
        {t(`${NS}.copyHeading`)}
      </h4>
      {props.blocks.map((block) => (
        <div key={block.entity} className="mb-3" data-copy-entity={block.entity}>
          <p className="m-0 mb-1 text-sm font-semibold text-neutral-700">
            {block.target === null
              ? t(`${NS}.targetNone.${block.entity}`)
              : t(`${NS}.target.${block.entity}`, { label: block.target.label })}
          </p>
          <dl className="m-0 grid gap-2">
            {block.rows.map((row) => {
              const requested = shown(row, row.requested, t);
              const existing = shown(row, row.existing, t);
              const labelId = `copy-${block.entity}-${row.key}`;
              return (
                <div
                  key={row.key}
                  className="flex flex-wrap items-center gap-3"
                  data-copy-row={row.key}
                  data-copy-state={row.state}
                >
                  <dt id={labelId} className="min-w-[160px] text-neutral-600">
                    {row.label}
                  </dt>
                  <dd className="m-0">
                    {row.state === "conflict" ? (
                      <SegmentedControl
                        purpose="choice"
                        name={`copy-${block.entity}-${row.key}`}
                        labelledBy={labelId}
                        label={row.label}
                        active={pickOf(props.picks, block.entity, row)}
                        onSelect={(id) =>
                          props.onPick(block.entity, row.key, id as "existing" | "requested")
                        }
                        segments={[
                          { id: "existing", label: t(`${NS}.existing`, { value: existing }) },
                          { id: "requested", label: t(`${NS}.requested`, { value: requested }) },
                        ]}
                      />
                    ) : (
                      <span className="text-neutral-700">
                        {t(`${NS}.state.${row.state}`, { value: requested })}
                      </span>
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      ))}
    </section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-161-BRC10 §R6 gap 3 (RULED C) · decision log 2026-10-02 (W6) · B14 rules 21, 31, 33, 36, 43
// generated: 2026-10-02 by lane CF-W6
// checklist: A✔ B✔ C✔ D✔(the server decides each row) E✔(ApproveChecksModal mounts it) F✔ G✔ H=n/a
// gates: tsc · vitest requestCustomFieldsW6.dom.test.tsx · routeBUtilities (on route-b-migrated.txt)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
