// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 13: the answers on the reading's page.
// Rules:    BR-MET-1218 · BR-MET-1216 (a flagged answer is shown with its flag)
//           · B14 rule 31 (the job by its NUMBER; the photo id only builds an
//           address) · hard-won law 2 (mounted under the real path pattern)
// ───────────────────────────────────────────────────────
// RED FIRST: before this lane `ReadFormatAnswersPanel` did not exist and the
// reading's page drew nothing from `read_format_answers` — the server had served
// it since task 10 and no screen read it (hard-won law 2's dead-data shape).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import i18n from "i18next";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ReadFormatAnswers } from "@/api/endpoints";

import { ReadFormatAnswersPanel } from "./ReadFormatAnswersPanel";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const PHOTO_ID = "0199aa00-1111-7222-8333-444455556666";
const ORDER_UUID = "0199aa00-9999-7222-8333-444455550000";

const ANSWERS: ReadFormatAnswers = {
  read_format: { id: "f-1", name: "Water monthly walk", version_id: "v-2", version_no: 2 },
  needs_review: true,
  answers: [
    {
      question_key: "seal_intact", label: "Seal intact?", data_type: "boolean", value: false,
      photo_id: null, issue: null, work_order: null,
    },
    {
      question_key: "photo_of_the_seal", label: "Photo of the seal", data_type: "photo",
      value: PHOTO_ID, photo_id: PHOTO_ID, issue: null, work_order: null,
    },
    {
      question_key: "meter_condition", label: "Meter condition", data_type: "select", value: "Damaged",
      photo_id: null, issue: null, work_order: { id: ORDER_UUID, order_no: "WO-4870" },
    },
    {
      question_key: "gate_code", label: "Gate code", data_type: "text", value: "Purple",
      photo_id: null, issue: "not_asked", work_order: null,
    },
    {
      question_key: "why_not_read", label: "Why not read", data_type: "text", value: null,
      photo_id: null, issue: "required_missing", work_order: null,
    },
  ],
};

function mount(answers: ReadFormatAnswers | null) {
  return render(
    <MemoryRouter initialEntries={["/brazosbend/reads/r-1"]}>
      <Routes>
        <Route path="/:tenant/reads/:readId" element={<ReadFormatAnswersPanel answers={answers} />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MQ-033 task 13 — the Read format panel on a reading", () => {
  it("names the format and its version, and says Needs review when flagged", () => {
    mount(ANSWERS);
    expect(screen.getByText(t("metering.read.panel.readFormat"))).toBeInTheDocument();
    expect(screen.getByText("Water monthly walk · v2")).toBeInTheDocument();
    expect(screen.getByText(t("metering.read.answers.needsReview"))).toBeInTheDocument();
  });

  it("shows each question in the utility's own words with its answer", () => {
    const { container } = mount(ANSWERS);
    const labels = [...container.querySelectorAll("[data-answer-label]")].map((el) => el.textContent);
    expect(labels).toEqual(["Seal intact?", "Photo of the seal", "Meter condition", "Gate code", "Why not read"]);
    const seal = container.querySelector('[data-answer="seal_intact"]') as HTMLElement;
    expect(seal).toHaveTextContent(t("metering.no"));
    const condition = container.querySelector('[data-answer="meter_condition"]') as HTMLElement;
    expect(condition).toHaveTextContent("Damaged");
  });

  it("a flagged answer is SHOWN with its flag, never hidden", () => {
    const { container } = mount(ANSWERS);
    const gate = container.querySelector('[data-answer="gate_code"]') as HTMLElement;
    expect(gate).toHaveTextContent("Purple");
    expect(within(gate).getByText(t("metering.read.answers.issue.not_asked"))).toBeInTheDocument();
    const missing = container.querySelector('[data-answer="why_not_read"]') as HTMLElement;
    expect(within(missing).getByText(t("metering.read.answers.issue.required_missing"))).toBeInTheDocument();
  });

  it("links the raised job by its ORDER NUMBER, never its id (B14 rule 31)", () => {
    mount(ANSWERS);
    const link = screen.getByRole("link", { name: "WO-4870" });
    expect(link).toHaveAttribute("href", "/brazosbend/work/orders/WO-4870");
    expect(document.body.textContent).not.toContain(ORDER_UUID);
  });

  it("draws a photo answer as a thumbnail from the API that opens the picture", () => {
    const { container } = mount(ANSWERS);
    const thumb = container.querySelector("[data-answer-photo] img") as HTMLImageElement;
    expect(thumb.getAttribute("src")).toContain(`/brazosbend/reads/photos/${PHOTO_ID}/content`);
    expect(document.body.textContent).not.toContain(PHOTO_ID);
    fireEvent.click(screen.getByRole("button", { name: t("metering.read.answers.openPhoto", { label: "Photo of the seal" }) }));
    const viewer = document.querySelector("[data-answer-photo-viewer] img") as HTMLImageElement;
    expect(viewer.getAttribute("src")).toContain(`/reads/photos/${PHOTO_ID}/content`);
    expect(viewer).toHaveAttribute("alt", "Photo of the seal");
  });

  it("a reading with no format renders nothing at all", () => {
    const { container } = mount(null);
    expect(container.innerHTML).toBe("");
  });

  it("an unknown version says so and still lists what was sent", () => {
    const { container } = mount({ ...ANSWERS, read_format: null, needs_review: true });
    expect(screen.getByText(t("metering.read.answers.formatUnknown"))).toBeInTheDocument();
    expect(container.querySelectorAll("[data-answer-label]")).toHaveLength(5);
  });
});
