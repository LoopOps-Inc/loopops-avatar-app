import { describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useAdvisorChat } from './use-advisor-chat';
import { createMockAdvisorService } from '../services/mock-advisor-service';

const service = createMockAdvisorService({ delayMs: 0 });

function renderAdvisor(overrides: Partial<Parameters<typeof useAdvisorChat>[0]> = {}) {
  const speak = vi.fn();
  const view = renderHook(
    ({ enabled }: { enabled: boolean }) =>
      useAdvisorChat({ speak, enabled, service, ...overrides }),
    { initialProps: { enabled: false } },
  );
  return { speak, ...view };
}

describe('useAdvisorChat', () => {
  it('streams a turn: user bubble, avatar bubble, speak on done', async () => {
    const { result, speak } = renderAdvisor({ greet: false });
    act(() => result.current.send('¿Cómo va mi portafolio?'));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    const [user, avatar] = result.current.messages;
    expect(user).toMatchObject({ sender: 'user', message: '¿Cómo va mi portafolio?' });
    expect(avatar?.sender).toBe('avatar');
    expect(avatar?.message).toContain('Tu portafolio');
    expect(avatar?.uiComponents?.map((component) => component.type)).toEqual([
      'portfolio_summary',
      'attribution_bars',
    ]);

    await waitFor(() => {
      expect(speak).toHaveBeenCalledTimes(1);
    });
    expect(speak.mock.calls[0][0]).toContain('Tu portafolio');
    expect(speak.mock.calls[0][0]).not.toContain('4,187,203');
    expect(result.current.isThinking).toBe(false);
  });

  it('greets once when the session becomes enabled', async () => {
    const { result, speak, rerender } = renderAdvisor({ greet: true });
    rerender({ enabled: true });
    await waitFor(() => {
      expect(result.current.messages).toHaveLength(1);
    });
    expect(result.current.messages[0]?.sender).toBe('avatar');
    await waitFor(() => {
      expect(speak).toHaveBeenCalledTimes(1);
    });
    expect(speak.mock.calls[0][0]).toContain('Tino');
    rerender({ enabled: false });
    rerender({ enabled: true });
    expect(result.current.messages).toHaveLength(1);
  });

  it('ignores sends while a turn is in flight', async () => {
    const { result } = renderAdvisor({ greet: false });
    act(() => {
      result.current.send('¿Cómo va mi portafolio?');
      result.current.send('otra pregunta');
    });
    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    expect(result.current.messages.map((message) => message.sender)).toEqual(['user', 'avatar']);
  });
});
