"""Offline Docker/Podman fixtures shared by optional discovery and strict CI.

The digest is Docker's official bash:3.2 index (Bash 3.2.57 / Alpine BusyBox).
This is not native macOS/BSD coverage. See docs/bash32-portability.md for provenance.
"""
import hashlib
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

BASH32_IMAGE = "docker.io/library/bash@sha256:0fd7cb8499c63a3c9345e7088a9cd83bb69f6e895e83833859aff838a0312091"
JQ_SHA256 = "5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5"
JQ_URL = "https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64"


def prepare(runtime, directory):
    """Network is allowed only during host-side preparation, never in fixtures."""
    directory.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(JQ_URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != JQ_SHA256:
        raise RuntimeError("upstream jq checksum mismatch")
    jq = directory / "jq"
    jq.write_bytes(data)
    jq.chmod(0o755)
    subprocess.run([runtime, "pull", "--platform=linux/amd64", BASH32_IMAGE], check=True, timeout=180)
    print(f"Prepared {BASH32_IMAGE} and jq 1.7.1 ({JQ_SHA256})")


def container_runtime():
    requested = os.environ.get("BASH32_CONTAINER_RUNTIME")
    for name in ([requested] if requested else ["podman", "docker"]):
        if name not in ("podman", "docker"):
            continue
        executable = shutil.which(name)
        if not executable:
            continue
        try:
            probe = subprocess.run([executable, "image", "inspect", BASH32_IMAGE],
                                   capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            return executable
    return None


def static_jq():
    path = os.environ.get("BASH32_STATIC_JQ", "")
    if not path or not Path(path).is_file():
        return None
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != JQ_SHA256:
        return None
    return path


def run_container(tmp, target, command, *, readonly=False, payload=None):
    runtime = container_runtime()
    if not runtime:
        raise RuntimeError("Bash 3.2 needs Docker/Podman with the pinned image pulled")
    # :Z labels only the disposable copy; never relabel the working tree.
    options = "ro,Z" if readonly else "Z"
    return subprocess.run(
        [runtime, "run", "--rm", "--pull=never", "--platform=linux/amd64",
         "-i", "--network=none", "-v", f"{tmp}:{target}:{options}",
         BASH32_IMAGE, "bash", "-c",
         'set -euo pipefail; test "${BASH_VERSINFO[0]}.${BASH_VERSINFO[1]}" = 3.2; '
         'sed --help 2>&1 | grep BusyBox >/dev/null; ' + command],
        input=payload, capture_output=True, text=True, timeout=180)
