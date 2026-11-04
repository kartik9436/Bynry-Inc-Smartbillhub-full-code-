import { fireEvent, screen } from '@testing-library/react-native';
import { TextInput } from 'react-native';

import { Field, FieldGroup } from '../../src/components';
import { renderIn, styleOf, themeOf } from './helpers';
import type { ReactTestInstance } from './helpers';

describe('Field', () => {
  test('label → input → help, in that order (B14 rule 39)', () => {
    renderIn(
      'light',
      <Field label="Why was it needed?" value="" help="The office reads this" testID="f" />,
    );
    const root = screen.getByTestId('f');
    const label = screen.getByText('Why was it needed?');
    const input = root.findByType(TextInput);
    const help = screen.getByText('The office reads this');
    const order = root.findAll(
      (n: ReactTestInstance) => n === label || n === input || n === help,
      { deep: true },
    );
    expect(order[0]).toBe(label);
    expect(order[order.length - 1]).toBe(help);
    expect(order.indexOf(input)).toBeGreaterThan(0);
  });

  test('anatomy: label → input 5, input → help 6', () => {
    renderIn('light', <Field label="What did you do?" value="" help="One line" />);
    expect(styleOf(screen.getByText('What did you do?')).marginBottom).toBe(5);
    expect(styleOf(screen.getByText('One line')).marginTop).toBe(6);
  });

  test('field → field 20 inside a FieldGroup', () => {
    renderIn(
      'light',
      <FieldGroup>
        <Field label="A" value="" />
        <Field label="B" value="" />
      </FieldGroup>,
    );
    const a = screen.getByText('A');
    // The spacer between the two fields is the only View carrying height 20.
    const spacers = screen.UNSAFE_root.findAll(
      (n: ReactTestInstance) => n.type === 'View' && styleOf(n).height === 20,
    );
    expect(spacers.length).toBe(1);
    expect(a).toBeTruthy();
  });

  test('the input is named by the label, at least 48 tall, and types', () => {
    const onChange = jest.fn();
    renderIn('light', <Field label="Closing read" value="" onChangeText={onChange} unit="gal" />);
    const input = screen.getByLabelText('Closing read');
    expect(Number(styleOf(input).minHeight)).toBeGreaterThanOrEqual(48);
    fireEvent.changeText(input, '1204');
    expect(onChange).toHaveBeenCalledWith('1204');
    expect(screen.getByText('gal')).toBeTruthy();
  });

  test('an error replaces the help, in the danger ink, and borders the input', () => {
    const t = themeOf('light');
    renderIn('light', <Field label="Reason" value="" help="Optional" error="Say why" />);
    expect(screen.queryByText('Optional')).toBeNull();
    expect(styleOf(screen.getByText('Say why')).color).toBe(t.colors.dangerAction);
    expect(styleOf(screen.getByLabelText('Reason')).borderColor).toBe(t.colors.status.danger.rule);
  });

  test('a warning tone colours the border and never disables the input (R11)', () => {
    const t = themeOf('light');
    renderIn('light', <Field label="Closing read" value="1,204" tone="warning" />);
    const input = screen.getByLabelText('Closing read');
    expect(styleOf(input).borderColor).toBe(t.colors.status.warning.rule);
    expect(input.props.editable).not.toBe(false);
  });
});
