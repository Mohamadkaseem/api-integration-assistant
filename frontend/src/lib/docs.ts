import type { Verification } from "@/lib/api";

export const VERIFICATION: Record<Verification, { label: string; badge: string; help: string }> = {
  spec: {
    label: "Verified · from spec",
    badge: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    help: "Read by code from an OpenAPI or Postman file. No AI involved.",
  },
  quoted: {
    label: "Quoted from document",
    badge: "bg-sky-50 text-sky-700 ring-sky-200",
    help: "Found by AI; its quote and path were found word-for-word in the document.",
  },
  unverified: {
    label: "Unverified",
    badge: "bg-amber-50 text-amber-800 ring-amber-300",
    help: "Found by AI but NOT matched in the document. Check the original before using it.",
  },
};

export const SOURCE_LABEL: Record<string, string> = {
  openapi: "OpenAPI / Swagger",
  postman: "Postman collection",
  pdf: "PDF",
  html: "Web page",
  text: "Text",
};

export const METHOD_STYLE: Record<string, string> = {
  GET: "bg-sky-600",
  POST: "bg-emerald-600",
  PUT: "bg-amber-600",
  PATCH: "bg-violet-600",
  DELETE: "bg-rose-600",
};
