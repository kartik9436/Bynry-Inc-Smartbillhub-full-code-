// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-008 (EP-SHL-02 §Stories)  Screens: every export-declaring list/report (S17, S30, S33, S44, S46, …)
// Rules:    BR-SHL-016 (server-side export, guards) · BR-SHL-029 (50k cap, money-export audit) · IS-11 (CSV always, PDF where formatted, no XLSX)
// ───────────────────────────────────────────────────────
// FE-14 DownloadButton (B13 §1): THE one download control, filling DataTable's
// IS-9 `downloadSlot` and the report screens' download row. IS-11 by
// construction: CSV is ALWAYS offered; PDF appears only where the screen
// declares a formatted layout (`pdf` prop); XLSX does not exist in v1 (no
// prop can ask for it). This control is UI only — it reports the chosen
// format to `onDownload`. Execution is server-side and lands with BE-21:
// streamed under RLS, current filters + visible columns (IS-9), the 50,000-row
// cap and the money-export audit_log row (BR-SHL-016/029) — none of that is
// the button's, so none of it is faked here.
import { useTranslation } from "react-i18next";

import { currentScreenId, track } from "@/analytics";

import { Button, ButtonSummary } from "./Button";
import { DownloadIcon } from "./icons";

export type DownloadFormat = "csv" | "pdf";

export interface DownloadButtonProps {
  // The consuming screen's export handler — wired to the real endpoint when
  // BE-21/FI-01 land. Receives which IS-11 format the user chose.
  onDownload: (format: DownloadFormat) => void;
  pdf?: boolean; // IS-11: PDF only where a formatted layout matters
  disabled?: boolean; // e.g. US-SHL-014 disabled-with-reason gating (title from consumer)
}

export function DownloadButton(props: DownloadButtonProps) {
  const { t } = useTranslation();
  // CR-169-BRC10 — `report_downloaded`: which screen's report and which format,
  // never its filters or rows. The screen id is the one `<body>` carries.
  const download = (format: DownloadFormat) => {
    track("report_downloaded", { report: currentScreenId() ?? "unregistered", format });
    props.onDownload(format);
  };

  if (props.pdf !== true || props.disabled === true) {
    // CSV-only screens get a plain button; a disabled control also renders as
    // one (a <summary> cannot be disabled, and a dead menu helps no one).
    return (
      // CR-018 Route B: DownloadButton.css (deleted) ported value for value.
      // `.download-button` only stopped the label wrapping (DEF-327 note);
      // `data-download="button"` carries the handle 12 test files grep for.
      // ⚠ **ICON-ONLY SINCE CR-045 A.3.** This read `Download CSV` in words and
      // cost ~130px of a toolbar the code already measures as over budget —
      // ~1,360px of controls in ~1,150px of room on the reads list (DEF-1085).
      // The glyph gives ~95px back, and that refund is what pays for the search
      // box growing to 320px in A.1; the two are one change in two files.
      //
      // The SENTENCE is not lost, it moves: `download.csv` is now the
      // `aria-label` AND the `title`, so a screen reader hears exactly what a
      // pointer user reads on hover. Same key, same string, no catalogue edit —
      // which is also why wave A touches no locale file (CR-045 step 6).
      <Button
        variant="secondary"
        className="h-9 w-9 justify-center px-0"
        data-download="button"
        disabled={props.disabled}
        aria-label={t("download.csv")}
        title={t("download.csv")}
        onClick={() => download("csv")}
      >
        <DownloadIcon />
      </Button>
    );
  }

  return (
    // Same boring <details> popover pattern as DataTable's column chooser.
    // CR-018 Route B: `.download-menu` -> relative; its `[open] > summary`
    // state rule -> the `[[open]>&]:` arbitrary variant on the summary itself
    // (the 7% ink wash long-hand in srgb) — Tailwind's `group` marker class
    // generates no rule of its own, which the Route B check rightly refuses.
    // The summary's killed disclosure marker -> list-none
    // + the -webkit-details-marker arbitrary variant; `.download-menu-list` ->
    // the same anchored popover utilities FilterBar and DataTable already use
    // (no border here — this one never had one).
    <details className="relative" data-download="menu">
      {/* A <summary> is the open-control of a <details> disclosure and cannot be a
          <button> without losing that behaviour — hence its own wrapper. */}
      {/* ⚠ **THE TRIGGER CHANGES; THE MENU DOES NOT (CR-045 A.3).** The two
          items below still read `Download CSV` and `Download PDF` in words,
          because a menu item is a choice and a choice needs a name. Only the
          control that OPENS it becomes a glyph, so both variants of this button
          occupy the same 36px square and a toolbar's width no longer depends on
          whether its screen happens to offer a PDF. */}
      <ButtonSummary
        className="h-9 w-9 justify-center px-0 list-none [&::-webkit-details-marker]:hidden [[open]>&]:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
        aria-label={t("download.csv")}
        title={t("download.csv")}
      >
        <DownloadIcon />
      </ButtonSummary>
      <div className="absolute right-0 top-[calc(100%+var(--space-1))] z-40 flex min-w-[180px] flex-col items-stretch gap-1 bg-surface p-2 shadow-md">
        {/* `.download-menu-list .btn { justify-content: flex-start }` was a PARENT
            rule; Route B has no parent selector, so it travels down here. The kit
            drops its own `justify-center` because the two fill the same slot —
            appending would have been a coin toss (buttonKit.ts). */}
        <Button variant="ghost" className="justify-start" onClick={() => download("csv")}>
          {t("download.csv")}
        </Button>
        <Button variant="ghost" className="justify-start" onClick={() => download("pdf")}>
          {t("download.pdf")}
        </Button>
      </div>
    </details>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-008@17df6a0 (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
