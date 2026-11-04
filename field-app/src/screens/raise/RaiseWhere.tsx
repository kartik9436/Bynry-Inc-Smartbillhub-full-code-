/**
 * FF-37's *Where* card — the place a raise stands on when there is no job to
 * carry it from: raised from Home, Scan or an asset (DEF-FLD-10603, MQ-036).
 *
 * The drawing (`wireframes/phone/FF-37-raise.png`) shows only the from-a-job
 * case, *Carried from WO-4801*. A raise with no job has no anchor of its own,
 * and the server refuses an order that stands on nothing (`BR-WRK-006`), so
 * before this card a raise from Home was captured, sent and refused, with
 * nothing on screen to say so.
 *
 *   PICKED — drawn as the carried card is: the premises' address (hard rule
 *     8 — the address lives there and nowhere else), the account and the
 *     meter, the phone's position now (`BR-MET-1202`), and *Change →*.
 *   NOT YET — one search box over address, account or meter: the phone's own
 *     places first (`db/queries/placeSearch.ts`, R41), then, with a signal,
 *     every meter of the utility (`GET work/mobile/assets/search`, N9 — the
 *     same door FF-41 asks, which searches address and account number too).
 *     A server hit is kept on the phone (its premises and meter) exactly as
 *     FF-41 keeps one it opens, so the picked card reads it from the store.
 *
 * A component (B14 rule 43): FF-37 mounts it, and nothing here knows about
 * Send — the screen keeps Send waiting until a place is picked.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DotLine } from '../../components/DotLine';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { SearchField } from '../../components/SearchField';
import * as assetQ from '../../db/queries/asset';
import * as placeQ from '../../db/queries/placeSearch';
import type { PlaceAnchors } from '../../db/queries/placeSearch';
import * as premiseQ from '../../db/queries/premise';
import type { WireAssetHit } from '../../sync/fieldApi';
import type { CaptureLocation } from '../../sync/outbox';
import { useTheme } from '../../theme';
import type { Wave } from '../onSite/fieldData';
import { addressLines } from '../onSite/format';

export const WHERE_PAGE = 20;

/** The phone's position line, as the carried card draws it. */
export function PositionLine({ location }: { location: CaptureLocation | null }) {
  const { t } = useTranslation();
  return location ? (
    <DotLine tone="success" mark="pin" testID="raise-fix">
      {t('field.ff37.fix', { lat: location.lat.toFixed(4), lng: location.lng.toFixed(4), m: Math.round(location.accuracy_m) })}
    </DotLine>
  ) : (
    <DotLine tone="warning" mark="pin">
      {t('field.ff37.noFix')}
    </DotLine>
  );
}

export function RaiseWhere(props: {
  w: Wave;
  place: PlaceAnchors | null;
  location: CaptureLocation | null;
  onPick: (place: PlaceAnchors | null) => void;
}) {
  const { w, place, location, onPick } = props;
  const { t } = useTranslation();
  const theme = useTheme();

  if (place) {
    const premise = place.premiseId ? premiseQ.get(w.db, place.premiseId) : undefined;
    const asset = place.assetId ? assetQ.get(w.db, place.assetId) : undefined;
    const account = place.accountId ? placeQ.accountNumberOf(w.s, place.accountId) : null;
    const where = addressLines(premise);
    return (
      <Card
        title={t('field.ff37.where')}
        testID="where-card"
        style={{ borderColor: theme.colors.text, borderWidth: theme.borderWidth.emphasis }}
      >
        <View>
          <AppText variant="section" testID="where-address">
            {where.line1}
          </AppText>
          <AppText variant="body">{where.line2}</AppText>
        </View>
        <AppText variant="label" tone="muted" testID="where-ids">
          {[account, asset?.serial ?? asset?.badge ?? asset?.device_id].filter(Boolean).join(' · ')}
        </AppText>
        <PositionLine location={location} />
        <ListRow divider label={t('field.ff37.where')} value={t('field.ff37.change')} onPress={() => onPick(null)} testID="where-change" />
      </Card>
    );
  }
  return <WhereSearch w={w} onPick={onPick} />;
}

function WhereSearch({ w, onPick }: { w: Wave; onPick: (place: PlaceAnchors) => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [text, setText] = useState('');
  const [pages, setPages] = useState(1);
  const query = text.trim();
  const hits = placeQ.searchPlaces(w.s, query, { limit: WHERE_PAGE * pages + 1 });
  const more = hits.length > WHERE_PAGE * pages;
  const shown = hits.slice(0, WHERE_PAGE * pages);

  // ── the server's half (N9), when this build has one ──
  const finder = w.assets ?? null;
  const [server, setServer] = useState<{ q: string; hits: WireAssetHit[] } | { q: string; failed: true } | null>(null);
  useEffect(() => {
    if (!finder || query.length < 2) {
      setServer(null);
      return;
    }
    let live = true;
    finder.search(query, 1).then(
      (r) => live && setServer({ q: query, hits: r.hits }),
      () => live && setServer({ q: query, failed: true }),
    );
    return () => {
      live = false;
    };
  }, [finder, query]);
  const onPhone = new Set(shown.map((h) => h.assetId).filter(Boolean));
  const serverHits =
    server && 'hits' in server && server.q === query ? server.hits.filter((h) => !onPhone.has(h.id) && h.place?.premises?.id) : [];
  const serverFailed = !!server && 'failed' in server && server.q === query;

  const keepAndPick = (h: WireAssetHit) => {
    const at = w.clock.now().toISOString();
    const premise = h.place?.premises ?? null;
    w.db.transaction(() => {
      if (premise?.id) premiseQ.upsert(w.db, { id: premise.id, premiseNo: premise.premise_no ?? null, addressLine: premise.address ?? null }, at);
      assetQ.upsert(
        w.db,
        { id: h.id, serial: h.serial, deviceId: h.asset_no, model: h.model, size: h.size_class, premiseId: premise?.id ?? null, status: 'active' },
        at,
      );
    });
    onPick({ premiseId: premise?.id ?? null, accountId: null, assetId: h.id });
  };

  return (
    <Card title={t('field.ff37.where')} tone="warning" testID="where-card">
      <SearchField
        label={t('field.ff37.whereSearch')}
        value={text}
        onChangeText={(v) => {
          setText(v);
          setPages(1);
        }}
        help={t('field.ff41.help')}
        testID="where-search"
      />
      {query.length >= 2 ? (
        <AppText variant="label" tone="muted" testID="where-on-phone">
          {t('field.ff41.onPhone', { count: shown.length })}
        </AppText>
      ) : null}
      {shown.map((h, i) => (
        <ListRow
          key={h.key}
          divider={i > 0}
          label={h.address ?? h.serial ?? h.accountNumber ?? '—'}
          detail={[h.locality, h.accountNumber, h.serial].filter(Boolean).join(' · ') || undefined}
          leading={<Mark name={h.kind === 'asset' ? 'document' : 'pin'} colour={theme.colors.statusInk.info} />}
          onPress={() => onPick({ premiseId: h.premiseId, accountId: h.accountId, assetId: h.assetId })}
          testID={`where-${h.key}`}
        />
      ))}
      {more ? (
        <Button size="sm" onPress={() => setPages((n) => n + 1)} testID="where-show-more">
          {t('field.site.showMore')}
        </Button>
      ) : null}
      {serverHits.length ? (
        <AppText variant="label" tone="muted" testID="where-on-server">
          {t('field.ff41.onServer', { count: serverHits.length })}
        </AppText>
      ) : null}
      {serverHits.map((h, i) => (
        <ListRow
          key={`server-${h.id}`}
          divider={i > 0}
          label={h.place?.premises?.address ?? h.serial ?? h.asset_no ?? '—'}
          detail={[h.serial ?? h.asset_no, h.place?.unit_label].filter(Boolean).join(' · ') || undefined}
          leading={<Mark name="document" colour={theme.colors.textMuted} />}
          onPress={() => keepAndPick(h)}
          testID={`where-server-${h.serial ?? h.asset_no ?? h.id}`}
        />
      ))}
      {serverFailed ? (
        <Notice tone="warning" testID="where-server-not-reached">
          {t('field.ff41.phoneOnly')}
        </Notice>
      ) : null}
    </Card>
  );
}
