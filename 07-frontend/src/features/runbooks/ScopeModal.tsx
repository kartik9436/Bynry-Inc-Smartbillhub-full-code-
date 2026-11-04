// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-039 (EP-RBS-05) — CR-075 wave T. Screens: RBS-004.3.
// Rules:   `BR-RBS-042` (a tenant sets input VALUES and nothing else; a domain
//          per input, resolved per tenant; one value, several, or *all*, and
//          *all* is stored as THE WORD) · B14 rule 9 (a multiple-choice field
//          is removable CHIPS plus an add control — never a wall of checkboxes)
//          · rule 8 (a list of five or more is searchable — the add control is
//          a `select`, which every browser type-filters) · rule 31 (no database
//          id is ever the visible value of a field) · rule 32 (one sentence per
//          section, no rule id or internal code in clerk-facing copy) ·
//          `BR-SHL-025` (a control a person may not use is drawn DISABLED with
//          its reason, never hidden) · `NFR-3`.
// Defects: DEF-RBS-4338 (a signed rule said a utility sets a runbook's inputs
//          and there was nowhere to save one) · DEF-CWP-3925 (a live screen
//          behind a dead control — this file is what expires that hold).
// Tests:   src/features/runbooks/RunbookSetupPage.test.tsx
// ───────────────────────────────────────────────────────
//
// **CHANGE SCOPE** — the modal that made `RBS-004.3`'s button do something.
//
// ══════════════════════════════════════════════════════════════════════════
// ***All* IS A SEPARATE QUESTION, AND DRAWING IT THAT WAY IS THE RULE**
// ══════════════════════════════════════════════════════════════════════════
// `BR-RBS-042` clause 1: *all* is stored as the WORD and resolved when the run
// starts. So the control asks TWO things — *every one* or *only the ones I
// choose* — and the chips appear only under the second. Putting *All* in the
// chip list as a twelfth service would make it a VALUE, which is exactly the
// reading the rule exists to prevent: a utility that adds Trash next month
// would silently be outside a runbook it had set to *all*.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IS DRAWN DISABLED, AND WHY IT IS DRAWN AT ALL
// ══════════════════════════════════════════════════════════════════════════
// B14: a control a person may not use is drawn disabled WITH its reason, never
// hidden — a hidden control is one a clerk assumes is absent. Three inputs are
// held here and each says why in one short sentence: an UNBOUNDED domain
// (`account`, 40,000 rows at the top of T5, and a picker over it needs a
// searching control this kit does not have), a Settings-owned value (`RBR-03`
// — duplicating one is how a utility ends up with two ladders), and the two
// types whose controls `09-component-inventory.md` marks ⬜ unbuilt.
//
// ⚠ **A HELD INPUT IS NEVER SENT.** `scopeToWire` carries only what a person
// could have changed, so a round trip through this modal cannot rewrite a value
// it could not show them.
import { useTranslation } from "react-i18next";
import { useQueries } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { ChipMultiSelect } from "@/components/ChipMultiSelect";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { z } from "zod";

import { RunbookSettingsFields } from "./RunbookSettingsFields";
import { editableKind, holdReason } from "./setupScope";
import type { ScopeDraft } from "./setupScope";
import { listParameterDomain } from "./setupWire";
import type { WireDomainRow, WireParameterSetting } from "./setupWire";

/** Nothing is refused on the client that the server does not refuse: the domain
 *  membership, the *all* rule and the unknown-name check all live in
 *  `services._validated_parameters`, which is the only place that can read this
 *  tenant's data. A schema here would be a second, weaker copy of it. */
const SCOPE_SCHEMA = z.object({});

/** How many rows of a domain the picker asks for.
 *
 *  ⚠ **THE PAGE SIZE IS NOT A CAP** (`NFR-5`). Only BOUNDED domains reach a
 *  picker at all — `service` is the enabled subset of an eleven-row platform
 *  catalogue and `period` grows by twelve a year — so one page holds all of
 *  them for any utility this product serves, and an unbounded domain is held
 *  above rather than truncated here. */
const DOMAIN_PAGE = 200;

export function ScopeModal(props: {
  runbookKey: string;
  parameters: readonly WireParameterSetting[];
  draft: ScopeDraft;
  onChange: (next: ScopeDraft) => void;
  onClose: () => void;
  onSubmit: () => Promise<FormSubmitOutcome>;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const editable = props.parameters.filter((one) => editableKind(one) === "domain");
  // One query per domain-backed input. `useQueries` rather than a loop of
  // `useQuery`, because the number of inputs varies by runbook and a hook
  // cannot be called conditionally.
  const domains = useQueries({
    queries: editable.map((parameter) => ({
      queryKey: ["runbooks", "domain", props.runbookKey, parameter.name],
      queryFn: () =>
        listParameterDomain(
          props.runbookKey,
          parameter.name,
          { page: 1, per: DOMAIN_PAGE },
          props.client,
        ),
    })),
  });
  const rowsFor = (name: string): readonly WireDomainRow[] => {
    const index = editable.findIndex((one) => one.name === name);
    return index === -1 ? [] : (domains[index]?.data?.rows ?? []);
  };

  const set = (name: string, patch: Partial<ScopeDraft[string]>) =>
    props.onChange({ ...props.draft, [name]: { ...props.draft[name], ...patch } });

  return (
    <FormModal
      title={t("runbooks.setup.scope.change")}
      schema={SCOPE_SCHEMA}
      values={props.draft}
      submitLabel={t("runbooks.setup.scope.save")}
      onClose={props.onClose}
      onSubmit={props.onSubmit}
    >
      {props.parameters.map((parameter) => {
        const entry = props.draft[parameter.name];
        if (entry === undefined) return null;
        const kind = editableKind(parameter);

        if (kind === "held" && holdReason(parameter) === "settings") {
          // `OQ-WRK-12793` → A (PO 2026-10-13): Settings' OWN value, read-only,
          // with a link to the page that edits it — never the greyed box over
          // the runbook's declared default that stood here (`DEF-WRK-10122`).
          // Never sent: `scopeToWire` still carries only what a person could
          // change.
          return (
            <RunbookSettingsFields
              key={parameter.name}
              fields={[
                {
                  name: parameter.name,
                  label: parameter.label,
                  setting: parameter.setting_key ?? "",
                },
              ]}
            />
          );
        }

        if (kind === "held") {
          // Drawn, disabled, with its reason — never hidden (B14 / BR-SHL-025).
          return (
            <TextField
              key={parameter.name}
              id={parameter.name}
              label={parameter.label}
              value={String(entry.value)}
              onChange={() => undefined}
              // `readOnly` and not `disabled`, which is `BR-SHL-025`'s own
              // shape in this kit: the field stays focusable and its text stays
              // selectable, so a person can still READ the value they may not
              // set, and the `help` line carries the reason.
              readOnly
              help={t(`runbooks.setup.scope.held.${holdReason(parameter)}`)}
            />
          );
        }

        if (kind === "domain" && parameter.multi) {
          const options = rowsFor(parameter.name);
          return (
            <div key={parameter.name} data-scope-input={parameter.name}>
              <SelectField
                id={`${parameter.name}-mode`}
                label={parameter.label}
                value={entry.mode}
                onChange={(mode) => set(parameter.name, { mode: mode as "all" | "some" })}
                options={[
                  { value: "all", label: t("runbooks.setup.scope.all") },
                  { value: "some", label: t("runbooks.setup.scope.some") },
                ]}
              />
              {entry.mode === "some" && (
                <ChipMultiSelect
                  label={parameter.label}
                  options={options}
                  selected={entry.values}
                  onChange={(values) => set(parameter.name, { values })}
                  addLabel={t("runbooks.setup.scope.add")}
                  // `BR-RBS-042` clause 2 — an empty domain SAYS SO. An empty
                  // dropdown reads as broken; this reads as a fact.
                  emptyLabel={
                    options.length === 0
                      ? t("runbooks.setup.scope.emptyDomain")
                      : t("runbooks.setup.scope.noneChosen")
                  }
                  removeLabel={t("runbooks.setup.scope.remove")}
                  testKey={parameter.name}
                />
              )}
            </div>
          );
        }

        if (kind === "domain") {
          const options = rowsFor(parameter.name);
          return (
            <SelectField
              key={parameter.name}
              id={parameter.name}
              label={parameter.label}
              value={entry.value}
              onChange={(value) => set(parameter.name, { value })}
              options={options.map((row) => ({ value: row.value, label: row.label }))}
            />
          );
        }

        if (kind === "choice") {
          return (
            <SelectField
              key={parameter.name}
              id={parameter.name}
              label={parameter.label}
              value={entry.value}
              onChange={(value) => set(parameter.name, { value })}
              // ⚠ THE CODE IS DE-CASED, NEVER PRINTED RAW (`DEF-RBS-4339`).
              // `choices` are bare strings in Python — `blockers_and_warnings`
              // — and a snake_case code in front of a clerk is B14 rule 32.
              options={entry.kind === "choice" ? choiceOptions(parameter) : []}
            />
          );
        }

        if (kind === "switch") {
          return (
            <SelectField
              key={parameter.name}
              id={parameter.name}
              label={parameter.label}
              value={entry.value === "true" ? "true" : "false"}
              onChange={(value) => set(parameter.name, { value })}
              options={[
                { value: "true", label: t("runbooks.setup.thisCan.yes") },
                { value: "false", label: t("runbooks.setup.thisCan.no") },
              ]}
            />
          );
        }

        return (
          <TextField
            key={parameter.name}
            id={parameter.name}
            label={parameter.label}
            value={entry.value}
            onChange={(value) => set(parameter.name, { value })}
          />
        );
      })}
    </FormModal>
  );
}

/** A runbook's own vocabulary, de-cased. `setupModel.ts` explains the reasoning
 *  at length and this repeats the ONE line that matters: a per-runbook lookup
 *  table is the one thing that is not allowed, because it would break `RB-020`
 *  — *adding runbook 23 needs one Python module and no frontend code*. */
function choiceOptions(parameter: WireParameterSetting) {
  return parameter.choices.map((code) => ({
    value: code,
    label: /^[a-z0-9]+(?:_[a-z0-9]+)+$/.test(code)
      ? code.split("_").join(" ").replace(/^./, (c) => c.toUpperCase())
      : code,
  }));
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-039 (EP-RBS-05; CR-075 wave T) · BR-RBS-042 (PO 2026-09-06) · B14 rules 8, 9, 31, 32 · BR-SHL-025 · NFR-3 · NFR-5
// generated: 2026-09-07 by the CR-075 wave T build lane
// checklist: A✔ B✔ C✔ D✔(GET /runbooks/{key}/domains/{parameter} · PUT /runbooks/{key}) E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest RunbookSetupPage.test.tsx · G13 · G31 (rule 21 — this file is under features/runbooks/, a DIRECTORY entry in route-b-migrated.txt)
// exceptions: an UNBOUNDED domain, `window`, `file` and `ref:setting` are drawn DISABLED with their reason rather than hidden, and none of them is sent
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
