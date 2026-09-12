from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .errors import DeployError


@dataclass(frozen=True)
class Config:
    server_host: str
    server_port: int
    server_user: str
    remote_dir: str

    @property
    def ssh_target(self) -> str:
        return f"{self.server_user}@{self.server_host}"


def parse_config_file(path: Path | None = None) -> Config:
    config_path = path or paths.CONFIG_FILE
    if not config_path.exists():
        raise DeployError(f"Config file not found at {config_path}. Run: ship init")

    values: dict[str, str] = {}
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values["".join(key.split())] = val.strip().strip('"').strip("'")

    required = ("SERVER_HOST", "SERVER_PORT", "SERVER_USER", "REMOTE_DIR")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise DeployError(f"Incomplete config in {config_path}. Missing: {', '.join(missing)}")

    validate_server_host(values["SERVER_HOST"])
    validate_server_user(values["SERVER_USER"])
    validate_remote_dir(values["REMOTE_DIR"])
    port = validate_server_port(values["SERVER_PORT"], config_path)

    return Config(
        server_host=values["SERVER_HOST"],
        server_port=port,
        server_user=values["SERVER_USER"],
        remote_dir=values["REMOTE_DIR"],
    )


def validate_server_host(host: str) -> None:
    if not host:
        raise DeployError("SERVER_HOST is empty in config.")
    if (
        re.search(r"[^a-zA-Z0-9_.-]", host)
        or host.startswith(".")
        or ".." in host
        or host.endswith("-.")
        or ".-" in host
    ):
        raise DeployError(f"Invalid SERVER_HOST '{host}' (illegal hostname/IP characters).")


def validate_server_user(user: str) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", user):
        raise DeployError(f"Invalid SERVER_USER '{user}' (illegal characters).")


def validate_server_port(port_raw: str, path: Path) -> int:
    if not port_raw.isdigit():
        raise DeployError(f"Invalid SERVER_PORT '{port_raw}' in {path} (must be 1..65535).")
    port = int(port_raw)
    if port < 1 or port > 65535:
        raise DeployError(f"Invalid SERVER_PORT '{port_raw}' in {path} (must be 1..65535).")
    return port


def validate_remote_dir(remote_dir: str) -> None:
    if not remote_dir:
        raise DeployError("REMOTE_DIR is empty in config.")
    if re.search(r"[^a-zA-Z0-9_./-]", remote_dir):
        raise DeployError(f"REMOTE_DIR contains illegal shell characters: '{remote_dir}'")
    if ".." in remote_dir:
        raise DeployError(f"REMOTE_DIR contains '..' path traversal: '{remote_dir}'")
    if not allowed_remote_path(remote_dir):
        raise DeployError(f"REMOTE_DIR is not allowed by {paths.ALLOWED_FILE}: '{remote_dir}'")
    if protected_remote_path(remote_dir):
        raise DeployError(f"Refusing dangerous system REMOTE_DIR: '{remote_dir}'")


def read_allowed_remote_paths(path: Path | None = None) -> list[str]:
    target_path = path or paths.ALLOWED_FILE
    if not target_path.exists():
        raise DeployError(f"Required remote path guardrail file not found: {target_path}")
    patterns: list[str] = []
    for raw_line in target_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def allowed_remote_path(remote_dir: str) -> bool:
    return any(re.fullmatch(pattern, remote_dir) for pattern in read_allowed_remote_paths())


def read_protected_remote_paths(path: Path | None = None) -> list[str]:
    target_path = path or paths.PROTECTED_FILE
    if not target_path.exists():
        raise DeployError(f"Required remote path guardrail file not found: {target_path}")
    patterns: list[str] = []
    for raw_line in target_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def protected_remote_path(remote_dir: str) -> bool:
    for pattern in read_protected_remote_paths():
        if pattern.endswith("*") and remote_dir.startswith(pattern[:-1]):
            return True
        if remote_dir == pattern:
            return True
    return False
