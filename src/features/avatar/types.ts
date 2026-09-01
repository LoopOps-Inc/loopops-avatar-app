export type MessageSender = 'user' | 'avatar';

export type ChatMessage = {
  sender: MessageSender;
  message: string;
  timestamp: number;
};
