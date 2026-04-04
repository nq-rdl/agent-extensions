/**
 * TypeScript interfaces for pi-rpc ConnectRPC responses.
 * These match the JSON shapes returned by the pirpc.v1.SessionService.
 */

export type SessionState =
  | "SESSION_STATE_UNSPECIFIED"
  | "SESSION_STATE_CREATING"
  | "SESSION_STATE_IDLE"
  | "SESSION_STATE_RUNNING"
  | "SESSION_STATE_ERROR"
  | "SESSION_STATE_TERMINATED";

export type MessageRole =
  | "MESSAGE_ROLE_UNSPECIFIED"
  | "MESSAGE_ROLE_USER"
  | "MESSAGE_ROLE_ASSISTANT"
  | "MESSAGE_ROLE_TOOL_RESULT";

export interface Message {
  role: MessageRole;
  content: string;
  isError?: boolean;
  toolCallId?: string;
  timestampMs?: number;
}

export interface SessionSummary {
  id: string;
  state: SessionState;
  provider: string;
  model: string;
  createdAt?: string;
}

export interface CreateResponse {
  sessionId: string;
  state: SessionState;
}

export interface PromptResponse {
  state: SessionState;
  messages?: Message[];
}

export interface PromptAsyncResponse {}

export interface GetMessagesResponse {
  messages: Message[];
}

export interface GetStateResponse {
  sessionId: string;
  state: SessionState;
  provider: string;
  model: string;
  cwd: string;
  pid: number;
  createdAt?: string;
  lastActivity?: string;
  errorMessage?: string;
}

export interface AbortResponse {
  state: SessionState;
}

export interface DeleteResponse {}

export interface ListResponse {
  sessions: SessionSummary[];
}
