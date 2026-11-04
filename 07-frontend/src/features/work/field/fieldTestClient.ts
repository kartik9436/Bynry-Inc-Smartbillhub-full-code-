// A recording fake of the transport for the field-desk suites. Every call is
// kept with its method, path, query and body, and each GET is answered from a
// table keyed by PATH, so a case asserts what the screen ASKED for — the
// endpoint, the filter it sent, the body it posted — rather than what it drew.
import type { ApiClient } from "@/api/client";

export type Call = { method: string; path: string; query: Record<string, unknown>; body: unknown };

export type Answer = (call: Call) => unknown;

export function fakeClient(calls: Call[], answers: Record<string, Answer | unknown>): ApiClient {
  const send =
    (method: string) =>
    async (path: string, a?: unknown, b?: unknown): Promise<unknown> => {
      const options = (method === "GET" ? a : b) as { query?: Record<string, unknown> } | undefined;
      const call: Call = {
        method,
        path,
        query: options?.query ?? {},
        body: method === "GET" ? null : (a ?? null),
      };
      calls.push(call);
      const answer = answers[`${method} ${path}`] ?? answers[path];
      const data = typeof answer === "function" ? (answer as Answer)(call) : (answer ?? {});
      return { status: 200, data, etag: null, notModified: false };
    };
  return {
    request: send("REQUEST"),
    get: send("GET"),
    post: send("POST"),
    put: send("PUT"),
    patch: send("PATCH"),
    del: send("DELETE"),
  } as unknown as ApiClient;
}

export const commits = (calls: Call[]): Call[] => calls.filter((c) => c.method !== "GET");
