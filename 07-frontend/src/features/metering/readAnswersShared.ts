// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 13: the office sees the read-format
//           answers (the reading's page, the Reads list's Answer filter).
// Rules:    BR-MET-1218 · BR-SHL-011 (the filter lives in the URL like every
//           other) · B14 rule 31 (an id builds an address, never shows) ·
//           NFR-3 (the vocabulary is server-paged and searched)
// Tests:    ReadAnswerFilter.dom.test.tsx · ReadFormatAnswersPanel.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The pure half of the answer screens: the vocabulary's two reads, the URL
 * grammar of an answer filter, and an answer's words.
 *
 * ⚠ **AN ANSWER FILTER IS NOT AN `f.` FILTER, AND THAT IS WHY IT HAS ITS OWN
 * GRAMMAR HERE.** `TableConfig.filters` are DECLARED by the screen, and
 * `parseTableParams` restores only declared names — but a question key is the
 * UTILITY's own, so no screen can declare it in advance. The server already
 * reads `answer[<key>]=<value>` (task 10), so the URL uses that exact spelling
 * and the list request, the export body and the address bar say one thing.
 */
import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { Paginated } from "@/api/paginated";
import type { Translator } from "@/features/tenancy/settingsShared";

/** One question a clerk can filter by (`GET reads/answer-questions`). */
export interface AnswerQuestion {
  /** For React keys and `title` only — never a visible value. */
  read_format_id: string;
  format_name: string;
  version_no: number | null;
  key: string;
  /** The utility's own words, verbatim. */
  label: string;
  data_type: string;
  options: string[];
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** How many questions one search asks for. The box narrows; it never lists. */
export const ANSWER_QUESTION_PER = 20;

/** `GET /reads/answer-questions?q=` — published questions, searched. */
export async function searchAnswerQuestions(
  q: string,
  client: ApiClient = api,
): Promise<AnswerQuestion[]> {
  const params = new URLSearchParams({ q, per: String(ANSWER_QUESTION_PER) });
  const page = requireData(
    await client.get<Paginated<AnswerQuestion>>(`/reads/answer-questions?${params.toString()}`),
  );
  return page.results;
}

/** `GET /reads/answer-questions?key=…` — the words for chips restored from a URL. */
export async function answerQuestionsByKey(
  keys: readonly string[],
  client: ApiClient = api,
): Promise<AnswerQuestion[]> {
  if (keys.length === 0) return [];
  const params = new URLSearchParams({ per: String(Math.max(keys.length * 4, ANSWER_QUESTION_PER)) });
  for (const key of keys) params.append("key", key);
  const page = requireData(
    await client.get<Paginated<AnswerQuestion>>(`/reads/answer-questions?${params.toString()}`),
  );
  return page.results;
}

// ── The URL grammar ────────────────────────────────────────────────────────
const ANSWER_PARAM = /^answer\[(.+)\]$/;

/** `answer[<key>]=<value>` pairs from the address bar; empty ones dropped. */
export function answerFiltersFrom(params: URLSearchParams): Record<string, string> {
  const out: Record<string, string> = {};
  params.forEach((value, name) => {
    const match = ANSWER_PARAM.exec(name);
    if (match !== null && match[1] !== undefined && match[1].trim() !== "" && value !== "") {
      out[match[1]] = value;
    }
  });
  return out;
}

/** Write the answer filters onto a params object (which the caller owns). */
export function writeAnswerFilters(params: URLSearchParams, answers: Record<string, string>): void {
  for (const [key, value] of Object.entries(answers)) {
    if (key !== "" && value !== "") params.set(`answer[${key}]`, value);
  }
}

/** The answer filters as export-body filter entries — the SAME spelling the
 *  server's `read_formats.answer_filters` reads in both places. */
export function answerFilterEntries(answers: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(answers)) out[`answer[${key}]`] = value;
  return out;
}

// ── An answer's words ──────────────────────────────────────────────────────
/** Yes/no questions filter on the stored words `true` / `false`. */
export const ANSWER_YES = "true";
export const ANSWER_NO = "false";

/** The values a question offers as choices, or null for a typed one. */
export function answerChoices(
  question: Pick<AnswerQuestion, "data_type" | "options">,
  t: Translator,
): { value: string; label: string }[] | null {
  if (question.data_type === "boolean") {
    return [
      { value: ANSWER_YES, label: t("metering.yes") },
      { value: ANSWER_NO, label: t("metering.no") },
    ];
  }
  if (question.data_type === "select" || question.data_type === "multi_select") {
    return question.options.map((option) => ({ value: option, label: option }));
  }
  return null;
}

/** A filter value as a chip shows it — yes/no in words, anything else as typed. */
export function answerFilterValueText(value: string, t: Translator): string {
  if (value === ANSWER_YES) return t("metering.yes");
  if (value === ANSWER_NO) return t("metering.no");
  return value;
}

/** A stored answer as words, or null when there is nothing to show. A photo
 *  is not words — the panel draws it. */
export function answerValueText(value: unknown, t: Translator): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "boolean") return value ? t("metering.yes") : t("metering.no");
  if (Array.isArray(value)) return value.map((item) => String(item)).join(", ");
  if (typeof value === "object") return null;
  return String(value);
}

/** The address of a photograph answer's bytes, on the API's origin. */
export function answerPhotoHref(tenant: string, photoId: string): string | null {
  if (tenant === "" || photoId === "") return null;
  return apiHref(`/${tenant}/reads/photos/${photoId}/content`);
}
