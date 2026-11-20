"use client";

import { useState } from "react";

import type { CredentialInput, CredentialType } from "@/lib/api";
import { TYPE_LABEL, ZOHO_DATA_CENTERS } from "@/lib/credentials";

const input = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";
const label = "block text-sm font-medium text-slate-700";

type Props = {
  initial: CredentialInput;
  editing?: boolean; // in edit mode secret fields start empty: leave blank to keep the saved value
  onSubmit: (data: CredentialInput) => Promise<void>;
  onCancel: () => void;
};

export function CredentialForm({ initial, editing = false, onSubmit, onCancel }: Props) {
  const [data, setData] = useState<CredentialInput>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<CredentialInput>) => setData((d) => ({ ...d, ...patch }));
  const keep = editing ? "Leave empty to keep the saved value" : "";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSubmit(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  const secretInput = (field: keyof CredentialInput, text: string, placeholder = "") => (
    <label className={label}>
      {text}
      <input className={`${input} font-mono`} type="password" autoComplete="off" value={data[field] as string}
        onChange={(e) => set({ [field]: e.target.value } as Partial<CredentialInput>)} placeholder={keep || placeholder} />
    </label>
  );

  return (
    <form onSubmit={submit} className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={label}>
          Name *
          <input className={input} value={data.name} onChange={(e) => set({ name: e.target.value })} placeholder="e.g. Zoho CRM — sandbox" maxLength={200} />
        </label>
        <label className={label}>
          Application
          <input className={input} value={data.app_name} onChange={(e) => set({ app_name: e.target.value })} placeholder="e.g. Zoho CRM" maxLength={100} />
        </label>
        <label className={label}>
          Type
          <select className={input} value={data.type} disabled={editing} onChange={(e) => set({ type: e.target.value as CredentialType })}>
            {(Object.keys(TYPE_LABEL) as CredentialType[]).map((t) => (
              <option key={t} value={t}>
                {TYPE_LABEL[t]}
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          Environment
          <select className={input} value={data.environment} onChange={(e) => set({ environment: e.target.value as "sandbox" | "production" })}>
            <option value="sandbox">Sandbox / test</option>
            <option value="production">Production (real data)</option>
          </select>
        </label>
      </div>

      {data.type === "api_key" && (
        <div className="grid gap-4 sm:grid-cols-3">
          <label className={label}>
            Key name
            <input className={input} value={data.key_name} onChange={(e) => set({ key_name: e.target.value })} placeholder="X-API-Key" />
          </label>
          {secretInput("key_value", "Key value")}
          <label className={label}>
            Send in
            <select className={input} value={data.key_in} onChange={(e) => set({ key_in: e.target.value as "header" | "query" })}>
              <option value="header">Header</option>
              <option value="query">URL query</option>
            </select>
          </label>
        </div>
      )}

      {data.type === "bearer" && (
        <div className="grid gap-4 sm:grid-cols-[12rem_1fr]">
          <label className={label}>
            Prefix
            <input className={input} value={data.token_prefix} onChange={(e) => set({ token_prefix: e.target.value })} placeholder="Bearer" />
          </label>
          {secretInput("token", "Token")}
        </div>
      )}

      {data.type === "basic" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <label className={label}>
            Username
            <input className={input} value={data.username} onChange={(e) => set({ username: e.target.value })} autoComplete="off" />
          </label>
          {secretInput("password", "Password")}
        </div>
      )}

      {data.type === "oauth2" && (
        <div className="space-y-4">
          {!editing && (
            <div className="flex gap-4 text-sm">
              {(["zoho", "generic"] as const).map((p) => (
                <label key={p} className="flex items-center gap-1.5">
                  <input type="radio" checked={data.provider === p} onChange={() => set({ provider: p })} />
                  {p === "zoho" ? "Zoho (CRM, Sign, Books, …)" : "Other OAuth 2.0 (HubSpot, Google, …)"}
                </label>
              ))}
            </div>
          )}
          {data.provider === "zoho" && (
            <label className={label}>
              Data centre (where the Zoho account lives)
              <select className={input} value={data.data_center} onChange={(e) => set({ data_center: e.target.value as CredentialInput["data_center"] })}>
                {ZOHO_DATA_CENTERS.map((dc) => (
                  <option key={dc.value} value={dc.value}>
                    {dc.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {data.provider === "generic" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className={label}>
                Authorization URL
                <input className={input} value={data.auth_url} onChange={(e) => set({ auth_url: e.target.value })} placeholder="https://app.example.com/oauth/authorize" />
              </label>
              <label className={label}>
                Token URL *
                <input className={input} value={data.token_url} onChange={(e) => set({ token_url: e.target.value })} placeholder="https://api.example.com/oauth/token" />
              </label>
              <label className={label}>
                Send client secret
                <select className={input} value={data.client_auth_method} onChange={(e) => set({ client_auth_method: e.target.value as "post" | "basic" })}>
                  <option value="post">In the request body (most providers)</option>
                  <option value="basic">As Basic auth header</option>
                </select>
              </label>
              <label className={label}>
                Token prefix
                <input className={input} value={data.token_prefix} onChange={(e) => set({ token_prefix: e.target.value })} placeholder="Bearer" />
              </label>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className={label}>
              Client ID
              <input className={`${input} font-mono`} value={data.client_id} onChange={(e) => set({ client_id: e.target.value })} placeholder={keep || "1000.XXXXXXXX"} autoComplete="off" />
            </label>
            {secretInput("client_secret", "Client Secret")}
          </div>
          <label className={label}>
            Scopes
            <input className={`${input} font-mono`} value={data.scopes} onChange={(e) => set({ scopes: e.target.value })}
              placeholder={data.provider === "zoho" ? "e.g. ZohoCRM.modules.ALL,ZohoCRM.settings.READ" : "space- or comma-separated, as the provider expects"} />
            {data.provider === "zoho" && (
              <span className="mt-1 block text-xs font-normal text-slate-500">Comma-separated. Use the scope names from the Zoho product&apos;s API documentation.</span>
            )}
          </label>
        </div>
      )}

      <label className={label}>
        Notes
        <input className={input} value={data.notes} onChange={(e) => set({ notes: e.target.value })} placeholder="Which org / account, who created it… (no secrets here)" />
      </label>

      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={saving || !data.name.trim()} className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
          {saving ? "Saving…" : editing ? "Save changes" : "Save credential"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
          Cancel
        </button>
      </div>
      <p className="text-xs text-slate-500">Secrets are encrypted on your computer and never sent to the browser again — only a hint like “…a1b2” is shown.</p>
    </form>
  );
}
