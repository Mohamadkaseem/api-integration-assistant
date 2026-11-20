"use client";

import { useState } from "react";

import { CredentialForm } from "@/components/CredentialForm";
import {
  deleteCredential,
  exchangeOAuthCode,
  getAuthorizeUrl,
  refreshOAuth,
  updateCredential,
  type Credential,
} from "@/lib/api";
import { EMPTY_CREDENTIAL, TYPE_LABEL, ZOHO_DATA_CENTERS, expiresIn } from "@/lib/credentials";

const STATUS = {
  ready: { label: "Ready", style: "bg-emerald-50 text-emerald-700" },
  needs_authorization: { label: "Not connected yet", style: "bg-amber-50 text-amber-800" },
  error: { label: "Error", style: "bg-rose-50 text-rose-700" },
};

export function CredentialCard({ cred, onChanged, onDeleted }: { cred: Credential; onChanged: (c: Credential) => void; onDeleted: () => void }) {
  const [editing, setEditing] = useState(false);
  const [showConnect, setShowConnect] = useState(cred.type === "oauth2" && cred.status !== "ready");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const isZoho = cred.settings.provider === "zoho";
  const dc = ZOHO_DATA_CENTERS.find((d) => d.value === cred.settings.data_center);

  async function run(action: () => Promise<Credential>, success: string) {
    setBusy(true);
    setMessage(null);
    try {
      const updated = await action();
      onChanged(updated);
      setMessage({ kind: "ok", text: success });
      if (updated.status === "ready") setShowConnect(false);
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Failed." });
    } finally {
      setBusy(false);
    }
  }

  async function signInWithBrowser() {
    try {
      const { url } = await getAuthorizeUrl(cred.id);
      window.location.href = url; // the provider sends the browser back to /credentials when done
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not start sign-in." });
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${cred.name}"? The saved secrets are removed permanently.`)) return;
    await deleteCredential(cred.id);
    onDeleted();
  }

  if (editing) {
    return (
      <CredentialForm
        editing
        initial={{
          ...EMPTY_CREDENTIAL,
          name: cred.name,
          app_name: cred.app_name,
          type: cred.type,
          environment: cred.environment,
          notes: cred.notes,
          key_name: cred.settings.key_name ?? "",
          key_in: (cred.settings.key_in as "header" | "query") ?? "header",
          token_prefix: cred.settings.token_prefix ?? "",
          username: cred.settings.username ?? "",
          provider: (cred.settings.provider as "zoho" | "generic") ?? "zoho",
          data_center: (cred.settings.data_center as typeof EMPTY_CREDENTIAL.data_center) ?? "com",
          scopes: cred.settings.scopes ?? "",
          auth_url: cred.settings.auth_url ?? "",
          token_url: cred.settings.token_url ?? "",
          client_auth_method: (cred.settings.client_auth_method as "post" | "basic") ?? "post",
        }}
        onCancel={() => setEditing(false)}
        onSubmit={async (data) => {
          // Only send what can change; empty secrets mean "keep".
          const { type: _type, provider: _provider, ...changes } = data;
          void _type;
          void _provider;
          onChanged(await updateCredential(cred.id, changes));
          setEditing(false);
        }}
      />
    );
  }

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-slate-900">{cred.name}</p>
          <p className="text-sm text-slate-600">
            {cred.app_name && <>{cred.app_name} · </>}
            {TYPE_LABEL[cred.type]}
            {isZoho && dc && <> · Zoho {dc.label}</>}
            {cred.secret_hint && <span className="ml-1 font-mono text-xs text-slate-400">{cred.secret_hint}</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cred.environment === "production" ? "bg-rose-600 text-white" : "bg-slate-100 text-slate-700"}`}>
            {cred.environment === "production" ? "PRODUCTION" : "Sandbox"}
          </span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS[cred.status].style}`}>{STATUS[cred.status].label}</span>
        </div>
      </div>

      {cred.type === "oauth2" && cred.status === "ready" && <p className="mt-2 text-xs text-slate-500">{expiresIn(cred.expires_at)}</p>}
      {cred.status === "error" && cred.last_error && <p className="mt-2 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{cred.last_error}</p>}
      {message && (
        <p className={`mt-2 rounded-md px-3 py-2 text-sm ${message.kind === "ok" ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-700"}`}>{message.text}</p>
      )}

      {cred.type === "oauth2" && showConnect && (
        <div className="mt-4 grid gap-4 rounded-lg bg-slate-50 p-4 lg:grid-cols-2">
          <div className="space-y-2 text-sm">
            <p className="font-semibold text-slate-900">Option A — paste a code{isZoho ? " (Zoho Self Client)" : ""}</p>
            {isZoho ? (
              <ol className="list-decimal space-y-1 pl-5 text-slate-700">
                <li>
                  Open the Zoho API Console:{" "}
                  <a href={dc?.console} target="_blank" rel="noreferrer" className="text-indigo-700 underline">
                    {dc?.console.replace("https://", "")}
                  </a>
                </li>
                <li>Choose your <b>Self Client</b> (the one whose Client ID/Secret you saved) → <b>Generate Code</b>.</li>
                <li>
                  Scope: <span className="font-mono text-xs">{cred.settings.scopes || "(the scopes you need)"}</span>, duration 10 minutes.
                </li>
                <li>Copy the code and paste it here right away (it works once).</li>
              </ol>
            ) : (
              <p className="text-slate-700">Paste an authorization code issued for this client with the redirect URL shown on the right.</p>
            )}
            <div className="flex gap-2">
              <input className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs" value={code} onChange={(e) => setCode(e.target.value)} placeholder="1000.xxxxxxxx…" autoComplete="off" />
              <button
                disabled={busy || code.trim().length < 4}
                onClick={() => run(() => exchangeOAuthCode(cred.id, code.trim()), "Connected ✓ — refresh token saved (encrypted).").then(() => setCode(""))}
                className="shrink-0 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {busy ? "Connecting…" : "Connect"}
              </button>
            </div>
          </div>
          <div className="space-y-2 text-sm">
            <p className="font-semibold text-slate-900">Option B — sign in with browser</p>
            <p className="text-slate-700">
              {isZoho ? "Needs a Server-based client in the Zoho API Console" : "Needs this redirect URL registered with the provider"} with this
              Authorized Redirect URI:
            </p>
            <div className="flex gap-2">
              <code className="flex-1 break-all rounded-md border border-slate-200 bg-white px-3 py-2 text-xs">{cred.redirect_uri}</code>
              <button
                onClick={async () => {
                  await navigator.clipboard.writeText(cred.redirect_uri);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
                className="shrink-0 rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700"
              >
                {copied ? "Copied ✓" : "Copy"}
              </button>
            </div>
            <button onClick={signInWithBrowser} className="rounded-md border border-indigo-300 bg-white px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50">
              Sign in with browser
            </button>
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        {cred.type === "oauth2" && cred.has_refresh_token && (
          <button disabled={busy} onClick={() => run(() => refreshOAuth(cred.id), "Connection works ✓ — got a fresh access token.")} className="font-medium text-indigo-700 hover:underline disabled:opacity-50">
            Test connection
          </button>
        )}
        {cred.type === "oauth2" && !showConnect && (
          <button onClick={() => setShowConnect(true)} className="text-slate-600 hover:underline">
            Reconnect
          </button>
        )}
        <button onClick={() => setEditing(true)} className="text-slate-600 hover:underline">
          Edit
        </button>
        <button onClick={remove} className="text-rose-700 hover:underline">
          Delete
        </button>
      </div>
    </li>
  );
}
