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
from .policies import tree_ignore_pattern
from .remote import remote_precheck, require_remote_ready
from .shell import rsync_argv, run_command, ssh_exec_script
from .staging import expand_paths, normalize_path, read_staged_items, validate_staged_item, validated_staging_tempfile, write_staging
from .templates import (
    DEFAULT_ALLOWED,
    DEFAULT_DENY,
    DEFAULT_PROTECTED,
    DEFAULT_SHIPIGNORE,
    DEFAULT_STAGING,
)
from .ui import BOLD, CYAN, GREEN, NC, RED, YELLOW, die, print_err


def load_config_or_die():
    try:
        return parse_config_file()
    except DeployError as exc:
        die(f"{RED}Error:{NC} {exc}")


def require_workspace_files() -> None:
    root = find_project_root()
    if root is None and not (Path.cwd() / ".ship").is_dir():
        raise DeployError(
            f"Not a ship repository (or any parent directory): .ship directory not found.\n"
            f"Run '{BOLD}ship init{NC}' to initialize a new ship repository."
        )
    missing = [path for path in REQUIRED_FILES if not path.exists()]
    if missing:
        missing_text = "\n".join(f"  - {path.relative_to(ROOT_DIR)}" for path in missing)
        raise DeployError(f"Missing required ship configuration file(s):\n{missing_text}\nRun '{BOLD}ship init{NC}' to restore default files.")


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
    print(f"{BOLD}[Init] Initializing ship deployment repository at {CYAN}{cwd}{NC}...")

    ship_dir = cwd / ".ship"
    guardrail_dir = ship_dir / "guardrails"
    state_dir = ship_dir / "state"
    config_file = ship_dir / "config.env"
    shipignore_file = cwd / ".shipignore"

    # Create directories
    guardrail_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    # Initialize templates
    if not (guardrail_dir / "allowed").exists():
        (guardrail_dir / "allowed").write_text(DEFAULT_ALLOWED, encoding="utf-8")
        print(f"  {GREEN}Created guardrail:{NC} .ship/guardrails/allowed")

    if not (guardrail_dir / "deny").exists():
        (guardrail_dir / "deny").write_text(DEFAULT_DENY, encoding="utf-8")
        print(f"  {GREEN}Created guardrail:{NC} .ship/guardrails/deny")

    if not (guardrail_dir / "protected").exists():
        (guardrail_dir / "protected").write_text(DEFAULT_PROTECTED, encoding="utf-8")
        print(f"  {GREEN}Created guardrail:{NC} .ship/guardrails/protected")

    if not (state_dir / "files").exists():
        (state_dir / "files").write_text(DEFAULT_STAGING, encoding="utf-8")
        print(f"  {GREEN}Created state manifest:{NC} .ship/state/files")

    if not shipignore_file.exists():
        shipignore_file.write_text(DEFAULT_SHIPIGNORE, encoding="utf-8")
        print(f"  {GREEN}Created ignore rules:{NC} .shipignore")

    is_interactive = sys.stdin.isatty() and not getattr(args, "no_input", False)
    reconfigure = not config_file.exists()

    if config_file.exists():
        try:
            config = parse_config_file(config_file)
            print(f"  Existing config: {CYAN}{config.server_user}@{config.server_host}:{config.server_port} ({config.remote_dir}){NC}")
            if is_interactive:
                choice = input("    Do you want to reconfigure? [y/N]: ").strip()
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
            print(f"  {GREEN}Saved config to:{NC} .ship/config.env")
        else:
            # Non-interactive: create template without arbitrary fallback values
            if not config_file.exists():
                config_file.write_text(
                    "# Deployment Server Configuration\nSERVER_HOST=\nSERVER_PORT=22\nSERVER_USER=\nREMOTE_DIR=\n",
                    encoding="utf-8",
                )
                print(f"  {YELLOW}Created empty config template at:{NC} .ship/config.env")
                print(f"  {YELLOW}Please fill in your server details before running 'ship preflight' or 'ship push'.{NC}")

    # Check if config is complete
    try:
        config = parse_config_file(config_file)
    except DeployError as exc:
        print(f"  {YELLOW}Notice:{NC} {exc}")
        print(f"{GREEN}{BOLD}Initialized empty ship repository in {ship_dir}.{NC}")
        return 0

    print(f"  {GREEN}Repository structure verified:{NC} .ship/ (config, guardrails, state) & .shipignore")

    if is_interactive:
        try:
            out = remote_precheck(config)
            if "===SSH_OK===" in out:
                print(f"  {GREEN}SSH connection established successfully.{NC}")
            else:
                print_err(f"{YELLOW}Warning: SSH test check returned unexpected output:{NC}\n{out}")
        except subprocess.CalledProcessError as exc:
            print_err(f"{YELLOW}Warning: Could not connect via SSH to {config.server_host}:{config.server_port}.{NC}")
            if exc.stdout:
                print_err(exc.stdout)
            print(f"{GREEN}{BOLD}Initialization completed.{NC} (Verify SSH connectivity later with 'ship preflight')")
            return 0

    print(f"{GREEN}{BOLD}Initialized ship repository in {ship_dir}. You are ready to ship!{NC}")
    return 0


def command_preflight(_args: argparse.Namespace) -> int:
    config = load_config_or_die()
    print(f"{BOLD}Running pre-flight verification...{NC}")

    for cmd in ("ssh", "rsync", "python3"):
        found = shutil.which(cmd)
        if not found:
            die(f"{RED}Missing required local tool:{NC} {cmd}")
        print(f"  {GREEN}OK{NC} Local tool: {cmd} ({found})")

    for path in REQUIRED_FILES:
        print(f"  {GREEN}OK{NC} Found file: {path.relative_to(ROOT_DIR)}")

    if IGNORE_FILE.exists():
        print(f"  {GREEN}OK{NC} Found file: {IGNORE_FILE.relative_to(ROOT_DIR)}")

    print(f"  Target: {CYAN}{config.server_user}@{config.server_host}:{config.server_port} ({config.remote_dir}){NC}")
    try:
        out = remote_precheck(config)
    except subprocess.CalledProcessError as exc:
        die(f"{RED}SSH Connection failed to {config.server_host}:{config.server_port}.{NC}\n{exc.stdout or ''}")
    if "===SSH_OK===" not in out:
        die(f"{RED}SSH Connection failed to {config.server_host}:{config.server_port}.{NC}\n{out}")
    print(f"{GREEN}{BOLD}Pre-flight verification completed successfully.{NC}")
    return 0


def command_add(args: argparse.Namespace) -> int:
    existing = set(read_staged_items())
    ordered_items = read_staged_items()
    force = getattr(args, "force", False)
    new_files = expand_paths(args.paths, force=force)

    added_count = 0
    for f in new_files:
        if f not in existing:
            ordered_items.append(f)
            existing.add(f)
            added_count += 1
            print(f"{GREEN}Staged:{NC} {f}")
        else:
            if len(new_files) <= 5:
                print(f"{CYAN}Already staged:{NC} {f}")

    if added_count > 0:
        write_staging(ordered_items)
        if len(new_files) > 5:
            print(f"\n{BOLD}Total added:{NC} {GREEN}{added_count}{NC} file(s).")
    elif not new_files:
        print(f"{YELLOW}No matching files to stage.{NC}")
    else:
        print(f"{CYAN}All specified files are already staged.{NC}")

    print(f"Run {CYAN}ship push{NC} to sync staged items to server.")
    return 0


def command_remove(args: argparse.Namespace) -> int:
    if not args.paths or args.all:
        write_staging([])
        print(f"{GREEN}Staging cleared:{NC} .ship/state/files is now empty.")
        return 0
    existing = read_staged_items()
    for raw_path in args.paths:
        rel_path = normalize_path(raw_path)
        matching = [item for item in existing if item == rel_path or item.startswith(f"{rel_path}/")]
        if matching:
            existing = [item for item in existing if item not in matching]
            for item in matching:
                print(f"{GREEN}Unstaged:{NC} {item}")
        else:
            print(f"{YELLOW}Not found in staging:{NC} {rel_path}")
    write_staging(existing)
    return 0


def command_status(args: argparse.Namespace) -> int:
    config = load_config_or_die()
    print(f"{CYAN}[Status]{NC} Target: {BOLD}{config.server_user}@{config.server_host}:{config.remote_dir}{NC} (depth: {args.depth})", flush=True)
    print(flush=True)
    if shutil.which("tree"):
        patterns = tree_ignore_pattern()
        subprocess.run(["tree", "-L", str(args.depth), "-a", "-I", patterns, "--dirsfirst", "."], cwd=ROOT_DIR, check=False)
    else:
        print("(tree not installed; showing staged files only)")

    print(f"\n{BOLD}=== Staged Files for Deployment (.ship/state/files) ==={NC}")
    items = read_staged_items()
    if not items:
        print(f"{YELLOW}(No files staged. Run 'ship add <path>' or 'ship add .' to stage.){NC}")
        return 0
    for item in items:
        marker = f"{GREEN}OK{NC}" if item == "." or (ROOT_DIR / item).exists() else f"{RED}MISSING{NC}"
        print(f"  {marker} {item}")
    print(f"\nTotal: {BOLD}{len(items)}{NC} path(s) staged ready for push.")
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    config = load_config_or_die()
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
        print(f"{YELLOW}Remote directory {config.remote_dir} does not exist on server.{NC}")
        return 0
    for line in out.splitlines():
        if line == "__SECTION_TREE__":
            print(f"{BOLD}Remote Directory Tree (Depth: {args.tree_level}):{NC}")
        else:
            print(line)
    return 0


def command_push(args: argparse.Namespace) -> int:
    config = load_config_or_die()
    tmp, count = validated_staging_tempfile()
    tmp_path = Path(tmp.name)
    try:
        print(f"{CYAN}-> Target:{NC} {config.server_user}@{config.server_host}:{config.server_port} ({config.remote_dir})")
        opts = ["-azn" if args.dry_run else "-az"]
        if args.verbose:
            opts = ["-azvn" if args.dry_run else "-azv", "--progress"]
        opts.append("-r")
        if args.dry_run:
            print(f"{YELLOW}[DRY-RUN] Simulating push of {count} declared path(s):{NC}")
        else:
            ssh_exec_script(config, 'mkdir -p "$1"', config.remote_dir)
            print(f"Syncing staged items ({count} declared path(s))... ", end="")
        run_command(rsync_argv(config, opts, [f"{ROOT_DIR}/"], files_from=tmp_path))
        if args.dry_run:
            print(f"\n{GREEN}Dry run completed.{NC} No files were modified on server.")
        else:
            print(f"{GREEN}done{NC}")
            print(f"{GREEN}Push completed:{NC} Files uploaded to server.")
        return 0
    finally:
        tmp_path.unlink(missing_ok=True)


def command_clean(args: argparse.Namespace) -> int:
    config = load_config_or_die()
    print(f"{YELLOW}WARNING:{NC} This will permanently delete {BOLD}{config.remote_dir}{NC} on {CYAN}{config.server_host}{NC}.")
    if args.dry_run:
        print(f"{YELLOW}[DRY-RUN] Clean workflow would remove the remote folder.{NC}")
        print(f"{GREEN}Dry run completed.{NC} No files deleted.")
        return 0
    if not args.yes:
        if input("Are you sure you want to proceed? [y/N]: ").strip().lower() != "y":
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
    print(f"{GREEN}Server cleaned:{NC} {BOLD}{config.remote_dir}{NC} permanently deleted.")
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
    p.add_argument("-f", "--force", action="store_true", help="Allow staging of files ignored by .shipignore")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=command_add)

    p = sub.add_parser("remove", aliases=["rm"], help="Remove files or directories from staging")
    p.add_argument("paths", nargs="*")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=command_remove)

    p = sub.add_parser("status", help="Show workspace tree and currently staged items")
    p.add_argument("depth_pos", nargs="?", type=int)
    p.add_argument("-L", "--depth", type=int, default=None)
    p.set_defaults(func=lambda args: command_status(argparse.Namespace(depth=args.depth or args.depth_pos or 2)))

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
        print_err(f"{RED}Error:{NC} {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout, end="")
        print_err(f"{RED}Command failed:{NC} {' '.join(shlex.quote(part) for part in exc.cmd)}")
        return exc.returncode or 1
