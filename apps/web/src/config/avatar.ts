/**
 * Tino, the Actinver avatar. Single canonical identity record.
 * Media (LiveKit session, voice, look) is owned by the agent backend,
 * which serves it via /v1/avatar/session.
 */

export const actinverAvatar = {
  name: 'Tino',
  language: 'es',
  previewImageUrl: '/tino-icon.png',
} as const;

/** Actinver brand mark for splash and auth chrome. */
export const actinverLogoUrl =
  'https://s3.amazonaws.com/evaluar-test-media-bucket/COMPANY/image/08/COMPANY_da362390-74b5-4476-af0e-9a8fa69b3ee8_3915c6f2-cb47-41e8-b78c-84cb47f9b865.png';
