// Helper for talking to our FastAPI backend.
// Every backend call in the app goes through this file.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------- Generic request helper ----------

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      ...options,
      // JSON bodies need this header; file uploads (FormData) must let the browser set its own.
      headers: typeof options.body === "string" ? { "Content-Type": "application/json", ...options.headers } : options.headers,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the backend. Is it running on port 8000?");
  }

  if (!response.ok) {
    // FastAPI sends errors as { "detail": ... }
    let message = `Backend responded with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail))
        message = body.detail.map((d: { loc?: string[]; msg: string }) => `${d.loc?.at(-1) ?? ""}: ${d.msg}`).join("; ");
    } catch {
      /* body was not JSON - keep the default message */
    }
    throw new ApiError(response.status, message);
  }

  // 204 No Content has no body
  return (response.status === 204 ? undefined : await response.json()) as T;
}

// ---------- Health ----------

export type HealthResponse = {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
};

export const getHealth = () => request<HealthResponse>("/api/health");

// ---------- Projects ----------

export type ProjectStatus = "planning" | "in_progress" | "testing" | "completed" | "on_hold";

export type ProjectInput = {
  name: string;
  source_app: string;
  target_app: string;
  requirement: string;
  status: ProjectStatus;
  notes: string;
};

export type Project = ProjectInput & {
  id: number;
  created_at: string;
  updated_at: string;
};

export const listProjects = () => request<Project[]>("/api/projects");

export const getProject = (id: number) => request<Project>(`/api/projects/${id}`);

export const createProject = (data: ProjectInput) =>
  request<Project>("/api/projects", { method: "POST", body: JSON.stringify(data) });

export const updateProject = (id: number, data: Partial<ProjectInput>) =>
  request<Project>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteProject = (id: number) =>
  request<void>(`/api/projects/${id}`, { method: "DELETE" });

// ---------- AI / Requirement analysis ----------

export type AIStatus = { configured: boolean; provider: string; model: string };

export type Clarification = { question: string; answer: string };

export type RequirementAnalysis = {
  summary: string;
  trigger: {
    event: string;
    app: string;
    detection: "webhook" | "polling" | "scheduled" | "manual" | "unknown";
    notes: string;
  };
  source_app: string;
  target_apps: string[];
  steps: {
    order: number;
    app: string;
    action: string;
    description: string;
    condition: string;
    waits_for: string;
  }[];
  data_to_transfer: { name: string; from_app: string; to_app: string; notes: string }[];
  conditions: string[];
  status_updates: string[];
  expected_outcome: string;
  assumptions: string[];
  clarification_questions: { question: string; why_it_matters: string; priority: "high" | "medium" | "low" }[];
  readiness: "ready_for_design" | "needs_clarification";
};

export type AnalysisResult = {
  id: number | null;
  project_id: number | null;
  requirement: string;
  clarifications: Clarification[];
  analysis: RequirementAnalysis;
  ai_model: string;
  created_at: string | null;
};

export const getAIStatus = () => request<AIStatus>("/api/ai/status");

export const analyzeRequirement = (data: {
  requirement: string;
  clarifications: Clarification[];
  project_id: number | null;
}) => request<AnalysisResult>("/api/analysis", { method: "POST", body: JSON.stringify(data) });

export const getLatestAnalysis = (projectId: number) =>
  request<AnalysisResult | null>(`/api/projects/${projectId}/analyses/latest`);

// ---------- API documentation ----------

export type Verification = "spec" | "quoted" | "unverified";

export type ApiParameter = {
  name: string;
  location: string;
  required: boolean;
  type: string;
  description: string;
};

export type ApiEndpoint = {
  id: number;
  method: string;
  path: string;
  summary: string;
  description: string;
  auth: string;
  parameters: ApiParameter[];
  request_body: string;
  responses: { status: string; description: string; example: string }[];
  verification: Verification;
  evidence: string;
};

export type ApiDocSummary = {
  id: number;
  project_id: number | null;
  app_name: string;
  title: string;
  source_type: "openapi" | "postman" | "pdf" | "html" | "text";
  source_ref: string;
  created_at: string;
  endpoint_count: number;
  counts: Record<Verification, number>;
};

export type ApiDocDetail = ApiDocSummary & {
  version: string;
  base_urls: string[];
  auth_schemes: { name: string; type: string; details: string }[];
  warnings: string[];
  endpoints: ApiEndpoint[];
};

export const listDocs = (projectId?: number) =>
  request<ApiDocSummary[]>(projectId ? `/api/docs?project_id=${projectId}` : "/api/docs");

export const getDoc = (id: number) => request<ApiDocDetail>(`/api/docs/${id}`);

export const importDoc = (form: FormData) =>
  request<ApiDocDetail>("/api/docs/import", { method: "POST", body: form });

export const deleteDoc = (id: number) => request<void>(`/api/docs/${id}`, { method: "DELETE" });

export const deleteEndpoint = (docId: number, endpointId: number) =>
  request<void>(`/api/docs/${docId}/endpoints/${endpointId}`, { method: "DELETE" });
