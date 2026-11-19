// One list that defines every section of the app.
// The sidebar and the placeholder pages both read from here.

export type NavItem = {
  href: string;
  label: string;
  description: string;
  milestone: string; // which milestone builds this section
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", description: "Overview of your integration projects.", milestone: "M1" },
  { href: "/projects", label: "Projects", description: "Your integration projects (Zwayam ↔ Zoho Sign, HubSpot → Zoho CRM, …).", milestone: "M2" },
  { href: "/requirements", label: "Requirement Analyzer", description: "Describe a requirement in plain language; get trigger, apps, data, conditions, actions and clarification questions.", milestone: "M3" },
  { href: "/request-builder", label: "Request Builder", description: "Build and send API requests, then see status, headers, body and timing.", milestone: "M4" },
  { href: "/credentials", label: "Credentials", description: "API keys, Bearer tokens, Basic auth and OAuth 2.0 — stored encrypted.", milestone: "M5" },
  { href: "/troubleshooter", label: "Error Troubleshooter", description: "Paste an API error; get the cause, the field at fault and a corrected request.", milestone: "M6" },
  { href: "/api-docs", label: "API Doc Analyzer", description: "Import OpenAPI, Postman collections, PDF, text or URLs and extract real endpoints.", milestone: "M7" },
  { href: "/field-mapping", label: "Field Mapping", description: "Match fields between two applications and spot type, date and picklist differences.", milestone: "M8" },
  { href: "/workflow", label: "Workflow Designer", description: "See the integration sequence as a diagram: trigger, steps, decisions, results.", milestone: "M8" },
  { href: "/handover", label: "Handover Docs", description: "Generate the developer handover document and export it.", milestone: "M9" },
];
