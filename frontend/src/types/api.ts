/**
 * TypeScript interfaces matching the FastAPI backend schemas.
 *
 * These types mirror the Pydantic models in src/api/schemas.py and
 * src/agent/models.py. Keep them in sync when the backend changes.
 */

export interface Source {
  title: string;
  video_id: string;
  url: string;
}

export interface AskRequest {
  question: string;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
}

export interface ResearchRequest {
  query: string;
}

export interface WorkflowResponse {
  answer: string;
  sources: Source[];
  confidence: number;
}

export interface MemoryAskRequest {
  question: string;
  user_id: string;
}

export interface MemoryAskResponse {
  answer: string;
  sources: Source[];
  confidence: number;
}

export interface HealthResponse {
  status: string;
  database: string;
  version: string;
}
