# Assessment report — localhost self-test

Authorization: SELF-OWNED-MACHINE  
Generated: 2026-11-17 08:05 UTC  
Findings recorded: 4
Severity summary: Critical: 1

## Findings

### #1 — http_fingerprint (via recon)

```
HTTP 200 for http://127.0.0.1:11434
content-type: text/plain; charset=utf-8
date: Tue, 17 Nov 2026 08:04:38 GMT
content-length: 17
```

- CVSS 4.0: _not scored_
- Remediation: _none provided_

### #2 — record_finding (via recon)

```
Recorded finding: Exposed Ollama API with no auth [CVSS 9.3 Critical]
```

- CVSS 4.0: **9.3 (Critical)** — `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N`
- Remediation: Implement authentication (e.g., API key or token) and validate requests before processing. Restrict access to trusted networks or IP addresses.
- PoC:

  ```
  GET http://127.0.0.1:11434\nResponse: \"Hello, world!\"
  ```

### #3 — http_fingerprint (via report)

```
HTTP 200 for http://127.0.0.1:11434
content-type: text/plain; charset=utf-8
date: Tue, 17 Nov 2026 08:05:09 GMT
content-length: 17
```

- CVSS 4.0: _not scored_
- Remediation: _none provided_

### #4 — http_fingerprint (via verify)

```
HTTP 200 for http://127.0.0.1:11434
content-type: text/plain; charset=utf-8
date: Tue, 17 Nov 2026 08:05:33 GMT
content-length: 17
```

- CVSS 4.0: _not scored_
- Remediation: _none provided_
