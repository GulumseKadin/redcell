# Assessment report — scanme.nmap.org demo

Authorization: NMAP-PUBLIC-TEST-HOST (http://scanme.nmap.org — owner authorizes scanning)  
Generated: 2026-11-18 05:50 UTC  
Findings recorded: 9
Severity summary: Critical: 3

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

### #5 — http_fingerprint (via recon)

```
HTTP 200 for http://scanme.nmap.org
date: Wed, 18 Nov 2026 05:46:17 GMT
server: Apache/2.4.7 (Ubuntu)
accept-ranges: bytes
vary: Accept-Encoding
content-encoding: gzip
content-length: 2068
keep-alive: timeout=5, max=100
connection: Keep-Alive
content-type: text/html
```

- CVSS 4.0: _not scored_
- Remediation: _none provided_

### #6 — record_finding (via exploit)

```
Recorded finding: Outdated Apache Server Version Exposes Known Vulnerabilities [CVSS 9.3 Critical]
```

- CVSS 4.0: **9.3 (Critical)** — `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N`
- Remediation: Upgrade Apache to a supported version (e.g., 2.4.41+) and apply security patches. Disable unnecessary modules and enable mod_security for mitigation.
- PoC:

  ```
  HTTP response header: 'Server: Apache/2.4.7 (Ubuntu)'
  ```

### #7 — http_fingerprint (via verify)

```
HTTP 200 for http://scanme.nmap.org
date: Wed, 18 Nov 2026 05:48:30 GMT
server: Apache/2.4.7 (Ubuntu)
accept-ranges: bytes
vary: Accept-Encoding
content-encoding: gzip
content-length: 2068
keep-alive: timeout=5, max=100
connection: Keep-Alive
content-type: text/html
```

- CVSS 4.0: _not scored_
- Remediation: _none provided_

### #8 — record_finding (via verify)

```
Recorded finding: Exposed Apache/2.4.7 (Ubuntu) with Known Vulnerabilities [CVSS 9.3 Critical]
```

- CVSS 4.0: **9.3 (Critical)** — `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N`
- Remediation: Upgrade Apache to a secure, patched version (e.g., 2.4.8+). Apply security patches promptly.
- PoC:

  ```
  HTTP GET request to http://scanme.nmap.org
  Response headers:
  server: Apache/2.4.7 (Ubuntu)
  This version is known to have vulnerabilities.
  ```

### #9 — http_fingerprint (via report)

```
HTTP 200 for http://scanme.nmap.org
date: Wed, 18 Nov 2026 05:49:30 GMT
server: Apache/2.4.7 (Ubuntu)
accept-ranges: bytes
vary: Accept-Encoding
content-encoding: gzip
content-length: 2068
keep-alive: timeout=5, max=100
connection: Keep-Alive
content-type: text/html
```

- CVSS 4.0: _not scored_
- Remediation: _none provided_
