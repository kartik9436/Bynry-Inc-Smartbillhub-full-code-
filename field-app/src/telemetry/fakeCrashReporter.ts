/**
 * The in-memory `CrashReporter` — what tests send to in place of Crashlytics
 * (ruled 2026-10-21; its SDK is not installed yet). It records exactly the
 * payload the Crashlytics adapter would receive, which is what T-76 inspects.
 */
import type { CrashReporter } from './crashReporter';
import type { ScrubbedCrashReport } from './types';

export interface FakeCrashReporter extends CrashReporter {
  readonly sent: ScrubbedCrashReport[];
  /** Make the next sends fail, as a dead endpoint would. */
  failWith(error: Error | null): void;
}

export function createFakeCrashReporter(): FakeCrashReporter {
  const sent: ScrubbedCrashReport[] = [];
  let failure: Error | null = null;
  return {
    sent,
    failWith(error) {
      failure = error;
    },
    async send(report) {
      if (failure) throw failure;
      // A deep copy through JSON: what a provider receives is a serialised
      // payload, so that is what a test should look at.
      sent.push(JSON.parse(JSON.stringify(report)) as ScrubbedCrashReport);
    },
  };
}
