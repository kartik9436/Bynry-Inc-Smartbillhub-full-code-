/**
 * The meter and the work, on a tablet (T-29):
 *
 * FF-40 T *Asset history* (`tablet/FF-40-T-asset-history.png`)
 *   LIST   — the phone's History, whole: the meter, then one card per visit;
 *            a card's head picks the visit (the newest until one is).
 *   DETAIL — the visit: what it was, its date, then Who · Outcome · Problem
 *            · Done · Parts · On site, from the history cached with the meter
 *            (R116 — read whole, never queried across meters).
 *
 * FF-41 T *Asset search* (`tablet/FF-41-T-asset-search.png`)
 *   LIST   — the phone's Search, whole; a hit, which opens FF-39 on a phone,
 *            picks the meter here (`SelectOnOpen`), so box and hits stay put.
 *   DETAIL — the picked meter: its serial, model and size, then Badge ·
 *            Device ID · Where · Fitted · Last read, and *Scan one* (FF-38) ·
 *            *Open it* (FF-39). The board's *Account* line is not on the
 *            handset's meter row (`asset` holds no account) and is left out.
 *            Its warning that offline search covers only this tablet is the
 *            list's own line (FF-41's *only today's assets*), not repeated.
 *
 * FF-62 T *Pick a template* (`tablet/FF-62-T-pick-a-template.png`)
 *   LIST   — the phone's What work?, whole; choosing a template, which opens
 *            FF-37 on a phone, picks it here (`SelectOnOpen`).
 *   DETAIL — the template: its name and version, *What it carries* — Steps ·
 *            Safety checks · Readings — and *Use this template*, which opens
 *            FF-37 with it exactly as the phone's choice does. The board's
 *            Materials, Photographs and Estimated lines are not columns of the
 *            handset's template row (`work_order_templates`) and are left out.
 *
 * The boards' rationale paragraphs are not on screen (B14 rule 33).
 */
import { type TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';

import { Button, EmptyState, Kicker, StatusChip } from '../../components';
import { type Fact, FactLines } from '../../components/Facts';
import * as premiseQ from '../../db/queries/premise';
import * as searchQ from '../../db/queries/templateSearch';
import { plainName } from '../../db/queries/workOrderTemplates';
import { waveScreen } from '../../screens/onSite/common';
import { goTo, useNav, useParam, useParams, useWave } from '../../screens/onSite/fieldData';
import { addressLines, formatDate, formatFigure } from '../../screens/onSite/format';
import { AssetHistoryScreen, KNOWN, TONE } from '../../screens/raise/AssetHistoryScreen';
import { assetFor } from '../../screens/raise/AssetScreen';
import { AssetSearchScreen } from '../../screens/raise/AssetSearchScreen';
import { extraOf, lastRead, type Visit, visitsOf } from '../../screens/raise/history';
import { PickTemplateScreen } from '../../screens/raise/PickTemplateScreen';
import { raiseCarry } from '../../screens/raise/raiseRoute';
import { DetailCard, DetailNone, DetailPane } from '../DetailPane';
import { SelectOnOpen, useDefaultSelection, useSelectedOr } from '../selection';

// ── FF-40 Asset history ───────────────────────────────────────────────────

const History = waveScreen('FF-40', AssetHistoryScreen);

export function HistoryList() {
  return <History />;
}

function outcomeOf(t: TFunction, v: Visit): string | null {
  if (!v.outcome) return null;
  return KNOWN.includes(v.outcome) ? t(`field.site.outcome.${v.outcome}`) : v.outcome;
}

export function VisitDetail() {
  const { t } = useTranslation();
  const w = useWave();
  const assetId = useParam('assetId');
  const workOrderId = useParam('workOrderId');
  const asset = w ? assetFor(w, assetId, workOrderId) : null;
  const visits = asset ? visitsOf(asset.history) : [];
  useDefaultSelection(visits.length > 0 ? '0' : null);
  const picked = Number(useSelectedOr('visit') ?? '0');
  const v = visits[picked] ?? null;
  if (!v) return <DetailNone title={t('field.ff40.noVisits')} helper={t('field.tablet.pickHelp')} testID="visit-detail" />;
  const none = t('field.ff40.none');
  const outcome = outcomeOf(t, v);
  const facts: Fact[] = [
    { label: t('field.ff40.who'), value: v.who ?? none },
    { label: t('field.tablet.ff40.outcome'), value: outcome ?? none },
    { label: t('field.ff40.problem'), value: v.problem ?? none },
    { label: t('field.ff40.done'), value: [v.done, v.reading ? `${formatFigure(v.reading.value)} ${v.reading.unit}` : null].filter(Boolean).join(' · ') || none },
    { label: t('field.ff40.parts'), value: v.parts ?? none },
    { label: t('field.tablet.onSite'), value: v.minutes !== null ? t('field.ff40.minutes', { count: v.minutes }) : none },
  ];
  return (
    <DetailPane testID="visit-detail">
      <DetailCard
        title={v.work}
        line={formatDate(v.date)}
        trailing={v.outcome && outcome ? <StatusChip tone={TONE[v.outcome] ?? 'neutral'}>{outcome}</StatusChip> : undefined}
        facts={facts}
        testID="visit-detail-card"
      />
    </DetailPane>
  );
}

// ── FF-41 Asset search ────────────────────────────────────────────────────

const Search = waveScreen('FF-41', AssetSearchScreen);

export function SearchList() {
  return (
    <SelectOnOpen opens="FF-39" param="assetId">
      <Search />
    </SelectOnOpen>
  );
}

export function SearchDetail() {
  const { t } = useTranslation();
  const navigation = useNav();
  const w = useWave();
  const id = useSelectedOr('assetId');
  const asset = w && id ? assetFor(w, id, null) : null;
  const scan = (
    <Button grow onPress={() => goTo(navigation, 'FF-38')} testID="pane-FF-38">
      {t('field.tablet.ff41.scanOne')}
    </Button>
  );
  if (!w || !asset) {
    return (
      <DetailPane testID="search-detail" acts={scan}>
        <EmptyState title={t('field.tablet.pick')} helper={t('field.tablet.pickHelp')} />
      </DetailPane>
    );
  }
  const premise = asset.premise_id ? premiseQ.get(w.db, asset.premise_id) : undefined;
  const where = addressLines(premise);
  const { installedAt } = extraOf(asset.extra);
  const last = lastRead(visitsOf(asset.history));
  const facts: Fact[] = [];
  if (asset.badge) facts.push({ label: t('field.ff39.badge'), value: asset.badge });
  if (asset.device_id) facts.push({ label: t('field.ff39.deviceId'), value: asset.device_id });
  if (where.line1) facts.push({ label: t('field.ff39.where'), value: where.line1 });
  if (installedAt) facts.push({ label: t('field.tablet.ff41.fitted'), value: formatDate(installedAt) });
  if (last?.reading) {
    facts.push({ label: t('field.ff39.lastRead'), value: `${formatFigure(last.reading.value)} ${last.reading.unit} · ${formatDate(last.date)}` });
  }
  return (
    <DetailPane
      testID="search-detail"
      acts={
        <>
          {scan}
          <Button grow variant="primary" onPress={() => goTo(navigation, 'FF-39', { assetId: asset.id })} testID="pane-FF-39">
            {t('field.tablet.openIt')}
          </Button>
        </>
      }
    >
      <DetailCard
        title={asset.serial ?? asset.badge ?? t('field.screen.ff39')}
        line={[asset.model, asset.size].filter(Boolean).join(' · ')}
        facts={facts}
        testID="search-detail-card"
      />
    </DetailPane>
  );
}

// ── FF-62 Pick a template ─────────────────────────────────────────────────

const Templates = waveScreen('FF-62', PickTemplateScreen);

export function TemplatesList() {
  return (
    <SelectOnOpen opens="FF-37" param="templateId">
      <Templates />
    </SelectOnOpen>
  );
}

export function TemplateDetail() {
  const { t } = useTranslation();
  const navigation = useNav();
  const params = useParams();
  const w = useWave();
  const first = w ? (searchQ.searchPublished(w.db, '', { limit: 1 })[0] ?? null) : null;
  useDefaultSelection(first?.id ?? null);
  const id = useSelectedOr('templateId') ?? first?.id ?? null;
  const tpl = w && id ? searchQ.getPublished(w.db, id) : undefined;
  if (!w || !tpl) return <DetailNone title={t('field.ff62.none')} helper={t('field.tablet.pickHelp')} testID="template-detail" />;
  return (
    <DetailPane
      testID="template-detail"
      acts={
        <Button
          grow
          variant="primary"
          onPress={() =>
            goTo(navigation, 'FF-37', { ...raiseCarry(params), templateId: tpl.id })
          }
          testID="pane-FF-37"
        >
          {t('field.tablet.ff62.use')}
        </Button>
      }
    >
      <DetailCard
        title={tpl.name}
        line={[t('field.tpl.version', { version: tpl.version }), plainName(tpl.service)].filter(Boolean).join(' · ')}
        testID="template-detail-card"
      >
        <Kicker>{t('field.tablet.ff62.carries')}</Kicker>
        <FactLines
          split
          facts={[
            { label: t('field.tablet.steps'), value: String(tpl.step_count) },
            { label: t('field.tablet.ff62.safety'), value: String(tpl.safety_count) },
            { label: t('field.ff15.readings'), value: String(tpl.reading_count) },
          ]}
        />
      </DetailCard>
    </DetailPane>
  );
}
