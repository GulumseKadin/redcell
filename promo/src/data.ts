// Real material captured from an actual REDCELL run against scanme.nmap.org
// (Nmap's public, scanning-authorized test host) on 2026-11-18.

export const SCOPE = {
  name: "scanme.nmap.org demo",
  auth: "NMAP-PUBLIC-TEST-HOST",
  domain: "scanme.nmap.org",
};

export const STAGES = ["RECON", "EXPLOIT", "VERIFY", "REPORT"] as const;

// The live log lines, trimmed to the punchy beats.
export const LOG_LINES: { kind: string; text: string }[] = [
  { kind: "stage", text: "▶ stage: recon" },
  { kind: "think", text: "· recon thinking (step 1)" },
  { kind: "act", text: "→ http_fingerprint { target: scanme.nmap.org }" },
  { kind: "data", text: "HTTP 200 · server: Apache/2.4.7 (Ubuntu)" },
  { kind: "stage", text: "▶ stage: exploit" },
  { kind: "act", text: "→ record_finding { CVSS:4.0 ... VC:H/VI:H/VA:H }" },
  { kind: "stage", text: "▶ stage: verify" },
  { kind: "ok", text: "✓ confirmed: Apache/2.4.7 — known CVEs" },
  { kind: "stage", text: "▶ stage: report" },
  { kind: "audit", text: "Scope audit: 4 allowed · 0 blocked" },
];

export const FINDING = {
  title: "Outdated Apache Server Exposes Known Vulnerabilities",
  host: "scanme.nmap.org",
  evidence: "Server: Apache/2.4.7 (Ubuntu)",
  score: 9.3,
  severity: "CRITICAL",
  vector: "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N",
  remediation: "Upgrade Apache to a supported, patched version. Enable mod_security.",
};

export const STATS = [
  { label: "scope actions allowed", value: "4" },
  { label: "out-of-scope blocked", value: "0" },
  { label: "agents orchestrated", value: "4" },
  { label: "max severity", value: "9.3" },
];

export const FEATURES = [
  { k: "SCOPE-GATED", v: "every action checked before it runs" },
  { k: "MULTI-AGENT", v: "recon · exploit · verify · report" },
  { k: "CVSS 4.0", v: "real scored, evidence-grade findings" },
  { k: "MCP / HexStrike", v: "plug external tool servers" },
  { k: "LOCAL LLM", v: "keyless, runs on Ollama" },
  { k: "GRAPH STATE", v: "SQLite or Neo4j backend" },
];
