// ── Trace ──────────────────────────────────────────────
// Change:   CR-183-BRC10 T8 — the customer sees their temporary stop on the
//           account, and may ask to restart now (PO ruling B4, 2026-10-14).
// Rules:    BR-CUS-1120 (B1 standing charge only while paused · B4 the ask, a
//           clerk approves, normal billing from that day) · BR-CWP-026 (a
//           portal ask changes no account) · B14 rule 43 (its own component,
//           mounted by `YourAccount`) · rule 33 (facts ≤ 6 words, no rationale)
//           · rule 35 (each catalogue in its own language)
// Tests:    src/portal/accounts/TemporaryStopCard.dom.test.tsx
// ───────────────────────────────────────────────────────
//
//     SERVICE PAUSED
//     Paused 13 Oct 2026 – 26 Oct 2026          (or: Pause starts 13 Oct 2026)
//     Restarts 26 Oct 2026
//     Standing charge only while paused.
//     [ Restart my service now ]                (or: Restart asked · SR-26-0021)
//
// ⚠ **ABSENT WHEN THERE IS NOTHING TO SAY** — no live stop and no waiting ask
// draws no card, never an empty one (`BR-CWP-093`).
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";

import { Card, SectionTitle } from "../components/primitives";
import { onDate } from "../components/content";
import { askToRestartNow, getTemporaryStop, type PortalTemporaryStop } from "../api/portalClient";
import { Announced } from "../components/a11y";

export function TemporaryStopCard(props: { accountId: string }) {
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<PortalTemporaryStop | null>(null);
  const [sending, setSending] = useState(false);
  const [asked, setAsked] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    getTemporaryStop(props.accountId)
      .then((answer) => {
        if (live) setData(answer);
      })
      .catch(() => {
        if (live) setData(null);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, asked]);

  if (data === null || (data.current === null && data.pending === null)) return null;
  const day = (iso: string | null) => onDate(iso, i18n.language);
  const current = data.current;
  const restartReference = asked ?? current?.restart_reference ?? null;

  return (
    <Card testId="temporary-stop">
      <SectionTitle>{t("portal.temporaryStop.title")}</SectionTitle>
      {current !== null ? (
        <>
          <p className="text-body font-bold" data-temporary-stop-status={current.status}>
            {current.status === "on_hold"
              ? t("portal.temporaryStop.paused", {
                  from: day(current.stop_from),
                  to: day(current.restart_on),
                })
              : t("portal.temporaryStop.starts", { date: day(current.stop_from) })}
          </p>
          {current.restart_on !== null && (
            <p className="text-body" data-temporary-stop-restarts="">
              {t("portal.temporaryStop.restarts", { date: day(current.restart_on) })}
            </p>
          )}
          <p className="text-body text-neutral-600">{t("portal.temporaryStop.baseOnly")}</p>
          {data.can_restart_now && asked === null ? (
            <div>
              <Button
                variant="primary"
                size="default"
                data-action="restart-now"
                disabled={sending}
                onClick={() => {
                  setSending(true);
                  setFailed(false);
                  void askToRestartNow(props.accountId)
                    .then((answer) => setAsked(answer.reference))
                    .catch(() => setFailed(true))
                    .finally(() => setSending(false));
                }}
              >
                {t("portal.temporaryStop.restartNow")}
              </Button>
            </div>
          ) : restartReference !== null ? (
            <p className="text-body font-semibold" data-temporary-stop-restart-asked="">
              {t("portal.temporaryStop.restartAsked", { reference: restartReference })}
            </p>
          ) : null}
          {failed && (
            <Announced tone="error" className="text-body text-danger-700">
              {t("portal.temporaryStop.couldNotSend")}
            </Announced>
          )}
        </>
      ) : data.pending !== null ? (
        <p className="text-body" data-temporary-stop-pending="">
          {t("portal.temporaryStop.pending", {
            from: day(data.pending.stop_from),
            reference: data.pending.reference ?? "",
          })}
        </p>
      ) : null}
    </Card>
  );
}
