#!/usr/bin/env python
"""FitTrack Admin frontend pre-flight check — verify dist/, port, and vite preview.

Usage:
    python scripts/check_fittrack_admin.py          # human-readable output
    python scripts/check_fittrack_admin.py --json   # JSON output

Exit code 0 when all three checks pass; 1 when any check fails.
"""

import sys
import os
import json
import time
import signal
import socket
import subprocess

ADMIN_DIR = "D:/FitnessManagement/admin"
DIST_INDEX = os.path.join(ADMIN_DIR, "dist", "index.html")
PORT = 5190
PREVIEW_URL = f"http://localhost:{PORT}"
WAIT_SECONDS = 3


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────


def _find_qt_windows() -> list[str]:
    """Return list of processes/owners for the port using netstat (Windows)."""
    try:
        r = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace"
        )
    except Exception:
        return []

    pids: set[str] = set()
    for line in r.stdout.splitlines():
        if f":{PORT}" in line and ("LISTENING" in line or "ESTABLISHED" in line):
            parts = line.split()
            if parts:
                pids.add(parts[-1])

    if not pids:
        return []

    result: list[str] = []
    for pid in pids:
        try:
            r2 = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace"
            )
            for line2 in r2.stdout.splitlines():
                line2 = line2.strip().strip('"')
                parts2 = line2.split('","')
                if len(parts2) >= 2:
                    result.append(f"{parts2[0]} (PID {pid})")
        except Exception:
            result.append(f"PID {pid}")
    return result


def _is_port_free(port: int) -> bool:
    """Return True if nothing is listening on the given TCP port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _run_checks() -> dict:
    """Execute all three checks and return a structured result dict."""
    result: dict = {
        "dist": {"status": "PASS", "detail": ""},
        "port": {"status": "FREE", "detail": ""},
        "preview": {"status": "STARTED", "detail": ""},
        "verdict": "READY",
    }

    # ── CHECK 1: dist/index.html exists ──
    if os.path.isfile(DIST_INDEX):
        result["dist"]["status"] = "PASS"
        result["dist"]["detail"] = DIST_INDEX
    else:
        result["dist"]["status"] = "MISSING"
        result["dist"]["detail"] = f"File not found: {DIST_INDEX}"
        result["dist"]["suggested_fix"] = f"cd {ADMIN_DIR} && npm run build"
        result["verdict"] = "BLOCKED"

    # ── CHECK 2: port 5190 availability ──
    if _is_port_free(PORT):
        result["port"]["status"] = "FREE"
        result["port"]["detail"] = f"Port {PORT} is free"
    else:
        result["port"]["status"] = "IN_USE"
        owners = _find_qt_windows()
        if owners:
            result["port"]["detail"] = f"Port {PORT} is in use by: " + ", ".join(owners)
        else:
            result["port"]["detail"] = f"Port {PORT} is in use (could not determine owner)"
        result["verdict"] = "BLOCKED"

    # ── CHECK 3: start vite preview, curl, kill ──
    # Check npx availability first
    npx_ok = False
    try:
        subprocess.run(["npx", "--version"], capture_output=True, text=True,
                       timeout=15, shell=True)
        npx_ok = True
    except Exception:
        pass

    if not npx_ok:
        result["preview"]["status"] = "FAILED"
        result["preview"]["detail"] = "npx is not available or not in PATH"
        result["verdict"] = "BLOCKED"
        return result

    proc = None
    try:
        proc = subprocess.Popen(
            ["npx", "vite", "preview", "--port", str(PORT)],
            cwd=ADMIN_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        time.sleep(WAIT_SECONDS)

        # curl check
        curl_ok = False
        try:
            r = subprocess.run(
                ["curl", "-s", "-o", os.devnull, "-w", "%{http_code}", PREVIEW_URL],
                capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace"
            )
            curl_ok = (r.stdout.strip() == "200")
        except Exception:
            pass

        if curl_ok:
            result["preview"]["status"] = "STARTED"
            result["preview"]["detail"] = f"vite preview responded 200 at {PREVIEW_URL}"
        else:
            result["preview"]["status"] = "FAILED"
            result["preview"]["detail"] = f"vite preview started but {PREVIEW_URL} did not return 200"
            result["verdict"] = "BLOCKED"

    except Exception as e:
        result["preview"]["status"] = "FAILED"
        result["preview"]["detail"] = f"Failed to start vite preview: {e}"
        result["verdict"] = "BLOCKED"
    finally:
        if proc is not None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                pass

    return result


def _format_text(result: dict) -> str:
    lines = []
    lines.append("=" * 50)
    lines.append("  FitTrack Admin Frontend Pre-flight Check")
    lines.append("=" * 50)
    lines.append("")

    # Check 1
    d = result["dist"]
    icon = "[OK]" if d["status"] == "PASS" else "[X]"
    lines.append(f"  {icon} CHECK 1: dist/index.html ................ {d['status']}")
    lines.append(f"         {d['detail']}")
    if d["status"] == "MISSING" and "suggested_fix" in d:
        lines.append(f"         Suggested fix: {d['suggested_fix']}")

    # Check 2
    p = result["port"]
    icon = "[OK]" if p["status"] == "FREE" else "[X]"
    lines.append(f"  {icon} CHECK 2: port {PORT} availability ........... {p['status']}")
    lines.append(f"         {p['detail']}")

    # Check 3
    pr = result["preview"]
    icon = "[OK]" if pr["status"] == "STARTED" else "[X]"
    lines.append(f"  {icon} CHECK 3: vite preview on port {PORT} ........ {pr['status']}")
    lines.append(f"         {pr['detail']}")

    lines.append("")
    verdict_mark = "READY" if result["verdict"] == "READY" else "BLOCKED"
    lines.append(f"  Runtime Verdict: {verdict_mark}")
    lines.append("=" * 50)
    return "\n".join(lines)


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────


def main():
    json_mode = "--json" in sys.argv

    result = _run_checks()

    if json_mode:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(_format_text(result))

    sys.exit(0 if result["verdict"] == "READY" else 1)


if __name__ == "__main__":
    main()
