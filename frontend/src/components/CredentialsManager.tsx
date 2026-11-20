"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { CredentialCard } from "@/components/CredentialCard";
import { CredentialForm } from "@/components/CredentialForm";
import { createCredential, listCredentials, type Credential } from "@/lib/api";
import { EMPTY_CREDENTIAL } from "@/lib/credentials";

export function CredentialsManager() {
  const searchParams = useSearchParams();
  const [creds, setCreds] = useState<Credential[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Coming back from "Sign in with browser": ?connected=3 or ?oauth_error=...
  const connected = searchParams.get("connected");
  const oauthError = searchParams.get("oauth_error");

  useEffect(() => {
    listCredentials()
      .then(setCreds)
      .catch((err: Error) => setError(err.message));
  }, []);

  const replace = (c: Credential) => setCreds((list) => (list ?? []).map((x) => (x.id === c.id ? c : x)));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Credentials</h1>
          <p className="mt-1 text-slate-600">
            Save API keys, tokens and OAuth connections once, encrypted on your computer. Use them from the Request Builder.
          </p>
        </div>
        {!adding && (
          <button onClick={() => setAdding(true)} className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            + New credential
          </button>
        )}
      </div>

      {connected && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Signed in successfully ✓ — the refresh token is saved (encrypted).</p>}
      {oauthError && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">Sign-in failed: {oauthError}</p>}
      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      {adding && (
        <CredentialForm
          initial={EMPTY_CREDENTIAL}
          onCancel={() => setAdding(false)}
          onSubmit={async (data) => {
            const created = await createCredential(data);
            setCreds((list) => [...(list ?? []), created]);
            setAdding(false);
          }}
        />
      )}

      {creds?.length === 0 && !adding && (
        <p className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          No credentials yet. For Project C, add a Zoho OAuth 2.0 credential.
        </p>
      )}
      <ul className="space-y-3">
        {creds?.map((c) => (
          <CredentialCard key={c.id} cred={c} onChanged={replace} onDeleted={() => setCreds((list) => (list ?? []).filter((x) => x.id !== c.id))} />
        ))}
      </ul>
    </div>
  );
}
