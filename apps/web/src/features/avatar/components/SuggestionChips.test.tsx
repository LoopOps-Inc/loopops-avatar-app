import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { setLocale } from '@/i18n';
import { SuggestionChips } from './SuggestionChips';

describe('SuggestionChips', () => {
  beforeEach(() => {
    setLocale('es');
  });

  it('renders the three suggestion chips from i18n', () => {
    render(<SuggestionChips onSend={vi.fn()} />);
    expect(
      screen.getByRole('button', { name: 'ETFs de deuda de bajo riesgo' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '¿Cómo empiezo a invertir?' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Revisar mi portafolio' })).toBeInTheDocument();
  });

  it('sends the chip text through the provided handler once on click', () => {
    const onSend = vi.fn();
    render(<SuggestionChips onSend={onSend} />);
    fireEvent.click(screen.getByRole('button', { name: 'Revisar mi portafolio' }));
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith('Revisar mi portafolio');
  });

  it('does not send when disabled', () => {
    const onSend = vi.fn();
    render(<SuggestionChips onSend={onSend} disabled />);
    fireEvent.click(screen.getByRole('button', { name: 'Revisar mi portafolio' }));
    expect(onSend).not.toHaveBeenCalled();
  });
});
