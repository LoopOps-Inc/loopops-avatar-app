import { afterEach, describe, expect, it } from 'vitest';
import { clearDevAuth, setDevAuth } from '@/services/dev-auth';
import { buildAudioWsUrl, frameToComponent, parseUiFrame } from './use-livekit-avatar-session';

describe('buildAudioWsUrl', () => {
  afterEach(() => {
    clearDevAuth();
  });

  it('returns a same-origin ws URL for a relative API base', () => {
    expect(buildAudioWsUrl('/v1/avatar/as_1/audio', null)).toBe(
      'ws://localhost:3000/api/v1/avatar/as_1/audio',
    );
  });

  it('appends the minted access token as a query param', () => {
    setDevAuth({
      clientId: '200002',
      accessToken: 'tok_200002',
      expiresAt: Date.now() + 60_000,
    });
    expect(buildAudioWsUrl('/v1/avatar/as_1/audio')).toBe(
      'ws://localhost:3000/api/v1/avatar/as_1/audio?access_token=tok_200002',
    );
  });
});

describe('parseUiFrame', () => {
  // Captured from a live voice socket: the component travels INSIDE the frame
  // (ws_handler.py documents `{"type":"ui","component":{...UIComponent}}`).
  const frame = {
    type: 'ui',
    component: {
      type: 'cash_summary',
      payload: {
        as_of: '2026-09-02T12:57:44-06:00',
        available: { amount: '556600.00', currency: 'MXN' },
        pending: { amount: '75900.00', currency: 'MXN' },
        settlements: [],
      },
      as_of: '2026-09-02T12:57:44-06:00',
      source: 'tool:get_cash_balance',
    },
  };

  it('returns the component carried by the frame, not the envelope', () => {
    const component = parseUiFrame(frame);

    // Regression: the envelope itself parsed against the permissive variant of
    // UIComponentSchema, so every voice turn delivered `{type: "ui"}` and no
    // card ever rendered.
    expect(component?.type).toBe('cash_summary');
  });

  it('ignores a frame with no component', () => {
    expect(parseUiFrame({ type: 'ui' })).toBeNull();
  });

  it('ignores a component that fails its schema', () => {
    expect(parseUiFrame({ type: 'ui', component: 'nope' })).toBeNull();
  });
});

describe('frameToComponent', () => {
  // The pipeline nests only `ui`; citations, form_spec and error are spread
  // flat into the frame (voice/pipeline.py: `{"type": kind, **event.data}`).
  it('unwraps a ui frame', () => {
    const component = frameToComponent({
      type: 'ui',
      component: { type: 'cash_summary', payload: { as_of: '2026-09-02' } },
    });

    expect(component?.type).toBe('cash_summary');
  });

  it('turns a flat citations frame into its component', () => {
    const component = frameToComponent({
      type: 'citations',
      items: [{ title: 'Banxico mantiene la tasa', source: 'Banxico' }],
    });

    expect(component?.type).toBe('citations');
    expect(component?.payload).toEqual({
      items: [{ title: 'Banxico mantiene la tasa', source: 'Banxico' }],
    });
  });

  it('turns a flat form_spec frame into its component', () => {
    const component = frameToComponent({
      type: 'form_spec',
      form_id: 'frm_1',
      operation: 'BUY',
      product: { product_id: 'ACTIGOB-BF' },
      fields: [],
      expires_at: '2026-09-02T18:00:00Z',
    });

    expect(component?.type).toBe('form_spec');
    expect((component?.payload as { form_id: string }).form_id).toBe('frm_1');
  });

  it('shows an error frame instead of dropping it', () => {
    const component = frameToComponent({
      type: 'error',
      code: 'LOW_CONFIDENCE',
      message: 'No te escuché bien. ¿Me lo repites, por favor?',
      escalate: false,
    });

    expect(component?.type).toBe('warning_banner');
    expect(component?.payload).toEqual({
      severity: 'warning',
      message: 'No te escuché bien. ¿Me lo repites, por favor?',
    });
  });

  it('ignores a frame kind that carries no component', () => {
    expect(frameToComponent({ type: 'agent.speaking' })).toBeNull();
    expect(frameToComponent({ type: 'citations' })).toBeNull();
  });
});
