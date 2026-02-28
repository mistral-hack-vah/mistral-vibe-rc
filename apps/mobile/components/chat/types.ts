export type Attachment = {
  uri: string;
  type: 'image' | 'file';
  name: string;
  width?: number;
  height?: number;
};

export type TextMessage = {
  type: 'text';
  role: 'user' | 'assistant';
  content: string;
  attachments?: Attachment[];
};

export type ToolCallMessage = {
  type: 'tool_call';
  name: string;
  args: string;
  result?: string;
};

export type AgentNotification = {
  type: 'notification';
  content: string;
};

export type Message = TextMessage | ToolCallMessage | AgentNotification;
