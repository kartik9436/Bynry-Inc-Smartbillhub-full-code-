/**
 * FB-030 (DEF-FLD-10806; PO 2026-10-31) — FF-35 on a PHONE: a Completed card
 * opens the job's record, with what the close said; *Earlier* holds days
 * 8–14; and the card is never a dead tap again.
 *
 * RED FIRST (law 7): at 7af7fbd1f the phone card's Pressable was `disabled`
 * off the tablet (it opened nothing), there was no *Earlier* segment, and the
 * close discarded its debrief and signer.
 */
import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as photoQ from '../../../src/db/queries/photo';
import * as closedQ from '../../../src/db/queries/workOrderClosed';
import { scoped } from '../../../src/db/scoped';
import { closeJob, defaultCloseTimes } from '../../../src/screens/closing/CloseScreen';
import { current, DANA, local, makeWave, MARCO, openScreen, waveOf } from '../onSite/fixture';

const onTop = (id: string) => screen.getAllByTestId(`screen-${id}`).at(-1)!;

describe('FB-030 · FF-35 opens the record on a phone', () => {
  test('tapping a card opens the record — header, outcome, the debrief and the signature', async () => {
    const w = makeWave();
    closeJob(
      waveOf(w),
      {
        workOrderId: 'wo-4822',
        debrief: { problem: 'Seized valve', done: 'Replaced the valve' },
        signature: { kind: 'signed', name: 'Sarah Miller', at: local(20, 9, 55) },
      },
      'passed',
      defaultCloseTimes(waveOf(w), 'wo-4822'),
    );
    const app = await openScreen(w, 'FF-35');
    fireEvent.press(within(app.onTop()).getByTestId('completed-WO-4822-pick'));
    expect(current(app.ref)).toEqual({ name: 'FF-35', params: { workOrderId: 'wo-4822' } });
    const record = within(onTop('FF-35'));
    expect(record.getByTestId('completed-record')).toBeTruthy();
    expect(record.getByText('WO-4822')).toBeTruthy();
    expect(record.getByText('Passed')).toBeTruthy();
    expect(record.getByTestId('completed-record-debrief')).toHaveTextContent(/Seized valve/);
    expect(record.getByTestId('completed-record-debrief')).toHaveTextContent(/Replaced the valve/);
    expect(record.getByTestId('completed-record-signature')).toHaveTextContent(/Signed by Sarah Miller/);
    // No money, no speed: the record names no minutes and no amount.
    expect(record.queryByText(/\d+h \d+m|\$/)).toBeNull();
  });

  test('a refusal reads as not signed, with its reason', async () => {
    const w = makeWave();
    closeJob(
      waveOf(w),
      { workOrderId: 'wo-4822', signature: { kind: 'refused', reason: 'Nobody home', at: local(20, 9, 55) } },
      'passed',
      defaultCloseTimes(waveOf(w), 'wo-4822'),
    );
    const app = await openScreen(w, 'FF-35', { workOrderId: 'wo-4822' });
    expect(within(app.onTop()).getByTestId('completed-record-signature')).toHaveTextContent(/Not signed: Nobody home/);
  });

  test('a photograph whose file has gone loads on tap, and with no signal says so', async () => {
    const w = makeWave();
    const s = scoped(w.db, DANA);
    closedQ.recordClose(s, 'wo-4822', 'passed', local(20, 9, 0));
    photoQ.insertRemote(s, { id: 'ph-gone', workOrderId: 'wo-4822', capturedAt: local(20, 8, 40), at: local(20, 9, 0) });
    const app = await openScreen(w, 'FF-35', { workOrderId: 'wo-4822' });
    const photo = within(app.onTop()).getByTestId('completed-record-photo-ph-gone');
    expect(within(photo).getByText('Tap to load')).toBeTruthy();
    fireEvent.press(photo);
    expect(within(app.onTop()).getByText('Needs signal')).toBeTruthy();
  });

  test('THE GUARD: every phone card opens something — never a dead tap (FB-030)', async () => {
    const w = makeWave();
    const s = scoped(w.db, DANA);
    for (const [id, d] of [['wo-4822', 20], ['wo-4824', 19], ['wo-4826', 18]] as const) closedQ.recordClose(s, id, 'passed', local(d, 9));
    const app = await openScreen(w, 'FF-35');
    fireEvent.press(within(app.onTop()).getByTestId('range-week'));
    const cards = within(app.onTop()).getAllByTestId(/^completed-WO-\d+-pick$/);
    expect(cards.length).toBe(3);
    for (const pick of cards) {
      expect(pick).not.toBeDisabled();
      expect(pick.props.accessibilityRole).toBe('button');
    }
    for (const number of ['4822', '4824', '4826']) {
      fireEvent.press(within(app.onTop()).getByTestId(`completed-WO-${number}-pick`));
      expect(current(app.ref)).toEqual({ name: 'FF-35', params: { workOrderId: `wo-${number}` } });
      expect(within(onTop('FF-35')).getByTestId('completed-record')).toBeTruthy();
      await act(async () => app.ref.goBack());
      expect(current(app.ref).params).toEqual({});
    }
  });
});

describe('FB-030 · FF-35 Earlier', () => {
  test('Today · This week · Earlier: day 10 is Earlier only, day 15 is nowhere', async () => {
    const w = makeWave();
    const s = scoped(w.db, DANA);
    closedQ.recordClose(s, 'wo-4822', 'passed', local(20, 9)); // today (NOW is 20 Oct)
    closedQ.recordClose(s, 'wo-4824', 'passed', local(17, 9)); // this week
    closedQ.recordClose(s, 'wo-4826', 'passed', local(10, 9)); // 10 days ago
    closedQ.recordClose(s, 'wo-4830', 'passed', local(5, 9)); // 15 days ago
    const app = await openScreen(w, 'FF-35');
    const shown = () => within(app.onTop()).queryAllByTestId(/^completed-WO-\d+$/).map((n) => n.props.testID);
    expect(shown()).toEqual(['completed-WO-4822']);
    fireEvent.press(within(app.onTop()).getByTestId('range-week'));
    expect(shown()).toEqual(['completed-WO-4822', 'completed-WO-4824']);
    fireEvent.press(within(app.onTop()).getByTestId('range-earlier'));
    expect(shown()).toEqual(['completed-WO-4826']);
    expect(within(app.onTop()).getByTestId('range-earlier')).toHaveTextContent('Earlier');
  });

  test('switch technician: another technician’s closed job is in nobody else’s Completed', async () => {
    const w = makeWave();
    closedQ.recordClose(scoped(w.db, DANA), 'wo-4822', 'passed', local(20, 9));
    const marco = makeWave({ tech: MARCO });
    const app = await openScreen({ ...marco, db: w.db } as typeof marco, 'FF-35');
    for (const range of ['range-today', 'range-week', 'range-earlier']) {
      fireEvent.press(within(app.onTop()).getByTestId(range));
      expect(within(app.onTop()).queryAllByTestId(/^completed-WO-\d+$/)).toEqual([]);
    }
  });
});
