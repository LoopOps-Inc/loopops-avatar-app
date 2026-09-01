/**
 * Actinver HeyGen avatar defaults.
 * Canonical source: AVATAR-ACTINVER.md
 */

export const actinverAvatar = {
  name: 'Actinver',
  heygenCatalogName: 'Ricky',
  groupId: '378cae579aef4c1189398b008dec0cd1',
  voiceId: 'd62a0ce960434056b25c058bc4fa2509',
  voiceName: 'Jorge - Professional',
  language: 'es',
  lookIds: {
    /** Default landscape look (suggested by Actinver / HeyGen team) */
    landscape: 'f00b90bab23243bc93a1484ebd63d8c9',
    /** Portrait look for mobile full-screen sessions */
    portrait: 'ec08a8bb0119489aa0019a090274c631',
  },
  previewImageUrl:
    'https://files2.heygen.ai/avatar/v3/6c421e25058b4dcf8e73e44de252fced/half/2.2/raw_preview_image.webp',
} as const;

/**
 * LiveAvatar sandbox defaults.
 * Sandbox mode: only the Wayne avatar is available and sessions last ~1 minute.
 * No voice_id: the Actinver voice lives in the HeyGen catalog, not in the
 * LiveAvatar space, and /v1/sessions/start rejects it with "Voice not found".
 * https://docs.liveavatar.com/docs/sandbox-mode
 */
export const liveAvatarSandbox = {
  avatarId: 'dd73ea75-1218-4ef3-92ce-606d5f7fbc0a',
  language: actinverAvatar.language,
} as const;

/** Look ID passed to HeyGen video / Live Avatar session APIs */
export function getAvatarLookId(orientation: 'landscape' | 'portrait' = 'portrait') {
  return actinverAvatar.lookIds[orientation];
}
