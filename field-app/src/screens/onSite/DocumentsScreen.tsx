/**
 * FF-28 Documents — the SOPs, guides and notes that ride with the job, and
 * the ones always on the phone; every one opens from the phone's own copy,
 * so the screen works offline (requirement: "SOPs ride with the job").
 *
 *   FOR THIS JOB — the order's own papers, its asset's and its template's
 *     (`document.owner_kind`), then the premise notes the job carries
 *     (`work_order.access_notes`).
 *   ALWAYS ON THE PHONE — the tenant's papers (`owner_kind = 'tenant'`).
 *   The footer counts what is on the phone, its size, and when it last
 *   changed.
 *
 * Opening goes through `DocumentOpener`: the phone's own copy is handed to
 * the operating system's *Open with…* (FB-031, PO ruling B, 2026-10-31). A
 * phone with no app for the file says *No app can open this.* A paper whose
 * file is not on the phone says so and does not pretend to open.
 *
 * THE JOB'S HELP (DEF-FLD-10581, MQ-011) rides in the same rows, by `kind`:
 *   document — opens the phone's own copy, fetched at sync. Until then it
 *              says it downloads at next sync — ONLY while there is a fetch
 *              to make (`url`); a row the server holds no file for says
 *              *No file attached.* (FB-031, DEF-FLD-10805).
 *   phone    — dials the number (`tel:`); a row with no number says so.
 *   link     — opens its https address in the browser; with no signal it
 *              says it needs one (the shell's connection state).
 *   note     — its words, nothing to open.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking } from 'react-native';

import { NoAppError } from '../../device';
import { AppText } from '../../components/AppText';
import { Card } from '../../components/Card';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { GroupLabel, ScreenFrame } from '../../components/ScreenFrame';
import { Notice } from '../../components/Notice';
import { useShellStatus } from '../../navigation/ShellStatus';
import { type DocumentRow, distinctHelp } from '../../db/queries/document';
import * as shelfQ from '../../db/queries/documentShelf';
import { Pickable } from '../../tablet/Pickable';
import { usePick } from '../../tablet/selection';
import { useTheme } from '../../theme';
import { NotOnPhone, useRefresh, type WaveScreenProps } from './common';
import { useJobId, type Wave } from './fieldData';
import { formatClock } from './format';
import { loadJob, showsOf } from './job';

/** "22 MB" — whole megabytes, at least 1 when anything is there. */
export function megabytes(bytes: number): number {
  return bytes <= 0 ? 0 : Math.max(1, Math.round(bytes / (1024 * 1024)));
}

/** Why a row did not open — each a `field.ff28.*` line. */
export type NotOpened = 'notOnPhone' | 'cannotOpen' | 'nextSync' | 'needsSignal' | 'noFile' | 'noNumber' | 'noApp';

/** A help row that dials or browses rather than opening a file. */
export function opensOutside(d: Pick<DocumentRow, 'kind'>): boolean {
  return d.kind === 'phone' || d.kind === 'link';
}

/** Where a row goes outside the app: `tel:` for a number, its https address for a link. */
function outsideTarget(d: Pick<DocumentRow, 'kind' | 'ref'>): string | null {
  const ref = d.ref ?? '';
  if (d.kind === 'phone') {
    const digits = ref.replace(/[^\d+]/g, '');
    return digits ? `tel:${digits}` : null;
  }
  return d.kind === 'link' && /^https:\/\//i.test(ref) ? ref : null;
}

/** Why a row cannot open, known before trying — the line shows at once. */
export function cannotOpenNow(d: DocumentRow, online: boolean): NotOpened | null {
  if (opensOutside(d)) {
    if (!outsideTarget(d)) return d.kind === 'phone' ? 'noNumber' : 'cannotOpen';
    return d.kind === 'link' && !online ? 'needsSignal' : null;
  }
  if (!d.local_path) return isServerDocument(d) ? (d.url ? 'nextSync' : 'noFile') : 'notOnPhone';
  return null;
}

function isServerDocument(d: Pick<DocumentRow, 'source' | 'kind'>): boolean {
  return d.source === 'server' && d.kind === 'document';
}

/** A file's type from its name, for the phone's own app (FB-031). */
export function contentTypeOf(path: string): string | undefined {
  const ext = /\.([A-Za-z0-9]{1,8})$/.exec(path)?.[1]?.toLowerCase();
  return ext === 'pdf' ? 'application/pdf' : ext === 'png' ? 'image/png' : ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg' : undefined;
}

/**
 * Open a paper from the phone's own copy — the row on a phone, *Open it* on
 * a tablet (FF-28 T) — or dial a help number, or browse a help link.
 * Resolves null once it opened, else which line says why.
 */
export async function openPaper(
  w: Wave,
  d: DocumentRow,
  opts: { online?: boolean; openUrl?: (url: string) => Promise<unknown> } = {},
): Promise<NotOpened | null> {
  const why = cannotOpenNow(d, opts.online !== false);
  if (why) return why;
  const target = outsideTarget(d);
  if (target) {
    const openUrl = opts.openUrl ?? ((url: string) => Linking.openURL(url));
    try {
      await openUrl(target);
      return null;
    } catch {
      return 'cannotOpen';
    }
  }
  shelfQ.markUsed(w.db, d.id, w.clock.now().toISOString());
  try {
    await w.device.documents.open(d.local_path!, contentTypeOf(d.local_path!));
    return null;
  } catch (err) {
    return err instanceof NoAppError ? 'noApp' : 'cannotOpen';
  }
}

export function DocumentsScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [note, setNote] = useState<string | null>(null);
  const [, refresh] = useRefresh();
  const online = useShellStatus().connection !== 'offline';
  // FF-28 T: beside the paper, a row picks it and the paper opens from there.
  const pick = usePick();
  const job = loadJob(w, useJobId());
  if (!job) return <NotOnPhone />;

  const mine = distinctHelp(
    shelfQ.forJob(w.db, {
      workOrderId: job.order.id,
      assetId: job.order.asset_id,
      templateId: job.order.template_id,
    }),
  );
  // FB-023 F6 — the template's *Access notes & hazards* tick (the job's copy).
  const accessNotes = showsOf(job).accessNotes ? job.order.access_notes : null;
  const always = shelfQ.alwaysOnPhone(w.db);
  const totals = shelfQ.shelfTotals(w.db);

  const open = (d: DocumentRow) => {
    const now = cannotOpenNow(d, online);
    if (now) {
      setNote(t(`field.ff28.${now}`));
      return;
    }
    setNote(null);
    void openPaper(w, d, { online }).then((why) => (why ? setNote(t(`field.ff28.${why}`)) : refresh()));
  };

  const detail = (d: DocumentRow): string => {
    if (d.kind === 'phone') return outsideTarget(d) ? (d.ref ?? '') : t('field.ff28.noNumber');
    if (d.kind === 'note') return d.ref ?? '';
    if (d.kind === 'link') return t('field.ff28.inBrowser');
    if (d.kind === 'document') {
      if (d.local_path) return t('field.ff28.onPhone');
      return d.source === 'server' && !d.url ? t('field.ff28.noFile') : t('field.ff28.nextSync');
    }
    return [d.kind?.toUpperCase(), d.local_path ? t('field.ff28.onPhone') : t('field.ff28.notOnPhone')].filter(Boolean).join(' · ');
  };

  const mark = (d: DocumentRow) =>
    d.kind === 'phone' ? (
      <Mark name="call" colour={theme.colors.statusInk.info} />
    ) : d.kind === 'link' ? (
      <Mark name="link" colour={theme.colors.statusInk.info} />
    ) : (
      <Mark name="document" colour={d.kind === 'note' ? theme.colors.textMuted : theme.colors.statusInk.info} />
    );

  return (
    <ScreenFrame>
      {note ? (
        <Notice tone="warning" testID="open-note">
          {note}
        </Notice>
      ) : null}
      <GroupLabel>{t('field.ff28.forJob')}</GroupLabel>
      <Card testID="job-docs">
        {mine.map((d, i) => (
          <Pickable key={d.id} id={d.id} label={d.title} testID={`doc-${d.id}-pick`}>
            <ListRow
              divider={i > 0}
              label={d.title}
              detail={detail(d) || undefined}
              leading={mark(d)}
              onPress={pick.active || d.kind === 'note' ? undefined : () => open(d)}
              testID={`doc-${d.id}`}
            />
          </Pickable>
        ))}
        {accessNotes ? (
          <ListRow
            divider={mine.length > 0}
            label={t('field.ff28.premiseNotes')}
            detail={accessNotes}
            leading={<Mark name="document" colour={theme.colors.textMuted} />}
            testID="premise-notes"
          />
        ) : null}
        {mine.length === 0 && !accessNotes ? (
          <AppText variant="body" tone="muted">
            {t('field.ff28.none')}
          </AppText>
        ) : null}
      </Card>

      <GroupLabel>{t('field.ff28.always')}</GroupLabel>
      <Card testID="always-docs">
        {always.map((d, i) => (
          <Pickable key={d.id} id={d.id} label={d.title} testID={`doc-${d.id}-pick`}>
            <ListRow divider={i > 0} label={d.title} onPress={pick.active ? undefined : () => open(d)} testID={`doc-${d.id}`} />
          </Pickable>
        ))}
        {always.length === 0 ? (
          <AppText variant="body" tone="muted">
            {t('field.ff28.none')}
          </AppText>
        ) : null}
      </Card>

      <AppText variant="label" tone="muted" testID="shelf-totals">
        {t('field.ff28.totals', {
          count: totals.count,
          mb: megabytes(totals.bytes),
          time: totals.updatedAt ? formatClock(totals.updatedAt) : '—',
        })}
      </AppText>
    </ScreenFrame>
  );
}
