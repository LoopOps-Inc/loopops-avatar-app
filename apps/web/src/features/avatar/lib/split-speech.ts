/** Incremental splitter for avatar TTS. Mirrors the agent SentenceSplitter:
 * emit a speakable sentence as soon as punctuation (or a 220-char soft limit)
 * lands, so Gemini TTS can start before the rest of the SSE turn arrives.
 */

const ABBREV =
  /\b(?:Sr|Sra|Srta|Lic|Ing|Dr|Dra|Av|No|Núm|S\.A|S\.A\.B|C\.V|aprox|etc|p\.ej|EE\.UU)\.$/i;
const BOUNDARY = /(?<=[.!?…:;])\s+/;
const SOFT_LIMIT = 220;

function isFalseBoundary(candidate: string): boolean {
  if (ABBREV.test(candidate)) return true;
  return /\d\.$/.test(candidate);
}

function isTerminalSentence(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) return false;
  if (!/[.!?…]$/.test(trimmed)) return false;
  return !isFalseBoundary(trimmed);
}

export function createSpeechSplitter() {
  let buffer = '';

  return {
    feed(token: string): string[] {
      buffer += token;
      const out: string[] = [];
      let searchFrom = 0;
      while (true) {
        const match = BOUNDARY.exec(buffer.slice(searchFrom));
        if (!match || match.index === undefined) break;
        const absEnd = searchFrom + match.index;
        const candidate = buffer.slice(0, absEnd).trim();
        if (isFalseBoundary(candidate)) {
          searchFrom = absEnd + match[0].length;
          continue;
        }
        buffer = buffer.slice(absEnd + match[0].length);
        searchFrom = 0;
        if (candidate) out.push(candidate);
      }
      if (buffer.length > SOFT_LIMIT) {
        const cut = buffer.lastIndexOf(' ', SOFT_LIMIT);
        if (cut > 0) {
          out.push(buffer.slice(0, cut).trim());
          buffer = buffer.slice(cut).trimStart();
        }
      }
      if (isTerminalSentence(buffer)) {
        out.push(buffer.trim());
        buffer = '';
      }
      return out;
    },
    flush(): string | null {
      const remainder = buffer.trim();
      buffer = '';
      return remainder || null;
    },
  };
}
