from __future__ import annotations

import sys

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"

# Action & Status symbols
ICON_SUCCESS = "✓"
ICON_WARNING = "⚠"
ICON_ERROR = "✗"
ICON_IGNORED = "⊘"
ICON_ARROW = "→"


def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        kb = num_bytes / 1024
        return f"{kb:.1f} KB" if kb < 10 else f"{int(round(kb))} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        mb = num_bytes / (1024 * 1024)
        return f"{mb:.1f} MB"
    else:
        gb = num_bytes / (1024 * 1024 * 1024)
        return f"{gb:.2f} GB"


def print_target(user: str, host: str, remote_dir: str, port: int | str = 22) -> None:
    port_str = f":{port}" if str(port) not in {"22", ""} else ""
    print(f"{BOLD}Ship{NC} {CYAN}→{NC} {user}@{host}{port_str}:{remote_dir}")


def print_section(title: str, width: int = 32) -> None:
    print(f"{BOLD}{title}{NC}")
    print("─" * width)


def print_success(message: str) -> None:
    print(f"{GREEN}{ICON_SUCCESS}{NC} {message}")


def print_warning(message: str, reason: str = "") -> None:
    print(f"{YELLOW}{ICON_WARNING}{NC} {message}")
    if reason:
        print(f"  Reason: {reason}")


def print_ignored(message: str, reason: str = "") -> None:
    print(f"{CYAN}{ICON_IGNORED}{NC} {message}")
    if reason:
        print(f"  Reason: {reason}")


def print_error(message: str, reason: str = "", check: str = "", run: str = "") -> None:
    print(f"{RED}{ICON_ERROR} {message}{NC}", file=sys.stderr)
    if reason:
        print(f"\nReason:\n  {reason}", file=sys.stderr)
    if check:
        print(f"\nCheck:\n  {check}", file=sys.stderr)
    if run:
        print(f"\nRun:\n  {run}", file=sys.stderr)


def print_action(action: str, target: str, detail: str = "") -> None:
    color = GREEN if action in {"UPLOAD", "ADD"} else YELLOW if action in {"UPDATE", "DENY"} else CYAN if action in {"IGNORE", "SKIP"} else NC
    detail_str = f"{DIM}{detail}{NC}" if detail else ""
    print(f"{color}{action:<8}{NC} {target:<40} {detail_str}")


def print_err(message: str) -> None:
    print(message, file=sys.stderr)


def die(message: str, code: int = 1, reason: str = "", check: str = "", run: str = "") -> None:
    print_error(message, reason=reason, check=check, run=run)
    raise SystemExit(code)
