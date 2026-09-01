import { describe, expect, it } from 'vitest';
import { resolveMockScenario } from './scenarios';
import { rodrigoFixture } from './fixtures/rodrigo';
import { UserSchema } from './schemas';

describe('mock fixtures', () => {
  it('parses rodrigo user', () => {
    expect(UserSchema.parse(rodrigoFixture.user).initials).toBe('DR');
  });

  it('storyboard explorar total matches fixture', () => {
    expect(rodrigoFixture.explorarSummary.marketValue.amount).toBe('948250.00');
  });
});

describe('resolveMockScenario', () => {
  it('returns portfolio response without figures in speech', () => {
    const result = resolveMockScenario('¿Cómo va mi portafolio?');
    expect(result.speech).not.toMatch(/948,?250/);
    expect(result.uiPayload.some((c) => c.type === 'portfolio_summary')).toBe(true);
  });

  it('returns chips for idle cash question', () => {
    const result = resolveMockScenario('Tengo tres millones parados');
    expect(result.chips?.length).toBeGreaterThan(0);
  });

  it('blocks structured note scenario', () => {
    const result = resolveMockScenario('Cuéntame de la nota estructurada');
    expect(result.speech).toMatch(/no es congruente/i);
    expect(result.uiPayload[0]?.type).toBe('warning_banner');
  });
});
