/**
 * T-76 — PROVE THE SCRUBBER BY BREAKING IT (Security §5, R66).
 *
 * FF-25 Customer and FF-20 Readings are not built yet, so two stand-ins put the
 * drawings' own values on screen (wireframes/phone/FF-25-customer.png,
 * FF-20-readings.png; the balance is FF-26's "$241.38", since FF-25 draws none).
 * Each one crashes, the handset records it, the next start sends it — and the
 * test reads exactly what left the handset: the crash report, the analytics
 * batch, the identity, and the crash file on disk before anything was sent.
 *
 * The second half runs the SAME scenario through a pass-through scrubber and
 * requires the leak detector to fire. That is the permanent half of "a privacy
 * guard nobody has watched fail is not a guard": if the detector ever stops
 * being able to see a name, this file goes red rather than green.
 */
import { Component, type ReactNode } from 'react';
import { Text, View } from 'react-native';
import { act, render, screen } from '@testing-library/react-native';
import {
  TelemetryErrorBoundary,
  createFakeCrashReporter,
  createMemoryStore,
  createScrubber,
  createTelemetry,
  installGlobalCrashHandler,
  type AnalyticsTransport,
  type ErrorUtilsLike,
  type Scrubber,
  type ScrubbedCrashReport,
  type ScrubbedEvent,
  type TelemetryIdentity,
} from '../../src/telemetry';

// ── The account on screen, from the drawings ─────────────────────────────────
const CUSTOMER = {
  name: 'Sarah Miller',
  street: '1400 Elm Street · Unit A',
  locality: 'Austin, TX 78704',
  account: 'A-10432',
  balance: '$241.38',
  meter: 'W-4471',
};
/** The person holding the handset — may be named (PO 2026-10-21). Not a customer. */
const TECHNICIAN = { name: 'Dana Reyes' };
const READINGS = [
  { meter: 'W-4471', value: 1204, shown: '1,204', last: '48,180' },
  { meter: 'W-4471-A', value: 12564, shown: '12,564', last: '12,210' },
];

/** Every string that must never leave the handset, in the forms it could take. */
const FORBIDDEN_TEXT = [
  'Sarah', 'Miller', '1400 Elm', 'Elm Street', 'Austin', '78704', 'A-10432', '10432',
  '241.38', 'W-4471', '1,204', '12,564', '48,180', '12,210',
];
/** Reading values as bare numbers, wherever they sit in the payload. */
const FORBIDDEN_NUMBERS = [1204, 12564, 48180, 12210, 241.38, 10432];

/**
 * The leak detector. Walks every value of a payload. Numbers under `line`/`col`
 * inside a stack frame, and `at` timestamps, are exempt from the NUMBER check
 * only: they come from the JavaScript engine, not the screen, and a frame at
 * line 1204 of a renderer bundle would otherwise be a false alarm. Their keys
 * and every string are still checked.
 */
function findLeaks(payload: unknown, path = '$'): string[] {
  const leaks: string[] = [];
  const visit = (v: unknown, p: string, key: string) => {
    if (typeof v === 'string') {
      for (const bad of FORBIDDEN_TEXT) {
        if (v.includes(bad)) leaks.push(`${p} = ${JSON.stringify(v)} carries "${bad}"`);
      }
    } else if (typeof v === 'number') {
      const engineNumber = key === 'line' || key === 'col' || key === 'at';
      if (!engineNumber && FORBIDDEN_NUMBERS.includes(v)) leaks.push(`${p} = ${v}`);
    } else if (Array.isArray(v)) {
      v.forEach((x, i) => visit(x, `${p}[${i}]`, String(i)));
    } else if (v && typeof v === 'object') {
      for (const [k, x] of Object.entries(v)) {
        for (const bad of FORBIDDEN_TEXT) if (k.includes(bad)) leaks.push(`${p} has key "${k}"`);
        visit(x, `${p}.${k}`, k);
      }
    }
  };
  visit(payload, path, '');
  return leaks;
}

// ── The stand-ins ────────────────────────────────────────────────────────────
function CustomerStandIn({ explode }: { explode: boolean }) {
  if (explode) {
    // The realistic leak: an error message built from what is on screen.
    const err = new TypeError(
      `Cannot read balance ${CUSTOMER.balance} for ${CUSTOMER.account} ${CUSTOMER.name}, ${CUSTOMER.street}`,
    );
    Object.assign(err, { account: CUSTOMER }); // and a payload hung on the error
    throw err;
  }
  return (
    <View>
      <Text>{CUSTOMER.name}</Text>
      <Text>{CUSTOMER.street}</Text>
      <Text>{CUSTOMER.locality}</Text>
      <Text>{`Account ${CUSTOMER.account} · since Mar 2024`}</Text>
      <Text>{CUSTOMER.balance}</Text>
      <Text>{CUSTOMER.meter}</Text>
    </View>
  );
}

function ReadingsStandIn({ explode }: { explode: boolean }) {
  if (explode) {
    throw new RangeError(`Reading ${READINGS[0]!.shown} gal outside 40,000–50,000, last ${READINGS[0]!.last}`);
  }
  return (
    <View>
      {READINGS.map((r) => (
        <Text key={r.meter}>{`${r.meter} ${r.shown} gal · last ${r.last}`}</Text>
      ))}
    </View>
  );
}

/** Lets a test flip a mounted screen into its crash without remounting it. */
class Switch extends Component<{ children: (explode: boolean) => ReactNode }, { explode: boolean }> {
  state = { explode: false };
  render() {
    return this.props.children(this.state.explode);
  }
}

// ── The scenario: put the account on screen, misuse telemetry, crash, restart ─
interface Outgoing {
  crashFileBeforeSend: unknown;
  crashes: ScrubbedCrashReport[];
  batches: { events: readonly ScrubbedEvent[]; identity: TelemetryIdentity | null }[];
  shownOnScreen: boolean;
}

async function runScenario(scrubber?: Scrubber): Promise<Outgoing> {
  const store = createMemoryStore();
  const batches: Outgoing['batches'] = [];
  const analytics: AnalyticsTransport = {
    async send(events, identity) {
      batches.push(JSON.parse(JSON.stringify({ events, identity })));
    },
  };
  // An identity object carrying more than it should. The technician's own id and
  // name are allowed (PO 2026-10-21, "Yes, by name"); the customer riding along
  // under `name` / `customerName` / `account` is not, and must be dropped.
  const leakyIdentity = {
    tenant: 'carl-water',
    role: 'technician',
    deviceId: '3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47',
    technicianId: 'u-1931',
    technicianName: TECHNICIAN.name,
    userId: 'u-1931',
    name: CUSTOMER.name,
    customerName: CUSTOMER.name,
    account: CUSTOMER.account,
  } as TelemetryIdentity;
  const t = createTelemetry({
    store,
    analytics,
    identity: () => leakyIdentity,
    clock: () => 1_760_000_000_000,
    scrubber,
  });

  // Telemetry misused the way a hurried screen would misuse it.
  t.track({ name: 'screen_view', fields: { screen: 'FF-25', customer: CUSTOMER.name, account: CUSTOMER.account } });
  t.track({ name: 'customer_opened', fields: { name: CUSTOMER.name, balance: CUSTOMER.balance } });
  t.track({ name: 'screen_view', fields: { screen: CUSTOMER.street } });
  t.track({ name: 'reading_saved', fields: { value: READINGS[0]!.value, meter: READINGS[0]!.meter } });
  t.track({ name: 'flow_abandoned', fields: { screen: 'FF-20', step: 2, last_read: READINGS[0]!.last } });

  // FF-25: the account is on screen, then the screen crashes during render.
  let flipCustomer: ((v: boolean) => void) | undefined;
  render(
    <TelemetryErrorBoundary capture={t.crashes} screen="FF-25">
      <Switch ref={(s) => { flipCustomer = (v) => s?.setState({ explode: v }); }}>
        {(explode) => <CustomerStandIn explode={explode} />}
      </Switch>
    </TelemetryErrorBoundary>,
  );
  const shownOnScreen =
    screen.queryByText(CUSTOMER.name) !== null && screen.queryByText(CUSTOMER.balance) !== null;
  const quiet = jest.spyOn(console, 'error').mockImplementation(() => {});
  act(() => flipCustomer?.(true));

  // FF-20: a reading on screen, then a crash during render.
  render(
    <TelemetryErrorBoundary capture={t.crashes} screen="FF-20">
      <ReadingsStandIn explode />
    </TelemetryErrorBoundary>,
  );
  quiet.mockRestore();

  // And an uncaught error through React Native's global handler.
  let handler: (e: unknown, fatal?: boolean) => void = () => {};
  const errorUtils: ErrorUtilsLike = {
    getGlobalHandler: () => () => {},
    setGlobalHandler: (h) => { handler = h; },
  };
  const uninstall = installGlobalCrashHandler(t.crashes, errorUtils, () => 'FF-25');
  handler(new Error(`${CUSTOMER.name} owes ${CUSTOMER.balance}`), true);
  uninstall();

  // The crash file as it sits on the handset, before any send.
  const crashFileBeforeSend = JSON.parse(store.dump()['telemetry.crashes.v1'] ?? 'null');

  // "Next start": the work queues are clear and the handset is online.
  t.gate.reportWork({ outbox: 0, photos: 0, syncing: false, online: true });
  const reporter = createFakeCrashReporter();
  await t.flush(reporter);

  return { crashFileBeforeSend, crashes: reporter.sent, batches, shownOnScreen };
}

describe('T-76 the scrubber, proved', () => {
  it('sends a crash from FF-25 and FF-20 with no name, address, account, balance or reading', async () => {
    const out = await runScenario();

    // The guard itself, first, so a failure names the leak rather than a shape.
    expect([
      ...findLeaks(out.crashFileBeforeSend, 'crashFile'),
      ...findLeaks(out.crashes, 'crashes'),
      ...findLeaks(out.batches, 'analytics'),
    ]).toEqual([]);

    // Not vacuous: the account WAS on screen, and reports DID leave.
    expect(out.shownOnScreen).toBe(true);
    expect(out.crashes.map((c) => [c.screen, c.errorType])).toEqual([
      ['FF-25', 'TypeError'],
      ['FF-20', 'RangeError'],
      ['FF-25', 'Error'],
    ]);
    expect(out.crashes[0]!.frames.length).toBeGreaterThan(0);
    // Component NAMES survive (the test transform names a destructured-props
    // function after its first prop, so the stand-in itself reads as `explode`
    // and is dropped by the capitalised-name rule — the class names remain).
    expect(out.crashes[0]!.components).toEqual(['Switch', 'TelemetryErrorBoundary']);
    expect(out.batches.length).toBe(1);
    const sentNames = out.batches[0]!.events.map((e) => e.name);
    // `customer_opened` and `reading_saved` are not on the list: dropped whole.
    // The second screen_view carried an address as its screen: field dropped.
    expect(sentNames).toEqual(['screen_view', 'screen_view', 'flow_abandoned']);
    expect(out.batches[0]!.events.map((e) => e.fields)).toEqual([
      { screen: 'FF-25' },
      {},
      { screen: 'FF-20', step: 2 },
    ]);
  });

  it('keeps identity to tenant, role, device id and the TECHNICIAN — never the customer', async () => {
    const out = await runScenario();
    const identities = [...out.crashes.map((c) => c.identity), ...out.batches.map((b) => b.identity)];
    expect(identities.length).toBe(4);
    for (const id of identities) {
      expect(id).toEqual({
        tenant: 'carl-water',
        role: 'technician',
        deviceId: '3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47',
        technicianId: 'u-1931',
        technicianName: TECHNICIAN.name,
      });
    }
  });

  it('the detector goes RED when the scrubber lets everything through', async () => {
    // A scrubber that copies what it is given, as a hurried "fix" might.
    const passThrough: Scrubber = {
      scrubEvent: (raw) => ({ name: raw.name, fields: raw.fields ?? {}, at: 0 }) as unknown as ScrubbedEvent,
      scrubIdentity: (raw) => raw as TelemetryIdentity,
      scrubCrash: (raw, breadcrumbs, identity) =>
        ({
          kind: 'crash',
          errorType: 'Error',
          message: raw.error instanceof Error ? raw.error.message : String(raw.error),
          extra: raw.error,
          fatal: raw.fatal,
          screen: raw.screen ?? null,
          frames: [],
          components: [],
          breadcrumbs,
          identity,
          at: 0,
        }) as unknown as ScrubbedCrashReport,
      rescrubCrash: (stored) => stored as ScrubbedCrashReport,
    };
    const out = await runScenario(passThrough);
    const leaks = [...findLeaks(out.crashes, 'crashes'), ...findLeaks(out.batches, 'analytics')];
    const joined = leaks.join('\n');
    for (const must of ['Sarah', 'A-10432', '241.38', '1,204', '1400 Elm']) {
      expect(joined).toContain(must);
    }
    expect(leaks.some((l) => l.endsWith('= 1204'))).toBe(true);
  });
});

// Keeps the real scrubber import live, so a rename of the factory is a compile error here.
void createScrubber;
