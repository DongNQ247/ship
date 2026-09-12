from __future__ import annotations

import subprocess

from .config import Config
from .errors import DeployError
from .shell import ssh_exec_script


def remote_precheck(config: Config) -> str:
    script = """
remote_dir="$1"
echo "===SSH_OK==="
if [ -d "$remote_dir" ]; then echo "DIR_EXISTS"; else echo "DIR_MISSING"; fi
"""
    result = ssh_exec_script(config, script, config.remote_dir, capture=True)
    return result.stdout or ""


def remote_detailed_precheck(config: Config) -> dict[str, bool]:
    script = """
remote_dir="$1"
echo "===SSH_OK==="
if command -v rsync >/dev/null 2>&1; then echo "===RSYNC_OK==="; else echo "===RSYNC_MISSING==="; fi

if [ -d "$remote_dir" ]; then
    echo "===DIR_EXISTS==="
    if [ -w "$remote_dir" ]; then echo "===WRITE_OK==="; else echo "===WRITE_DENIED==="; fi
else
    echo "===DIR_MISSING==="
    parent=$(dirname "$remote_dir")
    if [ -d "$parent" ] && [ -w "$parent" ]; then echo "===WRITE_OK==="; else echo "===PARENT_WRITE_DENIED==="; fi
fi
"""
    result = ssh_exec_script(config, script, config.remote_dir, capture=True)
    out = result.stdout or ""
    return {
        "ssh_ok": "===SSH_OK===" in out,
        "rsync_ok": "===RSYNC_OK===" in out,
        "dir_exists": "===DIR_EXISTS===" in out,
        "write_ok": "===WRITE_OK===" in out,
    }


def require_remote_ready(config: Config) -> None:
    try:
        out = remote_precheck(config)
    except subprocess.CalledProcessError as exc:
        raise DeployError(
            f"SSH Connection failed to {config.server_host}:{config.server_port}",
            reason=f"Subprocess error: {exc.stdout or ''}",
            check="Verify SERVER_HOST, SERVER_PORT, and SSH keys/credentials.",
        ) from exc
    if "===SSH_OK===" not in out:
        raise DeployError(
            f"SSH Connection failed to {config.server_host}:{config.server_port}",
            reason=out,
            check="Verify SERVER_HOST, SERVER_PORT, and SSH keys/credentials.",
        )
