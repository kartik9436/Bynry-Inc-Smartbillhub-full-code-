// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10591 — no screen could assign a route's reader, so the
//           phone's Reads tab was empty (beta MQ-033).
// Ruling:   PO 2026-10-24, *"i have given you a screen from where
//           assign/reassign should be done"* — Reads → cycle → Routes. It
//           SUPERSEDES `CR-029` D6 and `OQ-343` for that tab only; Settings →
//           Routes stays reader-free (decision log, same date).
// Rules:    BR-FLD-00087 (R87 — one reader per route for now) · B14 rule 31
//           (the reader by NAME, never an id) · rule 33 (labels ≤ 3 words,
//           facts ≤ 6) · rule 36 (the kit: `FormModal`, `PickBySearch`) ·
//           rule 43 (a piece of UI is a component) · rule 21 (Tailwind; this
//           file is on `styles/route-b-migrated.txt`)
// Server:   POST /routes/reader · GET /routes/reader-choices
// Tests:    AssignReaderModal.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ONE DIALOG FOR ONE ROUTE AND FOR MANY.
//
// The row action opens it over one route; the bulk bar over every ticked one.
// It shows who reads now (one route) or how many routes are picked (many),
// takes a field technician by search → look → *Use* (the kit's confirm-before-
// it-counts pick), and saves. *Unassign* clears the reader on every route in
// the dialog that has one — a route with no reader reaches no phone.
import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { FormModal } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PickBySearch } from "@/components/PickBySearch";
import type { PickCandidate } from "@/components/PickBySearch";

import { searchRouteReaders, setRouteReader } from "./routeReaderEndpoints";
import type { ReaderChoice, RouteReader, SetRouteReaderResult } from "./routeReaderEndpoints";

/** A route as the dialog needs it: the code it names, the reader it has. */
export interface ReaderTarget {
  id: string;
  code: string;
  reader: RouteReader | null;
}

/** Shape only: a technician must be picked before *Save* commits. Whether
 *  they MAY read a route is the server's (`route_readers.set_reader`). */
export const assignReaderSchema = z.object({ reader_id: z.string().min(1) });

/** The fact line: who reads one route now, or how many routes are picked. */
export function currentReaderLine(
  routes: readonly ReaderTarget[],
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  if (routes.length !== 1) {
    return t("metering.routeReader.routesPicked", { count: routes.length });
  }
  const reader = routes[0].reader;
  return reader === null
    ? t("metering.routeReader.notAssigned")
    : t("metering.routeReader.readsNow", { name: reader.name });
}

function candidateOf(choice: ReaderChoice): PickCandidate {
  return { id: choice.id, title: choice.name, meta: choice.email ?? undefined };
}

export interface AssignReaderModalProps {
  routes: readonly ReaderTarget[];
  client?: ApiClient;
  onClose: () => void;
  onSaved: (result: SetRouteReaderResult) => void;
}

export function AssignReaderModal(props: AssignReaderModalProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [chosen, setChosen] = useState<PickCandidate | null>(null);
  const seen = useRef(new Map<string, ReaderChoice>());
  const routeIds = props.routes.map((route) => route.id);
  const anyAssigned = props.routes.some((route) => route.reader !== null);

  const save = useMutation({
    mutationFn: (readerId: string | null) => setRouteReader(routeIds, readerId, client),
    onSuccess: (result) => {
      props.onSaved(result);
      props.onClose();
    },
  });

  // *Unassign* is its own act beside the form's commit, so its failure is
  // said beside it rather than lost (the form's own summary speaks for Save).
  const unassign = useMutation({
    mutationFn: () => setRouteReader(routeIds, null, client),
    onSuccess: (result) => {
      props.onSaved(result);
      props.onClose();
    },
  });

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await save.mutateAsync(chosen?.id ?? null);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: error as never };
    }
  }

  async function search(q: string): Promise<PickCandidate[]> {
    const rows = await searchRouteReaders(q, client);
    for (const row of rows) seen.current.set(row.id, row);
    return rows.map(candidateOf);
  }

  const title =
    props.routes.length === 1
      ? t("metering.routeReader.titleOne", { route: props.routes[0].code })
      : t("metering.routeReader.title");

  return (
    <FormModal
      title={title}
      kicker={t("metering.reads.kicker")}
      schema={assignReaderSchema}
      values={{ reader_id: chosen?.id ?? "" }}
      submitLabel={t("metering.routeReader.save")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <div className="mb-4 flex flex-wrap items-center gap-3" data-route-reader="current">
        <span className="text-sm">{currentReaderLine(props.routes, t)}</span>
        {anyAssigned && (
          <Button
            variant="ghost"
            size="sm"
            disabled={unassign.isPending || save.isPending}
            onClick={() => unassign.mutate()}
          >
            {t("metering.routeReader.unassign")}
          </Button>
        )}
        {unassign.isError && (
          <span role="alert" className="text-sm text-danger-700">
            {t("metering.routeReader.unassignFailed")}
          </span>
        )}
      </div>
      <PickBySearch
        id="reader_id"
        label={t("metering.routeReader.field")}
        required
        placeholder={t("metering.routeReader.placeholder")}
        findLabel={t("metering.routeReader.find")}
        noMatchLabel={t("metering.routeReader.noMatch")}
        search={search}
        chosen={chosen}
        onUse={setChosen}
        onChange={() => setChosen(null)}
        useLabel={t("metering.routeReader.use")}
        selectedLabel={`✓ ${t("metering.routeReader.selected")}`}
        changeLabel={t("metering.routeReader.change")}
        renderCard={(candidate) => (
          <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-3" data-route-reader="card">
            <div>
              <dt className="text-sm text-neutral-700">{t("metering.routeReader.name")}</dt>
              <dd className="m-0 font-semibold">{candidate.title}</dd>
            </div>
            <div>
              <dt className="text-sm text-neutral-700">{t("metering.routeReader.email")}</dt>
              <dd className="m-0 font-semibold">
                {seen.current.get(candidate.id)?.email ?? "—"}
              </dd>
            </div>
          </dl>
        )}
      />
    </FormModal>
  );
}
