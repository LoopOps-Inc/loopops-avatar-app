import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import { setLocale } from '@/i18n';
import { Composer } from './Composer';

describe('Composer', () => {
  beforeEach(() => {
    setLocale('es');
  });

  it('sends the trimmed message and clears the input', () => {
    const onSend = vi.fn();
    const { getByLabelText } = render(<Composer onSend={onSend} />);
    const input = getByLabelText('Mensaje para el avatar') as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: '  hola  ' } });
    fireEvent.submit(input.closest('form')!);
    expect(onSend).toHaveBeenCalledWith('hola');
    expect(input.value).toBe('');
  });

  it('keeps focus on the input after tapping send (keyboard stays open)', () => {
    const onSend = vi.fn();
    const { getByLabelText, getByRole } = render(<Composer onSend={onSend} />);
    const input = getByLabelText('Mensaje para el avatar');
    input.focus();
    fireEvent.change(input, { target: { value: 'hola' } });
    input.blur();
    fireEvent.click(getByRole('button', { name: 'Enviar' }));
    expect(onSend).toHaveBeenCalledWith('hola');
    expect(input).toHaveFocus();
  });

  it('does not send empty messages', () => {
    const onSend = vi.fn();
    const { getByLabelText } = render(<Composer onSend={onSend} />);
    const input = getByLabelText('Mensaje para el avatar');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.submit(input.closest('form')!);
    expect(onSend).not.toHaveBeenCalled();
  });
});
