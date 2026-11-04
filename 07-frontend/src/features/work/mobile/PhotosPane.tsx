// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-048 (three document kinds, and the compression that pays
//           for them).  Screens: Work-012, Work-033
// Rules:    BR-WRK-047 (compressed AT CAPTURE to 100 KB max; the row is
//           written with a per-image idempotency key) · BR-WRK-047a (the
//           upload goes through the application) · BR-WRK-048 (twelve months,
//           then an export before deletion — nothing here says "forever") ·
//           B14 rule 21 · rule 31 (no database id is a visible value) ·
//           rule 32 · rule 33
// Tests:    src/features/work/mobile/PhotosPane.dom.test.tsx
// Impacts:  06-backend/apps/work/evidence.py (#77) · heldPanes.ts (this file
//           RELEASES the `photos` hold — same commit, law 2's mirror)
// ───────────────────────────────────────────────────────
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { capturePhoto } from "./capture";
import { PhotoTooLarge } from "./compressPhoto";
import { loadAttachments, type AttachmentRow } from "./evidenceEndpoints";
import { onStoreChange, pendingPhotos } from "./offlineStore";

/**
 * `Work-012`'s photographs — the ones that belong to the job rather than to a
 * checklist row.
 *
 * ⚠ **A PHOTOGRAPH HERE BELONGS TO THE JOB AND NOT TO A READING**, and that is
 * why this pane exists beside the Readings pane rather than instead of it. The
 * state of a meter cupboard, a damaged seal, the van's parking spot — none of
 * them is evidence OF a particular reading, and attaching them to one would
 * make `Work-033`'s *2 of 3 required photographs* count wrong. The camera on a
 * reading row attaches to that reading; the camera here attaches to neither a
 * reading nor a task.
 *
 * ⚠ **NOTHING ON THIS SCREEN SAYS A PHOTOGRAPH IS KEPT FOREVER** (`BR-WRK-048`).
 * The regime is twelve months and then an export before deletion, and until
 * that export exists nothing is deleted at all — but *kept* is not *kept
 * forever*, and a reassuring word here would be the kind of promise the product
 * cannot make.
 *
 * ⚠ **THE COMPRESSION IS NOT OPTIONAL AND IT FAILS LOUDLY.** `compressPhoto`
 * throws rather than sending something the server will refuse, so a technician
 * finds out with the meter still in front of them rather than at sync time,
 * hours later and off site.
 */
export function PhotosPane() {
  const { t } = useTranslation();
  const { orderId } = useParams();
  const [rows, setRows] = useState<AttachmentRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [waiting, setWaiting] = useState(0);

  const refresh = useCallback(async () => {
    if (!orderId) return;
    // CR-168 §F — photographs taken here whose bytes have not reached the
    // server yet. Counted, never hidden: they are on this phone and will go.
    setWaiting((await pendingPhotos()).filter((p) => p.orderId === orderId).length);
    try {
      setRows(await loadAttachments(orderId));
    } catch {
      // Offline is not an error here — the list is simply what has reached the
      // server so far, and the technician knows they have no signal.
      setRows([]);
    }
  }, [orderId]);

  useEffect(() => {
    void refresh();
    return onStoreChange(() => void refresh());
  }, [refresh]);

  async function take(file: File) {
    if (!orderId) return;
    setBusy(true);
    setRefusal(null);
    try {
      // CR-168 §F — a job photograph (no task, no reading): its data joins the
      // outbox with its own link, its bytes follow in the background.
      await capturePhoto({ orderId, file });
      await refresh();
    } catch (error) {
      setRefusal(
        error instanceof PhotoTooLarge
          ? t("work.mobile.photos.too_large")
          : t("work.mobile.photos.failed"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="px-4 py-3">
      <h2 className="text-base font-semibold text-text">{t("work.mobile.photos.title")}</h2>

      <label className="mt-3 block text-sm text-accent">
        {t("work.mobile.photos.camera")}
        <input
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          disabled={busy}
          aria-label={t("work.mobile.photos.camera")}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void take(file);
          }}
        />
      </label>

      <ul className="mt-3 divide-y divide-divider">
        {rows.map((row) => (
          <li key={row.id} className="py-2 text-sm text-neutral-700" data-attachment>
            {/*
              B14 rule 31 — no database id is a visible value. What identifies a
              photograph to a person is WHEN it was taken and on WHICH handset,
              which is also what a supervisor reviewing a dispute asks for.
            */}
            {t("work.mobile.photos.row", {
              taken: new Date(row.taken_at).toLocaleTimeString(),
              device: row.device || t("work.mobile.photos.unknown_device"),
            })}
          </li>
        ))}
      </ul>

      {waiting > 0 ? (
        <p className="mt-3 text-sm text-neutral-600" data-testid="photos-waiting">
          {t("work.mobile.photos.waiting", { count: waiting })}
        </p>
      ) : null}

      {rows.length === 0 && waiting === 0 ? (
        <p className="mt-3 text-sm text-neutral-600">{t("work.mobile.photos.none")}</p>
      ) : null}

      {refusal ? (
        <p className="mt-3 text-sm text-danger-700" role="alert">
          {refusal}
        </p>
      ) : null}
    </section>
  );
}
