/**
 * A remark: spoken by default, typed as the fallback, never required (R95).
 * Used by RW-09 *Remark* and RW-21 *Say what you saw*.
 *
 * When the handset has no dictation (no speech library is installed today —
 * see `ports.ts`), the sheet opens straight on the typed box rather than
 * showing a microphone that does nothing.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Field, Sheet } from '../../components';
import { useReads } from './services';

export function RemarkSheet(props: {
  visible: boolean;
  initial: string | null;
  onClose: () => void;
  onSave: (text: string | null, source: 'voice' | 'typed' | null) => void;
}) {
  const { t, i18n } = useTranslation();
  const { services } = useReads();
  const [text, setText] = useState(props.initial ?? '');
  const [source, setSource] = useState<'voice' | 'typed' | null>(null);
  useEffect(() => {
    if (props.visible) setText(props.initial ?? '');
  }, [props.visible, props.initial]);
  const speak = async () => {
    try {
      const heard = await services.dictation.listen(i18n.language);
      if (heard) {
        setText(heard);
        setSource('voice');
      }
    } catch {
      setSource('typed');
    }
  };
  return (
    <Sheet
      visible={props.visible}
      onClose={props.onClose}
      title={t('field.reads.remark.title')}
      closeLabel={t('field.reads.common.close')}
      testID="remark-sheet"
      footer={
        <>
          <Button grow onPress={props.onClose} testID="remark-cancel">
            {t('field.reads.common.cancel')}
          </Button>
          <Button
            variant="primary"
            grow
            testID="remark-save"
            onPress={() => {
              const clean = text.trim();
              props.onSave(clean || null, clean ? (source ?? 'typed') : null);
            }}
          >
            {t('field.reads.remark.keep')}
          </Button>
        </>
      }
    >
      {services.dictation.available ? (
        <Button onPress={() => void speak()} testID="remark-speak">
          {t('field.reads.remark.speak')}
        </Button>
      ) : null}
      <Field
        label={t('field.reads.remark.label')}
        value={text}
        multiline
        onChangeText={(v) => {
          setText(v);
          setSource('typed');
        }}
        testID="remark-input"
      />
    </Sheet>
  );
}
