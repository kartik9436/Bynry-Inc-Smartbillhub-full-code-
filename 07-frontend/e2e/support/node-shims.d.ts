// ── Trace ──────────────────────────────────────────────
// Component: the four Node declarations the E2E harness needs to TYPECHECK.
// Rules:    CLAUDE.md hard-won law 1 (a claim of coverage is not coverage)
// ───────────────────────────────────────────────────────
//
// WHY THIS FILE EXISTS, AND WHEN TO DELETE IT.
//
// `tsconfig.json` includes only `src`, so `npx tsc --noEmit` — the command every
// packet in this repo quotes as `tsc✔` — has never once looked at `e2e/`. The
// support kit reads files and the specs read `process.env`, and none of it was
// checked by anything. `tsconfig.e2e.json` now points a typecheck at the
// directory, and that typecheck immediately failed for want of `@types/node`.
//
// Adding `@types/node` is the RIGHT fix and is deliberately not made here: it
// changes `package.json` and `package-lock.json`, which are shared with every
// other lane, and this lane owns neither. So this file declares the exact
// surface the harness uses — four functions and one env object — and nothing
// else, so an unchecked directory becomes a checked one today.
//
// **DELETE THIS FILE the moment `@types/node` is a devDependency.** Two
// declarations of `node:fs` will conflict, and the real ones are better.

declare const process: {
  env: Record<string, string | undefined>;
  stdout: { write(chunk: string): boolean };
  // Added 2026-08-15 (DEF-113): the run receipt is now one immutable shard per
  // run, and the pid is part of the name that makes two concurrent runs unable
  // to choose the same one.
  pid: number;
};

declare module "node:fs" {
  export function readFileSync(path: string, encoding: string): string;
  // Added 2026-08-11 when the census began WRITING its report rather than only
  // printing it — a suite that reports what it executed has to put that
  // somewhere CI can read.
  export function mkdirSync(path: string, options?: { recursive?: boolean }): void;
  export function writeFileSync(path: string, data: string, encoding?: string): void;
  // Added 2026-08-15 (DEF-113). The receipt became a directory of per-run shards
  // folded into a merged view: `readdirSync` to fold them, `renameSync` for the
  // atomic publish (a reader must never see half a file), `statSync`+`rmSync`
  // for retention housekeeping.
  export function readdirSync(path: string): string[];
  export function renameSync(from: string, to: string): void;
  export function statSync(path: string): { mtimeMs: number };
  export function rmSync(path: string, options?: { force?: boolean; recursive?: boolean }): void;
}

// Added 2026-09-30 by the final bulk-run lane: J72's accuracy walk plants a
// reading between two runs and J73's F1 kills and restarts a real billing
// worker, each through a command the walk is given in the environment
// (`E2E_J72_LATE_READ`, `E2E_J73_WORKER_KILL`/`_START`): `execSync`.
// Added 2026-09-30 by the E16/E17 lane. The single-account trace
// (`J72-bulk-bill-run-single-account-trace.spec.ts`) asks the DATABASE after
// every step through `10-scripts/verify_bulk_run.py`, and re-runs the J72 seed
// between the months — both are child processes. Exactly the one function and
// the fields it reads, for the reason the others here are narrow.
declare module "node:child_process" {
  export function execSync(command: string, options?: { stdio?: "inherit" | "pipe" | "ignore" }): unknown;
  export function spawnSync(
    command: string,
    args: string[],
    options?: { cwd?: string; env?: Record<string, string | undefined>; encoding?: string },
  ): { status: number | null; stdout: string; stderr: string };
}

declare module "node:path" {
  export function resolve(...segments: string[]): string;
  export function dirname(path: string): string;
  export function join(...segments: string[]): string;
}

declare module "node:url" {
  export function fileURLToPath(url: URL | string): string;
}

// Added 2026-08-15 by the batch-B journey lane. T5-28 (upload guards) posts
// real multipart bodies, and Playwright's `multipart` file field is typed
// `Buffer` — a Uint8Array does not satisfy it — so a spec that uploads a file
// could not typecheck at all without this. The surface declared is exactly the
// two constructors the spec uses and nothing else, for the same reason the four
// above are narrow: when `@types/node` lands, the real declaration is better
// and this whole file goes.
declare class Buffer extends Uint8Array {
  static from(input: string, encoding?: string): Buffer;
  static alloc(size: number, fill?: number): Buffer;
}
