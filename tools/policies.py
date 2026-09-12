from __future__ import annotations

import fnmatch
from pathlib import Path

from . import paths


def read_policy_patterns(path: Path) -> list[str]:
    if not path.exists():
        return []
    patterns: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def path_matches_policy(rel_path: str, pattern: str) -> bool:
    normalized_pattern = pattern.strip().lstrip("/").rstrip()
    if not normalized_pattern:
        return False
    if normalized_pattern.endswith("/"):
        prefix = normalized_pattern.rstrip("/")
        return rel_path == prefix or rel_path.startswith(f"{prefix}/")
    return fnmatch.fnmatch(rel_path, normalized_pattern) or fnmatch.fnmatch(Path(rel_path).name, normalized_pattern)


def deploy_path_denied(rel_path: str) -> bool:
    return any(path_matches_policy(rel_path, pattern) for pattern in read_policy_patterns(paths.DENY_FILE))


def path_ignored(rel_path: str) -> bool:
    return any(path_matches_policy(rel_path, pattern) for pattern in read_policy_patterns(paths.IGNORE_FILE))


def forbidden_deploy_path(rel_path: str) -> bool:
    return deploy_path_denied(rel_path)


def rsync_exclude_args() -> list[str]:
    args: list[str] = []
    if paths.IGNORE_FILE.exists():
        args.append(f"--exclude-from={paths.IGNORE_FILE}")
    if paths.DENY_FILE.exists():
        args.append(f"--exclude-from={paths.DENY_FILE}")
    args.extend(["--exclude=.ship", "--exclude=.git"])
    return args


def tree_ignore_pattern() -> str:
    patterns = {".ship", "deploy", ".git", ".github"}
    for pattern in [*read_policy_patterns(paths.IGNORE_FILE), *read_policy_patterns(paths.DENY_FILE)]:
        line = pattern.rstrip("/")
        patterns.add(line.split("/")[-1] if "/" in line else line)
    clean_patterns = sorted(pattern for pattern in patterns if "/" not in pattern)
    return "|".join(clean_patterns)
