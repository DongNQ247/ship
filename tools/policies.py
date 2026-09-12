from __future__ import annotations

import re
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


def gitignore_to_regex(raw_pattern: str) -> tuple[re.Pattern, bool, bool] | None:
    line = raw_pattern.rstrip("\r\n").strip()
    if not line or line.startswith("#"):
        return None

    # Handle negation
    is_negated = False
    if line.startswith("!"):
        is_negated = True
        line = line[1:].strip()
    elif line.startswith(r"\!"):
        line = line[1:]

    # Handle trailing slash (directory only)
    is_dir_only = False
    if line.endswith("/"):
        is_dir_only = True
        line = line[:-1]

    # Anchoring:
    # If starts with /, anchored at root.
    # If contains / in the middle, also anchored at root (relative to root).
    # Otherwise, unanchored (matches anywhere).
    anchored = False
    if line.startswith("/"):
        anchored = True
        line = line[1:]
    elif "/" in line:
        anchored = True

    # Build regex tokens
    res: list[str] = []
    i = 0
    n = len(line)

    while i < n:
        c = line[i]
        if c == "*":
            if i + 1 < n and line[i + 1] == "*":
                # Double asterisk **
                i += 2
                if i < n and line[i] == "/":
                    # Leading or middle **/
                    i += 1
                    res.append("(?:.+/)?")
                else:
                    # Trailing or standalone **
                    res.append(".*")
            else:
                # Single asterisk * -> matches anything except /
                res.append("[^/]*")
                i += 1
        elif c == "?":
            res.append("[^/]")
            i += 1
        elif c == "[":
            # Character class
            j = i + 1
            while j < n and line[j] != "]":
                j += 1
            if j < n:
                res.append(line[i : j + 1])
                i = j + 1
            else:
                res.append(r"\[")
                i += 1
        elif c in r"\.+^$(){}|":
            res.append("\\" + c)
            i += 1
        else:
            res.append(c)
            i += 1

    pattern_body = "".join(res)
    if anchored:
        # Must start from root
        regex_str = f"^{pattern_body}(?:/.*)?$"
    else:
        # Can match at root or in any subfolder
        regex_str = f"^(?:.+/)?{pattern_body}(?:/.*)?$"

    return re.compile(regex_str), is_negated, is_dir_only


def evaluate_policy_file(path: Path, rel_path: str) -> bool:
    patterns = read_policy_patterns(path)
    if not patterns:
        return False
    path_str = rel_path.replace("\\", "/").strip("/")
    if not path_str:
        return False

    matched = False
    for p in patterns:
        compiled = gitignore_to_regex(p)
        if compiled is not None:
            regex, is_negated, _ = compiled
            if regex.search(path_str):
                matched = not is_negated
    return matched


def path_ignored(rel_path: str) -> bool:
    return evaluate_policy_file(paths.IGNORE_FILE, rel_path)


def deploy_path_denied(rel_path: str) -> bool:
    return evaluate_policy_file(paths.DENY_FILE, rel_path)


def forbidden_deploy_path(rel_path: str) -> bool:
    return deploy_path_denied(rel_path)


def path_matches_policy(rel_path: str, pattern: str) -> bool:
    compiled = gitignore_to_regex(pattern)
    if compiled is None:
        return False
    regex, is_negated, _ = compiled
    path_str = rel_path.replace("\\", "/").strip("/")
    if regex.search(path_str):
        return not is_negated
    return False


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
