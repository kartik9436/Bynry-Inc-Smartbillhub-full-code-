// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-036 (the customer signs, or refuses).  Screens: Work-012,
//           Work-008 (the Customer tab reads what this writes)
// Rules:    BR-WRK-046 (a signature is a printed name plus an image, with who
//           captured it and when; a refusal records the decline reason and a
//           photograph of the door hanger INSTEAD) · BR-WRK-047 (100 KB) ·
//           B14 rule 21 · rule 31 · rule 32 · rule 33
// Tests:    src/features/work/mobile/SignaturePane.dom.test.tsx
// Impacts:  06-backend/apps/work/evidence.py (#79) · heldPanes.ts (this file
//           RELEASES the `signature` hold — same commit, law 2's mirror)
// ───────────────────────────────────────────────────────
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { compressPhoto } from "./compressPhoto";
import { captureToken } from "./offlineStore";
import {
  loadSignature,
  postAttachment,
  postSignature,
  type SignatureRow,
} from "./evidenceEndpoints";

/**
 * `Work-012`'s signature pane — one answer per job, and it is one of two.
 *
 * ⚠ **SIGNED OR REFUSED, NEVER BOTH** (`BR-WRK-046`; r10 verbatim: *"if
 * refused, record decline reason and photo of door hanger"*). The screen is
 * two modes rather than one form with optional fields, and that is not a
 * layout preference: a form that showed a name box and a decline box together
 * invites a technician to fill in both, and the result is a row that is not a
 * record of anything that happened. The database refuses it
 * (`ck_work_order_signatures_shape`) and this screen never offers it.
 *
 * ⚠ **THE PRINTED NAME IS REQUIRED, AND IT IS NOT DECORATION.** A signature is
 * a squiggle on glass. Six months later, in a dispute, the typed name beside it
 * is the only thing that says WHO made the mark — which is the entire reason
 * the signature is captured at all.
 *
 * ⚠ **A REFUSAL NEEDS ITS PHOTOGRAPH.** Without the door-hanger picture the
 * row is an unevidenced claim that somebody declined, which is exactly the
 * thing a dispute turns on. The Refused mode therefore takes the photograph
 * FIRST and only then offers to save.
 */
export function SignaturePane() {
  const { t } = useTranslation();
  const { orderId } = useParams();
  const [existing, setExisting] = useState<SignatureRow>(null);
  const [mode, setMode] = useState<"sign" | "refuse">("sign");
  const [printedName, setPrintedName] = useState("");
  const [declineReason, setDeclineReason] = useState("");
  const [hangerId, setHangerId] = useState<string | null>(null);
  const [refusalMessage, setRefusalMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const padRef = useRef<HTMLCanvasElement | null>(null);
  const drawn = useRef(false);

  const refresh = useCallback(async () => {
    if (!orderId) return;
    try {
      setExisting(await loadSignature(orderId));
    } catch {
      setExisting(null);
    }
  }, [orderId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function saveSigned() {
    if (!orderId || !padRef.current) return;
    if (!printedName.trim()) {
      setRefusalMessage(t("work.mobile.signature.name_required"));
      return;
    }
    if (!drawn.current) {
      setRefusalMessage(t("work.mobile.signature.mark_required"));
      return;
    }
    setBusy(true);
    setRefusalMessage(null);
    try {
      const blob = await canvasBlob(padRef.current);
      await postSignature(orderId, {
        refused: false,
        printedName: printedName.trim(),
        image: blob,
        captureToken: await captureToken(),
      });
      await refresh();
    } catch {
      setRefusalMessage(t("work.mobile.signature.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  async function takeHanger(file: File) {
    if (!orderId) return;
    setBusy(true);
    setRefusalMessage(null);
    try {
      const small = await compressPhoto(file);
      const attachment = await postAttachment(orderId, {
        file: small,
        idempotencyKey: `hanger-${Date.now()}`,
        takenAt: new Date().toISOString(),
      });
      setHangerId(attachment.id);
    } catch {
      setRefusalMessage(t("work.mobile.signature.photo_failed"));
    } finally {
      setBusy(false);
    }
  }

  async function saveRefused() {
    if (!orderId) return;
    if (!declineReason.trim()) {
      setRefusalMessage(t("work.mobile.signature.reason_required"));
      return;
    }
    if (!hangerId) {
      setRefusalMessage(t("work.mobile.signature.hanger_required"));
      return;
    }
    setBusy(true);
    setRefusalMessage(null);
    try {
      await postSignature(orderId, {
        refused: true,
        declineReason: declineReason.trim(),
        doorHangerAttachmentId: hangerId,
        captureToken: await captureToken(),
      });
      await refresh();
    } catch {
      setRefusalMessage(t("work.mobile.signature.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  // ⚠ ONE ANSWER PER JOB. Once it exists the pane shows it and offers nothing —
  // a second signature would raise *which of these two is the customer's
  // answer*, and there is no lawful reading of that.
  if (existing) {
    return (
      <section className="px-4 py-3">
        <h2 className="text-base font-semibold text-text">
          {t("work.mobile.signature.title")}
        </h2>
        <p className="mt-2 text-sm text-text" data-signature-state={existing.refused ? "refused" : "signed"}>
          {existing.refused
            ? t("work.mobile.signature.was_refused", { reason: existing.decline_reason })
            : t("work.mobile.signature.was_signed", { name: existing.printed_name })}
        </p>
      </section>
    );
  }

  return (
    <section className="px-4 py-3">
      <h2 className="text-base font-semibold text-text">{t("work.mobile.signature.title")}</h2>

      {/* Two MODES, never one form with both halves. See the docstring. */}
      <div className="mt-3 flex gap-2" role="tablist">
        <ModeTab active={mode === "sign"} onClick={() => setMode("sign")}>
          {t("work.mobile.signature.mode_sign")}
        </ModeTab>
        <ModeTab active={mode === "refuse"} onClick={() => setMode("refuse")}>
          {t("work.mobile.signature.mode_refuse")}
        </ModeTab>
      </div>

      {mode === "sign" ? (
        <div className="mt-3">
          <label className="block text-sm text-neutral-700" htmlFor="printed-name">
            {t("work.mobile.signature.printed_name")}
          </label>
          <input
            id="printed-name"
            className="mt-1 w-full border border-field-border bg-surface px-2 py-2 text-base text-text"
            value={printedName}
            disabled={busy}
            onChange={(event) => setPrintedName(event.target.value)}
          />
          <SignaturePad padRef={padRef} drawn={drawn} />
          <button
            type="button"
            className="mt-3 w-full bg-accent px-3 py-3 text-sm font-semibold text-bg"
            disabled={busy}
            onClick={() => void saveSigned()}
          >
            {t("work.mobile.signature.save_signed")}
          </button>
        </div>
      ) : (
        <div className="mt-3">
          <label className="block text-sm text-neutral-700" htmlFor="decline-reason">
            {t("work.mobile.signature.decline_reason")}
          </label>
          <input
            id="decline-reason"
            className="mt-1 w-full border border-field-border bg-surface px-2 py-2 text-base text-text"
            value={declineReason}
            disabled={busy}
            onChange={(event) => setDeclineReason(event.target.value)}
          />
          <label className="mt-3 block text-sm text-accent">
            {t("work.mobile.signature.hanger_photo")}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="sr-only"
              aria-label={t("work.mobile.signature.hanger_photo")}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void takeHanger(file);
              }}
            />
          </label>
          {hangerId ? (
            <p className="mt-1 text-sm text-neutral-600" data-hanger="taken">
              {t("work.mobile.signature.hanger_taken")}
            </p>
          ) : null}
          <button
            type="button"
            className="mt-3 w-full bg-accent px-3 py-3 text-sm font-semibold text-bg"
            disabled={busy}
            onClick={() => void saveRefused()}
          >
            {t("work.mobile.signature.save_refused")}
          </button>
        </div>
      )}

      {refusalMessage ? (
        <p className="mt-3 text-sm text-danger-700" role="alert">
          {refusalMessage}
        </p>
      ) : null}
    </section>
  );
}

function ModeTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={[
        "flex-1 py-3 text-sm",
        active ? "text-accent font-semibold" : "text-neutral-600",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

/**
 * The pad itself — a canvas a finger draws on.
 *
 * ⚠ **`drawn` IS A REF AND NOT STATE, DELIBERATELY.** It records whether the
 * customer actually made a mark, and re-rendering the pad on every pointer
 * move would clear the canvas mid-signature. What it guards is a real case: a
 * blank canvas encodes to a perfectly valid PNG, so without this a job could
 * be signed by nobody, and `printed_name` would be the only evidence that
 * anyone was there at all.
 */
function SignaturePad({
  padRef,
  drawn,
}: {
  padRef: React.MutableRefObject<HTMLCanvasElement | null>;
  drawn: React.MutableRefObject<boolean>;
}) {
  const { t } = useTranslation();

  useEffect(() => {
    const canvas = padRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.lineWidth = 2;
    context.lineCap = "round";
    let drawing = false;

    const point = (event: PointerEvent) => {
      const box = canvas.getBoundingClientRect();
      return { x: event.clientX - box.left, y: event.clientY - box.top };
    };
    const down = (event: PointerEvent) => {
      drawing = true;
      drawn.current = true;
      const { x, y } = point(event);
      context.beginPath();
      context.moveTo(x, y);
    };
    const move = (event: PointerEvent) => {
      if (!drawing) return;
      const { x, y } = point(event);
      context.lineTo(x, y);
      context.stroke();
    };
    const up = () => {
      drawing = false;
    };

    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointerleave", up);
    return () => {
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", up);
      canvas.removeEventListener("pointerleave", up);
    };
  }, [padRef, drawn]);

  return (
    <canvas
      ref={padRef}
      width={600}
      height={200}
      aria-label={t("work.mobile.signature.pad")}
      data-signature-pad
      className="mt-3 w-full border border-divider bg-surface touch-none"
    />
  );
}

async function canvasBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/png"),
  );
  if (!blob) throw new Error("the signature pad produced no image");
  return blob;
}
