// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-047 (an out-of-range reading flags, and never refuses) ·
//           US-WRK-049 (the rule column and the file column are different) ·
//           US-WRK-048 (the photograph, compressed at capture).
//           Screens: Work-012, Work-033
// Rules:    BR-WRK-039 (out of range FLAGS, never refuses) · BR-WRK-040 (a
//           missing REQUIRED photograph STOPS the close — two different rules,
//           two different sentences) · BR-WRK-047 (100 KB at capture) ·
//           hard rule 3 (a reading carries its unit) · B14 rule 21 (Tailwind
//           only; this file is on route-b-migrated.txt in the commit that
//           creates it) · rule 31 (no database id is a visible value) ·
//           rule 32 (one sentence per section) · rule 33 (a refusal caps at
//           five or six words)
// Tests:    src/features/work/mobile/ReadingsPane.dom.test.tsx
// Impacts:  06-backend/apps/work/evidence.py (#74, #77) · heldPanes.ts (this
//           file RELEASES the `readings` hold — same commit, law 2's mirror)
// ───────────────────────────────────────────────────────
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { capture, capturePhoto } from "./capture";
import { PhotoTooLarge } from "./compressPhoto";
import { loadCloseReadiness, type CloseReadiness, type ReadingRow } from "./evidenceEndpoints";
import { startFix } from "./location";
import { loadJob, mergeReadingIntoJob } from "./mobileEndpoints";
import { declaredPhotos } from "./offlineStore";

/**
 * `Work-012`'s Readings pane — what has to be measured, and what was.
 *
 * ⚠ **THE TWO RULES THIS SCREEN MUST NOT BLUR, AND THEY LOOK ALIKE.**
 *
 *   * `BR-WRK-039` — **out of range FLAGS and never refuses.** 1,204 on a dial
 *     bounded 0–999 is stored, shown in red, and the job still closes. The
 *     number is what the meter says.
 *   * `BR-WRK-040` — **a missing REQUIRED photograph STOPS the close.** Amber,
 *     and the job cannot be finished until somebody takes one.
 *
 * The rule's own text says *two different rules, two different sentences*, and
 * this component is where that is either honoured or lost. **They are rendered
 * in different colours, with different words, and the consequence line spells
 * out which is which** — because a screen that shows both as *check this*
 * teaches a technician that neither matters, and the one that does matter is
 * the one that stops a job closing at 16:55 on a Friday.
 *
 * ⚠ **THE VERDICT IS THE SERVER'S.** `can_close`, `blocking` and `flagged` all
 * come from `close_readiness()`; this component recomputes none of them. A
 * lane that derived *can close* here from the rows would create the second
 * opinion `BR-WRK-037`'s one-evaluator argument already rejected once — the
 * phone and the office disagreeing about whether a job may be finished.
 *
 * ⚠ **AND THE UNIT IS A COLUMN, NOT A WORD IN THE PROMPT** (hard rule 3). It
 * is displayed beside the input and sent with the value.
 */
export function ReadingsPane() {
  const { t } = useTranslation();
  const { orderId } = useParams();
  const [rows, setRows] = useState<ReadingRow[]>([]);
  const [ready, setReady] = useState<CloseReadiness | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!orderId) return;
    startFix(orderId); // BR-WRK-061 — the job's fix keeps improving here too
    const bundle = await loadJob(orderId);
    const declared = await declaredPhotos(orderId);
    // A photograph taken on this phone is TAKEN, whether or not its bytes have
    // reached the server yet (CR-168 §F: the link is pending, never missing).
    setRows(
      ((bundle?.readings as ReadingRow[] | undefined) ?? []).map((row) =>
        !row.photo_attachment_id && declared[row.id] ? { ...row, photo_attachment_id: "pending" } : row,
      ),
    );
    try {
      setReady(await loadCloseReadiness(orderId));
    } catch {
      // Offline. The rows still render from the store; only the verdict is
      // unavailable, and a missing verdict is shown as unknown rather than as
      // "you may close" — see the footer.
      setReady(null);
    }
  }, [orderId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function saveValue(row: ReadingRow, raw: string) {
    const isText = row.kind === "text";
    const saved = (isText ? row.value_text : row.value) ?? "";
    if (!orderId || raw.trim() === "" || raw.trim() === saved) return;
    setBusy(row.id);
    setRefusal(null);
    try {
      // ⚠ The unit goes with the number, always. See the component docstring.
      // CR-168-BRC10 §F — through the outbox like every other capture, so a
      // reading typed in a basement is kept and sent when there is a signal.
      // `DEF-WRK-10602` — a TEXT reading is words, sent in the phone's own text
      // shape (`field-app/tests/sync/support/jobReadingShapes.json`): no unit,
      // no figure. Sent as a figure it was refused `value_required`.
      const key = `reading-${row.id}-${Date.now()}`;
      const { sent } = await capture({
        orderId,
        kind: "reading",
        key,
        payload: isText
          ? { reading_id: row.id, value_text: raw.trim(), unable_to_read: false }
          : { reading_id: row.id, value: raw.trim(), unit: row.unit_of_measure },
      });
      const answer = sent?.flatMap((r) => r.items).find((i) => i.key === key);
      if (answer?.result === "refused") setRefusal(t("work.mobile.readings.save_failed"));
      // ⚠ **THE SERVER'S ROW GOES BACK INTO THE BUNDLE** (`DEF-WRK-4113`). The
      // pane renders from the store, so a screen that did not write the answer
      // back would show the value the technician typed and NONE of what the
      // server made of it — `in_range` above all, which is the whole rule.
      // Offline there is no answer yet: the typed value stands, unjudged.
      const detail = answer?.detail as ({ id?: string } & Record<string, unknown>) | null | undefined;
      await mergeReadingIntoJob(
        orderId,
        detail && detail.id
          ? (detail as { id: string })
          : isText
            ? { id: row.id, value_text: raw.trim() }
            : { id: row.id, value: raw.trim(), in_range: null },
      );
      await refresh();
    } catch {
      setRefusal(t("work.mobile.readings.save_failed"));
    } finally {
      setBusy(null);
    }
  }

  async function attach(row: ReadingRow, file: File) {
    if (!orderId) return;
    setBusy(row.id);
    setRefusal(null);
    try {
      // ⚠ COMPRESSED HERE, BEFORE IT LEAVES THE HANDSET (`BR-WRK-047`, the PO's
      // ruling of 2026-09-04). The raw original is never uploaded. CR-168 §F:
      // the photo's DATA joins the outbox and its link is made with it; the
      // bytes follow in the background. `refresh` reads the declared photo, so
      // *Photo needed to close.* does not survive the photograph (`DEF-WRK-4113`).
      await capturePhoto({ orderId, file, readingId: row.id });
      await refresh();
    } catch (error) {
      setRefusal(
        error instanceof PhotoTooLarge
          ? t("work.mobile.readings.photo_too_large")
          : t("work.mobile.readings.photo_failed"),
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="px-4 py-3">
      <h2 className="text-base font-semibold text-text">{t("work.mobile.readings.title")}</h2>

      <ul className="mt-3 divide-y divide-divider">
        {rows.map((row) => (
          <ReadingItem
            key={row.id}
            row={row}
            busy={busy === row.id}
            onSave={(value) => void saveValue(row, value)}
            onAttach={(file) => void attach(row, file)}
          />
        ))}
      </ul>

      {refusal ? (
        <p className="mt-3 text-sm text-danger-700" role="alert">
          {refusal}
        </p>
      ) : null}

      {ready ? <ReadinessFooter ready={ready} /> : null}
    </section>
  );
}

function ReadingItem({
  row,
  busy,
  onSave,
  onAttach,
}: {
  row: ReadingRow;
  busy: boolean;
  onSave: (value: string) => void;
  onAttach: (file: File) => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState((row.kind === "text" ? row.value_text : row.value) ?? "");
  // `DEF-WRK-10595` — a figure typed while its REQUIRED photo is missing is
  // HELD here, not sent, and goes out the moment the photo is attached.
  const [held, setHeld] = useState(false);

  // ⚠ THE RULE and THE FILE, read apart (`US-WRK-049`). `missingPhoto` is TRUE
  // only when the template asked AND nothing was taken. A reading that was
  // never asked for a photograph is not missing one.
  const missingPhoto = row.photo_required && !row.photo_attachment_id;
  const outOfRange = row.in_range === false;

  // MQ-020 (PO 2026-10-24, decision log "MQ-017: A STEP WITH A REQUIRED PHOTO
  // CANNOT BE MARKED DONE WITHOUT IT"): a reading whose photo is Required is not
  // saved until that photo exists — the phone's FF-20 rule, on this screen.
  // The server still accepts such a reading; the block is where the tap is.
  function commit(value: string) {
    if (missingPhoto) {
      setHeld(value.trim() !== "" && value.trim() !== ((row.kind === "text" ? row.value_text : row.value) ?? ""));
      return;
    }
    setHeld(false);
    onSave(value);
  }

  useEffect(() => {
    if (held && !missingPhoto) {
      setHeld(false);
      onSave(draft);
    }
    // Fires when the photograph arrives; `draft` and `onSave` are read as they stand then.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [missingPhoto]);

  return (
    <li className="py-3" data-reading-id={row.id}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-text">{row.prompt}</span>
        {/* Hard rule 3 — the unit is its own thing on screen, not a suffix
            buried in the prompt. */}
        <span className="text-xs text-neutral-600">{row.unit_of_measure}</span>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <input
          className="flex-1 border border-field-border bg-surface px-2 py-2 text-base text-text"
          inputMode={row.kind === "text" ? "text" : "decimal"}
          aria-label={row.prompt}
          aria-describedby={missingPhoto ? `reading-photo-${row.id}` : undefined}
          value={draft}
          disabled={busy}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => commit(draft)}
        />
        <label className="text-sm text-accent">
          {t("work.mobile.readings.camera")}
          <input
            type="file"
            accept="image/*"
            capture="environment"
            className="sr-only"
            aria-label={t("work.mobile.readings.camera")}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onAttach(file);
            }}
          />
        </label>
      </div>

      {/* ⚠ RED, AND IT DOES NOT BLOCK — `BR-WRK-039`. The value stands. */}
      {outOfRange ? (
        <p className="mt-1 text-sm text-danger-700" data-flag="out-of-range">
          {t("work.mobile.readings.out_of_range")}
        </p>
      ) : null}

      {/* ⚠ AMBER, AND IT DOES BLOCK — `BR-WRK-040`. A different colour and a
          different sentence from the one above, deliberately. */}
      {missingPhoto ? (
        <p id={`reading-photo-${row.id}`} className="mt-1 text-sm text-warning-700" data-flag="missing-photo">
          {t("work.mobile.readings.photoToSave", { count: 1 })}
        </p>
      ) : null}

      {/* Neither asked for nor taken is not a state worth a line of its own —
          B14 rule 32's description budget: a stated absence is CLOSED by
          default. Only the photograph that EXISTS is announced. */}
      {row.photo_attachment_id ? (
        <p className="mt-1 text-sm text-neutral-600" data-flag="photo-taken">
          {t("work.mobile.readings.photo_taken")}
        </p>
      ) : null}
    </li>
  );
}

/**
 * The footer sentence and the consequence line.
 *
 * ⚠ **THE CONSEQUENCE LINE IS THE ONE PIECE OF COPY THAT KEEPS THE TWO RULES
 * APART IN A TECHNICIAN'S HEAD**, and it is why it is worth its own paragraph
 * against B14 rule 32's description budget: *Required means the job will not
 * close without it; out of range never blocks.* Without it, a red line and an
 * amber line look like two shades of the same warning.
 */
function ReadinessFooter({ ready }: { ready: CloseReadiness }) {
  const { t } = useTranslation();
  return (
    <div className="mt-4 border-t border-divider pt-3">
      <p className="text-sm text-neutral-600">
        {t("work.mobile.readings.footer", {
          captured: ready.readings_captured,
          total: ready.readings_total,
          photos: ready.required_photos_taken,
          photosTotal: ready.required_photos_total,
        })}
      </p>
      <p className="mt-2 text-sm text-neutral-700" data-consequence>
        {t("work.mobile.readings.consequence")}
      </p>
    </div>
  );
}
