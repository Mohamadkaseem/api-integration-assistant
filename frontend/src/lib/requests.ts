// Helpers for the Request Builder: empty values, building a request from an
// imported endpoint, placeholder detection and "Copy as cURL".

import type { ApiDocDetail, ApiEndpoint, AuthConfig, KeyValue, OutgoingRequest } from "@/lib/api";

export const MASK = "••••••";
export const WRITE_METHODS = ["POST", "PUT", "PATCH", "DELETE"];

export const EMPTY_AUTH: AuthConfig = {
  type: "none",
  token: "",
  username: "",
  password: "",
  key_name: "",
  key_value: "",
  key_in: "header",
  token_prefix: "Bearer",
};

export const EMPTY_REQUEST: OutgoingRequest = {
  method: "GET",
  url: "",
  params: [],
  headers: [],
  body_type: "none",
  body: "",
  form: [],
  auth: EMPTY_AUTH,
};

/** Unfilled placeholders such as {id}, {{base_url}} or /:id/ that must be replaced before sending. */
export function findPlaceholders(text: string): string[] {
  const found = text.match(/\{\{[^}]+\}\}|\{[^}]+\}|\/:[A-Za-z_][\w-]*/g) ?? [];
  return Array.from(new Set(found));
}

/** Variables from Postman-style base URLs: "{{base_url}} = https://..." -> {base_url: "https://..."} */
function variablesFrom(doc: ApiDocDetail): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const line of doc.base_urls) {
    const m = line.match(/^\{\{([^}]+)\}\}\s*=\s*(.*)$/);
    if (m && m[2].trim()) vars[m[1]] = m[2].trim();
  }
  return vars;
}

function firstRealBaseUrl(doc: ApiDocDetail): string {
  return doc.base_urls.find((u) => /^https?:\/\//.test(u)) ?? "";
}

/** Make a simple example from a JSON schema: {"type":"object","properties":{"name":{"type":"string"}}} -> {"name": ""} */
function exampleFromSchema(schema: unknown, depth = 0): unknown {
  if (!schema || typeof schema !== "object" || depth > 6) return null;
  const s = schema as Record<string, unknown>;
  if (s.example !== undefined) return s.example;
  if (s.type === "object" || s.properties) {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries((s.properties as Record<string, unknown>) ?? {})) {
      out[key] = exampleFromSchema(value, depth + 1);
    }
    return out;
  }
  if (s.type === "array") return [exampleFromSchema(s.items, depth + 1)];
  if (s.type === "integer" || s.type === "number") return 0;
  if (s.type === "boolean") return false;
  if (Array.isArray(s.enum) && s.enum.length) return s.enum[0];
  return "";
}

function bodyFromEndpoint(raw: string): { body_type: OutgoingRequest["body_type"]; body: string } {
  if (!raw.trim()) return { body_type: "none", body: "" };
  const text = raw.replace(/^\[[^\]]+\]\n/, ""); // drop "[application/json]" label from OpenAPI imports
  try {
    const parsed = JSON.parse(text);
    const looksLikeSchema = parsed && typeof parsed === "object" && ("properties" in parsed || parsed.type === "object" || parsed.type === "array");
    const example = looksLikeSchema ? exampleFromSchema(parsed) : parsed;
    return { body_type: "json", body: JSON.stringify(example, null, 2) };
  } catch {
    return { body_type: "text", body: text };
  }
}

export function requestFromEndpoint(doc: ApiDocDetail, endpoint: ApiEndpoint): OutgoingRequest {
  const vars = variablesFrom(doc);
  let url = endpoint.path.trim();
  if (url.startsWith("/")) url = firstRealBaseUrl(doc).replace(/\/$/, "") + url;
  url = url.replace(/\{\{([^}]+)\}\}/g, (whole, name: string) => vars[name] ?? whole);

  const params: KeyValue[] = endpoint.parameters
    .filter((p) => p.location === "query")
    .map((p) => ({ name: p.name, value: "", enabled: p.required }));
  const headers: KeyValue[] = endpoint.parameters
    .filter((p) => p.location === "header" && p.name.toLowerCase() !== "authorization")
    .map((p) => ({ name: p.name, value: "", enabled: true }));
  const form: KeyValue[] = endpoint.parameters
    .filter((p) => p.location === "form")
    .map((p) => ({ name: p.name, value: "", enabled: true }));

  const body = form.length && !endpoint.request_body ? { body_type: "form" as const, body: "" } : bodyFromEndpoint(endpoint.request_body);
  const method = (["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"].includes(endpoint.method) ? endpoint.method : "GET") as OutgoingRequest["method"];
  return { ...EMPTY_REQUEST, method, url, params, headers, form, ...body };
}

/** A copy-paste cURL command. Secrets are replaced by placeholders unless includeSecrets is true. */
export function toCurl(req: OutgoingRequest, includeSecrets = false): string {
  const quote = (s: string) => `'${s.replace(/'/g, `'\\''`)}'`;
  const secret = (s: string, label: string) => (includeSecrets ? s : `<${label}>`);
  const url = new URL(req.url || "https://example.com");
  for (const p of req.params) if (p.enabled && p.name) url.searchParams.append(p.name, p.value);
  if (req.auth.type === "api_key" && req.auth.key_in === "query" && req.auth.key_name)
    url.searchParams.append(req.auth.key_name, secret(req.auth.key_value, "API_KEY"));

  const parts = [`curl -X ${req.method} ${quote(url.toString())}`];
  for (const h of req.headers) if (h.enabled && h.name) parts.push(`-H ${quote(`${h.name}: ${h.value}`)}`);
  if (req.auth.type === "bearer") parts.push(`-H ${quote(`Authorization: ${req.auth.token_prefix || "Bearer"} ${secret(req.auth.token, "TOKEN")}`)}`);
  if (req.auth.type === "basic") parts.push(`-u ${quote(`${req.auth.username}:${secret(req.auth.password, "PASSWORD")}`)}`);
  if (req.auth.type === "api_key" && req.auth.key_in === "header" && req.auth.key_name)
    parts.push(`-H ${quote(`${req.auth.key_name}: ${secret(req.auth.key_value, "API_KEY")}`)}`);
  if (!["GET", "HEAD"].includes(req.method)) {
    if (req.body_type === "json") parts.push(`-H 'Content-Type: application/json'`, `--data ${quote(req.body)}`);
    if (req.body_type === "text") parts.push(`--data ${quote(req.body)}`);
    if (req.body_type === "form") for (const f of req.form) if (f.enabled && f.name) parts.push(`--data-urlencode ${quote(`${f.name}=${f.value}`)}`);
  }
  return parts.join(" \\\n  ");
}
