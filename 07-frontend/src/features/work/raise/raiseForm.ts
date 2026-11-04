// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — what the three steps share.
//           The wizard holds it; each step reads it and writes it back, so
//           Back loses nothing (BR-SHL-018) and nothing is written until the
//           ONE press on Confirm.
// ───────────────────────────────────────────────────────
import type { CustomFieldValues } from "@/components/CustomFields";

import type { ChosenAsset, ChosenUnit } from "./raiseModel";

export interface RaiseCandidateChoice {
  kind: string;
  id: string;
  name: string;
}

export interface RaiseForm {
  premisesId: string;
  /** *301 Mill Pond Ln · Silver Creek* — what the box shows once chosen. */
  premisesLabel: string;
  /** *Apartment complex · 6 units* — the fact under the box. */
  premisesDetail: string;
  premisesTerm: string;
  units: ChosenUnit[];
  typeId: string;
  templateId: string;
  /** `""` is *None — the unit itself*. */
  assetTypeId: string;
  /** The words of the three choices, as the clerk saw them on step 1 — the
   *  Confirm summary reads these, never a second lookup. */
  typeLabel: string;
  templateLabel: string;
  assetTypeLabel: string;
  assets: ChosenAsset[];
  /** The units (by id, or label where the read names no id) on which at least
   *  one asset of the chosen type was read — ruling 20's "this unit has one". */
  assetUnitKeys: string[];
  priorityId: string;
  notes: string;
  /** CR-161-BRC10 W4 — the utility's own work-order fields (`WORK_NEW`), kept
   *  on step 1 under Description (CR-168 §5.7, item N4). */
  customData: CustomFieldValues;
  due: string;
  visitDay: string;
  visitWindow: "any" | "morning" | "afternoon";
  assignee: RaiseCandidateChoice | null;
}

export const EMPTY_RAISE_FORM: RaiseForm = {
  premisesId: "",
  premisesLabel: "",
  premisesDetail: "",
  premisesTerm: "",
  units: [],
  typeId: "",
  templateId: "",
  assetTypeId: "",
  typeLabel: "",
  templateLabel: "",
  assetTypeLabel: "",
  assets: [],
  assetUnitKeys: [],
  priorityId: "",
  notes: "",
  customData: {},
  due: "",
  visitDay: "",
  visitWindow: "any",
  assignee: null,
};

export type RaiseUpdate = (patch: Partial<RaiseForm>) => void;
