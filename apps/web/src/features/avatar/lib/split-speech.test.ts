import { describe, expect, it } from 'vitest';
import { createSpeechSplitter } from './split-speech';

describe('createSpeechSplitter', () => {
  it('emits a finished sentence when the token already ends with a period', () => {
    const splitter = createSpeechSplitter();
    expect(splitter.feed('Hola, soy Tino.')).toEqual(['Hola, soy Tino.']);
    expect(splitter.flush()).toBeNull();
  });

  it('holds fragments until the sentence completes', () => {
    const splitter = createSpeechSplitter();
    expect(splitter.feed('Tu portafolio ')).toEqual([]);
    expect(splitter.feed('va bien.')).toEqual(['Tu portafolio va bien.']);
    expect(splitter.flush()).toBeNull();
  });

  it('emits each sentence as it closes so TTS can start early', () => {
    const splitter = createSpeechSplitter();
    expect(splitter.feed('Primera frase. ')).toEqual(['Primera frase.']);
    expect(splitter.feed('Segunda frase.')).toEqual(['Segunda frase.']);
    expect(splitter.flush()).toBeNull();
  });

  it('flushes a remainder without terminal punctuation', () => {
    const splitter = createSpeechSplitter();
    expect(splitter.feed('respuesta')).toEqual([]);
    expect(splitter.flush()).toBe('respuesta');
  });
});
