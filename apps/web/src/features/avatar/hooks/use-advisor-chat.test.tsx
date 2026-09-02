import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAdvisorChat } from './use-advisor-chat';
import type { AdvisorService, AdvisorStreamEvent } from '../services/types';

function fakeService(
  turns: Record<string, AdvisorStreamEvent[]>,
  greeting?: AdvisorStreamEvent[],
): AdvisorService {
  return {
    sendTurn: async function* (message: string) {
      yield* turns[message] ?? [];
    },
    sendGreeting: greeting
      ? async function* () {
          yield* greeting;
        }
      : undefined,
  };
}

function renderAdvisor(
  service: AdvisorService,
  overrides: Partial<Parameters<typeof useAdvisorChat>[0]> = {},
) {
  const speak = vi.fn();
  const view = renderHook(
    ({ enabled }: { enabled: boolean }) =>
      useAdvisorChat({ speak, enabled, service, ...overrides }),
    { initialProps: { enabled: false } },
  );
  return { speak, ...view };
}

describe('useAdvisorChat', () => {
  it('streams a turn: user bubble, avatar bubble, ui payload, citations mapping, speak on done', async () => {
    const service = fakeService({
      '¿Cómo va mi portafolio?': [
        { event: 'token', data: { text: 'Tu portafolio ' } },
        { event: 'token', data: { text: 'va bien.' } },
        {
          event: 'ui',
          data: {
            type: 'portfolio_summary',
            payload: {
              as_of: '2026-08-31',
              market_value: 4187203,
              currency: 'MXN',
              period_return: 0.031,
              contributions: 15000,
            },
          },
        },
        { event: 'citations', data: { items: [{ title: 'Fuentes', url: 'https://x' }] } },
        {
          event: 'done',
          data: { turn_id: 't1', evidence_id: 'e1', service_type: 'advisory' },
        },
      ],
    });
    const { result, speak } = renderAdvisor(service, { greet: false });
    act(() => result.current.send('¿Cómo va mi portafolio?'));

    await vi.waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    const [user, avatar] = result.current.messages;
    expect(user).toMatchObject({ sender: 'user', message: '¿Cómo va mi portafolio?' });
    expect(avatar?.sender).toBe('avatar');
    expect(avatar?.message).toBe('Tu portafolio va bien.');
    expect(avatar?.uiComponents?.map((component) => component.type)).toEqual([
      'portfolio_summary',
      'citations',
    ]);
    expect(avatar?.uiComponents?.[1]).toEqual({
      type: 'citations',
      payload: { items: [{ title: 'Fuentes', url: 'https://x' }] },
    });

    await vi.waitFor(() => {
      expect(speak).toHaveBeenCalledTimes(1);
    });
    expect(speak.mock.calls[0][0]).toBe('Tu portafolio va bien.');
    expect(result.current.isThinking).toBe(false);
  });

  it('renders a fallback bubble when the turn stream fails', async () => {
    const service: AdvisorService = {
      sendTurn: async function* () {
        yield { event: 'error', data: { code: 'ADVISOR_DOWN', message: 'down' } };
      },
    };
    const { result } = renderAdvisor(service, { greet: false });
    act(() => result.current.send('hola'));

    await vi.waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    expect(result.current.messages[1]?.sender).toBe('avatar');
    expect(result.current.messages[1]?.message).toContain('ADVISOR_DOWN');
  });

  it('greets once when the session becomes enabled', async () => {
    const service = fakeService(
      {},
      [{ event: 'token', data: { text: 'Hola, soy Tino.' } }],
    );
    const { result, speak, rerender } = renderAdvisor(service, { greet: true });
    rerender({ enabled: true });
    await vi.waitFor(() => {
      expect(result.current.messages).toHaveLength(1);
    });
    expect(result.current.messages[0]?.sender).toBe('avatar');
    expect(result.current.messages[0]?.message).toBe('Hola, soy Tino.');
    await vi.waitFor(() => {
      expect(speak).toHaveBeenCalledTimes(1);
    });
    rerender({ enabled: false });
    rerender({ enabled: true });
    expect(result.current.messages).toHaveLength(1);
  });

  it('ignores sends while a turn is in flight', async () => {
    let release: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const service: AdvisorService = {
      sendTurn: async function* () {
        await gate;
        yield { event: 'token', data: { text: 'respuesta' } };
      },
    };
    const { result } = renderAdvisor(service, { greet: false });
    act(() => {
      result.current.send('primera');
      result.current.send('segunda');
    });
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.message).toBe('primera');
    await vi.waitFor(() => {
      expect(result.current.isThinking).toBe(true);
    });
    release?.();
    await vi.waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    expect(result.current.messages.map((message) => message.sender)).toEqual(['user', 'avatar']);
  });

  it('appends voice turns: user transcript, replacing captions, attached ui', async () => {
    const service = fakeService({});
    const { result } = renderAdvisor(service, { greet: false });

    act(() => result.current.appendUserMessage('¿Qué opinas del mercado?'));
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      sender: 'user',
      message: '¿Qué opinas del mercado?',
    });

    act(() => result.current.appendCaption('El mercado'));
    act(() => result.current.appendCaption('El mercado va estable.'));
    await vi.waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    expect(result.current.messages[1]).toMatchObject({
      sender: 'avatar',
      message: 'El mercado va estable.',
    });

    act(() =>
      result.current.appendUi({
        type: 'citations',
        payload: { items: [{ title: 'Fuentes', url: 'https://x' }] },
      }),
    );
    await vi.waitFor(() => {
      expect(result.current.messages[1]?.uiComponents).toHaveLength(1);
    });

    act(() => result.current.endVoiceTurn());
    act(() => result.current.appendCaption('Nueva respuesta.'));
    await vi.waitFor(() => {
      expect(result.current.messages).toHaveLength(3);
    });
    expect(result.current.messages[1]?.message).toBe('El mercado va estable.');
    expect(result.current.messages[2]?.message).toBe('Nueva respuesta.');
  });
});
