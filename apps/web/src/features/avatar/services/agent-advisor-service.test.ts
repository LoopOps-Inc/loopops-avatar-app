import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { SseDoneEvent, SseTokenEvent, UIComponent } from '@loopops/contracts';
import { sendAdvisorMessage } from '@/services/advisor-service';
import { createAgentAdvisorService } from './agent-advisor-service';
import type { AdvisorStreamEvent } from './types';

vi.mock('@/services/advisor-service', () => ({
  sendAdvisorMessage: vi.fn(),
}));

const token = (text: string): { event: 'token'; data: SseTokenEvent } => ({
  event: 'token',
  data: { text },
});

describe('createAgentAdvisorService', () => {
  beforeEach(() => {
    vi.mocked(sendAdvisorMessage).mockReset();
  });

  it('streams sendAdvisorMessage events in order', async () => {
    vi.mocked(sendAdvisorMessage).mockImplementation(async (_threadId, _request, handlers) => {
      handlers.onToken('Hola');
      handlers.onToken(', todo bien');
      handlers.onUi({ type: 'citations', payload: { items: [] } } as UIComponent);
      handlers.onCitations({ items: [{ title: 'F', url: 'https://f' }] });
      handlers.onDone({
        turn_id: 't1',
        evidence_id: 'e1',
        service_type: 'advisory',
      } as SseDoneEvent);
    });

    const service = createAgentAdvisorService('thread-1');
    const events: AdvisorStreamEvent[] = [];
    for await (const event of service.sendTurn('¿Cómo va mi portafolio?')) {
      events.push(event);
    }

    expect(events.map((event) => event.event)).toEqual([
      'token',
      'token',
      'ui',
      'citations',
      'done',
    ]);
    expect(events[0]).toEqual(token('Hola'));
    expect(events[1]).toEqual(token(', todo bien'));
    expect(vi.mocked(sendAdvisorMessage).mock.calls[0][0]).toBe('thread-1');
    expect(vi.mocked(sendAdvisorMessage).mock.calls[0][1].text).toBe('¿Cómo va mi portafolio?');
    expect(vi.mocked(sendAdvisorMessage).mock.calls[0][1].client_turn_id).toBeTruthy();
  });

  it('propagates transport failures to the consumer', async () => {
    vi.mocked(sendAdvisorMessage).mockRejectedValue(new Error('HTTP_503'));
    const service = createAgentAdvisorService('thread-1');
    const events: AdvisorStreamEvent[] = [];
    const consume = async () => {
      for await (const event of service.sendTurn('hola')) {
        events.push(event);
      }
    };
    await expect(consume()).rejects.toThrow('HTTP_503');
    expect(events).toHaveLength(0);
  });

  it('greets with a single static localized message', async () => {
    const service = createAgentAdvisorService('thread-1');
    const events: AdvisorStreamEvent[] = [];
    for await (const event of service.sendGreeting!()) {
      events.push(event);
    }
    expect(events).toHaveLength(1);
    const [first] = events;
    expect(first?.event).toBe('token');
    if (first?.event === 'token') {
      expect(first.data.text.length).toBeGreaterThan(0);
    }
  });
});
