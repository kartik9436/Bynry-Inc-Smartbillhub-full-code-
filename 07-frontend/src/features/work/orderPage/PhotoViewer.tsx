// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — image 09, the photo viewer
//           (P1.22 *See the photographs*, P1.24 *View* on the signature).
// Rules:    ruling 12 (*"where there are photos required there user can be
//           able to view the photos"*) · ruling 15 (photos only once the job is
//           completed — the caller decides; this component never fetches on an
//           open job because it is never mounted there) · B14 rule 31 (the
//           attachment's uuid builds the link and is never shown) · rule 43
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PICTURE IS DRAWN FROM THE API, NEVER FROM THE STORAGE HOST
// (`DEF-WRK-9594`).** `GET …/attachments/{aid}` mints a presigned link on another
// host, and the page policy draws images only from itself — the browser refused
// every photograph. `GET …/attachments/{aid}/content` serves the bytes through
// the session like any other read, so no bearer token leaves the server and the
// page policy is not widened.
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { apiHref } from "@/api/apiHref";
import { Button } from "@/components/Button";
import { ModalShell } from "@/components/FormModal";
import { Dash, Fact, FactList } from "@/features/metering/meteringShared";

import { whenText } from "./orderFormat";
import type { Regional } from "./orderFormat";

/** One picture the viewer can show. `attachmentId` null = a picture whose URL
 *  the caller already holds (the signature's mark). */
export interface ViewerPhoto {
  key: string;
  title: string;
  attachmentId: string | null;
  url?: string | null;
  takenBy: string | null;
  takenAt: string | null;
  forText: string;
}

/** The address of one photograph's bytes, on the API's origin (`apiHref`).
 *  It was built with `apiPath()` — no origin — until `DEF-WRK-9719`, so on a
 *  two-host deployment the browser asked the app's static host. */
export function photoSrc(tenant: string, orderId: string, photo: ViewerPhoto): string | null {
  if (photo.url) return photo.url;
  if (photo.attachmentId === null || tenant === "") return null;
  return apiHref(`/${tenant}/work-orders/${orderId}/attachments/${photo.attachmentId}/content`);
}

/** The picture in a table cell — a button, because it opens something. */
export function PhotoThumb(props: {
  orderId: string;
  photo: ViewerPhoto;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  const { tenant = "" } = useParams();
  const url = photoSrc(tenant, props.orderId, props.photo);
  return (
    <button
      type="button"
      data-photo-thumb={props.photo.key}
      className="h-12 w-16 border border-divider bg-surface focus-visible:outline-2 focus-visible:outline-accent"
      aria-label={t("work.order.photo.open", { title: props.photo.title })}
      onClick={props.onOpen}
    >
      {url !== null ? (
        <img src={url} alt="" className="h-full w-full object-cover" />
      ) : (
        <span className="text-sm text-neutral-600">▣</span>
      )}
    </button>
  );
}

export function PhotoViewer(props: {
  orderId: string;
  photos: ViewerPhoto[];
  index: number;
  onIndex: (index: number) => void;
  onClose: () => void;
  regional: Regional;
}) {
  const { t } = useTranslation();
  const { tenant = "" } = useParams();
  const photo = props.photos[props.index];
  if (photo === undefined) return null;
  const url = photoSrc(tenant, props.orderId, photo);
  const last = props.photos.length - 1;
  return (
    <ModalShell title={photo.title} onClose={props.onClose} size="wide">
      <div className="modal-body" data-photo-viewer={photo.key}>
        <div className="flex min-h-64 items-center justify-center border border-divider bg-surface">
          {url !== null ? (
            <img src={url} alt={photo.title} className="max-h-96 w-full object-contain" />
          ) : (
            <Dash />
          )}
        </div>
        <div className="mt-4">
          <FactList>
            <Fact label={t("work.order.photo.takenBy")}>{photo.takenBy ?? <Dash />}</Fact>
            <Fact label={t("work.order.photo.when")}>
              {whenText(photo.takenAt, props.regional) ?? <Dash />}
            </Fact>
            <Fact label={t("work.order.photo.for")}>{photo.forText}</Fact>
          </FactList>
        </div>
      </div>
      <div className="modal-foot">
        <span className="mr-auto text-sm text-neutral-600" data-photo-position="">
          {t("work.order.photo.position", { at: props.index + 1, total: props.photos.length })}
        </span>
        <Button
          variant="ghost"
          disabled={props.index === 0}
          onClick={() => props.onIndex(props.index - 1)}
        >
          {t("work.order.photo.previous")}
        </Button>
        <Button
          variant="ghost"
          disabled={props.index === last}
          onClick={() => props.onIndex(props.index + 1)}
        >
          {t("work.order.photo.next")}
        </Button>
      </div>
    </ModalShell>
  );
}
