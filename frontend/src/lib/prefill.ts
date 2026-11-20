// Hands a request from another page (e.g. the Troubleshooter's corrected request) to the Request Builder.

import type { CorrectedRequest, OutgoingRequest } from "@/lib/api";
import { EMPTY_REQUEST } from "@/lib/requests";

const KEY = "request-builder-prefill";

export type Prefill = {
  request: OutgoingRequest;
  credential_id: number | null;
  endpoint_id: number | null;
  note: string;
};

export function fromCorrected(c: CorrectedRequest): OutgoingRequest {
  return {
    ...EMPTY_REQUEST,
    method: c.method,
    url: c.url,
    params: c.query.map((q) => ({ ...q, enabled: true })),
    headers: c.headers.filter((h) => !/^authorization$/i.test(h.name)).map((h) => ({ ...h, enabled: true })),
    body_type: c.body_type,
    body: c.body,
  };
}

export function savePrefill(prefill: Prefill) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(prefill));
  } catch {
    /* storage unavailable - the Request Builder just opens empty */
  }
}

export function takePrefill(): Prefill | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    return raw ? (JSON.parse(raw) as Prefill) : null;
  } catch {
    return null;
  }
}
