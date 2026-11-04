/**
 * MQ-009 (DEF-FLD-10610) — a job's status reads the SAME word, in the SAME
 * tone, on the Today card (FF-10) and on the job page (FF-15), and never as
 * the raw server code. PO 2026-10-26: *"A Scheduled everywhere"*.
 *
 * The defect: the card relabelled `scheduled` as *Dispatched*
 * (`jobStatus.ts`), while the job page printed `order.dispatch_state` raw, in
 * the green success tone, whatever it was. Nothing compared the two. Every
 * state is sent here UPPER-CASE, so a list that only matches lower-case, or a
 * chip that prints what it was given, both fail.
 */
import 'react-native-gesture-handler/jestSetup';

import { render, within } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';

import type { DayJob } from '../../../src/db/queries/day';
import { scoped } from '../../../src/db/scoped';
import { createFieldI18n } from '../../../src/i18n/i18n';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { JobCard } from '../../../src/screens/theDay/JobCard';
import { LEGEND, statusLook } from '../../../src/screens/theDay/jobStatus';
import { ThemeProvider } from '../../../src/theme';
import { makeHandset } from '../../session/fakes';
import { DANA, seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

/** The seven server states and the one word each reads, everywhere. */
const SEVEN: ReadonlyArray<[string, string]> = [
  ['QUEUED', 'Queued'],
  ['SCHEDULED', 'Scheduled'],
  ['EN_ROUTE', 'En route'],
  ['ON_SITE', 'On site'],
  ['ON_HOLD', 'On hold'],
  ['COMPLETE', 'Complete'],
  ['CANCELLED', 'Canceled'],
];

function cardJob(state: string): DayJob {
  return {
    id: 'wo-1', number: 'WO-1', type: 'Meter exchange', dispatchState: state, priorityCode: null,
    windowStart: null, windowEnd: null, dueAt: null, estMinutes: null, premiseId: null,
    addressLine: '1400 Elm Street', locality: null, region: null, postalCode: null, lat: null, lng: null, customerName: 'Sarah Miller',
  };
}

function renderCard(state: string) {
  const h = makeHandset();
  const noop = () => undefined;
  return render(
    <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={h.prefs}>
      <ThemeProvider initialMode="light">
        <JobCard job={cardJob(state)} distance={null} onOpen={noop} onStart={noop} onNavigate={null} onMore={noop} />
      </ThemeProvider>
    </I18nProvider>,
  );
}

function bg(node: { props: { style?: unknown } }): unknown {
  return (StyleSheet.flatten(node.props.style as never) as { backgroundColor?: unknown } | undefined)?.backgroundColor;
}

describe('MQ-009 — one state, one word, on the card and the job page', () => {
  test('the list normalises the server value and never invents a word', () => {
    expect(statusLook('SCHEDULED')).toEqual(statusLook('scheduled'));
    expect(statusLook(' En_Route ').labelKey).toBe('field.job.state.enRoute');
    expect(statusLook('scheduled').labelKey).toBe('field.job.state.scheduled');
    expect(statusLook('teleported').labelKey).toBeNull();
    expect(statusLook(null).labelKey).toBeNull();
    expect(LEGEND.map((l) => l.labelKey)).toEqual(['field.map.legend.inProgress', 'field.map.legend.scheduled', 'field.map.legend.queued']);
  });

  test.each(SEVEN)('%s reads "%s" in the same tone on FF-10 and FF-15, never the raw code', async (code, word) => {
    // The card.
    const card = renderCard(code);
    const strip = card.getByTestId('job-wo-1-state');
    expect(strip).toHaveTextContent(word);
    expect(card.queryByText(code)).toBeNull();
    const cardTone = bg(strip);
    card.unmount();

    // The job page, with the order as the server sent it.
    const f = seedWO4822();
    scoped(f.db, DANA).run(`UPDATE work_order SET dispatch_state = :st WHERE technician_id = :technician_id AND id = :id`, { st: code, id: WO });
    const app = await mountJob(f.services, 'FF-15', { params: { workOrderId: WO }, openJob: WO });
    const top = within(onTop('FF-15'));
    const chip = top.getByTestId('job-state');
    expect(chip).toHaveTextContent(word);
    expect(top.queryByText(code)).toBeNull();
    expect(bg(chip)).toEqual(cardTone);
    app.unmount();
  }, 60_000);

  test('an unknown state shows no word on either', async () => {
    const card = renderCard('TELEPORTED');
    expect(card.getByTestId('job-wo-1-state')).toHaveTextContent('');
    expect(card.queryByText('TELEPORTED')).toBeNull();
    card.unmount();

    const f = seedWO4822();
    scoped(f.db, DANA).run(`UPDATE work_order SET dispatch_state = 'TELEPORTED' WHERE technician_id = :technician_id AND id = :id`, { id: WO });
    const app = await mountJob(f.services, 'FF-15', { params: { workOrderId: WO }, openJob: WO });
    const top = within(onTop('FF-15'));
    expect(top.queryByTestId('job-state')).toBeNull();
    expect(top.queryByText('TELEPORTED')).toBeNull();
    app.unmount();
  }, 60_000);
});
