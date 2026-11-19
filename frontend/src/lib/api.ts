// Small helper for talking to our FastAPI backend.
// Every backend call in the app should go through this file.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
};

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/api/health`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Backend responded with status ${response.status}`);
  }
  return response.json();
}
