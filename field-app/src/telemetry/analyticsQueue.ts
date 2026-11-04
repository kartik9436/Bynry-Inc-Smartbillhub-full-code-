/**
 * The analytics queue — T-73, R67, AD-18 ("both queue offline").
 *
 * A whole shift can pass with no signal, so events are held on the handset and
 * sent later. This is the third queue: it sends only when `gate.canSend()` says
 * the outbox and the photo queue are clear (`workGate.ts`).
 *
 * Bounded: past `maxEvents` the OLDEST event is dropped and a counter goes up.
 * The counter is persisted and leaves as one `telemetry_dropped` event on the
 * next successful send, so we learn the queue was too small without the
 * technician ever learning it existed.
 *
 * Every event is scrubbed on the way IN (so the disk never holds customer data)
 * and again on the way OUT (so an event written under an older allow list is
 * judged by the one that ships).
 */
import { readJson, writeJson } from './store';
import type { Scrubber } from './scrubber';
import type { KeyValueStore, RawEvent, ScrubbedEvent, TelemetryIdentity } from './types';
import type { WorkGate } from './workGate';
import { withTimeout, type SendOutcome } from './offline';

/** Provider-neutral analytics sink. `posthog.ts` adapts PostHog to it. */
export interface AnalyticsTransport {
  send(events: readonly ScrubbedEvent[], identity: TelemetryIdentity | null): Promise<void>;
}

export interface AnalyticsQueueOptions {
  store: KeyValueStore;
  scrubber: Scrubber;
  gate: WorkGate;
  transport: AnalyticsTransport;
  identity: () => TelemetryIdentity | null;
  /** Held through a shift. ~2,000 is several shifts of screen views and timings. */
  maxEvents?: number;
  batchSize?: number;
  timeoutMs?: number;
  /** Crashes the crash file had to drop, reported with the event counter. */
  droppedCrashes?: () => number;
  resetDroppedCrashes?: () => void;
}

export interface AnalyticsQueue {
  track(raw: RawEvent): void;
  flush(): Promise<SendOutcome>;
  size(): number;
  droppedCount(): number;
}

const QUEUE_KEY = 'telemetry.events.v1';
const DROPPED_KEY = 'telemetry.events.dropped.v1';

export function createAnalyticsQueue(opts: AnalyticsQueueOptions): AnalyticsQueue {
  const maxEvents = opts.maxEvents ?? 2000;
  const batchSize = opts.batchSize ?? 50;
  const timeoutMs = opts.timeoutMs ?? 15_000;
  const { store, scrubber, gate, transport } = opts;

  let queue: ScrubbedEvent[] = readJson<ScrubbedEvent[]>(store, QUEUE_KEY, []);
  if (!Array.isArray(queue)) queue = [];
  let dropped = readJson<number>(store, DROPPED_KEY, 0);
  if (typeof dropped !== 'number' || !Number.isFinite(dropped)) dropped = 0;
  let sending = false;
  // Events dropped off the FRONT while a batch was in flight were part of that
  // batch; the splice after a successful send must not remove newer ones for them.
  let shiftedWhileSending = 0;

  const persist = () => {
    writeJson(store, QUEUE_KEY, queue);
    writeJson(store, DROPPED_KEY, dropped);
  };

  return {
    track(raw) {
      try {
        const event = scrubber.scrubEvent(raw);
        if (!event) return;
        queue.push(event);
        if (queue.length > maxEvents) {
          const over = queue.length - maxEvents;
          queue.splice(0, over);
          dropped += over;
          if (sending) shiftedWhileSending += over;
        }
        persist();
      } catch {
        // Telemetry never surfaces a fault to the technician (R67).
      }
    },

    async flush() {
      if (sending) return 'busy';
      if (!gate.canSend()) return 'yielded';
      const crashesDropped = opts.droppedCrashes?.() ?? 0;
      if (queue.length === 0 && dropped === 0 && crashesDropped === 0) return 'empty';
      sending = true;
      shiftedWhileSending = 0;
      try {
        const batch = queue
          .slice(0, batchSize)
          .map((e) => scrubber.scrubEvent({ name: e.name, fields: e.fields }))
          .filter((e): e is ScrubbedEvent => e !== null);
        const taken = Math.min(batchSize, queue.length);
        const droppedAtSend = dropped;
        if (droppedAtSend > 0 || crashesDropped > 0) {
          const counter = scrubber.scrubEvent({
            name: 'telemetry_dropped',
            fields: { events: droppedAtSend, crashes: crashesDropped },
          });
          if (counter) batch.push(counter);
        }
        await withTimeout(() => transport.send(batch, scrubber.scrubIdentity(opts.identity())), timeoutMs);
        queue.splice(0, Math.max(0, taken - shiftedWhileSending));
        dropped -= droppedAtSend;
        if (crashesDropped > 0) opts.resetDroppedCrashes?.();
        persist();
        return 'sent';
      } catch {
        return 'failed';
      } finally {
        sending = false;
      }
    },

    size: () => queue.length,
    droppedCount: () => dropped,
  };
}
