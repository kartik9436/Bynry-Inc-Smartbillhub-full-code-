// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F6 — the Wording panel (`02`, `03`, `04`, `05`, `14`)
// Rules:    BR-BIL-026 (an edit is a new version) · CR-007 (*"subject line
//           (email)"*) · E4 (the locked rights blocks beside the words) · PO
//           rulings 2A (a simple rich editor) · A2 A (allowed placeholders only)
//           · B14 rules 33 · 43 · 44
// ───────────────────────────────────────────────────────
// THE LEFT HALF OF THE WORKSPACE: what the template SAYS.
//
//   Wording            [Rich | Plain text] [+ Insert placeholder]
//   Subject            (email only)
//   Message            [Bold] [Link] [Button] [List]   (rich only)
//   ┌───────────────────────────────┐
//   │ Hello {first_name}, …         │
//   └───────────────────────────────┘
//                                    249 characters   (a text: · 1 text)
//
// ⚠ **VIEWING AND EDITING ARE THE SAME PANEL.** The drawing shows the wording
// beside the preview in both modes; viewing greys the fields and switches off
// the controls that change them. That replaces CR-076's two layouts (a reading
// view with a rail, an editor with a different rail) — `CR-199-BRC10` §6 W4.
// The fields are `readOnly`, not `disabled`, so a clerk can still select and
// copy the wording they are reading.
//
// ⚠ **THE MARKUP THE TOOLBAR WRITES IS THE SERVER'S TO DEFINE.** The README
// beside the drawing says so: *"the storage format is the server lane's
// decision, provided it is a closed safe set and never raw HTML"*. So the
// format bar takes a `syntax` and draws NOTHING without one — a Bold button
// that typed a spelling the renderer then printed as asterisks would be a
// control that lies.
import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { TemplateDetail, TemplatePreview } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { SegmentedControl } from "@/components/SegmentedControl";
import { smsCost } from "./smsSegments";
import { TemplatePlaceholderPicker } from "./TemplatePlaceholderPicker";
import type { PlaceholderRow } from "./TemplatePlaceholderPicker";
import { placeholderName } from "./TemplatePlaceholderPicker";

/** How the rich format spells each of the four things the bar makes. Served
 *  by the server's rich-format contract; the screen never invents one. */
export interface RichSyntax {
  bold: (text: string) => string;
  link: (text: string, href: string) => string;
  button: (text: string, href: string) => string;
  listItem: (text: string) => string;
}

export type WordingFormat = "rich" | "plain";

/** The locked phrases a template may never be saved without (E4). Drawn once
 *  over the list, never once per phrase (`DEF-NOT-4464`). */
export function LockedPhrases(props: { phrases: readonly string[]; idPrefix: string }) {
  const { t } = useTranslation();
  if (props.phrases.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 flex flex-wrap items-baseline gap-2 font-heading text-sm font-semibold">
        <span aria-hidden="true">🔒</span>
        <span>{t("templates.detail.lockedBlock")}</span>
      </p>
      {props.phrases.map((phrase, index) => (
        <div
          key={phrase}
          className="border border-divider bg-bg px-3 py-2 text-sm"
          data-testid={`${props.idPrefix}-${index}`}
          role="note"
        >
          <p className="m-0">{phrase}</p>
        </div>
      ))}
    </div>
  );
}

function Counter(props: {
  data: TemplateDetail;
  kind: string;
  body: string;
  preview: TemplatePreview | null;
}) {
  const { t } = useTranslation();
  if (props.kind !== "sms") {
    return (
      <p className="m-0 self-end text-sm tabular-nums" data-testid="wording-count">
        {t("templates.workspace.characters", { count: props.body.length })}
      </p>
    );
  }
  /* A text message's count is the RENDERED length when the server has
     rendered it — `{amount_due}` is eleven characters in the box and six on a
     phone — and the typed length until then (`CR-199-BRC10` §6 W21). */
  const length = props.preview?.rendered_length ?? props.body.length;
  const cost = smsCost(length, props.data.sms_character_counter);
  return (
    <p
      className="m-0 flex flex-wrap justify-end gap-3 text-sm tabular-nums"
      data-testid="sms-meter"
    >
      <span data-testid="sms-meter-count">
        {t("templates.workspace.characters", { count: cost.length })}
      </span>
      <span data-testid="sms-meter-segments">
        {t("templates.detail.smsSegments", { count: cost.segments })}
      </span>
      <span data-testid="sms-meter-remaining">
        {t("templates.detail.smsRemaining", { count: cost.remaining })}
      </span>
      {cost.overSegment && (
        <span className="font-semibold text-warning-700" data-testid="sms-cost-warning">
          {t("templates.detail.smsCostWarning", { count: cost.segments })}
        </span>
      )}
    </p>
  );
}

function FormatBar(props: {
  syntax: RichSyntax;
  disabled: boolean;
  onWrap: (make: (selected: string) => string) => void;
}) {
  const { t } = useTranslation();
  const tools: { key: string; label: string; make: (selected: string) => string }[] = [
    { key: "bold", label: t("templates.workspace.bold"), make: (s) => props.syntax.bold(s) },
    { key: "link", label: t("templates.workspace.link"), make: (s) => props.syntax.link(s, "") },
    {
      key: "button",
      label: t("templates.workspace.button"),
      make: (s) => props.syntax.button(s, ""),
    },
    {
      key: "list",
      label: t("templates.workspace.list"),
      make: (s) =>
        s
          .split("\n")
          .map((line) => props.syntax.listItem(line))
          .join("\n"),
    },
  ];
  return (
    <div
      className="flex flex-wrap gap-1 border border-b-0 border-divider bg-bg p-1"
      role="toolbar"
      aria-label={t("templates.workspace.formatting")}
      data-testid="format-bar"
    >
      {tools.map((tool) => (
        <Button
          key={tool.key}
          variant="secondary"
          size="sm"
          disabled={props.disabled}
          onClick={() => props.onWrap(tool.make)}
          data-testid={`format-${tool.key}`}
        >
          {tool.label}
        </Button>
      ))}
    </div>
  );
}

export function TemplateWordingPane(props: {
  data: TemplateDetail;
  /** `email` · `sms` · `printable` · `in_app` · `contract` — the composer's
   *  shape follows the CLASS, never the preview tab. */
  kind: string;
  body: string;
  subject: string;
  onBody: (value: string) => void;
  onSubject: (value: string) => void;
  editing: boolean;
  /** The server's render of what is in the box, for the text counter. */
  preview: TemplatePreview | null;
  /** Rich / Plain — drawn only when the server serves a rich format for this
   *  template; `null` hides the switch AND the format bar. */
  format: {
    value: WordingFormat;
    syntax: RichSyntax;
    onChange: (next: WordingFormat) => void;
  } | null;
  /** Anything that belongs at the foot of the panel. */
  footer?: ReactNode;
}) {
  const { t } = useTranslation();
  const ids = useId();
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);
  const [picking, setPicking] = useState(false);
  const rich = props.format !== null && props.format.value === "rich";

  /* ⚠ DEF-NOT-10677 — WHERE THE CURSOR GOES AFTER AN INSERT. Measured in
     Chromium on the walk: once a format button or the placeholder picker
     takes focus, the textarea's own selection is reset to 0 (React rewrites
     its `defaultValue`, and opening the picker resets it again), so the next
     placeholder landed at the top of the email. jsdom keeps the selection,
     which is why no dom test saw it.
     So the pane REMEMBERS the caret: where it was when focus left the box,
     and the point just after anything inserted. A read
     while the box has focus trusts the box; otherwise the remembered caret
     wins, and the box's own selection is only the last resort. */
  const caretRef = useRef<[number, number] | null>(null);
  const pendingRef = useRef<number | null>(null);

  function caretNow(): [number, number] {
    const area = bodyRef.current;
    if (area !== null && document.activeElement === area) {
      return [area.selectionStart, area.selectionEnd];
    }
    if (caretRef.current !== null) return caretRef.current;
    if (area !== null) return [area.selectionStart, area.selectionEnd];
    return [props.body.length, props.body.length];
  }

  /** On BLUR — the moment focus leaves for a format button or the picker,
   *  while the box still holds the clerk's own selection. */
  function remember(event: { currentTarget: HTMLTextAreaElement }) {
    const area = event.currentTarget;
    caretRef.current = [area.selectionStart, area.selectionEnd];
  }

  useLayoutEffect(() => {
    const area = bodyRef.current;
    const caret = pendingRef.current;
    if (caret !== null && area !== null) {
      pendingRef.current = null;
      area.setSelectionRange(caret, caret);
    }
  }, [props.body]);

  function replaceRange(start: number, end: number, text: string) {
    const at = Math.min(start, props.body.length);
    const to = Math.min(Math.max(end, at), props.body.length);
    caretRef.current = [at + text.length, at + text.length];
    pendingRef.current = at + text.length;
    props.onBody(props.body.slice(0, at) + text + props.body.slice(to));
  }

  /** Replace the selection (or insert at the cursor) with `text`. */
  function insertAtCursor(text: string) {
    const [start, end] = caretNow();
    replaceRange(start, end, text);
  }

  function wrapSelection(make: (selected: string) => string) {
    const [start, end] = caretNow();
    replaceRange(start, end, make(props.body.slice(start, end)));
  }

  function insertPlaceholder(row: PlaceholderRow) {
    /* A link placeholder goes in as a BUTTON in rich text (`03`: *"Links go
       in as a button"*), labelled with its own name. In plain text, and in
       any format the server has not given us a button for, it goes in bare. */
    if (rich && row.kind === "link" && props.format !== null) {
      insertAtCursor(props.format.syntax.button(placeholderName(row), row.insert));
      return;
    }
    insertAtCursor(row.insert);
  }

  const field =
    "w-full border border-field-border px-3 py-2 text-md " +
    (props.editing ? "bg-field-fill" : "bg-bg");

  return (
    <section
      className="flex min-w-0 flex-col gap-3 border border-divider bg-surface p-4"
      aria-labelledby={`${ids}-title`}
      data-testid="wording-pane"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`${ids}-title`} className="m-0 font-heading text-lead font-semibold">
          {t("templates.workspace.wording")}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          {props.format !== null && props.kind === "email" && (
            <SegmentedControl
              label={t("templates.workspace.format")}
              segments={[
                { id: "rich", label: t("templates.workspace.rich") },
                { id: "plain", label: t("templates.workspace.plain") },
              ]}
              active={props.format.value}
              purpose="choice"
              name="wording-format"
              readOnly={!props.editing}
              onSelect={(id) => props.format?.onChange(id === "plain" ? "plain" : "rich")}
            />
          )}
          {/* A class nobody has defined placeholders for says so ON the
              control — the server's sentence, in every mode (DEF-163: it is a
              different absence from "nobody has written this letter", with a
              different fix, and both stay visible). */}
          <Button
            variant="secondary"
            disabled={!props.editing || props.data.catalog_unavailable !== null}
            title={
              props.data.catalog_unavailable ??
              (props.editing ? undefined : t("templates.workspace.editFirst"))
            }
            aria-expanded={picking}
            onClick={() => setPicking(!picking)}
            data-testid="insert-placeholder"
          >
            {t("templates.workspace.insertPlaceholder")}
          </Button>
        </div>
      </div>

      {props.kind === "email" && (
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-subject`} className="text-sm">
            {t("templates.detail.subject")}
          </label>
          <input
            id={`${ids}-subject`}
            className={field}
            value={props.subject}
            readOnly={!props.editing}
            onChange={(event) => props.onSubject(event.target.value)}
            data-testid="editor-subject"
          />
        </div>
      )}

      <div className="flex flex-col gap-1">
        <label htmlFor={`${ids}-body`} className="text-sm">
          {t("templates.workspace.message")}
        </label>
        {rich && props.format !== null && (
          <FormatBar
            syntax={props.format.syntax}
            disabled={!props.editing}
            onWrap={wrapSelection}
          />
        )}
        <textarea
          id={`${ids}-body`}
          ref={bodyRef}
          onBlur={remember}
          className={`${field} min-h-64 resize-y font-mono text-sm`}
          value={props.body}
          rows={props.kind === "sms" ? 8 : 14}
          readOnly={!props.editing}
          onChange={(event) => props.onBody(event.target.value)}
          data-testid="editor-body"
        />
        <Counter data={props.data} kind={props.kind} body={props.body} preview={props.preview} />
      </div>

      <LockedPhrases phrases={props.data.mandatory_content} idPrefix="locked-block" />

      {picking && props.editing && (
        <TemplatePlaceholderPicker
          data={props.data}
          onInsert={insertPlaceholder}
          onClose={() => setPicking(false)}
        />
      )}
      {props.footer}
    </section>
  );
}
