// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D4 · **US-RBS-038
//          (CR-075 wave E task E6) — the Clone row action**.
// Screens: RBS-003 at `/{tenant}/runbooks/mine`.
// Rules:   `NFR-3` (the page number travels to the server; nothing here slices
//          an array) · `BR-SHL-020` (a refusal is plain language) ·
//          `07-endpoints.md` row 6 (`POST /runbooks/{key}/clone`, `RB-040`).
// Defects: DEF-RBS-4311 (a live route behind a dead control).
// Tests:   MyRunbooks.dom.test.tsx
// ───────────────────────────────────────────────────────
// THE PAGE THAT FEEDS `MyRunbooks`, AND THE ONE THING IT HOLDS.
//
// `MyRunbooks` is pure over its rows and its request state. This file is the
// only place that knows there is a server.
//
// ⚠ **THE KIND CHIP IS THIS FILE'S STATE AND IT GOES BACK TO THE SERVER.**
// `DataTable`'s `TableRequestState` carries `q`, `sort`, `dir`, `page`, `per`
// and `filters`; the chip row the sheet draws is not one of its declared
// filters, so the value lives here and travels as `f.kind`. Nothing anywhere
// slices the rows the server returned — `RBS-003.2` is *the server's* answer to
// *filtered to Actions*, not a client-side `.filter()` over one page, which is
// the shape `NFR-3` exists to refuse.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { api, formErrorEnvelope, isApiError } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import type { PagedRows } from "@/api/paginated";
import { FormModal, TextField } from "@/components/FormModal";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import { getMyRunbooks } from "./libraryEndpoints";
import type { CatalogueRow } from "./libraryTypes";
import { MyRunbooks } from "./MyRunbooks";
import { cloneRunbook } from "../setupWire";

/** The one field a clone needs. `POST /runbooks/{key}/clone` takes `{name}` and
 *  `services.clone_runbook` mints the key itself — a person names the copy and
 *  never types an address. */
const CLONE_SCHEMA = z.object({ name: z.string().trim().min(1, { message: "errors.val-001" }) });

/** The request this screen starts from. Written out rather than derived from
 *  `defaultRequestState(config)` because the config lives inside the renderer,
 *  where it belongs, and a page that reached into it would be two files sharing
 *  one secret. `sort` is `name` because that is what the server orders by —
 *  stating the server's own order rather than asking for one it ignores. */
const INITIAL_STATE: TableRequestState = {
  q: "",
  sort: "name",
  dir: "asc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

export function MyRunbooksPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenant = useTenant();

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [state, setState] = useState<TableRequestState>(INITIAL_STATE);
  const [kind, setKind] = useState("");
  const [cloning, setCloning] = useState<{ key: string; name: string } | null>(null);
  const templatesTo = tenantPathFrom(tenant, "runbooks/templates");

  /**
   * **Clone** — `POST /runbooks/{key}/clone`, released in the wave that could
   * release it (`DEF-RBS-4311`).
   *
   * On success the person lands on the COPY's own setup screen, because
   * `US-RBS-038` is *"clone Dunning, name it Commercial accounts, set the first
   * reminder to 15 days"* — the naming and the varying are one errand, and the
   * copy arrives `enabled: false` precisely so it can be varied before it runs.
   */
  const clone = useMutation({
    mutationFn: (input: { key: string; name: string }) =>
      cloneRunbook(input.key, input.name, client),
    onSuccess: (copy) => {
      // Every cached page of My runbooks and of the library is now one row
      // short. The whole prefix goes rather than one key.
      void queryClient.invalidateQueries({ queryKey: ["runbooks"] });
      setCloning(null);
      navigate(tenantPathFrom(tenant, `runbooks/${copy.key}`));
    },
  });

  const query = useQuery<PagedRows<CatalogueRow>>({
    // ONE key from the whole request. A page turn cannot answer from the cache
    // of a different page, and a chip cannot answer from the cache of a
    // different chip.
    queryKey: ["runbooks", "mine", state.q, kind, state.page, state.per],
    queryFn: () => getMyRunbooks({ q: state.q, kind, page: state.page, per: state.per }, client),
  });

  const list = (
    <MyRunbooks
      rows={query.data?.rows ?? []}
      // `null` until the first response — the pager says nothing rather than
      // saying "of 0" over a list that has not loaded.
      total={query.data?.total ?? null}
      loading={query.isPending}
      error={
        query.isError
          ? { reason: refusalText(t, query.error), onRetry: () => void query.refetch() }
          : null
      }
      state={state}
      onStateChange={setState}
      kind={kind}
      onKind={(next) => {
        setKind(next);
        // A new filter is a new list, so it starts at page 1. Leaving the page
        // number alone is how a person lands on an empty page 3 of a 2-page
        // result and reads it as "nothing here".
        setState((current) => ({ ...current, page: 1 }));
      }}
      templatesTo={templatesTo}
      onBrowseTemplates={() => navigate(templatesTo)}
      onClone={(row) =>
        // The copy opens with the source's name plus one word, so a person
        // edits rather than types from nothing — and never lands on two rows
        // with the identical name, which is the only thing `RBS-003` shows.
        setCloning({ key: row.key, name: t("runbooks.mine.clone.suggested", { name: row.name }) })
      }
    />
  );

  return (
    <>
      {list}
      {cloning !== null && (
        <FormModal
          title={t("runbooks.mine.clone.title")}
          schema={CLONE_SCHEMA}
          values={cloning}
          submitLabel={t("runbooks.mine.clone.submit")}
          onClose={() => setCloning(null)}
          onSubmit={async () => {
            try {
              await clone.mutateAsync({ key: cloning.key, name: cloning.name.trim() });
              return { ok: true };
            } catch (error) {
              // The SERVER's sentence, never one this screen invented.
              if (isApiError(error)) {
                return { ok: false, error: formErrorEnvelope(error) };
              }
              return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
            }
          }}
        >
          <TextField
            id="name"
            required
            label={t("runbooks.mine.clone.nameLabel")}
            help={t("runbooks.mine.clone.nameHelp")}
            value={cloning.name}
            onChange={(name) => setCloning({ ...cloning, name })}
          />
        </FormModal>
      )}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-003 (EP-RBS-01; CR-075 wave D task D4) · US-RBS-038 (wave E task E6) · 07-endpoints.md rows 1 and 6 · NFR-3
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// amended:   2026-09-06 by the CR-075 wave E · E4/E5/E6 lane — the Clone row
//            action, released over the route wave E1 landed (DEF-RBS-4311)
// checklist: A✔ B✔ C✔ D✔(POST /runbooks/{key}/clone, 07-endpoints.md row 6) E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler) · vitest MyRunbooks.dom.test.tsx · G13
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
