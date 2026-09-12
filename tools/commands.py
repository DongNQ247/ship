from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .config import parse_config_file
from .errors import DeployError
from .paths import (
    ALLOWED_FILE,
    CONFIG_FILE,
    DENY_FILE,
    GUARDRAIL_DIR,
    IGNORE_FILE,
    PROTECTED_FILE,
    REQUIRED_FILES,
    ROOT_DIR,
    SHIP_DIR,
    STAGING_FILE,
    STATE_DIR,
    find_project_root,
    get_context,
)
from .policies import read_policy_patterns, tree_ignore_pattern
from .remote import remote_detailed_precheck, remote_precheck, require_remote_ready
from .shell import rsync_argv, run_command, ssh_exec_script
from .staging import (
    expand_paths,
    expand_paths_detailed,
    normalize_path,
    read_staged_items,
    validate_staged_item,
    validated_staging_tempfile,
    write_staging,
)
from .templates import (
    DEFAULT_ALLOWED,
    DEFAULT_DENY,
    DEFAULT_PROTECTED,
    DEFAULT_SHIPIGNORE,
    DEFAULT_STAGING,
)
from .ui import (
    BOLD,
    CYAN,
    DIM,
    GREEN,
    NC,
    RED,
    YELLOW,
    die,
    format_size,
    print_action,
    print_err,
    print_error,
    print_ignored,
    print_section,
    print_success,
    print_target,
    print_warning,
)


def load_config_or_die():
    try:
        return parse_config_file()
    except DeployError as exc:
        die(exc.message, reason=exc.reason, check=exc.check, run=exc.run)


def require_workspace_files() -> None:
    root = find_project_root()
    if root is None and not (Path.cwd() / ".ship").is_dir():
        raise DeployError(
            "Not a ship repository",
            reason=".ship directory not found in current directory or any parent.",
            run="ship init",
        )
    missing = [path for path in REQUIRED_FILES if not path.exists()]
    if missing:
        missing_text = "\n".join(f"  - {path.relative_to(ROOT_DIR)}" for path in missing)
        raise DeployError(
            "Missing required ship configuration file(s)",
            reason=missing_text,
            run="ship init",
        )


def prompt_input(label: str, default: str = "", required: bool = False) -> str:
    while True:
        prompt_text = f"    {label}"
        if default:
            prompt_text += f" [default: {default}]"
        prompt_text += ": "
        val = input(prompt_text).strip() or default
        if required and not val:
            print(f"    {RED}This field is required. Please provide a value.{NC}")
            continue
        return val


def command_init(args: argparse.Namespace) -> int:
    cwd = Path.cwd().resolve()
    print_section("Ship init")

    ship_dir = cwd / ".ship"
    guardrail_dir = ship_dir / "guardrails"
    state_dir = ship_dir / "state"
    config_file = ship_dir / "config.env"
    shipignore_file = cwd / ".shipignore"

    guardrail_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    if not (guardrail_dir / "allowed").exists():
        (guardrail_dir / "allowed").write_text(DEFAULT_ALLOWED, encoding="utf-8")
        print_success("Created guardrail: .ship/guardrails/allowed")

    if not (guardrail_dir / "deny").exists():
        (guardrail_dir / "deny").write_text(DEFAULT_DENY, encoding="utf-8")
        print_success("Created guardrail: .ship/guardrails/deny")

    if not (guardrail_dir / "protected").exists():
        (guardrail_dir / "protected").write_text(DEFAULT_PROTECTED, encoding="utf-8")
        print_success("Created guardrail: .ship/guardrails/protected")

    if not (state_dir / "files").exists():
        (state_dir / "files").write_text(DEFAULT_STAGING, encoding="utf-8")
        print_success("Created state manifest: .ship/state/files")

    if not shipignore_file.exists():
        shipignore_file.write_text(DEFAULT_SHIPIGNORE, encoding="utf-8")
        print_success("Created ignore rules: .shipignore")

    is_interactive = sys.stdin.isatty() and not getattr(args, "no_input", False)
    reconfigure = not config_file.exists()

    if config_file.exists():
        try:
            config = parse_config_file(config_file)
            print(f"\n  Existing target: {CYAN}{config.server_user}@{config.server_host}:{config.server_port} ({config.remote_dir}){NC}")
            if is_interactive:
                choice = input("  Do you want to reconfigure? [y/N]: ").strip()
                reconfigure = choice.lower() == "y"
            else:
                reconfigure = False
        except Exception:
            reconfigure = True

    if reconfigure:
        if is_interactive:
            print(f"\n{BOLD}Configure Remote Server Connection:{NC}")
            input_host = prompt_input("Server Host / IP", required=True)
            input_port = prompt_input("SSH Port", default="22", required=True)
            input_user = prompt_input("SSH User", default=os.environ.get("USER", ""), required=True)
            input_dir = prompt_input("Remote Directory (e.g. /home/user/project)", required=True)
            config_file.write_text(
                f"# Deployment Server Configuration\nSERVER_HOST={input_host}\nSERVER_PORT={input_port}\nSERVER_USER={input_user}\nREMOTE_DIR={input_dir}\n",
                encoding="utf-8",
            )
            print_success("Saved config to: .ship/config.env")
        else:
            if not config_file.exists():
                config_file.write_text(
                    "# Deployment Server Configuration\nSERVER_HOST=\nSERVER_PORT=22\nSERVER_USER=\nREMOTE_DIR=\n",
                    encoding="utf-8",
                )
                print_warning("Created empty config template at: .ship/config.env", reason="Fill in server details before running 'ship preflight' or 'ship push'.")

    try:
        config = parse_config_file(config_file)
    except DeployError as exc:
        print_warning(exc.message)
        print(f"\n{GREEN}{BOLD}Initialized empty ship repository in {ship_dir}.{NC}")
        return 0

    if is_interactive:
        try:
            out = remote_precheck(config)
            if "===SSH_OK===" in out:
                print_success("SSH connection established successfully.")
            else:
                print_warning("SSH test returned unexpected output", reason=out)
        except subprocess.CalledProcessError as exc:
            print_warning(f"Could not connect via SSH to {config.server_host}:{config.server_port}.", reason=exc.stdout or "")
            print(f"\n{GREEN}{BOLD}Initialization completed.{NC} (Verify SSH connectivity later with 'ship preflight')")
            return 0

    print(f"\n{GREEN}{BOLD}Initialized ship repository in {ship_dir}. You are ready to ship!{NC}")
    return 0


def command_preflight(_args: argparse.Namespace) -> int:
    config = load_config_or_die()
    print_target(config.server_user, config.server_host, config.remote_dir, config.server_port)

    # 1. Local checks
    print_section("Local")
    for cmd in ("ssh", "rsync", "python3"):
        found = shutil.which(cmd)
        if not found:
            print_error(f"Missing local tool: {cmd}", reason=f"{cmd} executable is not in PATH.", check=f"Install {cmd} on local system.")
            return 1
        print_success(cmd)

    if CONFIG_FILE.exists():
        print_success(".ship/config.env")
    else:
        print_error(".ship/config.env missing", run="ship init")
        return 1

    if IGNORE_FILE.exists():
        print_success(".shipignore")

    print_success("Guardrails (allowed, deny, protected)")

    # 2. SSH checks & 3. Remote checks
    print_section("SSH")
    try:
        check_res = remote_detailed_precheck(config)
    except subprocess.CalledProcessError as exc:
        print_error(
            "Connection failed",
            reason=f"Could not connect to {config.server_user}@{config.server_host}:{config.server_port}.\n{exc.stdout or ''}",
            check="- SERVER_HOST\n  - SERVER_PORT\n  - SSH credentials",
        )
        return 1
    except Exception as exc:
        print_error("Connection failed", reason=str(exc))
        return 1

    if not check_res.get("ssh_ok"):
        print_error(
            "Connection failed",
            reason=f"Could not connect to {config.server_user}@{config.server_host}:{config.server_port}.",
            check="- SERVER_HOST\n  - SERVER_PORT\n  - SSH credentials",
        )
        return 1

    print_success("Connection")
    print_success("Authentication")

    print_section("Remote")
    if check_res.get("dir_exists"):
        print_success(f"Remote directory ({config.remote_dir})")
    else:
        print_success(f"Remote directory (will be created automatically)")

    if check_res.get("write_ok"):
        print_success("Write permission")
    else:
        print_error(
            "Write permission denied",
            reason=f"{config.server_user}@{config.server_host} cannot write to {config.remote_dir}.",
            check="Check remote directory permissions or SERVER_USER.",
        )
        return 1

    if check_res.get("rsync_ok"):
        print_success("rsync")
    else:
        print_error(
            "Remote rsync missing",
            reason=f"rsync is not installed on remote server {config.server_host}.",
            check="Install rsync on the remote server.",
        )
        return 1

    print_section("Result")
    print_success("Preflight passed.")
    return 0


def command_add(args: argparse.Namespace) -> int:
    existing_list = read_staged_items()
    existing_set = set(existing_list)
    result = expand_paths_detailed(args.paths)

    new_added: list[str] = []
    for f in result.added:
        if f not in existing_set:
            existing_list.append(f)
            existing_set.add(f)
            new_added.append(f)

    if new_added:
        write_staging(existing_list)
        print_section("Ship staging")
        print_success(f"Added       {len(new_added)} file(s)")
        if result.ignored:
            print_ignored(f"Ignored     {len(result.ignored)} file(s)")
        if result.denied:
            print_warning(f"Denied      {len(result.denied)} file(s)")
        print(f"\nTotal staged: {len(existing_list)} file(s)")
        print(f"\nRun `ship status` to review.\nRun `ship push` to upload.")
    elif not result.added:
        print(f"{YELLOW}No matching files found to stage.{NC}")
    else:
        print(f"No new files added.\n\n{len(existing_list)} file(s) are already staged.")

    return 0


def command_reset(args: argparse.Namespace) -> int:
    if not args.paths:
        existing = read_staged_items()
        if not existing:
            print("Nothing is staged.")
            return 0
        write_staging([])
        print(f"Staging reset.\n\n{len(existing)} file(s) removed from staging.")
        return 0

    existing = read_staged_items()
    removed_items: list[str] = []
    not_staged_items: list[str] = []

    for raw_path in args.paths:
        rel_path = normalize_path(raw_path)
        matching = [item for item in existing if item == rel_path or item.startswith(f"{rel_path}/")]
        if matching:
            existing = [item for item in existing if item not in matching]
            removed_items.extend(matching)
        else:
            not_staged_items.append(raw_path)

    if removed_items:
        write_staging(existing)
        print("Removed from staging:\n")
        for item in removed_items:
            print(f"  {item}")
        print(f"\nRemaining staged: {len(existing)} file(s)")

    if not_staged_items:
        for p in not_staged_items:
            print(f"{p} is not staged.")

    return 0


def command_status(args: argparse.Namespace) -> int:
    config = load_config_or_die()
    print_target(config.server_user, config.server_host, config.remote_dir, config.server_port)
    print()

    items = read_staged_items()
    if not items:
        print("Nothing is staged.\n\nRun:\n\n  ship add .\n\nto select files for upload.")
        return 0

    print_section("Staged")
    for item in items:
        file_path = ROOT_DIR / item
        if file_path.exists() and file_path.is_file():
            size_str = format_size(file_path.stat().st_size)
            print_action("UPLOAD", item, size_str)
        elif item == ".":
            print_action("UPLOAD", ".", "")
        else:
            print_action("MISSING", item, "(missing locally)")

    # Show Ignored summary if present
    if IGNORE_FILE.exists():
        patterns = read_policy_patterns(IGNORE_FILE)
        if patterns:
            print()
            print_section("Ignored (.shipignore)")
            for p in patterns[:6]:
                print_action("IGNORE", p)
            if len(patterns) > 6:
                print(f"  {DIM}... and {len(patterns) - 6} more rule(s){NC}")

    print()
    print("─" * 32)
    print(f"Total staged: {len(items)} file(s)")
    print(f"\nReady to ship.")
    print(f"Run `ship push --dry-run` to preview the transfer.")
    print(f"Run `ship push` to upload.")
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    config = load_config_or_die()
    print(f"{BOLD}Remote{NC}\n{CYAN}→{NC} {config.server_user}@{config.server_host}:{config.remote_dir}\n")

    script = """
remote_dir="$1"
tree_level="$2"

if [ ! -d "$remote_dir" ]; then
    echo "__REMOTE_NO_DIR__"
    exit 0
fi

echo "__SECTION_TREE__"
if command -v tree >/dev/null 2>&1; then
    tree -L "$tree_level" -a "$remote_dir"
else
    find "$remote_dir" -maxdepth "$tree_level" -print
fi
"""
    result = ssh_exec_script(config, script, config.remote_dir, str(args.tree_level), capture=True)
    out = result.stdout or ""
    if "__REMOTE_NO_DIR__" in out:
        print(f"{YELLOW}Remote directory does not exist on server:{NC}\n  {config.remote_dir}")
        return 0
    for line in out.splitlines():
        if line != "__SECTION_TREE__":
            print(line)
    return 0


def command_push(args: argparse.Namespace) -> int:
    config = load_config_or_die()
    tmp, count = validated_staging_tempfile()
    tmp_path = Path(tmp.name)
    try:
        print_target(config.server_user, config.server_host, config.remote_dir, config.server_port)
        opts = ["-azn" if args.dry_run else "-az"]
        if args.verbose:
            opts = ["-azvn" if args.dry_run else "-azv", "--progress"]
        opts.append("-r")

        if args.dry_run:
            print(f"\nWould transfer:\n")
            items = read_staged_items()
            for item in items:
                print(f"  {item}")
            print("\n" + "─" * 32)
            # Execute native rsync dry run quietly or verbosely
            run_command(rsync_argv(config, opts, [f"{ROOT_DIR}/"], files_from=tmp_path))
            print_success("No changes made.")
        else:
            ssh_exec_script(config, 'mkdir -p "$1"', config.remote_dir)
            print(f"Syncing staged items ({count} declared path(s))... ", end="", flush=True)
            run_command(rsync_argv(config, opts, [f"{ROOT_DIR}/"], files_from=tmp_path))
            print(f"{GREEN}done{NC}")
            print("\n" + "─" * 32)
            print_success("Ship complete")
            print(f"\nUploaded: {count} file(s)")
        return 0
    finally:
        tmp_path.unlink(missing_ok=True)


def command_clean(args: argparse.Namespace) -> int:
    config = load_config_or_die()
    target_str = f"{config.server_user}@{config.server_host}:{config.remote_dir}"

    if args.dry_run:
        print(f"{BOLD}Dry run{NC}\n\nWould remove:\n\n  {target_str}\n\n" + "─" * 32)
        print_success("No changes made.")
        return 0

    print(f"\n{YELLOW}{BOLD}⚠ Remote cleanup{NC}\n\nThis will delete:\n\n  {CYAN}{target_str}{NC}\n\nAll files inside this remote directory will be removed.\n")
    if not args.yes:
        choice = input("Continue? [y/N]: ").strip().lower()
        if choice != "y":
            print(f"{CYAN}Operation cancelled.{NC}")
            return 0

    script = """
remote_dir="$1"
if [ -d "$remote_dir" ]; then
    rm -rf "$remote_dir"
fi
"""
    require_remote_ready(config)
    ssh_exec_script(config, script, config.remote_dir)
    print_success("Remote directory cleaned.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ship", description="Git-like file deployment CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Initialize a new .ship repository in current directory")
    p.add_argument("--no-input", action="store_true", help="Do not prompt interactively, create template")
    p.set_defaults(func=command_init)

    p = sub.add_parser("preflight", help="Test local environment and remote SSH connectivity")
    p.set_defaults(func=command_preflight)

    p = sub.add_parser("add", help="Add files or directories to staging")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=command_add)

    p = sub.add_parser("reset", help="Reset staging area or unstage specific files/directories")
    p.add_argument("paths", nargs="*")
    p.set_defaults(func=command_reset)

    p = sub.add_parser("status", help="Show workspace tree and currently staged items")
    p.add_argument("depth_pos", nargs="?", type=int)
    p.add_argument("-L", "--depth", type=int, default=None)
    p.set_defaults(func=command_status)

    p = sub.add_parser("inspect", help="Inspect directory structure on remote server")
    p.set_defaults(mode="tree")
    p.add_argument("tree_level", nargs="?", type=int, default=2)
    p.set_defaults(func=command_inspect)

    p = sub.add_parser("push", help="Sync staged files to remote server via SSH/rsync")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=command_push)

    p = sub.add_parser("clean", help="Clean remote directory on server")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=command_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if argv and argv[0] in {"help", "-h", "--help"}:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    try:
        if args.command != "init":
            require_workspace_files()
        return int(args.func(args))
    except DeployError as exc:
        print_error(exc.message, reason=exc.reason, check=exc.check, run=exc.run)
        return 1
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout, end="")
        print_error(f"Command failed: {' '.join(shlex.quote(part) for part in exc.cmd)}")
        return exc.returncode or 1
