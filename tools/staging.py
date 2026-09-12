from __future__ import annotations

import os
import tempfile
from pathlib import Path

from . import paths
from .errors import DeployError
from .policies import forbidden_deploy_path, path_ignored
from .ui import NC, YELLOW, print_err


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
    return rel_path


def expand_paths(raw_paths: list[str]) -> list[str]:
    root = paths.ROOT_DIR.resolve(strict=True)
    collected: list[str] = []

    for raw_path in raw_paths:
        rel_path = normalize_path(raw_path)
        target = root / rel_path if rel_path != "." else root

        if not target.exists():
            raise DeployError(f"Path '{raw_path}' does not exist locally. Remove it or create it before add.")

        if target.is_file():
            if forbidden_deploy_path(rel_path):
                raise DeployError(f"Refusing to deploy local secret/control path '{rel_path}'.")
            if path_ignored(rel_path):
                raise DeployError(f"Path '{rel_path}' is ignored by .shipignore. Use '!{rel_path}' in .shipignore to un-ignore.")
            if rel_path not in collected:
                collected.append(rel_path)
        elif target.is_dir():
            if rel_path != "." and forbidden_deploy_path(rel_path):
                raise DeployError(f"Refusing to deploy local secret/control path '{rel_path}'.")

            for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
                current_dir = Path(dirpath).resolve()
                try:
                    rel_dir = current_dir.relative_to(root).as_posix()
                except ValueError:
                    continue

                # Filter subdirectories
                filtered_dirs = []
                for d in dirnames:
                    sub_rel = f"{rel_dir}/{d}" if rel_dir != "." else d
                    if sub_rel in {".git", ".ship"} or forbidden_deploy_path(sub_rel):
                        continue
                    if path_ignored(sub_rel) or path_ignored(f"{sub_rel}/"):
                        continue
                    filtered_dirs.append(d)
                dirnames[:] = filtered_dirs

                for f in sorted(filenames):
                    f_rel = f"{rel_dir}/{f}" if rel_dir != "." else f
                    if forbidden_deploy_path(f_rel):
                        continue
                    if path_ignored(f_rel):
                        continue
                    if f_rel not in collected:
                        collected.append(f_rel)

    return collected


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

    validated: list[str] = []
    skipped: list[str] = []

    for item in items:
        valid_item = validate_staged_item(item)
        if valid_item != "." and path_ignored(valid_item):
            skipped.append(valid_item)
            continue
        validated.append(valid_item)

    if skipped:
        for s in skipped:
            print_err(f"  {YELLOW}Notice:{NC} Skipping '{s}' (matched .shipignore)")

    if not validated:
        raise DeployError("No files remain to push (all staged items are ignored by .shipignore).")

    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
    try:
        for item in validated:
            tmp.write(f"{item}\n")
        tmp.close()
        return tmp, len(validated)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise
