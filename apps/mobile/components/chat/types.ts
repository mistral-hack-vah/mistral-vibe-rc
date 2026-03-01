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
  isStreaming?: boolean;
  timestamp?: number;
};

export type ToolCallMessage = {
  type: 'edit';
  filePath: string;
  diff: string;
  status?: 'pending' | 'approved' | 'denied';
};

export type ReadRequestMessage = {
  type: 'read_request';
  filePath: string;
  status?: 'pending' | 'approved' | 'denied';
};

export type ExecuteRequestMessage = {
  type: 'execute_request';
  command: string;
  status?: 'pending' | 'approved' | 'denied';
};

export type AgentNotification = {
  type: 'notification';
  content: string;
};

export type StatusMessage = {
  type: 'status';
  status: 'recording' | 'transcribing';
};

export type Message =
  | TextMessage
  | ToolCallMessage
  | ReadRequestMessage
  | ExecuteRequestMessage
  | AgentNotification
  | StatusMessage;
