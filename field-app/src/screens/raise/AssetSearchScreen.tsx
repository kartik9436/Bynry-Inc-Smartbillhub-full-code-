/**
 * FF-41 Assets — find a meter by serial, badge, device ID or address, LOCAL
 * FIRST (R41), and say what the search cannot see (R42, US-FLD-039).
 *
 *   One query over the handset's search index (`searchIndex.search` — one
 *   FTS5 table, built from this technician's rows, so another technician's
 *   customers never surface). Asset hits only.
 *   The result area always says how many are ON THIS PHONE and that only
 *   today's assets are here: a silent subset is worse than a refusal (R42),
 *   because the technician concludes the meter does not exist.
 *   THEN THE SERVER (`GET work/mobile/assets/search`, N9 — released by lane
 *   INTEGRATE-2): with a signal, the same words are asked of every meter of
 *   the utility and what the phone does not hold is listed beneath, with its
 *   count. No button — the board draws none; the search simply reaches
 *   further when it can. Opening one keeps it on the phone (asset and its
 *   premises) so FF-39 opens it like any other. No signal: the phone's list
 *   stands under the board's own note, *"Only today's assets are here. A
 *   signal searches the whole utility."* (DEF-FLD-10604, MQ-046 — it read
 *   *"Server not reached. This phone only."* until then, which the board does
 *   not draw). What the phone holds is what the syncs index: today's job
 *   meters (`sync/delta.ts`) and the assigned routes' meters
 *   (`sync/routes.ts`) — never the whole utility's meters (PO 2026-10-26).
 *   A server hit is kept on the phone by `serverAsset.keepServerAsset`, the
 *   same way FF-38 Scan keeps one (FB-009, DEF-FLD-10634).
 *   This is the menu's *Assets* page.
 *   Paged: 50 at a time, *Show more* (NFR-3, no cap).
 *
 * The scan icon opens FF-38 — scanning is the first-class way in (R83).
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button, IconButton } from '../../components/Button';
import { Card } from '../../components/Card';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { ScreenFrame } from '../../components/ScreenFrame';
import { SearchField } from '../../components/SearchField';
import * as familyQ from '../../db/queries/assetFamily';
import type { WireAssetHit } from '../../sync/fieldApi';
import * as premiseQ from '../../db/queries/premise';
import * as searchQ from '../../db/queries/searchIndex';
import { useTheme } from '../../theme';
import { useTabletSelection } from '../../tablet/TabletFrame';
import type { WaveScreenProps } from '../onSite/common';
import { goTo, useNav } from '../onSite/fieldData';
import { addressLines } from '../onSite/format';
import { keepServerAsset } from './serverAsset';

export const PAGE = 50;

export function AssetSearchScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const [text, setText] = useState('');
  const [pages, setPages] = useState(1);
  // Beside the asset on a tablet (FF-39 T), the one on show is ruled heavy.
  const picked = useTabletSelection();

  const hits = text.trim()
    ? searchQ.search(w.s, text, { limit: PAGE * pages + 1 }).filter((h) => h.entity_kind === 'asset')
    : [];
  const more = hits.length > PAGE * pages;
  const assets = familyQ.getMany(
    w.db,
    hits.slice(0, PAGE * pages).map((h) => h.entity_id),
  );
  const order = new Map(hits.map((h, i) => [h.entity_id, i]));
  assets.sort((a, b) => (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0));

  // ── the server's half (N9), when this build has one ──
  const finder = w.assets ?? null;
  const query = text.trim();
  const [server, setServer] = useState<{ q: string; hits: WireAssetHit[]; count: number; hasMore: boolean; page: number } | { q: string; failed: true } | null>(null);
  const [serverPage, setServerPage] = useState(1);
  useEffect(() => {
    setServerPage(1);
  }, [query]);
  useEffect(() => {
    if (!finder || query.length < 2) {
      setServer(null);
      return;
    }
    let live = true;
    finder.search(query, serverPage).then(
      (r) =>
        live &&
        setServer((was) => {
          const kept = was && 'hits' in was && was.q === query && serverPage > 1 ? was.hits : [];
          return { q: query, hits: [...kept, ...r.hits], count: r.count, hasMore: r.hasMore, page: serverPage };
        }),
      () => live && setServer({ q: query, failed: true }),
    );
    return () => {
      live = false;
    };
  }, [finder, query, serverPage]);
  const onPhone = new Set(assets.map((a) => a.id));
  const serverHits = server && 'hits' in server && server.q === query ? server.hits.filter((h) => !onPhone.has(h.id)) : [];
  const serverFailed = !!server && 'failed' in server && server.q === query;

  const keepAndOpen = (h: WireAssetHit) => {
    keepServerAsset(w, h);
    goTo(navigation, 'FF-39', { assetId: h.id });
  };

  return (
    <ScreenFrame
      header={
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: theme.space[2] }}>
          <View style={{ flex: 1 }}>
            <SearchField
              label={t('field.ff41.search')}
              value={text}
              onChangeText={(v) => {
                setText(v);
                setPages(1);
              }}
              help={t('field.ff41.help')}
              testID="asset-search"
            />
          </View>
          <IconButton label={t('field.ff39.scan')} onPress={() => goTo(navigation, 'FF-38')} testID="door-FF-38">
            <Mark name="scan" />
          </IconButton>
        </View>
      }
    >
      {text.trim() ? (
        <AppText variant="label" tone="muted" testID="on-phone-count">
          {t('field.ff41.onPhone', { count: assets.length })}
        </AppText>
      ) : null}
      {assets.map((a) => {
        const premise = a.premise_id ? premiseQ.get(w.db, a.premise_id) : undefined;
        const kind = a.parent_asset_id ? t('field.ff41.subMeter') : [a.model, a.size].filter(Boolean).join(' · ');
        return (
          <Card
            key={a.id}
            style={picked.split && picked.selected === a.id ? { borderColor: theme.colors.text, borderWidth: theme.borderWidth.emphasis } : undefined}
          >
            <ListRow
              label={a.serial ?? a.badge ?? a.device_id ?? '—'}
              detail={[addressLines(premise).line1, kind].filter(Boolean).join('\n')}
              leading={<Mark name="document" colour={a.parent_asset_id ? theme.colors.textMuted : theme.colors.statusInk.info} />}
              onPress={() => goTo(navigation, 'FF-39', { assetId: a.id })}
              testID={`asset-${a.serial ?? a.id}`}
            />
          </Card>
        );
      })}
      {more ? (
        <Button size="sm" onPress={() => setPages((n) => n + 1)} testID="show-more">
          {t('field.site.showMore')}
        </Button>
      ) : null}
      {serverHits.length ? (
        <AppText variant="label" tone="muted" testID="on-server-count">
          {t('field.ff41.onServer', { count: serverHits.length })}
        </AppText>
      ) : null}
      {serverHits.map((h) => {
        const kind = h.sub_meter ? t('field.ff41.subMeter') : [h.model, h.size_class].filter(Boolean).join(' · ');
        return (
          <Card key={`server-${h.id}`}>
            <ListRow
              label={h.serial ?? h.asset_no ?? '—'}
              detail={[h.place?.premises?.address ?? null, kind].filter(Boolean).join('\n')}
              leading={<Mark name="document" colour={theme.colors.textMuted} />}
              onPress={() => keepAndOpen(h)}
              testID={`server-asset-${h.serial ?? h.asset_no ?? h.id}`}
            />
          </Card>
        );
      })}
      {server && 'hits' in server && server.q === query && server.hasMore ? (
        <Button size="sm" onPress={() => setServerPage((n) => n + 1)} testID="server-show-more">
          {t('field.site.showMore')}
        </Button>
      ) : null}
      {serverFailed || !finder || !query ? (
        <Notice tone="info" icon={<Mark name="info" colour={theme.colors.status.info.fg} />} testID="only-today">
          {`${t('field.ff41.onlyToday')}\n${t('field.ff41.signal')}`}
        </Notice>
      ) : null}
    </ScreenFrame>
  );
}
