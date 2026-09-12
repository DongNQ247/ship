from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from .config import Config
from .policies import rsync_exclude_args


def run_command(argv: list[str], *, input_text: str | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        input=input_text,
        text=True,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def ssh_exec_script(config: Config, script: str, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    remote_cmd = " ".join(["bash", "-se", "--", *(shlex.quote(arg) for arg in args)])
    argv = [
        "ssh",
        "-p",
        str(config.server_port),
        "-o",
        "ConnectTimeout=10",
        config.ssh_target,
        remote_cmd,
    ]
    return run_command(argv, input_text=script, capture=capture)


def rsync_argv(config: Config, opts: list[str], source_args: list[str], *, files_from: Path | None = None) -> list[str]:
    argv = ["rsync", *opts, "-e", f"ssh -p {config.server_port}", *rsync_exclude_args()]
    if files_from is not None:
        argv.append(f"--files-from={files_from}")
    argv.extend(source_args)
    argv.append(f"{config.ssh_target}:{config.remote_dir}/")
    return argv

