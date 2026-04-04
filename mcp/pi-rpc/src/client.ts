/**
 * HTTP client for the pi-rpc ConnectRPC service.
 *
 * Calls pirpc.v1.SessionService endpoints using the Connect protocol
 * (plain HTTP/JSON POST). Server URL is configured via PI_SERVER_URL
 * (default: http://localhost:4097).
 */

import type {
  CreateResponse,
  PromptResponse,
  PromptAsyncResponse,
  GetMessagesResponse,
  GetStateResponse,
  AbortResponse,
  DeleteResponse,
  ListResponse,
} from "./types.js";

const BASE_URL =
  (process.env.PI_SERVER_URL ?? "http://localhost:4097").replace(/\/$/, "") +
  "/pirpc.v1.SessionService";

const HEADERS = { "Content-Type": "application/json" };

async function post<T>(endpoint: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}/${endpoint}`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`pi-rpc ${endpoint} failed (${res.status}): ${text}`);
  }

  return res.json() as Promise<T>;
}

export function piCreate(
  provider: string,
  model: string,
  cwd?: string,
  thinkingLevel?: string
): Promise<CreateResponse> {
  return post<CreateResponse>("Create", { provider, model, cwd, thinkingLevel });
}

export function piPrompt(
  sessionId: string,
  message: string
): Promise<PromptResponse> {
  return post<PromptResponse>("Prompt", { sessionId, message });
}

export function piPromptAsync(
  sessionId: string,
  message: string
): Promise<PromptAsyncResponse> {
  return post<PromptAsyncResponse>("PromptAsync", { sessionId, message });
}

export function piGetMessages(sessionId: string): Promise<GetMessagesResponse> {
  return post<GetMessagesResponse>("GetMessages", { sessionId });
}

export function piGetState(sessionId: string): Promise<GetStateResponse> {
  return post<GetStateResponse>("GetState", { sessionId });
}

export function piAbort(sessionId: string): Promise<AbortResponse> {
  return post<AbortResponse>("Abort", { sessionId });
}

export function piDelete(sessionId: string): Promise<DeleteResponse> {
  return post<DeleteResponse>("Delete", { sessionId });
}

export function piList(): Promise<ListResponse> {
  return post<ListResponse>("List", {});
}
