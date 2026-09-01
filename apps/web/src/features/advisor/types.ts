import type { UIComponent } from '@loopops/contracts';
import type { SuggestionChip } from '@/mocks/schemas';

export type AdvisorMessageRole = 'user' | 'assistant';

export type AdvisorMessage = {
  id: string;
  role: AdvisorMessageRole;
  text: string;
  uiPayload: UIComponent[];
  chips?: SuggestionChip[];
  timestamp: number;
  streaming?: boolean;
};

export type AdvisorPhase = 'idle' | 'loading_session' | 'ready' | 'thinking' | 'error';
