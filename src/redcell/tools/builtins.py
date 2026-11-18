"""Built-in tool wrappers (skeleton).

These wrap standard, legitimate recon utilities and return *summaries*,
not raw output. They are deliberately minimal — add parsing, timeouts,
and output truncation as you build. No exploitation payloads live here;
this layer is for discovery/enumeration against in-scope targets only.
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Any

from .base import Tool, ToolResult

# How much tool output we ever hand back to the model, in characters.
MAX_OUTPUT_CHARS = 4000


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out[:MAX_OUTPUT_CHARS]
    except FileNotFoundError:
        return 127, f"binary not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"


class PortScanTool(Tool):
    """Wrap nmap for service discovery on an in-scope host."""
    name = "port_scan"
    description = "Discover open ports and services on a single in-scope host using nmap."
    target_arg = "target"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Single host/IP, must be in scope."},
            "ports": {"type": "string", "description": "e.g. 'top100' or '1-1000'", "default": "top100"},
        },
        "required": ["target"],
    }

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        if not shutil.which("nmap"):
            return ToolResult(ok=False, summary="nmap is not installed on this host.")
        target = arguments["target"]
        ports = arguments.get("ports", "top100")
        cmd = ["nmap", "-sV", "-Pn"]
        cmd += ["--top-ports", "100"] if ports == "top100" else ["-p", ports]
        cmd += [target]
        code, out = _run(cmd)
        return ToolResult(
            ok=(code == 0),
            summary=out or f"nmap exited {code} with no output.",
            data={"target": target, "ports": ports, "exit_code": code},
        )


class HttpFingerprintTool(Tool):
    """Fetch headers / basic fingerprint of an in-scope web service."""
    name = "http_fingerprint"
    description = "Retrieve HTTP response headers and status for an in-scope URL/host."
    target_arg = "target"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"target": {"type": "string", "description": "Host or URL, must be in scope."}},
        "required": ["target"],
    }

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        import httpx
        target = arguments["target"]
        url = target if target.startswith("http") else f"http://{target}"
        try:
            r = httpx.get(url, follow_redirects=True, timeout=15.0)
            headers = "\n".join(f"{k}: {v}" for k, v in r.headers.items())
            return ToolResult(
                ok=True,
                summary=f"HTTP {r.status_code} for {url}\n{headers}"[:MAX_OUTPUT_CHARS],
                data={"target": target, "status": r.status_code},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, summary=f"request failed: {e}")


def default_registry():
    from .base import ToolRegistry
    from .findings import RecordFindingTool

    reg = ToolRegistry()
    reg.register(PortScanTool())
    reg.register(HttpFingerprintTool())
    reg.register(RecordFindingTool())  # Faz 7: let agents record scored findings
    return reg
