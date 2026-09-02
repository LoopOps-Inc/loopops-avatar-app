import { afterEach, describe, expect, it } from 'vitest';
import { clearDevAuth, setDevAuth } from '@/services/dev-auth';
import { buildAudioWsUrl } from './use-livekit-avatar-session';

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
