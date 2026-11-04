// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-10003 (PO GIS review gap 9 — the City's fields drawn for a
//          utility with no City GIS) · DEF-INT-10004 (gap 12 — broken and
//          never set up read the same)
// Screens: S14/S15 the property and unit Overviews and their edit forms
// Reads:   GET /integrations/gis_esri/state (apps/integrations/gis.city_state)
// ───────────────────────────────────────────────────────
/**
 * ONE QUESTION, ASKED ONCE PER SCREEN: is a City GIS in use here, and is it well?
 *
 * ⚠ **ONE HOOK AND ONE NOTE, SO EVERY PREMISES AND UNIT SURFACE ANSWERS THE SAME
 * WAY (B14 rule 43).** Until 2026-10-07 the only screen that could tell was the
 * create form, and only because its address search was REFUSED (`DEF-MET-5624`);
 * the Overviews and the edit forms drew the point and the GIS check for every
 * utility, whether it had a City or not.
 *
 * **What `showCity` decides, and what it does NOT.** It hides the City's fields —
 * the parcel, the point, *Checked against GIS*, the latitude and longitude boxes.
 * It **deletes nothing**: the stored values stay in their columns, an edit form
 * that does not draw a box does not send it, and they come back the day a City is
 * connected. The import reference is NOT a City field and is never hidden.
 *
 * ⚠ **WHILE THE ANSWER IS IN FLIGHT THE FIELDS ARE HIDDEN; IF THE READ FAILS THEY
 * ARE SHOWN.** Hidden-then-shown is a row appearing on a utility that has a City;
 * shown-then-hidden would be a row vanishing under the clerk's eye on most
 * utilities. And a read that fails must not take a utility's data off screen —
 * a failure is not an answer that there is no City.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCityGisState } from "@/api/endpoints";
import type { CityGisStateView } from "@/api/endpoints";

export const cityGisQueryKey = ["integrations", "gis_esri", "state"] as const;

/** The pure decision — exported so it can be read in a test without a client. */
export function showCityFields(answer: {
  data: CityGisStateView | undefined;
  isError: boolean;
}): boolean {
  if (answer.isError) return true;
  if (answer.data === undefined) return false;
  return answer.data.state !== "none";
}

export function useCityGis(client: ApiClient = api) {
  const query = useQuery({
    queryKey: cityGisQueryKey,
    queryFn: () => getCityGisState(client),
    staleTime: 60 * 1000,
    retry: false,
  });
  return {
    showCity: showCityFields({ data: query.data, isError: query.isError }),
    brokenKey: query.data?.state === "broken" ? query.data.message_key : null,
  };
}

/** The one line a BROKEN City gets beneath its fields (gap 12). Nothing otherwise. */
export function CityGisNote(props: { messageKey: string | null }) {
  const { t } = useTranslation();
  if (!props.messageKey) return null;
  return (
    <p className="m-0 py-2 text-sm text-neutral-600" data-city-gis-note="" role="status">
      {t(props.messageKey)}
    </p>
  );
}
