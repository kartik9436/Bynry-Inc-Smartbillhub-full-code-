// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-058 (EP-WRK-11) — the office sees every handset a
//           technician signs in on, and can sign one out (Security §4, R115)
// Server:   GET /work/technicians/{slug}/devices?page=&per= ·
//           POST /work/technicians/{slug}/devices/{device_id}/sign-out
//           (`apps/work/mobile.devices_page`, `.remote_sign_out`)
// Rules:    R113 (*"there is no state in which captured work is thrown away
//           to resolve an auth problem"* — unsent work is KEPT) · R115 (the
//           office signs a handset out) · NFR-3 (paged by the server) ·
//           B14 rule 6 (a sign-out is a destructive commit — the danger
//           tier, asked first, its consequence named) · rule 15 (an icon with
//           a tooltip) · rule 31 (neither the handset's identifier nor a push
//           token is ever shown) · 33 · 21 · 43
// Impacts:  src/features/work/TechnicianDetailPage.tsx (Overview mounts it)
// ───────────────────────────────────────────────────────
//
// ⚠ **IT SIGNS OUT THE HANDSET, NOT ONE PERSON ON IT.** The server marks every
// registration of the same handset — a lost shared tablet is lost for
// everybody who used it — so the consequence says *everyone on it*, which is
// what actually happens, rather than naming only this technician.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DateCell } from "@/components/DateCell";
import { PowerIcon } from "@/components/icons";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { PAGE_SIZES } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";

import { listTechnicianDevices, signOutTechnicianDevice } from "./fieldDeskEndpoints";
import type { TechnicianDeviceRow } from "./fieldDeskEndpoints";

const PLATFORMS = ["ios", "android", "web"] as const;

export function TechnicianDevicesPanel(props: {
  slug: string;
  client: ApiClient;
  timeZone: string;
  dateFormat: Parameters<typeof DateCell>[0]["dateFormat"];
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(PAGE_SIZES[0]);
  const [asking, setAsking] = useState<TechnicianDeviceRow | null>(null);
  const [working, setWorking] = useState(false);
  // ⚠ THE ANSWER IS SAID IN THE PANEL, NOT IN A TOAST. This panel is mounted
  // by the technician page, whose own suite renders it without the toast
  // queue; a group that needs a provider its host does not promise is a
  // component that only works on one screen (rule 43). The row's own status
  // turning *Signed out* is the success; a refusal is the sentence below.
  const [said, setSaid] = useState<string | null>(null);

  const devices = useQuery({
    queryKey: ["work", "technician", props.slug, "devices", page, per],
    queryFn: () => listTechnicianDevices(props.slug, { page, per }, props.client),
  });

  const name = (row: TechnicianDeviceRow) =>
    row.name !== null && row.name !== "" ? row.name : t("work.field.deviceUnnamed");

  async function signOut(row: TechnicianDeviceRow) {
    setWorking(true);
    try {
      await signOutTechnicianDevice(props.slug, row.device_id, props.client);
      setSaid(t("work.field.deviceSignedOutDone", { device: name(row) }));
      void queryClient.invalidateQueries({ queryKey: ["work", "technician", props.slug, "devices"] });
    } catch (error) {
      setSaid(refusalText((key, params) => t(key, params), error));
    } finally {
      setWorking(false);
      setAsking(null);
    }
  }

  const rows = devices.data?.rows ?? [];
  return (
    <Panel as="section" title={t("work.field.devicesTitle")} data-technician-devices="">
      {said !== null && (
        <p className="m-0 mb-3" role="status" data-devices-said="">
          {said}
        </p>
      )}
      {devices.isError ? (
        <Note>{t("work.field.devicesFailed")}</Note>
      ) : devices.data !== undefined && rows.length === 0 ? (
        <Note data-devices-empty="">{t("work.field.devicesEmpty")}</Note>
      ) : devices.data === undefined ? null : (
        <>
          <PlainTable data-devices-table="">
            <thead>
              <tr>
                <th>{t("work.field.col.device")}</th>
                <th>{t("work.field.col.platform")}</th>
                <th>{t("work.field.col.lastSeen")}</th>
                <th>{t("work.field.col.push")}</th>
                <th>{t("work.field.col.status")}</th>
                <th>{t("work.field.col.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.device_id} data-device-row={row.signed_out ? "signed-out" : "signed-in"}>
                  <td>{name(row)}</td>
                  <td>
                    {row.platform === null ? (
                      <Dash />
                    ) : (PLATFORMS as readonly string[]).includes(row.platform) ? (
                      t(`work.field.platform.${row.platform}`)
                    ) : (
                      row.platform
                    )}
                  </td>
                  <td>
                    {row.last_seen_at === null ? (
                      <Dash />
                    ) : (
                      <DateCell value={row.last_seen_at} timeZone={props.timeZone} dateFormat={props.dateFormat} withTime />
                    )}
                  </td>
                  <td>{row.push_registered ? t("work.field.pushOn") : t("work.field.pushOff")}</td>
                  <td>
                    <StatusPill tone={row.signed_out ? "muted" : "success"}>
                      {row.signed_out ? t("work.field.deviceSignedOut") : t("work.field.deviceSignedIn")}
                    </StatusPill>
                  </td>
                  <td>
                    <RowActions>
                      <RowAction
                        label={t("work.field.deviceSignOut", { device: name(row) })}
                        icon={<PowerIcon />}
                        danger
                        testId="device-sign-out"
                        // Already signed out: the act has nothing left to do,
                        // and the reason is the status beside it.
                        reason={row.signed_out ? t("work.field.deviceSignedOut") : null}
                        onClick={() => setAsking(row)}
                      />
                    </RowActions>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
          <ListPager
            total={devices.data.total}
            page={page}
            per={per}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1);
            }}
          />
        </>
      )}
      {asking !== null && (
        <ConfirmDialog
          title={t("work.field.deviceSignOutTitle", { device: name(asking) })}
          consequence={t("work.field.deviceSignOutConsequence")}
          confirmLabel={t("work.field.deviceSignOutConfirm")}
          cancelLabel={t("work.field.back")}
          confirmVariant="danger"
          working={working}
          onConfirm={() => void signOut(asking)}
          onCancel={() => setAsking(null)}
        />
      )}
    </Panel>
  );
}
