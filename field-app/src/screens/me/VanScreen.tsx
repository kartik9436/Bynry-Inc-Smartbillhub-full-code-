/**
 * FF-49 Van (T-24; image `phone/FF-49-van.png`).
 *
 * What is on the truck, READ, never counted: the design's *Scope · Out* list
 * excludes van stock-takes (EP-FLD-08 Out: *"van stock-takes"*), so the
 * drawing's *Count the van* button is not built. Parts needed today and short
 * come first, in red, with *Ask the depot*; then everything on the truck with
 * how many. The scan button opens FF-38.
 *
 * A part's unit price is shown as the server sends it, up to four places
 * (CLAUDE.md hard rule 2: a unit price is the one exception to "display 2"),
 * and never calculated with — money is read only here (R16).
 *
 * The stock is a server door that does not exist yet (`ME-van-stock`).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, EmptyState, Glyph, IconButton, Kicker, Notice } from '../../components';
import { Pickable } from '../../tablet/Pickable';
import { useTheme } from '../../theme';
import { formatClock } from './format';
import { useActiveTechnician, useHandsetPrefs, usePortRead } from './hooks';
import { MeScreen, useDoor } from './MeScreen';
import { type VanItem, useMeServices } from './services';

const SYMBOL: Record<string, string> = { USD: '$', CAD: '$' };

/** `"92.4000"` USD → `$92.4000`, `"0.1"` → `$0.10`: a unit price by STRING — never through a float. */
export function unitPriceText(amount: string, currency: string): string {
  const m = /^(-?)(\d+)(?:\.(\d*))?$/.exec(amount.trim());
  if (!m) return amount;
  // As many places as it carries, at least two and at most four (`$0.0425`, `$8.9375`, `$0.10`).
  const places = (m[3] ?? '').padEnd(2, '0').slice(0, 4);
  const symbol = SYMBOL[currency] ?? `${currency} `;
  return `${m[1]}${symbol}${m[2]}.${places}`;
}

function ItemRow({ item, short }: { item: VanItem; short: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${item.name}, ${item.sku}, ${t('field.ff49.onHand', { count: item.onHand })}`}
      testID={`ff49-item-${item.sku}`}
      style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3], minHeight: theme.touch.control }}
    >
      <View style={{ flexGrow: 1, flexShrink: 1 }}>
        <AppText variant="body" weight="heavy">
          {item.name}
        </AppText>
        <AppText variant="label" tone="muted">
          {item.unitPrice && short
            ? `${item.sku} · ${t('field.ff49.each', { price: unitPriceText(item.unitPrice.amount, item.unitPrice.currency) })}`
            : item.sku}
        </AppText>
      </View>
      <View style={{ alignItems: 'flex-end' }}>
        <AppText variant="title" tone={short ? 'danger' : 'default'} testID={`ff49-count-${item.sku}`}>
          {String(item.onHand)}
        </AppText>
        {short && item.neededToday != null ? (
          <AppText variant="label" tone="muted">
            {t('field.ff49.need', { count: item.neededToday })}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

export function VanScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const door = useDoor('FF-49');
  const tech = useActiveTechnician();
  const [prefs] = useHandsetPrefs();
  const [notice, setNotice] = useState<string | null>(null);
  const [loaded] = usePortRead(
    () => (tech ? services.van.stock(tech.technicianId) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  const stock = loaded.state === 'ready' ? loaded.value : null;
  const short = (stock?.items ?? []).filter((i) => i.neededToday != null && i.neededToday > i.onHand);
  const rest = (stock?.items ?? []).filter((i) => !short.includes(i));

  async function ask(sku: string) {
    if (!tech) return;
    setNotice(null);
    try {
      await services.van.askDepot(tech.technicianId, sku);
      setNotice(t('field.ff49.asked'));
    } catch {
      setNotice(t('field.me.notSent'));
    }
  }

  return (
    <MeScreen
      id="FF-49"
      title={t('field.screen.ff49')}
      leading="drawer"
      trailing={
        <IconButton label={t('field.ff49.scan')} onPress={() => door('FF-38')} testID="door-FF-38">
          <Glyph name="scan" />
        </IconButton>
      }
    >
      {notice ? <Notice tone="info">{notice}</Notice> : null}
      {stock ? (
        <>
          <View>
            <AppText variant="body" weight="heavy" testID="ff49-van">
              {stock.van}
            </AppText>
            {stock.countedAt ? (
              <AppText variant="label" tone="muted">
                {t('field.ff49.countedAt', { time: formatClock(stock.countedAt, prefs.clock) })}
              </AppText>
            ) : null}
          </View>
          {short.length > 0 ? (
            <Card tone="danger" title={t('field.ff49.neededToday')} testID="ff49-needed">
              {short.map((item) => (
                <View key={item.sku} style={{ gap: theme.space[3] }}>
                  {/* FF-49 T: beside the part, a part picks it. */}
                  <Pickable id={item.sku} label={item.name} testID={`ff49-item-${item.sku}-pick`}>
                    <ItemRow item={item} short />
                  </Pickable>
                  <Button size="sm" variant="danger" onPress={() => ask(item.sku)} testID={`ff49-ask-${item.sku}`}>
                    {t('field.ff49.askDepot')}
                  </Button>
                </View>
              ))}
            </Card>
          ) : null}
          <Kicker>{t('field.ff49.onTruck')}</Kicker>
          {rest.map((item) => (
            <Pickable key={item.sku} id={item.sku} label={item.name} testID={`ff49-item-${item.sku}-pick`}>
              <Card>
                <ItemRow item={item} short={false} />
              </Card>
            </Pickable>
          ))}
        </>
      ) : loaded.state === 'loading' ? null : (
        <EmptyState title={t('field.me.notHereYet')} helper={t('field.ff49.emptyHelper')} testID="ff49-not-wired" />
      )}
    </MeScreen>
  );
}
