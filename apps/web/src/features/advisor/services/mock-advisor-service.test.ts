import { describe, expect, it } from 'vitest';
import type { UIComponent } from '@loopops/contracts';
import { createMockAdvisorService } from './mock-advisor-service';
import type { AdvisorStreamEvent } from './types';

async function collect(stream: AsyncIterable<AdvisorStreamEvent>): Promise<AdvisorStreamEvent[]> {
  const events: AdvisorStreamEvent[] = [];
  for await (const event of stream) {
    events.push(event);
  }
  return events;
}

function fullSpeech(events: AdvisorStreamEvent[]): string {
  return events
    .filter((event) => event.event === 'token')
    .map((event) => (event.event === 'token' ? event.data.text : ''))
    .join('');
}

function uiComponents(events: AdvisorStreamEvent[]): UIComponent[] {
  return events.flatMap((event) => (event.event === 'ui' ? [event.data] : []));
}

const service = createMockAdvisorService({ delayMs: 0 });

describe('createMockAdvisorService', () => {
  it('answers the portfolio intent with summary and attribution cards', async () => {
    const events = await collect(service.sendTurn('¿Cómo va mi portafolio?'));
    const types = uiComponents(events).map((component) => component.type);
    expect(types).toContain('portfolio_summary');
    expect(types).toContain('attribution_bars');
  });

  it('answers the attribution intent with bars only', async () => {
    const events = await collect(service.sendTurn('Dame la atribución del mes'));
    expect(uiComponents(events).map((component) => component.type)).toEqual(['attribution_bars']);
  });

  it('answers the quote intent with a market quote card', async () => {
    const events = await collect(service.sendTurn('¿A cuánto está el dólar?'));
    expect(uiComponents(events).map((component) => component.type)).toEqual(['market_quote']);
  });

  it('answers the news intent with citations', async () => {
    const events = await collect(service.sendTurn('¿Qué noticias hay del mercado?'));
    expect(uiComponents(events).map((component) => component.type)).toEqual(['citations']);
  });

  it('falls back to a warning banner for unknown intents', async () => {
    const events = await collect(service.sendTurn('compra acciones de tesla'));
    expect(uiComponents(events).map((component) => component.type)).toEqual(['warning_banner']);
  });

  it('matches intents without accents or casing (en included)', async () => {
    const events = await collect(service.sendTurn('PORTAFOLIO performance'));
    expect(uiComponents(events).map((component) => component.type)).toContain('portfolio_summary');
  });

  it('keeps exact figures out of the speech channel (split-channel invariant)', async () => {
    const questions = [
      '¿Cómo va mi portafolio?',
      '¿Qué noticias hay del mercado?',
      '¿A cuánto está el dólar?',
      'atribución por sleeve',
      'compra acciones de tesla',
    ];
    for (const question of questions) {
      const events = await collect(service.sendTurn(question));
      const speech = fullSpeech(events);
      expect(speech.trim().length, `speech empty for: ${question}`).toBeGreaterThan(0);
      for (const figure of ['4,187,203', '4187203', '0.87', '18.42', '118', '-52', '52', '8.00']) {
        expect(speech, `figure ${figure} leaked into speech`).not.toContain(figure);
      }
    }
  });

  it('streams tokens first, then ui cards, and always ends with done', async () => {
    const events = await collect(service.sendTurn('¿Cómo va mi portafolio?'));
    const names = events.map((event) => event.event);
    const lastToken = names.lastIndexOf('token');
    const firstUi = names.indexOf('ui');
    expect(names[0]).toBe('token');
    expect(names[names.length - 1]).toBe('done');
    expect(names.filter((name) => name === 'done')).toHaveLength(1);
    expect(firstUi).toBeGreaterThan(lastToken);
    const done = events[events.length - 1];
    expect(done).toEqual({
      event: 'done',
      data: {
        turn_id: expect.any(String),
        evidence_id: 'mock-evidence',
        service_type: 'no_asesorado',
      },
    });
  });

  it('exposes a greeting turn with speech and no cards', async () => {
    const greeting = service.sendGreeting;
    expect(greeting).toBeDefined();
    if (!greeting) return;
    const events = await collect(greeting());
    expect(fullSpeech(events)).toContain('Tino');
    expect(uiComponents(events)).toHaveLength(0);
  });
});
