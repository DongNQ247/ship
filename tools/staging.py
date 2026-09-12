from __future__ import annotations

import tempfile
from pathlib import Path

from . import paths
from .errors import DeployError
from .policies import forbidden_deploy_path, path_ignored


def normalize_path(raw_path: str) -> str:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw_path):
        raise DeployError("Path contains control characters.")

    real_root = paths.ROOT_DIR.resolve(strict=True)
    cwd = Path.cwd().resolve()

    if raw_path in {".", "./", "all", "-A", "*"}:
        if cwd == real_root:
            return "."
        try:
            rel = cwd.relative_to(real_root)
            return rel.as_posix()
        except ValueError:
            return "."

    target = Path(raw_path)
    if not target.is_absolute():
        target = (cwd / target).resolve(strict=False)
    else:
        target = target.resolve(strict=False)

    try:
        rel = target.relative_to(real_root)
    except ValueError as exc:
        raise DeployError(f"Path '{raw_path}' resolves outside project root.") from exc

    rel_text = rel.as_posix()
    return "." if rel_text == "." else rel_text


def validate_staged_item(item: str) -> str:
    rel_path = normalize_path(item)
    if rel_path == ".":
        return rel_path
    if not (paths.ROOT_DIR / rel_path).exists():
        raise DeployError(f"Staged path '{item}' does not exist locally. Remove it or create it before push.")
    if forbidden_deploy_path(rel_path):
        raise DeployError(f"Refusing to deploy local secret/control path '{rel_path}'.")
    if path_ignored(rel_path):
        raise DeployError(f"Path '{rel_path}' is ignored by .shipignore.")
    return rel_path


def read_staged_items() -> list[str]:
    if not paths.STAGING_FILE.exists():
        raise DeployError(f"Required deploy state file not found: {paths.STAGING_FILE}")
    items: list[str] = []
    for line in paths.STAGING_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            items.append(stripped)
    return items


def write_staging(items: list[str]) -> None:
    if not paths.STAGING_FILE.exists():
        raise DeployError(f"Required deploy state file not found: {paths.STAGING_FILE}")
    header_lines = []
    for line in paths.STAGING_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            break
        header_lines.append(line)
    header = "\n".join(header_lines).rstrip("\n")
    body = "\n".join(items)
    text = f"{header}\n" if header else ""
    if body:
        text += f"{body}\n"
    paths.STAGING_FILE.write_text(text, encoding="utf-8")


def validated_staging_tempfile() -> tuple[tempfile.NamedTemporaryFile, int]:
    items = read_staged_items()
    if not items:
        raise DeployError("No files are currently staged for push.")
    validated = [validate_staged_item(item) for item in items]
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
    try:
        for item in validated:
            tmp.write(f"{item}\n")
        tmp.close()
        return tmp, len(validated)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise
