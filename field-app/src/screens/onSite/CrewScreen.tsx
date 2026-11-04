/**
 * FF-29 Crew — labour per person on one job (US-FLD-020, US-FLD-031; R8, R9).
 *
 * The header is the sum — *2h 24m labour on this job · 2 technicians* —
 * because two technicians are two time records and the cost is their sum.
 * One card per person: who, their grade and employment, LEAD on the lead,
 * Travel · Arrived · Labour. Anyone but the lead can be taken off (×) and
 * have their time corrected; *Add a technician* picks from the roster
 * (TC-3); the lead closes the job (R8).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button, IconButton } from '../../components/Button';
import { Card } from '../../components/Card';
import { FactLines } from '../../components/Facts';
import { Glyph } from '../../components/Glyph';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { ScreenFrame } from '../../components/ScreenFrame';
import { Sheet } from '../../components/Sheet';
import { StatusChip } from '../../components/StatusChip';
import * as crewOrderQ from '../../db/queries/crewTimeOrder';
import * as technicianQ from '../../db/queries/technician';
import { Pickable } from '../../tablet/Pickable';
import { usePick } from '../../tablet/selection';
import { useTheme } from '../../theme';
import { NotOnPhone, useRefresh, type WaveScreenProps } from './common';
import { CorrectTimeSheet } from './CorrectTimeSheet';
import { crewLines, type CrewLine, totalLabour } from './crew';
import { addTechnician, correctTime, removeTechnician } from './crewActions';
import { goTo, useNav, useJobId } from './fieldData';
import { formatClock, formatMinutes, initialsOf } from './format';
import { employmentWord, leadOf, loadJob, myName } from './job';

function Avatar(props: { name: string }) {
  const theme = useTheme();
  return (
    <View
      accessible={false}
      style={{
        width: theme.touch.control,
        height: theme.touch.control,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: theme.colors.surface,
        borderRadius: theme.radius.lg,
      }}
    >
      <AppText variant="body" weight="heavy" tone="muted">
        {initialsOf(props.name)}
      </AppText>
    </View>
  );
}

export function CrewScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const [, refresh] = useRefresh();
  const [correcting, setCorrecting] = useState<CrewLine | null>(null);
  const [adding, setAdding] = useState(false);
  const pick = usePick();
  const job = loadJob(w, useJobId());
  if (!job) return <NotOnPhone />;

  const now = w.clock.now();
  const workOrderId = job.order.id;
  const lead = leadOf(job);
  const lines = crewLines(crewOrderQ.listForOrder(w.s, workOrderId), now).sort((a, b) =>
    a.personId === lead ? -1 : b.personId === lead ? 1 : 0,
  );
  const total = totalLabour(lines);
  const nameOf = (id: string) => technicianQ.get(w.db, id)?.name?.trim() || (id === w.me ? myName(w) : '') || t('field.ff29.someone');
  // FB-023: a roster row the change feed made for this phone's own technician
  // has no name yet — never offer a blank card.
  const roster = technicianQ.list(w.db).filter((p) => p.name.trim() !== '' && !lines.some((l) => l.personId === p.id));
  const each = lines.length > 0 && lines.every((l) => l.labourMinutes === lines[0]?.labourMinutes);

  return (
    <ScreenFrame
      header={
        <View>
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: theme.space[2], flexWrap: 'wrap' }}>
            <AppText variant="title" testID="crew-total">
              {formatMinutes(total)}
            </AppText>
            <AppText variant="body" tone="muted">
              {t('field.ff29.labourOnJob')}
            </AppText>
          </View>
          <AppText variant="label" tone="muted" testID="crew-count">
            {each && lines[0]
              ? t('field.ff29.countEach', { count: lines.length, each: formatMinutes(lines[0].labourMinutes) })
              : t('field.ff29.count', { count: lines.length })}
          </AppText>
        </View>
      }
      footer={
        <Button variant="primary" grow onPress={() => goTo(navigation, 'FF-15', { workOrderId })} testID="door-FF-15">
          {t('field.ff29.done')}
        </Button>
      }
    >
      {lines.map((line) => {
        const person = technicianQ.get(w.db, line.personId);
        const isLead = line.personId === lead;
        const name = person?.name?.trim() || (line.personId === w.me ? myName(w) : '') || t('field.ff29.someone');
        // FF-29 T: beside the crew, a person's card picks them and the picked
        // one is ruled heavy; on the phone the lead's card is.
        const ruled = pick.active ? pick.isPicked(line.personId) : isLead;
        return (
          <Card key={line.personId} testID={`crew-${line.personId}`} style={ruled ? { borderColor: theme.colors.text, borderWidth: theme.borderWidth.emphasis } : undefined}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
              <Pickable id={line.personId} label={name} bare testID={`crew-${line.personId}-pick`}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3], flexShrink: 1 }}>
                  <Avatar name={name} />
                  <View style={{ flexShrink: 1 }}>
                    <AppText variant="section">{name}</AppText>
                    <AppText variant="label" tone="muted">
                      {[person?.role, person?.employment ? employmentWord(t, person.employment) : null].filter(Boolean).join(' · ')}
                    </AppText>
                  </View>
                </View>
              </Pickable>
              <View style={{ flex: 1 }} />
              {isLead ? (
                <StatusChip tone="neutral">{t('field.ff29.lead')}</StatusChip>
              ) : (
                <IconButton
                  outlined
                  label={t('field.ff29.remove', { name })}
                  onPress={() => {
                    removeTechnician(w, workOrderId, line.personId);
                    refresh();
                  }}
                  testID={`remove-${line.personId}`}
                >
                  <Glyph name="close" colour={theme.colors.dangerAction} />
                </IconButton>
              )}
            </View>
            <FactLines
              recessed
              split
              facts={[
                {
                  label: t('field.ff29.travel'),
                  value: line.travelMinutes === 0 && !isLead ? t('field.ff29.cameWithLead') : formatMinutes(line.travelMinutes),
                },
                { label: t('field.ff29.arrived'), value: line.arrivedAt ? formatClock(line.arrivedAt) : '—' },
                { label: t('field.ff29.labour'), value: formatMinutes(line.labourMinutes), tone: 'success', strong: true, testID: `labour-${line.personId}` },
              ]}
            />
            {!isLead ? (
              <Button size="sm" onPress={() => setCorrecting(line)} testID={`correct-${line.personId}`}>
                {t('field.ff29.correct')}
              </Button>
            ) : null}
          </Card>
        );
      })}

      <Button onPress={() => setAdding(true)} icon={<Glyph name="more" colour={theme.colors.textMuted} />} testID="add-technician">
        {t('field.ff29.add')}
      </Button>
      <Notice tone="info" icon={<Mark name="info" colour={theme.colors.status.info.fg} />}>
        {t('field.ff29.leadCloses')}
      </Notice>

      <CorrectTimeSheet
        visible={correcting !== null}
        name={correcting ? nameOf(correcting.personId) : ''}
        travel={correcting?.travelMinutes ?? 0}
        labour={correcting?.labourMinutes ?? 0}
        onCancel={() => setCorrecting(null)}
        onSave={(m) => {
          if (correcting) correctTime(w, workOrderId, correcting, m);
          setCorrecting(null);
          refresh();
        }}
      />

      <Sheet
        visible={adding}
        onClose={() => setAdding(false)}
        closeLabel={t('field.site.cancel')}
        title={t('field.ff29.add')}
        testID="add-sheet"
      >
        {roster.length === 0 ? (
          <AppText variant="body" tone="muted">
            {t('field.ff29.nobody')}
          </AppText>
        ) : (
          roster.map((p, i) => (
            <ListRow
              key={p.id}
              divider={i > 0}
              label={p.name}
              detail={[p.role, p.employment ? employmentWord(t, p.employment) : null].filter(Boolean).join(' · ')}
              onPress={() => {
                addTechnician(w, workOrderId, { id: p.id, name: p.name }, myName(w));
                setAdding(false);
                refresh();
              }}
              testID={`pick-${p.id}`}
            />
          ))
        )}
      </Sheet>
    </ScreenFrame>
  );
}
