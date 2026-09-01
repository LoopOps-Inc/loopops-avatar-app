import type { UIComponent } from '@loopops/contracts';

export type MessageSender = 'user' | 'avatar';

export type ChatMessage = {
  sender: MessageSender;
  message: string;
  timestamp: number;
  /** Rich cards attached to an avatar turn (split-channel ui_payload). */
  uiComponents?: UIComponent[];
};

export type SessionEndReason = 'user' | 'server' | 'error';
