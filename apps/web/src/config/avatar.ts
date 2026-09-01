/**
 * Tino, the Actinver avatar. Single canonical identity record.
 * Media (LiveKit session, voice, look) is owned by the agent backend,
 * which serves it via /v1/avatar/session.
 */

export const actinverAvatar = {
  name: 'Tino',
  language: 'es',
} as const;
