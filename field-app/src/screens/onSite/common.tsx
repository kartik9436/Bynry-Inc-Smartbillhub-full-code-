/**
 * What every screen of the on-site, closing and raise waves shares.
 *
 *   `waveScreen(id, Body)` — what the wave's group file registers. It wraps
 *     the screen:
 *       · in a `TelemetryErrorBoundary` — a render error is recorded,
 *         scrubbed, and the technician sees a sentence, not a white page;
 *       · in a `ThemeProvider` when the app root has not mounted one (it does
 *         not yet — reported), so a built screen never crashes on its theme;
 *       · in a view carrying `screen-<id>`, the address the doors test finds
 *         a screen by.
 *     When the data is not there — no database provided, or no job named — it
 *     says so and still offers the screen's DOORS (`navigation/doors.ts`),
 *     carrying the job along, so a screen is never a dead end and
 *     `tests/navigation/doors.test.tsx` can press every door of every built
 *     screen exactly as it pressed the placeholder's.
 *   `useHeader()` — the drawn title (WO-4824, W-4471) and a header chip.
 *   `useRefresh()` — a screen re-reads the handset after it captures.
 */
import { DrawerActions, useNavigation } from '@react-navigation/native';
import { type ComponentType, createContext, useCallback, useContext, useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Button, IconButton } from '../../components/Button';
import { EmptyState } from '../../components/EmptyState';
import { Glyph } from '../../components/Glyph';
import { StatusChip } from '../../components/StatusChip';
import { useHistoryBack } from '../../navigation/back';
import { DOORS } from '../../navigation/doors';
import { doorKind } from '../../navigation/routing';
import { type ScreenId, screenDef } from '../../navigation/screens';
import type { CrashCapture } from '../../telemetry/crashReporter';
import { TelemetryErrorBoundary } from '../../telemetry/TelemetryErrorBoundary';
import { ThemeProvider, useTheme } from '../../theme';
import { goTo, useNav, useParams, useWave, type Wave } from './fieldData';

export interface WaveScreenProps {
  w: Wave;
}

/** Recorded crashes go here once the app root hands its capture over. */
let crashCapture: CrashCapture | null = null;
export function setWaveCrashCapture(capture: CrashCapture | null): void {
  crashCapture = capture;
}

const NO_CAPTURE = {
  record: () => undefined,
  breadcrumb: () => undefined,
  sendPending: () => Promise.reject(new Error('no crash capture wired')),
  pending: () => [],
  droppedCount: () => 0,
  resetDropped: () => undefined,
} as CrashCapture;

const ScreenIdContext = createContext<ScreenId | null>(null);

/** The screen's own doors, as buttons: the way on when there is nothing to show. */
export function ScreenDoors(props: { id: ScreenId }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const params = useParams();
  const carry = typeof params.workOrderId === 'string' ? { workOrderId: params.workOrderId } : undefined;
  return (
    <View style={{ gap: theme.space[2], padding: theme.space[3] }}>
      {DOORS[props.id].map((to) => {
        const kind = doorKind(props.id, to);
        return (
          <Button
            key={to}
            size="sm"
            disabled={kind === 'signs-in' || kind === 'signs-out'}
            onPress={() => (kind === 'opens-menu' ? navigation.dispatch(DrawerActions.openDrawer()) : goTo(navigation, to, carry))}
            testID={`door-${to}`}
          >
            {t(screenDef(to).titleKey)}
          </Button>
        );
      })}
    </View>
  );
}

/** Nothing to show: say so, and offer the way on. */
export function NotOnPhone() {
  const { t } = useTranslation();
  const id = useContext(ScreenIdContext);
  return (
    <View testID="not-on-phone" style={{ flex: 1 }}>
      <EmptyState title={t('field.site.notOnPhone.title')} helper={t('field.site.notOnPhone.helper')} />
      {id ? <ScreenDoors id={id} /> : null}
    </View>
  );
}

function Failed() {
  const { t } = useTranslation();
  const id = useContext(ScreenIdContext);
  return (
    <View testID="screen-failed" style={{ flex: 1 }}>
      <EmptyState title={t('field.site.failed.title')} helper={t('field.site.failed.helper')} />
      {id ? <ScreenDoors id={id} /> : null}
    </View>
  );
}

/** True when a ThemeProvider is above. `useTheme` reads context first and
 *  only then throws, so the hook order is the same either way. */
function useHasTheme(): boolean {
  try {
    useTheme();
    return true;
  } catch {
    return false;
  }
}

export function waveScreen(id: ScreenId, Body: ComponentType<WaveScreenProps>): ComponentType {
  function Inner() {
    const w = useWave();
    const theme = useTheme();
    useBoardHeader(id);
    return (
      <View testID={`screen-${id}`} style={{ flex: 1, backgroundColor: theme.colors.page }}>
        <TelemetryErrorBoundary capture={crashCapture ?? NO_CAPTURE} screen={id} fallback={<Failed />}>
          {w ? <Body w={w} /> : <NotOnPhone />}
        </TelemetryErrorBoundary>
      </View>
    );
  }
  function Screen() {
    const themed = useHasTheme();
    return (
      <ScreenIdContext.Provider value={id}>
        {themed ? (
          <Inner />
        ) : (
          <ThemeProvider>
            <Inner />
          </ThemeProvider>
        )}
      </ScreenIdContext.Provider>
    );
  }
  Screen.displayName = `Screen(${id})`;
  return Screen;
}

/**
 * The header's left-hand control, as each board draws it: a back arrow, or the
 * menu on the two screens the boards draw as top-level pages (FF-35
 * Completed, FF-41 Asset search). Every back row names the board's own link
 * (`navigation/doors.ts`) — FF-27's arrow is drawn to Today, FF-40's to the
 * meter.
 *
 * BACK GOES WHERE YOU CAME FROM (DEF-FLD-10607; PO 2026-10-26, *"A for back
 * button"*): the arrow pops back through history, and the door named here is
 * followed only when there is no history (a notification or a cold link),
 * carrying the job (`workOrderId`) and the meter (`assetId`) so the screen it
 * opens is the same job's. One hook does it for every arrow in the app
 * (`navigation/back.tsx`), and the phone's own back does the same. ⚠ This
 * block read *"a back arrow that goes where the board's own link goes (not
 * merely 'back')"* until then, and called the stack's own back "not the drawn
 * door" — the judgment the PO's ruling superseded.
 */
export const BOARD_HEADER: Partial<Record<ScreenId, { back: ScreenId } | { menu: true }>> = {
  'FF-26': { back: 'FF-15' },
  'FF-27': { back: 'FF-10' },
  'FF-28': { back: 'FF-15' },
  'FF-30': { back: 'FF-15' },
  'FF-31': { back: 'FF-15' },
  'FF-32': { back: 'FF-17' },
  'FF-36': { back: 'FF-15' },
  'FF-38': { back: 'FF-15' },
  'FF-39': { back: 'FF-15' },
  'FF-40': { back: 'FF-39' },
  'FF-62': { back: 'FF-15' },
  'FF-35': { menu: true },
  'FF-41': { menu: true },
};

function useBoardHeader(id: ScreenId): void {
  const { t } = useTranslation();
  const navigation = useNav();
  const params = useParams();
  const door = BOARD_HEADER[id];
  const workOrderId = typeof params.workOrderId === 'string' ? params.workOrderId : undefined;
  const assetId = typeof params.assetId === 'string' ? params.assetId : undefined;
  const to = door && 'back' in door ? door.back : null;
  const { onBack, label } = useHistoryBack(
    to
      ? {
          label: t('field.site.back'),
          follow: () => {
            const carry: Record<string, unknown> = {};
            if (workOrderId) carry.workOrderId = workOrderId;
            if (assetId && to === 'FF-39') carry.assetId = assetId;
            goTo(navigation, to, Object.keys(carry).length ? carry : undefined);
          },
        }
      : null,
  );
  useLayoutEffect(() => {
    if (!door) return;
    if ('menu' in door) {
      navigation.setOptions({
        headerLeft: () => (
          <IconButton label={t('field.nav.menu')} onPress={() => navigation.dispatch(DrawerActions.openDrawer())} testID="door-FF-09">
            <Glyph name="drawer" />
          </IconButton>
        ),
      });
      return;
    }
    navigation.setOptions({
      headerBackVisible: false,
      headerLeft: () => (
        <IconButton label={label} onPress={onBack} testID={`door-${door.back}`}>
          <Glyph name="back" />
        </IconButton>
      ),
    });
  }, [navigation, door, t, onBack, label]);
}

/**
 * The drawn title when it is the job's or the meter's own (FF-27 *WO-4824*,
 * FF-39 *W-4471*), and a chip at the header's right (FF-25 *Contractor*).
 */
export function useHeader(opts: { title?: string | null; chip?: string | null }): void {
  const navigation = useNavigation();
  const { title, chip } = opts;
  useLayoutEffect(() => {
    navigation.setOptions({
      ...(title ? { title } : {}),
      ...(chip ? { headerRight: () => <StatusChip tone="neutral" testID="header-chip">{chip}</StatusChip> } : {}),
    });
  }, [navigation, title, chip]);
}

export function useRefresh(): [number, () => void] {
  const [tick, setTick] = useState(0);
  const bump = useCallback(() => setTick((n) => n + 1), []);
  return [tick, bump];
}
