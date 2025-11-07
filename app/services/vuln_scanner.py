import os
import platform
import re
import subprocess
import tempfile
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from flask import current_app


class ScannerError(Exception):
    """Raised when the scanner cannot be executed."""


class ScannerNotFoundError(ScannerError):
    """Raised when the fscan executable is missing."""


class ScannerCancelled(Exception):
    """Raised when a running scan is cancelled."""


_HOST_PORT_REGEX = re.compile(r"((?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F:.]+):(\d{1,5})")


def _detect_platform() -> str:
    """Return a lowercase platform string ('windows', 'linux', etc.)."""
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system.startswith("linux"):
        return "linux"
    if system.startswith("darwin"):
        return "darwin"
    return system


def _ensure_absolute(path: str) -> str:
    """Resolve relative paths against the Flask app root."""
    if os.path.isabs(path):
        return path
    return os.path.join(current_app.root_path, path)


def _resolve_fscan_path() -> str:
    """Pick the correct fscan binary for the current platform."""
    platform_name = _detect_platform()
    cfg = current_app.config

    if platform_name == "windows":
        configured = cfg.get("FSCAN_WINDOWS_PATH")
        fallback = "fscan/fscan.exe"
    elif platform_name == "linux":
        configured = cfg.get("FSCAN_LINUX_PATH")
        fallback = "fscan/fscan"
    else:
        configured = cfg.get("FSCAN_DEFAULT_PATH")
        fallback = cfg.get("FSCAN_WINDOWS_PATH") or cfg.get("FSCAN_LINUX_PATH")

    candidate = configured or fallback
    if not candidate:
        raise ScannerNotFoundError("No fscan executable path configured for this platform.")

    absolute_path = _ensure_absolute(candidate)
    if not os.path.exists(absolute_path):
        raise ScannerNotFoundError(f"fscan executable not found at {absolute_path}")

    return absolute_path


def _build_command(
    executable: str,
    target: str,
    scan_type: str,
    options: Optional[Dict[str, bool]],
    extra_args: Optional[Iterable[str]] = None,
) -> List[str]:
    """Construct the fscan command-line."""
    command = [executable, "-h", target]

    # Map UI toggles to fscan switches when possible.
    if options is not None:
        if options.get("portScan") is False:
            command.append("-np")
        if options.get("serviceScan") is False:
            command.append("-nobr")
        if options.get("vulnScan") is False:
            command.append("-nopoc")

    if extra_args:
        command.extend(extra_args)

    return command


def _classify_severity(content: str) -> str:
    lowered = content.lower()
    if any(keyword in lowered for keyword in ("unauth", "rce", "cve", "vuln", "ms17", "weak password", "default password")):
        return "high"
    if "open" in lowered or "port" in lowered:
        return "low"
    return "medium"


def _derive_vuln_name(content: str) -> str:
    if "cve-" in content.lower():
        match = re.search(r"(CVE-\d{4}-\d{4,7})", content, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return "CVE Finding"
    if "weak password" in content.lower() or "default password" in content.lower():
        return "Weak Credential"
    if "open" in content.lower():
        return "Open Port"
    return "fscan Finding"


def _extract_location(content: str) -> str:
    match = _HOST_PORT_REGEX.search(content)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    return content[:120]


def _build_recommendation(severity: str) -> str:
    if severity == "high":
        return "Apply security patches or disable exposed services immediately."
    if severity == "medium":
        return "Review the finding and harden the related service configuration."
    return "Review the exposed surface and close unnecessary ports."


def _parse_fscan_output(lines: Iterable[str]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    seen: set[Tuple[str, str]] = set()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if not (line.startswith("[*]") or line.startswith("[+]") or line.startswith("[!]")):
            continue

        # Remove the leading marker for readability.
        content = line.split("]", 1)[1].strip() if "]" in line else line
        severity = _classify_severity(content)
        vulnerability = _derive_vuln_name(content)
        location = _extract_location(content)
        recommendation = _build_recommendation(severity)

        key = (vulnerability, location)
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            {
                "vulnerability": vulnerability,
                "severity": severity,
                "description": content,
                "location": location,
                "recommendation": recommendation,
            }
        )

    return findings


def run_fscan(
    target: str,
    scan_type: str,
    options: Optional[Dict[str, bool]],
    progress_callback: Optional[Callable[[int, str], None]] = None,
    stop_callback: Optional[Callable[[], bool]] = None,
) -> Dict[str, object]:
    """
    Execute fscan against the provided target.

    Returns a dict with raw output lines and structured findings:
        {
            "command": [...],
            "output": [...],
            "findings": [...],
        }
    Raises ScannerNotFoundError when the executable is missing, ScannerCancelled when stopped,
    or ScannerError for other execution failures.
    """
    executable = _resolve_fscan_path()
    command = _build_command(executable, target, scan_type, options)

    output_dir = current_app.config.get("FSCAN_OUTPUT_DIR", "downloads/scan_reports")
    absolute_output_dir = _ensure_absolute(output_dir)
    os.makedirs(absolute_output_dir, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w+", dir=absolute_output_dir, suffix=".log", delete=False) as temp_file:
        output_file = temp_file.name

    command.extend(["-o", output_file])

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise ScannerNotFoundError(str(exc)) from exc
    except OSError as exc:
        raise ScannerError(f"Failed to start fscan: {exc}") from exc

    collected_output: List[str] = []
    progress = 10
    if progress_callback:
        progress_callback(progress, "fscan started")

    try:
        assert process.stdout is not None  # mypy guard
        for line in process.stdout:
            collected_output.append(line.rstrip("\n"))
            if stop_callback and stop_callback():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise ScannerCancelled()

            progress = min(progress + 3, 85)
            if progress_callback:
                progress_callback(progress, line.strip() or "fscan running")

        exit_code = process.wait()
    except ScannerCancelled:
        raise
    except Exception as exc:
        process.kill()
        raise ScannerError(f"fscan execution failed: {exc}") from exc

    if exit_code != 0:
        raise ScannerError(f"fscan exited with code {exit_code}")

    findings = _parse_fscan_output(collected_output)

    if progress_callback:
        progress_callback(90, "fscan completed, analysing results")

    result = {
        "command": command,
        "output": collected_output,
        "findings": findings,
        "report_path": output_file,
    }

    return result
