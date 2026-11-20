import type { CredentialInput, CredentialType } from "@/lib/api";

export const TYPE_LABEL: Record<CredentialType, string> = {
  api_key: "API key",
  bearer: "Bearer token",
  basic: "Basic auth",
  oauth2: "OAuth 2.0",
};

export const ZOHO_DATA_CENTERS: { value: CredentialInput["data_center"]; label: string; console: string }[] = [
  { value: "com", label: "United States (zoho.com)", console: "https://api-console.zoho.com" },
  { value: "in", label: "India (zoho.in)", console: "https://api-console.zoho.in" },
  { value: "eu", label: "Europe (zoho.eu)", console: "https://api-console.zoho.eu" },
  { value: "com.au", label: "Australia (zoho.com.au)", console: "https://api-console.zoho.com.au" },
  { value: "jp", label: "Japan (zoho.jp)", console: "https://api-console.zoho.jp" },
  { value: "ca", label: "Canada (zohocloud.ca)", console: "https://api-console.zohocloud.ca" },
];

export const EMPTY_CREDENTIAL: CredentialInput = {
  name: "",
  app_name: "",
  type: "oauth2",
  environment: "sandbox",
  notes: "",
  key_name: "",
  key_in: "header",
  key_value: "",
  token: "",
  token_prefix: "",
  username: "",
  password: "",
  provider: "zoho",
  data_center: "com",
  client_id: "",
  client_secret: "",
  scopes: "",
  auth_url: "",
  token_url: "",
  client_auth_method: "post",
};

export function expiresIn(expiresAt: number | null): string {
  if (!expiresAt) return "";
  const minutes = Math.round((expiresAt * 1000 - Date.now()) / 60000);
  if (minutes <= 0) return "access token expired — renewed automatically on next use";
  return `access token valid for ${minutes} min (renewed automatically)`;
}
