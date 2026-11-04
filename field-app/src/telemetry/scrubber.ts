/**
 * THE SCRUBBER — T-74, R66, R68, R69, AD-19.
 *
 * The only code that turns a RAW event or crash into a SCRUBBED one (see
 * `types.ts` — the scrubbed types are branded, so nothing else can make one).
 * It runs at the moment of capture, BEFORE anything is written to the handset's
 * telemetry queue or crash file, so customer data never reaches the disk either.
 *
 * Rules it applies, every one of them "keep only", never "remove":
 *   - an event whose name is not on the allow list is dropped whole;
 *   - a field not listed under its event is dropped, and so is one whose value
 *     fails its rule;
 *   - a crash keeps the error's CLASS NAME and its stack as code coordinates
 *     (function, file basename, line, column). The MESSAGE is never kept — an
 *     error message is free text and the commonest place a name ends up;
 *   - identity passes its OWN allow list (`IDENTITY_ALLOW_LIST`): tenant, role and
 *     an anonymous device id are required, the technician's id and name optional
 *     (PO 2026-10-21, "Yes, by name" — supersedes R69's anonymous-only identity);
 *     an identity missing a required key is sent as null. A CUSTOMER's name has
 *     no place in identity or in any event.
 *
 * Session replay is not a scrubber setting — it is off at the client (`posthog.ts`).
 */
import {
  ALLOW_LIST,
  IDENTITY_ALLOW_LIST,
  IDENTITY_REQUIRED,
  type AllowListPolicy,
} from './allowList';
import type {
  Clock,
  CrashFrame,
  RawCrash,
  RawEvent,
  ScrubbedCrashReport,
  ScrubbedEvent,
  TelemetryIdentity,
  TelemetryValue,
} from './types';

const MAX_FRAMES = 40;
const MAX_COMPONENTS = 30;

export interface Scrubber {
  scrubEvent(raw: RawEvent): ScrubbedEvent | null;
  scrubCrash(
    raw: RawCrash,
    breadcrumbs: readonly ScrubbedEvent[],
    identity: TelemetryIdentity | null,
  ): ScrubbedCrashReport;
  scrubIdentity(raw: unknown): TelemetryIdentity | null;
  /** Re-judge a report read back from the crash file against THIS build's rules. */
  rescrubCrash(stored: unknown): ScrubbedCrashReport | null;
}

const ERROR_TYPE = /^[A-Z][A-Za-z]{0,48}$/;
const FN_NAME = /^(?:new )?(?:[A-Za-z_$][\w$]*|<anonymous>)(?:\.(?:[A-Za-z_$][\w$]*|<anonymous>))*$/;
const FILE_BASENAME = /^[\w.-]{1,120}$/;
const COMPONENT = /^[A-Z][\w$]{0,80}$/;
// V8:     at fn (/path/file.ts:12:34)   |   at /path/file.ts:12:34
// Hermes: at fn (address at index.android.bundle:1:2345)
const FRAME = /^\s*at (?:(.+?) \()?(?:address at )?([^()\s]+?):(\d+):(\d+)\)?\s*$/;

function basename(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] ?? '';
}

function stackWithoutMessage(error: Error): string {
  const stack = typeof error.stack === 'string' ? error.stack : '';
  // V8 begins the stack with "<name>: <message>", and a message can span lines —
  // so cut the message off by VALUE before reading a single frame, rather than
  // trusting that frame-shaped lines are frames.
  const head = `${error.name}: ${error.message}`;
  if (error.message && stack.startsWith(head)) return stack.slice(head.length);
  return stack;
}

export function parseFrames(error: unknown): CrashFrame[] {
  if (!(error instanceof Error)) return [];
  const frames: CrashFrame[] = [];
  for (const line of stackWithoutMessage(error).split('\n')) {
    if (frames.length >= MAX_FRAMES) break;
    const m = FRAME.exec(line);
    if (!m) continue;
    const fnRaw = (m[1] ?? '').trim();
    const file = basename(m[2] ?? '');
    frames.push({
      fn: fnRaw && FN_NAME.test(fnRaw) ? fnRaw : '?',
      file: FILE_BASENAME.test(file) ? file : '?',
      line: Number(m[3]),
      col: Number(m[4]),
    });
  }
  return frames;
}

export function parseComponents(componentStack: string | undefined): string[] {
  if (!componentStack) return [];
  const out: string[] = [];
  for (const line of componentStack.split('\n')) {
    if (out.length >= MAX_COMPONENTS) break;
    const m = /^\s*(?:in|at) ([^\s(]+)/.exec(line);
    const name = m?.[1];
    if (name && COMPONENT.test(name)) out.push(name);
  }
  return out;
}

function errorType(error: unknown): string {
  if (!(error instanceof Error)) return 'NonError';
  return ERROR_TYPE.test(error.name) ? error.name : 'Error';
}

export function createScrubber(
  clock: Clock = Date.now,
  policy: AllowListPolicy = ALLOW_LIST,
): Scrubber {
  function scrubEvent(raw: RawEvent): ScrubbedEvent | null {
    if (!raw || typeof raw.name !== 'string') return null;
    if (!Object.prototype.hasOwnProperty.call(policy, raw.name)) return null;
    const rules = policy[raw.name] ?? {};
    const fields: Record<string, TelemetryValue> = {};
    const given = raw.fields ?? {};
    for (const key of Object.keys(rules)) {
      if (!Object.prototype.hasOwnProperty.call(given, key)) continue;
      const rule = rules[key];
      const value = given[key];
      if (rule && rule(value)) fields[key] = value;
    }
    return { name: raw.name, fields, at: clock() } as unknown as ScrubbedEvent;
  }

  function scrubIdentity(raw: unknown): TelemetryIdentity | null {
    if (!raw || typeof raw !== 'object') return null;
    const r = raw as Record<string, unknown>;
    const id = IDENTITY_ALLOW_LIST;
    for (const key of IDENTITY_REQUIRED) {
      if (!id[key](r[key])) return null;
    }
    const out: TelemetryIdentity = {
      tenant: r.tenant as string,
      role: r.role as string,
      deviceId: r.deviceId as string,
    };
    // The technician's own id and name (PO 2026-10-21). Each kept only when it
    // passes its rule; every other key on the object — `name`, `userId`,
    // `customerName` — is never read, so it never leaves.
    if (id.technicianId(r.technicianId)) out.technicianId = r.technicianId;
    if (id.technicianName(r.technicianName)) out.technicianName = r.technicianName.trim();
    return out;
  }

  function scrubCrash(
    raw: RawCrash,
    breadcrumbs: readonly ScrubbedEvent[],
    identity: TelemetryIdentity | null,
  ): ScrubbedCrashReport {
    const screen = typeof raw.screen === 'string' && /^(FF|RW)-\d{2}$/.test(raw.screen) ? raw.screen : null;
    // Breadcrumbs arrive already scrubbed (the type says so); they are re-run
    // through the policy anyway, because a crash file is the last stop before
    // the network and the brand is a compile-time promise, not a runtime one.
    const crumbs = breadcrumbs
      .map((b) => scrubEvent({ name: b.name, fields: b.fields }))
      .filter((b): b is ScrubbedEvent => b !== null);
    return {
      kind: 'crash',
      errorType: errorType(raw.error),
      fatal: raw.fatal === true,
      screen,
      frames: parseFrames(raw.error),
      components: parseComponents(raw.componentStack),
      breadcrumbs: crumbs,
      identity: scrubIdentity(identity),
      at: clock(),
    } as unknown as ScrubbedCrashReport;
  }

  function rescrubCrash(stored: unknown): ScrubbedCrashReport | null {
    if (!stored || typeof stored !== 'object') return null;
    const r = stored as Record<string, unknown>;
    if (r.kind !== 'crash') return null;
    const frames = (Array.isArray(r.frames) ? r.frames : [])
      .slice(0, MAX_FRAMES)
      .flatMap((f: unknown): CrashFrame[] => {
        if (!f || typeof f !== 'object') return [];
        const { fn, file, line, col } = f as Record<string, unknown>;
        if (!Number.isInteger(line) || !Number.isInteger(col)) return [];
        return [
          {
            fn: typeof fn === 'string' && FN_NAME.test(fn) ? fn : '?',
            file: typeof file === 'string' && FILE_BASENAME.test(file) ? file : '?',
            line: line as number,
            col: col as number,
          },
        ];
      });
    const components = (Array.isArray(r.components) ? r.components : [])
      .slice(0, MAX_COMPONENTS)
      .filter((c: unknown): c is string => typeof c === 'string' && COMPONENT.test(c));
    const crumbs = (Array.isArray(r.breadcrumbs) ? r.breadcrumbs : [])
      .map((b: unknown) => {
        const e = b as { name?: unknown; fields?: unknown; at?: unknown } | null;
        if (!e || typeof e.name !== 'string') return null;
        const clean = scrubEvent({ name: e.name, fields: (e.fields ?? {}) as Record<string, unknown> });
        return clean && typeof e.at === 'number' ? ({ ...clean, at: e.at } as ScrubbedEvent) : clean;
      })
      .filter((b): b is ScrubbedEvent => b !== null);
    return {
      kind: 'crash',
      errorType: typeof r.errorType === 'string' && ERROR_TYPE.test(r.errorType) ? r.errorType : 'Error',
      fatal: r.fatal === true,
      screen: typeof r.screen === 'string' && /^(FF|RW)-\d{2}$/.test(r.screen) ? r.screen : null,
      frames,
      components,
      breadcrumbs: crumbs,
      identity: scrubIdentity(r.identity),
      at: typeof r.at === 'number' && Number.isFinite(r.at) ? r.at : clock(),
    } as unknown as ScrubbedCrashReport;
  }

  return { scrubEvent, scrubCrash, scrubIdentity, rescrubCrash };
}
