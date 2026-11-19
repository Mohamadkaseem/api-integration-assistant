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
      headers: { "Content-Type": "application/json", ...options.headers },
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
