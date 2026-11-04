/**
 * FF-62 What work? — raising an order starts with a template, and every
 * published template is offered: recently used first, search behind it
 * (US-FLD-076; R112). Picking the template is picking the work.
 *
 *   YOU USED RECENTLY — the ones this handset has used, newest first; the
 *     first one drawn larger with *Used 2 days ago · Use it →*.
 *   ALL TEMPLATES · N — every published one, by name. Drafts never (TC-4).
 *   Search narrows both by name. Paged, *Show more* (NFR-3, no cap).
 *
 * Choosing opens FF-37 with the template and whatever the raise was carried
 * from. The board's closing paragraph is rationale and is not on screen
 * (B14 rule 33).
 *
 * ⚠ The catalogue's download (`07-endpoints.md` N8) is not on the branch;
 * until it is, this lists what the handset table holds (reported).
 */
import type { TFunction } from 'i18next';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ListRow } from '../../components/ListRow';
import { GroupLabel, ScreenFrame } from '../../components/ScreenFrame';
import { SearchField } from '../../components/SearchField';
import * as searchQ from '../../db/queries/templateSearch';
import { plainName, type TemplateRow } from '../../db/queries/workOrderTemplates';
import { useTheme } from '../../theme';
import type { WaveScreenProps } from '../onSite/common';
import { goTo, useNav, useParams } from '../onSite/fieldData';
import { raiseCarry } from './raiseRoute';

export const PAGE = 50;

/**
 * "Water · 4 steps · 3 safety checks · 1 reading", the counts that are not
 * zero. The service is shown only as plain text — never a stored object
 * (DEF-FLD-10613: `{id=…, code=water, name=Water}` on every card).
 */
export function countsLine(t: TFunction, tpl: TemplateRow): string {
  return [
    plainName(tpl.service),
    tpl.step_count ? t('field.tpl.steps', { count: tpl.step_count }) : null,
    tpl.safety_count ? t('field.tpl.safety', { count: tpl.safety_count }) : null,
    tpl.reading_count ? t('field.tpl.readings', { count: tpl.reading_count }) : null,
  ]
    .filter(Boolean)
    .join(' · ');
}

export function daysAgo(at: string, now: Date): number {
  const a = new Date(at);
  const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  return Math.max(0, Math.round((start(now) - start(a)) / 86400000));
}

export function PickTemplateScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const params = useParams();
  const [text, setText] = useState('');
  const [pages, setPages] = useState(1);

  const total = searchQ.countPublished(w.db);
  const rows = searchQ.searchPublished(w.db, text, { limit: PAGE * pages + 1 });
  const more = rows.length > PAGE * pages;
  const shown = rows.slice(0, PAGE * pages);
  const recent = shown.filter((r) => r.last_used_at !== null);
  const all = [...shown].sort((a, b) => a.name.localeCompare(b.name));
  const now = w.clock.now();

  const pick = (tpl: TemplateRow) =>
    // The raise's own params go on unchanged — the job, the place picked and
    // where to go back to (`raiseRoute.ts`, DEF-FLD-10603).
    goTo(navigation, 'FF-37', { ...raiseCarry(params), templateId: tpl.id });

  const version = (tpl: TemplateRow) => (
    <AppText variant="label" tone="muted">
      {t('field.tpl.version', { version: tpl.version })}
    </AppText>
  );

  return (
    <ScreenFrame
      header={
        <SearchField
          label={t('field.ff62.searchLabel')}
          placeholder={t('field.ff62.search', { count: total })}
          value={text}
          onChangeText={(v) => {
            setText(v);
            setPages(1);
          }}
          testID="template-search"
        />
      }
    >
      {recent.length > 0 ? <GroupLabel>{t('field.ff62.recent')}</GroupLabel> : null}
      {recent.map((tpl, i) =>
        i === 0 ? (
          <Card key={tpl.id} testID={`recent-${tpl.id}`} style={{ borderColor: theme.colors.text, borderWidth: theme.borderWidth.emphasis }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.space[2] }}>
              <AppText variant="section">{tpl.name}</AppText>
              {version(tpl)}
            </View>
            <AppText variant="label" tone="muted">
              {countsLine(t, tpl)}
            </AppText>
            <ListRow
              divider
              label={t('field.ff62.usedAgo', { count: daysAgo(tpl.last_used_at ?? '', now) })}
              value={t('field.ff62.useIt')}
              onPress={() => pick(tpl)}
              testID={`use-${tpl.id}`}
            />
          </Card>
        ) : (
          <Card key={tpl.id}>
            <ListRow label={tpl.name} detail={countsLine(t, tpl)} value={version(tpl)} onPress={() => pick(tpl)} testID={`use-${tpl.id}`} />
          </Card>
        ),
      )}
      <GroupLabel>{t('field.ff62.all', { count: total })}</GroupLabel>
      {all.map((tpl) => (
        <Card key={tpl.id}>
          <ListRow label={tpl.name} detail={countsLine(t, tpl)} value={version(tpl)} onPress={() => pick(tpl)} testID={`tpl-${tpl.id}`} />
        </Card>
      ))}
      {shown.length === 0 ? (
        <AppText variant="body" tone="muted" testID="no-templates">
          {t('field.ff62.none')}
        </AppText>
      ) : null}
      {more ? (
        <Button size="sm" onPress={() => setPages((n) => n + 1)} testID="show-more">
          {t('field.site.showMore')}
        </Button>
      ) : null}
    </ScreenFrame>
  );
}
