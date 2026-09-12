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


def require_remote_ready(config: Config) -> None:
    try:
        out = remote_precheck(config)
    except subprocess.CalledProcessError as exc:
        raise DeployError(f"SSH Connection failed to {config.server_host}:{config.server_port}\n{exc.stdout or ''}") from exc
    if "===SSH_OK===" not in out:
        raise DeployError(f"SSH Connection failed to {config.server_host}:{config.server_port}\n{out}")
