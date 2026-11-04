// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F6 — the placeholder picker (`03`)
// Rules:    PO ruling A2 A (placeholders only from the allowed list) · B14
//           rules 31 · 33 · 43 · US-NOT-005 TC-5 (an unknown token is refused)
// ───────────────────────────────────────────────────────
// `+ Insert placeholder` OPENS THIS: a search box and the template's own
// allowed placeholders, each drawn as its name, its `{key}`, a *link* tag when
// it fills with an address, and what it fills with *(e.g. Pat Rivera)*.
// Clicking one inserts it at the cursor; a link placeholder goes in AS A
// BUTTON in rich text (`[[Label|{key}]]`) — the drawing's *"Links go in as a
// button"*, and PO defect #6 (*"links not clickable"*).
//
// ⚠ **THE LIST IS THE SERVER'S WHITELIST AND NOTHING ELSE.** It is
// `merge_field_rows` — the same list the save validates against — so a token
// this picker offers is a token the save accepts. It replaces the merge-field
// RAIL panel (`CR-199-BRC10` §6 W11), and keeps what that panel showed: every
// token with what it resolves to, or why it has no sample.
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import type { TemplateDetail } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { RefusalStrip } from "@/components/Surfaces";

export type PlaceholderRow = TemplateDetail["merge_field_rows"][number];

/** A placeholder's visible name: the server's `label` when it serves one, else
 *  the key in words (`account_no` → `Account no`). Never the raw key alone —
 *  the key is drawn beside it in code type. */
export function placeholderName(row: PlaceholderRow): string {
  if (row.label != null && row.label !== "") {
    return row.label;
  }
  const words = row.token.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function TemplatePlaceholderPicker(props: {
  data: TemplateDetail;
  onInsert: (row: PlaceholderRow) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const searchId = useId();
  const [query, setQuery] = useState("");
  if (props.data.catalog_unavailable !== null) {
    return (
      <RefusalStrip role="note" data-testid="merge-fields-unavailable">
        {props.data.catalog_unavailable}
      </RefusalStrip>
    );
  }
  const needle = query.trim().toLowerCase();
  const rows = props.data.merge_field_rows.filter(
    (row) =>
      needle === "" ||
      row.token.toLowerCase().includes(needle) ||
      placeholderName(row).toLowerCase().includes(needle) ||
      (row.description ?? "").toLowerCase().includes(needle),
  );
  return (
    <section
      className="flex flex-col gap-2 border border-divider bg-bg p-4"
      aria-label={t("templates.workspace.placeholders")}
      data-testid="placeholder-picker"
    >
      <div className="flex items-center justify-between gap-2">
        <h4 className="m-0 font-heading text-base font-semibold">
          {t("templates.workspace.placeholders")}
        </h4>
        <Button
          variant="ghost"
          size="sm"
          aria-label={t("templates.workspace.closePlaceholders")}
          title={t("templates.workspace.closePlaceholders")}
          onClick={props.onClose}
          data-testid="placeholder-close"
        >
          ×
        </Button>
      </div>
      <label className="sr-only" htmlFor={searchId}>
        {t("templates.workspace.searchPlaceholders")}
      </label>
      <input
        id={searchId}
        type="search"
        value={query}
        placeholder={t("templates.workspace.searchPlaceholders")}
        onChange={(event) => setQuery(event.target.value)}
        data-testid="placeholder-search"
      />
      <ul
        className="m-0 flex max-h-80 list-none flex-col gap-2 overflow-y-auto p-0"
        data-testid="merge-fields"
      >
        {rows.map((row) => (
          /* The CARD is the list item (border, fill, the accent on hover and on
             keyboard focus); the control inside it is a bare full-width button
             with no box of its own — so the whole card is one click, and the
             kit's rule that a boxed control is a `Button` (G86) holds. */
          <li
            key={row.token}
            className="border border-divider bg-surface hover:border-accent focus-within:border-accent"
            data-testid={`merge-field-${row.token}`}
          >
            <button
              type="button"
              className="flex w-full cursor-pointer flex-col items-start gap-1 border-0 bg-transparent px-3 py-2 text-left"
              onClick={() => props.onInsert(row)}
              data-testid={`insert-${row.token}`}
              data-derived-spelling={row.derived_spelling ? "true" : undefined}
            >
              <span className="flex flex-wrap items-baseline gap-2">
                <span className="font-semibold text-text">{placeholderName(row)}</span>
                <code className="text-sm text-info-700">{row.insert}</code>
                {row.kind === "link" && (
                  <span className="bg-info-100 px-1 text-xs font-semibold text-info-700">
                    {t("templates.workspace.linkTag")}
                  </span>
                )}
              </span>
              <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                {row.description != null && row.description !== "" && (
                  <>
                    {row.description}
                    {" · "}
                  </>
                )}
                {row.sample_value !== null ? (
                  t("templates.workspace.example", { value: row.sample_value })
                ) : (
                  <span data-testid={`merge-absent-${row.token}`}>{row.sample_unavailable}</span>
                )}
              </span>
            </button>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="text-sm" data-testid="placeholder-none">
            {t("templates.workspace.noPlaceholderMatch")}
          </li>
        )}
      </ul>
      <p className="m-0 max-w-measure text-sm" data-desc data-testid="placeholder-hint">
        {t("templates.workspace.placeholderHint")}
      </p>
      {/* US-NOT-016 — the custom-field SHAPE the merge-field panel listed,
          kept (`CR-199-BRC10` §6 W11). */}
      {props.data.custom_field_variables.length > 0 && (
        <ul
          className="m-0 flex list-none flex-wrap gap-2 p-0 text-sm"
          data-testid="custom-field-shape"
        >
          {props.data.custom_field_variables.map((shape) => (
            <li key={shape}>
              <code>{shape}</code>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
