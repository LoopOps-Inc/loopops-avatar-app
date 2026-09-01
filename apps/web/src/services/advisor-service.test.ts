import { describe, expect, it } from 'vitest';
import { parseSseStream } from './advisor-service';

function encodeSse(events: Array<{ event: string; data: string }>): ReadableStream<Uint8Array> {
  const text = events.map((e) => `event: ${e.event}\ndata: ${e.data}\n\n`).join('');
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
}

describe('parseSseStream', () => {
  it('parses token and done events', async () => {
    const stream = encodeSse([
      { event: 'token', data: '{"text":"Hola"}' },
      {
        event: 'done',
        data: '{"turn_id":"tn_1","evidence_id":"ev_1","service_type":"no_asesorado"}',
      },
    ]);

    const events = [];
    for await (const item of parseSseStream(stream)) {
      events.push(item);
    }

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ event: 'token', data: '{"text":"Hola"}' });
    expect(events[1]?.event).toBe('done');
  });
});
