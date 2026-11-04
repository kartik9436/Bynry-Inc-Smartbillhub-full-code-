// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — hand a CSV the server streamed to the
//           browser as a file (the Units and Audit tabs' ⤓, images 31, 34).
// ───────────────────────────────────────────────────────

/** Save `body` as `name`. The CONTENT is the server's; nothing is rebuilt here. */
export function saveCsv(body: string, name: string): void {
  const url = URL.createObjectURL(new Blob([body], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
