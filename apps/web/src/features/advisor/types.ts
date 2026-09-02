import type { UIComponent } from '@loopops/contracts';

export type AdvisorMessageRole = 'user' | 'assistant';

export type AdvisorMessage = {
  id: string;
  role: AdvisorMessageRole;
  text: string;
  uiPayload: UIComponent[];
  timestamp: number;
  streaming?: boolean;
};

export type AdvisorPhase = 'idle' | 'loading_session' | 'ready' | 'thinking' | 'error';

export type VoiceActivity = 'idle' | 'listening' | 'thinking' | 'speaking';
