// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-10040 (PO 2026-10-11) — *Check address* lifted out of Add a
//           premise's PropertyStep so the New request wizard's step 2 draws the
//           SAME button and the SAME four answers. PO, verbatim: *"we ahve build
//           same capabaility in add premise ; you can use same code"*.
// Rules:    BR-MET-1191 (Check address asks the City once, never on every
//           keystroke) · B14 rule 43 (a piece of UI is a component — this one
//           was inline in one step file, which is why the second screen that
//           captures a new address never got it) · B14 rule 21
// ───────────────────────────────────────────────────────
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { checkCityAddress } from "@/api/endpoints";
import { Button } from "@/components/Button";

import { checkFromAnswer, pointText } from "./addPremiseModel";
import type { AddressCheck } from "./addPremiseModel";
import { ResultBox } from "./addPremiseShared";
import type { Translator } from "./addPremiseShared";

export interface CityAddressParts {
  address_line: string;
  city: string;
  state: string;
  postal_code: string;
}

/**
 * The check's state and the one call that changes it. A failed request is
 * *unavailable*, never an exception the screen has to catch: the check is a
 * courtesy and refuses nothing.
 */
export function useCityAddressCheck(client: ApiClient, today: () => string) {
  const [check, setCheck] = useState<AddressCheck>({ kind: "none" });
  async function run(parts: CityAddressParts): Promise<void> {
    setCheck({ kind: "checking" });
    try {
      setCheck(checkFromAnswer(await checkCityAddress(parts, client), today()));
    } catch {
      setCheck({ kind: "unavailable", messageKey: null });
    }
  }
  return { check, setCheck, run };
}

/** The button, its help line and the answer box beneath — one piece, two screens. */
export function CityAddressCheck(props: {
  check: AddressCheck;
  onCheck: () => void;
  onUseDetails: () => void;
  onKeepMine: () => void;
  t: Translator;
}) {
  const { t } = props;
  return (
    <>
      <div className="mt-5 flex items-center gap-3">
        <Button onClick={props.onCheck} disabled={props.check.kind === "checking"} data-check-address="">
          {t("metering.addPremise.check.button")}
        </Button>
        <span className="text-sm text-neutral-700">{t("metering.addPremise.check.help")}</span>
      </div>
      <CityAddressCheckResult {...props} />
    </>
  );
}

function CityAddressCheckResult(props: {
  check: AddressCheck;
  onUseDetails: () => void;
  onKeepMine: () => void;
  t: Translator;
}) {
  const { check, t } = props;
  if (check.kind === "none" || check.kind === "checking") return null;
  let box;
  if (check.kind === "not_connected") {
    box = (
      <ResultBox
        tone="plain"
        data-result="not-connected"
        title={t("metering.addPremise.check.notConnectedTitle")}
        line={t("metering.addPremise.check.notConnectedLine")}
      />
    );
  } else if (check.kind === "no_match") {
    box = (
      <ResultBox
        tone="warn"
        data-result="no-match"
        title={t("metering.addPremise.check.noMatchTitle")}
        line={t("metering.addPremise.check.noMatchLine")}
      />
    );
  } else if (check.kind === "unavailable") {
    box = (
      <ResultBox
        tone="plain"
        data-result="unavailable"
        title={check.messageKey === null ? t("metering.addPremise.check.unavailableTitle") : t(check.messageKey)}
        line={t("metering.addPremise.check.notConnectedLine")}
      />
    );
  } else {
    box = (
      <ResultBox
        tone="good"
        data-result="match"
        title={check.used ? t("metering.addPremise.check.usedTitle") : t("metering.addPremise.check.matchTitle")}
        facts={[
          {
            id: "address",
            label: t("metering.addPremise.check.cityAddress"),
            value: [check.match.address_line, check.match.city, [check.match.state, check.match.postal_code].filter(Boolean).join(" ")]
              .filter((part) => part !== null && part !== undefined && part !== "")
              .join(", "),
          },
          { id: "parcel", label: t("metering.addPremise.check.parcel"), value: check.match.parcel || "—" },
          { id: "point", label: t("metering.addPremise.check.point"), value: pointText(check.match.lat, check.match.lng) || "—" },
        ]}
        actions={
          check.used ? undefined : (
            <>
              <Button variant="primary" onClick={props.onUseDetails}>
                {t("metering.addPremise.check.use")}
              </Button>
              <Button onClick={props.onKeepMine}>{t("metering.addPremise.check.keep")}</Button>
            </>
          )
        }
      />
    );
  }
  return <div className="mt-5">{box}</div>;
}
