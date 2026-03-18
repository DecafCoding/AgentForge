/**
 * API client for the AgentForge backend.
 *
 * Uses the native fetch API. The base URL is configurable via the
 * VITE_API_BASE environment variable (defaults to "/api").
 */

import type {
  AskResponse,
  HealthResponse,
  MemoryAskResponse,
  WorkflowResponse,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function askAgent(question: string): Promise<AskResponse> {
  return request<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export async function runResearch(query: string): Promise<WorkflowResponse> {
  return request<WorkflowResponse>("/research", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export async function askWithMemory(
  question: string,
  userId: string,
): Promise<MemoryAskResponse> {
  return request<MemoryAskResponse>("/ask/memory", {
    method: "POST",
    body: JSON.stringify({ question, user_id: userId }),
  });
}

export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { method: "GET" });
}

export { ApiError };
