#!/usr/bin/env python3
"""ship - Git-like file deployment CLI."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path so tools.* can be resolved
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.commands import (
    build_parser,
    command_add,
    command_clean,
    command_init,
    command_inspect,
    command_preflight,
    command_push,
    command_remove,
    command_status,
    load_config_or_die,
    main,
)
from tools.config import (
    Config,
    allowed_remote_path,
    parse_config_file,
    protected_remote_path,
    read_allowed_remote_paths,
    read_protected_remote_paths,
    validate_remote_dir,
    validate_server_host,
    validate_server_user,
)
from tools.errors import DeployError
from tools.paths import (
    ALLOWED_FILE,
    CONFIG_FILE,
    DENY_FILE,
    GUARDRAIL_DIR,
    IGNORE_FILE,
    PROTECTED_FILE,
    REQUIRED_FILES,
    ROOT_DIR,
    SCRIPT_DIR,
    STAGING_FILE,
    STATE_DIR,
    find_project_root,
    get_context,
)
from tools.policies import deploy_path_denied, forbidden_deploy_path, path_ignored, path_matches_policy, read_policy_patterns, tree_ignore_pattern
from tools.remote import remote_precheck, require_remote_ready
from tools.shell import rsync_argv, run_command, ssh_exec_script
from tools.staging import normalize_path, read_staged_items, validate_staged_item, validated_staging_tempfile, write_staging
from tools.ui import BOLD, CYAN, GREEN, NC, RED, YELLOW, die, print_err

def cli() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    cli()

